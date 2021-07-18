#
# BTZen - library to asynchronously access Bluetooth devices.
#
# Copyright (C) 2015-2021 by Artur Wroblewski <wrobell@riseup.net>
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

import enum
import logging
import typing as tp
import dataclasses as dtc
from collections import defaultdict

logger = logging.getLogger(__name__)

# registry of known devices
REGISTRY: dict[Make, dict[DeviceType, Device]] = defaultdict(dict)

T = tp.TypeVar('T')
DeviceAny = tp.Union['Device[T]', 'DeviceNotifying[T]']

class Make(enum.Enum):
    """
    Bluetooth device make.
    """
    STANDARD = enum.auto()
    SENSOR_TAG = enum.auto()
    THINGY52 = enum.auto()

class DeviceType(enum.Enum):
    """
    Bluetooth device type.
    """
    PRESSURE = enum.auto()
    TEMPERATURE = enum.auto()
    HUMIDITY = enum.auto()
    LIGHT = enum.auto()
    ACCELEROMETER = enum.auto()
    BUTTON = enum.auto()
    WEIGHT_MEASUREMENT = enum.auto()

class AddressType(enum.Enum):
    """
    Bluetooth device address type.


    .. seealso::

        `ConnectDevice` method documentation at
        https://git.kernel.org/pub/scm/bluetooth/bluez.git/tree/doc/adapter-api.txt.
    """
    PUBLIC = 'public'
    RANDOM = 'random'

@dtc.dataclass(frozen=True)
class Device(tp.Generic[T]):
    """
    Bluetooth device descriptor.

    :var service: UUID of Bluetooth service.
    :var convert: Function to convert binary device data to value.
    """
    service: str
    convert: tp.Callable[[bytes], T]

    def __str__(self):
        return "{}('{}')".format(self.__class__.__name__, self.service)

@dtc.dataclass(frozen=True)
class DeviceNotifying(tp.Generic[T]):
    """
    Bluetooth device descriptor for a device reading data via
    notifications.

    :var device: Bluetooth device descriptor.
    """
    device: T  # TODO: T == Device[T]

    @property
    def service(self):
        return self.device.service

    def __str__(self):
        return "Device('{}')".format(self.service)

@dtc.dataclass(frozen=True)
class DeviceCharacteristic(Device[T]):
    """
    Bluetooth device information for device providing data via Bluetooth
    characteristic.

    :var uuid_data: UUID of characteristic to read data from.
    :var size: Length of data received from Bluetooth characteristic on
        read.
    """
    uuid_data: str
    size: int

    def __str__(self):
        return super().__str__()

@dtc.dataclass(frozen=True)
class DeviceEnvSensing(DeviceCharacteristic[T]):
    """
    Bluetooth device information for device providing data via Bluetooth
    Environmental Sensing characteristic.

    :var uuid_conf: UUID of characteristic to write and read device
        configuration.
    :var uuid_trigger: UUID of characteristic to write and read device
        trigger data.
    :var config_on: Default configuration of device to switch device on.
    :var config_off: Default configuration of device to switch device off.
    """
    uuid_conf: str
    uuid_trigger: str
    config_on: bytes
    config_off: bytes

    def __str__(self):
        return super().__str__()

@dtc.dataclass(frozen=True)
class DeviceRegistration:
    """
    Bluetooth device connection information.

    Associates Bluetooth device MAC address and address type with a device.

    :var device: Bluetooth device descriptor.
    :var mac: MAC address of Bluetooth device.
    :var address_type: Bluetooth device address type.
    """
    device: Device
    mac: str
    address_type: AddressType = AddressType.PUBLIC

    def __str__(self):
        return "DeviceRegistration('{}', '{}')".format(self.mac, self.device)


def from_registry(make: Make, dev_type: DeviceType):
    return REGISTRY[make][dev_type]

def register(make: Make, dev_type: DeviceType, dev):
    REGISTRY[make][dev_type] = dev

def register_device(device: Device, mac: str, address_type: AddressType=AddressType.PUBLIC) -> DeviceRegistration:
    return DeviceRegistration(device, mac, address_type=address_type)

def pressure(mac: str, make: Make=Make.STANDARD) -> DeviceRegistration:
    return register_device(from_registry(make, DeviceType.PRESSURE), mac)

def temperature(mac: str, make: Make=Make.STANDARD) -> DeviceRegistration:
    return register_device(from_registry(make, DeviceType.TEMPERATURE), mac)

def humidity(mac: str, make: Make=Make.STANDARD) -> DeviceRegistration:
    return register_device(from_registry(make, DeviceType.HUMIDITY), mac)

def light(mac: str, make: Make=Make.STANDARD) -> DeviceRegistration:
    return register_device(from_registry(make, DeviceType.LIGHT), mac)

def accelerometer(mac: str, make: Make=Make.STANDARD) -> DeviceRegistration:
    return register_device(from_registry(make, DeviceType.ACCELEROMETER), mac)

def button(mac: str, make: Make=Make.STANDARD) -> DeviceRegistration:
    return register_device(from_registry(make, DeviceType.BUTTON), mac)

# vim: sw=4:et:ai
