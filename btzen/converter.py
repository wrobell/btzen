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
Data conversion functions for various sensors.
"""

import struct
from collections import namedtuple
from .util import dev_uuid

Weight = namedtuple('Weight', 'weight stabilized')

SHT21_TEMP = 175.72 / 65536
SHT21_HUMIDITY = 125 / 65536
HDC1000_HUMIDITY = 65536 / 100
MPU9250_GYRO = 65536 / 500
MPU9250_ACCEL_2G = 32768 / 2
MPU9250_ACCEL_UNPACK = struct.Struct('<3h').unpack

BYTE_SHIFT = 1, 8, 16

to_int = lambda data: sum(v << b for v, b in zip(data, BYTE_SHIFT))

first_arg = lambda value, *args: value
sht21_humidity = lambda data: -6.0 + SHT21_HUMIDITY * (to_int(data[2:]) & 0xfffc)
sht21_temp = lambda data: -46.85 + SHT21_TEMP * to_int(data[:2])
tmp006_temp = lambda data: to_int(data[2:]) / 128.0
bmp280_pressure = lambda data: to_int(data[3:])
hdc1000_humidity = lambda data: to_int(data[2:]) / HDC1000_HUMIDITY

def opt3001_light(data):
    v = to_int(data)
    m = (v & 0x0FFF) / 100
    e = (v & 0xF000) >> 12
    return m * (2 << e)

def epcos_t5400_pressure(calib, data):
    # todo: use struct object
    temp, pressure = struct.unpack('<hH', bytearray(data))

    c = calib
    t2 = temp << 2
    sens = c[2] + ((c[3] * temp) >> 17) + ((c[4] * t2) >> 34)
    off = (c[5] << 14) + ((c[6] * temp) >> 3) + ((c[7] * t2) >> 19)
    return (sens * pressure + off) >> 14

def mpu9250_motion(data):
    # gyro: data[:6]
    # magnet: data[12:]
    return tuple(v / MPU9250_ACCEL_2G for v in MPU9250_ACCEL_UNPACK(data[6:12]))

# TODO: fix for CC2541DK
def converter_epcos_t5400_pressure(dev, p_conf):
    p_calib = dbus.find_sensor(dev, dev_uuid(0xaa43))
    p_conf._obj.WriteValue([2])
    calib = p_calib._obj.ReadValue({})
    calib = struct.unpack('<4H4h', bytearray(calib))
    return functools.partial(epcos_t5400_pressure, calib)

# see https://github.com/oliexdev/openScale/wiki/Xiaomi-Bluetooth-Mi-Scale
def mi_weight_scale(data):
    status, weight = struct.unpack('<BH', data[0:3])
    stabilized = (status & 0x20) == 0x20
    return Weight(weight * 0.005, stabilized)

# (sensor name, sensor id): data converter
DATA_CONVERTER = {
    ('TI BLE Sensor Tag', dev_uuid(0xaa01)):lambda *args: tmp006_temp,
    ('TI BLE Sensor Tag', dev_uuid(0xaa21)): lambda *args: sht21_humidity,
    ('TI BLE Sensor Tag', dev_uuid(0xaa41)): converter_epcos_t5400_pressure,
    ('SensorTag 2.0', dev_uuid(0xaa01)):lambda *args: tmp006_temp,
    ('SensorTag 2.0', dev_uuid(0xaa21)): lambda *args: hdc1000_humidity,
    ('SensorTag 2.0', dev_uuid(0xaa41)): lambda *args: bmp280_pressure,
    ('SensorTag 2.0', dev_uuid(0xaa71)): lambda *args: opt3001_light,
    ('SensorTag 2.0', dev_uuid(0xaa81)): lambda *args: mpu9250_motion,
    ('SensorTag 2.0', '0000ffe1-0000-1000-8000-00805f9b34fb'): lambda *args: first_arg,
    ('CC2650 SensorTag', dev_uuid(0xaa01)):lambda *args: tmp006_temp,
    ('CC2650 SensorTag', dev_uuid(0xaa21)): lambda *args: hdc1000_humidity,
    ('CC2650 SensorTag', dev_uuid(0xaa41)): lambda *args: bmp280_pressure,
    ('CC2650 SensorTag', dev_uuid(0xaa71)): lambda *args: opt3001_light,
    ('CC2650 SensorTag', dev_uuid(0xaa81)): lambda *args: mpu9250_motion,
    ('CC2650 SensorTag', '0000ffe1-0000-1000-8000-00805f9b34fb'): lambda *args: first_arg,
    ('MI_SCALE', '00002a9d-0000-1000-8000-00805f9b34fb'): lambda *args: mi_weight_scale,
}

# return data conversion function for sensor device name and sensor UUID
# value
data_converter = lambda name, uuid: \
    DATA_CONVERTER[(name, uuid)]

__all__ = ['data_converter']

# vim: sw=4:et:ai
