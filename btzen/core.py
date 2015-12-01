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
    ('TI BLE Sensor Tag', 0xaa01):lambda *args: conv.tmp006_temp,
    ('TI BLE Sensor Tag', 0xaa21): lambda *args: conv.sht21_humidity,
    ('TI BLE Sensor Tag', 0xaa41): converter_epcos_t5400_pressure,
    ('SensorTag 2.0', 0xaa01):lambda *args: conv.tmp006_temp,
    ('SensorTag 2.0', 0xaa21): lambda *args: conv.hdc1000_humidity,
    ('SensorTag 2.0', 0xaa41): lambda *args: conv.bmp280_pressure,
}

dev_uuid = 'f000{:04x}-0451-4000-b000-000000000000'.format
data_converter = lambda device, dev_id: \
    DATA_CONVERTER[(str(device.Name), dev_id)]


def connect(mac):
    """
    Connect to device with MAC address `mac`.

    :param mac: Bluetooth device MAC address.
    """
    device = dbus.get_device(mac)
    return device


class Reader:
    def __init__(self, device, conf_id, data_id):
        super().__init__()

        conf_uuid = dev_uuid(conf_id)
        self.conf = dbus.find_sensor(device, conf_uuid)

        if not self.conf:
            raise ValueError('Cannot find configuration for uuid {}'.format(
                conf_uuid
            ))
        if __debug__:
            logger.debug(
                'sensor configuration found for uuiid={}'.format(conf_uuid)
            )

        self.converter = data_converter(device, data_id)(device, self.conf)
        self.data = dbus.find_sensor(device, dev_uuid(data_id))
        self.conf._obj.WriteValue([1])


    def read(self):
        value = self.data._obj.ReadValue()
        return self.converter(value)



class Temperature(Reader):
    def __init__(self, device):
        super().__init__(device, 0xaa02, 0xaa01)


class Humidity(Reader):
    def __init__(self, device):
        super().__init__(device, 0xaa22, 0xaa21)



class Pressure(Reader):
    def __init__(self, device):
        super().__init__(device, 0xaa42, 0xaa41)


class Light(Reader):
    def __init__(self, device):
        super().__init__(device, 0xaa72, 0xaa71)


# vim: sw=4:et:ai
