# -*- coding: utf-8 -*-
#
# Copyright (C) 2013-2014 Andreas Lang-Nevyjel
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

""" host-monitoring, with 0MQ and direct socket support, relay part """

from initat.host_monitoring import limits
import argparse
import logging_tools
import process_tools
import server_command
import time
import zmq


class sr_probe(object):
    __slots__ = ["host_con", "__val", "__time"]

    def __init__(self, host_con):
        self.host_con = host_con
        self.__val = {
            "send": 0,
            "recv": 0,
        }
        self.__time = time.time()

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.host_con.log("[probe for %s] %s" % (self.host_con.conn_str, what), log_level)

    @property
    def send(self):
        return self.__val["send"]

    @send.setter
    def send(self, val):
        cur_time = time.time()
        diff_time = abs(cur_time - self.__time)
        if diff_time > 30 * 60:
            self.log("sent / received in %s: %s / %s" % (
                logging_tools.get_diff_time_str(diff_time),
                logging_tools.get_size_str(self.__val["send"]),
                logging_tools.get_size_str(self.__val["recv"]),
            ))
            self.__time = cur_time
            self.__val = {
                "send": 0,
                "recv": 0
            }
        self.__val["send"] += val

    @property
    def recv(self):
        return self.__val["recv"]

    @recv.setter
    def recv(self, val):
        self.__val["recv"] += val


