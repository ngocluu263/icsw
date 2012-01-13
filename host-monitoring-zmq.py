#!/usr/bin/python-init -Ot
# -*- coding: utf-8 -*-
#
# Copyright (C) 2011 Andreas Lang-Nevyjel
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of host-monitoring
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
""" host-monitoring, with 0MQ and twisted support """

import zmq
import sys
import os
import os.path
import socket
import time
import logging_tools
import process_tools
import mail_tools
import threading_tools
import configfile
import server_command
import stat
import net_tools
from lxml import etree
import limits
import argparse

try:
    from host_monitoring_version import VERSION_STRING
except ImportError:
    VERSION_STRING = "?.?"

def client_code():
    import modules
    #log_template = logging_tools.get_logger(global_config["LOG_NAME"], global_config["LOG_DESTINATION"], zmq=True, context=)
    conn_str = "tcp://%s:%d" % (global_config["HOST"],
                                global_config["COM_PORT"])
    arg_stuff = global_config.get_argument_stuff()
    arg_list = arg_stuff["arg_list"]
    com_name = arg_list.pop(0)
    if com_name in modules.command_dict:
        srv_com = server_command.srv_command(command=com_name)#" ".join(arg_list))
        com_struct = modules.command_dict[com_name]
        try:
            cur_ns, rest = com_struct.handle_commandline(arg_list)
        except ValueError, what:
            ret_state, ret_str = (limits.nag_STATE_CRITICAL, "error parsing: %s" % (what[1]))
        else:
            print "***", cur_ns, rest
            if hasattr(cur_ns, "arguments"):
                for arg_index, arg in enumerate(cur_ns.arguments):
                    srv_com["arguments:arg%d" % (arg_index)] = arg
            srv_com["arguments:rest"] = " ".join(rest)
            result = net_tools.zmq_connection(global_config["IDENTITY_STRING"]).add_connection(conn_str, srv_com)
            if result:
                error_result = result.xpath(None, ".//ns:result[@state != '0']")
                if error_result:
                    error_result = error_result[0]
                    ret_state, ret_str = (int(error_result.attrib["state"]),
                                          error_result.attrib["reply"])
                else:
                    ret_state, ret_str = com_struct.interpret(result, cur_ns)
            else:
                ret_state, ret_str = (limits.nag_STATE_CRITICAL, "timeout")
    else:
        ret_str = "unknown command %s" % (com_name)
        ret_state = limits.nag_STATE_CRITICAL
    print ret_str
    return ret_state
    
class pending_connection(object):
    pending = {}
    counter = 0
    def __init__(self, r_thread, send_xml, src_id, srv_com, com_struct, conn_str):
        cur_ns, rest = com_struct.handle_commandline([])
        self.s_time = time.time()
        self.relayer_thread = r_thread
        pending_connection.counter += 1
        self.identity_str = "relay_%d" % (pending_connection.counter)
        cur_sock = self.relayer_thread.zmq_context.socket(zmq.XREQ)
        cur_sock.setsockopt(zmq.IDENTITY, self.identity_str)
        cur_sock.setsockopt(zmq.LINGER, 100)
        cur_sock.connect(conn_str)
        cur_sock.send_unicode(unicode(send_xml))
        pending_connection.pending[cur_sock] = self
        self.sock = cur_sock
        self.com_struct = com_struct
        self.ns = cur_ns
        self.src_id = src_id
        print "pending: %d" % (len(pending_connection.pending))
    @staticmethod
    def init():
        pending_connection.pending = {}
        pending_connection.counter = 0
    def close(self):
        del pending_connection.pending[self.sock]
        self.sock.close()
        self.relayer_thread.unregister_poller(self.sock, zmq.POLLIN)
        del self.sock
        del self
    def __del__(self):
        print "dpc #%s" % (self.identity_str)
    def interpret(self, result):
        return self.com_struct.interpret(result, self.ns)
    def send_result(self, result):
        self.relayer_thread.relayer_socket.send_unicode(self.src_id, zmq.SNDMORE)
        self.relayer_thread.relayer_socket.send_unicode(unicode(result))

