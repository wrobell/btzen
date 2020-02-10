#!/usr/bin/env python3
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
Build setup for the BTZen library.
"""

import ast
import sys
from setuptools import setup, find_packages, Extension

VERSION = ast.parse(
    next(l for l in open('btzen/__init__.py') if l.startswith('__version__'))
).body[0].value.s

try:
    from Cython.Build import cythonize
except:
    sys.exit(
        '\ncython is required, please install it with: pip install cython'
    )

setup(
    name='btzen',
    version=VERSION,
    author='Artur Wroblewski',
    author_email='wrobell@riseup.net',
    url='https://github.com/wrobell/btzen',
    description='BTZen - library to asynchronously access Bluetooth devices',
    setup_requires = ['setuptools_git >= 1.0',],
    classifiers=[
        'License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Development Status :: 3 - Alpha',
        'Topic :: Software Development :: Libraries',
    ],
    ext_modules=cythonize([
        Extension('btzen._sd_bus', ['btzen/_sd_bus.pyx'], libraries=['systemd']),
        Extension('btzen._btzen', ['btzen/_btzen.pyx'], libraries=['systemd']),
        Extension('btzen._cm', ['btzen/_cm.pyx'], libraries=['systemd']),
    ]),
    packages=find_packages('.'),
    include_package_data=True,
    long_description=open('README').read(),
    long_description_content_type='text/x-rst',
)

# vim: sw=4:et:ai

