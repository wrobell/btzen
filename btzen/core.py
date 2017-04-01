#
# BTZen - Bluetooh Smart sensor reading library.
#
# Copyright (C) 2015-2017 by Artur Wroblewski <wrobell@riseup.net>
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
from collections import namedtuple

from . import dbus
from .import conv

logger = logging.getLogger(__name__)


Parameters = namedtuple('Parameters', [
    'uuid_dev', 'uuid_conf', 'uuid_period', 'config_on', 'config_off',
])


def converter_epcos_t5400_pressure(dev, p_conf):
    p_calib = dbus.find_sensor(dev, dev_uuid(0xaa43))
    p_conf._obj.WriteValue([2])
    calib = p_calib._obj.ReadValue({})
    calib = struct.unpack('<4H4h', bytearray(calib))
    return functools.partial(conv.epcos_t5400_pressure, calib)


dev_uuid = 'f000{:04x}-0451-4000-b000-000000000000'.format


# (sensor name, sensor id): data converter
DATA_CONVERTER = {
    ('TI BLE Sensor Tag', dev_uuid(0xaa01)):lambda *args: conv.tmp006_temp,
    ('TI BLE Sensor Tag', dev_uuid(0xaa21)): lambda *args: conv.sht21_humidity,
    ('TI BLE Sensor Tag', dev_uuid(0xaa41)): converter_epcos_t5400_pressure,
    ('SensorTag 2.0', dev_uuid(0xaa01)):lambda *args: conv.tmp006_temp,
    ('SensorTag 2.0', dev_uuid(0xaa21)): lambda *args: conv.hdc1000_humidity,
    ('SensorTag 2.0', dev_uuid(0xaa41)): lambda *args: conv.bmp280_pressure,
    ('SensorTag 2.0', dev_uuid(0xaa71)): lambda *args: conv.opt3001_light,
    ('SensorTag 2.0', dev_uuid(0xaa81)): lambda *args: conv.mpu9250_motion,
}

data_converter = lambda device, dev_id: \
    DATA_CONVERTER[(str(device.Name), dev_id)]


def connect(bus, mac):
    """
    Connect to device with MAC address `mac`.

    :param mac: Bluetooth device MAC address.
    """
    device = dbus.get_device(bus, mac)
    device._obj.Connect()
    return device


class Reader:
    def __init__(self, bus, device, params, loop=None):
        super().__init__()
        self._loop = asyncio.get_event_loop() if loop is None else loop

        self._params = params
        self._device = self._find(bus, device, params.uuid_dev)
        self._dev_conf = self._find(bus, device, params.uuid_conf)
        self._dev_period = self._find(bus, device, params.uuid_period)

        self._values = asyncio.Queue()

        factory = data_converter(device, params.uuid_dev)
        self._converter = factory(device, self._dev_conf)

        self.set_interval(1)
        self._dev_conf._obj.WriteValue(params.config_on, {})


    def _find(self, bus, device, uuid):
        obj = dbus.find_sensor(bus, device, uuid)
        if obj is None:
            raise ValueError(
                'Cannot find object for uuid {}'.format(uuid)
            )
        if __debug__:
            logger.debug('object for uuid {} found'.format(uuid))

        return obj


    def set_interval(self, interval):
        self._dev_period._obj.WriteValue([interval * 100], {})


    def read(self):
        """
        Read data from sensor.
        """
        value = self._device._obj.ReadValue({})
        return self._converter(value)


    async def read_async(self):
        """
        Read data from sensor in asynchronous manner.

        This method is a coroutine.
        """
        def cb(value):
            value = self._converter(value)
            self._loop.call_soon_threadsafe(self._values.put_nowait, value)

        def error_cb(*args):
            raise TypeError(self.__class__.__name__, *args) # FIXME

        self._device._obj.ReadValue({}, reply_handler=cb, error_handler=error_cb)
        value = await self._values.get()
        return value


    def close(self):
        self._dev_conf._obj.WriteValue(self._params.config_off)
        logger.info('{} device closed'.format(self.__class__.__name__))



class Temperature(Reader):
    def __init__(self, bus, device, loop=None):
        dev = Parameters(
            dev_uuid(0xaa01),
            dev_uuid(0xaa02),
            dev_uuid(0xaa03),
            [1],
            [0],
        )
        super().__init__(bus, device, dev, loop=loop)


class Humidity(Reader):
    def __init__(self, bus, device, loop=None):
        dev = Parameters(
            dev_uuid(0xaa21),
            dev_uuid(0xaa22),
            dev_uuid(0xaa23),
            [1],
            [0],
        )
        super().__init__(bus, device, dev, loop=loop)



class Pressure(Reader):
    def __init__(self, bus, device, loop=None):
        dev = Parameters(
            dev_uuid(0xaa41),
            dev_uuid(0xaa42),
            dev_uuid(0xaa44),
            [1],
            [0],
        )
        super().__init__(bus, device, dev, loop=loop)


class Light(Reader):
    def __init__(self, bus, device, loop=None):
        dev = Parameters(
            dev_uuid(0xaa71),
            dev_uuid(0xaa72),
            dev_uuid(0xaa73),
            [1],
            [0],
        )
        super().__init__(bus, device, dev, loop=loop)


class Accelerometer(Reader):
    ACCEL_X = 0x20
    ACCEL_Y = 0x10
    ACCEL_Z = 0x08

    def __init__(self, bus, device, loop=None):
        config = self.ACCEL_X | self.ACCEL_Y | self.ACCEL_Z
        dev = Parameters(
            dev_uuid(0xaa81),
            dev_uuid(0xaa82),
            dev_uuid(0xaa83),
            struct.pack('<H', config),
            b'\x00\x00',
        )
        super().__init__(bus, device, dev, loop=loop)


# vim: sw=4:et:ai
