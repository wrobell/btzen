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

"""
Generic access to Bluetooth devices.

See also

    https://www.bluetooth.com/specifications/gatt/characteristics
"""

import asyncio
import enum
import logging
import typing as tp
from dataclasses import dataclass
from functools import partial

from . import _btzen  # type: ignore
from .bus import Bus
from .error import CallError

logger = logging.getLogger(__name__)

# function to convert 16-bit UUID to full 128-bit Bluetooth normative UUID
# string
to_uuid: tp.Callable[[int], str] = '0000{:04x}-0000-1000-8000-00805f9b34fb'.format

@dataclass(frozen=True)
class Info:
    """
    Bluetooth device information.

    :var service: UUID of Bluetooth service.
    """
    service: str

@dataclass(frozen=True)
class InfoInterface(Info):
    """
    Bluetooth device information for device providing data via Bluez
    interface property.

    Example of interface for Battery Level Bluetooth characteristic is
    `org.bluez.Battery1` Bluez interface, which provides data via
    `Percentage` property.

    :var interface: Bluez interface name.
    :var property: Property name of the interface.
    :var type: Type of property value.
    """
    interface: str
    property: str
    type: str

@dataclass(frozen=True)
class InfoCharacteristic(Info):
    """
    Bluetooth device information for device providing data via Bluetooth
    characteristic.

    :var uuid_data: UUID of characteristic to read data from.
    :var size: Length of data received from Bluetooth characteristic on
        read.
    """
    uuid_data: str
    size: int

@dataclass(frozen=True)
class InfoEnvSensing(InfoCharacteristic):
    """
    Bluetooth device information for device providing data via Bluetooth
    Environmental Sensing characteristic.

    :var uuid_conf: UUID of characteristic to write and read device
        configuration.
    :var uuid_trigger: UUID of characteristic to write and read device
        trigger data.
    :var config_on: Default configuration of device to switch device on.
    :var config_notify_on: Default configuration of device to switch device
        on in notifying mode. If none, then `config_on` is used.
    :var config_off: Default configuration of device to switch device off.
    """
    uuid_conf: tp.Optional[str] = None
    uuid_trigger: tp.Optional[str] = None
    config_on: tp.Optional[bytes] = None
    config_on_notify: tp.Optional[bytes] = None
    config_off: tp.Optional[bytes] = None

class Device:
    """
    Base class for all Bluetooth devices.

    :var mac: Address of Bluetooth device.
    :var notifying: Indicates if data is read in notifying mode.
    """
    def __init__(self, mac, *, notifying=False):
        self.mac = mac
        self.notifying = notifying

        self._bus = None
        self._cm = None
        self._task = None

    async def enable(self):
        """
        Enable Bluetooth device.

        If a Bluetooth device is connected or reconnected, the enable
        method shall be called to configure/reconfigure the device.
        """
        raise NotImplementedError('Enable method is not implemented')

    async def read(self) -> tp.Any:
        """
        Read data from Bluetooth device.

        The coroutine can raise cancellation error (`asyncio.CancelledError`),
        i.e. when the device is disconnected. The caller should handle the
        error, if it wants to continue reading data when the device is
        reconnected.
        """
        await self._cm.connected(self.mac)

        if self._task is not None:
            raise CallError('device {} is still executing'.format(self))

        self._task = asyncio.create_task(self._read_data())
        try:
            data = await self._task
        except asyncio.CancelledError as ex:
            logger.info('{} cancelled'.format(self))
            raise
        else:
            return self.get_value(data)
        finally:
            self._task = None

    async def _read_data(self):
        """
        Low-level method to read data from Bluetooth device.
        """
        raise NotImplementedError('Read data method is not implemented')

    def get_value(self, data):
        """
        Convert data returned by Bluetooth device into value.

        By default no conversion is performed.
        """
        return data

    def disable(self):
        """
        Disable Bluetooth device.

        If a Bluetooth device is disconnected, then disable method shall be
        called to release any resources held by the device.
        """
        if self._task is not None:
            self._task.cancel()

        self._task = None
        logger.info('device {} disabled'.format(self))

    def close(self):
        """
        Disable device and stop reading its data.

        Pending, asynchronous coroutines are closed.
        """
        self.disable()
        logger.info('device {} closed'.format(self))

    def __repr__(self):
        return '{}/{}'.format(self.mac, self.__class__.__name__)

