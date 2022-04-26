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

import dataclasses as dtc
import typing as tp
from functools import singledispatch

from ..data import T, AddressType, Trigger, TriggerCondition
from ..device import DeviceBase, Device, DeviceTrigger
from ..service import S, Service, ServiceCharacteristic

import pytest

Tf = tp.TypeVar('Tf', bound=float)

@dtc.dataclass(frozen=True)
class ServiceEnvSensing(ServiceCharacteristic):
    pass

@singledispatch
def read(dev: DeviceBase[Service, Tf]) -> Tf:
    return 1.0  # type: ignore

@read.register
def _read_service(dev: Device[Service, Tf]) -> Tf:
    return dev.convert(b'11')

@read.register
def _read_service_chr(dev: Device[ServiceCharacteristic, Tf]) -> Tf:
    return dev.convert(b'22')

@read.register
def _read_service_chr_tr(dev: DeviceTrigger[ServiceCharacteristic, Tf]) -> Tf:
    return dev.convert(b'33')

def to_int(v: bytes) -> int:
    return int(v.decode())

INSTANCE_DATA = [
    [
        Device(Service('aaa'), '1', AddressType.PUBLIC, to_int),
        Device[Service, T],
        _read_service,
        11,
    ],
    [
        Device(ServiceCharacteristic('aaa', 'bbb', 4), '1', AddressType.PUBLIC, str),
        Device[ServiceCharacteristic, T],
        _read_service_chr,
        "b'22'",
    ],
    [
        DeviceTrigger(
            ServiceCharacteristic('aaa', 'bbb', 4),
            '1',
            AddressType.PUBLIC,
            str,
            Trigger(TriggerCondition.FIXED_TIME, 1),
        ),
        DeviceTrigger[ServiceCharacteristic, T],
        _read_service_chr_tr,
        "b'33'",
    ],
]

SUBCLASS_DATA = [
    [
        Device[Service, T],
        Device[ServiceCharacteristic, T],
    ],
    [
        Device[Service, T],
        Device[ServiceEnvSensing, T],
    ],
    [
        Device[ServiceCharacteristic, T],
        Device[ServiceEnvSensing, T],
    ],
]

NON_SUBCLASS_DATA = [
    [
        Device[ServiceCharacteristic, T],
        DeviceTrigger[ServiceCharacteristic, T],
    ],
    [
        Device[Service, T],
        DeviceTrigger[ServiceCharacteristic, T],
    ],
]

@pytest.mark.parametrize('obj, cls, func, func_result', INSTANCE_DATA)
def test_instance(obj, cls, func, func_result) -> None:  # type: ignore
    """
    Test instance of parametrised class.
    """
    assert isinstance(obj, cls)
    assert type(obj) == cls
    assert dtc.is_dataclass(obj)

@pytest.mark.parametrize('parent, cls', SUBCLASS_DATA)
def test_subclass(parent: type, cls: type) -> None:
    """
    Test inheritance of parametrised subclasses.
    """
    assert parent in cls.mro()
    assert issubclass(cls, parent)

@pytest.mark.parametrize('parent, cls', NON_SUBCLASS_DATA)
def test_not_subclass(parent: type, cls: type) -> None:
    """
    Test lack of inheritance of parametrised subclasses.
    """
    assert parent not in cls.mro()
    assert not issubclass(cls, parent)

@pytest.mark.parametrize('obj, cls, func, func_result', INSTANCE_DATA)
def test_dispatch(obj, cls, func, func_result) -> None:  # type: ignore
    """
    Test generic functions dispatch against instances of parametrised
    classes.
    """
    assert read.dispatch(type(obj)) == func
    assert read(obj) == func_result

def test_cls_create_self() -> None:
    """
    Test creating parametrised class when itself has to be returned.
    """
    t = Device[S, T]
    assert t == Device

@pytest.mark.parametrize('cls', (T, int, tp.Any))
def test_cls_create(cls: tp.Any) -> None:
    """
    Test creating parametrised class.
    """
    t = Device[Service, T]
    assert isinstance(t, type)

@pytest.mark.parametrize('cls_param', [(Service,), (Service, 'a value')])
def test_cls_param_invalid(cls_param: type) -> None:
    """
    Test if error is raised on an invalid parameters passed to a class.
    """
    with pytest.raises(TypeError) as ctx:
        Device[cls_param]   # type: ignore

    expected = 'Class subscript requires dataclass and type variable. Got {}' \
        .format(cls_param)
    assert str(ctx.value) == expected

# vim: sw=4:et:ai
