#
# BTZen - Bluetooth Smart sensor reading library.
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

import asyncio
import logging
import threading
import time
from functools import lru_cache, partial

from . import _btzen
from .error import ConnectionError

logger = logging.getLogger(__name__)

INTERFACE_DEVICE = 'org.bluez.Device1'

def _mac(mac):
    return mac.replace(':', '_').upper()

class Bus:
    THREAD_LOCAL = threading.local()

    # TODO: get rid of loop parameter
    def __init__(self, loop=None):
        self._loop = asyncio.get_event_loop()

        self._fd = self.get_bus().fileno
        self._loop.add_reader(self._fd, self._process_event)

        self._lock = {}

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
        get_property = partial(_btzen.bt_property_bool, bus, path, INTERFACE_DEVICE)

        lock = self._lock.get(mac)
        if lock is None:
            self._lock[mac] = lock = asyncio.Lock()

        async with lock:
            # create "service resolved" notification first
            cb = _btzen.PropertyChange('ServicesResolved')
            _btzen.bt_wait_for(bus, path, INTERFACE_DEVICE, cb)

            # if services resolved, then device is connected
            resolved = get_property('ServicesResolved')
            if not resolved:
                try:
                    task = asyncio.get_event_loop().create_future()
                    logger.info('connecting to {}'.format(mac))
                    _btzen.bt_connect(bus, path, task)
                    await task
                except Exception as ex:
                    # exception can be raised when device is already
                    # connected
                    logger.debug('Connection error: {}'.format(ex))
                    connected = get_property('Connected')
                    if not connected:
                        raise

                value = await cb.get()
                # TODO: destroy "service resolved" notification"
                logger.info('{} services resolved {}'.format(mac, value))

        name = self._get_name(mac)
        logger.info('connected to {}'.format(name))
        return name

    def sensor_path(self, mac, uuid):
        if uuid is None:
            return ''
        by_uuid = self._get_sensor_paths(mac)
        return by_uuid[uuid]

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
