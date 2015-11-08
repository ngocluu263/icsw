# Copyright (C) 2015 Andreas Lang-Nevyjel, init.at
#
# this file is part of icsw-client
#
# Send feedback to: <lang-nevyjel@init.at>
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

""" constants for service handling """

import os


__all__ = [
    # process states
    "SERVICE_OK",
    "SERVICE_DEAD",
    "SERVICE_NOT_INSTALLED",
    "SERVICE_INCOMPLETE",
    "SERVICE_NOT_CONFIGURED",
    # license states
    "LIC_STATE_EXPIRED",
    "LIC_STATE_GRACE",
    "LIC_STATE_NEW_INSTALL",
    "LIC_STATE_NONE",
    "LIC_STATE_NOT_NEEDED",
    "LIC_STATE_VALID",
    "LIC_STATE_VALID_IN_FUTURE",
    "LIC_STATE_VIOLATED",
    # target states
    "TARGET_STATE_RUNNING",
    "TARGET_STATE_STOPPED",
    # configured target states (by db or IP)
    "CONF_STATE_RUN",
    "CONF_STATE_STOP",
    "CONF_STATE_IP_MISMATCH",
    "CONF_STATE_MODELS_CHANGED",
    "INIT_BASE",
    "SERVERS_DIR",
    "STATE_DICT",
    "LIC_STATE_DICT",
    "CONF_STATE_DICT",
]

# service states (== process states)
SERVICE_OK = 0
SERVICE_DEAD = 1
SERVICE_INCOMPLETE = 2
SERVICE_NOT_INSTALLED = 3
SERVICE_NOT_CONFIGURED = 4

# configured states (== from DB)
CONF_STATE_RUN = 0
CONF_STATE_STOP = 1
CONF_STATE_IP_MISMATCH = 2
CONF_STATE_MODELS_CHANGED = 3

# license states
LIC_STATE_VIOLATED = 120
LIC_STATE_VALID = 100
LIC_STATE_GRACE = 80
LIC_STATE_NEW_INSTALL = 60
LIC_STATE_EXPIRED = 40
LIC_STATE_VALID_IN_FUTURE = 20
LIC_STATE_NONE = 0
LIC_STATE_NOT_NEEDED = -1

_locs = locals()

STATE_DICT = {
    _locs[_key]: _key.split("_", 1)[1].lower().replace("_", " ") for _key in _locs.keys() if _key.startswith("SERVICE_")
}

LIC_STATE_DICT = {
    _locs[_key]: _key.split("_", 2)[2].lower().replace("_", " ") for _key in _locs.keys() if _key.startswith("LIC_STATE_")
}

CONF_STATE_DICT = {
    _locs[_key]: _key.split("_", 2)[2].lower().replace("_", " ") for _key in _locs.keys() if _key.startswith("CONF_STATE_")
}

# for meta server
TARGET_STATE_STOPPED = 0
TARGET_STATE_RUNNING = 1

# path definitions
INIT_BASE = os.path.join("/", "opt", "python-init", "lib", "python", "site-packages", "initat")
SERVERS_DIR = os.path.join("/", "opt", "cluster", "etc", "servers.d")
