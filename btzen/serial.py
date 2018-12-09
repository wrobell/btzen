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
Driver for serial device over Bluetooth Smart connection. Implements
Stollmann protcol

    http://www.telit.com/fileadmin/user_upload/products/Downloads/sr-rf/BlueMod/TIO_Implementation_Guide_r04.pdf

Tested with HeinrichsWeikamp OSTC 2 dive computer.
"""

import asyncio
import math
import logging
from binascii import hexlify
from functools import partial

from btzen import _btzen
from .bus import BUS
from .util import contextmanager

logger = logging.getLogger(__name__)

def credits_for(n):
    """
    Calculate number of required credits to send `n` number of bytes.
    """
    return min(255, math.ceil(n / 20))

class Serial:
    UUID_RX_UART = '00000001-0000-1000-8000-008025000000'
    UUID_TX_UART = '00000002-0000-1000-8000-008025000000'
    UUID_TX_CREDIT = '00000004-0000-1000-8000-008025000000'
    UUID_RX_CREDIT = '00000003-0000-1000-8000-008025000000'

    def __init__(self, mac):
        self._mac = mac
        self._system_bus = None
        self._loop = asyncio.get_event_loop()
        self._buffer = bytearray()

    async def connect(self):
        bus = self._system_bus = BUS.get_bus()
        get_path = partial(BUS.sensor_path, self._mac)
        bt_notify = partial(_btzen.bt_notify, bus)

        await BUS.connect(self._mac)

        self._tx_credit_path = get_path(self.UUID_TX_CREDIT)
        self._tx_uart_path = get_path(self.UUID_TX_UART)
        self._rx_credit_path = get_path(self.UUID_RX_CREDIT)
        self._rx_uart_path = get_path(self.UUID_RX_UART)

        self._tx_credit = bt_notify(self._tx_credit_path)
        self._tx_uart = bt_notify(self._tx_uart_path)

        self._rx_credits = 0
        await self._add_rx_credits()
        logger.debug('requesting tx credits')
        value = await self._tx_credit
        logger.debug('got tx credits: {}'.format(value))

    async def read(self, n):
        tx = self._tx_uart

        data = bytearray(self._buffer)
        while len(data) < n:
            async with self._rx_credits_mgr(n - len(data)):
                item = await tx
                data.extend(item)

                if __debug__:
                    logger.debug(
                        'bytes read {}, last {}, tx credits queue len {}'
                        .format(len(data), hexlify(data[-5:]), len(self._tx_credit))
                    )

        assert len(data) >= n

        # keep extra data in buffer, return only requested number of bytes
        self._buffer = data[n:]
        return data[:n]

    async def write(self, data):
        assert len(data) <= 20

        if self._rx_credits < 1:
            await self._add_rx_credits()

        if len(self._tx_credit):
            logger.debug('requesting tx credits')
            value = await self._tx_credit
            logger.debug('got tx credits: {}'.format(value))

        await self._write(self._rx_uart_path, data)

    def close(self):
        """
        Close serial device.
        """
        bt_notify_stop = partial(_btzen.bt_notify_stop, self._system_bus)
        bt_notify_stop(self._tx_credit_path)
        bt_notify_stop(self._tx_uart_path)

    @contextmanager
    async def _rx_credits_mgr(self, n):
        if self._rx_credits < 1:
            await self._add_rx_credits(credits_for(n))
        try:
            yield
        finally:
            self._rx_credits -= 1

    async def _add_rx_credits(self, n=0x20):
        await self._write(self._rx_credit_path, bytes([n]))
        self._rx_credits += n
        logger.debug('rx credits: {}'.format(self._rx_credits))

    async def _write(self, path, data):
        task = self._loop.create_future()
        _btzen.bt_write(self._system_bus, path, data, task)
        await task

# vim: sw=4:et:ai
