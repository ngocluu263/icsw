#!/usr/bin/python-init -OtW default
#
# Copyright (C) 2014 Andreas Lang-Nevyjel, init.at
#
# this file is part of md-config-server
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
"""

syncer process for md-config-server
keeps the monitoring-clients in sync and collects vital information about their installed
software and performance

"""

from django.db import connection
from django.db.models import Q
from initat.cluster.backbone.models import device
from initat.md_config_server import constants
from initat.md_config_server.config import global_config, sync_config
import logging_tools
import config_tools
import server_command
import threading_tools

class syncer_process(threading_tools.process_obj):
    def process_init(self):
        self.__log_template = logging_tools.get_logger(global_config["LOG_NAME"], global_config["LOG_DESTINATION"], zmq=True, context=self.zmq_context, init_logger=True)
        connection.close()
        self.router_obj = config_tools.router_object(self.log)
        self.__register_timer = False
        self.register_func("send_register_msg", self._send_register_msg)
        self.register_func("file_content_result", self._file_content_result)
        self.register_func("file_content_bulk_result", self._file_content_result)
        self.register_func("check_for_slaves", self._check_for_slaves)
        self.register_func("check_for_redistribute", self._check_for_redistribute)
        self.register_func("build_info", self._build_info)
        self.__build_in_progress, self.__build_version = (False, 0)
    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__log_template.log(log_level, what)
    def loop_post(self):
        self.__log_template.close()
    def _check_for_slaves(self, **kwargs):
        master_server = device.objects.get(Q(pk=global_config["SERVER_IDX"]))
        slave_servers = device.objects.filter(Q(device_config__config__name="monitor_slave")).select_related("domain_tree_node")
        # slave configs
        self.__master_config = sync_config(self, master_server, distributed=True if len(slave_servers) else False)
        self.__slave_configs, self.__slave_lut = ({}, {})
        # connect to local relayer
        self.log("  master %s (IP %s, %s)" % (master_server.full_name, "127.0.0.1", master_server.uuid))
        self.send_pool_message("register_slave", "127.0.0.1", master_server.uuid)
        if len(slave_servers):
            self.log(
                "found %s: %s" % (
                    logging_tools.get_plural("slave_server", len(slave_servers)),
                    ", ".join(sorted([cur_dev.full_name for cur_dev in slave_servers]))))
            for cur_dev in slave_servers:
                _slave_c = sync_config(
                    self,
                    cur_dev,
                    slave_name=cur_dev.full_name,
                    master_server=master_server,
                )
                self.__slave_configs[cur_dev.pk] = _slave_c
                self.__slave_lut[cur_dev.full_name] = cur_dev.pk
                self.__slave_lut[cur_dev.uuid] = cur_dev.pk
                self.log("  slave %s (IP %s, %s)" % (_slave_c.monitor_server.full_name, _slave_c.slave_ip, _slave_c.monitor_server.uuid))
                if _slave_c.slave_ip:
                    self.send_pool_message("register_slave", _slave_c.slave_ip, _slave_c.monitor_server.uuid)
                else:
                    self.log("slave has an invalid IP", logging_tools.LOG_LEVEL_CRITICAL)
        else:
            self.log("no slave-servers found")
        if not self.__register_timer:
            self.__register_timer = True
            self.register_func("relayer_info", self._relayer_info)
            self.register_timer(self._send_register_msg, 600, instant=global_config["DEBUG"])
    def _send_register_msg(self, **kwargs):
        master_server = device.objects.get(Q(pk=global_config["SERVER_IDX"]))
        for _slave_struct in [None] + self.__slave_configs.values():
            if _slave_struct:
                master_ip = _slave_struct.master_ip
                _srv = _slave_struct.monitor_server
            else:
                master_ip = "127.0.0.1"
                _srv = master_server
            srv_com = server_command.srv_command(
                command="register_master",
                host="DIRECT",
                port="0",
                master_ip=master_ip,
                master_port="%d" % (constants.SERVER_COM_PORT))
            self.log("send register_master to %s (master IP %s, UUID %s)" % (unicode(_srv), master_ip, _srv.uuid))
            self.send_command(_srv.uuid, unicode(srv_com))
    def send_command(self, src_id, srv_com):
        self.send_pool_message("send_command", "urn:uuid:%s:relayer" % (src_id), srv_com)
    def _check_for_redistribute(self, *args, **kwargs):
        for slave_config in self.__slave_configs.itervalues():
            slave_config.check_for_resend()
    def _file_content_result(self, *args, **kwargs):
        srv_com = server_command.srv_command(source=args[0])
        slave_name = srv_com["slave_name"].text
        if slave_name in self.__slave_lut:
            self.__slave_configs[self.__slave_lut[slave_name]].file_content_info(srv_com)
        else:
            self.log("unknown slave_name '%s'" % (slave_name), logging_tools.LOG_LEVEL_ERROR)
    def _relayer_info(self, *args, **kwargs):
        srv_com = server_command.srv_command(source=args[0])
        if "uuid" in srv_com:
            uuid = srv_com["uuid"].text.split(":")[-1]
            if uuid == self.__master_config.monitor_server.uuid:
                self.__master_config.set_relayer_info(srv_com)
            elif uuid in self.__slave_lut:
                _pk = self.__slave_lut[uuid]
                self.__slave_configs[_pk].set_relayer_info(srv_com)
            else:
                self.log("uuid %s not found in slave_lut" % (uuid), logging_tools.LOG_LEVEL_ERROR)
        else:
            self.log("uuid missing in relayer_info", logging_tools.LOG_LEVEL_ERROR)
    def _build_info(self, *args, **kwargs):
        _vals = list(args)
        _bi_type = _vals.pop(0)
        if _bi_type == "start_build":
            # config build started
            self.__build_in_progress, self.__build_version = (True, _vals.pop(0))
            self.log("build started (%d)" % (self.__build_version))
            self._master_md = self.__master_config.start_build(self.__build_version)
            for _conf in self.__slave_configs.values():
                _conf.start_build(self.__build_version, master=self._master_md)
        elif _bi_type == "end_build":
            self.__build_in_progress = False
            self.log("build ended (%d)" % (self.__build_version))
            self.__master_config.end_build()
            # trigger reload when sync is done
            for _slave in self.__slave_configs.itervalues():
                _slave.reload_after_sync()
        elif _bi_type == "sync_slave":
            slave_name = _vals.pop(0)
            if slave_name in self.__slave_lut:
                self.log("syncing config to slave '%s'" % (slave_name))
                slave_pk = self.__slave_lut[slave_name]
                self.__slave_configs[slave_pk].distribute()
            else:
                self.log("unknown slave '%s'" % (slave_name), logging_tools.LOG_LEVEL_CRITICAL)
        else:
            self.log("unknown build_info '%s'" % (str(args)), logging_tools.LOG_LEVEL_CRITICAL)
