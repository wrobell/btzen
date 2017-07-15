#
# BTZen - Bluetooth Smart sensor reading library.
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

# distutils: language = c
# cython: c_string_type=unicode, c_string_encoding=utf8

from libc.stdio cimport perror
from libc.string cimport strerror
from libc.errno cimport errno

from cpython.bytes cimport PyBytes_FromStringAndSize

import asyncio
import logging

logger = logging.getLogger(__name__)

cdef extern from "<systemd/sd-bus.h>":
    ctypedef struct sd_bus:
        pass

    ctypedef struct sd_bus_message:
        pass

    ctypedef struct sd_bus_slot:
        pass

    ctypedef struct sd_bus_error:
        const char *name
        const char *message

    ctypedef int (*sd_bus_message_handler_t)(sd_bus_message*, void*, sd_bus_error*)

    int sd_bus_default_system(sd_bus**)
    int sd_bus_get_fd(sd_bus*)
    int sd_bus_process(sd_bus*, sd_bus_message**)

    int sd_bus_call_method(sd_bus*, const char*, const char*, const char*, const char*, sd_bus_error*, sd_bus_message**, const char*, ...)
    int sd_bus_call_method_async(sd_bus*, sd_bus_slot**, const char*, const char*, const char*, const char*, sd_bus_message_handler_t, void*, const char*, ...)
    int sd_bus_message_new_method_call(sd_bus*, sd_bus_message**, const char*, const char*, const char*, const char*)
    int sd_bus_message_append_array(sd_bus_message*, char, const void*, size_t)
    int sd_bus_message_open_container(sd_bus_message*, char, const char*)
    int sd_bus_message_close_container(sd_bus_message*)
    int sd_bus_call(sd_bus*, sd_bus_message*, long, sd_bus_error*, sd_bus_message**)

    int sd_bus_get_property(sd_bus*, const char*, const char*, const char*, const char*, sd_bus_error*, sd_bus_message**, const char*)

    const sd_bus_error *sd_bus_message_get_error(sd_bus_message*)
    int sd_bus_message_read(sd_bus_message*, const char*, ...)
    int sd_bus_message_read_basic(sd_bus_message*, char, void*)
    int sd_bus_message_read_array(sd_bus_message*, char, const void**, size_t*)
    int sd_bus_message_enter_container(sd_bus_message*, char, const char*)
    int sd_bus_message_exit_container(sd_bus_message*)
    int sd_bus_message_skip(sd_bus_message*, const char*)
    int sd_bus_message_get_type(sd_bus_message*, unsigned char*)
    int sd_bus_message_peek_type(sd_bus_message*, char*, const char**)

    int sd_bus_add_match(sd_bus*, sd_bus_slot**, const char*, sd_bus_message_handler_t, void*)

    sd_bus *sd_bus_unref(sd_bus*)
    sd_bus_message *sd_bus_message_unref(sd_bus_message*)
    void sd_bus_error_free(sd_bus_error*)

cdef sd_bus_error SD_BUS_ERROR_NULL = sd_bus_error(NULL, NULL, 0)

cdef class Bus:
    cdef sd_bus *bus
    cdef readonly int _fd_no

    @property
    def fileno(self):
        return self._fd_no

cdef class BusMessage:
    """
    Python level wrapper around SD bus message structure.
    """
    cdef sd_bus_message *c_obj

class PropertyChange:
    def __init__(self, *args):
        self._queue = asyncio.Queue()
        self.filter = set(args)

    def put(self, name, value):
        self._queue.put_nowait((name, value))

    async def get(self):
        return (await self._queue.get())

class ValueChange:
    def __init__(self):
        self._queue = asyncio.Queue()
        self.filter = {'Value'}

    def put(self, name, value):
        self._queue.put_nowait(value)

    async def get(self):
        return (await self._queue.get())

class BtError(Exception):
    pass

class FatalError(BtError):
    pass

class BtRuntimeError(BtError):
    pass

class ConnectionError(BtRuntimeError):
    pass

