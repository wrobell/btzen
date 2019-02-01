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
from .bus import Bus
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
    """
    def __init__(self, mac, notifying=False):
        self._mac = mac
        self._notifying = notifying
        self._task = None
        self._interval = 1

        self._params = None
        self._bus = None
        self._read_data = None
        self._write = None
        self._connected = asyncio.Event()

    async def connect(self):
        """
        Connect to sensor Bluetooth device.
        """
        await Bus.get_bus().connect(self._mac)
        await self._enable()

    async def set_interval(self, interval: int) -> None:
        self._interval = interval
        await self._connected.wait()
        await self._write_interval(interval)

    async def read(self):
        """
        Read and return sensor data.

        This method is an asynchronous coroutine and is *not* thread safe.
        """
        await self._connected.wait()
        self._task = self._read_data(self._params.path_data)
        value = self._converter(await self._task)
        self._task = None
        return value

    def close(self):
        """
        Disable sensor and stop reading sensor data.

        Pending, asynchronous coroutines are closed.
        """
        params = self._params
        if not params:
            return

        if self._notifying:
            try:
                # TODO: make it asynchronous
                self._bus._gatt_stop(params.path_data)
            except Exception as ex:
                logger.warning('cannot stop notifications: {}'.format(ex))

        # disable switched on sensor; some sensors stay always on,
        # i.e. button
        system_bus = self._bus.system_bus
        if params.config_off:
            try:
                _btzen.bt_write_sync(system_bus, params.path_conf, params.config_off)
            except Exception as ex:
                logger.warning('Cannot switch sensor off: {}'.format(ex))

        task = self._task
        if task is not None:
            task.close()
            self._task = None

        logger.info('sensor {} closed'.format(self))

    def _set_parameters(self):
        assert isinstance(self.UUID_DATA, str)
        assert isinstance(self.UUID_CONF, str) or self.UUID_CONF is None
        assert isinstance(self.UUID_PERIOD, str) or self.UUID_PERIOD is None

        get_path = partial(self._bus.sensor_path, self._mac)
        mac = self._mac
        name = self._bus._get_name(mac)

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

    async def _enable(self):
        """
        Switch on and enable the sensor.
        """
        notify = self._notifying

        self._bus = Bus.get_bus()
        system_bus = self._bus.system_bus

        read = partial(_btzen.bt_read, system_bus)
        self._read_data = self._bus._gatt_get if notify else read
        self._write = partial(_btzen.bt_write, system_bus)

        self._set_parameters()

        params = self._params

        config_on = params.config_on_notify if notify else params.config_on

        # enable sensor; some sensors are always on, i.e. button
        if config_on:
            await self._write(params.path_conf, config_on)

        if notify:
            self._bus._gatt_start(params.path_data)

        await self._write_interval(self._interval)

        self._connected.set()
        logger.info('enabled device: {}'.format(self))

    async def _hold(self):
        self._connected.clear()
        logger.info('device {} on hold'.format(self))

    async def _write_interval(self, interval: int) -> None:
        path = self._params.path_period
        if path is not None:
            value = int(interval * 100)
            assert value < 256
            await self._write(path, bytes([value]))
        else:
            logger.warning('setting interval for {} not supported'.format(self))

    def __repr__(self):
        return '{}/{}'.format(self._mac, self.__class__.__name__)


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

    # not possible to set interval on button
    async def set_interval(self, interval):
        pass

class Weight(Sensor):
    DATA_LEN = 9
    UUID_DATA = '00002a9d-0000-1000-8000-00805f9b34fb'

    UUID_CONF = None
    UUID_PERIOD = None

    CONFIG_ON = None
    CONFIG_ON_NOTIFY = None
    CONFIG_OFF = None

# vim: sw=4:et:ai
