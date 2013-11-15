#!/usr/bin/python-init -Ot
#
# Copyright (C) 2001,2002,2003,2004,2005,2006,2007,2008,2009,2012,2013 Andreas Lang-Nevyjel
#
# this file is part of package-server
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
""" package server """

import os
import logging_tools
import server_command
import threading_tools
import time
from django.db import connection
from django.db.models import Q
from initat.cluster.backbone.models import package_search
from initat.package_install.server.config import global_config
from initat.package_install.server.structs import repo_type_rpm_yum, repo_type_rpm_zypper, \
    subprocess_struct

class repo_process(threading_tools.process_obj):
    def process_init(self):
        self.__log_template = logging_tools.get_logger(
            global_config["LOG_NAME"],
            global_config["LOG_DESTINATION"],
            zmq=True,
            context=self.zmq_context,
            init_logger=True)
        # close database connection
        connection.close()
        self.register_func("rescan_repos", self._rescan_repos)
        self.register_func("reload_searches", self._reload_searches)
        self.register_func("search", self._search)
        self.__background_commands = []
        self.register_timer(self._check_delayed, 1)
        # set repository type
        if os.path.isfile("/etc/centos-release"):
            self.repo_type = repo_type_rpm_yum(self)
        else:
            self.repo_type = repo_type_rpm_zypper(self)
    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__log_template.log(log_level, what)
    def loop_post(self):
        self.__log_template.close()
    def _check_delayed(self):
        if len(self.__background_commands):
            self.log("%s running in background" % (logging_tools.get_plural("command", len(self.__background_commands))))
        cur_time = time.time()
        new_list = []
        for cur_del in self.__background_commands:
            if cur_del.Meta.use_popen:
                if cur_del.finished():
                    # print "finished delayed"
                    # print "cur_del.send_return()"
                    pass
                elif abs(cur_time - cur_del._init_time) > cur_del.Meta.max_runtime:
                    self.log("delay_object runtime exceeded, stopping")
                    cur_del.terminate()
                    # cur_del.send_return()
                else:
                    new_list.append(cur_del)
            else:
                if not cur_del.terminated:
                    new_list.append(cur_del)
        self.__background_commands = new_list
    # commands
    def _rescan_repos(self, *args, **kwargs):
        if args:
            srv_com = server_command.srv_command(source=args[0])
        else:
            srv_com = None
        self.log("rescan repositories")
        self.__background_commands.append(subprocess_struct(
            self,
            0 if srv_com is None else int(srv_com["return_id"].text),
            self.repo_type.SCAN_REPOS,
            start=True,
            verbose=global_config["DEBUG"],
            post_cb_func=self.repo_type.repo_scan_result))
    def _search(self, s_string):
        self.log("searching for '%s'" % (s_string))
        self.__background_commands.append(subprocess_struct(self, 0, self.repo_type.search_package(s_string), start=True, verbose=global_config["DEBUG"], post_cb_func=self.repo_type.search_result))
    def _reload_searches(self, *args, **kwargs):
        self.log("reloading searches")
        search_list = []
        for cur_search in package_search.objects.filter(Q(deleted=False) & Q(current_state__in=["ini", "wait"])):
            search_list.append((self.repo_type.search_package(cur_search.search_string), cur_search))
        if search_list:
            self.log("%s found" % (logging_tools.get_plural("search", len(search_list))))
            self.__background_commands.append(subprocess_struct(
                self,
                0,
                search_list,
                start=True,
                verbose=global_config["DEBUG"],
                pre_cb_func=self.repo_type.init_search,
                post_cb_func=self.repo_type.search_result))
        else:
            self.log("nothing to search", logging_tools.LOG_LEVEL_WARN)

