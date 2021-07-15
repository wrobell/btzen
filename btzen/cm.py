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
from contextlib import asynccontextmanager
from contextvars import ContextVar
from functools import partial
from operator import attrgetter

from .bus import Bus
from .error import BTZenError
from .config import DEFAULT_DBUS_TIMEOUT
from .device import Device
from .ndevice import DeviceRegistration, AddressType, enable, disable
from . import _cm  # type: ignore
from .util import concat

DeviceDict = tp.DefaultDict[str, tp.Set[Device]]
Devices = tp.Iterable[Device]

RDeviceDict = tp.DefaultDict[str, set[DeviceRegistration]]
RDevices = tp.Iterable[DeviceRegistration]

logger = logging.getLogger(__name__)

CM_CONNECTION = ContextVar[dict[str, asyncio.Event]]('CM_CONNECTION')
CM_STOP = ContextVar[bool]('CM_STOP')

FMT_PATH_ADAPTER = '/org/bluez/{}'.format

class ConnectionManager:
    def __init__(self, interface='hci0'):
        self._interface = interface
        self._devices: DeviceDict = defaultdict(set)
        self._connected = {}
        self._process = False
        self._handle = None
        self._dbus_timeout = DEFAULT_DBUS_TIMEOUT

        self._connection_tasks = []

        self.enable_timeout = 30

    def add(self, *devices: Device) -> None:
        for dev in devices:
            self._devices[dev.mac].add(dev)
            dev._cm = self
            dev._bus = self._get_bus()
        for mac in self._devices:
            self._connected[mac] = asyncio.Event()

    def close(self) -> None:
        """
        Close connection manager.

        All managed devices are closed and disconnected.
        """
        try:
            bus = self._get_bus()
            self._process = False
            for dev in concat(self._devices.values()):
                dev.close()

            for mac in self._devices:
                self._disconnect(mac)

            # wake up any device waiting for connection
            for mac in self._devices:
                self._connected[mac].set()

            _cm.bt_unregister_agent(bus.system_bus)

            if self._handle is not None:
                adapter_path = FMT_PATH_ADAPTER(self._interface)
                _cm.cm_close(bus.system_bus, adapter_path, self._handle)
        except Exception as ex:
            logger.warning('error when closing connection manager: {}'.format(ex))
        else:
            logger.info('connection manager closed')
        finally:
            for t in self._connection_tasks:
                t.cancel()

    async def connected(self, mac: str) -> None:
        if not mac in self._connected:
            raise ValueError(
                'Device with address {} not managed by the connection manager'
                .format(mac)
            )
        await self._connected[mac].wait()

    def __await__(self) -> tp.Generator:
        self._process = True
        bus = self._get_bus()
        path = FMT_PATH_ADAPTER(self._interface)

        yield from _cm.bt_register_agent(
            bus.system_bus, self._dbus_timeout
        ).__await__()

        # TODO: if bluez daemon is restarted, the connection manager needs
        # to be reinitialized
        handle = yield from _cm.cm_init(bus.system_bus, path, self).__await__()
        self._handle = handle

        self._connection_tasks = [
            asyncio.create_task(self._reconnect(mac, devs))
            for mac, devs in self._devices.items()
        ]
        yield from asyncio.gather(*self._connection_tasks).__await__()

    async def _reconnect(self, mac: str, devices: Devices) -> None:
        bus = self._get_bus()

        # determine connection address type; this is a hack, we need better
        # solution in the future; favour random address type; this is
        # useful when battery level is used (specifies no address type, so
        # defaults to "public) and thingy52 sensors (they require "random"
        # address type)
        address_types = set(
            getattr(dev, 'ADDRESS_TYPE', 'public') for dev in devices
        )
        address_type = 'random' if 'random' in address_types else 'public'

        # enable monitoring of the `ServicesResolved` property first
        bus._dev_property_start(mac, 'ServicesResolved')

        adapter_path = FMT_PATH_ADAPTER(self._interface)

        # remove a device preemptively; if it is left in bluez daemon
        # registry, then it might interfere with establishing of new
        # connection
        connected = False
        while not connected and self._process:
            await self._preempt_remove_dev(bus, mac, adapter_path)
            connected = await self._connect_dev(bus, mac, adapter_path, address_type)

        try:
            await self._restart(mac, devices)
        finally:
            bus._dev_property_stop(mac, 'ServicesResolved')

    async def _restart(self, mac: str, devices: Devices):
        """
        Re-enable or hold Bluetooth device when property 'ServicesResolved`
        changes.
        """
        enable = partial(self._enable, mac, devices)
        disable = partial(self._disable, mac, devices)
        cn_set = self._connected[mac].set

        # the `ServicesResolved` property monitoring is started by a
        # caller, so just wait for the service to be resolved
        async for _ in self._resolve_services(mac, devices):
            try:
                logger.info('enabling device {}'.format(mac))
                await enable()
            except asyncio.CancelledError as ex:
                logger.info(
                    'enabling device %s failed, seems to be not connected',
                    mac
                )
                if self._process:
                    disable()
                else:
                    raise
            except Exception as ex:
                logger.info(
                    'enabling device %s failed, seems to be not connected',
                    mac
                )
                if __debug__:
                    logger.exception('error when enabling %s', mac)

                # disable devices; while a device itself might be
                # disconneted, we might need to release d-bus related
                # resources
                disable()
            else:
                cn_set()

    async def _resolve_services(
            self,
            mac: str,
            devices: Devices,
        ) -> tp.AsyncGenerator[None, None]:
        """
        Asynchronous generator waiting for a Bluetooth device to be
        resolved.
        """
        bus = self._get_bus()
        disable = partial(self._disable, mac, devices)

        while self._process:
            logger.info(
                'device {} waiting for services resolved status change'
                .format(mac)
            )
            resolved = await bus._dev_property_get(mac, 'ServicesResolved')
            logger.info('device {} services resolved: {}'.format(mac, resolved))

            if resolved:
                yield
            else:
                # disable devices; while a device itself might be
                # disconneted, we might need to release d-bus related
                # resources
                disable()

    async def _enable(self, mac: str, devices: Devices) -> None:
        # NOTE: some devices might deadlock when trying to enable multiple
        # subsystems, i.e. sensor tag with button and temperature only; use
        # timeout to try to avoid the deadlock
        while self._process:
            timeout = self.enable_timeout
            try:
                tasks = (dev.enable() for dev in devices)
                tasks = (asyncio.wait_for(t, timeout=timeout) for t in tasks)
                # serialize enabling of devices as the devices might use
                # the common bluetooth characteristics for configuration,
                # i.e. thingy:52
                for t in tasks:
                    await t
                break
            except asyncio.TimeoutError as ex:
                logger.exception('enabling device %s failed due to timeout', mac)

    async def _connect_dev(
            self,
            bus: Bus,
            mac: str,
            adapter_path: str,
            address_type: str,
        ) -> bool:
        # connect to a device
        #
        # NOTE: bluez 5.50 - scanning by external programs shall be off or
        # we will never connect
        connected = False
        dev_path = bus.dev_path(mac)
        try:
            logger.info(
                'connect device {} via controller {}, address type {}'
                .format(mac, adapter_path, address_type)
            )
            await _cm.bt_connect(
                bus.system_bus, adapter_path, mac, address_type,
                self._dbus_timeout
            )
        except asyncio.CancelledError as ex:
            if self._process:
                await self._handle_connection_error(mac, ex)
            else:
                logger.info('connection attempt cancelled for {}'.format(mac))
                raise
        except Exception as ex:
            if str(ex) == 'Already Exists':
                connected = True
            else:
                await self._handle_connection_error(mac, ex)
        else:
            _cm.bt_device_set_trusted(bus.system_bus, dev_path)
            connected = True
        return connected

    async def _handle_connection_error(self, mac, ex: BaseException) -> None:
        sleep = int(self._dbus_timeout / 1e6)
        logger.info(
            'connection for {} failed: {}, sleep for {}s'
            .format(mac, ex, sleep)
        )
        await asyncio.sleep(sleep)

    async def _preempt_remove_dev(self, bus: Bus, mac: str, adapter_path: str):
        dev_path = bus.dev_path(mac)
        try:
            _cm.bt_remove(bus.system_bus, adapter_path, dev_path)
        except (Exception, asyncio.CancelledError) as ex:
            if __debug__:
                logger.debug(
                    'preemptive removal of device {} failed: {}'
                    .format(mac, ex)
                )

    def _disable(self, mac: str, devices) -> None:
        self._connected[mac].clear()
        # no exception checks as the disable methods should not raise
        # exceptions on failure
        for dev in devices:
            dev.disable()

    def _disconnect(self, mac: str) -> None:
        bus = self._get_bus()
        dev_path = bus.dev_path(mac)
        adapter_path = FMT_PATH_ADAPTER(self._interface)
        try:
            _cm.bt_disconnect(bus.system_bus, dev_path)
            logger.info('device {} disconnected'.format(mac))

            _cm.bt_remove(bus.system_bus, adapter_path, dev_path)
            logger.info('device {} removed'.format(mac))
        except Exception as ex:
            logger.warning('error when disconnecting {}: {}'.format(mac, ex))

    def _get_bus(self) -> Bus:
        return Bus.get_bus()

