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
Bluetooth device descriptors, device object constructors and
modification functions.


                                   +--------------+
                                   | <<abstract>> |
                         +-------|>|  DeviceBase  |<|-------+
                         |         +--------------+         |
                         |                                  |
                         |                                  |
                     +---+----+   set_trigger() >    +---------------+
                     | Device |--------------------->| DeviceTrigger |
                     +--------+                      +---------------+

The following functions create Bluetooth device objects

- `accelerometer`
- `battery_level`
- `button`
- `humidity`
- `light`
- `light_rgb`
- `pressure`
- `serial`
- `temperature`
- `weight`

Depending on context a non-triggered or a triggered device is created. This
depends on a device itself and its make. If possible, non-triggered device
is created by default. Use `set_trigger` function to create tirggered
device.

It is not possible to create a non-triggered device from a triggered one.
"""

from __future__ import annotations

import dataclasses as dtc
import logging
import typing as tp
from functools import partial, singledispatch

from .data import T, AddressType, Converter, Make, NoTrigger, Trigger, \
    TriggerCondition, ServiceType, LightColor, Button, WeightData
from .service import S, Service, _SERVICE_REGISTRY

logger = logging.getLogger(__name__)

D = tp.TypeVar('D')

MakeNonTrigger = tp.Literal[Make.STANDARD, Make.SENSOR_TAG, Make.OSTC]

# key is tuple (base class, parameter class)
_PROXY_REGISTRY: dict[tuple[type, type], type] = {}

#
# define protocols for the constructors of devices objects
#
class Ctor(tp.Protocol[T]):
    """
    Constructor protocol for a device.

    By default it creates non-triggered device object. Exceptions are
    defined for devices, which work only with a trigger set.

    For example, by default a pressure device works without a trigger. But
    certain makes of pressure devices, i.e. Thingy:52, works only with
    a trigger set.
    """
    @tp.overload
    def __call__(
        self, mac: str, *, make: MakeNonTrigger=Make.STANDARD
    ) -> Device[Service, T]: ...

    @tp.overload
    def __call__(
        self, mac: str, *, make: tp.Literal[Make.THINGY52]
    ) -> DeviceTrigger[Service, T]: ...

    def __call__(
        self,
        mac: str,
        *,
        make: tp.Literal[Make.THINGY52] | MakeNonTrigger=Make.STANDARD
    ) -> Device[Service, T] | DeviceTrigger[Service, T]: ...

class CtorTrigger(tp.Protocol[T]):
    """
    Constructor for devices, which work only with triggers set.

    For example, any accelerometer device works with trigger set only.
    """
    def __call__(self, mac: str, make: Make=Make.STANDARD) -> DeviceTrigger[Service, T]: ...

#
# device objects
#
@dtc.dataclass(frozen=True)
class DeviceBase(tp.Generic[S, T]):
    """
    Abstract Bluetooth device descriptor.

    Implemenation notes

        BTZen handles complexity and diversity of non-compliant Bluetooth
        devices by using product of device and service types (`+` denotes
        that service class is upper bound for all other service classes)::

            (Device | DeviceTrigger, Service+)

        In Python, construction of product types can be achieved with
        `__new__` and `__class_getitem__` methods, for example::

            assert isinstance(Device(Service(...), ...), Device[Service])
            assert isinstance(Device(ServiceCharacteristic(...), ...), Device[ServiceCharacteristic])
            assert isinstance(DeviceTrigger(ServiceCharacteristic(...), ...), DeviceTrigger[ServiceCharacteristic])

        For BTZen purposes, instances of such types have to be dispatched
        with Python single-dispatch generic functions. The functions
        implement behaviour for the Bluetooth devices, i.e.::

            @read.register
            async def _read_sensor_tag(device: Device[SensorTagService, T]):
                ...

        where `SensorTagService` is an example of service class, which
        describes Texas Instrument Sensor Tag Bluetooth device sensors.

        The `__class_getitem__` method creates proxy classes for the device
        and service product types plus Python generic psuedo-types. This
        allows to use them with single-dispatch generic functions in
        Python.

        The `__new__` method creates instance using the proxy class.

        Why "pseudo-type"? The types defined in Python typing module (as of
        Python 3.9) are not real Python types, for example all statements
        below return false or raise error::

            issubclass(Generic, type)  # False
            issubclass(Generic[TypeVar('T')], type)  # type error "arg1 must be a class"

        As such, the pseudo-types cannot be used by single-dispatch generic
        functions in Python at the moment. See also

            https://bugs.python.org/issue34498

        Single-dispatch generic functions, which implement behaviour for
        the product types, can be listed with script
        `scripts/btzen-service-impl`.

    :var service: Bluetooth service descriptor.
    :var mac: MAC address of Bluetooth device.
    :var address_type: Bluetooth device address type.
    :var convert: Function to convert binary data provided by service
        to a value.
    """
    service: S
    mac: str
    address_type: AddressType
    convert: Converter[T]

    def __new__(cls, *args, **kw):  # type: ignore
        tv = type(args[0])
        return cls[tv, T](*args, **kw)  # type: ignore

    def __class_getitem__(cls, cls_param: tuple[type[S], tp.TypeVar]) -> type[Device[S, T]]:
        ok = (
            isinstance(cls_param, tuple)
            and len(cls_param) == 2
            and (dtc.is_dataclass(cls_param[0]) or cls_param[0] == S) # type: ignore
            and (
                isinstance(cls_param[1], (tp.TypeVar, type))
                or cls_param[1] is tp.Any
            )
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
            fields = cls.__dataclass_fields__ 
            t = dtc.make_dataclass(t.__name__, fields, bases=bases, frozen=True)
            t.__product__ = (cls, cls_pt)  # type: ignore
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
    Bluetooth device descriptor with trigger.

    :var trigger: Trigger information.
    """
    trigger: Trigger

