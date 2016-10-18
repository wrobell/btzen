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
import threading

from _btzen import ffi, lib
from .import conv

logger = logging.getLogger(__name__)

READ_LOCK = threading.Lock()


# TODO: fix for CC2541DK
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
    ('SensorTag 2.0', '0000ffe1-0000-1000-8000-00805f9b34fb'): lambda *args: conv.first_arg,
    ('CC2650 SensorTag', dev_uuid(0xaa01)):lambda *args: conv.tmp006_temp,
    ('CC2650 SensorTag', dev_uuid(0xaa21)): lambda *args: conv.hdc1000_humidity,
    ('CC2650 SensorTag', dev_uuid(0xaa41)): lambda *args: conv.bmp280_pressure,
    ('CC2650 SensorTag', dev_uuid(0xaa71)): lambda *args: conv.opt3001_light,
    ('CC2650 SensorTag', dev_uuid(0xaa81)): lambda *args: conv.mpu9250_motion,
    ('CC2650 SensorTag', '0000ffe1-0000-1000-8000-00805f9b34fb'): lambda *args: conv.first_arg,
}

data_converter = lambda name, uuid: \
    DATA_CONVERTER[(name, uuid)]


class Reader:
    def __init__(self, params, bus, loop, notifying):
        self._loop = loop
        self._queue = asyncio.Queue(loop=loop)

        self._notifying = notifying
        self._params = params
        self._bus = bus
        self._data = bytearray(self.DATA_LEN)

        # keep reference to device data with the dictionary below
        self._device_data = {
            'chr_data': ffi.new('char[]', params.path_data),
            'chr_conf': ffi.new('char[]', params.path_conf),
            'chr_period': ffi.new('char[]', params.path_period),
            'data': ffi.from_buffer(self._data),
            'len': self.DATA_LEN,
        }
        self._device = ffi.new('t_bt_device*', self._device_data)

        self.set_interval(1)

        if self._notifying:
            config_on = self._params.config_on_notify
            r = lib.bt_device_start_notify(self._bus, self._device)
        else:
            config_on = self._params.config_on

        # enabled switched off sensor; some sensors are always on,
        # i.e. button
        if config_on:
            r = lib.bt_device_write(
                self._bus,
                self._device.chr_conf,
                config_on,
                len(config_on)
            )

        name = self._params.name
        factory = data_converter(name, self.UUID_DATA)
        # TODO: fix for CC2541DK
        self._converter = factory(name, None)

    def set_interval(self, interval):
        value = int(interval * 100)
        assert value < 256
        r = lib.bt_device_write(self._bus, self._device.chr_period, [value], 1)

    def read(self):
        """
        Read and return sensor data.
        """
        with READ_LOCK:
            lib.bt_device_read(self._bus, self._device, ffi.from_buffer(self._data))
        return self._converter(self._data)

    async def read_async(self):
        """
        Read and return sensor data.

        This method is a coroutine.
        """
        if not self._notifying:
            r = lib.bt_device_read_async(self._bus, self._device)
        value = await self._queue.get()
        return value

    def close(self):
        """
        Disable sensor and stop reading sensor data.

        Pending, asynchronous coroutines are cancelled.
        """
        if self._notifying:
            r = lib.bt_device_stop_notify(self._bus, self._device)

        # disable switched on sensor; some sensors stay always on,
        # i.e. button
        if self._params.config_off:
            r = lib.bt_device_write(
                self._bus,
                self._device.chr_conf,
                self._params.config_off,
                len(self._params.config_off)
            )

        # empty data queue to avoid not done futures
        while self._queue.qsize():
            self._queue.get_nowait()

        logger.info('{} sensor closed'.format(self.__class__.__name__))

    def _process_async(self):
        """
        Set sensor data as result of current asynchronous call.

        .. seealso:: :py:meth:`Reader.read_async`
        """
        value = self._converter(self._data)
        self._queue.put_nowait(value)


class Temperature(Reader):
    DATA_LEN = 4
    UUID_DATA = dev_uuid(0xaa01)
    UUID_CONF = dev_uuid(0xaa02)
    UUID_PERIOD = dev_uuid(0xaa03)
    CONFIG_ON = [1]
    CONFIG_ON_NOTIFY = [1]
    CONFIG_OFF = [0]


class Pressure(Reader):
    DATA_LEN = 6
    UUID_DATA = dev_uuid(0xaa41)
    UUID_CONF = dev_uuid(0xaa42)
    UUID_PERIOD = dev_uuid(0xaa44)
    CONFIG_ON = [1]
    CONFIG_ON_NOTIFY = [1]
    CONFIG_OFF = [0]


class Humidity(Reader):
    DATA_LEN = 4
    UUID_DATA = dev_uuid(0xaa21)
    UUID_CONF = dev_uuid(0xaa22)
    UUID_PERIOD = dev_uuid(0xaa23)
    CONFIG_ON = [1]
    CONFIG_ON_NOTIFY = [1]
    CONFIG_OFF = [0]


class Light(Reader):
    DATA_LEN = 2
    UUID_DATA = dev_uuid(0xaa71)
    UUID_CONF = dev_uuid(0xaa72)
    UUID_PERIOD = dev_uuid(0xaa73)
    CONFIG_ON = [1]
    CONFIG_ON_NOTIFY = [1]
    CONFIG_OFF = [0]


class Accelerometer(Reader):
    DATA_LEN = 18
    UUID_DATA = dev_uuid(0xaa81)
    UUID_CONF = dev_uuid(0xaa82)
    UUID_PERIOD = dev_uuid(0xaa83)

    ACCEL_Z = 0x08
    ACCEL_Y = 0x10
    ACCEL_X = 0x20
    WAKE_ON_MOTION = 0x80
    CONFIG_ON = struct.pack('<H', ACCEL_X | ACCEL_Y | ACCEL_Z)
    CONFIG_ON_NOTIFY = struct.pack('<H', ACCEL_X | ACCEL_Y | ACCEL_Z | WAKE_ON_MOTION)
    CONFIG_OFF = [0, 0]


class Button(Reader):
    DATA_LEN = 1
    UUID_DATA = '0000ffe1-0000-1000-8000-00805f9b34fb'
    UUID_CONF = None
    UUID_PERIOD = None

    CONFIG_ON = None
    CONFIG_ON_NOTIFY = None
    CONFIG_OFF = None

# vim: sw=4:et:ai