@asynccontextmanager
async def connect(devices: RDevices, *, interface: str='hci0'):
    bus = Bus.create_bus(interface)
    adapter_path = bus.adapter_path()

    CM_STOP.set(False)

    # TODO: use context variable
    _dbus_timeout = DEFAULT_DBUS_TIMEOUT
    await _cm.bt_register_agent(bus.system_bus, _dbus_timeout)

    by_mac: RDeviceDict = defaultdict(set)
    for dev in devices:
        by_mac[dev.mac].add(dev)

    CM_CONNECTION.set({mac: asyncio.Event() for mac in by_mac})

    # TODO: if bluez daemon is restarted, the connection manager needs
    # to be reinitialized
    bt_services = set(dev.device.service for dev in concat(by_mac.values()))
    cm_handle = await _cm.cm_init(bus.system_bus, adapter_path, bt_services)

    conn_tasks = [
        asyncio.create_task(manage_connection(bus, m, devs))
        for m, devs in by_mac.items()
    ]
    for t in conn_tasks:
        t.add_done_callback(stop_tasks)
    try:
        yield
    finally:
        CM_STOP.set(True)
        for t in conn_tasks:
            t.cancel()

        disarm(
            'agent unregistered',
            'agent failed to unregister',
            _cm.bt_unregister_agent,
            bus.system_bus
        )

        disarm(
            'connection manager unregistered',
            'connection manager failed to unregister',
            _cm.cm_close,
            bus.system_bus,
            adapter_path,
            cm_handle
        )

