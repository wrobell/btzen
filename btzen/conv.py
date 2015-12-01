#
# BTZen - Bluetooh Smart sensor reading library.
#
# Copyright (C) 2015 by Artur Wroblewski <wrobell@pld-linux.org>
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

SHT21_TEMP = 175.72 / 65536
SHT21_HUMIDITY = 125 / 65536
HDC1000_HUMIDITY = 65536 / 100

BYTE_SHIFT = 1, 8, 16

to_int = lambda data: sum(v << b for v, b in zip(data, BYTE_SHIFT))

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
    temp, pressure = struct.unpack('<hH', bytearray(data))

    c = calib
    t2 = temp << 2
    sens = c[2] + ((c[3] * temp) >> 17) + ((c[4] * t2) >> 34)
    off = (c[5] << 14) + ((c[6] * temp) >> 3) + ((c[7] * t2) >> 19)
    return (sens * pressure + off) >> 14


# vim: sw=4:et:ai
