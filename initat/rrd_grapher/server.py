#!/usr/bin/python-init -Ot
#
# Copyright (C) 2007-2009,2013-2014 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file belongs to the rrd-server package
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
""" server-part of rrd-grapher """

from django.db import connection
from initat.rrd_grapher.config import global_config
from initat.rrd_grapher.graph import graph_process
from initat.rrd_grapher.struct import data_store
from lxml.builder import E # @UnresolvedImport
import cluster_location
import configfile
import logging_tools
import os
import process_tools
import server_command
import stat
import threading_tools
import time
import uuid_tools
import zmq
try:
    import rrdtool # @UnresolvedImport
except ImportError:
    rrdtool = None

class server_process(threading_tools.process_pool):
    def __init__(self):
        self.__log_cache, self.__log_template = ([], None)
        self.__pid_name = global_config["PID_NAME"]
        self.__verbose = global_config["VERBOSE"]
        threading_tools.process_pool.__init__(self, "main", zmq=True, zmq_debug=global_config["ZMQ_DEBUG"])
        self.__log_template = logging_tools.get_logger(global_config["LOG_NAME"], global_config["LOG_DESTINATION"], zmq=True, context=self.zmq_context)
        if not global_config["DEBUG"]:
            process_tools.set_handles({
                "out" : (1, "rrd-grapher.out"),
                "err" : (0, "/var/lib/logging-server/py_err_zmq")},
                                      zmq_context=self.zmq_context)
        self.__msi_block = self._init_msi_block()
        # re-insert config
        self._re_insert_config()
        self.register_exception("int_error", self._int_error)
        self.register_exception("term_error", self._int_error)
        self.register_exception("hup_error", self._hup_error)
        self._log_config()
        self._init_network_sockets()
        self.add_process(graph_process("graph"), start=True)
        connection.close()
        self.register_func("send_command", self._send_command)
        self.register_timer(self._clear_old_graphs, 60, instant=True)
        self.register_timer(self._check_for_stale_rrds, 3600, instant=True)
        data_store.setup(self)
    def _log_config(self):
        self.log("Config info:")
        for line, log_level in global_config.get_log(clear=True):
            self.log(" - clf: [%d] %s" % (log_level, line))
        conf_info = global_config.get_config_info()
        self.log("Found %d valid global config-lines:" % (len(conf_info)))
        for conf in conf_info:
            self.log("Config : %s" % (conf))
    def _re_insert_config(self):
        cluster_location.write_config("rrd_server", global_config)
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
    def _hup_error(self, err_cause):
        self.log("got sighup", logging_tools.LOG_LEVEL_WARN)
    def process_start(self, src_process, src_pid):
        mult = 3
        process_tools.append_pids(self.__pid_name, src_pid, mult=mult)
        if self.__msi_block:
            self.__msi_block.add_actual_pid(src_pid, mult=mult, process_name=src_process)
            self.__msi_block.save_block()
    def _check_for_stale_rrds(self):
        cur_time = time.time()
        # set stale after two hours
        MAX_DT = 3600 * 2
        num_changed = 0
        for pk in data_store.present_pks():
            _struct = data_store.get_instance(pk)
            enabled, disabled = (0, 0)
            for file_el in _struct.xml_vector.xpath(".//*[@file_name]", smart_strings=False):
                f_name = file_el.attrib["file_name"]
                if os.path.isfile(f_name):
                    c_time = os.stat(f_name)[stat.ST_CTIME]
                    stale = abs(cur_time - c_time) > MAX_DT
                    if stale and rrdtool:
                        # check via rrdtool
                        try:
                            rrd_info = rrdtool.info(f_name)
                        except:
                            self.log("cannot get info for {} via rrdtool: {}".format(
                                f_name,
                                process_tools.get_except_info()
                                ), logging_tools.LOG_LEVEL_ERROR)
                        else:
                            c_time = int(rrd_info["last_update"])
                            stale = abs(cur_time - c_time) > MAX_DT
                    is_active = True if int(file_el.attrib["active"]) else False
                    if is_active and stale:
                        file_el.attrib["active"] = "0"
                        disabled += 1
                    elif not is_active and not stale:
                        file_el.attrib["active"] = "1"
                        disabled += 1
                else:
                    self.log("file '%s' missing, disabling" % (file_el.attrib["file_name"]), logging_tools.LOG_LEVEL_ERROR)
                    file_el.attrib["active"] = "0"
                    disabled += 1
            if enabled or disabled:
                num_changed += 1
                self.log("updated active info for %s: %d enabled, %d disabled" % (
                    _struct.name,
                    enabled,
                    disabled,
                    ))
                _struct.store()
        self.log("checked for stale entries, modified %s" % (logging_tools.get_plural("device", num_changed)))
    def _clear_old_graphs(self):
        cur_time = time.time()
        graph_root = global_config["GRAPH_ROOT"]
        del_list = []
        if os.path.isdir(graph_root):
            for entry in os.listdir(graph_root):
                if entry.endswith(".png"):
                    full_name = os.path.join(graph_root, entry)
                    c_time = os.stat(full_name)[stat.ST_CTIME]
                    diff_time = abs(c_time - cur_time)
                    if diff_time > 5 * 60:
                        del_list.append(full_name)
        else:
            self.log("graph_root '%s' not found, strange" % (graph_root), logging_tools.LOG_LEVEL_ERROR)
        if del_list:
            self.log("clearing %s is %s" % (
                logging_tools.get_plural("old graph", len(del_list)),
                graph_root))
            for del_entry in del_list:
                try:
                    os.unlink(del_entry)
                except:
                    pass
    def _init_msi_block(self):
        process_tools.save_pid(self.__pid_name, mult=3)
        process_tools.append_pids(self.__pid_name, pid=configfile.get_manager_pid(), mult=3)
        if not global_config["DEBUG"] or True:
            self.log("Initialising meta-server-info block")
            msi_block = process_tools.meta_server_info("rrd-grapher")
            msi_block.add_actual_pid(mult=3, fuzzy_ceiling=3, process_name="main")
            msi_block.add_actual_pid(act_pid=configfile.get_manager_pid(), mult=3, process_name="manager")
            msi_block.start_command = "/etc/init.d/rrd-grapher start"
            msi_block.stop_command = "/etc/init.d/rrd-grapher force-stop"
            msi_block.kill_pids = True
            msi_block.save_block()
        else:
            msi_block = None
        return msi_block
    def _send_command(self, *args, **kwargs):
        _src_proc, _src_id, full_uuid, srv_com = args
        self.log("init send of %s bytes to %s" % (len(srv_com), full_uuid))
        self.com_socket.send_unicode(full_uuid, zmq.SNDMORE)
        self.com_socket.send_unicode(srv_com)
    def _init_network_sockets(self):
        client = self.zmq_context.socket(zmq.ROUTER)
        self.bind_id = "%s:rrd_grapher" % (uuid_tools.get_uuid().get_urn())
        client.setsockopt(zmq.IDENTITY, self.bind_id)
        client.setsockopt(zmq.SNDHWM, 256)
        client.setsockopt(zmq.RCVHWM, 256)
        client.setsockopt(zmq.TCP_KEEPALIVE, 1)
        client.setsockopt(zmq.TCP_KEEPALIVE_IDLE, 300)
        bind_str = "tcp://*:%d" % (global_config["COM_PORT"])
        try:
            client.bind(bind_str)
        except zmq.ZMQError:
            self.log(
                "error binding to %d: %s" % (
                    global_config["COM_PORT"],
                    process_tools.get_except_info()
                ),
                logging_tools.LOG_LEVEL_CRITICAL)
            raise
        else:
            self.log("bound to %s" % (bind_str))
            self.register_poller(client, zmq.POLLIN, self._recv_command)
            self.com_socket = client
    def _interpret_mv_info(self, in_vector):
        data_store.feed_vector(in_vector[0])
    def _interpret_perfdata_info(self, host_name, pd_type, pd_info):
        data_store.feed_perfdata(host_name, pd_type, pd_info)
    def _get_node_rrd(self, srv_com):
        node_results = E.node_results()
        dev_list = srv_com.xpath(".//device_list", smart_strings=False)[0]
        pk_list = [int(cur_pk) for cur_pk in dev_list.xpath(".//device/@pk", smart_strings=False)]
        for dev_pk in pk_list:
            cur_res = E.node_result(pk="%d" % (dev_pk))
            if data_store.has_rrd_xml(dev_pk):
                cur_res.append(data_store.get_rrd_xml(dev_pk, sort=True))
            else:
                self.log("no rrd_xml found for device %d" % (dev_pk), logging_tools.LOG_LEVEL_WARN)
            node_results.append(cur_res)
        if int(dev_list.get("merge_results", "0")):
            data_store.merge_node_results(node_results)
        srv_com["result"] = node_results
    def _recv_command(self, zmq_sock):
        in_data = []
        while True:
            in_data.append(zmq_sock.recv())
            if not zmq_sock.getsockopt(zmq.RCVMORE):
                break
        if len(in_data) == 2:
            src_id, data = in_data
            try:
                srv_com = server_command.srv_command(source=data)
            except:
                self.log(
                    "error interpreting command: %s" % (process_tools.get_except_info()),
                    logging_tools.LOG_LEVEL_ERROR)
                # send something back
                self.com_socket.send_unicode(src_id, zmq.SNDMORE)
                self.com_socket.send_unicode("internal error")
            else:
                cur_com = srv_com["command"].text
                if self.__verbose or cur_com not in ["ocsp-event", "ochp-event" "vector", "perfdata_info"]:
                    self.log("got command '%s' from '%s'" % (
                        cur_com,
                        srv_com["source"].attrib["host"]))
                srv_com.update_source()
                send_return = True
                srv_reply, srv_state = (
                    "ok processed command %s" % (cur_com),
                    server_command.SRV_REPLY_STATE_OK
                    )
                if cur_com in ["mv_info"]:
                    self._interpret_mv_info(srv_com["vector"])
                    send_return = False
                elif cur_com in ["perfdata_info"]:
                    self._interpret_perfdata_info(srv_com["hostname"].text, srv_com["pd_type"].text, srv_com["info"][0])
                    send_return = False
                elif cur_com == "get_node_rrd":
                    self._get_node_rrd(srv_com)
                elif cur_com == "graph_rrd":
                    send_return = False
                    self.send_to_process("graph", "graph_rrd", src_id, unicode(srv_com))
                elif cur_com == "get_0mq_id":
                    srv_com["zmq_id"] = self.bind_id
                    srv_reply = "0MQ_ID is %s" % (self.bind_id)
                elif cur_com == "status":
                    srv_reply = "up and running"
                else:
                    self.log("got unknown command '%s'" % (cur_com), logging_tools.LOG_LEVEL_ERROR)
                    srv_reply, srv_state = (
                        "unknown command '%s'" % (cur_com),
                        server_command.SRV_REPLY_STATE_ERROR,
                        )
                if send_return:
                    srv_com["result"] = None
                    # blabla
                    srv_com["result"].attrib.update(
                        {
                            "reply" : srv_reply,
                            "state" : "%d" % (srv_state)
                        }
                    )
                    self.com_socket.send_unicode(src_id, zmq.SNDMORE)
                    self.com_socket.send_unicode(unicode(srv_com))
                else:
                    del cur_com
        else:
            self.log(
                "wrong count of input data frames: %d, first one is %s" % (
                    len(in_data),
                    in_data[0]),
                logging_tools.LOG_LEVEL_ERROR)
    def loop_end(self):
        process_tools.delete_pid(self.__pid_name)
        if self.__msi_block:
            self.__msi_block.remove_meta_block()
    def loop_post(self):
        self.com_socket.close()
        self.__log_template.close()
    def thread_loop_post(self):
        process_tools.delete_pid(self.__pid_name)
        if self.__msi_block:
            self.__msi_block.remove_meta_block()

