#!/usr/bin/env python3
#
# BTZen - Bluetooh Smart sensor reading library.
#
# Copyright (C) 2015-2017 by Artur Wroblewski <wrobell@riseup.net>
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

from setuptools import setup, find_packages

setup(
    name='btzen',
    version='0.1.0',
    author='Artur Wroblewski',
    author_email='wrobell@riseup.net',
    url='https://github.com/wrobell/btzen',
    description='BTZen - Bluetooh Smart sensor reading library',
    setup_requires = ['setuptools_git >= 1.0',],
    cffi_modules=['cffi_builders/btzen_build.py:ffi'],
    install_requires=['cffi >= 1.4.2'],
    classifiers=[
        'License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Development Status :: 3 - Alpha',
        'Topic :: Software Development :: Libraries',
    ],
    packages=find_packages('.'),
    scripts=('bin/btzen',),
    include_package_data=True,
)

# vim: sw=4:et:ai

