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
Connection manager to manage connections of multiple Bluetooth devices.

Based on

    https://gist.github.com/parthitce/eb6b751df3235f7247babc4c9aba41d8

NOTE: Discovery is still required on devices like Raspberry Pi to reconnect
    a long running device.

When starting and running connection manager

1. Register Bluetooth agent.
2. Create connection manager object on D-Bus event bus and register UUIDs
   of services of devices to be managed by the connection manager.
3. For each device
3.1. Remove device preemptively to allow new connection.
3.2. Use `ConnectDevice` method of adapter interface to connect to the
     device. If fails, then move to 3.1 above.
3.3. Set the device to be seen as trusted.
3.4. Wait for `ServicesResolved` property to be changed.
3.4.1. If the property is set to true enable Bluetooth device.
3.4.2. If the property is set to false, then disable Bluetooth device.

When connection manager is closed

1. Close each Bluetooth device.
2. Disconnect each Bluetooth device.
3. Remove each Bluetooth device.
4. Unregister Bluetooth agent.
5. Close connection manager.

"""

import asyncio
import logging
import typing as tp
from collections import defaultdict
from collections.abc import Coroutine, AsyncGenerator, AsyncIterator
from contextlib import asynccontextmanager
from contextvars import ContextVar
from functools import partial
from operator import attrgetter

from . import _cm  # type: ignore
from .bus import Bus
from .error import BTZenError
from .config import DEFAULT_DBUS_TIMEOUT, DEFAULT_CONNECTION_TIMEOUT
from .data import T, AddressType
from .device import DeviceBase
from .devio import enable, disable, disarm
from .session import BT_SESSION, Session, get_session, is_active
from .service import S
from .util import concat

Devices = tp.Iterable[DeviceBase[S, T]]

logger = logging.getLogger(__name__)


@asynccontextmanager
async def connect(
        devices: Devices,  # type: ignore
        *,
        interface: str='hci0'
    ) -> AsyncIterator[Session]:

    bus = Bus.create_bus(interface)
    adapter_path = bus.adapter_path()

    session = Session(bus)
    BT_SESSION.set(session)

    # TODO: use context variable
    _dbus_timeout = DEFAULT_DBUS_TIMEOUT
    await _cm.bt_register_agent(bus.system_bus, _dbus_timeout)

    by_mac = defaultdict(set)
    for dev in devices:
        by_mac[dev.mac].add(dev)

    # TODO: if bluez daemon is restarted, the connection manager needs
    # to be reinitialized
    bt_services = set(dev.service.uuid for dev in concat(by_mac.values()))
    cm_handle = await _cm.cm_init(bus.system_bus, adapter_path, bt_services)

    for mac, devs in by_mac.items():
        task = manage_connection(bus, mac, devs)
        session.add_connection_task(mac, task)

    session.start()
    try:
        yield session
    finally:
        session.stop()

        await disarm(
            'agent unregistered',
            'agent failed to unregister',
            _cm.bt_unregister_agent,
            bus.system_bus
        )

        await disarm(
            'connection manager unregistered',
            'connection manager failed to unregister',
            _cm.cm_close,
            bus.system_bus,
            adapter_path,
            cm_handle
        )

async def manage_connection(bus: Bus, mac: str, devices: Devices) -> None:  # type: ignore
    """
    Manage Bluetooth connection for the devices.
    """
    # determine connection address type and favour random one
    address_types = set(dev.address_type for dev in devices)
    has_random = AddressType.RANDOM in address_types
    address_type = AddressType.RANDOM if has_random else AddressType.PUBLIC

    # enable monitoring of the `ServicesResolved` property first
    bus._dev_property_start(mac, 'ServicesResolved')

    # create connection to a device; if it exists already, then remove it
    # first; if it exists in bluez daemon registry, then creating new
    # connection blocks
    created = False
    while not created and is_active():
        await remove_connection(bus, mac)
        created = await create_connection(bus, mac, address_type)

    try:
        await restart_devices(bus, mac, devices)
    finally:
        bus._dev_property_stop(mac, 'ServicesResolved')

        await disarm(
            'device {} disconnected'.format(mac),
            'device {} failed to disconnect'.format(mac),
            _cm.bt_disconnect,
            bus.system_bus,
            bus.dev_path(mac),
        )

        await remove_connection(bus, mac)

# TODO: make real async
async def remove_connection(bus: Bus, mac: str) -> None:
    await disarm(
        'connection for device {} removed'.format(mac),
        'removal of connection failed for device {}'.format(mac),
        _cm.bt_remove,
        bus.system_bus,
        bus.adapter_path(),
        bus.dev_path(mac)
    )

async def create_connection(
        bus: Bus,
        mac: str,
        address_type: AddressType,
    ) -> bool:
    # create connection to a device
    #
    # NOTE: bluez 5.50 - scanning by external programs shall be off or we
    # will never connect

    _dbus_timeout = DEFAULT_DBUS_TIMEOUT

    created = False
    dev_path = bus.dev_path(mac)
    try:
        logger.info(
            'connect device {} via controller {}, address type {}'
            .format(mac, bus.adapter_path(), address_type)
        )
        await _cm.bt_connect(
            bus.system_bus, bus.adapter_path(), mac, address_type.value,
            DEFAULT_CONNECTION_TIMEOUT
        )
    except (BTZenError, asyncio.CancelledError) as ex:
        is_active = get_session().is_active()
        if is_active and str(ex) == 'Already Exists':
            created = True
        elif is_active:
            sleep = int(_dbus_timeout / 1e6)
            logger.info(
                'connection for {} failed: {}, sleep for {}s'
                .format(mac, ex, sleep)
            )
            await asyncio.sleep(sleep)
    else:
        created = True

    if created:
        _cm.bt_device_set_trusted(bus.system_bus, dev_path)
    return created

async def enable_devices(mac: str, devices: Devices) -> None:  # type: ignore
    logger.info('enabling devices: {}'.format(mac))

    for dev in devices:
        await enable(dev)

    get_session().set_connected(mac)
    logger.info('enabled services: {}'.format(mac))

async def disable_devices(mac: str, devices: Devices) -> None:  # type: ignore
    logger.info('disabling services: {}'.format(mac))

    session = get_session()

    # clear connection flag as soon as possible, to prevent reading from
    # disabled device
    session.set_disconnected(mac)
    session.cancel_device_tasks(mac, 'Disable device')

    for dev in devices:
        # no exception checks as the disable functions should not raise
        # exceptions on failure
        await disable(dev)

    logger.info('disabled services: {}'.format(mac))

async def restart_devices(bus: Bus, mac: str, devices: Devices) -> None:  # type: ignore
    """
    Enable or disable Bluetooth device when property 'ServicesResolved`
    changes.
    """
    # the `ServicesResolved` property monitoring is started by a caller, so
    # just wait for services to be resolved
    async for resolved in resolve_services(bus, mac, devices):
        try:
            enabled = False
            if resolved:
                await enable_devices(mac, devices)
                enabled = True
        except asyncio.CancelledError as ex:
            logger.info(
                'enabling devices for %s failed, seems to be not connected',
                mac
            )
            if not is_active():
                raise
        finally:
            # not resolved or not all devices enabled, then disable all;
            # some devices might be partially disabled and they still need
            # release other resources, i.e. d-bus related
            if not enabled:
                # some devices might be enabled, so try to disable them
                await disable_devices(mac, devices)

async def resolve_services(
        bus: Bus, mac: str, devices: Devices  # type: ignore
    ) -> AsyncGenerator[bool, None]:
    """
    Asynchronous generator waiting for a Bluetooth device to be
    resolved.
    """
    while True:
        logger.info(
            'device {} waiting for services resolved status change'
            .format(mac)
        )
        resolved = await bus._dev_property_get(mac, 'ServicesResolved')
        logger.info('device {} services resolved: {}'.format(mac, resolved))
        yield resolved

# vim: sw=4:et:ai
