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

import asyncio
import logging
import threading
import time
from functools import lru_cache, partial
from weakref import WeakValueDictionary

from . import _btzen
from .error import ConnectionError

logger = logging.getLogger(__name__)

INTERFACE_DEVICE = 'org.bluez.Device1'

def _mac(mac):
    return mac.replace(':', '_').upper()

class Bus:
    THREAD_LOCAL = threading.local()

    def __init__(self):
        self._loop = asyncio.get_event_loop()

        self._fd = self.get_bus().fileno
        self._loop.add_reader(self._fd, self._process_event)

        # cache of connection locks; lock is used to perform single
        # connection to a given bluetooth device; once a lock is deleted,
        # it will be removed from the dictionary
        self._lock = WeakValueDictionary()

    @staticmethod
    def get_bus():
        """
        Get system bus reference.

        The reference is local to current thread.
        """
        local = Bus.THREAD_LOCAL
        if not hasattr(local, 'bus'):
            local.bus = _btzen.default_bus()
        return local.bus

    async def connect(self, mac):
        """
        Connect to Bluetooth device.

        If connected, the method does nothing.

        :param mac: MAC address of Bluetooth device.
        """
        bus = self.get_bus()
        path = self._get_device_path(mac)

        lock = self._lock.get(mac)
        if lock is None:
            self._lock[mac] = lock = asyncio.Lock()

        try:
            async with lock:
                await self._connect_and_resolve(bus, path)
        finally:
            # destroy lock, so it is removed from the cache when no longer
            # in use
            del lock
            logger.debug('number of connection locks: {}'.format(len(self._lock)))

        name = self._get_name(mac)
        logger.info('connected to {}'.format(name))

        return name

    def sensor_path(self, mac, uuid):
        if uuid is None:
            return ''
        by_uuid = self._get_sensor_paths(mac)
        return by_uuid[uuid]

    async def _connect_and_resolve(self, bus, path):
        logger.info('connecting to {}'.format(path))
        await self._connect(bus, path)

        # first create task
        task_sr = _btzen.bt_property_monitor(
            bus, path, INTERFACE_DEVICE, 'ServicesResolved'
        )
        # then check the property
        resolved = self._property_bool(path, 'ServicesResolved')
        if not resolved:
            try:
                logger.info('resolving services for {}'.format(path))
                # and wait for services to be resolved
                value = await task_sr
                logger.info('{} services resolved {}'.format(path, value))
            finally:
                # destroy the notification
                task_sr.close()

    async def _connect(self, bus, path):
        try:
            task = self._loop.create_future()
            _btzen.bt_connect(bus, path, task)
            await task
        except Exception as ex:
            # exception might be raised if device is already connected, so
            # check if errors has to be raised
            logger.debug('connection error: {}'.format(ex))
            connected = self._property_bool(path, 'Connected')
            if not connected:
                raise

    def _property_bool(self, path, name):
        bus = self.get_bus()
        value = _btzen.bt_property_bool(bus, path, INTERFACE_DEVICE, name)
        return value

    @lru_cache()
    def _get_sensor_paths(self, mac):
        path = self._get_device_path(mac)
        by_uuid = _btzen.bt_characteristic(self.get_bus(), path)
        return by_uuid

    @lru_cache()
    def _get_name(self, mac):
        path = self._get_device_path(mac)
        bus = self.get_bus()
        return _btzen.bt_property_str(bus, path, INTERFACE_DEVICE, 'Name')

    def _get_device_path(self, mac):
        path = '/org/bluez/hci0/dev_{}'.format(_mac(mac))
        return path

    def _process_event(self):
        bus = self.get_bus()
        process = _btzen.bt_process
        r = process(bus)
        while r > 0:
            r = process(bus)

BUS = Bus()

# vim: sw=4:et:ai
