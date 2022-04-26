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

USEC = 10 ** 6
DEFAULT_DBUS_TIMEOUT = 5 * USEC

# NOTE: connection timeout needs to be longer than default dbus timeout
# used by btzen to allow connection object creation
DEFAULT_CONNECTION_TIMEOUT = 30 * USEC

DEFAULT_CHARACTERISTIC_PATH_RETRY = 5

# vim: sw=4:et:ai
