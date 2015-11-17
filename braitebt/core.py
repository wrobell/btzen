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

from . import dbus
from .conv import tmp006_temp, sht21_humidity


def read_data(obj, converter):
    while True:
        data = obj.ReadValue()
        yield converter(data)


def connect(mac):
    device = dbus.get_device(mac)
    return device


def read_temperature(device):
    temp_conf = dbus.find_sensor(device, 'IR Temp. Conf.')
    temp_data = dbus.find_sensor(device, 'IR Temp. Data')
    temp_conf._obj.WriteValue([1])

    yield from read_data(temp_data._obj, tmp006_temp)


def read_humidity(device):
    hum_conf = dbus.find_sensor(device, 'Humid. Conf.')
    hum_data = dbus.find_sensor(device, 'Humid. Data')
    hum_conf._obj.WriteValue([1])
    yield from read_data(hum_data._obj, sht21_humidity)


# vim: sw=4:et:ai
