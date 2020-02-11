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

# distutils: language = c
# cython: c_string_type=unicode, c_string_encoding=utf8, language_level=3str

from libc.stdio cimport perror
from libc.string cimport strerror
from libc.errno cimport errno

import asyncio
import logging

from ._sd_bus cimport *
from . import _sd_bus
from .error import *

logger = logging.getLogger(__name__)

FMT_RULE = """
type='signal',
sender='org.bluez',
interface='org.freedesktop.DBus.Properties',
member='PropertiesChanged',
path='{}',
arg0='{}'
"""

cdef class PropertyNotification:
    """
    Property notification based on asyncio queue class.

    The `put` method is used to add new value for a property. The `get`
    coroutine allows to retrieve property value in asynchronous manner.
    """
    cdef sd_bus_slot *slot
    cdef public object queues
    cdef public str path

    def __init__(self, path):
        self.queues = {}
        self.path = path

    def register(self, name):
        assert name not in self.queues
        assert self.slot is not NULL
        self.queues[name] = asyncio.Queue()

    def is_registered(self, name):
        return name in self.queues

    def put(self, name, value):
        assert name in self.queues
        assert self.slot is not NULL
        self.queues[name].put_nowait(value)

    async def get(self, name):
        assert name in self.queues
        assert self.slot is not NULL
        return (await self.queues[name].get())

    def size(self, name) -> int:
        return self.queues[name].qsize()

    def stop(self):
        self.queues.clear()
        sd_bus_slot_unref(self.slot)

cdef fmt_rule(iface, path):
    rule = FMT_RULE.format(path, iface)
    rule = rule.strip().replace('\n', '')
    return rule.encode()

cdef int task_cb_read(sd_bus_message *msg, void *user_data, sd_bus_error *ret_error) with gil:
    cdef object task = <object>user_data
    cdef const sd_bus_error *error = sd_bus_message_get_error(msg)
    cdef BusMessage bus_msg = BusMessage.__new__(BusMessage)
    bus_msg.c_obj = msg

    return _sd_bus.task_handle_message(bus_msg, task, DataReadError, 'ay')

async def bt_read(Bus bus, str path, timeout=0):
    assert bus is not None

    cdef sd_bus_message *msg = NULL
    cdef sd_bus_slot *slot = NULL

    task = asyncio.get_event_loop().create_future()

    r = sd_bus_message_new_method_call(
        bus.bus,
        &msg,
        'org.bluez',
        path.encode(),
        'org.bluez.GattCharacteristic1',
        'ReadValue'
    )
    _sd_bus.check_call('prepare read data from {}'.format(path), r)

    r = sd_bus_message_open_container(msg, 'a', '{sv}')
    _sd_bus.check_call('write data to {}'.format(path), r)

    r = sd_bus_message_close_container(msg)
    _sd_bus.check_call('write data to {}'.format(path), r)

    r = sd_bus_call_async(
        bus.bus, &slot,
        msg, task_cb_read,
        <void*>task,
        1e6 * timeout
    )
    _sd_bus.check_call('read data from {}'.format(path), r)

    try:
        return (await task)
    finally:
        sd_bus_message_unref(msg)
        sd_bus_slot_unref(slot)

cdef int task_cb_write(sd_bus_message *msg, void *user_data, sd_bus_error *ret_error) with gil:
    """
    Data write callback used by `bt_write` function.
    """
    cdef object task = <object>user_data
    cdef BusMessage bus_msg = BusMessage.__new__(BusMessage)
    bus_msg.c_obj = msg

    return _sd_bus.task_handle_message(bus_msg, task, DataWriteError, None)

