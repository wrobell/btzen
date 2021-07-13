#
# BTZen - library to asynchronously access Bluetooth devices.
#
# Copyright (C) 2015-2021 by Artur Wroblewski <wrobell@riseup.net>
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

import typing as tp
from dataclasses import dataclass

AddressType = tp.Literal['public', 'random']

@dataclass(frozen=True)
class Device:
    """
    Bluetooth device information.

    :var service: UUID of Bluetooth service.
    :var address_type: Bluetooth device address type.
    """
    service: str
    address_type: AddressType='public'

def register_device(mac: str, device: Device):
    from .cm import CM_REGISTER
    queue = CM_REGISTER.get()
    queue.put_nowait((mac, device))

# vim: sw=4:et:ai
