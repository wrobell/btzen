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

"""
Support for single-dispatch generic functions and generic pseudo-type
provided by Python `typing` module.

BTZen handles complexity and diversity of non-compliant Bluetooth devices,
by using parametrised types - generic pseudo-types in Python. The behaviour
is implemented in functions, which are overloaded by the combination of
parametrised types, i.e.:

    @enable.register
    async def _enable_sensor_tag(device: Device[SensorTagService]):
        ...

Metaclasses and functions implemented in this module create proxy classes
for generic psuedo-types, which allows to use them with single-dispatch
generic functions in Python. 

Why "pseudo-type"? The types defined in Python typing module (as of Python
3.9) are not real Python types, for example all statements below return
false or raise error::

    issubclass(Generic, type)  # False
    issubclass(Generic[TypeVar('T')], type)  # type error "arg1 must be a class"

As such, at the moment the pseudo-types cannot be used by single-dispatch
generic functions in Python. See also

    https://bugs.python.org/issue34498

"""

import logging
import typing as tp

logger = logging.getLogger(__name__)

RegistryEntry = tuple[type, type]
_REGISTRY: dict[RegistryEntry, type] = {}

class ParametrisedType(type):
    """
    Metaclass to create proxy class for a generic pseudo-type to support
    single-dispatch generic functions.
    """
    def __new__(cls, name, bases, dict_data):
        pt = super().__new__(cls, name, bases, dict_data)
        pt.__new__ = pt_new
        pt.__class_getitem__ = classmethod(pt_class_getitem)
        return pt

def pt_new(cls: type, cls_param: tp.Any) -> tp.Any:
    """
    Function to be bound as proxy class `__new__` class method.
    """
    p = type(cls_param)
    return super(type, cls).__new__(pt_class(cls, p))

def pt_class_getitem(cls: type, cls_param: type) -> type:
    """
    Function to be bound as proxy class `__class_getitem__` class method.
    """
    return pt_class(cls, cls_param)

def pt_class(cls: type, param: type) -> type:
    """
    Function to create or find proxy class for a generic pseudo-type.
    """
    assert isinstance(param, type)
    k = cls, param
    if k not in _REGISTRY:
        class X(cls): pass  # type: ignore
        _REGISTRY[k] = X
        logger.info('class for {} created'.format(k)) 

    return _REGISTRY[k]

# vim: sw=4:et:ai