async def bt_write(Bus bus, str path, bytes data):
    """
    Write data to Bluetooth device.

    :param bus: D-Bus reference.
    :param path: GATT characteristics path of the device.
    :param data: Data to write.
    """
    assert bus is not None

    cdef sd_bus_message *msg = NULL
    cdef sd_bus_slot *slot = NULL
    cdef char* buff = data

    task = asyncio.get_event_loop().create_future()
    try:
        r = sd_bus_message_new_method_call(
            bus.bus,
            &msg,
            'org.bluez',
            path.encode(),
            'org.bluez.GattCharacteristic1',
            'WriteValue'
        )
        _sd_bus.check_call('write data to {}'.format(path), r)

        r = sd_bus_message_append_array(msg, 'y', buff, len(data))
        _sd_bus.check_call('write data to {}'.format(path), r)

        r = sd_bus_message_open_container(msg, 'a', '{sv}')
        _sd_bus.check_call('write data to {}'.format(path), r)

        r = sd_bus_message_close_container(msg)
        _sd_bus.check_call('write data to {}'.format(path), r)

        r = sd_bus_call_async(bus.bus, &slot, msg, task_cb_write, <void*>task, 0)
        _sd_bus.check_call('write data to {}'.format(path), r)

        return (await task)
    finally:
        sd_bus_message_unref(msg)
        sd_bus_slot_unref(slot)

def bt_write_sync(Bus bus, str path, bytes data):
    """
    Write data to Bluetooth device.

    :param bus: D-Bus reference.
    :param path: GATT characteristics path of the device.
    :param data: Data to write.
    """
    assert bus is not None

    cdef sd_bus_message *msg = NULL
    cdef sd_bus_message *ret_msg = NULL
    cdef sd_bus_error error = SD_BUS_ERROR_NULL
    cdef char* buff = data

    r = sd_bus_message_new_method_call(
        bus.bus,
        &msg,
        'org.bluez',
        path.encode(),
        'org.bluez.GattCharacteristic1',
        'WriteValue'
    )
    _sd_bus.check_call('write data to {}'.format(path), r)

    r = sd_bus_message_append_array(msg, 'y', buff, len(data))
    _sd_bus.check_call('write data to {}'.format(path), r)

    r = sd_bus_message_open_container(msg, 'a', '{sv}')
    _sd_bus.check_call('write data to {}'.format(path), r)

    r = sd_bus_message_close_container(msg)
    _sd_bus.check_call('write data to {}'.format(path), r)

    r = sd_bus_call(bus.bus, msg, 0, &error, &ret_msg)
    _sd_bus.check_call('write data to {}'.format(path), r)

cdef int task_cb_property_monitor(sd_bus_message *msg, void *user_data, sd_bus_error *ret_error) with gil:
    cdef object cb = <object>user_data
    cdef const char *path
    cdef BusMessage bus_msg = BusMessage.__new__(BusMessage)

    path = sd_bus_message_get_path(msg)
    assert path == cb.path
    bus_msg.c_obj = msg

    # skip interface name
    _sd_bus.msg_skip(bus_msg, 's')

    for _ in _sd_bus.msg_container_dict(bus_msg, '{sv}'):
        name = _sd_bus.msg_read_value(bus_msg, 's')
        if cb.is_registered(name):
            value = _sd_bus.msg_read_value(bus_msg, 'v')
            cb.put(name, value)
        else:
            _sd_bus.msg_skip(bus_msg, 'v')

    return 0

def bt_property_monitor_start(Bus bus, str path, str iface):
    """
    Enable notification of value changes of Bluetooth device property.

    Property notification object is returned, which allows to register
    property names.

    :param bus: D-Bus reference.
    :param path: GATT characteristics path of the device.
    :param iface: Device interface.
    """
    assert bus is not None

    cdef sd_bus_slot *slot

    rule = fmt_rule(iface, path)
    data = PropertyNotification(path)

    r = sd_bus_add_match(
        bus.bus,
        &slot,
        rule,
        task_cb_property_monitor,
        <void*>data
    )
    _sd_bus.check_call('bus match rule', r)
    assert slot is not NULL

    data.slot = slot
    return data

async def bt_property(Bus bus, str path, str iface, str name, str type):
    assert bus is not None

    cdef sd_bus_message *msg = NULL
    cdef sd_bus_error error = SD_BUS_ERROR_NULL
    cdef BusMessage bus_msg = BusMessage.__new__(BusMessage)

    r = sd_bus_get_property(
        bus.bus,
        'org.bluez',
        path.encode(),
        iface.encode(),
        name.encode(),
        &error,
        &msg,
        type.encode()
    )
    _sd_bus.check_call('getting property {}'.format(name), r)

    bus_msg.c_obj = msg
    value =_sd_bus.msg_read_value(bus_msg, type)
    sd_bus_message_unref(msg)
    sd_bus_error_free(&error)

    return value

