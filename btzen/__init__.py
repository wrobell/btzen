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

import pkg_resources

# register devices
from . import serial as mod_serial
from . import sensortag
from . import thingy52
from . import bluez

from .btweight import MiScaleWeightData
from .data import AddressType, Button, Make, LightColor, TriggerCondition, \
    Trigger, ServiceType, WeightFlags, WeightData
from .device import DeviceBase, Device, DeviceTrigger, set_interval, \
    set_trigger, set_address_type, create_device, \
    accelerometer, battery_level, button, humidity, light, \
    light_rgb, pressure, serial, temperature, weight
from .devio import read, read_all, write, enable, disable
from .serial import SerialService
from .service import Service, ServiceCharacteristic, ServiceInterface
from .cm import connect
from .error import *
from .session import is_active
from .sensortag import SensorTagButtonState
from .thingy52 import Thingy52ButtonState

__version__ = pkg_resources.get_distribution('btzen').version

__all__ = [
    # connection session
    'is_active', 'connect',

    # bluetooth device descriptors and constructors
    'DeviceBase', 'Device', 'DeviceTrigger', 'create_device',
    'accelerometer', 'battery_level', 'button', 'humidity', 'light',
    'light_rgb', 'pressure', 'serial', 'temperature', 'weight',

    # bluetooth service descriptors
    'Service', 'ServiceCharacteristic', 'ServiceInterface', 'SerialService',

    # basic data
    'AddressType', 'Make', 'ServiceType', 'Button', 'LightColor', 'WeightData',
    'WeightFlags', 'Trigger', 'TriggerCondition',

    # bluetooth device i/o
    'read', 'read_all', 'write',

    # bluetooth device configuration
    'set_interval', 'set_trigger', 'set_address_type',

    # make specific objects
    'SensorTagButtonState', 'Thingy52ButtonState', 'MiScaleWeightData',
]

# vim: sw=4:et:ai
