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

"""
Driver for serial device over Bluetooth Smart connection. Implements
Stollmann protcol

    http://www.telit.com/fileadmin/user_upload/products/Downloads/sr-rf/BlueMod/TIO_Implementation_Guide_r04.pdf

Tested with HeinrichsWeikamp OSTC 2 dive computer.
"""

import asyncio
import math
import logging
from contextlib import contextmanager

import btzen._btzen as cbtzen

logger = logging.getLogger(__name__)

# TODO: use the function from btzen.bus
def _mac(mac):
    return mac.replace(':', '_').upper()

def credits_for(data, n):
    return min(255, math.ceil((n - len(data)) / 20))

class Serial:
    UUID_RX_UART = '00000001-0000-1000-8000-008025000000'
    UUID_TX_UART = '00000002-0000-1000-8000-008025000000'
    UUID_TX_CREDIT = '00000004-0000-1000-8000-008025000000'
    UUID_RX_CREDIT = '00000003-0000-1000-8000-008025000000'

    def __init__(self, mac):
        self._mac = mac

    # TODO: use btzen.bus
    async def connect(self):
        bus = self._bus = cbtzen.default_bus()

        logger.debug('connecting to {}'.format(self._mac))
        path = '/org/bluez/hci0/dev_{}'.format(_mac(self._mac))
        task = asyncio.get_event_loop().create_future()
        cbtzen.bt_connect(bus, path, task)
        await task

        logger.debug('resolving services of {}'.format(self._mac))
        cb = cbtzen.PropertyChange('ServicesResolved')
        cbtzen.bt_wait_for(bus, path, 'org.bluez.Device1', cb)
        await cb.get()

        logger.debug('connected to {}'.format(self._mac))
        by_uuid = cbtzen.bt_characteristic(bus, path)

        self._tx_credit = self._add_notification(by_uuid[self.UUID_TX_CREDIT])
        self._tx_uart = self._add_notification(by_uuid[self.UUID_TX_UART])

        self._rx_credit_path = by_uuid[self.UUID_RX_CREDIT]
        self._rx_uart_path = by_uuid[self.UUID_RX_UART]

        self._rx_credits = 0
        self._add_rx_credits()

        logger.debug('requesting tx credits')
        value = await self._tx_credit.get()
        logger.debug('got tx credits: {}'.format(value))

    async def read(self, n):
        tx = self._tx_uart

        data = bytearray()
        while len(data) < n:
            with self._rx_credits_mgr(data, n):
                item = await tx.get()
                data.extend(item)

        assert len(data) == n
        return data

    def write(self, data):
        assert len(data) <= 20
        if self._rx_credits < 1:
            self._add_rx_credits()
        cbtzen.bt_write(self._bus, self._rx_uart_path, data)

    def _add_notification(self, path):
        cb = cbtzen.ValueChange()
        cbtzen.bt_characteristic_notify(self._bus, path, cb)
        return cb

    @contextmanager
    def _rx_credits_mgr(self, data, n):
        if self._rx_credits < 1:
            self._add_rx_credits(credits_for(data, n))
        try:
            yield
        finally:
            self._rx_credits -= 1

    def _add_rx_credits(self, n=0x20):
        cbtzen.bt_write(self._bus, self._rx_credit_path, bytes([n]))
        self._rx_credits += n
        logger.debug('rx credits: {}'.format(self._rx_credits))

# vim: sw=4:et:ai
