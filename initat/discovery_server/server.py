# Copyright (C) 2014 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# this file is part of discovery-server
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
""" discovery-server, server part """

from django.db import connection
from django.db.models import Q
from initat.cluster.backbone.models import device
from initat.cluster.backbone.routing import get_server_uuid
from initat.discovery_server.config import global_config
from initat.discovery_server.discovery import discovery_process
from lxml import etree  # @UnresolvedImport
from lxml.builder import E  # @UnresolvedImport
import cluster_location
import configfile
import logging_tools
import process_tools
import server_command
import threading_tools
import zmq


class server_process(threading_tools.process_pool):
    def __init__(self):
        self.__log_cache, self.__log_template = ([], None)
        self.__pid_name = global_config["PID_NAME"]
        threading_tools.process_pool.__init__(self, "main", zmq=True, zmq_debug=global_config["ZMQ_DEBUG"])
        self.register_exception("int_error", self._int_error)
        self.register_exception("term_error", self._int_error)
        self.__log_template = logging_tools.get_logger(global_config["LOG_NAME"], global_config["LOG_DESTINATION"], zmq=True, context=self.zmq_context)
        self._re_insert_config()
        self._log_config()
        self.__msi_block = self._init_msi_block()
        self.add_process(discovery_process("discovery"), start=True)
        self._init_network_sockets()
        self.register_func("discovery_result", self._discovery_result)
        # self.add_process(build_process("build"), start=True)
        connection.close()
        self.__run_idx = 0
        self.__pending_commands = {}

    def log(self, what, lev=logging_tools.LOG_LEVEL_OK):
        if self.__log_template:
            while self.__log_cache:
                self.__log_template.log(*self.__log_cache.pop(0))
            self.__log_template.log(lev, what)
        else:
            self.__log_cache.append((lev, what))

    def _int_error(self, err_cause):
        if self["exit_requested"]:
            self.log("exit already requested, ignoring", logging_tools.LOG_LEVEL_WARN)
        else:
            self["exit_requested"] = True

    def _re_insert_config(self):
        cluster_location.write_config("config_server", global_config)

    def _log_config(self):
        self.log("Config info:")
        for line, log_level in global_config.get_log(clear=True):
            self.log(" - clf: [%d] %s" % (log_level, line))
        conf_info = global_config.get_config_info()
        self.log("Found %d valid config-lines:" % (len(conf_info)))
        for conf in conf_info:
            self.log("Config : %s" % (conf))

    def process_start(self, src_process, src_pid):
        mult = 3
        process_tools.append_pids(self.__pid_name, src_pid, mult=mult)
        if self.__msi_block:
            self.__msi_block.add_actual_pid(src_pid, mult=mult)
            self.__msi_block.save_block()

    def _init_msi_block(self):
        process_tools.save_pid(self.__pid_name, mult=3)
        process_tools.append_pids(self.__pid_name, pid=configfile.get_manager_pid(), mult=3)
        if not global_config["DEBUG"] or True:
            self.log("Initialising meta-server-info block")
            msi_block = process_tools.meta_server_info("discovery-server")
            msi_block.add_actual_pid(mult=3, fuzzy_ceiling=3)
            msi_block.add_actual_pid(act_pid=configfile.get_manager_pid(), mult=3)
            msi_block.start_command = "/etc/init.d/discovery-server start"
            msi_block.stop_command = "/etc/init.d/discovery-server force-stop"
            msi_block.kill_pids = True
            msi_block.save_block()
        else:
            msi_block = None
        return msi_block

    def loop_end(self):
        process_tools.delete_pid(self.__pid_name)
        if self.__msi_block:
            self.__msi_block.remove_meta_block()

    def loop_post(self):
        self.com_socket.close()
        self.__log_template.close()

    def _init_network_sockets(self):
        my_0mq_id = get_server_uuid("config")
        self.bind_id = my_0mq_id
        # get all ipv4 interfaces with their ip addresses, dict: interfacename -> IPv4
        self.com_socket = process_tools.get_socket(self.zmq_context, "ROUTER", identity=self.bind_id)
        conn_str = "tcp://*:{:d}".format(global_config["SERVER_PORT"])
        try:
            self.com_socket.bind(conn_str)
        except zmq.ZMQError:
            self.log(
                "error binding to {}: {}".format(
                    conn_str,
                    process_tools.get_except_info()
                ),
                logging_tools.LOG_LEVEL_CRITICAL
            )
            self.com_socket.close()
        else:
            self.log(
                "bind socket to {}".format(
                    conn_str,
                )
            )
            self.register_poller(self.com_socket, zmq.POLLIN, self._new_com)

    def _discovery_result(self, *args, **kwargs):
        _src_prod, _src_pid, id_str, srv_com = args
        self.com_socket.send_unicode(id_str, zmq.SNDMORE)
        self.com_socket.send_unicode(srv_com)

    def _new_com(self, zmq_sock):
        data = [zmq_sock.recv_unicode()]
        while zmq_sock.getsockopt(zmq.RCVMORE):
            data.append(zmq_sock.recv_unicode())
        if len(data) == 2:
            c_uid, srv_com = (data[0], server_command.srv_command(source=data[1]))
            cur_com = srv_com["command"].text
            srv_com.update_source()
            if cur_com in [
                "fetch_partition_info", "scan_network_info"
            ]:
                self.send_to_process("discovery", cur_com, c_uid, unicode(srv_com))
            else:
                srv_com.set_result("unknown command '{}'".format(cur_com), server_command.SRV_REPLY_STATE_ERROR)
                self.com_socket.send_unicode(c_uid, zmq.SNDMORE)
                self.com_socket.send_unicode(unicode(srv_com))

        else:
            self.log("wrong number of data chunks (%d != 2), data is '%s'" % (len(data), data[:20]),
                     logging_tools.LOG_LEVEL_ERROR)
