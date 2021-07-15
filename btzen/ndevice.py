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

import asyncio
import enum
import logging
import typing as tp
import dataclasses as dtc
from collections import defaultdict
from functools import singledispatch

from . import _btzen  # type: ignore
from .bus import Bus
from .config import DEFAULT_DBUS_TIMEOUT
from .error import CallError
from .util import to_int

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

def accelerometer(mac: str, make: Make=Make.STANDARD) -> DeviceRegistration:
    return register_device(from_registry(make, DeviceType.ACCELEROMETER), mac)

def button(mac: str, make: Make=Make.STANDARD) -> DeviceRegistration:
    return register_device(from_registry(make, DeviceType.BUTTON), mac)

async def read(device: DeviceRegistration) -> tp.Any:
    from .cm import CM_STOP, connected
    mac = device.mac

    if CM_STOP.get():
        raise CallError('btzen is not running for device {}'.format(device))

    await connected(mac)
    if CM_STOP.get():
        return

    return (await read_data(device.device, mac))


@singledispatch
async def read_data(device: DeviceAny, mac: str) -> T:
    pass

@read_data.register
async def _read_env_sensing(device: DeviceCharacteristic, mac: str) -> T:
    bus = Bus.get_bus('hci0')  # FIXME: no hci0
    path = bus.characteristic_path(mac, device.uuid_data)
    assert path is not None

    data = await _btzen.bt_read(bus.system_bus, path, DEFAULT_DBUS_TIMEOUT)
    return device.convert(data)
    # TODO: await asyncio.ensure_future(self._read_data())

@read_data.register
async def _read_dev_notifying(device: DeviceNotifying, mac: str) -> T:
    bus = Bus.get_bus('hci0')
    dev = device.device
    path = bus.characteristic_path(mac, dev.uuid_data)
    data = await bus._gatt_get(path)
    return dev.convert(data)

@singledispatch
async def enable(device: DeviceAny, mac: str):
    pass

@singledispatch
async def disable(device: DeviceAny, mac: str):
    pass

@enable.register
async def _enable_env_sensing(device: DeviceEnvSensing, mac: str):
    await write_config(mac, device.uuid_conf, device.config_on)

@enable.register
async def _enable_dev_notifying(device: DeviceNotifying, mac: str):
    bus = Bus.get_bus('hci0')
    dev = device.device
    await enable(dev, mac)
    path = bus.characteristic_path(mac, dev.uuid_data)
    bus._gatt_start(path)
    logger.info('notifications enabled for {}'.format(path))

@disable.register
async def _disable_env_sensing(device: DeviceEnvSensing, mac: str):
    await disarm(
        'device {}/{} disabled'.format(mac, device),
        'cannot disable device {}/{}'.format(mac, device),
        write_config, mac, device.uuid_conf, device.config_off
    )

@disable.register
async def _disable_dev_notifying(device: DeviceNotifying, mac: str):
    bus = Bus.get_bus('hci0')
    dev = device.device
    path = bus.characteristic_path(mac, dev.uuid_data)
    assert path is not None
    await disarm(
        'notifications for {}/{} are disabled'.format(mac, device),
        'cannot disable notifications for {}/{}'.format(mac, device),
        bus._gatt_stop, path
    )
    await disable(dev, mac)

async def write_config(mac: str, uuid_conf: str, data: bytes):
    bus = Bus.get_bus('hci0')
    path = bus.characteristic_path(mac, uuid_conf)
    await _btzen.bt_write(
        bus.system_bus, path, data, DEFAULT_DBUS_TIMEOUT
    )

async def disarm(msg: str, warn: str, f, *args):
    try:
        await f(*args)
        logger.info(msg)
    except (Exception, asyncio.CancelledError) as ex:
        logger.warning(warn + ': ' + str(ex))

# vim: sw=4:et:ai
