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

"""
Texas Instrument Sensor Tag Bluetooth device sensors.

The sensors do not implement the Bluetooth Environmental Sensing interfaces
and require custom classes. To enable reading data from sensors, trigger is
required, which we default to one second. Only one trigger can be
configured.

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

from .device import to_uuid as to_bt_uuid
from .ndevice import DeviceEnvSensing, register, Make, DeviceType
from .util import to_int

logger = logging.getLogger(__name__)

T = tp.TypeVar('T')

HDC1000_HUMIDITY = 65536 / 100

@dtc.dataclass(frozen=True)
class DeviceSensorTag(DeviceEnvSensing[T]):
    pass

# function to convert 16-bit UUID to full 128-bit Sensor Tag UUID
to_uuid = 'f000{:04x}-0451-4000-b000-000000000000'.format

register_st = partial(register, Make.SENSOR_TAG)

def convert_light(data: bytes) -> float:
    """
    Convert Sensor Tag light sensor data to a lux value.
    """
    v = to_int(data)
    m = (v & 0x0FFF) / 100
    e = (v & 0xF000) >> 12
    return m * (2 << e)

register_st(DeviceType.PRESSURE, DeviceEnvSensing(
    to_uuid(0xaa40),
    lambda v: to_int(v[3:]),
    to_uuid(0xaa41),
    6,
    to_uuid(0xaa42),
    to_uuid(0xaa44),
    b'\x01',
    b'\x00',
))

register_st(DeviceType.TEMPERATURE, DeviceEnvSensing(
    to_uuid(0xaa00),
    lambda v: to_int(v[2:]) / 128,
    to_uuid(0xaa01),
    4,
    to_uuid(0xaa02),
    to_uuid(0xaa03),
    b'\x01',
    b'\x00',
))

register_st(DeviceType.HUMIDITY, DeviceSensorTag(
    to_uuid(0xaa20),
    lambda v: to_int(v[2:]) / HDC1000_HUMIDITY,
    to_uuid(0xaa21),
    4,
    to_uuid(0xaa22),
    to_uuid(0xaa23),
    b'\x01',
    b'\x00',
))

register_st(DeviceType.LIGHT, DeviceSensorTag(
    to_uuid(0xaa70),
    convert_light,
    to_uuid(0xaa71),
    2,
    to_uuid(0xaa72),
    to_uuid(0xaa73),
    b'\x01',
    b'\x00',
))

#   class DeviceSensorTag(DeviceEnvSensing):
#       """
#       Sensor Tag Bluetooth device sensor.
#       """
#       def __init__(self, mac, notifying=False):
#           super().__init__(mac, notifying=notifying)
#
#           self.set_trigger(Trigger(TriggerCondition.FIXED_TIME, 1))
#
#       async def _configure(self):
#           await super()._configure()
#           # allow to read first value from sensor
#           await asyncio.sleep(self._trigger.operand)
#
#       def _trigger_data(self, trigger: Trigger) -> bytes:
#           assert trigger.condition == TriggerCondition.FIXED_TIME
#
#           value = int(trigger.operand * 100)
#           assert value < 256
#           return bytes([value])
#
#
#   class Accelerometer(DeviceSensorTag):
#       """
#       Sensor Tag Bluetooth device accelerometer sensor.
#       """
#       ACCEL = 0x08 | 0x10 | 0x20
#       WAKE_ON_MOTION = 0x80
#
#       MPU9250_GYRO = 65536 / 500
#       MPU9250_ACCEL_2G = 32768 / 2
#       MPU9250_ACCEL_UNPACK = struct.Struct('<3h').unpack
#
#       info = InfoEnvSensing(
#           to_uuid(0xaa80),
#           to_uuid(0xaa81),
#           18,
#           to_uuid(0xaa82),
#           to_uuid(0xaa83),
#           struct.pack('<H', ACCEL),
#           struct.pack('<H', ACCEL | WAKE_ON_MOTION),
#           b'\x00\x00',
#       )
#
#       def get_value(self, data):
#           # gyro: data[:6]
#           # magnet: data[12:]
#           return tuple(
#               v / self.MPU9250_ACCEL_2G
#               for v in self.MPU9250_ACCEL_UNPACK(data[6:12])
#           )
#
#   class ButtonState(enum.IntFlag):
#       """
#       Sensor Tag Bluetooth device button state.
#       """
#       OFF = 0x00
#       USER = 0x01
#       POWER = 0x02
#       REED_RELAY = 0x04
#
#   class Button(DeviceCharacteristic):
#       """
#       Sensor Tag Bluetooth device button.
#       """
#       info = InfoCharacteristic(to_bt_uuid(0xffe0), to_bt_uuid(0xffe1), 1)
#
#       def get_value(self, data: bytes) -> ButtonState:
#           return ButtonState(data[0])

# vim: sw=4:et:ai
