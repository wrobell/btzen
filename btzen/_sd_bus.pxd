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

    ctypedef struct sd_bus_vtable:
        pass

    ctypedef int (*sd_bus_message_handler_t)(sd_bus_message*, void*, sd_bus_error*)
    ctypedef int (*sd_bus_property_get_t)(sd_bus*, const char*, const char*, const char *, sd_bus_message*, void*, sd_bus_error*)

    int sd_bus_default_system(sd_bus**)
    int sd_bus_get_fd(sd_bus*)
    int sd_bus_process(sd_bus*, sd_bus_message**)
    int sd_bus_add_object_vtable(sd_bus*, sd_bus_slot**, const char*, const char*, const sd_bus_vtable*, void*)
    int sd_bus_add_object_manager(sd_bus*, sd_bus_slot**, const char*)

    int sd_bus_call_method(sd_bus*, const char*, const char*, const char*, const char*, sd_bus_error*, sd_bus_message**, const char*, ...)
    int sd_bus_call_method_async(sd_bus*, sd_bus_slot**, const char*, const char*, const char*, const char*, sd_bus_message_handler_t, void*, const char*, ...)
    int sd_bus_message_new_method_call(sd_bus*, sd_bus_message**, const char*, const char*, const char*, const char*)
    int sd_bus_call(sd_bus*, sd_bus_message*, long, sd_bus_error*, sd_bus_message**)
    int sd_bus_call_async(sd_bus*, sd_bus_slot**, sd_bus_message*, sd_bus_message_handler_t, void*, long)
    int sd_bus_reply_method_return(sd_bus_message*, const char*)

    int sd_bus_message_append_array(sd_bus_message*, char, const void*, size_t)
    int sd_bus_message_append_basic(sd_bus_message*, char, const void*)
    int sd_bus_message_append(sd_bus_message*, const char*, ...)
    int sd_bus_message_append_strv(sd_bus_message*, char**)
    int sd_bus_message_open_container(sd_bus_message*, char, const char*)
    int sd_bus_message_close_container(sd_bus_message*)

    int sd_bus_get_property(sd_bus*, const char*, const char*, const char*, const char*, sd_bus_error*, sd_bus_message**, const char*)

    const sd_bus_error *sd_bus_message_get_error(sd_bus_message*)
    const char *sd_bus_message_get_path(sd_bus_message*)
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
    sd_bus_slot* sd_bus_slot_unref(sd_bus_slot*)

# no idea how use these at the moment, see _cm.pyx for workaround
#   sd_bus_vtable SD_BUS_VTABLE_START(uint64_t)
#   sd_bus_vtable SD_BUS_METHOD(const char*, const char*, const char*, sd_bus_message_handler_t, uint64_t)
#   sd_bus_vtable SD_BUS_PROPERTY(const char*, const char*, sd_bus_property_get_t, size_t, uint64_t)
#   sd_bus_vtable SD_BUS_VTABLE_END

cdef sd_bus_error SD_BUS_ERROR_NULL = sd_bus_error(NULL, NULL, 0)

cdef class Bus:
    """
    Python level wrapper around D-Bus connection.
    """
    cdef sd_bus *bus
    cdef readonly int _fd_no

cdef class BusMessage:
    """
    Python level wrapper around D-Bus message structure.
    """
    cdef sd_bus_message *c_obj

# vim: sw=4:et:ai
