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

from __future__ import annotations

import dataclasses as dtc
import typing as tp

@dtc.dataclass(frozen=True)
class Service:
    """
    Bluetooth service descriptor.

    :var uuid: UUID of Bluetooth service.
    """
    uuid: str

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


@dtc.dataclass(frozen=True)
class ServiceEnvSensing(ServiceCharacteristic):
    """
    Bluetooth service descriptor for Bluetooth Environmental Sensing
    characteristic.

    :var uuid_conf: UUID of characteristic to write and read device
        configuration.
    :var uuid_trigger: UUID of characteristic to write and read device
        trigger data.
    :var config_on: Default configuration of device to switch device on.
    :var config_off: Default configuration of device to switch device off.
    """
    uuid_conf: str
    uuid_trigger: str
    config_on: bytes
    config_off: bytes

S = tp.TypeVar('S', bound=Service, covariant=True)

# vim: sw=4:et:ai