class DeviceInterface(Device):
    """
    Bluetooth device reading data from Bluez interface property.
    """
    info: InfoInterface

    def __init__(self, mac, *, notifying=False):
        super().__init__(mac, notifying=notifying)

        self._params = {
            'mac': self.mac,
            'name': self.info.property,
            'iface': self.info.interface,
        }

    async def enable(self):
        logger.info('enabling device: {}'.format(self))
        if self.notifying:
            self._bus._dev_property_start(**self._params)
        logger.info('enabled device: {}'.format(self))

    async def _read_data(self):
        if self.notifying:
            task = self._bus._dev_property_get(**self._params)
        else:
            task = self._bus._property(**self._params, type=self.info.type)
        return (await task)

    def disable(self):
        if self.notifying:
            try:
                self._bus._dev_property_stop(**self._params)
            except Exception as ex:
                logger.warning('cannot stop notifications: {}'.format(ex))

        super().disable()

class DeviceCharacteristic(Device):
    """
    Bluetooth device reading data from Bluetooth characteristic.
    """
    info: InfoCharacteristic

    def __init__(self, mac, *, notifying=False):
        super().__init__(mac, notifying=notifying)

        self._path_data = None

    async def enable(self):
        logger.info('enabling device: {}'.format(self))
        self._path_data = self._get_path(self.info.uuid_data)

        await self._configure()
        if self.notifying:
            self._bus._gatt_start(self._path_data)

        logger.info('enabled device: {}'.format(self))

    def disable(self):
        if self.notifying:
            try:
                self._bus._gatt_stop(self._path_data)
            except Exception as ex:
                logger.warning('cannot stop notifications: {}'.format(ex))

        super().disable()

    async def _configure(self):
        return None

    async def _read_data(self):
        if self.notifying:
            task = self._bus._gatt_get(self._path_data)
        else:
            task = _btzen.bt_read(self._bus.system_bus, self._path_data)
        return (await task)

    def _get_path(self, uuid):
        return self._bus.characteristic_path(self.mac, uuid)

class DeviceEnvSensing(DeviceCharacteristic):
    """
    Bluetooth device providing data via Bluetooth Environmental Sensing
    characteristic.
    """
    info: InfoEnvSensing

    def __init__(self, mac, notifying=False):
        super().__init__(mac, notifying=notifying)

        self._path_conf = None
        self._path_trigger = None
        self._trigger = None

    def set_trigger(self, trigger: 'Trigger'):
        """
        Set Bluetooth Environmental Sensing device trigger data.

        NOTE: The specification supports up to three triggers.

        :param trigger: Information for first trigger.
        """
        self._trigger = trigger

    def set_interval(self, interval: float) -> None:
        """
        Set fixed time interval for Bluetooth Environmental Sensing device.

        This is equivalent to::

            set_trigger(Trigger(TriggerCondition.FIXED_TIME, interval))

        :param interval: Interval in seconds.
        """
        self.set_trigger(Trigger(TriggerCondition.FIXED_TIME, interval))

    def close(self):
        super().close()

        info = self.info
        system_bus = self._bus.system_bus
        if info.config_off:
            try:
                _btzen.bt_write_sync(system_bus, self._path_conf, info.config_off)
            except Exception as ex:
                logger.warning('cannot switch device off: {}'.format(ex))

    async def _configure(self):
        info = self.info

        config_on = info.config_on_notify if self.notifying else info.config_on
        if config_on:
            self._path_conf = self._get_path(info.uuid_conf)

            if __debug__:
                logger.debug(
                    'writing {} configuration data to {}'
                    .format(config_on, self._path_conf)
                )
            await self._write(self._path_conf, config_on)

        path = self._path_trigger = self._get_path(info.uuid_trigger)
        data = self._trigger_data(self._trigger)
        if path is not None and data is not None:
            await self._write(path, data)
        else:
            logger.warning('setting trigger for {} not supported'.format(self))

    def _trigger_data(self, trigger: 'Trigger') -> tp.Optional[bytes]:
        """
        Convert Bluetooth Environmental Sensing device trigger information
        into raw data.

        ;param: Trigger information.
        """
        return None

    async def _write(self, path: str, data: bytes) -> None:
        await _btzen.bt_write(self._bus.system_bus, path, data)


class BatteryLevel(DeviceInterface):
    """
    The current charge level of a Bluetooth device battery.
    """
    info = InfoInterface(
        to_uuid(0x180f),
        'org.bluez.Battery1',
        'Percentage',
        'y'
    )

class TriggerCondition(enum.IntEnum):
    """
    Condition value for Bluetooth Environmental Sensing device trigger
    information.

    NOTE: Incomplete, see Bluetooth Environmental Sensing Service
        specification, page 18..
    """
    INACTIVE = 0x00
    FIXED_TIME = 0x01

@dataclass(frozen=True)
class Trigger:
    """
    Bluetooth Environmental Sensing device trigger information.
    """
    condition: TriggerCondition
    operand: tp.Any

# vim: sw=4:et:ai
