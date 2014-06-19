# -*- coding: utf-8 -*-
#
# Copyright (C) 2012-2014 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of mother
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License Version 2 as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FTNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#
""" external commands (dhcp, ipmi, SNMP) parts of mother """

from django.db import connection
from django.db.models import Q
from initat.cluster.backbone.models import network, cd_connection, device_variable, \
    netdevice, devicelog, user
from initat.mother.command_tools import simple_command
from initat.snmp_relay.snmp_process import simple_snmp_oid
from initat.mother.config import global_config
import config_tools
import logging_tools
import process_tools
import re
import server_command
import threading_tools

class snmp_scheme(object):
    def __init__(self, cdc):
        self.cdc = cdc
    def set_command(self, command):
        _list = []
        if command == "cycle":
            _list = self.cycle()
        elif command == "on":
            _list = self.on()
        elif command == "off":
            _list = self.off()
        if _list:
            _list = ["S", _list]
        return _list

class apcv1_scheme(snmp_scheme):
    def cycle(self):
        # cdc ... controlling device connection
        return [
            (simple_snmp_oid((1, 3, 6, 1, 4, 1, 318, 1, 1, 12, 3, 3, 1, 1, 4, self.cdc.parameter_i1), target_value=3)),
        ]
    def on(self):
        # cdc ... controlling device connection
        # delayed on : 5, delayed off : 6, delayed cycle : 7
        return [
            (simple_snmp_oid((1, 3, 6, 1, 4, 1, 318, 1, 1, 12, 3, 3, 1, 1, 4, self.cdc.parameter_i1), target_value=1)),
        ]
    def off(self):
        # cdc ... controlling device connection
        return [
            (simple_snmp_oid((1, 3, 6, 1, 4, 1, 318, 1, 1, 12, 3, 3, 1, 1, 4, self.cdc.parameter_i1), target_value=2)),
        ]

_SNMP_SCHEME_LUT = {"apcv1" : apcv1_scheme}

