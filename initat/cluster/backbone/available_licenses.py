# -*- coding: utf-8 -*-
#
# Copyright (C) 2015 Bernhard Mallinger
#
# Send feedback to: <mallinger@init.at>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License Version 2 as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#

from collections import namedtuple
from enum import Enum


# NOTE: This file has been automatically generated by generate_license_list.py
# DO NOT EDIT

__all__ = ['get_available_licenses', 'LicenseEnum']


LicenseEnum = Enum('LicenseEnum', 'kpi ext_lic package_install virtual_desktop a')


LicenseParameterTypeEnum = Enum('LicenseParameterTypeEnum', 'services node user ext_lic')


def get_available_licenses():
    AvailableLicense = namedtuple('AvailableLicense', ['id', 'name', 'description'])

    available_licenses = []

    available_licenses.append(AvailableLicense(id=u'kpi', name=u'KPI', description=u'Key Performance Indicators'))
    available_licenses.append(AvailableLicense(id=u'ext_lic', name=u'License Optimization Management', description=u'Manage external licenses'))
    available_licenses.append(AvailableLicense(id=u'package_install', name=u'Package Install', description=u''))
    available_licenses.append(AvailableLicense(id=u'virtual_desktop', name=u'Virtual Desktop', description=u''))
    available_licenses.append(AvailableLicense(id=u'a', name=u'b', description=u''))

    return available_licenses
