#
# BTZen - library to asynchronously access Bluetooth devices.
#
# Copyright (C) 2015-2021 by Artur Wroblewski <wrobell@riseup.net>
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

from __future__ import annotations

import asyncio
import dataclasses as dtc
import logging
import typing as tp
from functools import singledispatch

from . import _btzen  # type: ignore
from .config import DEFAULT_DBUS_TIMEOUT
from .ndevice import T, DeviceBase, Device, DeviceTrigger, NoTrigger, \
    Trigger, TriggerCondition
from .service import S, Service, ServiceInterface, ServiceCharacteristic, \
    ServiceEnvSensing
from .error import CallError
from .session import get_session, connected

logger = logging.getLogger(__name__)

@singledispatch
async def read(device: DeviceBase[Service, T], *args: tp.Any) -> T:
    """
    Read data from Bluetooth device.

    The coroutine can raise cancellation error (`asyncio.CancelledError`),
    i.e. when the device is disconnected. The caller should handle the
    error, if it wants to continue reading data when the device is
    reconnected.
    """
    pass

@singledispatch
async def write(device: DeviceBase[Service, T], data: bytes):
    pass

def set_interval(
        device: DeviceBase[S, T],
        interval: float,
    ) -> DeviceTrigger[S, T]:
    """
    Set fixed time interval for Bluetooth Environmental Sensing device.

    This is equivalent to::

        set_trigger(TriggerCondition.FIXED_TIME, interval)

    :param device: Bluetooth device descriptor.
    :param interval: Interval in seconds.
    """
    return set_trigger(device, TriggerCondition.FIXED_TIME, operand=interval)

@singledispatch
def set_trigger(
        device: DeviceBase[S, T],
        condition: TriggerCondition,
        *,
        operand: tp.Optional[float]=None,
        ) -> DeviceTrigger[S, T]:
    """
    Set trigger for Bluetooth Environmental Sensing device.
    """
    return DeviceTrigger(
        device.service,
        device.mac,
        device.address_type,
        device.convert,
        Trigger(condition, operand),
    )

def unset_trigger(device: DeviceTrigger[S, T]) -> Device[S, T]:
    """
    Set trigger for Bluetooth Environmental Sensing device.
    """
    return Device(
        device.service,
        device.mac,
        device.address_type,
        device.convert,
    )

@singledispatch
async def enable(device: DeviceBase[Service, T]):
    """
    Enable and configure Bluetooth device.

    The function is called when a Bluetooth device is connected or
    reconnected.
    """

@singledispatch
async def disable(device: DeviceBase[Service, T]):
    """
    Disable Bluetooth device.

    The function is called when device is disconnected to release any
    resources held by the device.

    While the device might be gone and thus it is not possible to, for
    example, switch off a sensor on a Bluetooth device, there might be
    other resources to release like Bluez notification setup.
    """
    pass

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
async def _enable(device: Device[ServiceCharacteristic, T]):
    bus = get_session().bus
    await bus.ensure_characteristic_paths(device.mac, device.service.uuid_data)

@enable.register
async def _enable_int(device: DeviceTrigger[ServiceInterface, T]):
    bus = get_session().bus
    srv = device.service
    bus._dev_property_start(device.mac, srv.property, iface=srv.interface)

@enable.register
async def _enable_tr(device: DeviceTrigger[ServiceCharacteristic, T]):
    bus = get_session().bus
    await enable(unset_trigger(device))
    path = bus.characteristic_path(device.mac, device.service.uuid_data)
    assert path is not None

    bus._gatt_start(path)
    logger.info('notifications enabled for {}'.format(path))

@enable.register
async def _enable_env_sensing(device: Device[ServiceEnvSensing, T]):
    bus = get_session().bus
    srv = device.service
    await bus.ensure_characteristic_paths(
        device.mac, srv.uuid_data, srv.uuid_conf, srv.uuid_trigger
    )
    await write_config(device.mac, srv.uuid_conf, srv.config_on)

@disable.register
async def _disable_int(device: DeviceTrigger[ServiceInterface, T]):
    bus = get_session().bus
    srv = device.service
    bus._dev_property_stop(device.mac, srv.property, iface=srv.interface)

@disable.register
async def _disable_tr(device: DeviceTrigger[ServiceCharacteristic, T]):
    bus = get_session().bus
    srv = device.service
    path = bus.characteristic_path(device.mac, srv.uuid_data)
    assert path is not None

    await disarm(
        'notifications for {} are disabled'.format(device),
        'cannot disable notifications for {}'.format(device),
        bus._gatt_stop, path
    )
    await disable(unset_trigger(device))

@disable.register
async def _disable_env_sensing(device: Device[ServiceEnvSensing, T]):
    srv = device.service
    await disarm_async(
        '{} disabled'.format(device),
        'cannot disable {}'.format(device),
        write_config, device.mac, srv.uuid_conf, srv.config_off
    )

async def write_config(mac: str, uuid: str, data: bytes):
    bus = get_session().bus
    path = bus.characteristic_path(mac, uuid)
    await _btzen.bt_write(
        bus.system_bus, path, data, DEFAULT_DBUS_TIMEOUT
    )

# TODO: there is disarm in btzen.cm
async def disarm(msg: str, warn: str, f, *args):
    try:
        f(*args)
        logger.info(msg)
    except (Exception, asyncio.CancelledError) as ex:
        logger.warning(warn + ': ' + str(ex))

async def disarm_async(msg: str, warn: str, f, *args):
    try:
        await f(*args)
        logger.info(msg)
    except (Exception, asyncio.CancelledError) as ex:
        logger.warning(warn + ': ' + str(ex))

# vim: sw=4:et:ai