class hc_command(object):
    def __init__(self, user_id, xml_struct, router_obj):
        hc_command.hc_id += 1
        self.cur_id = hc_command.hc_id
        cur_cd = cd_connection.objects.select_related("child", "parent").prefetch_related("parent__device_variable_set").get(Q(pk=xml_struct.get("cd_con")))
        self.cd_obj = cur_cd
        command = xml_struct.get("command")
        self.user = user.objects.get(Q(pk=user_id)) if user_id else None
        self.curl_base = self.cd_obj.parent.curl.split(":")[0]
        self.log("got command %s for %s (curl is '%s', target: %s)" % (
            command,
            unicode(cur_cd.parent),
            cur_cd.parent.curl,
            unicode(cur_cd.child)))
        # better use subclasses, FIXME
        var_list = {
            "ipmi" : [
                ("IPMI_USERNAME", "admin"),
                ("IPMI_PASSWORD", "admin"),
                ("IPMI_INTERFACE", ""),
                ],
            "ilo4" : [
                ("ILO_USERNAME", "Administrator"),
                ("ILO_PASSWORD", "passwd"),
                ],
            "snmp" : [
                ("SNMP_SCHEME", None),
                ("SNMP_VERSION", 2),
                ("SNMP_WRITE_COMMUNITY", "private"),
                ],
            }.get(self.curl_base, [])
        var_dict = dict([(key, self.get_var(key, def_val)) for key, def_val in var_list])
        for key in sorted(var_dict):
            self.log(" var %-20s : %s" % (
                key,
                str(var_dict[key])))
        com_ip = self.get_ip_to_host(self.cd_obj.parent, router_obj)
        if not com_ip:
            self.log("cannot reach device %s" % (unicode(self.cd_obj.parent)),
                     logging_tools.LOG_LEVEL_ERROR,
                     dev=cur_cd.child)
        else:
            if self.curl_base in ["ipmi"]:
                com_str = self._build_com_str(var_dict, com_ip, command)
                self.log("com_str is '%s'" % (com_str))
                self.log("sending com_str to '%s'" % (unicode(self.cd_obj.parent)), dev=self.cd_obj.child)
                simple_command(com_str,
                               short_info="True",
                               done_func=self.hc_done,
                               log_com=self.log,
                               info="hard_control")
            elif self.curl_base in ["snmp"]:
                if not var_dict["SNMP_SCHEME"]:
                    self.log("no SNMP_SCHEME defined for '%s'" % (unicode(self.cd_obj.parent)), logging_tools.LOG_LEVEL_ERROR, dev=self.cd_obj.child)
                elif var_dict["SNMP_SCHEME"] not in _SNMP_SCHEME_LUT:
                    self.log("SNMP_SCHEME '%s' not found for '%s' (%s)" % (
                        var_dict["SNMP_SCHEME"],
                        unicode(self.cd_obj.parent),
                        ", ".join(sorted(_SNMP_SCHEME_LUT.keys())),
                        ), logging_tools.LOG_LEVEL_ERROR, dev=self.cd_obj.child)
                else:
                    self.log("sending command '%s' (scheme %s) to %s" % (
                        command,
                        var_dict["SNMP_SCHEME"],
                        unicode(self.cd_obj.parent)), dev=self.cd_obj.child)
                    cur_scheme = _SNMP_SCHEME_LUT[var_dict["SNMP_SCHEME"]](self.cd_obj)
                    hc_command.register(self)
                    # snmp_ver, snmp_host, snmp_community, self.envelope, self.transform_single_key, self.__timeout
                    self.process.send_pool_message(
                        int(var_dict["SNMP_VERSION"]),
                        com_ip,
                        var_dict["SNMP_WRITE_COMMUNITY"],
                        self.cur_id,
                        False,
                        10,
                        cur_scheme.set_command(command),
                        target="snmp_process",
                    )
            else:
                self.log("cannot handle curl_base '%s' for %s" % (
                    self.curl_base,
                    unicode(self.cd_obj.parent),
                ), logging_tools.LOG_LEVEL_CRITICAL, dev=self.cd_obj.child)
    def _build_com_str(self, var_dict, com_ip, command):
        if self.curl_base == "ipmi":
            com_str = "%s %s -H %s -U %s -P %s chassis power %s" % (
                process_tools.find_file("ipmitool"),
                # add ipmi interface if defined
                "-I %s" % (var_dict["IPMI_INTERFACE"]) if var_dict.get("IPMI_INTERFACE", "") else "",
                com_ip,
                var_dict["IPMI_USERNAME"],
                var_dict["IPMI_PASSWORD"],
                {"on"    : "on",
                 "off"   : "off",
                 "cycle" : "cycle"}.get(command, "status")
            )
        # ilo4 is no longer supported, use ipmi with IPMI_INTERFACE=lanplus
        # elif self.curl_base == "ilo4":
        #    com_str = "%s -I lanplus -H %s -U %s -P %s chassis power %s" % (
        #        process_tools.find_file("ipmitool"),
        #        com_ip,
        #        var_dict["ILO_USERNAME"],
        #        var_dict["ILO_PASSWORD"],
        #        {"on"    : "on",
        #         "off"   : "off",
        #         "cycle" : "cycle"}.get(command, "status")
        #    )
        return com_str
    def hc_done(self, hc_sc):
        cur_out = hc_sc.read()
        self.log("hc_com finished with stat %d (%d bytes)" % (
            hc_sc.result,
            len(cur_out)))
        for line_num, line in enumerate(cur_out.split("\n")):
            if line.strip():
                self.log(" %3d %s" % (line_num + 1, line), logging_tools.LOG_LEVEL_ERROR if hc_sc.result else logging_tools.LOG_LEVEL_OK, dev=self.cd_obj.child)
        hc_sc.terminate()
    def get_var(self, var_name, default_val=None):
        try:
            cur_var = self.cd_obj.parent.device_variable_set.get(Q(name=var_name))
        except device_variable.DoesNotExist:
            try:
                cur_var = self.cd_obj.parent.device_group.device.device_variable_set.get(Q(name=var_name))
            except device_variable.DoesNotExist:
                try:
                    cur_var = device_variable.objects.get(Q(device__device_group__cluster_device_group=True) & Q(name=var_name))
                except device_variable.DoesNotExist:
                    var_value = default_val
                    cur_var = None
        if cur_var:
            var_value = cur_var.value
        return var_value
    def get_ip_to_host(self, dev_struct, router_obj):
        all_paths = sorted(
            router_obj.get_ndl_ndl_pathes(
                hc_command.process.sc.netdevice_idx_list,
                list(dev_struct.netdevice_set.all().values_list("pk", flat=True)),
                only_endpoints=True,
                add_penalty=True,
            )
        )
        com_ip = None
        if all_paths:
            ip_list = netdevice.objects.get(Q(pk=all_paths[0][2])).net_ip_set.all().values_list("ip", flat=True)
            if ip_list:
                com_ip = ip_list[0]
        return com_ip
    def snmp_finished(self, *args):
        hc_command.unregister(self)
    @staticmethod
    def g_log(what, log_level=logging_tools.LOG_LEVEL_OK):
        hc_command.process.log("[hc] %s" % (what), log_level)
    @staticmethod
    def register(cur_hc):
        hc_command.g_log("registered %d" % (cur_hc.cur_id))
        hc_command.hc_lut[cur_hc.cur_id] = cur_hc
    @staticmethod
    def unregister(cur_hc):
        hc_command.g_log("unregistered %d" % (cur_hc.cur_id))
        del hc_command.hc_lut[cur_hc.cur_id]
    @staticmethod
    def setup(proc):
        hc_command.process = proc
        hc_command.hc_lut = {}
        hc_command.g_log("init hc_command")
        hc_command.hc_id = 0
    @staticmethod
    def feed_snmp_result(*args):
        if args[0] in hc_command.hc_lut:
            hc_command.hc_lut[args[0]].snmp_finished(*args)
        else:
            hc_command.g_log("unknown id '%s' for snmp_result (%s)" % (
                args[0],
                str(args),
                ), logging_tools.LOG_LEVEL_ERROR)
    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK, dev=None):
        hc_command.process.log("[hc] %s" % (what), log_level)
        if dev is not None:
            devicelog.new_log(
                dev,
                global_config["LOG_SOURCE_IDX"],
                log_level,
                "[hc] %s" % (what),
                user=self.user,
            )

