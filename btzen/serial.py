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

"""
Driver for serial device over Bluetooth Smart connection. Implements
Stollmann protcol

    http://www.telit.com/fileadmin/user_upload/products/Downloads/sr-rf/BlueMod/TIO_Implementation_Guide_r04.pdf

Tested with HeinrichsWeikamp OSTC 2 dive computer.
"""

import asyncio
import math
import logging
import typing as tp
from binascii import hexlify
from contextlib import asynccontextmanager
from functools import partial, cache

from . import _btzen  # type: ignore
from .bus import Bus
from .config import DEFAULT_DBUS_TIMEOUT
from .data import Make, ServiceType
from .device import Device
from .devio import enable, disable, read, write, disarm
from .service import Service, register_service
from .session import get_session, connected
from .util import to_uuid

logger = logging.getLogger(__name__)

T = tp.TypeVar('T', bound=bytes)

UUID_RX_UART = '00000001-0000-1000-8000-008025000000'
UUID_TX_UART = '00000002-0000-1000-8000-008025000000'
UUID_TX_CREDIT = '00000004-0000-1000-8000-008025000000'
UUID_RX_CREDIT = '00000003-0000-1000-8000-008025000000'

class State(tp.TypedDict):
    """
    Device state with buffer and number of RX credits.
    """
    buffer: bytearray
    rx_credits: int

class SerialService(Service):
    pass

register_service(
    Make.OSTC,
    ServiceType.SERIAL,
    SerialService(to_uuid(0xfefb)),
)

@cache
def device_state(device: Device[SerialService, T]) -> State:
    """
    Create or get serial device state.
    """
    return State(buffer=bytearray(), rx_credits=0)

@read.register  # type: ignore
async def _read_serial(device: Device[SerialService, T], n: int) -> bytes:
    async with connected(device) as session:
        task = session.create_future(device, _read_data(session.bus, device, n))   # type: ignore
        return (await task)  # type: ignore

async def _read_data(bus: Bus, device: Device[SerialService, T], n: int) -> bytes:
    state = device_state(device)
    data = bytearray(state['buffer'])

    await bus.ensure_characteristic_paths(
        device.mac, UUID_TX_UART, UUID_RX_UART, UUID_TX_CREDIT, UUID_RX_CREDIT
    )

    path_uart = bus.characteristic_path(device.mac, UUID_TX_UART)

    while len(data) < n:
        async with _rx_credits_mgr(bus, device, n - len(data)):
            item = await bus._gatt_get(path_uart)
            data.extend(item)

            if __debug__:
                logger.debug(
                    'bytes read {}, last {}, tx credits size {}'
                    .format(len(data), hexlify(data[-5:]).decode(), _tx_credit_size(bus, device.mac))
                )

    assert len(data) >= n

    # keep extra data in buffer, return only requested number of bytes
    state['buffer'] = data[n:]
    return data[:n]

@write.register  # type: ignore
async def _write_serial(device: Device[SerialService, T], data: bytes) -> None:
    assert len(data) <= 20
    async with connected(device) as session:
        state = device_state(device)

        if state['rx_credits'] < 1:
            await _add_rx_credits(session.bus, device)

        if _tx_credit_size(session.bus, device.mac) > 0:
            logger.debug('requesting tx credits on write')
            await _tx_credit(session.bus, device.mac)

        await _write(session.bus, device.mac, UUID_RX_UART, data)

@enable.register  # type: ignore
async def _enable_serial(device: Device[SerialService, T]) -> None:
    bus = get_session().bus
    get_path = partial(bus.characteristic_path, device.mac)

    # reset cache for device
    state = device_state(device)
    state['buffer'] = bytearray()
    state['rx_credits'] = 0

    bus._gatt_start(get_path(UUID_TX_CREDIT))
    bus._gatt_start(get_path(UUID_TX_UART))

    logger.debug('requesting xx credits on enable')
    await _add_rx_credits(bus, device)

    logger.debug('requesting tx credits on enable')
    await _tx_credit(bus, device.mac)

@disable.register  # type: ignore
async def _disable_serial(device: Device[SerialService, T]) -> None:
    bus = get_session().bus
    await disarm(
        'disabled tx credit for {}'.format(device.mac),
        'cannot disabl tx credit for {}'.format(device.mac),
        bus._gatt_stop,
        bus.characteristic_path(device.mac, UUID_TX_CREDIT),
    )
    await disarm(
        'disabled tx uart for {}'.format(device.mac),
        'cannot disabl tx uart for {}'.format(device.mac),
        bus._gatt_stop,
        bus.characteristic_path(device.mac, UUID_TX_UART),
    )

async def _tx_credit(bus: Bus, mac: str) -> None:
    path = bus.characteristic_path(mac, UUID_TX_CREDIT)
    n = await bus._gatt_get(path)
    logger.debug('got tx credits: {}'.format(n))

def _tx_credit_size(bus: Bus, mac: str) -> int:
    path = bus.characteristic_path(mac, UUID_TX_CREDIT)
    return bus._gatt_size(path)

async def _add_rx_credits(
        bus: Bus, device: Device[SerialService, T], n: int=0x20
    ) -> None:

    state = device_state(device)
    await _write(bus, device.mac, UUID_RX_CREDIT, bytes([n]))
    state['rx_credits'] += n
    logger.debug('rx credits: {}'.format(state['rx_credits']))

@asynccontextmanager
async def _rx_credits_mgr(
        bus: Bus, device: Device[SerialService, T], n: int
    ) -> tp.AsyncIterator[None]:

    state = device_state(device)
    if state['rx_credits'] < 1:
        await _add_rx_credits(bus, device, credits_for(n))

    try:
        yield
    finally:
        state['rx_credits'] -= 1

async def _write(bus: Bus, mac: str, uuid: str, data: bytes) -> None:
    path = bus.characteristic_path(mac, uuid)
    task = _btzen.bt_write(bus.system_bus, path, data, DEFAULT_DBUS_TIMEOUT)
    await task

def credits_for(n: int) -> int:
    """
    Calculate number of required credits to send `n` number of bytes.
    """
    return min(255, math.ceil(n / 20))

# vim: sw=4:et:ai
