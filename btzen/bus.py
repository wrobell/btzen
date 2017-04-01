#
# BTZen - Bluetooh Smart sensor reading library.
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

import asyncio
import logging
import threading
import time
from functools import lru_cache

from _btzen import ffi, lib
from .error import ConnectionError

logger = logging.getLogger(__name__)

def _mac(mac):
    return mac.replace(':', '_').upper()

class Bus:
    THREAD_LOCAL = threading.local()

    def __init__(self, loop):
        self._loop = loop

        self._fd = lib.sd_bus_get_fd(self.get_bus())
        self._loop.add_reader(self._fd, self._process_event)

        self._sensors = {}

    @staticmethod
    def get_bus():
        """
        Get system bus reference.

        The reference is local to current thread.
        """
        local = Bus.THREAD_LOCAL
        if not hasattr(local, 'bus'):
            local.bus = SDBus()
        return local.bus.bus

    def connect(self, mac):
        """
        Connect to Bluetooth device.

        If connected, the method does nothing.

        :param mac: MAC address of Bluetooth device.
        """
        path = self._get_device_path(mac)
        connected = lib.bt_device_property_bool(
            self.get_bus(), path, 'Connected'.encode()
        )
        if connected != 1:
            r = lib.bt_device_connect(self.get_bus(), path)
            if r < 0:
                raise ConnectionError('Connection to {} failed'.format(mac))
            for i in range(10):
                resolved = lib.bt_device_property_bool(
                    self.get_bus(), path, 'ServicesResolved'.encode()
                )
                if resolved == 1:
                    break
                logger.debug(
                    'bluetooth device {} services not resolved, wait 1s...'
                    .format(mac)
                )
                time.sleep(1)
            if i == 9:
                raise ConnectionError('Cannot resolve services of {}'.format(mac))
        return self._get_device_name(mac)

    def register(self, sensor):
        """
        Register sensor on the sensor bus.
        """
        self._sensors[sensor._device] = sensor

    def unregister(self, sensor):
        """
        Unregister sensor object from the sensor bus.
        """
        sensors = self._sensors
        dev = sensor._device
        if dev in sensors:
            del sensors[dev]

    def sensor_path(self, mac, uuid):
        if uuid is None:
            return b''

        paths = self._get_sensor_paths(mac)
        uuid = uuid.encode()
        items = (p for p, u in paths if uuid == u)
        return next(items, None)

    @lru_cache()
    def _get_sensor_paths(self, mac):
        mac = _mac(mac).encode()
        items = []
        root = dev_chr = ffi.new('t_bt_device_chr **')
        r = lib.bt_device_chr_list(self.get_bus(), dev_chr)
        while dev_chr != ffi.NULL and dev_chr[0] != ffi.NULL:
            uuid = ffi.string(dev_chr[0].uuid)[:]
            path = ffi.string(dev_chr[0].path)[:]
            dev_chr = dev_chr[0].next
            if mac in path:
                items.append((path, uuid))
        lib.bt_device_chr_list_free(root[0]);
        return items

    @lru_cache()
    def _get_device_name(self, mac):
        path = self._get_device_path(mac)
        return self._get_property_str(path, 'Name')

    @lru_cache()
    def _get_device_path(self, mac):
        path = '/org/bluez/hci0/dev_{}'.format(_mac(mac))
        path = ffi.new('char[]', path.encode())
        return path

    def _get_property_str(self, path, property):
        value = ffi.new('char**')
        property = property.encode()
        r = lib.bt_device_property_str(self.get_bus(), path, property, value)
        return ffi.string(value[0]).decode()

    def _process_event(self):
        processed = lib.sd_bus_process(self.get_bus(), ffi.NULL)
        while processed > 0:
            processed = lib.sd_bus_process(self.get_bus(), ffi.NULL)


class SDBus:
    """
    Reference to default system bus (sd-bus).
    """
    def __init__(self):
        self.bus_ref = ffi.new('sd_bus **')
        lib.sd_bus_default_system(self.bus_ref)
        self.bus = self.bus_ref[0]

    def __del__(self):
        lib.sd_bus_unref(self.bus)
        logger.info('reference to system bus destroyed')

# vim: sw=4:et:ai
