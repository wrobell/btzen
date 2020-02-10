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

# distutils: language = c
# cython: c_string_type=unicode, c_string_encoding=utf8, language_level=3str

from libc.stdio cimport perror
from libc.string cimport strerror
from libc.stdint cimport uint8_t
from libc.errno cimport errno
from cpython.bytes cimport PyBytes_FromStringAndSize

import logging
from contextlib import contextmanager

from ._sd_bus cimport *
from .error import *

logger = logging.getLogger(__name__)

ERROR_HINTS = {
}

cdef class Bus:
    @property
    def fileno(self):
        return self._fd_no

def default_bus():
    """
    Get default system bus connection.
    """
    cdef Bus bus = Bus.__new__(Bus)
    cdef int r

    r = sd_bus_default_system(&bus.bus)
    check_call('connect bus', r)
    bus._fd_no = sd_bus_get_fd(bus.bus)

    return bus

def check_call(msg_err, code):
    """
    Raise call error if a D-Bus call has failed.
    """
    if code < 0:
        msg_err = 'Call failed - {}: {} ({})'.format(
            msg_err, strerror(-code), code
        )
        logger.debug('got error code {}: '.format(code, strerror(-code)))
        raise CallError(msg_err)

#
# sd-bus message parsing
#
class BusMessageError(Error):
    """
    Bus message parsing error.
    """

def check_msg_error(r):
    if r < 0:
        raise BusMessageError(
            'D-Bus message parsing error: {}'.format(strerror(-r))
        )

def task_handle_message(BusMessage bus_msg, task, cls_err, value_type: str):
    """
    Handle asynchronous task result or error.

    :param bus_msg: D-Bus message representation as Python object.
    :param task: Asynchronous task instance.
    :param cls: Class of exception to be raised on error.
    :param value_type: Type of value to be read from D-Bus message.
    """
    cdef const sd_bus_error *error = sd_bus_message_get_error(bus_msg.c_obj)

    if task.done():
        return 0
    elif error and error.message:
        task.set_exception(cls_err(error.message))
    elif value_type is None:
        task.set_result(None)
    else:
        value = msg_read_value(bus_msg, value_type)
        task.set_result(value)
    return 0

@contextmanager
def msg_container(BusMessage bus_msg, str type, str contents):
    """
    Parse single D-Bus container entry of given type and contents.
    """
    cdef char msg_type = ord(type)
    cdef sd_bus_message *msg = bus_msg.c_obj
    assert msg != NULL

    r = sd_bus_message_enter_container(msg, msg_type, contents.encode())
    check_msg_error(r)

    yield

    r = sd_bus_message_exit_container(msg)
    check_msg_error(r)

def msg_container_dict(BusMessage bus_msg, str contents):
    """
    Loop over items of D-Bus message dictionary container.
    """
    with msg_container(bus_msg, 'a', contents):
        for _ in msg_container_loop(bus_msg, 'e', contents[1:-1]):
            yield

def msg_container_loop(BusMessage bus_msg, str type, str contents):
    """
    Loop over items of D-Bus message container.

    For dictionary containers use `msg_container_dict`.
    """
    cdef char msg_type = ord(type)
    cdef sd_bus_message *msg = bus_msg.c_obj

    while True:
        r = sd_bus_message_enter_container(msg, msg_type, contents.encode())
        check_msg_error(r)
        if r == 0:
            break

        yield

        r = sd_bus_message_exit_container(msg)
        check_msg_error(r)

def msg_read_value(BusMessage bus_msg, str type):
    """
    Read a value from a sd-bus message of given type.

    Supported values

    - boolean
    - signed short int
    - string
    - byte array
    - variant
    """
    cdef sd_bus_message *msg = bus_msg.c_obj

    cdef bytes value_str
    cdef int value
    cdef uint8_t value_byte
    cdef signed short value_short
    cdef const void *buff
    cdef size_t buff_size
    cdef char *buff_str
    cdef const char *contents
    cdef char msg_type_v

    msg_type = type.encode()

    if msg_type == b'b':
        r = sd_bus_message_read_basic(msg, 'b', &value)
        check_msg_error(r)
        r_value = value == 1

    elif msg_type == b'n':
        r = sd_bus_message_read_basic(msg, 'n', &value_short)
        check_msg_error(r)
        r_value = value_short

    elif msg_type == b'y':
        r = sd_bus_message_read_basic(msg, 'y', &value_byte)
        check_msg_error(r)
        r_value = value_byte

    elif msg_type == b'ay':
        r = sd_bus_message_read_array(msg, 'y', &buff, &buff_size)
        check_msg_error(r)

        r_value = PyBytes_FromStringAndSize(<char*>buff, buff_size)
        logger.debug('array value of size: {}'.format(buff_size))

    elif msg_type == b's' or msg_type == b'o':
        r = sd_bus_message_read(msg, msg_type, &buff_str)
        check_msg_error(r)
        r_value = <str>buff_str
        logger.debug('string value: {} of size {}'.format(r_value, len(r_value)))

    elif msg_type == b'v':
        r = sd_bus_message_peek_type(msg, &msg_type_v, &contents)
        check_msg_error(r)
        assert chr(msg_type_v) == 'v', (msg_type, contents)

        with msg_container(bus_msg, type, contents):
            r_value = msg_read_value(bus_msg, contents)
    else:
        # FIXME: add support for other types
        raise BusMessageError('Unknown message type: {}'.format(type))

    return r_value

def msg_skip(BusMessage bus_msg, str type):
    """
    Skip D-Bus message entry of given type.
    """
    r = sd_bus_message_skip(bus_msg.c_obj, type.encode())
    check_msg_error(r)

# vim: sw=4:et:ai
