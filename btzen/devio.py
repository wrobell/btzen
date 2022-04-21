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
Operations for Bluetooth devices.

Basic operations

- `enable`
- `disable`
- `read`
- `write`
"""

from __future__ import annotations

import asyncio
import dataclasses as dtc
import inspect
import logging
import typing as tp
from collections.abc import AsyncIterator
from functools import singledispatch

from . import _btzen  # type: ignore
from .config import DEFAULT_DBUS_TIMEOUT
from .data import T
from .device import DeviceBase, Device, DeviceTrigger
from .service import Service, ServiceInterface, ServiceCharacteristic
from .session import get_session, connected, is_active

logger = logging.getLogger(__name__)

@singledispatch
async def read(device: DeviceBase[Service, T], *args: tp.Any) -> T:
    """
    Read data from Bluetooth device.

    The coroutine can raise cancellation error (`asyncio.CancelledError`),
    i.e. when the device is disconnected. The caller should handle the
    error, if it wants to continue reading data when the device is
    reconnected.

    :param device: Bluetooth device to read data from.
    :param args: Addition read arguments.
    """
    raise NotImplementedError(
        'Read function for {} is not implemented'.format(device)
    )

async def read_all(device: DeviceBase[Service, T]) -> AsyncIterator[T]:
    """
    Read all data from Bluetooth device.

    It ignores cancellation errors.

    :param device: Bluetooth device to read data from.
    """
    while is_active():
        try:
            value = await read(device)
        except asyncio.CancelledError as ex:
            # cancelled calls happen on device disconnection
            logger.info('{}: {}'.format(device, ex))
        else:
            yield value

@singledispatch
async def write(device: DeviceBase[Service, T], data: bytes) -> None:
    """
    Write data to Bluetooth device.

    :param device: Bluetooth device to write data to.
    :param data: Data to write to the Bluetooth device.
    """
    raise NotImplementedError(
        'Write function for {} is not implemented'.format(device)
    )

@singledispatch
async def enable(device: DeviceBase[Service, T]) -> None:
    """
    Enable and configure Bluetooth device.

    The function is called when a Bluetooth device is connected or
    reconnected.
    """

@singledispatch
async def disable(device: DeviceBase[Service, T]) -> None:
    """
    Disable Bluetooth device.

    The function is called when device is disconnected to release any
    resources held by the device.

    While the device might be gone and thus it is not possible to, for
    example, switch off a sensor on a Bluetooth device, there might be
    other resources to release like Bluez notification setup.
    """

@read.register
async def _read_dev(device: Device[ServiceCharacteristic, T]) -> T:
    async with connected(device) as session:
        bus = session.bus
        path = bus.characteristic_path(device.mac, device.service.uuid_data)
        assert path is not None

        task = session.create_future(
            device,
            _btzen.bt_read(bus.system_bus, path, DEFAULT_DBUS_TIMEOUT)
        )
        data = await task
        return device.convert(data)

@read.register
async def _read_dev_int(device: DeviceTrigger[ServiceInterface, T]) -> T:
    async with connected(device) as session:
        bus = session.bus
        srv = device.service

        task = session.create_future(
            device,
            bus._dev_property_get(device.mac, srv.property, srv.interface)
        )
        data = await task
        return device.convert(data)

@read.register
async def _read_dev_tr(device: DeviceTrigger[ServiceCharacteristic, T]) -> T:
    async with connected(device) as session:
        bus = session.bus
        path = bus.characteristic_path(device.mac, device.service.uuid_data)
        task = session.create_future(device, bus._gatt_get(path))
        data = await task
        return device.convert(data)

@enable.register
async def _enable_dev(device: Device[ServiceCharacteristic, T]) -> None:
    bus = get_session().bus
    await bus.ensure_characteristic_paths(device.mac, device.service.uuid_data)

@enable.register
async def _enable_int(device: DeviceTrigger[ServiceInterface, T]) -> None:
    bus = get_session().bus
    srv = device.service
    bus._dev_property_start(device.mac, srv.property, iface=srv.interface)

@enable.register
async def _enable_dev_trigger(
        device: DeviceTrigger[ServiceCharacteristic, T]
    ) -> None:

    bus = get_session().bus
    await bus.ensure_characteristic_paths(device.mac, device.service.uuid_data)

    path = bus.characteristic_path(device.mac, device.service.uuid_data)
    assert path is not None
    bus._gatt_start(path)
    logger.info('notifications enabled for {}'.format(path))

@disable.register
async def _disable_int(device: DeviceTrigger[ServiceInterface, T]) -> None:
    bus = get_session().bus
    srv = device.service
    bus._dev_property_stop(device.mac, srv.property, iface=srv.interface)

@disable.register
async def _disable_device_trigger(device: DeviceTrigger[ServiceCharacteristic, T]) -> None:
    bus = get_session().bus
    srv = device.service
    path = bus.characteristic_path(device.mac, srv.uuid_data)
    assert path is not None

    await disarm(
        'notifications for {} are disabled'.format(device),
        'cannot disable notifications for {}'.format(device),
        bus._gatt_stop, path
    )

async def write_config(mac: str, uuid: str, data: bytes) -> None:
    bus = get_session().bus
    path = bus.characteristic_path(mac, uuid)
    await _btzen.bt_write(
        bus.system_bus, path, data, DEFAULT_DBUS_TIMEOUT
    )

async def disarm(
        msg: str, warn: str, f: tp.Callable[..., tp.Any], *args: tp.Any
    ) -> None:
    try:
        if inspect.iscoroutinefunction(f):
            await f(*args)
        else:
            f(*args)
        logger.info(msg)
    except asyncio.CancelledError as ex:
        if not is_active():
            raise
        else:
            logger.warning(warn + ': ' + str(ex))
    except Exception as ex:
        logger.warning(warn + ': ' + str(ex))

# vim: sw=4:et:ai
