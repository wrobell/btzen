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

# distutils: language = c
# cython: c_string_type=unicode, c_string_encoding=utf8

from libc.stdio cimport perror
from libc.string cimport strerror
from libc.errno cimport errno

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

    # int sd_bus_call_method(sd_bus*, const char*, const char*, const char*, const char*, sd_bus_error*, sd_bus_message**, const char*, ...)
    int sd_bus_call_method_async(sd_bus*, sd_bus_slot**, const char*, const char*, const char*, const char*, sd_bus_message_handler_t, void*, const char*, ...)

    const sd_bus_error *sd_bus_message_get_error(sd_bus_message*)
    int sd_bus_message_skip(sd_bus_message*, const char*)

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

def bt_process(Bus bus):
    cdef sd_bus_message *msg
    return sd_bus_process(bus.bus, &msg)

# vim: sw=4:et:ai
