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
Basic enums, records and types.
"""

import dataclasses as dtc
import enum
import typing as tp

T = tp.TypeVar('T')
Converter = tp.Callable[[bytes], T]
AnyTrigger = tp.Union['Trigger', 'NoTrigger']

class Make(enum.Enum):
    """
    Bluetooth device make.
    """
    STANDARD = 'standard'
    SENSOR_TAG = 'sensor_tag'
    THINGY52 = 'thingy52'
    OSTC = 'ostc'
    MI_SMART_SCALE = 'mi_smart_scale'

class ServiceType(enum.Enum):
    """
    Bluetooth service type.
    """
    ACCELEROMETER = enum.auto()
    BUTTON = enum.auto()
    BATTERY_LEVEL = enum.auto()
    HUMIDITY = enum.auto()
    LIGHT = enum.auto()
    LIGHT_RGB = enum.auto()
    PRESSURE = enum.auto()
    SERIAL = enum.auto()
    TEMPERATURE = enum.auto()
    WEIGHT_MEASUREMENT = enum.auto()

class AddressType(enum.Enum):
    """
    Bluetooth device address type.


    .. seealso::

        `ConnectDevice` method documentation at
        https://git.kernel.org/pub/scm/bluetooth/bluez.git/tree/doc/adapter-api.txt.
    """
    PUBLIC = 'public'
    RANDOM = 'random'

class TriggerCondition(enum.IntEnum):
    """
    Condition value for Bluetooth Environmental Sensing device trigger
    information.

    Use `NoTrigger` for inactive trigger.

    NOTE: Incomplete, see Bluetooth Environmental Sensing Service
        specification, page 18.
    """
    FIXED_TIME = 0x01
    ON_CHANGE = 0x04

@dtc.dataclass(frozen=True)
class Trigger:
    """
    Bluetooth Environmental Sensing device trigger information.
    """
    condition: TriggerCondition
    operand: tp.Optional[tp.Any]=None

@dtc.dataclass
class NoTrigger:
    """
    Singleton object indicating no trigger for a Bluetooth device.
    """

class Button(enum.IntFlag):
    """
    Base enumeration class for state of buttons found on various Bluetooth
    devices.
    """

@dtc.dataclass(frozen=True)
class LightColor:
    """
    Light value with RGB colour information.
    """
    red: float
    blue: float
    green: float
    clear: float

class WeightFlags(enum.IntFlag):
    IMPERIAL = 0x01
    TIMESTAMP = 0x02
    USER_ID = 0x04
    BMI = 0x08
    RESERVED_1 = 0x10
    RESERVED_2 = 0x20
    RESERVED_3 = 0x40
    RESERVED_4 = 0x80

@dtc.dataclass(frozen=True)
class WeightData:
    """
    Weight measurement data.

    var flags: Weight scale flags value.
    var weight: Weight measurement value.
    """
    flags: WeightFlags
    weight: float

# vim: sw=4:et:ai
