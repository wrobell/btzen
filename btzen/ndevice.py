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

import enum
import logging
import typing as tp
import dataclasses as dtc
from collections import defaultdict
from functools import partial

from .service import S, Service

logger = logging.getLogger(__name__)

T = tp.TypeVar('T')
Converter = tp.Callable[[bytes], T]
AnyTrigger = tp.Union['Trigger', 'NoTrigger']

# registry of known services
_SERVICE_REGISTRY = defaultdict[
    'Make',
    dict['ServiceType', tuple['Service', Converter, AnyTrigger, 'AddressType']]
](dict)

# key is tuple (base class, parameter class)
_PROXY_REGISTRY: dict[tuple[type, type], type] = {}

# function to convert 16-bit UUID to full 128-bit Bluetooth normative UUID
# string
to_uuid: tp.Callable[[int], str] = '0000{:04x}-0000-1000-8000-00805f9b34fb'.format

class Make(enum.Enum):
    """
    Bluetooth device make.
    """
    STANDARD = enum.auto()
    SENSOR_TAG = enum.auto()
    THINGY52 = enum.auto()
    OSTC = enum.auto()
    MI_SMART_SCALE = enum.auto()

class ServiceType(enum.Enum):
    """
    Bluetooth service type.
    """
    ACCELEROMETER = enum.auto()
    BUTTON = enum.auto()
    HUMIDITY = enum.auto()
    LIGHT = enum.auto()
    LIGHT_RGBA = enum.auto()
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
class NoTrigger: pass

@dtc.dataclass(frozen=True)
class DeviceBase(tp.Generic[S, T]):
    """
    Abstract Bluetooth device descriptor.

    Implemenation notes

        Add support for single-dispatch generic functions and generic
        pseudo-type provided by Python `typing` module.

        BTZen handles complexity and diversity of non-compliant Bluetooth
        devices by using parametrised types - generic pseudo-types in
        Python. The behaviour for Bluetooth devices is implemented in
        functions, which are overloaded by the combination of device class
        and service class, i.e.:

            @enable.register
            async def _enable_sensor_tag(device: Device[SensorTagService, T]):
                ...

        The `__class_getitem__` method creates proxy classes for generic
        psuedo-types, which allows to use them with single-dispatch generic
        functions in Python. 

        The `__new__` method creates instance using the proxy class.

        Why "pseudo-type"? The types defined in Python typing module (as of
        Python 3.9) are not real Python types, for example all statements
        below return false or raise error::

            issubclass(Generic, type)  # False
            issubclass(Generic[TypeVar('T')], type)  # type error "arg1 must be a class"

        As such, the pseudo-types cannot be used by single-dispatch generic
        functions in Python at the moment. See also

            https://bugs.python.org/issue34498


    :var service: Bluetooth service descriptor.
    :var mac: MAC address of Bluetooth device.
    :var address_type: Bluetooth device address type.
    :var convert: Function to convert binary data provided by service
        to a value.
    """
    service: S
    mac: str
    address_type: AddressType
    convert: Converter

    def __new__(cls, *args, **kw):
        tv = type(args[0])
        return cls[tv, T](*args, **kw)

    def __class_getitem__(cls, cls_param: tuple[type[S], tp.TypeVar]) -> type[Device[S, T]]:
        ok = (
            isinstance(cls_param, tuple)
            and len(cls_param) == 2
            and (dtc.is_dataclass(cls_param[0]) or cls_param[0] == S) # type: ignore
            and isinstance(cls_param[1], tp.TypeVar)  # type: ignore
        )

        if not ok:
            raise TypeError(
                'Class subscript requires dataclass and type variable. Got {}'
                .format(cls_param)
            )

        cls_pt = cls_param[0]
        is_s = cls_pt == S  # type: ignore

        # this allows use of subclasses
        if is_s:
            return cls  # type: ignore

        key = cls, cls_pt
        t = _PROXY_REGISTRY.get(key)
        if t is None:
            # find base class of new dataclass, so subclassing works
            get_parent = cls.__class_getitem__
            mro = [] if is_s else cls_pt.mro()[1:]
            items = (c for c in mro if issubclass(c, S.__bound__))  # type: ignore
            base = next(items, None)
            bases = (get_parent((base, cls_param[1])), object,) if base else (object,)

            # create new dataclass based on main class `cls` and the
            # parameter class `cls_pt`
            t = type('{}[{}]'.format(cls.__name__, cls_pt.__name__), bases, {})
            fields = cls.__dataclass_fields__  # type: ignore
            t = dtc.make_dataclass(t.__name__, fields, bases=bases, frozen=True)
            _PROXY_REGISTRY[key] = t
        return t

@dtc.dataclass(frozen=True)
class Device(DeviceBase[S, T]):
    """
    Bluetooth device descriptor.
    """

@dtc.dataclass(frozen=True)
class DeviceTrigger(DeviceBase[S, T]):
    """
    Bluetooth device descriptor with tirgger.

    :var trigger: Trigger information.
    """
    trigger: Trigger

def register_service(
        make: Make,
        service_type: ServiceType,
        service: Service,
        *,
        convert: Converter[T]=tp.cast(Converter, lambda v: v),
        trigger: AnyTrigger=NoTrigger(),
        address_type=AddressType.PUBLIC,
    ):
    """
    Register service with data conversion function.
    """
    _SERVICE_REGISTRY[make][service_type] = (
        service, convert, trigger, address_type
    )

def create_device(
        service: Service,
        mac: str,
        *,
        address_type: AddressType=AddressType.PUBLIC,
        convert: Converter[T]=tp.cast(Converter, lambda v: v),
    ) -> Device[Service, T]:
    """
    Create Bluetooth device for a Bluetooth service.
    """
    return Device(service, mac, address_type=address_type, convert=convert)

def _create_device(
        service_type: ServiceType,
        mac: str,
        *,
        make: Make=Make.STANDARD,
    ) -> DeviceBase[Service, tp.Any]:

    srv, conv, trigger, addr_type = _SERVICE_REGISTRY[make][service_type]
    dev = create_device(srv, mac, address_type=addr_type, convert=conv)

    if isinstance(trigger, NoTrigger):
        return dev
    else:
        from .fdevice import set_trigger
        return set_trigger(dev, trigger.condition, operand=trigger.operand)

pressure = partial(_create_device, ServiceType.PRESSURE)
temperature = partial(_create_device, ServiceType.TEMPERATURE)
humidity = partial(_create_device, ServiceType.HUMIDITY)
light = partial(_create_device, ServiceType.LIGHT)
light_rgba = partial(_create_device, ServiceType.LIGHT_RGBA)
accelerometer = partial(_create_device, ServiceType.ACCELEROMETER)
button = partial(_create_device, ServiceType.BUTTON)
serial = partial(_create_device, ServiceType.SERIAL)
weight = partial(_create_device, ServiceType.WEIGHT_MEASUREMENT)

# vim: sw=4:et:ai
