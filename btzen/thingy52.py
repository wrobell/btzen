#
# BTZen - library to asynchronously access Bluetooth devices.
#
# Copyright (C) 2015-2019 by Artur Wroblewski <wrobell@riseup.net>
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
Nordic Thingy:52 Bluetooth device sensors

    https://nordicsemiconductor.github.io/Nordic-Thingy52-FW/documentation/firmware_architecture.html

The sensors do not implement the Bluetooth Environmental Sensing interfaces
and require custom classes. All Thingy:52 Bluetooth device sensors are
notifying.
"""

import asyncio
import logging

from .device import InfoEnvSensing, DeviceEnvSensing, \
    DeviceCharacteristic, Trigger, TriggerCondition
from .util import to_int

logger = logging.getLogger(__name__)

# function to convert 16-bit UUID to full 128-bit Thingy:52 UUID
to_uuid = 'ef68{:04x}-9b35-4933-9b10-52ffa9740042'.format

class DeviceThingy52(DeviceEnvSensing):
    """
    Thingy:52 Bluetooth device sensor.
    """
    def __init__(self, mac, notifying=True):
        super().__init__(mac, notifying=notifying)

        self.set_trigger(Trigger(TriggerCondition.FIXED_TIME, 1))

    def _trigger_data(self, trigger: Trigger) -> bytes:
        assert trigger.condition == TriggerCondition.FIXED_TIME
        return bytes()

class Temperature(DeviceThingy52):
    """
    Thingy:52 Bluetooth device temperature sensor.
    """
    info = InfoEnvSensing(
        to_uuid(0x0200),
        to_uuid(0x0201),
        2
    )

    def get_value(self, data):
        return data[0] + data[1] / 100

class Pressure(DeviceThingy52):
    """
    Thingy:52 Bluetooth device pressure sensor.
    """
    info = InfoEnvSensing(
        to_uuid(0x0200),
        to_uuid(0x0202),
        5,
    )

    def get_value(self, data):
        return to_int(data[:4]) * 100 + data[4]

class Humidity(DeviceThingy52):
    """
    Thingy:52 Bluetooth device humidity sensor.
    """
    info = InfoEnvSensing(
        to_uuid(0x0200),
        to_uuid(0x0203),
        1,
    )

    def get_value(self, data):
        return data[0]

# vim: sw=4:et:ai
