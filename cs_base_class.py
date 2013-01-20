#!/usr/bin/python-init -Ot
#
# Copyright (C) 2007,2012,2013 Andreas Lang-Nevyjel
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
import config_tools
import time
import os
import logging_tools
import cluster_location
import pprint
from django.db import connection
from django.conf import settings

class server_com(object):
    class Meta:
        # callable via net
        available_via_net = True
        # restartable
        restartable = False
        # is blocking
        blocking = True
        # needed configurations
        needed_configs = []
        # actual configs
        actual_configs = []
        # needed options keys
        needed_option_keys = []
        # write log entries
        write_log = True
        # show execution time
        show_execution_time = True
        # keys needed in config
        needed_config_keys = []
        # public via network
        public_via_net = True
    def __init__(self):
        # copy Meta keys
        for key in dir(server_com.Meta):
            if not key.startswith("__") and not hasattr(self.Meta, key):
                setattr(self.Meta, key, getattr(server_com.Meta, key))
    def link(self, process_pool):
        self.process_pool = process_pool
    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.process_pool.log("[com] %s" % (what), log_level)
    def check_config(self, loc_config, force=False):
        self.server_idx, self.act_config_name = (0, "")
        doit, srv_origin, err_str = (False, "---", "OK")
        if self.Meta.needed_configs:
            for act_c in self.Meta.needed_configs:
                sql_info = config_tools.server_check(server_type="%s" % (act_c))
                if sql_info.effective_device:
                    doit, srv_origin = (True, sql_info.server_origin)
                    if not self.server_idx:
                        self.server_device_name = sql_info.effective_device.name
                        self.server_idx, self.act_config_name = (sql_info.effective_device.pk, sql_info.effective_device.name)
            if doit:
                self.Meta.actual_configs = self.Meta.needed_configs
            else:
                if force:
                    doit = True
                else:
                    err_str = "Server %s has no %s attribute" % (loc_config["SERVER_SHORT_NAME"], " or ".join(self.Meta.needed_configs))
        else:
            doit = True
        if doit and self.Meta.needed_config_keys:
            for key in self.Meta.needed_config_keys:
                if key not in loc_config:
                    self.log("key '%s' not defined in config" % (key), logging_tools.LOG_LEVEL_ERROR)
                    doit = False
        if doit and srv_origin == "---":
            srv_origin = "yes"
        return (doit, srv_origin, err_str)
    def __call__(self):
        if settings.DEBUG:
            pre_queries = len(connection.queries)
        self.start_time = time.time()
        result = self._call()
        self.end_time = time.time()
        if int(self.srv_com["result"].attrib["state"]):
            self.log("result is (%d) %s" % (int(self.srv_com["result"].attrib["state"]),
                                            self.srv_com["result"].attrib["reply"]),
                     logging_tools.LOG_LEVEL_ERROR)
        if self.Meta.show_execution_time:
            self.log("run took %s" % (logging_tools.get_diff_time_str(self.end_time - self.start_time)))
            self.srv_com["result"].attrib["reply"] = "%s in %s" % (
                self.srv_com["result"].attrib["reply"],
                logging_tools.get_diff_time_str(self.end_time - self.start_time))
        if settings.DEBUG:
            self.log("queries executed : %d" % (len(connection.queries) - pre_queries))
        return result
    def write_start_log(self):
        if self.Meta.write_log:
            self.log("Got command %s (options %s) from host %s (port %d) to %s, %s: %s" % (
                self.srv_com["command"].text,
                "self.opt_str",
                "self.src_host",
                0,#"self.src_port",
                "self.loc_ip",
                logging_tools.get_plural("config", len(self.Meta.actual_configs)),
                ", ".join(self.Meta.actual_configs)))
    def write_end_log(self):
        if self.Meta.write_log:
            # FIXME
            pass
        
if __name__ == "__main__":
    print "Loadable module, exiting ..."
    sys.exit(0)
