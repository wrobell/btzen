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

import enum
import typing as tp
import dataclasses as dtc

class AddressType(enum.Enum):
    """
    Bluetooth device address type.


    .. seealso::

        `ConnectDevice` method documentation at
        https://git.kernel.org/pub/scm/bluetooth/bluez.git/tree/doc/adapter-api.txt.
    """
    PUBLIC = 'public'
    RANDOM = 'random'


@dtc.dataclass(frozen=True)
class Device:
    """
    Bluetooth device descriptor.

    :var service: UUID of Bluetooth service.
    """
    service: str

@dtc.dataclass(frozen=True)
class DeviceRegistration:
    """
    Bluetooth device connection information.

    Associates Bluetooth device MAC address and address type with a device.

    :var device: Bluetooth device descriptor.
    :var mac: MAC address of Bluetooth device.
    :var address_type: Bluetooth device address type.
    """
    device: Device
    mac: str
    address_type: AddressType=AddressType.PUBLIC

def register_device(device: Device, mac: str) -> DeviceRegistration:
    return DeviceRegistration(device, mac)

# vim: sw=4:et:ai
