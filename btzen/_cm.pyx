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

# distutils: language = c
# cython: c_string_type=unicode, c_string_encoding=utf8, language_level=3str

"""
Bluetooth connection management.
"""

from libc.stdint cimport uint64_t
from libc.stdlib cimport malloc, free

import asyncio
import logging

from ._sd_bus cimport *
from . import _sd_bus

logger = logging.getLogger(__name__)

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

    cdef set services = <object>user_data
    cdef int r

    size = len(services) + 1
    cdef char **arr = <char**>malloc(size * sizeof(char*))

    for i, u in enumerate(sorted(services)):
        logger.info('register reconnection for service: {}'.format(u))
        arr[i] = u
    arr[size - 1] = NULL

    r = sd_bus_message_append_strv(reply, arr)
    free(arr)

    _sd_bus.check_call('adding services uuids', r)
    return 0

async def cm_init(Bus bus, str path, set services):
    """
    Initialize connection manager.
    """
    cdef sd_bus_slot *slot
    cdef sd_bus_slot *handle_slot

    handle = ConnectionManagerHandle()
    create_vtable(cm_release, cm_property, &handle.vtable)

    task = asyncio.get_event_loop().create_future()

    r = sd_bus_add_object_manager(bus.bus, NULL, '/')
    _sd_bus.check_call('add object manager', r)

    r = sd_bus_add_object_vtable(
        bus.bus,
        &handle_slot,
        '/org/btzen/ConnectionManager',
        'org.bluez.GattProfile1',
        handle.vtable,
        <void*>services
    )
    _sd_bus.check_call('add cm vtable', r)

    r = sd_bus_call_method_async(
        bus.bus,
        &slot,
        'org.bluez',
        path.encode(),
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
        sd_bus_slot_unref(handle_slot)
        raise
    else:
        handle.slot = handle_slot

    try:
        await task
    finally:
        sd_bus_slot_unref(slot)

    return handle

def cm_close(Bus bus, str path, handle):
    """
    Close connection manager.
    """
    assert bus is not None

    cdef sd_bus_message *msg = NULL
    cdef sd_bus_error error = SD_BUS_ERROR_NULL

    handle.stop()

    try:
        r = sd_bus_call_method(
            bus.bus,
            'org.bluez',
            path.encode(),
            'org.bluez.GattManager1',
            'UnregisterApplication',
            &error,
            &msg,
             'o',
             '/',
             NULL
        )
        _sd_bus.check_call('unregister application call', r)
    finally:
        sd_bus_error_free(&error);
        sd_bus_message_unref(msg);

cdef int task_cb(sd_bus_message *msg, void *user_data, sd_bus_error *ret_error) with gil:
    cdef object task = <object>user_data
    cdef BusMessage bus_msg = BusMessage.__new__(BusMessage)
    bus_msg.c_obj = msg

    return _sd_bus.task_handle_message(bus_msg, task, ConnectionError, None)

async def bt_connect(
        Bus bus, str path, str address, str address_type, uint64_t timeout
    ):
    """
    Connect to Bluetooth device.

    :param bus: D-Bus reference.
    :param path: D-Bus adapter path.
    :param address: Bluetooth device address.
    :param address_type: Bluetooth device address type (public or random).
    :param timeout: Call timeout in microseconds.
    """
    assert bus is not None

    buff_addr = address.encode()
    buff_addr_type = address_type.encode()

    cdef sd_bus_slot *slot = NULL
    cdef sd_bus_message *msg = NULL
    cdef unsigned char *addr_data = buff_addr
    cdef unsigned char *addr_type_data = buff_addr_type

    task = asyncio.get_event_loop().create_future()

    r = sd_bus_message_new_method_call(
        bus.bus,
        &msg,
        'org.bluez',
        path.encode(),
        'org.bluez.Adapter1',
        'ConnectDevice'
    )

    try:
        _sd_bus.check_call('bt connect call prepare {}'.format(path), r)

        r = sd_bus_message_append(
            msg, 'a{sv}', 2,
            'Address', 's', addr_data,
            "AddressType", "s", addr_type_data,
        )
        _sd_bus.check_call('bt connect call args {}'.format(path), r)

        r = sd_bus_call_async(
            bus.bus, &slot, msg, task_cb, <void*>task, timeout
        )
        _sd_bus.check_call('bt connect call {}'.format(path), r)
    finally:
        sd_bus_message_unref(msg)

    try:
        return (await task)
    finally:
        sd_bus_slot_unref(slot)

def bt_device_set_trusted(Bus bus, str path):
    """
    Set Bluetooth device to be seen as trusted.

    :param bus: D-Bus reference.
    :param path: D-Bus device path.
    """
    cdef sd_bus_error error = SD_BUS_ERROR_NULL

    try:
        r = sd_bus_set_property(
            bus.bus,
            'org.bluez',
            path.encode(),
            'org.bluez.Device1',
            'Trusted',
            &error,
            'b',
            1,
            NULL
        );
        _sd_bus.check_call('trust device', r)
    finally:
        sd_bus_error_free(&error);

def bt_disconnect(Bus bus, str path):
    """
    Disconnect Bluetooth device.

    :param bus: D-Bus reference.
    :param path: D-Bus device path.
    """
    assert bus is not None

    cdef sd_bus_message *msg = NULL
    cdef sd_bus_error error = SD_BUS_ERROR_NULL

    try:
        r = sd_bus_call_method(
            bus.bus,
            'org.bluez',
            path.encode(),
            'org.bluez.Device1',
            'Disconnect',
            &error,
            &msg,
            NULL,
            NULL
        )
        _sd_bus.check_call('disconnect device', r)
    finally:
        sd_bus_error_free(&error);
        sd_bus_message_unref(msg);

def bt_remove(Bus bus, str adapter, str device):
    """
    Remove Bluetooth device.

    :param bus: D-Bus reference.
    :param adapter: D-Bus adapter path.
    :param device: D-Bus device path.
    """
    assert bus is not None

    cdef sd_bus_message *msg = NULL
    cdef sd_bus_error error = SD_BUS_ERROR_NULL

    buff = device.encode()
    cdef unsigned char *dev_data = buff

    try:
        r = sd_bus_call_method(
            bus.bus,
            'org.bluez',
            adapter.encode(),
            "org.bluez.Adapter1",
            'RemoveDevice',
            &error,
            &msg,
            'o',
            dev_data
        )
        _sd_bus.check_call('remove device', r)
    finally:
        sd_bus_error_free(&error);
        sd_bus_message_unref(msg);

async def bt_register_agent(Bus bus, uint64_t timeout):
    """
    Register pairing agent for BTZen library.

    :param bus: D-Bus reference.
    :param timeout: Call timeout in microseconds.
    """
    assert bus is not None
    await _bt_agent_register_agent(bus, timeout)
    await _bt_agent_request_default_agent(bus, timeout)

async def _bt_agent_register_agent(Bus bus, uint64_t timeout):
    """
    Register auto pair Bluetooth agent.

    :param bus: D-Bus reference.
    :param timeout: Call timeout in microseconds.
    """
    assert bus is not None
    cdef sd_bus_message *msg = NULL

    try:
        task = asyncio.get_event_loop().create_future()
        r = sd_bus_message_new_method_call(
            bus.bus,
            &msg,
            'org.bluez',
            '/org/bluez',
            'org.bluez.AgentManager1',
            'RegisterAgent'
        )
        _sd_bus.check_call('agent registration call prepare', r)

        r = sd_bus_message_append(msg, 'os', '/org/btzen/Agent', 'NoInputNoOutput')
        _sd_bus.check_call('agent registration params', r)

        r = sd_bus_call_async(
            bus.bus, NULL, msg, task_cb, <void*>task, timeout
        )
        _sd_bus.check_call('agent registration call', r)

        return (await task)
    finally:
        sd_bus_message_unref(msg)

async def _bt_agent_request_default_agent(Bus bus, uint64_t timeout):
    """
    Request Bluetooth default agent.

    :param bus: D-Bus reference.
    :param timeout: Call timeout in microseconds.
    """
    assert bus is not None
    cdef sd_bus_message *msg = NULL
    cdef unsigned char *arg_data

    try:
        task = asyncio.get_event_loop().create_future()
        r = sd_bus_message_new_method_call(
            bus.bus,
            &msg,
            'org.bluez',
            '/org/bluez',
            'org.bluez.AgentManager1',
            'RequestDefaultAgent'
        )
        _sd_bus.check_call('agent registration call prepare', r)

        r = sd_bus_message_append(msg, 'o', '/org/btzen/Agent')
        _sd_bus.check_call('agent registration params', r)

        r = sd_bus_call_async(
            bus.bus, NULL, msg, task_cb, <void*>task, timeout
        )
        _sd_bus.check_call('agent registration call', r)

        return (await task)
    finally:
        sd_bus_message_unref(msg)

def bt_unregister_agent(Bus bus):
    """
    Unregister auto pair agent.

    :param bus: D-Bus reference.
    """
    assert bus is not None

    cdef sd_bus_message *msg = NULL
    cdef sd_bus_error error = SD_BUS_ERROR_NULL

    try:
        r = sd_bus_call_method(
            bus.bus,
            'org.bluez',
            '/org/bluez',
            "org.bluez.AgentManager1",
            'UnregisterAgent',
            &error,
            &msg,
            'o',
            '/org/btzen/Agent',
            NULL
        )
        _sd_bus.check_call('unregister agent', r)
    finally:
        sd_bus_error_free(&error);
        sd_bus_message_unref(msg);

# vim: sw=4:et:ai
