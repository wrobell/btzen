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

import cffi

ffi = cffi.FFI()
ffi.cdef("""
typedef struct sd_bus sd_bus;
typedef struct sd_bus_message sd_bus_message;

typedef struct {
    char *chr_data;
    char *chr_conf;
    char *chr_period;
    uint8_t *data;
    size_t len;
} t_bt_device;

typedef struct bt_device_chr {
    char *path;
    char *uuid;
    struct bt_device_chr *next;
} t_bt_device_chr;

int sd_bus_open_system(sd_bus**);
int sd_bus_process(sd_bus*, sd_bus_message**);
int sd_bus_get_fd(sd_bus*);
void *sd_bus_get_current_userdata(sd_bus*);

int bt_device_connect(sd_bus*, const char*);
int bt_device_services_resolved(sd_bus*, const char*);
t_bt_device *bt_device_last(void);
int bt_device_write(sd_bus*, const char*, const uint8_t*, ssize_t);
int bt_device_read(sd_bus*, t_bt_device*, uint8_t[]);
int bt_device_start_notify(sd_bus*, t_bt_device*);
int bt_device_stop_notify(sd_bus*, t_bt_device*);
int bt_device_read_async(sd_bus*, t_bt_device *dev);
int bt_device_chr_list(sd_bus*, t_bt_device_chr**);
void bt_device_chr_list_free(t_bt_device_chr*);
""")

ffi.set_source('_btzen', """
#include "btzen.c"
""", libraries=['systemd'], include_dirs=['.'])

# vim: sw=4:et:ai
