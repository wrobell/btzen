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

from __future__ import annotations

import dataclasses as dtc
import typing as tp
from collections import defaultdict

from .data import T, AddressType, AnyTrigger, Converter, Make, NoTrigger, \
    ServiceType

# registry of known services
_SERVICE_REGISTRY = defaultdict[
    'Make',
    dict['ServiceType', tuple['Service', Converter[T], AnyTrigger, 'AddressType']]
](dict)

@dtc.dataclass(frozen=True)
class Service:
    """
    Bluetooth service descriptor.

    :var uuid: UUID of Bluetooth service.
    """
    uuid: str

@dtc.dataclass(frozen=True)
class ServiceInterface(Service):
    """
    Bluetooth device information for device providing data via Bluez
    interface property.

    Example of interface for Battery Level Bluetooth characteristic is
    `org.bluez.Battery1` Bluez interface, which provides data via
    `Percentage` property.

    :var interface: Bluez interface name.
    :var property: Property name of the interface.
    :var type: Type of property value.
    """
    interface: str
    property: str
    type: str

@dtc.dataclass(frozen=True)
class ServiceCharacteristic(Service):
    """
    Bluetooth service descriptor for Bluetooth characteristic.

    :var uuid_data: UUID of characteristic to read data from.
    :var size: Length of data received from Bluetooth characteristic on
        read.
    """
    uuid_data: str
    size: int

def register_service(
        make: Make,
        service_type: ServiceType,
        service: Service,
        *,
        convert: Converter[T]=tp.cast(Converter[tp.Any], lambda v: v),
        trigger: AnyTrigger=NoTrigger(),
        address_type: AddressType=AddressType.PUBLIC,
    ) -> None:
    """
    Register service with data conversion function.
    """
    _SERVICE_REGISTRY[make][service_type] = (
        service, convert, trigger, address_type
    )

S = tp.TypeVar('S', bound=Service, covariant=True)

# vim: sw=4:et:ai
