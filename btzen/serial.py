#
# BTZen - library to asynchronously access Bluetooth devices.
#
# Copyright (C) 2015-2019 by Artur Wroblewski <wrobell@riseup.net>
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
from .bus import Bus
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
        self._bus = None
        self._loop = asyncio.get_event_loop()
        self._buffer = bytearray()

    async def connect(self):
        self._bus = Bus.get_bus()
        await self._bus.connect(self._mac)
        await self._enable()

    async def _enable(self):
        get_path = partial(bus.sensor_path, self._mac)

        self._tx_credit_path = get_path(self.UUID_TX_CREDIT)
        self._tx_uart_path = get_path(self.UUID_TX_UART)
        self._rx_credit_path = get_path(self.UUID_RX_CREDIT)
        self._rx_uart_path = get_path(self.UUID_RX_UART)

        self._bus._gatt_start(self._tx_credit_path)
        self._bus._gatt_start(self._tx_uart_path)

        self._tx_credit = partial(self._bus._gatt_get, self._tx_credit_path)
        self._tx_uart = partial(self._bus._gatt_get, self._tx_uart_path)
        self._tx_credit_size = partial(self._bus._gatt_size, self._tx_credit_path)

        self._rx_credits = 0
        await self._add_rx_credits()
        logger.debug('requesting tx credits on enable')
        value = await self._tx_credit()
        logger.debug('got tx credits on enable: {}'.format(value))

    async def read(self, n):
        data = bytearray(self._buffer)
        while len(data) < n:
            async with self._rx_credits_mgr(n - len(data)):
                item = await self._tx_uart()
                data.extend(item)

                if __debug__:
                    logger.debug(
                        'bytes read {}, last {}, tx credits size {}'
                        .format(len(data), hexlify(data[-5:]), self._tx_credit_size())
                    )

        assert len(data) >= n

        # keep extra data in buffer, return only requested number of bytes
        self._buffer = data[n:]
        return data[:n]

    async def write(self, data):
        assert len(data) <= 20

        if self._rx_credits < 1:
            await self._add_rx_credits()

        if self._tx_credit_size() > 0:
            logger.debug('requesting tx credits')
            value = await self._tx_credit()
            logger.debug('got tx credits: {}'.format(value))

        await self._write(self._rx_uart_path, data)

    def close(self):
        """
        Close serial device.
        """
        self._bus._gatt_stop(self._tx_credit_path)
        self._bus._gatt_stop(self._tx_uart_path)

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
        task = _btzen.bt_write(self._bus._system_bus, path, data)
        await task

# vim: sw=4:et:ai
