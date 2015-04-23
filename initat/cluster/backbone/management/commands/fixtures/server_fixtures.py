# -*- coding: utf-8 -*-
#
# Copyright (C) 2014 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of cluster-server
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License Version 2 as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FTNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#
""" creates fixtures for cluster-server """

from initat.cluster.backbone import factories


def add_fixtures(**kwargs):
    factories.Config(
        name="server",
        description="sets device as a cluster-server",
        server_config=True,
        system_config=True,
    )
    factories.Config(
        name="quota_scan",
        description="scan quotas for all users when device has quotas enabled",
        server_config=True,
        system_config=True,
    )
    factories.Config(
        name="user_scan",
        description="scan user dirs for all users found on this device",
        server_config=True,
        system_config=True,
    )
    factories.Config(
        name="usv_server",
        description="device has an USV from APC directly attached",
        server_config=True,
        system_config=True,
    )
    factories.Config(
        name="virtual_desktop",
        description="device can offer virtual desktops to users",
        server_config=True,
        system_config=True,
    )
    factories.Config(
        name="virtual_desktop_client",
        description="device has a virtual desktop client",
        server_config=True,
        system_config=True,
    )
    factories.Config(
        name="auto_etc_hosts",
        description="/etc/hosts file can be created from local cluster-server",
        server_config=True,
        system_config=True,
    )
