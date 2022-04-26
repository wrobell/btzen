#
# BTZen - library to asynchronously access Bluetooth devices.
#
# Copyright (C) 2015-2022 by Artur Wroblewski <wrobell@riseup.net>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

from __future__ import annotations

import asyncio
import contextvars
import logging
import typing as tp
from functools import partial

from . import _btzen  # type: ignore
from . import _sd_bus  # type: ignore
from .config import DEFAULT_CHARACTERISTIC_PATH_RETRY
from .error import BTZenError, ConnectionError

logger = logging.getLogger(__name__)

INTERFACE_DEVICE = 'org.bluez.Device1'
INTERFACE_GATT_CHR = 'org.bluez.GattCharacteristic1'

def _mac_to_path(mac: str) -> str:
    return mac.replace(':', '_').upper()

class Bus:
    BUS = contextvars.ContextVar[tp.Optional['Bus']]('BUS', default=None)

    def __init__(self, system_bus: _sd_bus.Bus, interface: str) -> None:
        self.system_bus = system_bus
        self.interface = interface

        loop = asyncio.get_event_loop()
        process = partial(_btzen.bt_process, system_bus)
        loop.add_reader(system_bus.fileno, process)

        self._notifications = Notifications(self)
        self._characteristic_cache: dict[tuple[str, str], str] = {}

    @staticmethod
    def create_bus(interface: str) -> Bus:
        """
        Create system bus reference.

        The reference is local to current context.

        :param interface: Bluetooth interface, i.e. `hci0`.
        """
        bus = Bus.BUS.get()
        if bus is None:
            system_bus = _sd_bus.default_bus()
            bus = Bus(system_bus, interface)
            Bus.BUS.set(bus)
        else:
            raise ValueError('Bus already exists')

        return bus

    @staticmethod
    def get_bus() -> Bus:
        """
        Get system bus reference from current context.
        """
        bus = Bus.BUS.get()
        if bus is None:
            raise ValueError('Bus does not exist')
        return bus

    def characteristic_path(self, mac: str, uuid: str) -> str:
        """
        Get Bluetooth GATT Characteristic path for Bluetooth device address
        and GATT Characteristic UUID.

        The paths are cached.

        :param mac: Bluetooth device MAC address.
        :param uuid: UUID of Bluetooth GATT Characteristic.
        """
        key = mac, uuid
        prefix = self.dev_path(mac)
        path = self._characteristic_cache.get(key)
        if path is None:
            path = _btzen.bt_characteristic(self.system_bus, prefix, uuid)

        # store in cache only non-null values
        if path is None:
            raise BTZenError('Path for {}/{} not found'.format(mac, uuid))
        else:
            self._characteristic_cache[key] = path
        return path

    async def ensure_characteristic_paths(self, mac: str, *uuid: str) -> None:
        """
        Ensure Bluetooth GATT characteristic path exists for each UUID.
        """
        # TODO: in the future we might want to use object manager
        for u in uuid:
            await self.ensure_characteristic_path(mac, u)

    async def ensure_characteristic_path(self, mac: str, uuid: str) -> None:
        key = mac, uuid
        prefix = self.dev_path(mac)
        for i in range(DEFAULT_CHARACTERISTIC_PATH_RETRY):
            path = _btzen.bt_characteristic(self.system_bus, prefix, uuid)
            if path is None:
                logger.warning(
                    'characteristic path not found for {}/{}'.format(mac, uuid)
                )
                await asyncio.sleep(1)
            else:
                self._characteristic_cache[key] = path
                return

        raise BTZenError(
            'Cannot determine characteristic path for {}/{}'.format(mac, uuid)
        )

    def _gatt_start(self, path: str) -> None:
        # TODO: creates notification session; if another session started,
        # then we get notifications twice; this needs to be fixed
        self._notifications.start(path, INTERFACE_GATT_CHR, 'Value')
        try:
            _btzen.bt_notify_start(self.system_bus, path)
        except Exception as ex:
            logger.warning('cannot start notification for {}: {}'.format(path, ex))
            self._notifications.stop(path, INTERFACE_GATT_CHR)
            raise

    def adapter_path(self) -> str:
        return '/org/bluez/{}'.format(self.interface)

    def dev_path(self, mac: str) -> str:
        return '/org/bluez/{}/dev_{}'.format(self.interface, _mac_to_path(mac))

    async def _gatt_get(self, path: str) -> tp.Any:
        task = self._notifications.get(path, INTERFACE_GATT_CHR, 'Value')
        return (await task)

    def _gatt_stop(self, path: str) -> None:
        try:
            _btzen.bt_notify_stop(self.system_bus, path)
        except Exception as ex:
            logger.warning('cannot stop notification for {}: {}'.format(path, ex))
        finally:
            self._notifications.stop(path, INTERFACE_GATT_CHR)

    def _gatt_size(self, path: str) -> int:
        return self._notifications.size(path, INTERFACE_GATT_CHR, 'Value')

    def _dev_property_start(
        self, mac: str, name: str, iface: str=INTERFACE_DEVICE
    ) -> None:
        path = self.dev_path(mac)
        self._notifications.start(path, iface, name)

    async def _dev_property_get(
            self,
            mac: str,
            name: str,
            iface: str=INTERFACE_DEVICE,
    ) -> tp.Any:
        path = self.dev_path(mac)
        value = await self._notifications.get(path, iface, name)
        return value

    def _dev_property_stop(
        self, mac: str, name: str, iface: str=INTERFACE_DEVICE
    ) -> None:
        path = self.dev_path(mac)
        self._notifications.stop(path, iface)

    async def _property(
        self, mac: str, iface: str, name: str, type: str='s'
    ) -> tp.Any:
        bus = self.system_bus
        path = self.dev_path(mac)
        value = await _btzen.bt_property(bus, path, iface, name, type)
        return value

    async def _get_name(self, mac: str) -> str:
        path = self.dev_path(mac)
        bus = self.system_bus
        value = await _btzen.bt_property(bus, path, INTERFACE_DEVICE, 'Name', 's')
        return value  # type: ignore

class Notifications:
    def __init__(self, bus: Bus):
        self._data: dict[tuple[str, str], _btzen.PropertyNotification] = {}
        self._bus = bus

    def start(self, path: str, iface: str, name: str) -> None:
        key = path, iface
        bus = self._bus.system_bus

        assert key not in self._data
        data = _btzen.bt_property_monitor_start(bus, path, iface)
        self._data[key] = data

        assert key in self._data
        data.register(name)

    def size(self, path: str, iface: str, name: str) -> int:
        key = path, iface
        return self._data[key].size(name)  # type: ignore

    async def get(self, path: str, iface: str, name: str) -> tp.Any:
        key = path, iface
        data = self._data[key]
        return (await data.get(name))

    def stop(self, path: str, iface: str) -> None:
        # TODO: add name and call PropertyNotification.stop when no
        # properties monitored
        key = path, iface
        if key in self._data:
            self._data[key].stop()
            del self._data[key]

        assert key not in self._data

# vim: sw=4:et:ai
