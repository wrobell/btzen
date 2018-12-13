#!/usr/bin/env python3
#
# BTZen - Bluetooth Smart sensor reading library.
#
# Copyright (C) 2015-2018 by Artur Wroblewski <wrobell@riseup.net>
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
Build setup for btsensor library.
"""

from setuptools import setup, find_packages, Extension
from Cython.Build import cythonize

setup(
    name='btzen',
    version='0.2.5',
    author='Artur Wroblewski',
    author_email='wrobell@riseup.net',
    url='https://github.com/wrobell/btzen',
    description='BTZen - Bluetooth Smart sensor reading library',
    setup_requires = ['setuptools_git >= 1.0',],
    classifiers=[
        'License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Development Status :: 3 - Alpha',
        'Topic :: Software Development :: Libraries',
    ],
    ext_modules=cythonize([
        Extension('btzen._btzen', ['btzen/_btzen.pyx'], libraries=['systemd'])
    ]),
    packages=find_packages('.'),
    include_package_data=True,
    long_description="""\
Library to asynchronously access Bluetooth Smart devices.

Features

1. Devices and sensor readings

   - SensorTag (CC2541DK, CC2650STK)

     - temperature
     - pressure
     - humidity
     - light (CC2650STK only)
     - accelerometer (CC2650STK only)
     - buttons (CC2650STK only)

   - Mi Smart Scale
   - serial devices implementing Stollmann (Telit) protocol

2. Device access using `asyncio` coroutines.
3. Notifications interface is supported.

The scripts in `scripts` directory demonstrate reading data from various
Bluetooth Smart devices, i.e. Sensor Tag, Mi Smart Scale or OSTC dive
computer.
"""
)

# vim: sw=4:et:ai

