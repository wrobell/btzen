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
Bluetooth services implemented by BlueZ protocol stack.
"""

from .data import Make, ServiceType, Trigger, TriggerCondition
from .service import ServiceInterface, register_service
from .util import to_uuid

register_service(
    Make.STANDARD,
    ServiceType.BATTERY_LEVEL,
    ServiceInterface(
        to_uuid(0x180f),
        'org.bluez.Battery1',
        'Percentage',
        'y'
    ),
    trigger=Trigger(TriggerCondition.ON_CHANGE),
)

# vim: sw=4:et:ai
