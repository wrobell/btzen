#
# BTZen - library to asynchronously access Bluetooth devices.
#
# Copyright (C) 2015-2022 by Artur Wroblewski <wrobell@riseup.net>
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
import typing as tp
from collections.abc import Coroutine
from contextlib import asynccontextmanager
from contextvars import ContextVar

from .bus import Bus
from .error import BTZenError, CallError
from .data import T
from .device import DeviceBase
from .service import S

logger = logging.getLogger(__name__)

BT_SESSION = ContextVar['Session']('BT_SESSION')

class Session:
    """
    BTZen connection session.

    Await this object to close the session properly.
    """
    def __init__(self, bus: Bus):
        self.bus = bus
        self._is_active = False

        self._device_task: dict[DeviceBase[tp.Any, tp.Any], asyncio.Future[tp.Any]] = {}
        self._connection_task: dict[str, asyncio.Task[tp.Any]] = {}
        self._connection_status: dict[str, asyncio.Event] = {}

        self._event = asyncio.Event()

    def start(self) -> None:
        self._is_active = True

    def create_future(
        self, device: DeviceBase[S, T], f: Coroutine[None, None, T]
    ) -> asyncio.Future[T]:
        """
        Create future managed by BTZen connection session.

        If session stops, then all pending tasks are cancelled.
        """
        assert self._is_active

        task = asyncio.ensure_future(f)
        self._device_task[device] = task
        return task

    def add_connection_task(
        self, mac: str, f: Coroutine[None, None, T]
    ) -> asyncio.Task[T]:
        assert not self._is_active

        self._connection_status[mac] = asyncio.Event()

        task = asyncio.create_task(f)
        task.add_done_callback(self._stop)

        self._connection_task[mac] = task
        return task

    def set_connected(self, mac: str) -> None:
        assert self._is_active
        self._connection_status[mac].set()

    def set_disconnected(self, mac: str) -> None:
        self._connection_status[mac].clear()

    async def wait_connected(self, device: DeviceBase[S, T]) -> None:
        assert self._is_active

        event = self._connection_status.get(device.mac)
        if event is None:
            raise BTZenError(
                'Device with address {} not managed by BTZen connection manager'
                .format(device.mac)
            )
        # create future, so it can be cancelled when error happens in
        # connection management tasks
        task = self.create_future(device, event.wait())  # type: ignore
        await task

    def is_active(self) -> bool:
        return self._is_active

    def cancel_device_tasks(self, mac: str, msg: str) -> None:
        tasks = (t for d, t in self._device_task.items() if d.mac == mac)
        for t in tasks:
            t.cancel(msg=msg)

    def stop(self) -> None:
        self._is_active = False

        msg = 'BTZen session stopped'
        for t in self._device_task.values():
            t.cancel(msg=msg)
        for t in self._connection_task.values():
            t.cancel(msg=msg)

        logger.info('session is done')

    def _stop(self, task: asyncio.Task[T]) -> None:
        """
        Stop BTZen session if task is in error.
        """
        if task.done() and not task.cancelled() and task.exception():
            get_session().stop()
            try:
                task.result()
            except:
                logger.critical('Error in connection task', exc_info=True) 
                self._event.set()

    def __await__(self) -> tp.Generator[None, None, None]:
        # just wait forever and stop session on exit
        try:
            yield from self._event.wait().__await__()
        finally:
            self.stop()
        logger.info('session await exit')

@asynccontextmanager
async def connected(device: DeviceBase[S, T]) -> tp.AsyncIterator[Session]:
    session = get_session()

    if not session.is_active():
        raise asyncio.CancelledError(
            'BTZen is not running for device with address {}'
            .format(device.mac)
        )

    await session.wait_connected(device)
    if session.is_active():
        yield session

def get_session() -> Session:
    return BT_SESSION.get()

def is_active() -> bool:
    return get_session().is_active()

# vim: sw=4:et:ai