class relay_thread(threading_tools.process_pool):
    def __init__(self):
        # copy to access from modules
        import modules
        self.modules = modules
        self.global_config = global_config
        self.__log_cache, self.__log_template = ([], None)
        threading_tools.process_pool.__init__(self, "main", zmq=True)
        self.renice()
        pending_connection.init()
        if not global_config["DEBUG"]:
            process_tools.set_handles({"out" : (1, "collrelay.out"),
                                       "err" : (0, "/var/lib/logging-server/py_err")},
                                      zmq_context=self.zmq_context)
        self.__log_template = logging_tools.get_logger(global_config["LOG_NAME"], global_config["LOG_DESTINATION"], zmq=True, context=self.zmq_context)
        self.install_signal_handlers()
        self._init_msi_block()
        self._init_ipc_sockets()
        self.register_exception("int_error", self._sigint)
        self.register_exception("term_error", self._sigint)
        self.register_timer(self._check_timeout, 1)
        self._show_config()
        if not self._init_commands():
            self._sigint("error init")
    def log(self, what, lev=logging_tools.LOG_LEVEL_OK):
        if self.__log_template:
            self.__log_template.log(lev, what)
        else:
            self.__log_cache.append((lev, what))
    def _sigint(self, err_cause):
        if self["exit_requested"]:
            self.log("exit already requested, ignoring", logging_tools.LOG_LEVEL_WARN)
        else:
            self["exit_requested"] = True
    def _init_msi_block(self):
        # store pid name because global_config becomes unavailable after SIGTERM
        self.__pid_name = global_config["PID_NAME"]
        process_tools.save_pids(global_config["PID_NAME"], mult=3)
        process_tools.append_pids(global_config["PID_NAME"], pid=configfile.get_manager_pid(), mult=2)
        if True:#not self.__options.DEBUG:
            self.log("Initialising meta-server-info block")
            msi_block = process_tools.meta_server_info("collrelay")
            msi_block.add_actual_pid(mult=3)
            msi_block.add_actual_pid(act_pid=configfile.get_manager_pid(), mult=2)
            msi_block.start_command = "/etc/init.d/host-relay start"
            msi_block.stop_command = "/etc/init.d/host-relay force-stop"
            msi_block.kill_pids = True
            #msi_block.heartbeat_timeout = 60
            msi_block.save_block()
        else:
            msi_block = None
        self.__msi_block = msi_block
    def _check_timeout(self):
        cur_time = time.time()
        del_nodes = [value for value in pending_connection.pending.itervalues() if abs(value.s_time - cur_time) > 5]
        if del_nodes:
            print "*", del_nodes
            [cur_node.close() for cur_node in del_nodes]
    def _init_ipc_sockets(self):
        client = self.zmq_context.socket(zmq.XREP)
        try:
            process_tools.bind_zmq_socket(client, process_tools.get_zmq_ipc_name("receiver"))
        except zmq.core.error.ZMQError:
            self.log("error binding %s: %s" % (process_tools.get_zmq_ipc_name("receiver"),
                                               process_tools.get_except_info()),
                     logging_tools.LOG_LEVEL_CRITICAL)
            raise
        else:
            self.relayer_socket = client
            os.chmod(process_tools.get_zmq_ipc_name("receiver")[5:], 0777)
            self.register_poller(client, zmq.POLLIN, self._recv_command)
    def _recv_command(self, zmq_sock):
        print "RECV"
        src_id = zmq_sock.recv()
        more = zmq_sock.getsockopt(zmq.RCVMORE)
        if more:
            data = zmq_sock.recv()
            more = zmq_sock.getsockopt(zmq.RCVMORE)
            print data
            srv_com = server_command.srv_command(source=data)
            self.log("got command '%s' from '%s'" % (srv_com["command"].text,
                                                     srv_com["source"].attrib["host"]))
            self._send_to_client(src_id, srv_com)
            #zmq_sock.send_unicode(src_id, zmq.SNDMORE)
            #zmq_sock.send_unicode(unicode(result))
        else:
            self.log("cannot receive more data, already got '%s'" % (src_id),
                     logging_tools.LOG_LEVEL_ERROR)
    def _send_to_client(self, src_id, srv_com):
        # generate new xml from srv_com
        send_xml = server_command.srv_command(command=srv_com["command"].text)
        target_host, target_port = ("localhost", 2001)
        conn_str = "tcp://%s:%d" % (target_host,
                                    target_port)
        com_struct = self.modules.command_dict[send_xml["command"].text]
        # handle commandline
        self.register_poller(pending_connection(self, send_xml, src_id, srv_com, com_struct, conn_str).sock, zmq.POLLIN, self._get_result)
        #result = net_tools.zmq_connection(identity_string).add_connection(conn_str, send_xml)
        #return result
    def _get_result(self, zmq_sock):
        result = server_command.srv_command(source=zmq_sock.recv())
        cur_pc = pending_connection.pending[zmq_sock]
        cur_pc.send_result(result)
        cur_pc.close()
    def _close_socket(self, zmq_sock):
        del self.__send_dict[zmq_sock]
        self.unregister_poller(zmq_sock, zmq.POLLIN)
    def _handle_module_command(self, srv_com):
        try:
            self.commands[srv_com["command"].text](srv_com)
        except:
            exc_info = process_tools.exception_info()
            for log_line in process_tools.exception_info().log_lines:
                self.log(log_line, logging_tools.LOG_LEVEL_ERROR)
            srv_com["result"].attrib.update({
                "reply" : "caught server exception '%s'" % (process_tools.get_except_info()),
                "state" : "%d" % (server_command.SRV_REPLY_STATE_CRITICAL)})
    def _show_config(self):
        try:
            for log_line, log_level in global_config.get_log():
                self.log("Config info : [%d] %s" % (log_level, log_line))
        except:
            self.log("error showing configfile log, old configfile ? (%s)" % (process_tools.get_except_info()),
                     logging_tools.LOG_LEVEL_ERROR)
        conf_info = global_config.get_config_info()
        self.log("Found %s:" % (logging_tools.get_plural("valid configline", len(conf_info))))
        for conf in conf_info:
            self.log("Config : %s" % (conf))
    def loop_end(self):
        process_tools.delete_pid(self.__pid_name)
        if self.__msi_block:
            self.__msi_block.remove_meta_block()
    def _init_commands(self):
        self.log("init commands")
        self.module_list = self.modules.module_list
        self.commands = self.modules.command_dict
        _init_ok = True
        for call_name, add_self in [("register_server", True),
                                    ("init_module", False)]:
            for cur_mod in self.modules.module_list:
                if global_config["VERBOSE"]:
                    self.log("calling %s for module '%s'" % (call_name,
                                                             cur_mod.name))
                try:
                    if add_self:
                        getattr(cur_mod, call_name)(self)
                    else:
                        getattr(cur_mod, call_name)()
                except:
                    exc_info = process_tools.exception_info()
                    for log_line in exc_info.log_lines:
                        self.log(log_line, logging_tools.LOG_LEVEL_CRITICAL)
                    _init_ok = False
                    break
            if not _init_ok:
                break
        return _init_ok

