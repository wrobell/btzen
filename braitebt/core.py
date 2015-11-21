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
The identificators for specific sensors can be found at

CC2541DK
    http://processors.wiki.ti.com/index.php/SensorTag_User_Guide
CC2650STK
    http://processors.wiki.ti.com/index.php/CC2650_SensorTag_User's_Guide
"""

import functools
import logging
import struct

from . import dbus
from .import conv

logger = logging.getLogger(__name__)


def converter_epcos_t5400_pressure(dev, p_conf):
    p_calib = dbus.find_sensor(dev, dev_uuid(0xaa43))
    p_conf._obj.WriteValue([2])
    calib = p_calib._obj.ReadValue()
    calib = struct.unpack('<4H4h', bytearray(calib))
    return functools.partial(conv.epcos_t5400_pressure, calib)


# (sensor name, sensor id): data converter
DATA_CONVERTER = {
    ('SensorTag', 0xaa21): lambda *args: conv.sht21_humidity,
    ('SensorTag 2.0', 0xaa21): lambda *args: conv.hdc1000_humidity,
    ('SensorTag', 0xaa41): converter_epcos_t5400_pressure,
    ('SensorTag 2.0', 0xaa41): lambda *args: conv.bmp280_pressure,
}

dev_uuid = 'f000{:04x}-0451-4000-b000-000000000000'.format
data_converter = lambda device, dev_id: \
    DATA_CONVERTER[(str(device.Name), dev_id)]


def read_data(obj, converter):
    while True:
        data = obj.ReadValue()
        yield converter(data)


def connect(mac):
    device = dbus.get_device(mac)
    return device


def read_temperature(device):
    temp_conf = dbus.find_sensor(device, dev_uuid(0xaa02))
    temp_data = dbus.find_sensor(device, dev_uuid(0xaa01))
    temp_conf._obj.WriteValue([1])

    yield from read_data(temp_data._obj, conv.tmp006_temp)


def read_humidity(device):
    hum_conf = dbus.find_sensor(device, dev_uuid(0xaa22))
    if hum_conf:
        converter = data_converter(device, 0xaa21)(device, hum_conf)
        hum_data = dbus.find_sensor(device, dev_uuid(0xaa21))
        hum_conf._obj.WriteValue([1])
        return read_data(hum_data._obj, converter)
    else:
        return None


def read_pressure(device):
    p_conf = dbus.find_sensor(device, dev_uuid(0xaa42))
    if p_conf:
        converter = data_converter(device, 0xaa41)(device, p_conf)
        p_data = dbus.find_sensor(device, dev_uuid(0xaa41))
        p_conf._obj.WriteValue([1])
        return read_data(p_data._obj, converter)
    else:
        return None


def read_light(device):
    p_conf = dbus.find_sensor(device, dev_uuid(0xaa72))
    if p_conf:
        p_data = dbus.find_sensor(device, dev_uuid(0xaa71))
        p_conf._obj.WriteValue([1])
        return read_data(p_data._obj, conv.opt3001_light)
    else:
        if __debug__:
            logger.debug(
                'light sensor configuration not found (id={:x})'.format(0xaa72)
            )
        return None


# vim: sw=4:et:ai
