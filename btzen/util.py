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

"""
BTZen utility functions.
"""

import typing as tp
from functools import partial
from itertools import chain

concat = chain.from_iterable
to_int = partial(int.from_bytes, byteorder='little')

# function to convert 16-bit UUID to full 128-bit Bluetooth normative UUID
# string
to_uuid: tp.Callable[[int], str] = '0000{:04x}-0000-1000-8000-00805f9b34fb'.format

# vim: sw=4:et:ai