def bt_notify_start(Bus bus, str path):
    """
    Start monitoring value changes of a device identified by GATT
    characteristics path.

    :param bus: D-Bus reference.
    :param path: GATT characteristics path of the device.
    """
    assert bus is not None

    cdef sd_bus_message *msg = NULL
    cdef sd_bus_error error = SD_BUS_ERROR_NULL

    iface = 'org.bluez.GattCharacteristic1'

    r = sd_bus_call_method(
        bus.bus,
        'org.bluez',
        path.encode(),
        iface.encode(),
        'StartNotify',
        &error,
        &msg,
        NULL,
        NULL
    )
    sd_bus_error_free(&error);
    sd_bus_message_unref(msg);

    _sd_bus.check_call('start notification', r)

def bt_notify_stop(Bus bus, str path):
    """
    Stop monitoring value changes of a device identified by GATT
    characteristics path.

    :param bus: D-Bus reference.
    :param path: GATT characteristics path of the device.
    """
    assert bus is not None

    cdef sd_bus_message *msg = NULL
    cdef sd_bus_error error = SD_BUS_ERROR_NULL

    try:
        r = sd_bus_call_method(
            bus.bus,
            'org.bluez',
            path.encode(),
            'org.bluez.GattCharacteristic1',
            'StopNotify',
            &error,
            &msg,
            NULL,
            NULL
        )
        _sd_bus.check_call('stop notification', r)
    finally:
        sd_bus_error_free(&error)
        sd_bus_message_unref(msg)

def bt_process(Bus bus):
    """
    Process D-Bus events.
    """
    cdef int r
    assert bus is not None

    r = sd_bus_process(bus.bus, NULL)
    while r > 0:
        r = sd_bus_process(bus.bus, NULL)

def bt_characteristic(Bus bus, str prefix, str uuid):
    """
    Fetch Gatt Characteristic path relative to `prefix` and for specified
    UUID.
    """
    assert bus is not None

    cdef sd_bus_message *msg = NULL
    cdef sd_bus_error error = SD_BUS_ERROR_NULL
    cdef BusMessage bus_msg = BusMessage.__new__(BusMessage)

    try:
        r = sd_bus_call_method(
            bus.bus,
            'org.bluez',
            '/',
            'org.freedesktop.DBus.ObjectManager',
            'GetManagedObjects',
            &error,
            &msg,
            NULL
        )
        if r < 0:
            raise ConfigurationError(
                'Failed to get GATT characteristics paths: {}'
                .format(strerror(-r))
            )

        bus_msg.c_obj = msg

        path = _find_characteristic_path(bus_msg, prefix, uuid)

    finally:
        sd_bus_message_unref(msg)
        sd_bus_error_free(&error)

    return path

def _find_characteristic_path(BusMessage bus_msg, str prefix, str uuid):
    for _ in _sd_bus.msg_container_dict(bus_msg, '{oa{sa{sv}}}'):
        chr_path = _sd_bus.msg_read_value(bus_msg, 'o')

        if not chr_path.startswith(prefix):
             _sd_bus.msg_skip(bus_msg, 'a{sa{sv}}')
             continue

        for _ in _sd_bus.msg_container_dict(bus_msg, '{sa{sv}}'):
            iface = _sd_bus.msg_read_value(bus_msg, 's')

            if iface != 'org.bluez.GattCharacteristic1':
                _sd_bus.msg_skip(bus_msg, 'a{sv}')
                continue

            for _ in _sd_bus.msg_container_dict(bus_msg, '{sv}'):
                name = _sd_bus.msg_read_value(bus_msg, 's')
                if name == 'UUID':
                    value = _sd_bus.msg_read_value(bus_msg, 'v')
                    if uuid == value:
                        return chr_path
                else:
                    _sd_bus.msg_skip(bus_msg, 'v')
    return None

# vim: sw=4:et:ai
