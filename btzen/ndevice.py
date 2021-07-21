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
REGISTRY = defaultdict['Make', dict['ServiceType', 'Device']](dict)

T = tp.TypeVar('T')
ServiceAny = tp.Union['Service[T]', 'ServiceNotifying[T]']

class Make(enum.Enum):
    """
    Bluetooth device make.
    """
    STANDARD = enum.auto()
    SENSOR_TAG = enum.auto()
    THINGY52 = enum.auto()

class ServiceType(enum.Enum):
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

    :var service: Bluetooth service descriptor.
    :var mac: MAC address of Bluetooth device.
    :var address_type: Bluetooth device address type.
    """
    service: Service[T]
    mac: str
    address_type: AddressType = AddressType.PUBLIC

    def __str__(self) -> str:
        return "Device('{}', '{}')".format(self.mac, self.service)

@dtc.dataclass(frozen=True)
class Service(tp.Generic[T]):
    """
    Bluetooth service descriptor.

    :var uuid: UUID of Bluetooth service.
    :var convert: Function to convert binary data provided by service
        to a value.
    """
    uuid: str
    convert: tp.Callable[[bytes], T]

    def __str__(self):
        return "{}('{}')".format(self.__class__.__name__, self.uuid)

@dtc.dataclass(frozen=True)
class ServiceNotifying(tp.Generic[T]):
    """
    Bluetooth service descriptor for a service providing data via
    notifications.

    :var service: Bluetooth service descriptor.
    :var trigger: Trigger for the service.
    """
    service: ServiceCharacteristic[T]
    trigger: Trigger

    @property
    def uuid(self):
        return self.service.uuid

    def __str__(self):
        return "ServiceNotifying('{}')".format(self.service)

@dtc.dataclass(frozen=True)
class ServiceCharacteristic(Service[T]):
    """
    Bluetooth service descriptor for Bluetooth characteristic.

    :var uuid_data: UUID of characteristic to read data from.
    :var size: Length of data received from Bluetooth characteristic on
        read.
    """
    uuid_data: str
    size: int

    def __str__(self):
        return super().__str__()

@dtc.dataclass(frozen=True)
class ServiceEnvSensing(ServiceCharacteristic[T]):
    """
    Bluetooth service descriptor for Bluetooth Environmental Sensing
    characteristic.

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

class TriggerCondition(enum.IntEnum):
    """
    Condition value for Bluetooth Environmental Sensing device trigger
    information.

    NOTE: Incomplete, see Bluetooth Environmental Sensing Service
        specification, page 18.
    """
    INACTIVE = 0x00
    FIXED_TIME = 0x01

@dtc.dataclass(frozen=True)
class Trigger:
    """
    Bluetooth Environmental Sensing device trigger information.
    """
    condition: TriggerCondition
    operand: tp.Optional[float]=None

def from_registry(make: Make, service_type: ServiceType):
    return REGISTRY[make][service_type]

def register_service(make: Make, service_type: ServiceType, service):
    REGISTRY[make][service_type] = service

def create_device(
        service: Service, mac: str, address_type: AddressType=AddressType.PUBLIC
    ) -> Device:
    """
    Create Bluetooth device for a Bluetooth service.
    """
    return Device(service, mac, address_type=address_type)

def pressure(mac: str, make: Make=Make.STANDARD) -> Device:
    return create_device(from_registry(make, ServiceType.PRESSURE), mac)

def temperature(mac: str, make: Make=Make.STANDARD) -> Device:
    return create_device(from_registry(make, ServiceType.TEMPERATURE), mac)

def humidity(mac: str, make: Make=Make.STANDARD) -> Device:
    return create_device(from_registry(make, ServiceType.HUMIDITY), mac)

def light(mac: str, make: Make=Make.STANDARD) -> Device:
    return create_device(from_registry(make, ServiceType.LIGHT), mac)

def accelerometer(mac: str, make: Make=Make.STANDARD) -> Device:
    return create_device(from_registry(make, ServiceType.ACCELEROMETER), mac)

def button(mac: str, make: Make=Make.STANDARD) -> Device:
    return create_device(from_registry(make, ServiceType.BUTTON), mac)

# vim: sw=4:et:ai
