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
The identificators for specific sensors can be found at

CC2541DK
    http://processors.wiki.ti.com/index.php/SensorTag_User_Guide
CC2650STK
    http://processors.wiki.ti.com/index.php/CC2650_SensorTag_User's_Guide
"""

import asyncio
import logging
import struct
from collections import deque, namedtuple
from functools import partial

from . import _btzen
from .import converter
from .bus import BUS
from .error import ConfigurationError, DataReadError, DataWriteError
from .util import dev_uuid

logger = logging.getLogger(__name__)

Parameters = namedtuple('Parameters', [
    'name', 'path_data', 'path_conf', 'path_period', 'config_on',
    'config_on_notify', 'config_off',
])


class Sensor:
    """
    :var _task: Current asynchronous task.
    :var _system_bus: System D-Bus reference (not thread safe).
    """
    def __init__(self, mac, notifying=False, loop=None):
        self._mac = mac
        self._notifying = notifying
        self._loop = loop if loop else asyncio.get_event_loop()
        self._task = None
        self._notification = None

        self._params = None
        self._system_bus = None

    async def connect(self):
        """
        Connect to sensor Bluetooth device.
        """
        assert isinstance(self.UUID_DATA, str)
        assert isinstance(self.UUID_CONF, str) or self.UUID_CONF is None
        assert isinstance(self.UUID_PERIOD, str) or self.UUID_PERIOD is None

        self._system_bus = BUS.get_bus()

        name = await BUS.connect(self._mac)
        self._set_parameters(name)
        await self._enable()

    def set_interval(self, interval):
        path = self._params.path_period
        if path:
            value = int(interval * 100)
            assert value < 256
            bus = self._system_bus
            try:
                self._write_sync(path, bytes([value]))
            except DataWriteError as ex:
                logger.exception(ex)
                msg = 'Cannot set sensor interval value: {}'.format(r)
                raise ConfigurationError(msg)

    async def read(self):
        """
        Read and return sensor data.

        This method is an asynchronous coroutine and is *not* thread safe.
        """
        if self._notifying:
            task = self._notification
        else:
            task = self._loop.create_future()
            _btzen.bt_read(self._system_bus, self._params.path_data, task)
        self._task = task
        value = self._converter(await task)
        self._task = None
        return value

    def close(self):
        """
        Disable sensor and stop reading sensor data.

        Pending, asynchronous coroutines are cancelled.
        """
        # ignore any errors when closing sensor
        try:
            bus = self._system_bus
            params = self._params
            if not params:
                return

            if self._notifying:
                _btzen.bt_notify_stop(bus, params.path_data)

            # disable switched on sensor; some sensors stay always on,
            # i.e. button
            if params.config_off:
                self._write_sync(params.path_conf, params.config_off)

            task = self._task
            if task and not task.done():
                ex = asyncio.CancelledError('Sensor coroutine closed')
                task.set_exception(ex)

        except Exception as ex:
            logger.warn('error when closing sensor: {}'.format(ex))
        finally:
            self._task = None
            self._system_bus = None
            logger.info('{} sensor closed'.format(self._mac))

    def _set_parameters(self, name):
        get_path = partial(BUS.sensor_path, self._mac)
        mac = self._mac
        self._params = params = Parameters(
            name,
            get_path(self.UUID_DATA),
            get_path(self.UUID_CONF),
            get_path(self.UUID_PERIOD),
            self.CONFIG_ON,
            self.CONFIG_ON_NOTIFY,
            self.CONFIG_OFF,
        )

        # ceate data converter
        name = params.name
        factory = converter.data_converter(name, self.UUID_DATA)
        # TODO: fix for CC2541DK
        self._converter = factory(name, None)

    async def _write(self, path, data):
        """
        Write data to Bluetooth device.

        The method is an asynchronous coroutine.

        :param path: Gatt characteristic path of the device.
        :param data: Data to write.
        """
        task = self._loop.create_future()
        _btzen.bt_write(self._system_bus, path, data, task)
        await task

    def _write_sync(self, path, data):
        """
        Write data to Bluetooth device.

        :param path: Gatt characteristic path of the device.
        :param data: Data to write.
        """
        task = self._write(path, data)
        next(asyncio.as_completed([task]))

    async def _enable(self):
        bus = self._system_bus
        params = self._params
        if self._notifying:
            config_on = params.config_on_notify
            self._notification = _btzen.bt_notify(bus, params.path_data)
        else:
            config_on = params.config_on

        # enabled switched off sensor; some sensors are always on,
        # i.e. button
        if config_on:
            await self._write(params.path_conf, config_on)


class Temperature(Sensor):
    DATA_LEN = 4
    UUID_DATA = dev_uuid(0xaa01)
    UUID_CONF = dev_uuid(0xaa02)
    UUID_PERIOD = dev_uuid(0xaa03)
    CONFIG_ON = b'\x01'
    CONFIG_ON_NOTIFY = b'\x01'
    CONFIG_OFF = b'\x00'


class Pressure(Sensor):
    DATA_LEN = 6
    UUID_DATA = dev_uuid(0xaa41)
    UUID_CONF = dev_uuid(0xaa42)
    UUID_PERIOD = dev_uuid(0xaa44)
    CONFIG_ON = b'\x01'
    CONFIG_ON_NOTIFY = b'\x01'
    CONFIG_OFF = b'\x00'


class Humidity(Sensor):
    DATA_LEN = 4
    UUID_DATA = dev_uuid(0xaa21)
    UUID_CONF = dev_uuid(0xaa22)
    UUID_PERIOD = dev_uuid(0xaa23)
    CONFIG_ON = b'\x01'
    CONFIG_ON_NOTIFY = b'\x01'
    CONFIG_OFF = b'\x00'


class Light(Sensor):
    DATA_LEN = 2
    UUID_DATA = dev_uuid(0xaa71)
    UUID_CONF = dev_uuid(0xaa72)
    UUID_PERIOD = dev_uuid(0xaa73)
    CONFIG_ON = b'\x01'
    CONFIG_ON_NOTIFY = b'\x01'
    CONFIG_OFF = b'\x00'


class Accelerometer(Sensor):
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
    CONFIG_OFF = b'\x00\x00'


class Button(Sensor):
    DATA_LEN = 1
    UUID_DATA = '0000ffe1-0000-1000-8000-00805f9b34fb'
    UUID_CONF = None
    UUID_PERIOD = None

    CONFIG_ON = None
    CONFIG_ON_NOTIFY = None
    CONFIG_OFF = None

class Weight(Sensor):
    DATA_LEN = 9
    UUID_DATA = '00002a9d-0000-1000-8000-00805f9b34fb'

    UUID_CONF = None
    UUID_PERIOD = None

    CONFIG_ON = None
    CONFIG_ON_NOTIFY = None
    CONFIG_OFF = None

# vim: sw=4:et:ai