def default_bus():
    cdef Bus bus = Bus.__new__(Bus)

    sd_bus_default_system(&bus.bus)
    bus._fd_no = sd_bus_get_fd(bus.bus)

    return bus

cdef int task_callback(sd_bus_message *msg, void *user_data, sd_bus_error *ret_error) with gil:
    cdef object task = <object>user_data
    cdef const sd_bus_error *error = sd_bus_message_get_error(msg)

    if error and error.message:
        task.set_exception(ConnectionError(error.message))
    else:
        task.set_result(None)
    return 1

def bt_connect(Bus bus, str path, task):
    r = sd_bus_call_method_async(
        bus.bus,
        NULL,
        'org.bluez',
        path.encode(),
        'org.bluez.Device1',
        'Connect',
        task_callback,
        <void*>task,
        NULL,
        NULL
    )
    if r < 0:
        raise FatalError('Failed to issue connection call for {}'.format(path))

cdef int bt_wait_for_callback(sd_bus_message *msg, void *user_data, sd_bus_error *ret_error) with gil:
    cdef object cb = <object>user_data
    cdef char *name
    cdef int value
    cdef signed short value_short
    cdef const char *contents
    cdef char msg_type
    cdef const void *buff
    cdef size_t buff_size
    cdef BusMessage bus_msg = BusMessage.__new__(BusMessage)

    bus_msg.c_obj = msg

    r = sd_bus_message_skip(msg, 's')
    assert r == 1

    for _ in msg_container(bus_msg, 'a', '{sv}'):
        for _ in msg_container(bus_msg, 'e', 'sv'):
            r = sd_bus_message_read_basic(msg, 's', &name)

            r = sd_bus_message_peek_type(msg, &msg_type, &contents)
            assert chr(msg_type) == 'v', (name, msg_type, contents)

            if cb.filter and name not in cb.filter:
                continue

            for _ in msg_container(bus_msg, 'v', contents):
                if <bytes>contents == b'b':
                    r = sd_bus_message_read_basic(msg, 'b', &value)
                    assert r >= 0
                    r_value = value == 1

                elif <bytes>contents == b'n':
                    r = sd_bus_message_read_basic(msg, 'n', &value_short)
                    assert r >= 0
                    r_value = value_short

                elif <bytes>contents == b'ay':
                    r = sd_bus_message_read_array(msg, 'y', &buff, &buff_size)
                    assert r >= 0

                    r_value = PyBytes_FromStringAndSize(<char*>buff, buff_size)
                    logger.debug('array value of size {}'.format(buff_size))
                else:
                    # FIXME: add support for other types
                    assert False, 'unsupported type {}'.format(contents)

                cb.put(name, r_value)
    return 1

def bt_wait_for(Bus bus, str path, str iface, object data):
    cdef sd_bus_message *msg = NULL
    cdef sd_bus_error error = SD_BUS_ERROR_NULL

    rule = """\
type='signal',\
sender='org.bluez',\
interface='org.freedesktop.DBus.Properties',\
member='PropertiesChanged',\
path='{}',\
arg0='{}'""".format(path, iface)

#   r = sd_bus_call_method(
#       bus.bus,
#       'org.bluez',
#       path.encode(),
#       iface.encode(),
#       'StartNotify',
#       &error,
#       &msg,
#       NULL,
#       NULL
#   )
#   print('match start', r)
#    if (r < 0) {
#        fprintf(stderr, "Failed to issue StartNotify call: %s\n", error.message);
#        goto finish;
#    }
    r = sd_bus_add_match(bus.bus, NULL, rule.encode(), bt_wait_for_callback, <void*>data)
#    if (r < 0)
#        fprintf(stderr, "Failed to add match rule: %s\n", strerror(-r));
#

def bt_property_str(Bus bus, str path, str iface, str name):
    cdef sd_bus_message *msg = NULL
    cdef sd_bus_error error = SD_BUS_ERROR_NULL
    cdef char *value

    r = sd_bus_get_property(
        bus.bus,
        'org.bluez',
        path.encode(),
        iface.encode(),
        name.encode(),
        &error,
        &msg,
        's'
    )
    assert r == 0
