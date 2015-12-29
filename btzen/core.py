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

import asyncio
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
    ('SensorTag 2.0', 0xaa71): lambda *args: conv.opt3001_light,
    ('SensorTag 2.0', 0xaa81): lambda *args: conv.mpu9250_motion,
}

dev_uuid = 'f000{:04x}-0451-4000-b000-000000000000'.format
data_converter = lambda device, dev_id: \
    DATA_CONVERTER[(str(device.Name), dev_id)]


def connect(bus, mac):
    """
    Connect to device with MAC address `mac`.

    :param mac: Bluetooth device MAC address.
    """
    device = dbus.get_device(bus, mac)
    return device


class Reader:
    def __init__(self, bus, device, conf_id, data_id, config, loop=None):
        super().__init__()

        self._loop = asyncio.get_event_loop() if loop is None else loop
        conf_uuid = dev_uuid(conf_id)
        self.conf = dbus.find_sensor(bus, device, conf_uuid)

        if not self.conf:
            raise ValueError(
                'Cannot find configuration for uuid {}'
                .format(conf_uuid)
            )
        if __debug__:
            logger.debug(
                'sensor configuration found for uuiid={}'.format(conf_uuid)
            )

        self._values = asyncio.Queue()

        self.converter = data_converter(device, data_id)(device, self.conf)
        self.data = dbus.find_sensor(bus, device, dev_uuid(data_id))
        self.conf._obj.WriteValue(config)


    def read(self):
        """
        Read data from sensor.
        """
        value = self.data._obj.ReadValue()
        return self.converter(value)


    async def read_async(self):
        """
        Read data from sensor in asynchronous manner.

        This method is a coroutine.
        """
        def cb(value):
            value = self.converter(value)
            self._loop.call_soon_threadsafe(self._values.put_nowait, value)

        def error_cb(*args):
            raise TypeError(self.__class__.__name__, *args) # FIXME

        self.data._obj.ReadValue(reply_handler=cb, error_handler=error_cb)
        value = await self._values.get()
        return value



class Temperature(Reader):
    def __init__(self, bus, device, loop=None):
        super().__init__(bus, device, 0xaa02, 0xaa01, [1], loop=loop)


class Humidity(Reader):
    def __init__(self, bus, device, loop=None):
        super().__init__(bus, device, 0xaa22, 0xaa21, [1], loop=loop)



class Pressure(Reader):
    def __init__(self, bus, device, loop=None):
        super().__init__(bus, device, 0xaa42, 0xaa41, [1], loop=loop)


class Light(Reader):
    def __init__(self, bus, device, loop=None):
        super().__init__(bus, device, 0xaa72, 0xaa71, [1], loop=loop)


class Motion(Reader):
    GYRO_X = 0x04
    GYRO_Y = 0x02
    GYRO_Z = 0x01
    ACCEL_X = 0x20
    ACCEL_Y = 0x10
    ACCEL_Z = 0x08
    MAGNET = 0x40

    def __init__(self, bus, device, loop=None):
        # FIXME: configuration needs to be independent from sensor
        config = self.GYRO_X | self.GYRO_Y | self.GYRO_Z \
            | self.ACCEL_X | self.ACCEL_Y | self.ACCEL_Z
            #| self.MAGNET
        config = struct.pack('<H', config)
        super().__init__(bus, device, 0xaa82, 0xaa81, config, loop=loop)


# vim: sw=4:et:ai