class server_thread(threading_tools.process_pool):
    def __init__(self):
        # copy to access from modules
        self.global_config = global_config
        self.__log_cache, self.__log_template = ([], None)
        threading_tools.process_pool.__init__(self, "main", zmq=True)
        self.renice()
        if not global_config["DEBUG"]:
            process_tools.set_handles({"out" : (1, "host-monitoring.out"),
                                       "err" : (0, "/var/lib/logging-server/py_err")},
                                      zmq_context=self.zmq_context)
        self.__log_template = logging_tools.get_logger(global_config["LOG_NAME"], global_config["LOG_DESTINATION"], zmq=True, context=self.zmq_context)
        self.install_signal_handlers()
        self._init_msi_block()
        self._init_network_sockets()
        self.register_exception("int_error", self._sigint)
        self.register_exception("term_error", self._sigint)
        self._show_config()
        if not self._init_commands():
            self._sigint("error init")
    def log(self, what, lev=logging_tools.LOG_LEVEL_OK):
        if self.__log_template:
            self.__log_template.log(lev, what)
        else:
            self.__log_cache.append((lev, what))
    def _sigint(self, err_cause):
        if self["exit_requested"]:
            self.log("exit already requested, ignoring", logging_tools.LOG_LEVEL_WARN)
        else:
            self["exit_requested"] = True
    def _init_msi_block(self):
        # store pid name because global_config becomes unavailable after SIGTERM
        self.__pid_name = global_config["PID_NAME"]
        process_tools.save_pids(global_config["PID_NAME"], mult=3)
        process_tools.append_pids(global_config["PID_NAME"], pid=configfile.get_manager_pid(), mult=2)
        if True:#not self.__options.DEBUG:
            self.log("Initialising meta-server-info block")
            msi_block = process_tools.meta_server_info("collserver")
            msi_block.add_actual_pid(mult=3)
            msi_block.add_actual_pid(act_pid=configfile.get_manager_pid(), mult=2)
            msi_block.start_command = "/etc/init.d/host-monitoring start"
            msi_block.stop_command = "/etc/init.d/host-monitoring force-stop"
            msi_block.kill_pids = True
            #msi_block.heartbeat_timeout = 60
            msi_block.save_block()
        else:
            msi_block = None
        self.__msi_block = msi_block
    def _init_network_sockets(self):
        client = self.zmq_context.socket(zmq.XREP)
        client.setsockopt(zmq.IDENTITY, "ms")
        try:
            client.bind("tcp://*:%d" % (global_config["COM_PORT"]))
        except zmq.core.error.ZMQError:
            self.log("error binding to %d: %s" % (global_config["COM_PORT"],
                                                  process_tools.get_except_info()),
                     logging_tools.LOG_LEVEL_CRITICAL)
            raise
        else:
            self.register_poller(client, zmq.POLLIN, self._recv_command)
    def _recv_command(self, zmq_sock):
        src_id = zmq_sock.recv()
        more = zmq_sock.getsockopt(zmq.RCVMORE)
        if more:
            data = zmq_sock.recv()
            more = zmq_sock.getsockopt(zmq.RCVMORE)
            print "*", src_id, len(data)
            srv_com = server_command.srv_command(source=data)
            rest_el = srv_com.xpath(None, ".//ns:arguments/ns:rest")
            if rest_el:
                rest_str = rest_el[0].text or u""
            else:
                rest_str = u""
            self.log("got command '%s' from '%s'" % (srv_com["command"].text,
                                                     srv_com["source"].attrib["host"]))
            
            srv_com.update_source()
            srv_com["result"] = {"state" : server_command.SRV_REPLY_STATE_OK,
                                 "reply" : "ok"}
            if srv_com["command"].text == "status":
                srv_com["result"].attrib["reply"] = "ok process is running"
            elif srv_com["command"].text == "version":
                srv_com["result"].attrib["reply"] = "version is %s" % (VERSION_STRING)
            elif srv_com["command"].text in self.commands:
                self._handle_module_command(srv_com, rest_str)
                #srv_com["result"].attrib.update(["reply"] = "ok got %s" % (srv_com["command"].text)
            else:
                srv_com["result"].attrib.update(
                    {"reply" : "unknown command '%s'" % (srv_com["command"].text),
                     "state" : "%d" % (server_command.SRV_REPLY_STATE_ERROR)})
            zmq_sock.send_unicode(src_id, zmq.SNDMORE)
            zmq_sock.send_unicode(unicode(srv_com))
        else:
            self.log("cannot receive more data, already got '%s'" % (src_id),
                     logging_tools.LOG_LEVEL_ERROR)
    def _handle_module_command(self, srv_com, rest_str):
        cur_com = self.commands[srv_com["command"].text]
        try:
            cur_ns = cur_com.handle_server_commandline(rest_str.split())
            cur_com(srv_com, cur_ns)
        except:
            exc_info = process_tools.exception_info()
            for log_line in process_tools.exception_info().log_lines:
                self.log(log_line, logging_tools.LOG_LEVEL_ERROR)
            srv_com["result"].attrib.update({
                "reply" : "caught server exception '%s'" % (process_tools.get_except_info()),
                "state" : "%d" % (server_command.SRV_REPLY_STATE_CRITICAL)})
    def _show_config(self):
        try:
            for log_line, log_level in global_config.get_log():
                self.log("Config info : [%d] %s" % (log_level, log_line))
        except:
            self.log("error showing configfile log, old configfile ? (%s)" % (process_tools.get_except_info()),
                     logging_tools.LOG_LEVEL_ERROR)
        conf_info = global_config.get_config_info()
        self.log("Found %s:" % (logging_tools.get_plural("valid configline", len(conf_info))))
        for conf in conf_info:
            self.log("Config : %s" % (conf))
    def loop_end(self):
        process_tools.delete_pid(self.__pid_name)
        if self.__msi_block:
            self.__msi_block.remove_meta_block()
    def _init_commands(self):
        self.log("init commands")
        import modules
        self.module_list = modules.module_list
        self.commands = modules.command_dict
        _init_ok = True
        for call_name, add_self in [("register_server", True),
                                    ("init_module", False)]:
            for cur_mod in modules.module_list:
                if global_config["VERBOSE"]:
                    self.log("calling %s for module '%s'" % (call_name,
                                                             cur_mod.name))
                try:
                    if add_self:
                        getattr(cur_mod, call_name)(self)
                    else:
                        getattr(cur_mod, call_name)()
                except:
                    exc_info = process_tools.exception_info()
                    for log_line in exc_info.log_lines:
                        self.log(log_line, logging_tools.LOG_LEVEL_CRITICAL)
                    _init_ok = False
                    break
            if not _init_ok:
                break
        return _init_ok

