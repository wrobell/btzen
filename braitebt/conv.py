#
# BraiteBT - Bluetooh Smart sensor reading library. 
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

SHT21_TEMP = 175.72 / 65536
SHT21_HUMIDITY = 125.0 / 65536

to_int16 = lambda data: (data[1] << 8) + data[0]

sht21_humidity = lambda data: -6.0 + SHT21_HUMIDITY * (to_int16(data[2:]) & 0xfffc)
sht21_temp = lambda data: -46.85 + SHT21_TEMP * to_int16(data)

tmp006_temp = lambda data: to_int16(data[2:]) / 128.0

# vim: sw=4:et:ai
