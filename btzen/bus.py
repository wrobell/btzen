#
# BTZen - library to asynchronously access Bluetooth devices.
#
# Copyright (C) 2015-2020 by Artur Wroblewski <wrobell@riseup.net>
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

import asyncio
import contextvars
import logging
from functools import partial

from . import _btzen
from . import _sd_bus
from .error import ConnectionError

logger = logging.getLogger(__name__)

INTERFACE_DEVICE = 'org.bluez.Device1'
INTERFACE_GATT_CHR = 'org.bluez.GattCharacteristic1'

def _mac_to_path(mac):
    return mac.replace(':', '_').upper()

class Bus:
    bus = contextvars.ContextVar('bus', default=None)

    def __init__(self, system_bus, interface):
        self.system_bus = system_bus
        self.interface = interface

        loop = asyncio.get_event_loop()
        process = partial(_btzen.bt_process, system_bus)
        loop.add_reader(system_bus.fileno, process)

        self._notifications = Notifications(self)

    @staticmethod
    def get_bus(interface: str) -> 'Bus':
        """
        Get system bus reference.

        The reference is local to current thread.

        :param interface: Bluetooth interface, i.e. `hci0`.
        """
        bus = Bus.bus.get()
        if bus is None:
            system_bus = _sd_bus.default_bus()
            bus = Bus(system_bus, interface)
            Bus.bus.set(bus)
        return bus

    def characteristic_path(self, mac, uuid):
        prefix = self.dev_path(mac)
        return _btzen.bt_characteristic(self.system_bus, prefix, uuid)

    def _gatt_start(self, path):
        # TODO: creates notification session; if another session started,
        # then we get notifications twice; this needs to be fixed
        self._notifications.start(path, INTERFACE_GATT_CHR, 'Value')
        _btzen.bt_notify_start(self.system_bus, path)

    def dev_path(self, mac):
        return '/org/bluez/{}/dev_{}'.format(self.interface, _mac_to_path(mac))

    async def _gatt_get(self, path, timeout=0):
        task = self._notifications.get(path, INTERFACE_GATT_CHR, 'Value')
        return (await task)

    def _gatt_stop(self, path):
        _btzen.bt_notify_stop(self.system_bus, path)
        self._notifications.stop(path, INTERFACE_GATT_CHR)

    def _gatt_size(self, path) -> int:
        return self._notifications.size(path, INTERFACE_GATT_CHR, 'Value')

    def _dev_property_start(self, mac, name, iface=INTERFACE_DEVICE):
        path = self.dev_path(mac)
        self._notifications.start(path, iface, name)

    async def _dev_property_get(
            self,
            mac,
            name,
            iface=INTERFACE_DEVICE,
            timeout=0
        ):
        path = self.dev_path(mac)
        value = await self._notifications.get(path, iface, name)
        return value

    def _dev_property_stop(self, mac, name, iface=INTERFACE_DEVICE):
        path = self.dev_path(mac)
        self._notifications.stop(path, iface)

    async def _property(self, mac, iface, name, type='s', timeout=0):
        bus = self.system_bus
        path = self.dev_path(mac)
        value = await _btzen.bt_property(bus, path, iface, name, type)
        return value

    async def _get_name(self, mac):
        path = self.dev_path(mac)
        bus = self.system_bus
        value = await _btzen.bt_property(bus, path, INTERFACE_DEVICE, 'Name', 's')
        return value

class Notifications:
    def __init__(self, bus):
        self._data = {}
        self._bus = bus

    def start(self, path, iface, name):
        key = path, iface
        data = self._data.get(key)
        if data is None:
            bus = self._bus.system_bus
            data = _btzen.bt_property_monitor_start(bus, path, iface)
            self._data[key] = data

        assert key in self._data
        if not data.is_registered(name):
            data.register(name)

    def size(self, path, iface, name):
        key = path, iface
        return self._data[key].size(name)

    async def get(self, path, iface, name):
        key = path, iface
        data = self._data[key]
        return (await data.get(name))

    def stop(self, path, iface):
        # TODO: add name and call PropertyNotification.stop when no
        # properties monitored
        key = path, iface
        data = self._data[key].stop()

# vim: sw=4:et:ai