#    if (r < 0) {
#        fprintf(stderr, "Failed to read Name property: %s\n", error.message);
#        goto finish;
#    }
    r = sd_bus_message_read(msg, 's', &value)
    assert r > 0
    #if (r < 0)
    #    fprintf(stderr, "Failed to get Name property data\n");
    sd_bus_message_unref(msg)
    sd_bus_error_free(&error)

    return value

def bt_write(Bus bus, str path, bytes data):
    cdef sd_bus_message *msg = NULL
    cdef sd_bus_message *reply = NULL
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
    assert r >= 0
    #if (r < 0) {
    #    fprintf(stderr, "Failed to create call to WriteValue\n");
    #    goto finish;
    #}

    sd_bus_message_append_array(msg, 'y', buff, len(data))
    sd_bus_message_open_container(msg, 'a', '{sv}')
    sd_bus_message_close_container(msg)

    r = sd_bus_call(bus.bus, msg, 0, &error, &reply)
    assert r >= 0
#    if (r < 0) {
#        fprintf(stderr, "Failed to call WriteValue: %s\n", error.message);
#        goto finish;
#    }
#finish:
    sd_bus_error_free(&error)
    sd_bus_message_unref(msg)
    sd_bus_message_unref(reply)

def bt_characteristic_notify(Bus bus, str path, object data):
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
    assert r >= 0, (path, iface)
    bt_wait_for(bus, path, iface, data)

def bt_characteristic_notify_stop(Bus bus, str path):
    cdef sd_bus_message *msg = NULL
    cdef sd_bus_error error = SD_BUS_ERROR_NULL

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
    assert r >= 0
#    if (r < 0)
#        fprintf(stderr, "Failed to issue StopNotify call: %s\n", error.message);

    sd_bus_error_free(&error)
    sd_bus_message_unref(msg)

def bt_process(Bus bus):
    cdef sd_bus_message *msg
    return sd_bus_process(bus.bus, &msg)

def bt_characteristic(Bus bus, str path):
    """
    Fetch Gatt Characteristic paths relative to `path`.

    Dictionary `uuid -> path` is returned.

    TODO: The "relative to path" not working yet.
    """
    cdef sd_bus_message *msg = NULL
    cdef sd_bus_error error = SD_BUS_ERROR_NULL
    cdef char *chr_path
    cdef char *iface
    cdef BusMessage bus_msg = BusMessage.__new__(BusMessage)

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
    assert r >= 0
#    if (r < 0) {
#        fprintf(stderr, "Failed to issue method call: %s\n", error.message);
#        goto finish;
#    }

    bus_msg.c_obj = msg
    data = {}

    for _ in msg_container(bus_msg, 'a', '{oa{sa{sv}}}'):
        for _ in msg_container(bus_msg, 'e', 'oa{sa{sv}}'):
            r = sd_bus_message_read(msg, 'o', &chr_path)
            assert r > 0

            for _ in msg_container(bus_msg, 'a', '{sa{sv}}'):
                for _ in msg_container(bus_msg, 'e', 'sa{sv}'):
                    r = sd_bus_message_read(msg, "s", &iface);
                    assert r > 0
                    r = sd_bus_message_skip(msg, "a{sv}")
                    assert r > 0

                    if <bytes>iface == b'org.bluez.GattCharacteristic1':
                        uuid = bt_property_str(bus, chr_path, 'org.bluez.GattCharacteristic1', 'UUID')
                        data[uuid] = chr_path
#finish:
    sd_bus_message_unref(msg)
    sd_bus_error_free(&error)
    return data

def msg_container(BusMessage bus_msg, str type, str contents):
    """
    Parse SD bus message container entry.
    """
    cdef char msg_type = ord(type)
    cdef sd_bus_message *msg = bus_msg.c_obj

    while sd_bus_message_enter_container(msg, msg_type, contents.encode()) > 0:
        yield
        r = sd_bus_message_exit_container(msg)
        assert r == 1

# vim: sw=4:et:ai
