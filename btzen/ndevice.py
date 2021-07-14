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
import typing as tp
import dataclasses as dtc
from collections import defaultdict
from functools import singledispatch

from . import _btzen  # type: ignore
from .bus import Bus
from .config import DEFAULT_DBUS_TIMEOUT
from .error import CallError
from .util import to_int

# registry of known devices
REGISTRY: dict[Make, dict[DeviceType, Device]] = defaultdict(dict)

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
class Device:
    """
    Bluetooth device descriptor.

    :var service: UUID of Bluetooth service.
    """
    service: str

@dtc.dataclass(frozen=True)
class DeviceCharacteristic(Device):
    """
    Bluetooth device information for device providing data via Bluetooth
    characteristic.

    :var uuid_data: UUID of characteristic to read data from.
    :var size: Length of data received from Bluetooth characteristic on
        read.
    """
    uuid_data: str
    size: int

@dtc.dataclass(frozen=True)
class DeviceEnvSensing(DeviceCharacteristic):
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
    config_off: tp.Optional[bytes] = None

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

@singledispatch
async def read(device: DeviceRegistration) -> tp.Any:
    from .cm import CM_STOP, connected
    bus = Bus.get_bus('hci0')  # FIXME: no hci0
    mac = device.mac

    if CM_STOP.get():
        raise CallError('btzen is not running for device {}'.format(device))

    await connected(mac)
    if CM_STOP.get():
        return

    path = bus.characteristic_path(mac, device.device.uuid_data)
    data = await _btzen.bt_read(bus.system_bus, path, DEFAULT_DBUS_TIMEOUT)
    return to_int(data[3:])
    #await asyncio.ensure_future(self._read_data())

@singledispatch
async def enable(device: Device, mac: str):
    pass

@singledispatch
async def disable(device: Device, mac: str):
    pass

@enable.register
async def _enable_env_sensing(device: DeviceEnvSensing, mac: str):
    await write_config(mac, device.uuid_conf, device.config_on)

@disable.register
async def _disable_env_sensing(device: DeviceEnvSensing, mac: str):
    await write_config(mac, device.uuid_conf, device.config_off)

async def write_config(mac: str, uuid_conf: str, data: bytes):
    bus = Bus.get_bus('hci0')
    path = bus.characteristic_path(mac, uuid_conf)
    await _btzen.bt_write(
        bus.system_bus, path, data, DEFAULT_DBUS_TIMEOUT
    )

# vim: sw=4:et:ai
