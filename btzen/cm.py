#
# BTZen - library to asynchronously access Bluetooth devices.
#
# Copyright (C) 2015-2020 by Artur Wroblewski <wrobell@riseup.net>
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
     device. If fails, then move to 4.1 above.
3.3. Wait for `ServicesResolved` property to be changed.
3.3.1. If the property is set to true enable Bluetooth device.
3.3.2. If the property is set to false, then disable Bluetooth device.

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
from functools import partial
from itertools import chain
from operator import attrgetter

from .bus import Bus
from .device import Device
from . import _cm  # type: ignore

DeviceDict = tp.DefaultDict[str, tp.Set[Device]]
Devices = tp.Iterable[Device]

flatten = chain.from_iterable

logger = logging.getLogger(__name__)

FMT_PATH_ADAPTER = '/org/bluez/{}'.format

class ConnectionManager:
    def __init__(self, interface='hci0'):
        self._interface = interface
        self._devices: DeviceDict = defaultdict(set)
        self._connected = {}
        self._process = False
        self._handle = None

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
        bus = self._get_bus()
        self._process = False
        for dev in flatten(self._devices.values()):
            dev.close()

        for mac in self._devices:
            self._disconnect(mac)

        _cm.bt_unregister_agent(bus.system_bus)

        if self._handle is not None:
            adapter_path = FMT_PATH_ADAPTER(self._interface)
            _cm.cm_close(bus.system_bus, adapter_path, self._handle)
        logger.info('connection manager closed')

    async def connected(self, mac: str) -> None:
        if not mac in self._connected:
            raise ValueError(
                'Device with address {} not managed by the connection manager'
                .format(mac)
            )
        await self._connected[mac].wait()

    def __await__(self):
        self._process = True
        bus = self._get_bus()
        path = FMT_PATH_ADAPTER(self._interface)

        yield from _cm.bt_register_agent(bus.system_bus).__await__()

        # TODO: if bluez daemon is restarted, the connection manager needs
        # to be reinitialized
        handle = yield from _cm.cm_init(bus.system_bus, path, self).__await__()
        self._handle = handle

        f = self._reconnect
        tasks = (f(mac, devs) for mac, devs in self._devices.items())
        yield from asyncio.gather(*tasks).__await__()

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
        while not connected:
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
        bus = self._get_bus()
        enable = partial(self._enable, mac, devices)
        disable = partial(self._disable, mac, devices)
        cn_set = self._connected[mac].set

        # the `ServicesResolved` property monitoring is started by a
        # caller, so just wait for the service to be resolved
        async for _ in self._resolve_services(mac, devices):
            try:
                logger.info('enabling device {}'.format(mac))
                await enable()
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
        try:
            logger.info(
                'connect device {} via controller {}, address type {}'
                .format(mac, adapter_path, address_type)
            )
            await _cm.bt_connect(bus.system_bus, adapter_path, mac, address_type)
        except Exception as ex:
            if str(ex) == 'Already Exists':
                connected = True
            else:
                logger.info(
                    'connection for {} failed: {}, sleep for 1s'
                    .format(mac, ex)
                )
                await asyncio.sleep(1)
        else:
            connected = True
        return connected


    async def _preempt_remove_dev(self, bus: Bus, mac: str, adapter_path: str):
        dev_path = bus.dev_path(mac)
        try:
            _cm.bt_remove(bus.system_bus, adapter_path, dev_path)
        except Exception as ex:
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
        return Bus.get_bus(self._interface)

# vim: sw=4:et:ai