class host_connection(object):
    __slots__ = ["zmq_id", "tcp_con", "sr_probe", "__open", "__conn_str", "messages"]

    def __init__(self, conn_str, **kwargs):
        self.zmq_id = kwargs.get("zmq_id", "ms")
        self.__conn_str = conn_str
        self.tcp_con = kwargs.get("dummy_connection", False)
        host_connection.hc_dict[self.hc_dict_key] = self
        self.sr_probe = sr_probe(self)
        self.messages = {}
        self.__open = False

    @property
    def hc_dict_key(self):
        return (not self.tcp_con, self.__conn_str)

    @property
    def conn_str(self):
        return self.__conn_str

    def close(self):
        pass

    def __del__(self):
        pass

    @staticmethod
    def init(r_process, backlog_size, timeout, verbose):
        host_connection.relayer_process = r_process
        # 2 queues for 0MQ and tcp, 0MQ is (True, conn_str), TCP is (False, conn_str)
        host_connection.hc_dict = {}
        # lut to map message_ids to host_connections
        host_connection.message_lut = {}
        host_connection.backlog_size = backlog_size
        host_connection.timeout = timeout
        host_connection.verbose = verbose
        host_connection.g_log(
            "backlog size is {:d}, timeout is {:d}, verbose is {}".format(
                host_connection.backlog_size,
                host_connection.timeout,
                str(host_connection.verbose),
            )
        )
        # router socket
        new_sock = host_connection.relayer_process.zmq_context.socket(zmq.ROUTER)
        id_str = "relayer_rtr_{}".format(process_tools.get_machine_name())
        new_sock.setsockopt(zmq.IDENTITY, id_str)
        new_sock.setsockopt(zmq.LINGER, 0)
        new_sock.setsockopt(zmq.SNDHWM, host_connection.backlog_size)
        new_sock.setsockopt(zmq.RCVHWM, host_connection.backlog_size)
        new_sock.setsockopt(zmq.RECONNECT_IVL_MAX, 500)
        new_sock.setsockopt(zmq.RECONNECT_IVL, 200)
        new_sock.setsockopt(zmq.BACKLOG, host_connection.backlog_size)
        new_sock.setsockopt(zmq.TCP_KEEPALIVE, 1)
        new_sock.setsockopt(zmq.TCP_KEEPALIVE_IDLE, 300)
        host_connection.zmq_socket = new_sock
        host_connection.relayer_process.register_poller(new_sock, zmq.POLLIN, host_connection.get_result)

    @staticmethod
    def get_hc_0mq(conn_str, target_id="ms", **kwargs):
        if (True, conn_str) not in host_connection.hc_dict:
            if host_connection.verbose > 1:
                host_connection.relayer_process.log("new 0MQ host_connection for '%s'" % (conn_str))
            cur_hc = host_connection(conn_str, zmq_id=target_id, **kwargs)
        else:
            cur_hc = host_connection.hc_dict[(True, conn_str)]
        return cur_hc

    @staticmethod
    def get_hc_tcp(conn_str, **kwargs):
        if (False, conn_str) not in host_connection.hc_dict:
            if host_connection.verbose > 1:
                host_connection.relayer_process.log("new TCP host_connection for '%s'" % (conn_str))
            cur_hc = host_connection(conn_str, **kwargs)
        else:
            cur_hc = host_connection.hc_dict[(False, conn_str)]
        return cur_hc

    @staticmethod
    def check_timeout_global(id_discovery):
        # global check_timeout function
        cur_time = time.time()
        id_discovery.check_timeout(cur_time)
        # check timeouts for all host connections
        [cur_hc.check_timeout(cur_time) for cur_hc in host_connection.hc_dict.itervalues()]

    @staticmethod
    def global_close():
        host_connection.zmq_socket.close()

    @staticmethod
    def g_log(what, log_level=logging_tools.LOG_LEVEL_OK):
        host_connection.relayer_process.log("[hc] {}".format(what), log_level)

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        host_connection.relayer_process.log("[hc {}] {}".format(self.__conn_str, what), log_level)

    def check_timeout(self, cur_time):
        # check all messages for current host_connection
        to_messages = [cur_mes for cur_mes in self.messages.itervalues() if cur_mes.check_timeout(cur_time, host_connection.timeout)]
        if to_messages:
            for to_mes in to_messages:
                self.return_error(
                    to_mes,
                    "timeout (after {:.2f} seconds [{:.2f}, {:.2f}])".format(
                        to_mes.get_runtime(cur_time),
                        host_connection.timeout,
                        to_mes.timeout,
                    )
                )

    def _open(self):
        if not self.__open:
            try:
                self.log("connecting")
                host_connection.zmq_socket.connect(self.__conn_str)
            except:
                raise
            else:
                self.__open = True
                # make a short nap to let 0MQ settle things down
                time.sleep(0.2)
        return self.__open

    def _close(self):
        if self.__open:
            host_connection.zmq_socket.close()
            self.__open = False

    def add_message(self, new_mes):
        host_connection.message_lut[new_mes.src_id] = self.hc_dict_key
        self.messages[new_mes.src_id] = new_mes
        return new_mes

    def send(self, host_mes, com_struct):
        try:
            host_mes.set_com_struct(com_struct)
        except:
            self.return_error(
                host_mes,
                "error parsing arguments: %s" % (process_tools.get_except_info()))
        else:
            if not self.tcp_con:
                try:
                    self._open()
                except:
                    self.return_error(
                        host_mes,
                        "error connecting to %s: %s" % (self.__conn_str,
                                                        process_tools.get_except_info()))
                else:
                    if False and self.__backlog_counter == host_connection.backlog_size:
                        # no stupid backlog counting
                        self.return_error(
                            host_mes,
                            "connection error (backlog full [%d.%d]) for '%s'" % (
                                self.__backlog_counter,
                                host_connection.backlog_size,
                                self.__conn_str))
                        # self._close()
                    else:
                        try:
                            host_connection.zmq_socket.send_unicode(self.zmq_id, zmq.DONTWAIT | zmq.SNDMORE)
                            send_str = unicode(host_mes.srv_com)
                            host_connection.zmq_socket.send_unicode(send_str, zmq.DONTWAIT)
                        except:
                            self.return_error(
                                host_mes,
                                "connection error (%s)" % (process_tools.get_except_info()),
                            )
                        else:
                            # self.__backlog_counter += 1
                            self.sr_probe.send = len(send_str)
                            host_mes.sr_probe = self.sr_probe
                            host_mes.sent = True
            else:
                # send to socket-thread for old clients
                host_connection.relayer_process.send_to_process(
                    "socket",
                    "connection",
                    host_mes.src_id,
                    unicode(host_mes.srv_com))

    def send_result(self, host_mes, result=None):
        host_connection.relayer_process.sender_socket.send_unicode(host_mes.src_id, zmq.SNDMORE)
        host_connection.relayer_process.sender_socket.send_unicode(host_mes.get_result(result))
        del self.messages[host_mes.src_id]
        del host_connection.message_lut[host_mes.src_id]
        del host_mes

    # @staticmethod
    # def _send_result(host_mes, result=None):
    #    host_connection.relayer_process.sender_socket.send_unicode(host_mes.src_id, zmq.SNDMORE)
    #    host_connection.relayer_process.sender_socket.send_unicode(host_mes.get_result(result))
    #    del host_connection.messages[host_mes.src_id]
    #    del host_mes

    def return_error(self, host_mes, error_str):
        host_mes.set_result(limits.nag_STATE_CRITICAL, error_str)
        self.send_result(host_mes)

    def _error(self, zmq_sock):
        # not needed right now
        # print "**** _error", zmq_sock
        # print dir(zmq_sock)
        # print zmq_sock.getsockopt(zmq.EVENTS)
        pass
        # self._close()
        # raise zmq.ZMQError()

    @staticmethod
    def get_result(zmq_sock):
        _src_id = zmq_sock.recv()
        cur_reply = server_command.srv_command(source=zmq_sock.recv())
        host_connection._handle_result(cur_reply)

    @staticmethod
    def _handle_result(result):
        # print unicode(result)
        mes_id = result["relayer_id"].text
        # if mes_id in host_connection.messages:
        if mes_id in host_connection.message_lut:
            host_connection.relayer_process._new_client(result["host"].text, int(result["port"].text))
            if "host_unresolved" in result:
                host_connection.relayer_process._new_client(result["host_unresolved"].text, int(result["port"].text))
            host_connection.hc_dict[host_connection.message_lut[mes_id]].handle_result(mes_id, result)
        else:
            host_connection.g_log("got result for delayed id '%s'" % (mes_id), logging_tools.LOG_LEVEL_WARN)
        del result

    def handle_result(self, mes_id, result):
        cur_mes = self.messages[mes_id]
        if cur_mes.sent:
            cur_mes.sent = False
            # self.__backlog_counter -= 1
        if len(result.xpath(".//ns:raw", smart_strings=False)):
            # raw response, no interpret
            cur_mes.srv_com = result
            self.send_result(cur_mes, None)
            # self.send_result(cur_mes, None)
        else:
            try:
                res_tuple = cur_mes.interpret(result)
            except:
                res_tuple = (
                    limits.nag_STATE_CRITICAL,
                    "error interpreting result: %s" % (
                        process_tools.get_except_info()))
                exc_info = process_tools.exception_info()
                for line in exc_info.log_lines:
                    host_connection.relayer_process.log(line, logging_tools.LOG_LEVEL_CRITICAL)
            self.send_result(cur_mes, res_tuple)
            # self.send_result(cur_mes, res_tuple)

    def _handle_old_result(self, mes_id, result):
        if mes_id in host_connection.messages:
            cur_mes = host_connection.messages[mes_id]
            if result.startswith("no valid"):
                res_tuple = (limits.nag_STATE_CRITICAL, result)
            else:
                host_connection.relayer_process._old_client(cur_mes.srv_com["host"].text, int(cur_mes.srv_com["port"].text))
                try:
                    res_tuple = cur_mes.interpret_old(result)
                except:
                    res_tuple = (limits.nag_STATE_CRITICAL, "error interpreting result: %s" % (process_tools.get_except_info()))
            self.send_result(cur_mes, res_tuple)
        else:
            self.log("unknown id '%s' in _handle_old_result" % (mes_id), logging_tools.LOG_LEVEL_ERROR)


