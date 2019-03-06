#
# BTZen - Bluetooth Smart sensor reading library.
#
# Copyright (C) 2015-2019 by Artur Wroblewski <wrobell@riseup.net>
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

from libc.stdlib cimport malloc, free

import asyncio
import logging
from itertools import chain

from ._sd_bus cimport *
from . import _sd_bus

logger = logging.getLogger(__name__)

flatten = chain.from_iterable

cdef extern from *:
    # cdef sd_bus_vtable *cm_vtable = [
    #     SD_BUS_VTABLE_START(0),
    #     SD_BUS_METHOD('Release', '', '', cm_release, 0),
    #     SD_BUS_PROPERTY('UUIDs', 'as', cm_property, 0, SD_BUS_VTABLE_PROPERTY_CONST),
    #     SD_BUS_VTABLE_END
    # ]
    """
    #include <string.h>
    void create_vtable(sd_bus_message_handler_t f_release, sd_bus_property_get_t f_property, sd_bus_vtable** ret) {
        /* FIXME: fix the local variable issue */
        sd_bus_vtable vtable[] = {
            SD_BUS_VTABLE_START(0),
            SD_BUS_METHOD("Release", "", "", f_release, 0),
            SD_BUS_PROPERTY("UUIDs", "as", f_property, 0, SD_BUS_VTABLE_PROPERTY_CONST),
            SD_BUS_VTABLE_END
        };
        *ret = malloc(4 * sizeof(sd_bus_vtable));
        memcpy(*ret, vtable, 4 * sizeof(sd_bus_vtable));
    }
    """
    void create_vtable(sd_bus_message_handler_t, sd_bus_property_get_t, sd_bus_vtable**)

cdef class ConnectionManagerHandle:
    cdef sd_bus_slot *slot
    cdef sd_bus_vtable *vtable

    def stop(self):
        sd_bus_slot_unref(self.slot)
        free(self.vtable)

cdef int cm_release(sd_bus_message *msg, void *user_data, sd_bus_error *error) with gil:
    return sd_bus_reply_method_return(msg, NULL)

cdef int cm_property(
        sd_bus *bus,
        const char *path,
        const char *interface,
        const char *prop,
        sd_bus_message *reply,
        void *user_data,
        sd_bus_error *error
    ) with gil:

    cdef object cm = <object>user_data
    cdef int r

    uuids = set(dev.info.service.encode() for dev in flatten(cm._devices.values()))
    size = len(uuids) + 1
    cdef char **arr = <char**>malloc(size * sizeof(char*))

    for i, uv in enumerate(uuids):
        arr[i] = uv
    arr[size - 1] = NULL

    r = sd_bus_message_append_strv(reply, arr)
    free(arr)

    _sd_bus.check_call('adding uuids', r)
    return 0

async def cm_init(Bus bus, cm):
    """
    Initialize connection manager.
    """
    cdef sd_bus_slot *slot

    handle = ConnectionManagerHandle()
    create_vtable(cm_release, cm_property, &handle.vtable)

    task = asyncio.get_event_loop().create_future()

    r = sd_bus_add_object_manager(bus.bus, NULL, '/')
    _sd_bus.check_call('add object manager', r)

    r = sd_bus_add_object_vtable(
        bus.bus,
        &slot,
        '/org/btzen/ConnectionManager',
        'org.bluez.GattProfile1',
        handle.vtable,
        <void*>cm
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
    try:
        _sd_bus.check_call('register application call', r)
    except Exception as ex:
        sd_bus_slot_unref(slot)
        raise
    else:
        handle.slot = slot

    await task
    return handle

def cm_close(Bus bus, handle):
    """
    Close connection manager.
    """
    assert bus is not None

    cdef sd_bus_message *msg = NULL
    cdef sd_bus_error error = SD_BUS_ERROR_NULL

    handle.stop()

    r = sd_bus_call_method(
        bus.bus,
        'org.bluez',
        '/org/bluez/hci0',
        'org.bluez.GattManager1',
        'UnregisterApplication',
        &error,
        &msg,
         'o',
         '/',
         NULL
    )

    sd_bus_error_free(&error);
    sd_bus_message_unref(msg);

    _sd_bus.check_call('unregister application call', r)

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
