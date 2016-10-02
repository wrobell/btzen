#
# BTZen - Bluetooh Smart sensor reading library.
#
# Copyright (C) 2015 by Artur Wroblewski <wrobell@pld-linux.org>
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
import time
from collections import namedtuple

from _btzen import ffi, lib

logger = logging.getLogger(__name__)

Parameters = namedtuple('Parameters', [
    'path_data', 'path_conf', 'path_period', 'config_on',
    'config_on_notify', 'config_off',
])

def _mac(mac):
    return mac.replace(':', '_').upper()

class Bus:
    def __init__(self, loop=None):
        self._loop = asyncio.get_event_loop() if loop is None else loop

        self._bus_ref = ffi.new('sd_bus **')
        lib.sd_bus_open_system(self._bus_ref)
        self._bus = self._bus_ref[0]

        self._fd = lib.sd_bus_get_fd(self._bus)
        self._loop.add_reader(self._fd, self._process_event)

        self._sensors = {}

    def connect(self, *args):
        for mac in args:
            path = '/org/bluez/hci0/dev_{}'.format(_mac(mac))
            path = ffi.new('char[]', path.encode())
            r = lib.bt_device_connect(self._bus, path)
            for i in range(10):
                resolved = lib.bt_device_services_resolved(self._bus, path)
                if resolved == 1:
                    break
                logger.debug(
                    'bluetooth device {} services not resolved, wait 1s...'
                    .format(mac)
                )
                time.sleep(1)
            if i == 9:
                raise ValueError('not resolved')

        items = []
        root = dev_chr = ffi.new('t_bt_device_chr **')
        r = lib.bt_device_chr_list(self._bus, dev_chr)
        while dev_chr != ffi.NULL and dev_chr[0] != ffi.NULL:
            uuid = ffi.string(dev_chr[0].uuid)[:]
            path = ffi.string(dev_chr[0].path)[:]
            dev_chr = dev_chr[0].next
            items.append((path, uuid))
        lib.bt_device_chr_list_free(root[0]);

        self._chr_uuid = items

    def sensor(self, mac, cls, notifying=False):
        assert isinstance(cls.UUID_DATA, str)
        assert isinstance(cls.UUID_CONF, str)
        assert isinstance(cls.UUID_PERIOD, str)

        params = Parameters(
            self._find_path(mac, cls.UUID_DATA),
            self._find_path(mac, cls.UUID_CONF),
            self._find_path(mac, cls.UUID_PERIOD),
            cls.CONFIG_ON,
            cls.CONFIG_ON_NOTIFY,
            cls.CONFIG_OFF,
        )
        reader = cls(params, self._bus, self._loop, notifying)
        self._sensors[reader._device] = reader
        return reader

    def _process_event(self):
        processed = 1
        while processed > 0:
            processed = lib.sd_bus_process(self._bus, ffi.NULL)
            device = lib.bt_device_last()
            if processed == 1 and device != ffi.NULL:
                assert device in self._sensors
                sensor = self._sensors[device]
                sensor.set_result()

    def _find_path(self, mac, uuid):
        mac = _mac(mac).encode()
        uuid = uuid.encode()
        items = (p for p, u in self._chr_uuid if mac in p and uuid == u)
        return next(items, None)

# vim: sw=4:et:ai