class host_message(object):
    hm_idx = 0
    hm_open = set()
    __slots__ = ["src_id", "xml_input", "timeout", "s_time", "sent", "sr_probe", "ns", "com_name", "srv_com", "com_struct"]

    def __init__(self, com_name, src_id, srv_com, xml_input):
        self.com_name = com_name
        # self.hm_idx = host_message.hm_idx
        # host_message.hm_idx += 1
        # host_message.hm_open.add(self.hm_idx)
        self.src_id = src_id
        self.xml_input = xml_input
        self.srv_com = srv_com
        # print srv_com.pretty_print()
        self.timeout = int(srv_com.get("timeout", "10"))
        self.srv_com[""].append(srv_com.builder("relayer_id", self.src_id))
        self.s_time = time.time()
        self.sent = False
        self.sr_probe = None

    def set_result(self, state, res_str):
        self.srv_com.set_result(res_str, state)

    def set_com_struct(self, com_struct):
        self.com_struct = com_struct
        if com_struct:
            cur_ns, rest = com_struct.handle_commandline((self.srv_com["arg_list"].text or "").split())
            _e = self.srv_com.builder()
            _arg_list = self.srv_com.xpath(".//ns:arg_list", smart_strings=False)
            if len(_arg_list):
                _arg_list[0].text = " ".join(rest)
            else:
                self.srv_com[""].append(_e.arg_list(" ".join(rest)))
            self.srv_com.delete_subtree("arguments")
            self.srv_com[""].append(
                _e.arguments(
                    *([getattr(_e, "arg%d" % (arg_idx))(arg) for arg_idx, arg in enumerate(rest)] + [_e.rest(" ".join(rest))])
                )
            )
            self.srv_com.delete_subtree("namespace")
            for key, value in vars(cur_ns).iteritems():
                self.srv_com["namespace:{}".format(key)] = value
            self.ns = cur_ns
        else:
            # connect to non-host-monitoring service
            self.srv_com["arguments:rest"] = self.srv_com["arg_list"].text
            self.ns = argparse.Namespace()

    def check_timeout(self, cur_time, to_value):
        # check for timeout, to_value is a global timeout from the host_connection object
        _timeout = self.get_runtime(cur_time) > min(to_value, self.timeout - 2)
        return _timeout

    def get_runtime(self, cur_time):
        return abs(cur_time - self.s_time)

    def get_result(self, result):
        if result is None:
            result = self.srv_com
        if type(result) == tuple:
            # from interpret
            if not self.xml_input:
                ret_str = u"%d\0%s" % (
                    result[0],
                    result[1]
                )
            else:
                # shortcut
                self.set_result(result[0], result[1])
                ret_str = unicode(self.srv_com)
        else:
            if not self.xml_input:
                ret_str = u"%s\0%s" % (
                    result["result"].attrib["state"],
                    result["result"].attrib["reply"],
                )
            else:
                ret_str = unicode(result)
        return ret_str

    def interpret(self, result):
        if self.sr_probe:
            self.sr_probe.recv = len(result)
            self.sr_probe = None
        server_error = result.xpath(".//ns:result[@state != '0']", smart_strings=False)
        if server_error:
            return (int(server_error[0].attrib["state"]),
                    server_error[0].attrib["reply"])
        else:
            return self.com_struct.interpret(result, self.ns)

    def interpret_old(self, result):
        if type(result) not in [str, unicode]:
            server_error = result.xpath(".//ns:result[@state != '0']", smart_strings=False)
        else:
            server_error = None
        if server_error:
            return (int(server_error[0].attrib["state"]),
                    server_error[0].attrib["reply"])
        else:
            if result.startswith("error "):
                return (limits.nag_STATE_CRITICAL,
                        result)
            else:
                # copy host, hacky hack
                self.com_struct.NOGOOD_srv_com = self.srv_com
                ret_value = self.com_struct.interpret_old(result, self.ns)
                del self.com_struct.NOGOOD_srv_com
                return ret_value

    def __del__(self):
        # host_message.hm_open.remove(self.hm_idx)
        del self.srv_com
        pass
