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
Texas Instrument Sensor Tag Bluetooth device sensors.

The sensors do not implement the Bluetooth Environmental Sensing interfaces
and require custom classes.

The identificators for specific sensors can be found at

CC2541DK
    http://processors.wiki.ti.com/index.php/SensorTag_User_Guide
CC2650STK
    http://processors.wiki.ti.com/index.php/CC2650_SensorTag_User's_Guide
"""

import asyncio
import logging
import struct
from functools import partial

from .bus import Bus
from .device import InfoCharacteristic, InfoEnvSensing, DeviceEnvSensing, \
    DeviceCharacteristic
from .device import to_uuid as to_bt_uuid

logger = logging.getLogger(__name__)

# function to convert 16-bit UUID to full 128-bit Sensor Tag UUID
to_uuid = 'f000{:04x}-0451-4000-b000-000000000000'.format

class DeviceSensorTag(DeviceEnvSensing):
    """
    Sensor Tag Bluetooth device sensor.
    """
    def __init__(self, mac, notifying=False):
        super().__init__(mac, notifying=notifying)

        self.set_interval(1)

    def set_interval(self, interval):
        value = int(interval * 100)
        assert value < 256
        self._data_trigger = bytes([value])

class Temperature(DeviceSensorTag):
    info = InfoEnvSensing(
        to_uuid(0xaa00),
        to_uuid(0xaa01),
        4,
        to_uuid(0xaa02),
        to_uuid(0xaa03),
        b'\x01',
        b'\x01',
        b'\x00',
    )
    UUID_SERVICE = info.service

    def get_value(self, data):
        return int.from_bytes(data[2:], byteorder='little') / 128.0

#   class Pressure(Sensor):
#       DATA_LEN = 6
#       UUID_SERVICE = dev_uuid(0xaa40)
#       UUID_DATA = dev_uuid(0xaa41)
#       UUID_CONF = dev_uuid(0xaa42)
#       UUID_PERIOD = dev_uuid(0xaa44)
#       CONFIG_ON = b'\x01'
#       CONFIG_ON_NOTIFY = b'\x01'
#       CONFIG_OFF = b'\x00'
#
#
#   class Humidity(Sensor):
#       DATA_LEN = 4
#       UUID_SERVICE = dev_uuid(0xaa20)
#       UUID_DATA = dev_uuid(0xaa21)
#       UUID_CONF = dev_uuid(0xaa22)
#       UUID_PERIOD = dev_uuid(0xaa23)
#       CONFIG_ON = b'\x01'
#       CONFIG_ON_NOTIFY = b'\x01'
#       CONFIG_OFF = b'\x00'
#
#
#   class Light(Sensor):
#       DATA_LEN = 2
#       UUID_SERVICE = dev_uuid(0xaa70)
#       UUID_DATA = dev_uuid(0xaa71)
#       UUID_CONF = dev_uuid(0xaa72)
#       UUID_PERIOD = dev_uuid(0xaa73)
#       CONFIG_ON = b'\x01'
#       CONFIG_ON_NOTIFY = b'\x01'
#       CONFIG_OFF = b'\x00'
#
#
#   class Accelerometer(Sensor):
#       DATA_LEN = 18
#       UUID_SERVICE = dev_uuid(0xaa80)
#       UUID_DATA = dev_uuid(0xaa81)
#       UUID_CONF = dev_uuid(0xaa82)
#       UUID_PERIOD = dev_uuid(0xaa83)
#
#       ACCEL_Z = 0x08
#       ACCEL_Y = 0x10
#       ACCEL_X = 0x20
#       WAKE_ON_MOTION = 0x80
#       CONFIG_ON = struct.pack('<H', ACCEL_X | ACCEL_Y | ACCEL_Z)
#       CONFIG_ON_NOTIFY = struct.pack('<H', ACCEL_X | ACCEL_Y | ACCEL_Z | WAKE_ON_MOTION)
#       CONFIG_OFF = b'\x00\x00'

class Button(DeviceCharacteristic):
    """
    Sensor Tag button.
    """
    info = InfoCharacteristic(to_bt_uuid(0xffe0), to_bt_uuid(0xffe1), 1)
    UUID_SERVICE = info.service

    def get_value(self, data):
        return data[0]

# vim: sw=4:et:ai
