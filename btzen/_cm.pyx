#
# BTZen - Bluetooth Smart sensor reading library.
#
# Copyright (C) 2015-2018 by Artur Wroblewski <wrobell@riseup.net>
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

# distutils: language = c
# cython: c_string_type=unicode, c_string_encoding=utf8, language_level=3str

"""
Bluetooth connection management.
"""

import asyncio
import logging

from ._sd_bus cimport *
from . import _sd_bus

logger = logging.getLogger(__name__)

cdef extern from *:
    """
    #include <string.h>
    void create_vtable(sd_bus_message_handler_t f_release, sd_bus_property_get_t f_property, sd_bus_vtable** ret) {
        /* FIXME: fix the local variable issue */
        sd_bus_vtable cm_vtable[] = {
            SD_BUS_VTABLE_START(0),
            SD_BUS_METHOD("Release", "", "", f_release, 0),
            SD_BUS_PROPERTY("UUIDs", "as", f_property, 0, SD_BUS_VTABLE_PROPERTY_CONST),
            SD_BUS_VTABLE_END
        };
        *ret = malloc(4 * sizeof(sd_bus_vtable));
        memcpy(*ret, cm_vtable, 4 * sizeof(sd_bus_vtable));
    }
    """
    void create_vtable(sd_bus_message_handler_t, sd_bus_property_get_t, sd_bus_vtable**)
#   cdef sd_bus_vtable *cm_vtable = [
#       SD_BUS_VTABLE_START(0),
#       SD_BUS_METHOD('Release', '', '', cm_release, 0),
#       SD_BUS_PROPERTY('UUIDs', 'as', cm_property, 0, SD_BUS_VTABLE_PROPERTY_CONST),
#       SD_BUS_VTABLE_END
#   ]

cdef int cm_release(sd_bus_message *msg, void *user_data, sd_bus_error *error) with gil:
    return sd_bus_reply_method_return(msg, '')

cdef int cm_property(
        sd_bus *bus,
        const char *path,
        const char *interface,
        const char *prop,
        sd_bus_message *reply,
        void *user_data,
        sd_bus_error *error
    ) with gil:

    #cdef object cm = <object>user_data
    cdef char* uv
    r = sd_bus_message_append(reply, 'as', 1, "f000aa64-0451-4000-b000-000000000000", NULL)
    return r

    # TODO
    #if prop != 'UUIDs':
    #    return -ENOENT

#   for uuid in cm.uuid:
#       uv = uuid
#       r = sd_bus_message_append(reply, 'as', 1, uv, NULL)
#       _sd_bus.check_call('message append', r)
#   return 0

async def cm_init(Bus bus, cm):
    cdef sd_bus_vtable *cm_vtable

    create_vtable(cm_release, cm_property, &cm_vtable)

    task = asyncio.get_event_loop().create_future()

    r = sd_bus_add_object_manager(bus.bus, NULL, '/')
    _sd_bus.check_call('add object manager', r)

    r = sd_bus_add_object_vtable(
        bus.bus,
        NULL,
        '/org/btzen/ConnectionManager',
        'org.bluez.GattProfile1',
        cm_vtable,
        NULL
    )
    _sd_bus.check_call('add cm vtable', r)

    r = sd_bus_call_method_async(
        bus.bus,
        NULL,
        'org.bluez',
        '/org/bluez/hci0',
        'org.bluez.GattManager1',
        'RegisterApplication',
        task_cb,
        <void*>task,
         'oa{sv}',
         '/',
         0
    )
    _sd_bus.check_call('register application call', r)
    await task

cdef int task_cb(sd_bus_message *msg, void *user_data, sd_bus_error *ret_error) with gil:
    cdef object task = <object>user_data
    cdef BusMessage bus_msg = BusMessage.__new__(BusMessage)
    bus_msg.c_obj = msg

    return _sd_bus.task_handle_message(bus_msg, task, ConnectionError, None)

async def bt_connect(Bus bus, str path, str address):
    """
    Connect to Bluetooth device.

    :param bus: D-Bus reference.
    :param path: D-Bus adapter path.
    :param address: Bluetooth device address.
    """
    assert bus is not None

    buff = address.encode()
    cdef sd_bus_message *msg = NULL
    cdef unsigned char *addr_data = buff

    task = asyncio.get_event_loop().create_future()
    try:
        r = sd_bus_message_new_method_call(
            bus.bus,
            &msg,
            'org.bluez',
            path.encode(),
            'org.bluez.Adapter1',
            'ConnectDevice'
        )
        _sd_bus.check_call('write data to {}'.format(path), r)

        r = sd_bus_message_append(msg, 'a{sv}', 2, 'Address', 's', addr_data, "AddressType", "s", "public")
        _sd_bus.check_call('write data to {}'.format(path), r)

        r = sd_bus_call_async(bus.bus, NULL, msg, task_cb, <void*>task, 0)
        _sd_bus.check_call('write data to {}'.format(path), r)

        return (await task)
    finally:
        sd_bus_message_unref(msg)

# vim: sw=4:et:ai
