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

import pkg_resources

# register devices
from . import serial as mod_serial
from . import sensortag
from . import thingy52

from .btweight import WeightFlags, WeightData, MiScaleWeightData
from .ndevice import Make, Service, DeviceBase, Device, DeviceTrigger, \
    pressure, temperature, humidity, light, light_rgba, create_device, \
    accelerometer, button, serial, weight
from .fdevice import read, write, enable, disable, set_interval, set_trigger
from .cm import connect, is_active
from .error import *
from .sensortag import SensorTagButtonState

__version__ = pkg_resources.get_distribution('btzen').version

__all__ = [
    # bluetooth service descriptors
    'Service',

    'Make', 'is_active', 'read', 'write', 'set_interval', 'set_trigger',

    # bluetooth device classes and functions
    'DeviceBase', 'Device', 'DeviceTrigger', 'create_device', 'pressure',
    'temperature', 'humidity', 'light', 'light_rgba', 'accelerometer',
    'button', 'serial', 'weight',

    # make specific objects
    'SensorTagButtonState',
]

# vim: sw=4:et:ai
