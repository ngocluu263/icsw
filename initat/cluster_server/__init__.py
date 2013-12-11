#!/usr/bin/python -Ot
#
# Copyright (C) 2012,2013 Andreas Lang-Nevyjel
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

from initat.cluster_server import cs_base_class
import imp
import os.path
import pkgutil
import pprint
import process_tools
import sys

__all__ = [cur_entry for cur_entry in [entry.split(".")[0] for entry in os.listdir(os.path.dirname(__file__)) if entry.endswith("_mod.py")] if cur_entry and not cur_entry.startswith("_")]

_new_hm_list = []
for mod_name in __all__:
    new_mod = __import__(mod_name, globals(), locals())
    _new_hm_list.extend([cur_obj for cur_obj in [getattr(new_mod, key) for key in dir(new_mod)] if type(cur_obj) == type and issubclass(cur_obj, cs_base_class.server_com)])

error_log = []
command_dict = {}
for hm in _new_hm_list:
    try:
        command_dict[hm.__name__] = hm()
    except:
        error_log.append("%s : %s" % (
            hm.__name__,
            process_tools.get_except_info()))
    else:
        if not hm.Meta.disabled:
            command_dict[hm.__name__].name = hm.__name__
        else:
            del command_dict[hm.__name__]

command_names = sorted(command_dict.keys())
