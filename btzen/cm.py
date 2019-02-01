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

flatten = chain.from_iterable

logger = logging.getLogger(__name__)

ENABLE = attrgetter('_enable')
HOLD = attrgetter('_hold')

class ConnectionManager:
    def __init__(self):
        self._devices = defaultdict(set)
        self._process = False

        self._enable = partial(self._exec, ENABLE)
        self._hold = partial(self._exec, HOLD)

    def add(self, *devices):
        for dev in devices:
            self._devices[dev._mac].add(dev)

    def close(self):
        self._process = False
        for dev in flatten(self._devices.values()):
            dev.close()
        logger.info('connection manager closed')

    def __await__(self):
        tasks = [self._reconnect(mac, devs) for mac, devs in self._devices.items()]
        yield from asyncio.gather(*tasks).__await__()

    async def _reconnect(self, mac, devices):
        path = _device_path(mac)

        self._process = True
        # run reconnection in the loop; this loop shall rarely restart as
        # `self._restart` is the main loop reacting to reconnections;
        # therefore if there is an error, sleep for 5 seconds to avoid cpu
        # hogging
        while self._process:
            try:
                await Bus.get_bus().connect(mac)
                await self._enable(devices)
                await self._restart(path, devices)
            except Exception as ex:
                logger.warning(
                    'cannot connect to {} due to {}, waiting 5s'
                    .format(mac, ex)
                )
                # TODO: make it configurable
                await asyncio.sleep(5)

    async def _restart(self, path, devices):
        # renable or hold device when services resolved property changes;
        # no exception handling as it is done by `self._reconnect`; here we
        # assume everything works without any errors
        bus = Bus.get_bus()
        bus._dev_property_start(path, 'ServicesResolved')
        try:
            while self._process:
                resolved = await bus._dev_property_get(path, 'ServicesResolved')
                # enable if services resolved, otherwise no point of disabling
                # or disconnecting the device, so just hold
                f = self._enable if resolved else self._hold
                await f(devices)
        finally:
            bus._dev_property_stop(path, 'ServicesResolved')

    async def _exec(self, f_get, devices):
        tasks = [f_get(dev)() for dev in devices]
        # use `wait` to execute each task independently, so a failed task
        # does not influence another one
        await asyncio.wait(tasks)

# vim: sw=4:et:ai
