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

# function to convert 16-bit part uuid to full 128-bit UUID string
dev_uuid = 'f000{:04x}-0451-4000-b000-000000000000'.format

#
# from https://github.com/agronholm/asyncio_extras/blob/master/asyncio_extras/contextmanager.py
# MIT license
#
from functools import wraps
from inspect import iscoroutinefunction

class _AsyncContextManager:
    __slots__ = 'generator'

    def __init__(self, generator) -> None:
        self.generator = generator

    def __aenter__(self):
        return self.generator.asend(None)

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_val is not None:
            await self.generator.athrow(exc_val)
        else:
            try:
                await self.generator.asend(None)
            except StopAsyncIteration:
                pass
            else:
                raise RuntimeError("async generator didn't stop")

def contextmanager(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        generator = func(*args, **kwargs)
        return _AsyncContextManager(generator)

    return wrapper

# vim: sw=4:et:ai
