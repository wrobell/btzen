#
# BTZen - Bluetooth Smart sensor reading library.
#
# Copyright (C) 2015-2018 by Artur Wroblewski <wrobell@riseup.net>
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

import typing as tp
from dataclasses import dataclass
from functools import partial

from .bus import Bus

# function to convert 16-bit UUID to full 128-bit Bluetooth normative UUID
# string
to_uuid = '0000{:04x}-0000-1000-8000-00805f9b34fb'.format

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
    Bluetooth device information for device reading data from Bluez
    interface property.

    Example of interface for Battery Level Bluetooth characteristics is
    `org.bluez.Battery1` Bluez interface, which provides data via
    `Percentage` property.

    :var interface: Bluez interface name.
    :var property: Property name of the interface.
    :var type: Type of 
    """
    interface: str
    property: str
    type: str

class Device:
    """
    Base class for all Bluetooth devices.

    :var mac: Address of Bluetooth device.
    :var notifying: Indicates if data is read in notifying mode.
    """
    def __init__(self, mac, *, notifying=False):
        self.mac = mac
        self.notifying = notifying

        self._bus = Bus.get_bus()
        self._cm = None

    async def enable(self):
        """
        Enable Bluetooth device.

        If a Bluetooth device is connected or reconnected, the enable
        method shall be called to configure/reconfigure the device.
        """
        raise NotImplementedError('Enable method is not implemented')

    async def read(self):
        """
        Read data from Bluetooth device.

        If device is in notifying mode, the data might be returned after
        long period of time.
        """
        raise NotImplementedError('Read method is not implemented')

    def close(sef):
        """
        Disable device and stop reading its data.

        Pending, asynchronous coroutines are closed.
        """
        raise NotImplementedError('Close method is not implemented')

class DeviceInterface(Device):
    """
    Bluetooth device reading data from Bluez interface property.
    """
    info: InfoInterface

    def __init__(self, mac, *, notifying=False):
        super().__init__(mac, notifying=notifying)

        self._mac = mac  # FIXME: remove
        self._enable = self.enable
        self._interval = 0

        self._params = {
            'mac': self.mac,
            'name': self.info.property,
            'iface': self.info.interface,
        }

        read_notify = partial(self._bus._dev_property_get, **self._params)
        read = partial(self._bus._property, **self._params, type=self.info.type)
        self._read_data = read_notify if notifying else read

    async def enable(self):
        if self.notifying:
            self._bus._dev_property_start(**self._params)

    async def read(self):
        await self._cm.connected(self.mac)
        return (await self._read_data())

    def close(self):
        if self.notifying:
            self._bus._dev_property_stop(**self._params)

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

    UUID_SERVICE = to_uuid(0x180f)

# vim: sw=4:et:ai
