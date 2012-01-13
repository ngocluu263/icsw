#!/usr/bin/python-init -Ot
#
# Copyright (C) 2008,2010 Andreas Lang-Nevyjel, init.at
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

import sys
import re
import commands
import limits
import hm_classes
import os
import os.path
import time
import logging_tools
import pprint
try:
    import drbd_tools
except ImportError:
    drbd_tools = None

class my_modclass(hm_classes.hm_fileinfo):
    def __init__(self, **args):
        hm_classes.hm_fileinfo.__init__(self,
                                        "drbd",
                                        "provides a interface to check the status of DRBD hosts",
                                        **args)
    def init(self, mode, logger, basedir_name, **args):
        self.__last_drbd_check = (-1, -1)
        if mode == "i":
            if drbd_tools:
                self.drbd_config = drbd_tools.drbd_config()
            else:
                self.drbd_config = None

class drbd_status_command(hm_classes.hmb_command):
    def __init__(self, **args):
        hm_classes.hmb_command.__init__(self, "drbd_status", **args)
        self.help_str = "returns the status of the hosts DRBD devices"
        self.is_immediate = True
    def server_call(self, cm):
        if drbd_tools:
            self.module_info.drbd_config._parse_all()
            return "ok %s" % (self.module_info.drbd_config.get_net_data())
        else:
            return "error no drbd_tools found"
    def client_call(self, result, parsed_coms):
        if result.startswith("ok "):
            drbd_conf = drbd_tools.drbd_config(data=result[3:])
            if drbd_conf:
                if drbd_conf["status_present"] and drbd_conf["config_present"]:
                    res_dict = drbd_conf["resources"]
                    res_keys = sorted(res_dict.keys())
                    num_total, num_warn, num_error, state_dict = (len(res_keys), 0, 0, {"total" : res_keys})
                    dev_states, ret_strs = ([], [])
                    for key in res_keys:
                        loc_dict = res_dict[key]["localhost"]
                        # check connection_state
                        c_state = loc_dict["connection_state"].lower()
                        if c_state in ["connected"]:
                            dev_state = limits.nag_STATE_OK
                        elif c_state in ["unconfigured", "syncsource", "synctarget", "wfconnection", "wfreportparams",
                                         "pausedsyncs", "pausedsynct", "wfbitmaps", "wfbitmapt"]:
                            dev_state = limits.nag_STATE_WARNING
                        else:
                            dev_state = limits.nag_STATE_CRITICAL
                        # check states
                        if "state" in loc_dict:
                            state_dict.setdefault(loc_dict["state"][0], []).append(key)
                            for state in loc_dict["state"]:
                                if state not in ["primary", "secondary"]:
                                    dev_state = max(dev_state, limits.nag_STATE_CRITICAL)
                        else:
                            dev_state = limits.nag_STATE_CRITICAL
                        if dev_state != limits.nag_STATE_OK:
                            #pprint.pprint(loc_dict)
                            ret_strs.append("%s (%s, protocol '%s'%s): cs %s, %s, ds %s" % (key,
                                                                                            loc_dict["device"],
                                                                                            loc_dict.get("protocol", "???"),
                                                                                            ", %s%%" % (loc_dict["resync_percentage"]) if loc_dict.has_key("resync_percentage") else "",
                                                                                            c_state,
                                                                                            "/".join(loc_dict.get("state", ["???"])),
                                                                                            "/".join(loc_dict.get("data_state", ["???"]))))
                        dev_states.append(dev_state)
                        #pprint.pprint(res_dict[key]["localhost"])
                    #pprint.pprint(state_dict)
                    ret_state = max(dev_states)
                    return ret_state, "%s: %s; %s" % (limits.get_state_str(ret_state),
                                                      ", ".join([logging_tools.get_plural(key, len(value)) for key, value in state_dict.iteritems()]),
                                                      ", ".join(ret_strs) if ret_strs else "everything ok")
                else:
                    ret_strs = []
                    if not drbd_conf["status_present"]:
                        ret_state = limits.nag_STATE_WARNING
                        ret_strs.append("drbd status not present, module not loaded ?")
                    elif not drbd_conf["config_present"]:
                        ret_state = limits.nag_STATE_CRITICAL
                        ret_strs.append("drbd config not present")
                    return ret_state, "%s: %s" % (limits.get_state_str(ret_state),
                                                  ", ".join(ret_strs))
            else:
                return limits.nag_STATE_WARNING, "warn empty dbrd_config"
        else:
            return limits.nag_STATE_CRITICAL, "error %s" % (resulto)

if __name__ == "__main__":
    print "This is a loadable module."
    sys.exit(0)