def create_device(
        service: Service,
        mac: str,
        *,
        address_type: AddressType=AddressType.PUBLIC,
        convert: Converter[T]=tp.cast(Converter[tp.Any], lambda v: v),
    ) -> Device[Service, T]:
    """
    Create Bluetooth device for a Bluetooth service.
    """
    return Device(service, mac, address_type=address_type, convert=convert)

def set_interval(
        device: DeviceBase[S, T],
        interval: float,
    ) -> DeviceTrigger[S, T]:
    """
    Set fixed time interval for Bluetooth Environmental Sensing device.

    This is equivalent to::

        set_trigger(TriggerCondition.FIXED_TIME, interval)

    :param device: Bluetooth device descriptor.
    :param interval: Interval in seconds.
    """
    return set_trigger(device, TriggerCondition.FIXED_TIME, operand=interval)

@singledispatch
def set_trigger(
        device: DeviceBase[S, T],
        condition: TriggerCondition,
        *,
        operand: tp.Optional[float]=None,
        ) -> DeviceTrigger[S, T]:
    """
    Set trigger for Bluetooth Environmental Sensing device.
    """
    return DeviceTrigger(
        device.service,
        device.mac,
        device.address_type,
        device.convert,
        Trigger(condition, operand),
    )

def set_address_type(device: D, address_type: AddressType) -> D:
    """
    Set connection address type for a Bluetooth device.

    :param device: Bluetooth device descriptor.
    :param address_type: Bluetooth device connection address type.
    """
    return dtc.replace(device, address_type=address_type)

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
        return set_trigger(dev, trigger.condition, operand=trigger.operand)

accelerometer = tp.cast(
    CtorTrigger[tuple[float, float, float]],
    partial(_create_device, ServiceType.ACCELEROMETER),
)

battery_level = tp.cast(CtorTrigger[int], partial(_create_device, ServiceType.BATTERY_LEVEL))
battery_level.__doc__ = """
The current charge level of a Bluetooth device battery.

:param mac: MAC address of Bluetooth device.
:param make: Bluetooth device make.

.. seealso:: `Make`
"""

button = tp.cast(CtorTrigger[Button], partial(_create_device, ServiceType.BUTTON))
humidity = tp.cast(Ctor[float], partial(_create_device, ServiceType.HUMIDITY))
light = tp.cast(Ctor[float], partial(_create_device, ServiceType.LIGHT))
light_rgb = tp.cast(Ctor[LightColor], partial(_create_device, ServiceType.LIGHT_RGB))
pressure = tp.cast(Ctor[float], partial(_create_device, ServiceType.PRESSURE))
serial = tp.cast(Ctor[bytes], partial(_create_device, ServiceType.SERIAL))
temperature = tp.cast(Ctor[float], partial(_create_device, ServiceType.TEMPERATURE))
weight = tp.cast(CtorTrigger[WeightData], partial(_create_device, ServiceType.WEIGHT_MEASUREMENT))

# vim: sw=4:et:ai
