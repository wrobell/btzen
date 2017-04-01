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

"""
D-Bus support classes and functions.
"""

import dbus

IFACE = 'org.bluez.GattCharacteristic1'

class Proxy:
    """
    D-Bus object proxy to expose properties via simple attribute access.
    """
    def __init__(self, obj, iface):
        self._obj = obj
        self._iface = iface
        self._properties = dbus.Interface(obj, 'org.freedesktop.DBus.Properties')

    def __getattr__(self, name):
        return self._properties.Get(self._iface, name)

def load_object(bus, path, iface):
    proxy = bus.get_object('org.bluez', path)
    return Proxy(dbus.Interface(proxy, iface), iface)

def get_device(bus, mac):
    path = '/org/bluez/hci0/dev_{}'.format(mac.replace(':', '_'))
    device = load_object(bus, path, 'org.bluez.Device1')
    return device

def find_sensor(bus, device, uuid):
    om = load_object(bus, '/', 'org.freedesktop.DBus.ObjectManager')
    managed = om._obj.GetManagedObjects()
    objects = (
        load_object(bus, path, IFACE) for path, data in managed.items()
        if IFACE in data and data[IFACE]['UUID'] == uuid
    )
    obj = next(objects, None)
    return obj


# vim: sw=4:et:ai
