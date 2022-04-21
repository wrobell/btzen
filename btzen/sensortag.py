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

"""
Texas Instrument Sensor Tag Bluetooth device sensors.

The sensors do not implement the Bluetooth Environmental Sensing interfaces
and require some custom implementation.

The sensors on device read data at certain time interval (period), usually
one second. Functions `set_interval` or `set_trigger` change this interval.
To change the time interval for a device with inactive trigger, use
`dataclasses.replace` function.

The identificators for specific sensors can be found at

CC2541DK
    http://processors.wiki.ti.com/index.php/SensorTag_User_Guide
CC2650STK
    http://processors.wiki.ti.com/index.php/CC2650_SensorTag_User's_Guide
"""

import asyncio
import dataclasses as dtc
import enum
import logging
import struct
import typing as tp
from functools import partial

from .data import T, Button, Make, ServiceType, Trigger, TriggerCondition
from .device import Device, DeviceTrigger
from .devio import enable, disable, write_config, disarm, \
    _enable_dev_trigger
from .service import ServiceCharacteristic, register_service
from .session import get_session
from .util import to_int, to_uuid as to_bt_uuid

logger = logging.getLogger(__name__)

HDC1000_HUMIDITY = 65536 / 100
ACCEL = 0x08 | 0x10 | 0x20
ACCEL_WAKE_ON_MOTION = 0x80
MPU9250_GYRO = 65536 / 500
MPU9250_ACCEL_2G = 32768 / 2
MPU9250_ACCEL_UNPACK = struct.Struct('<3h').unpack

@dtc.dataclass(frozen=True)
class SensorTagService(ServiceCharacteristic):
    """
    Bluetooth service descriptor for GATT characteristics of Texas
    Instrument Sensor Tag Bluetooth device sensors.

    :var uuid_conf: UUID of characteristic to write and read device
        configuration.
    :var uuid_trigger: UUID of characteristic to write and read device
        trigger data.
    :var config_on: Default configuration of device to switch device on.
    :var config_off: Default configuration of device to switch device off.
    :var interval: Time interval (period) of sensor.
    """
    uuid_conf: str
    uuid_trigger: str
    config_on: bytes
    config_off: bytes
    interval: float=1

class SensorTagButtonState(Button):
    """
    Sensor Tag Bluetooth device button state.
    """
    OFF = 0x00
    USER = 0x01
    POWER = 0x02
    REED_RELAY = 0x04

# function to convert 16-bit UUID to full 128-bit Sensor Tag UUID
to_uuid = 'f000{:04x}-0451-4000-b000-000000000000'.format

register_st = partial(register_service, Make.SENSOR_TAG)

def convert_light(data: bytes) -> float:
    """
    Convert Sensor Tag light sensor data to a lux value.
    """
    v = to_int(data)
    m = (v & 0x0FFF) / 100
    e = (v & 0xF000) >> 12
    return m * (2 << e)

def convert_accel(data: bytes) -> tuple[float, float, float]:
    """
    Convert Sensor Tag Bluetooth device accelerometer data into (x, y, z)
    values.
    """
    # gyro: data[:6]
    # magnet: data[12:]
    x, y, z = tp.cast(tuple[float, float, float], MPU9250_ACCEL_UNPACK(data[6:12]))
    return (x / MPU9250_ACCEL_2G, y / MPU9250_ACCEL_2G, z / MPU9250_ACCEL_2G)

def convert_button(data: bytes) -> SensorTagButtonState:
    """
    Convert Sensor Tag Bluetooth device button data into button state
    object.
    """
    return SensorTagButtonState(data[0])

register_st(
    ServiceType.PRESSURE,
    SensorTagService(
        to_uuid(0xaa40),
        to_uuid(0xaa41),
        6,
        to_uuid(0xaa42),
        to_uuid(0xaa44),
        b'\x01',
        b'\x00',
    ),
    convert=lambda v: to_int(v[3:]),
)

register_st(
    ServiceType.TEMPERATURE,
    SensorTagService(
        to_uuid(0xaa00),
        to_uuid(0xaa01),
        4,
        to_uuid(0xaa02),
        to_uuid(0xaa03),
        b'\x01',
        b'\x00',
    ),
    convert=lambda v: to_int(v[2:]) / 128,
)

register_st(
    ServiceType.HUMIDITY,
    SensorTagService(
        to_uuid(0xaa20),
        to_uuid(0xaa21),
        4,
        to_uuid(0xaa22),
        to_uuid(0xaa23),
        b'\x01',
        b'\x00',
    ),
    convert=lambda v: to_int(v[2:]) / HDC1000_HUMIDITY,
)

register_st(
    ServiceType.LIGHT,
    SensorTagService(
        to_uuid(0xaa70),
        to_uuid(0xaa71),
        2,
        to_uuid(0xaa72),
        to_uuid(0xaa73),
        b'\x01',
        b'\x00',
    ),
    convert=convert_light,
)

register_st(
    ServiceType.ACCELEROMETER,
    SensorTagService(
        to_uuid(0xaa80),
        to_uuid(0xaa81),
        18,
        to_uuid(0xaa82),
        to_uuid(0xaa83),
        struct.pack('<H', ACCEL | ACCEL_WAKE_ON_MOTION),
        b'\x00\x00',
    ),
    convert=convert_accel,
    trigger=Trigger(TriggerCondition.FIXED_TIME, 0.1),
)

register_st(
    ServiceType.BUTTON,
    ServiceCharacteristic(
        to_bt_uuid(0xffe0),
        to_bt_uuid(0xffe1),
        1,
    ),
    convert=convert_button,
    trigger=Trigger(TriggerCondition.ON_CHANGE),
)

@enable.register  # type: ignore
async def _enable_sensor_tag(device: Device[SensorTagService, T]) -> None:
    bus = get_session().bus
    srv = device.service

    await bus.ensure_characteristic_paths(
        device.mac, srv.uuid_data, srv.uuid_conf, srv.uuid_trigger
    )
    await write_config(device.mac, srv.uuid_conf, srv.config_on)

    value = int(device.service.interval * 100)
    assert value < 256  # TODO: raise value error

    await write_config(device.mac, device.service.uuid_trigger, bytes([value]))
    logger.info('interval for {} is set'.format(device))

@disable.register  # type: ignore
async def _disable_sensor_tag(device: Device[SensorTagService, T]) -> None:
    srv = device.service
    await disarm(
        '{} disabled'.format(device),
        'cannot disable {}'.format(device),
        write_config, device.mac, srv.uuid_conf, srv.config_off
    )

@enable.register  # type: ignore
async def _enable_sensor_tag_tr(
        device: DeviceTrigger[SensorTagService, T]
    ) -> None:

    await _enable_sensor_tag(device)

    assert device.trigger.operand is not None
    value = int(device.trigger.operand * 100)
    assert value < 256  # TODO: raise value error

    await write_config(device.mac, device.service.uuid_trigger, bytes([value]))
    logger.info('trigger for {} is set'.format(device))

    await _enable_dev_trigger(device)

@disable.register  # type: ignore
async def _disable_sensor_tag_tr(device: Device[SensorTagService, T]) -> None:
    await _disable_sensor_tag(device)

# vim: sw=4:et:ai
