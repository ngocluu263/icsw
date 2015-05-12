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

__all__ = ['get_available_licenses', 'LicenseEnum', 'LicenseParameterTypeEnum']


def id_string_to_user_name(cls, id_string):
    try:
        return cls[id_string].to_user_name()
    except KeyError:
        return id_string

# NOTE: This file has been automatically generated by generate_license_list.py
# DO NOT EDIT

LicenseEnum = Enum('LicenseEnum', 'md_config_server kpi graphing discovery_server monitoring_dashboard distributed_monitoring snapshot notification network_weathermap rootkit_hunter reporting ext_license virtual_desktop hpc_workbench package_install rms')
LicenseEnum.to_user_name = lambda x: dict(((LicenseEnum.md_config_server, 'MD Config Server'), (LicenseEnum.kpi, 'Key Performance Indicators'), (LicenseEnum.graphing, 'Graphing'), (LicenseEnum.discovery_server, 'Discover Server'), (LicenseEnum.monitoring_dashboard, 'Monitoring dashboard'), (LicenseEnum.distributed_monitoring, 'Distributed Monitoring'), (LicenseEnum.snapshot, 'Database snapshot'), (LicenseEnum.notification, 'Notifications'), (LicenseEnum.network_weathermap, 'Network Weathermap'), (LicenseEnum.rootkit_hunter, 'Rootkit Hunter'), (LicenseEnum.reporting, 'Reporting'), (LicenseEnum.ext_license, 'License Optimization Management'), (LicenseEnum.virtual_desktop, 'Virtual Desktop'), (LicenseEnum.hpc_workbench, 'HPC Workbench'), (LicenseEnum.package_install, 'Package Install'), (LicenseEnum.rms, 'Resource Management System'))).get(x, None)
LicenseEnum.id_string_to_user_name = classmethod(id_string_to_user_name)

# NOTE: This file has been automatically generated by generate_license_list.py
# DO NOT EDIT

LicenseParameterTypeEnum = Enum('LicenseParameterTypeEnum', 'service device user ext_license')
LicenseParameterTypeEnum.to_user_name = lambda x: dict(((LicenseParameterTypeEnum.service, 'Service'), (LicenseParameterTypeEnum.device, 'Device'), (LicenseParameterTypeEnum.user, 'User'), (LicenseParameterTypeEnum.ext_license, 'External license'))).get(x, None)
LicenseParameterTypeEnum.id_string_to_user_name = classmethod(id_string_to_user_name)

# NOTE: This file has been automatically generated by generate_license_list.py
# DO NOT EDIT


def get_available_licenses():
    from initat.cluster.backbone.models.license import InitProduct
    AvailableLicense = namedtuple('AvailableLicense', ['id', 'enum_value', 'name', 'description', 'product'])

    available_licenses = []

    available_licenses.append(AvailableLicense(id=u'md_config_server', enum_value=LicenseEnum.md_config_server, name=u'MD Config Server',description=u'Monitoring Daemon Configuration Writer', product=InitProduct.NOCTUA))
    available_licenses.append(AvailableLicense(id=u'kpi', enum_value=LicenseEnum.kpi, name=u'Key Performance Indicators',description=u'Calculate key figures to measure the performance of your cluster', product=InitProduct.NOCTUA))
    available_licenses.append(AvailableLicense(id=u'graphing', enum_value=LicenseEnum.graphing, name=u'Graphing',description=u'Comprehensive graphical evaluation using RRDs', product=InitProduct.NOCTUA))
    available_licenses.append(AvailableLicense(id=u'discovery_server', enum_value=LicenseEnum.discovery_server, name=u'Discover Server',description=u'Automatical configuration using SNMP', product=InitProduct.NOCTUA))
    available_licenses.append(AvailableLicense(id=u'monitoring_dashboard', enum_value=LicenseEnum.monitoring_dashboard, name=u'Monitoring dashboard',description=u'Central monitoring unit consisting of livestatus, geolocation and maplocation', product=InitProduct.NOCTUA))
    available_licenses.append(AvailableLicense(id=u'distributed_monitoring', enum_value=LicenseEnum.distributed_monitoring, name=u'Distributed Monitoring',description=u'Distribute monitoring load to multiple workers', product=InitProduct.NOCTUA))
    available_licenses.append(AvailableLicense(id=u'snapshot', enum_value=LicenseEnum.snapshot, name=u'Database snapshot',description=u'Keep track of the configuration changes', product=InitProduct.NOCTUA))
    available_licenses.append(AvailableLicense(id=u'notification', enum_value=LicenseEnum.notification, name=u'Notifications',description=u'Status notifications via mail and text messages', product=InitProduct.NOCTUA))
    available_licenses.append(AvailableLicense(id=u'network_weathermap', enum_value=LicenseEnum.network_weathermap, name=u'Network Weathermap',description=u'Overview of relevant network utilization data', product=InitProduct.NOCTUA))
    available_licenses.append(AvailableLicense(id=u'rootkit_hunter', enum_value=LicenseEnum.rootkit_hunter, name=u'Rootkit Hunter',description=u'Security scan for installations', product=InitProduct.NOCTUA))
    available_licenses.append(AvailableLicense(id=u'reporting', enum_value=LicenseEnum.reporting, name=u'Reporting',description=u'Generate graphs to view the state of your cluster', product=InitProduct.NOCTUA))
    available_licenses.append(AvailableLicense(id=u'ext_license', enum_value=LicenseEnum.ext_license, name=u'License Optimization Management',description=u'Interactive graphic license utlilization evaluation', product=InitProduct.NOCTUA))
    available_licenses.append(AvailableLicense(id=u'virtual_desktop', enum_value=LicenseEnum.virtual_desktop, name=u'Virtual Desktop',description=u'Manage virtual desktop sessions on your cluster', product=InitProduct.NESTOR))
    available_licenses.append(AvailableLicense(id=u'hpc_workbench', enum_value=LicenseEnum.hpc_workbench, name=u'HPC Workbench',description=u'Convenient interface for job management', product=InitProduct.NESTOR))
    available_licenses.append(AvailableLicense(id=u'package_install', enum_value=LicenseEnum.package_install, name=u'Package Install',description=u'Configure repositories and install packages on your nodes', product=InitProduct.NESTOR))
    available_licenses.append(AvailableLicense(id=u'rms', enum_value=LicenseEnum.rms, name=u'Resource Management System',description=u'Overview over your job system', product=InitProduct.NESTOR))

    return available_licenses