# Copyright (C) 2011-2016 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of icsw-server
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License Version 3 as
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
# -*- coding: utf-8 -*-
#

"""
system-wide constants for the ICSW
"""

from __future__ import unicode_literals, print_function

import os
import sys

__all__ = [
    b"GEN_CS_NAME",
    b"DB_ACCESS_CS_NAME",
    b"VERSION_CS_NAME",
    b"CLUSTER_DIR",
    b"CONFIG_STORE_ROOT",
    b"USER_EXTENSION_ROOT",
    b"LOG_ROOT",
    b"MON_DAEMON_INFO_FILE",
    b"PY_LIBDIR_SHORT",
    b"ICSW_ROOT",
    b"SITE_PACKAGES_BASE",
    b"INITAT_BASE",
    b"INITAT_BASE_DEBUG",
]

GEN_CS_NAME = "icsw.general"
DB_ACCESS_CS_NAME = "icsw.db.access"
VERSION_CS_NAME = "icsw.sysversion"

# python version
_PY_VERSION = "{:d}.{:d}".format(
    sys.version_info.major,
    sys.version_info.minor
)
PY_LIBDIR_SHORT = "python{}".format(_PY_VERSION)

# cluster dir
_cluster_dir = os.path.join("/", "opt", "cluster")
_icsw_root = os.path.join("/", "opt", "python-init", "lib", PY_LIBDIR_SHORT, "site-packages")

_os_vars = {"ICSW_CLUSTER_DIR", "ICSW_ROOT"}

if any([_var in os.environ for _var in _os_vars]) and not all([_var in os.environ for _var in _os_vars]):
    print(
        "not all environment vars for debugging are set: {}".format(
            ", ".join(
                [
                    "{} ({})".format(
                        _var,
                        "present" if _var in os.environ else "not present",
                    ) for _var in sorted(_os_vars)
                ]
            )
        )
    )
    raise SystemExit

CLUSTER_DIR = os.environ.get("ICSW_CLUSTER_DIR", _cluster_dir)
ICSW_ROOT = os.environ.get("ICSW_ROOT", _icsw_root)

# user extension dir
USER_EXTENSION_ROOT = os.path.join(CLUSTER_DIR, "share", "user_extensions.d")
# changed from cluster to icsw due to clash with corosync packages
LOG_ROOT = "/var/log/icsw"
# monitoring daemon info
MON_DAEMON_INFO_FILE = os.path.join(CLUSTER_DIR, "etc", "mon_info")

SITE_PACKAGES_BASE = ICSW_ROOT
CONFIG_STORE_ROOT = os.path.join(CLUSTER_DIR, "etc", "cstores.d")

BACKBONE_DIR = os.path.join(ICSW_ROOT, "initat", "cluster", "backbone")

# system base
INITAT_BASE = os.path.join(SITE_PACKAGES_BASE, "initat")
# local debug base (== same as INITAT_BASE for production)
INITAT_BASE_DEBUG = os.path.dirname(__file__)
