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
Nordic Thingy:52 Bluetooth device sensors

    https://nordicsemiconductor.github.io/Nordic-Thingy52-FW/documentation/firmware_architecture.html

The sensors do not implement the Bluetooth Environmental Sensing interfaces
and require custom classes. All Thingy:52 Bluetooth device sensors are
notifying.
"""

import asyncio
import logging
import struct
import typing as tp
from dataclasses import dataclass, replace

from . import _btzen
from .device import InfoCharacteristic, InfoEnvSensing, DeviceEnvSensing, \
    DeviceCharacteristic, Trigger, TriggerCondition
from .util import to_int

logger = logging.getLogger(__name__)

CONFIG_DATA_FMT = struct.Struct('<HHHHBBBB')

# function to convert 16-bit UUID to full 128-bit Thingy:52 UUID
to_uuid = 'ef68{:04x}-9b35-4933-9b10-52ffa9740042'.format

@dataclass
class Config:
    """
    Thingy:52 Bluetooth device configuration for the weather service
    sensors.
    """
    # temperature sensor data read interval
    temperature: float = 1.0
    # pressure sensor data read interval
    pressure: float = 1.0
    # humidity sensor data read interval
    humidity: float = 1.0
    # color sensor data read interval
    color: float = 1.0
    # gas sensor data read interval (1 - 1s, 2 - 10s, 3 - 60s)
    gas: int = 1
    # color sensor LED calibration (RGB value)
    rgb: tp.Tuple[int, int, int] = (0, 255, 0)

class DeviceThingy52EnvSensing(DeviceEnvSensing):
    """
    Thingy:52 Bluetooth device sensor.
    """
    ADDRESS_TYPE = 'random'

    # NOTE: the configuration is shared by all sensors per given device
    # (mac address)
    CONFIG = {}

    def __init__(self, mac, notifying=True):
        super().__init__(mac, notifying=notifying)

        DeviceThingy52EnvSensing.CONFIG[mac] = Config()
        self.set_trigger(Trigger(TriggerCondition.FIXED_TIME, 1))

    def _trigger_data(self, trigger: Trigger) -> bytes:
        assert trigger.condition == TriggerCondition.FIXED_TIME

        # replace configuration for given thingy52 device
        mac = self.mac
        data = {self.config_attr: trigger.operand}
        config = replace(DeviceThingy52EnvSensing.CONFIG[self.mac], **data)
        DeviceThingy52EnvSensing.CONFIG[mac] = config
        logger.info('thingy52 configuration: {}'.format(config))

        to_ms = lambda v: int(v * 1000)
        data = CONFIG_DATA_FMT.pack(
            to_ms(config.temperature),
            to_ms(config.pressure),
            to_ms(config.humidity),
            to_ms(config.color),
            config.gas,
            *config.rgb,
        )
        return data

class Temperature(DeviceThingy52EnvSensing):
    """
    Thingy:52 Bluetooth device temperature sensor.
    """
    info = InfoEnvSensing(
        to_uuid(0x0200),
        to_uuid(0x0201),
        2,
        uuid_trigger=to_uuid(0x0206),
    )
    config_attr = 'temperature'

    def get_value(self, data):
        return data[0] + data[1] / 100

class Pressure(DeviceThingy52EnvSensing):
    """
    Thingy:52 Bluetooth device pressure sensor.
    """
    info = InfoEnvSensing(
        to_uuid(0x0200),
        to_uuid(0x0202),
        5,
        uuid_trigger=to_uuid(0x0206),
    )
    config_attr = 'pressure'

    def get_value(self, data):
        return to_int(data[:4]) * 100 + data[4]

class Humidity(DeviceThingy52EnvSensing):
    """
    Thingy:52 Bluetooth device humidity sensor.
    """
    info = InfoEnvSensing(
        to_uuid(0x0200),
        to_uuid(0x0203),
        1,
        uuid_trigger=to_uuid(0x0206),
    )
    config_attr = 'humidity'

    def get_value(self, data):
        return data[0]

class DeviceThingy52Configuration(DeviceCharacteristic):
    """
    Thingy:52 Bluetooth device configuration.
    """
    ADDRESS_TYPE = 'random'

class ConnectionParameters(DeviceThingy52Configuration):
    info = InfoCharacteristic(
        to_uuid(0x0100),
        to_uuid(0x0104),
        8,
    )
    async def set_params(
        self,
        min_conn_interval,
        max_conn_interval,
        slave_latency,
        supervision_timeout,
    ):
        system_bus = self._bus.system_bus
        data = struct.pack(
            '<HHHH',
            min_conn_interval,
            max_conn_interval,
            slave_latency,
            supervision_timeout,
        )
        await _btzen.bt_write(system_bus, self._path_data, data)

# vim: sw=4:et:ai
