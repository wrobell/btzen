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

"""
Bluetooth Weight service implementation.
"""

import enum
import struct
import typing as tp
from dataclasses import dataclass

from .device import InfoCharacteristic, DeviceCharacteristic, to_uuid

class WeightFlags(enum.IntFlag):
    IMPERIAL = 0x01
    TIMESTAMP = 0x02
    USER_ID = 0x04
    BMI = 0x08
    RESERVED_1 = 0x10
    RESERVED_2 = 0x20
    RESERVED_3 = 0x40
    RESERVED_4 = 0x80

@dataclass(frozen=True)
class WeightData:
    """
    Weight measurement.

    var flags: Weight scale flags value.
    var weight: Weight measurement value.

    Mi Smart Scale extensions:

    :var stabilized: Indicates if weight stabilized.
    :var load_removed: Indicates if load is removed.
    """
    flags: WeightFlags
    weight: float

    stabilized: tp.Optional[bool] = True
    load_removed: tp.Optional[bool] = False

class WeightMeasurement(DeviceCharacteristic):
    """
    Weight measurement Bluetooth device.
    """
    info = InfoCharacteristic(to_uuid(0x181d), to_uuid(0x2a9d), 9)

    def get_value(self, data: bytes):
        flags, weight = struct.unpack('<BH', data[0:3])
        flags = WeightFlags(flags)

        # TODO: set only when mi smart scale
        stabilized = bool(flags & WeightFlags.RESERVED_2)
        load_removed = bool(flags & WeightFlags.RESERVED_4)

        return WeightData(
            flags,
            weight * 0.005,
            stabilized=stabilized,
            load_removed=load_removed
        )

# vim: sw=4:et:ai