class external_command_process(threading_tools.process_obj):
    def process_init(self):
        self.__log_template = logging_tools.get_logger(
            global_config["LOG_NAME"],
            global_config["LOG_DESTINATION"],
            zmq=True,
            context=self.zmq_context,
            init_logger=True)
        # close database connection
        connection.close()
        simple_command.setup(self)
        self.router_obj = config_tools.router_object(self.log)
        self.sc = config_tools.server_check(server_type="mother")
        if "b" in self.sc.identifier_ip_lut:
            self.__kernel_ip = self.sc.identifier_ip_lut["b"][0].ip
            self.log("IP address in boot-net is %s" % (self.__kernel_ip))
        else:
            self.__kernel_ip = None
            self.log("no IP address in boot-net", logging_tools.LOG_LEVEL_ERROR)
        self.register_func("delay_command", self._delay_command)
        self.register_func("hard_control", self._hard_control)
        self.register_func("snmp_finished", self._snmp_finished)
        self.register_timer(self._check_commands, 10)
        hc_command.setup(self)
        self.send_pool_message("register_return", "command", target="snmp_process")
    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__log_template.log(log_level, what)
    def loop_post(self):
        self.__log_template.close()
    def _delay_command(self, *args, **kwargs):
        if simple_command.idle():
            self.register_timer(self._check_commands, 1)
        _new_sc = simple_command(args[0], delay_time=kwargs.get("delay_time", 0))
    def _server_com(self, s_com):
        dst_call = {"alter_macadr"  : self._adw_macaddr,
                    "delete_macadr" : self._adw_macaddr,
                    "write_macadr"  : self._adw_macaddr,
                    "syslog_line"   : self._syslog_line}.get(s_com.get_command(), None)
        if dst_call:
            dst_call(s_com.get_command(), s_com)
        else:
            self.log("Unknown server_message_command: %s" % (s_com.get_command()), logging_tools.LOG_LEVEL_ERROR)
        if s_com.get_option_dict().has_key("SIGNAL_MAIN_THREAD"):
            self.send_pool_message(s_com.get_option_dict()["SIGNAL_MAIN_THREAD"])
    def _check_commands(self):
        simple_command.check()
        if simple_command.idle():
            self.unregister_timer(self._check_commands)
    def _hard_control(self, zmq_id, in_com, *args, **kwargs):
        if simple_command.idle():
            self.register_timer(self._check_commands, 1)
        in_com = server_command.srv_command(source=in_com)
        self.router_obj.check_for_update()
        for cur_dev in in_com.xpath(".//ns:device", smart_strings=False):
            hc_command(in_com.get("user_id", None), cur_dev, self.router_obj)
    def sc_finished(self, sc_com):
        self.log("simple command done")
        print sc_com.read()
    def _snmp_finished(self, *args, **kwargs):
        hc_command.feed_snmp_result(*args)