async def manage_connection(bus: Bus, mac: str, devices: RDevices) -> None:
    """
    Manage Bluetooth connection for the devices.
    """
    # determine connection address type; favour random one; is there a
    # better way? thingy52 requires random address type, but its battery
    # service public only (FIXME: check that again)
    address_types = set(dev.address_type for dev in devices)
    has_random = AddressType.RANDOM in address_types
    address_type = AddressType.RANDOM if has_random else AddressType.PUBLIC

    # enable monitoring of the `ServicesResolved` property first
    bus._dev_property_start(mac, 'ServicesResolved')

    # create connection to a device; if it exists already, then remove it
    # first; if it exists in bluez daemon registry, then creating new
    # connection blocks
    created = False
    while not created:
        await remove_connection(bus, mac)
        created = await create_connection(bus, mac, address_type)

    try:
        await restart_devices(bus, mac, devices)
    finally:
        bus._dev_property_stop(mac, 'ServicesResolved')

        # TODO: make async
        disarm(
            'device {} disconnected'.format(mac),
            'device {} failed to disconnect'.format(mac),
            _cm.bt_disconnect,
            bus.system_bus,
            bus.dev_path(mac),
        )

        await remove_connection(bus, mac)

# TODO: make real async
async def remove_connection(bus: Bus, mac: str):
    disarm(
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
            _dbus_timeout
        )
    except (BTZenError, asyncio.CancelledError) as ex:
        stop = CM_STOP.get()
        if not stop and str(ex) == 'Already Exists':
            created = True
        elif not stop:
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

async def enable_devices(mac: str, devices: RDevices):
    logger.info('enabling devices: {}'.format(mac))

    for dev in devices:
        await enable(dev.device, mac)

    CM_CONNECTION.get()[mac].set()
    logger.info('enabled devices: {}'.format(mac))

async def disable_devices(mac: str, devices: RDevices):
    logger.info('disabling devices: {}'.format(mac))

    # clear connection flag as soon as possible, to prevent reading from
    # disabled device
    CM_CONNECTION.get()[mac].clear()

    for dev in devices:
        # no exception checks as the disable functions should not raise
        # exceptions on failure
        await disable(dev.device, mac)

    logger.info('disabled devices: {}'.format(mac))

async def restart_devices(bus: Bus, mac: str, devices: RDevices) -> None:
    """
    Re-enable or hold Bluetooth device when property 'ServicesResolved`
    changes.
    """

    # the `ServicesResolved` property monitoring is started by a
    # caller, so just wait for the service to be resolved
    async for _ in resolve_services(bus, mac, devices):
        try:
            await enable_devices(mac, devices)
        except asyncio.CancelledError as ex:
            logger.info(
                'enabling device %s failed, seems to be not connected',
                mac
            )
            # some devices might be enabled, so try to disable them
            await disable_devices(mac, devices)
            if CM_STOP.get():
                raise

async def resolve_services(bus: Bus, mac: str, devices: RDevices) -> tp.AsyncGenerator[None, None]:
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

        if resolved:
            yield
        else:
            # disable devices; while a device itself might be
            # disconneted, we might need to release d-bus related
            # resources
            await disable_devices(mac, devices)

def stop_tasks(task: asyncio.Task):
    """
    Stop BTZen connection tasks if a task is in error.
    """
    if task.done() and not task.cancelled() and task.exception():
        CM_STOP.set(True)
        try:
            task.result()
        except:
            logger.critical('Error in connection task', exc_info=True) 

def disarm(msg: str, warn: str, f: tp.Callable, *args: tp.Any) -> None:
    try:
        f(*args)
    except asyncio.CancelledError as ex:
        if CM_STOP.get():
            raise
        else:
            logger.warning(warn + ': ' + str(ex))
    except Exception as ex:
        logger.warning(warn + ': ' + str(ex))
    else:
        logger.info(msg)

def is_running() -> bool:
    return not CM_STOP.get()

async def connected(mac: str) -> None:
    cm = CM_CONNECTION.get()    
    if not mac in cm:
        raise ValueError(
            'Device with address {} not managed by BTZen connection manager'
            .format(mac)
        )
    await cm[mac].wait()

# vim: sw=4:et:ai
