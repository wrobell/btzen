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
Nordic Thingy:52 Bluetooth device sensors

    https://nordicsemiconductor.github.io/Nordic-Thingy52-FW/documentation/firmware_architecture.html

The sensors do not implement the Bluetooth Environmental Sensing interfaces
and require custom classes. All Thingy:52 Bluetooth device sensors are
notifying.
"""

import dataclasses as dtc
import logging
import struct
import typing as tp
from collections import defaultdict
from functools import partial, cache

from .data import T, AddressType, Button, LightColor, Make, ServiceType, \
    Trigger, TriggerCondition
from .device import DeviceTrigger, set_trigger
from .devio import enable, _enable_dev_trigger, write_config
from .service import register_service, ServiceCharacteristic
from .util import to_int

logger = logging.getLogger(__name__)

CONFIG_DATA_FMT = struct.Struct('<HHHHBBBB')
SENSOR_COLOR_FMT = struct.Struct('<HHHH')
LIGHT_MAX = 0xffff

# function to convert 16-bit UUID to full 128-bit Thingy:52 UUID
to_uuid = 'ef68{:04x}-9b35-4933-9b10-52ffa9740042'.format

register_th = partial(
    register_service,
    Make.THINGY52,
    address_type=AddressType.RANDOM,
    trigger=Trigger(TriggerCondition.FIXED_TIME, 1),
)

@dtc.dataclass(frozen=True)
class Thingy52Service(ServiceCharacteristic):
    uuid_conf: str
    config_entry: str

@dtc.dataclass
class Thingy52Config:
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
    rgb: tuple[int, int, int] = (0, 255, 0)

_CONFIG_CACHE: defaultdict[str, Thingy52Config] = defaultdict(Thingy52Config)

class Thingy52ButtonState(Button):
    """
    Thingy:52 Bluetooth device button state.
    """
    OFF = 0x00
    ON = 0x01

def convert_light(data: bytes) -> LightColor:
    """
    Convert data of BH1745 light sensor in Thingy:52 to light color object.
    """
    values = SENSOR_COLOR_FMT.unpack(data)
    return LightColor(*(v / LIGHT_MAX for v in values))

register_th(
    ServiceType.PRESSURE,
    Thingy52Service(
        to_uuid(0x0200),
        to_uuid(0x0202),
        5,
        to_uuid(0x0206),
        'pressure',
    ),
    convert=lambda data: to_int(data[:4]) * 100 + data[4],
)

register_th(
    ServiceType.TEMPERATURE,
    Thingy52Service(
        to_uuid(0x0200),
        to_uuid(0x0201),
        2,
        to_uuid(0x0206),
        'temperature',
    ),
    convert=lambda data: data[0] + data[1] / 100
)

register_th(
    ServiceType.HUMIDITY,
    Thingy52Service(
        to_uuid(0x0200),
        to_uuid(0x0203),
        1,
        to_uuid(0x0206),
        'humidity',
    ),
    convert=lambda data: data[0],
)

register_th(
    ServiceType.LIGHT_RGB,
    Thingy52Service(
        to_uuid(0x0200),
        to_uuid(0x0205),
        8,
        to_uuid(0x0206),
        'color',
    ),
    convert=convert_light,
)

register_th(
    ServiceType.BUTTON,
    ServiceCharacteristic(
        to_uuid(0x0300),
        to_uuid(0x0302),
        1,
    ),
    convert=lambda data: Thingy52ButtonState(data[0]),
)

@enable.register  # type: ignore
async def _enable_thingy52(device: DeviceTrigger[Thingy52Service, T]) -> None:
    to_ms: tp.Callable[[float], int] = lambda v: int(v * 1000)
    mac = device.mac
    srv = device.service

    config = _CONFIG_CACHE[mac]
    data = CONFIG_DATA_FMT.pack(
        to_ms(config.temperature),
        to_ms(config.pressure),
        to_ms(config.humidity),
        to_ms(config.color),
        config.gas,
        *config.rgb,
    )
    await write_config(mac, srv.uuid_conf, data)
    await _enable_dev_trigger(device)

@set_trigger.register  # type: ignore
def _set_trigger_thingy52(  # type: ignore
        device: DeviceTrigger[Thingy52Service, T],
        condition: TriggerCondition,
        *,
        operand: tp.Optional[float]=None,
    ) -> DeviceTrigger[Thingy52Service, T]:

    assert operand is not None

    mac = device.mac
    config_entry = device.service.config_entry
    config = _CONFIG_CACHE[device.mac]
    config = dtc.replace(config, **{config_entry: operand})
    _CONFIG_CACHE[mac] = config

    return device

# class DeviceThingy52Configuration(DeviceCharacteristic):
#     """
#     Thingy:52 Bluetooth device configuration.
#     """
#     ADDRESS_TYPE = 'random'
# 
# class ConnectionParameters(DeviceThingy52Configuration):
#     info = InfoCharacteristic(
#         to_uuid(0x0100),
#         to_uuid(0x0104),
#         8,
#     )
#     async def set_params(
#         self,
#         min_conn_interval,
#         max_conn_interval,
#         slave_latency,
#         supervision_timeout,
#     ):
#         system_bus = self._bus.system_bus
#         data = struct.pack(
#             '<HHHH',
#             min_conn_interval,
#             max_conn_interval,
#             slave_latency,
#             supervision_timeout,
#         )
#         path = self._get_path(self.info.uuid_data)
#         await _btzen.bt_write(system_bus, path, data)

# vim: sw=4:et:ai
