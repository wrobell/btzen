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
from collections import defaultdict
from functools import partial
from itertools import chain
from operator import attrgetter

from .bus import Bus, _device_path
from . import _cm

flatten = chain.from_iterable

logger = logging.getLogger(__name__)

PATH_ADAPTER = '/org/bluez/hci0'

class ConnectionManager:
    def __init__(self):
        self._devices = defaultdict(set)
        self._connected = {}
        self._process = False

    def add(self, *devices):
        for dev in devices:
            self._devices[dev._mac].add(dev)
            dev._cm = self
        for mac in self._devices:
            self._connected[mac] = asyncio.Event()

    def close(self):
        self._process = False
        for dev in flatten(self._devices.values()):
            dev.close()
        logger.info('connection manager closed')

    async def connected(self, mac):
        if not mac in self._connected:
            raise ValueError(
                'Device with address {} not managed by the connection manager'
                .format(mac)
            )
        await self._connected[mac].wait()

    def __await__(self):
        self._process = True

        # TODO: if bluez daemon is restarted, the connection manager needs
        # to be reinitialized
        yield from _cm.cm_init(Bus.get_bus().system_bus, self).__await__()

        f = self._reconnect
        tasks = (f(mac, devs) for mac, devs in self._devices.items())
        yield from asyncio.gather(*tasks).__await__()

    async def _reconnect(self, mac, devices):
        path = _device_path(mac)
        bus = Bus.get_bus()

        # enable monitoring of the `ServicesResolved` property first
        bus._dev_property_start(path, 'ServicesResolved')

        # connect to a device
        #
        # NOTE: scanning by external programs shall be off or we will never
        # connect
        try:
            await _cm.bt_connect(bus.system_bus, PATH_ADAPTER, mac)
        except Exception as ex:
            if str(ex) == 'Already Exists':
                logger.info('connection for {} already exists'.format(mac))
            else:
                raise

        try:
            # if connected, then enable devices
            #
            # NOTE: at this stage we might be affected by race conditions,
            # we need to improve this
            if bus._property_bool(path, 'ServicesResolved'):
                await self._enable(mac, devices)
        except Exception as ex:
            logger.info(
                'error when enabling devices of {} on start: {}'
                .format(mac, ex)
            )

        await self._restart(mac, devices)

    async def _restart(self, mac, devices):
        """
        Renable or hold Bluetooth device when property 'ServicesResolved`
        changes.
        """
        path = _device_path(mac)
        bus = Bus.get_bus()
        enable = partial(self._enable, mac, devices)
        clear = self._connected[mac].clear
        try:
            while self._process:
                logger.info('waiting for services to be resolved for {}'.format(mac))
                resolved = await bus._dev_property_get(path, 'ServicesResolved')
                # enable if services resolved
                #
                # otherwise force the devices to wait; no point to
                # disconnect or disable device at this stage
                if resolved:
                    await enable()
                else:
                    clear()
                    logger.info('device {} disconnected'.format(mac))
        finally:
            bus._dev_property_stop(path, 'ServicesResolved')

    async def _enable(self, mac, devices):
        for dev in devices:
            # enable devices one by one to avoid any deadlocks
            await dev._enable()

        # wait for first data sample to be measured using the longest
        # interval
        interval = max(dev._interval for dev in devices)
        await asyncio.sleep(interval)

        self._connected[mac].set()

# vim: sw=4:et:ai
