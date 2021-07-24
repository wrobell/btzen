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

import dataclasses as dtc
import typing as tp
from functools import singledispatch

from btzen.dispatch import ParametrisedType, _REGISTRY

def test_new_class():
    """
    Test creation of instance of parametrised type.
    """
    T = tp.TypeVar('T')

    @dtc.dataclass(frozen=True)
    class TC(tp.Generic[T], metaclass=ParametrisedType):
        x: T


    t = TC(1)
    assert isinstance(t, TC)
    assert t.__class__ == _REGISTRY[TC, int]

def test_dispatch():
    """
    Test dispatching for instance of parametrised type. 
    """
    T = tp.TypeVar('T')

    @dtc.dataclass(frozen=True)
    class TC(tp.Generic[T], metaclass=ParametrisedType):
        x: T

    @singledispatch
    def f(t: TC) -> str:
        return '0'

    @f.register
    def _f_int(t: TC[int]) -> str:
        return 'int'

    @f.register
    def _f_str(t: TC[str]) -> str:
        return 'str'

    assert f(TC(object())) == '0'
    assert f(TC('a')) == 'str'
    assert f(TC(1)) == 'int'

def test_dispatch_subclass():
    """
    Test dispatching for instance of subclass of parametrised type. 
    """
    T = tp.TypeVar('T')

    @dtc.dataclass(frozen=True)
    class TSuperclass(tp.Generic[T], metaclass=ParametrisedType):
        x: T

    @dtc.dataclass(frozen=True)
    class TSubclass(TSuperclass):
        pass

    V = tp.TypeVar('V', bound=TSuperclass, covariant=True)

    @dtc.dataclass(frozen=True)
    class TC(tp.Generic[V], metaclass=ParametrisedType):
        x: V

    @singledispatch
    def f(t: TC[TSuperclass[int]]) -> str:
        return 'super'

    @f.register
    def _f_sub(t: TC[TSubclass[int]]) -> str:
        return 'sub'

    assert f(TC(TSuperclass(1))) == 'super'
    assert f(TC(TSubclass(1))) == 'sub'

# vim: sw=4:et:ai