global_config = configfile.get_global_config(process_tools.get_programm_name())

def main():
    long_host_name, mach_name = process_tools.get_fqdn()
    prog_name = global_config.name()
    global_config.add_config_entries([
        #("MAILSERVER"          , configfile.str_c_var("localhost", info="Mail Server")),
        ("DEBUG"               , configfile.bool_c_var(False, help_string="enable debug mode [%(default)s]", short_options="d", only_commandline=True)),
        ("LOG_DESTINATION"     , configfile.str_c_var("uds:/var/lib/logging-server/py_log")),
        ("LOG_NAME"            , configfile.str_c_var(prog_name)),
        ("KILL_RUNNING"        , configfile.bool_c_var(True)),
        ("SERVER_FULL_NAME"    , configfile.str_c_var(long_host_name)),
        ("VERBOSE"             , configfile.int_c_var(0, help_string="set verbose level [%(default)d]", short_options="v", only_commandline=True)),
        ("PID_NAME"            , configfile.str_c_var("%s/%s" % (prog_name,
                                                                 prog_name)))])
    if prog_name == "collserver":
        global_config.add_config_entries([
            ("COM_PORT", configfile.int_c_var(2001, info="listening Port", help_string="port to communicate [%(default)i]", short_options="p")),
        ])
    elif prog_name == "collclient":
        global_config.add_config_entries([
            ("IDENTITY_STRING", configfile.str_c_var("collclient", help_string="identity string", short_options="i")),
            ("COM_PORT", configfile.int_c_var(2001, info="listening Port", help_string="port to communicate [%(default)i]", short_options="p")),
            ("HOST"    , configfile.str_c_var("localhost", help_string="host to connect to"))
        ])
    global_config.parse_file()
    # import modules
    # modules = addon_modules("modules")
    options = global_config.handle_commandline(description="%s, version is %s" % (prog_name,
                                                                                  VERSION_STRING),
                                               add_writeback_option=prog_name in ["collserver"],
                                               positional_arguments=prog_name in ["collclient"],
                                               partial=prog_name in ["collclient"])
    # always set FROM_ADDR
    #global_config["FROM_ADDR"] = long_host_name
    global_config.write_file()
    #process_tools.fix_directories("root", "root", [(glob_config["MAIN_DIR"], 0777)])
    if not options.DEBUG and prog_name in ["collserver"]:
        process_tools.become_daemon()
    elif prog_name in ["collserver"]:
        print "Debugging %s on %s" % (prog_name,
                                      global_config["SERVER_FULL_NAME"])
    if prog_name == "collserver":
        ret_state = server_thread().loop()
    elif prog_name == "collrelay":
        ret_state = relay_thread().loop()
    elif prog_name == "collclient":
        ret_state = client_code()
    else:
        print "Unknown opmode %s" % (prog_name)
        ret_state = -1
    sys.exit(ret_state)

if __name__ == "__main__":
    main()
