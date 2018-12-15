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

from .bus import BUS, _device_path

flatten = chain.from_iterable

logger = logging.getLogger(__name__)

ENABLE = attrgetter('_enable')
DISABLE = attrgetter('_disable')

class ConnectionManager:
    def __init__(self):
        self._bus = BUS.get_bus()
        self._devices = defaultdict(set)
        self._process = False
        self._tasks = []

        self._enable = partial(self._exec, ENABLE)
        self._disable = partial(self._exec, DISABLE)

    def add(self, *devices):
        for dev in devices:
            self._devices[dev._mac].add(dev)

    def close(self):
        self._process = False
        for dev in flatten(self._devices.values()):
            dev.close()
        for t in self._tasks:
            t.close()
        logger.info('connection manager closed')

    def __await__(self):
        self._tasks = [self._reconnect(mac, devs) for mac, devs in self._devices.items()]
        yield from asyncio.wait(self._tasks).__await__()

    async def _reconnect(self, mac, devices):
        self._process = True
        while self._process:
            await self._connect(devices)
            break

        while self._process:
            await self._restart(mac, devices)

    async def _restart(self, mac, devices):
        path = _device_path(mac)
        resolved = await BUS._property_monitor(path, 'ServicesResolved')
        f = self._enable if resolved else self._disable
        await f(devices)

    async def _exec(self, f_get, devices):
        tasks = [f_get(dev)() for dev in devices]
        await asyncio.wait(tasks)

    async def _connect(self, devices):
        try:
            for dev in devices:
                await dev.connect()
        except Exception as ex:
            logger.warning('cannot connect due to: {}'.format(ex))

# vim: sw=4:et:ai
