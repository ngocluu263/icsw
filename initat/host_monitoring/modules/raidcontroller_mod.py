#!/usr/bin/python-init -Ot
#
# Copyright (C) 2001-2008,2012-2014 Andreas Lang-Nevyjel, init.at
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
""" checks for various RAID controllers """

import base64
import bz2
import commands
import datetime
import logging_tools
import marshal
import os
import pprint
import re
import server_command
import stat
import sys
import time
from initat.host_monitoring import limits, hm_classes

TW_EXEC = "/sbin/tw_cli"
ARCCONF_BIN = "/usr/sbin/arcconf"

SAS_OK_KEYS = {
    "adp"  : set(),
    "virt" : set(
        ["virtual_drive", "raid_level", "name", "size", "state", "strip_size",
         "number_of_drives", "ongoing_progresses", "current_cache_policy",
         ]),
    "pd"   : set(
        ["slot_number", "pd_type", "raw_size", "firmware_state"
         ])
}
# for which keys do we read the following line
SAS_CONT_KEYS = set(["ongoing_progresses"])

def get_size(in_str):
    try:
        s_p, p_p = in_str.split()
        return float(s_p) * {
            "k" : 1000,
            "m" : 1000 * 1000,
            "g" : 1000 * 1000 * 1000,
            "t" : 1000 * 1000 * 1000 * 1000}.get(p_p[0].lower(), 1)
    except:
        return 0

def _split_config_line(line):
    key, val = line.split(":", 1)
    key = key.lower().strip().replace(" ", "_")
    val = val.strip()
    if val.isdigit():
        val = int(val)
    elif val.lower() == "enabled":
        val = True
    elif val.lower() == "disabled":
        val = False
    return key, val

class dummy_mod(object):
    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        print "[%d] %s" % (log_level, what)

class ctrl_type(object):
    _all_types = None
    def __init__(self, module_struct, **kwargs):
        self.name = self.Meta.name
        # last scan date
        self.scanned = None
        # last check date
        self.checked = None
        self._dict = {}
        self._module = module_struct
        self._check_exec = None
        if not kwargs.get("quiet", False):
            self.log("init")
    @staticmethod
    def init(module_struct):
        ctrl_type._all_types = {}
        for ctrl_struct in [glob_struct for glob_struct in globals().itervalues() if type(glob_struct) == type and issubclass(glob_struct, ctrl_type) and not glob_struct == ctrl_type]:
            ctrl_type._all_types[ctrl_struct.Meta.name] = ctrl_struct(module_struct)
        # for sub_class in globals()#
        # for type_name, exec_name in
    @staticmethod
    def update(c_type, ctrl_ids=[]):
        if c_type is None:
            c_type = ctrl_type._all_types.keys()
        elif type(c_type) != list:
            c_type = [c_type]
        for cur_type in c_type:
            ctrl_type._all_types[cur_type]._update(ctrl_ids)
    @staticmethod
    def ctrl(key):
        if ctrl_type._all_types:
            return ctrl_type._all_types[key]
        else:
            return globals()["ctrl_type_%s" % (key)](dummy_mod(), quiet=True)
    def exec_command(self, com_line, **kwargs):
        if com_line.startswith(" "):
            com_line = "%s%s" % (self._check_exec, com_line)
        cur_stat, cur_out = commands.getstatusoutput(com_line)
        lines = cur_out.split("\n")
        if cur_stat:
            self.log("%s gave %d:" % (com_line, cur_stat), logging_tools.LOG_LEVEL_ERROR)
            for line_num, cur_line in enumerate(lines):
                self.log("  %3d %s" % (line_num + 1, cur_line), logging_tools.LOG_LEVEL_ERROR)
        if "post" in kwargs:
            lines = [getattr(cur_line, kwargs["post"])() for cur_line in lines]
        if kwargs.get("super_strip", False):
            lines = [" ".join(line.strip().split()) for line in lines]
        if not kwargs.get("empty_ok", False):
            lines = [cur_line for cur_line in lines if cur_line.strip()]
        # print cur_stat, lines
        return cur_stat, lines
    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self._module.log("[ct %s] %s" % (self.name, what), log_level)
    def _scan(self):
        self.scanned = time.time()
        self.log("scanning for %s controller" % (self.name))
        self.check_for_exec()
        if self._check_exec:
            self.log("scanning for %s" % (self.Meta.description))
            self.scan_ctrl()
    def _update(self, ctrl_ids):
        if not self.scanned:
            self._scan()
        self.update_ctrl(ctrl_ids)
    def check_for_exec(self):
        if self._check_exec is None:
            for s_path in ["/sbin", "/usr/sbin", "/bin", "/usr/bin"]:
                cur_path = os.path.join(s_path, self.Meta.exec_name)
                if os.path.isfile(cur_path):
                    self._check_exec = cur_path
                    break
        if self._check_exec:
            self.log("found check binary at '%s'" % (self._check_exec))
        else:
            self.log("no check binary '%s' found" % (self.Meta.exec_name),
                     logging_tools.LOG_LEVEL_ERROR)
    def controller_list(self):
        return self._dict.keys()
    def scan_ctrl(self):
        # override to scan for controllers
        pass
    def update_ctrl(self, *args):
        # override to update controllers, args optional
        pass
    def update_ok(self, srv_com):
        # return True if update is OK, can be overridden to add more checks (maybe arguments)
        if self._check_exec:
            return True
        else:
            srv_com["result"].attrib.update({"reply" : "monitoring tool '%s' missing" % (self.Meta.exec_name),
                                             "state" : "%d" % (server_command.SRV_REPLY_STATE_ERROR)})
            return False

class ctrl_check_struct(hm_classes.subprocess_struct):
    class Meta:
        verbose = True
        id_str = "raid_ctrl"
    def __init__(self, log_com, srv_com, ct_struct, ctrl_list=[]):
        self.__log_com = log_com
        self.__ct_struct = ct_struct
        hm_classes.subprocess_struct.__init__(self, srv_com, ct_struct.get_exec_list(ctrl_list))
    def process(self):
        self.__ct_struct.process(self)
    def started(self):
        if hasattr(self.__ct_struct, "started"):
            self.__ct_struct.started(self)
            self.send_return()
    def log(self, what, level=logging_tools.LOG_LEVEL_OK):
        self.__log_com("[ccs] %s" % (what), level)

class ctrl_type_lsi(ctrl_type):
    class Meta:
        name = "lsi"
        exec_name = "cfggen"
        description = "LSI 1030 RAID Controller"
    def get_exec_list(self, ctrl_list=[]):
        if ctrl_list == []:
            ctrl_list = self._dict.keys()
        return ["%s %s DISPLAY" % (self._check_exec, ctrl_id[3:]) for ctrl_id in ctrl_list]
    def scan_ctrl(self):
        cur_stat, cur_lines = self.exec_command(" LIST", super_strip=True)
        if not cur_stat:
            c_ids = set()
            for line in cur_lines:
                if line.split()[0].isdigit():
                    c_ids.add("ioc%s" % (line.split()[0]))
            self._dict = dict([(key, {}) for key in c_ids])
    def update_ctrl(self, ctrl_ids):
        pass
        # print ctrl_ids
    def process(self, ccs):
        ctrl_id = "ioc%s" % (ccs.run_info["command"].split()[1])
        ctrl_dict = self._dict[ctrl_id]
        cur_mode = None
        # pacify checker
        vol_dict, phys_dict = ({}, {})
        to_int = set(["device", "function", "maximum_physical_devices", "size", "slot", "enclosure"])
        for line in ccs.read().split("\n"):
            if line.strip():
                space_line = line[0] == " "
                if line.count("information") and not space_line:
                    cur_mode = {
                        "con" : "c",
                        "ir " : "v",
                        "phy" : "p",
                        "enc" : "e"}.get(line.lower()[0:3], None)
                elif line.startswith("---"):
                    pass
                else:
                    if cur_mode:
                        if space_line:
                            # print cur_mode, "s", line
                            if line.count(":"):
                                key, value = line.strip().split(":", 1)
                                key = (" ".join(key.strip().lower().split("(")[0].split()))
                                if key.endswith("#"):
                                    key = key[:-1].strip()
                                key = key.replace(" ", "_")
                                value = value.strip()
                                if key in to_int or key.endswith("_id"):
                                    try:
                                        value = int(value.split("/")[0])
                                    except:
                                        pass
                                if cur_mode == "c":
                                    ctrl_dict[key] = value
                                elif cur_mode == "v":
                                    vol_dict[key] = value
                                elif cur_mode == "p":
                                    phys_dict[key] = value
                        else:
                            # print cur_mode, line
                            if cur_mode == "v":
                                vol_dict = {}
                                ctrl_dict.setdefault("volumes", {})[line.split()[-1]] = vol_dict
                            if cur_mode == "p":
                                phys_dict = {}
                                if "volumes" in ctrl_dict:
                                    vol_dict.setdefault("disks", {})[line.split()[-1].replace("#", "")] = phys_dict
        ccs.srv_com["result:ctrls"] = self._dict
        return
        # code mpt-status, not used any more
        ctrl_re = re.compile("^(?P<c_name>\S+) vol_id (?P<vol_id>\d+) type (?P<c_type>\S+), (?P<num_discs>\d+) phy, (?P<size>\S+) (?P<size_pfix>\S+), state (?P<state>\S+), flags (?P<flags>\S+)")
        disk_re = re.compile("^(?P<c_name>\S+) phy (?P<phy_id>\d+) scsi_id (?P<scsi_id>\d+) (?P<disk_info>.*), (?P<size>\S+) (?P<size_pfix>\S+), state (?P<state>\S+), flags (?P<flags>\S+)$")
        to_int = ["num_discs", "vol_id", "phy_id", "scsi_id"]
        to_float = ["size"]
        for line in ccs.read().split("\n"):
            if line.strip():
                line = " ".join(line.split())
                for re_type, cur_re in [("c", ctrl_re), ("d", disk_re)]:
                    cur_m = cur_re.match(line)
                    if cur_m:
                        break
                if cur_m:
                    cur_dict = cur_m.groupdict()
                    for key, value in cur_dict.iteritems():
                        if key in to_int:
                            cur_dict[key] = int(value)
                        elif key in to_float:
                            cur_dict[key] = float(value)
                    if re_type == "c":
                        self._dict[cur_dict["c_name"]] = cur_dict
                        self._dict[cur_dict["c_name"]]["disks"] = []
                    elif cur_m:
                        self._dict[cur_dict["c_name"]]["disks"].append(cur_dict)
        ccs.srv_com["result:ctrls"] = self._dict
    def _interpret(self, in_dict, cur_ns):
        if "ctrls" in in_dict and in_dict["ctrls"]:
            ret_state = limits.nag_STATE_OK
            c_array = []
            for c_name in sorted(in_dict["ctrls"]):
                ctrl_dict = in_dict["ctrls"][c_name]
                vol_list = []
                for vol_key in sorted(ctrl_dict.get("volumes", {})):
                    vol_dict = ctrl_dict["volumes"][vol_key]
                    vol_stat = vol_dict["status_of_volume"].split()[0]
                    vol_list.append("vol%s, RAID%s, %s, %s" % (
                        vol_key,
                        vol_dict["raid_level"],
                        logging_tools.get_size_str(vol_dict["size"] * 1024 * 1024),
                        vol_stat)
                                    )
                    if vol_stat.lower() != "okay":
                        ret_state = max(ret_state, limits.nag_STATE_CRITICAL)
                c_array.append("%s (%s%s)%s" % (
                    c_name,
                    ctrl_dict["controller_type"],
                    ", %s" % (logging_tools.get_plural("volume", len(ctrl_dict.get("volumes", {})))) if vol_list else "",
                    ": %s" % (", ".join(vol_list)) if vol_list else "",
                ))
            return ret_state, "; ".join(c_array)
        else:
            return limits.nag_STATE_WARNING, "no controller found"

class ctrl_type_tw(ctrl_type):
    class Meta:
        name = "tw"
        exec_name = "tw_cli"
        description = "Threeware RAID Controller"
    def get_exec_list(self, ctrl_list=[]):
        if ctrl_list == []:
            ctrl_list = self._dict.keys()
        return ["%s info %s" % (self._check_exec, ctrl_id) for ctrl_id in ctrl_list]
    def scan_ctrl(self):
        cur_stat, cur_lines = self.exec_command(" info", post="strip")
        if not cur_stat:
            mode = None
            for line in cur_lines:
                # print "*", line
                line_p = line.split()
                if mode is None:
                    if line_p[0].lower() == "list":
                        # old mode
                        mode = 1
                    elif line_p[0].lower() == "ctl":
                        # new mode
                        mode = 2
                elif mode:
                    if line_p[0].lower().startswith("controller") and mode == 1:
                        if ("%s %s" % (line_p[2], line_p[3])).lower() == "not compatible.":
                            self._dict["c%d" % (int(line_p[1][:-1]))] = {"type" : "not compatible",
                                                                         "info" : "error not compatible"}
                        else:
                            self._dict["c%d" % (int(line_p[1][:-1]))] = {"type"  : line_p[2]}
                    elif line_p[0].startswith("c") and mode == 2:
                        self._dict[line_p[0]] = {"type" : line_p[1]}
    def update_ctrl(self, ctrl_ids):
        pass
        # print ctrl_ids
    def update_ok(self, srv_com):
        if self._dict:
            return ctrl_type.update_ok(self, srv_com)
        else:
            srv_com["result"].attrib.update({
                    "reply" : "no controller found",
                    "state" : "%d" % (server_command.SRV_REPLY_STATE_ERROR)})
            return False
    def process(self, ccs):
        unit_match = re.compile("^\s+Unit\s*(?P<num>\d+):\s*(?P<raid>.*)\s+(?P<size>\S+\s+\S+)\s+\(\s*(?P<blocks>\d+)\s+\S+\):\s*(?P<status>.*)$")
        port_match = re.compile("^\s+Port\s*(?P<num>\d+):\s*(?P<info>[^:]+):\s*(?P<status>.*)\(unit\s*(?P<unit>\d+)\)$")
        u2_0_match = re.compile("^u(?P<num>\d+)\s+(?P<raid>\S+)\s+(?P<status>\S+)\s+(?P<cmpl>\S+)\s+(?P<stripe>\S+)\s+(?P<size>\S+)\s+(?P<cache>\S+)\s+.*$")
        u2_1_match = re.compile("^u(?P<num>\d+)\s+(?P<raid>\S+)\s+(?P<status>\S+)\s+(?P<rcmpl>\S+)\s+(?P<cmpl>\S+)\s+(?P<stripe>\S+)\s+(?P<size>\S+)\s+(?P<cache>\S+)\s+(?P<avrfy>\S+)$")
        p2_match = re.compile("^p(?P<num>\d+)\s+(?P<status>\S+)\s+u(?P<unit>\d+)\s+(?P<size>\S+\s+\S+)\s+(?P<blocks>\d+)\s+.*$")
        bbu_match = re.compile("^bbu\s+(?P<onlinestate>\S+)\s+(?P<ready>\S+)\s+(?P<status>\S+)\s+(?P<volt>\S+)\s+(?P<temp>\S+)\s+.*$")
        com_line, com_type, ctrl_id = ccs.run_info["command"].strip().split()
        if com_type == "info":
            ctrl_result = {
                "type"  : self._dict[ctrl_id]["type"],
                "units" : {},
                "ports" : {}}
            if ccs.run_info["result"]:
                ctrl_result["error"] = "%s gave %d" % (ccs.run_info["comline"], ccs.run_info["result"])
            else:
                ctrl_result["error"] = "ok"
                lines = [line.strip() for line in ccs.read().split("\n") if line.strip()]
                num_units, num_ports = (0, 0)
                l_mode = "c"
                if lines:
                    if lines[0].lower().strip().startswith("unit"):
                        # new format
                        if lines[0].lower().count("rcmpl"):
                            # new tw_cli
                            u2_match = u2_1_match
                        else:
                            # old tw_cli
                            u2_match = u2_0_match
                        for line in lines:
                            um = u2_match.match(line)
                            pm = p2_match.match(line)
                            bm = bbu_match.match(line)
                            if um:
                                ctrl_result["units"][um.group("num")] = {
                                    "raid"   : um.group("raid").strip(),
                                    "size"   : "%s GB" % (um.group("size").strip()),
                                    "ports"  : [],
                                    "status" : um.group("status").strip(),
                                    "cmpl"   : um.group("cmpl")}
                            elif pm:
                                ctrl_result["ports"][pm.group("num")] = {
                                    "status" : pm.group("status").strip(),
                                    "unit"   : pm.group("unit")}
                                if ctrl_result["units"].has_key(pm.group("unit")):
                                    ctrl_result["units"][pm.group("unit")]["ports"].append(pm.group("num"))
                            elif bm:
                                ctrl_result["bbu"] = dict([(key, bm.group(key)) for key in [
                                    "onlinestate",
                                    "ready",
                                    "status",
                                    "volt",
                                    "temp"]])
                    else:
                        for line in lines:
                            if line.startswith("# of unit"):
                                uc_m = re.match("^# of units\s*:\s*(\d+).*$", line)
                                if uc_m:
                                    num_units = uc_m.group(1)
                                l_mode = "u"
                            elif line.startswith("# of port"):
                                l_mode = "p"
                                pc_m = re.match("^# of ports\s*:\s*(\d+).*$", line)
                                if num_units and pc_m:
                                    num_ports = pc_m.group(1)
                            elif l_mode == "u":
                                um = unit_match.match(line)
                                if um:
                                    cmpl_str, stat_str = ("???",
                                                          um.group("status").strip())
                                    if stat_str.lower().startswith("rebuil"):
                                        # try to exctract rebuild_percentage
                                        pc_m = re.match("^(?P<stat>\S+)\s+\((?P<perc>\d+)%\)$", stat_str)
                                        if pc_m:
                                            stat_str = pc_m.group("stat")
                                            cmpl_str = pc_m.group("perc")
                                    ctrl_result["units"][um.group("num")] = {
                                        "raid"   : um.group("raid").strip(),
                                        "size"   : um.group("size").strip(),
                                        "blocks" : um.group("blocks").strip(),
                                        "ports"  : [],
                                        "status" : stat_str,
                                        "cmpl"   : cmpl_str}
                            elif l_mode == "p":
                                pm = port_match.match(line)
                                if pm:
                                    ctrl_result["ports"][pm.group("num")] = {"info"   : pm.group("info").strip(),
                                                                             "status" : pm.group("status").strip()}
                                    if ctrl_result["units"].has_key(pm.group("unit")):
                                        ctrl_result["units"][pm.group("unit")]["ports"].append(pm.group("num"))
            ccs.srv_com["result:ctrl_%s" % (ctrl_id)] = ctrl_result
        else:
            pass
# #    def server_call(self, cm):
# #        ret_str = self.module_info.check_exec()
# #        if ret_str.startswith("ok"):
# #            ret_str = self.module_info.update_ctrl_dict()
# #            if ret_str.startswith("ok"):
# #                if cm:
# #                    ctrl_list = [x for x in cm if x in self.module_info.ctrl_dict.keys()]
# #                else:
# #                    ctrl_list = self.module_info.ctrl_dict.keys()
# #                ret_dict = {}
# #                for ctrl_id in ctrl_list:
# #                    ret_dict[ctrl_id] = self.module_info.check_controller(ctrl_id)
# #                ret_str = "ok %s" % (hm_classes.sys_to_net(ret_dict))
# #        return ret_str
    def _interpret(self, tw_dict, cur_ns):
        # if tw_dict.has_key("units"):
        #    tw_dict = {parsed_coms[0] : tw_dict}
        num_warn, num_error = (0, 0)
        ret_list = []
        if tw_dict:
            for ctrl, ctrl_dict in tw_dict.iteritems():
                info = ctrl_dict.get("info", "")
                if info.startswith("error"):
                    num_error += 1
                    ret_list.append("%s (%s): %s " % (ctrl, ctrl_dict.get("type", "???"), info))
                else:
                    num_units, num_ports = (len(ctrl_dict["units"]), len(ctrl_dict["ports"]))
                    unit_info, port_info = ([], [])
                    # check units
                    for u_num, u_stuff in ctrl_dict["units"].iteritems():
                        l_status = u_stuff["status"].lower()
                        if l_status in ["degraded"]:
                            num_error += 1
                        elif l_status != "ok":
                            num_warn += 1
                        if u_stuff["raid"].lower() in ["jbod"]:
                            num_error += 1
                        unit_info.append("unit %s (%s, %s, %s): %s%s" % (u_num,
                                                                         u_stuff["raid"],
                                                                         u_stuff["size"],
                                                                         "/".join(u_stuff["ports"]),
                                                                         u_stuff["status"],
                                                                         (l_status.startswith("verify") or l_status.startswith("initia") or l_status.startswith("rebuild")) and " (%s %%)" % (u_stuff.get("cmpl", "???")) or ""))
                    for p_num, p_stuff in ctrl_dict["ports"].iteritems():
                        if p_stuff["status"].lower() != "ok":
                            num_error += 1
                            port_info.append("port %s (u%s): %s" % (p_num, p_stuff.get("unit", "???"), p_stuff["status"]))
                    if ctrl_dict.has_key("bbu"):
                        bbu_errors, bbu_ok = ([], 0)
                        for key in sorted(ctrl_dict["bbu"].iterkeys()):
                            value = ctrl_dict["bbu"][key]
                            if value.lower() not in ["on", "ok", "yes"]:
                                bbu_errors.append((key, value))
                                num_error += 1
                            else:
                                bbu_ok += 1
                        bbu_str = "%s ok" % (logging_tools.get_plural("attribute", bbu_ok))
                        if bbu_errors:
                            bbu_str = "%s, %s" % ("; ".join(["error %s: %s" % (key, value) for key, value in bbu_errors]), bbu_str)
                    else:
                        bbu_str = ""
                    ret_list.append("%s (%s) %du/%dp: %s%s%s" % (ctrl,
                                                                 ctrl_dict.get("type", "???"),
                                                                 num_units,
                                                                 num_ports,
                                                                 ",".join(unit_info),
                                                                 port_info and "; %s" % (",".join(port_info)) or "",
                                                                 ", BBU: %s" % (bbu_str) if bbu_str else ""))
        else:
            ret_list.append("no controller found")
            num_error = 1
        if num_error:
            ret_state = limits.nag_STATE_CRITICAL
        elif num_warn:
            ret_state = limits.nag_STATE_WARNING
        else:
            ret_state = limits.nag_STATE_OK
        return ret_state, ", ".join(ret_list)

class ctrl_type_ips(ctrl_type):
    class Meta:
        name = "ips"
        exec_name = "arcconf"
        description = "Adapatec AAC RAID Controller"
    def get_exec_list(self, ctrl_ids=[]):
        ctrl_ids = ctrl_ids or self._dict.keys()
        return [("%s getconfig %d AL" % (self._check_exec, ctrl_id),
                 "config", ctrl_id) for ctrl_id in ctrl_ids] + \
               [("%s getstatus %d" % (self._check_exec, ctrl_id),
                 "status", ctrl_id) for ctrl_id in ctrl_ids]
    def scan_ctrl(self):
        cur_stat, cur_lines = self.exec_command(" getversion", post="strip")
        if not cur_stat:
            num_ctrl = len([True for line in cur_lines if line.lower().count("controller #")])
            if num_ctrl:
                for ctrl_num in range(1, num_ctrl + 1):
                    ctrl_stuff = {"last_al_lines" : []}
                    # get config for every controller
                    c_stat, c_result = self.exec_command(" getconfig %d AD" % (ctrl_num))
                    ctrl_stuff["config"] = {}
                    for key, val in [_split_config_line(line) for line in c_result if line.count(":")]:
                        ctrl_stuff["config"][key] = val
                    self._dict[ctrl_num] = ctrl_stuff
    def update_ok(self, srv_com):
        if self._dict:
            return ctrl_type.update_ok(self, srv_com)
        else:
            srv_com["result"].attrib.update({"reply" : "no controller found",
                                             "state" : "%d" % (server_command.SRV_REPLY_STATE_ERROR)})
            return False
    def process(self, ccs):
        com_line, com_type, ctrl_num = ccs.run_info["command"]
        if com_type == "config":
            ctrl_config = {"logical"    : {},
                           "array"      : {},
                           "channel"    : {},
                           "physical"   : [],
                           "controller" : {}}
            act_part, prev_line = ("", "")
            for line in ccs.read().split("\n"):
                ls = line.strip()
                lsl = ls.lower()
                # get key and value, space is important here
                if lsl.count(" :"):
                    key, value = [entry.strip() for entry in lsl.split(" :", 1)]
                else:
                    key, value = (None, None)
                if prev_line.startswith("-" * 10) and line.endswith("information"):
                    act_part = " ".join(line.split()[0:2]).lower().replace(" ", "_").replace("drive", "device")
                elif line.lower().startswith("command complet") or line.startswith("-" * 10):
                    pass
                else:
                    if act_part == "logical_device":
                        if line.lower().count("logical device number") or line.lower().count("logical drive number"):
                            act_log_drv_num = int(line.split()[-1])
                            ctrl_config["logical"][act_log_drv_num] = {}
                        elif line.lower().strip().startswith("logical device name"):
                            array_name = ls.split()[1]
                            ctrl_config["array"][array_name] = " ".join(line.lower().strip().split()[2:])
                        elif line.count(":"):
                            key, val = _split_config_line(line)
                            ctrl_config["logical"][act_log_drv_num][key] = val
                    elif act_part == "physical_device":
                        if lsl.startswith("channel #"):
                            act_channel_num = int(lsl[-2])
                            ctrl_config["channel"][act_channel_num] = {}
                            act_scsi_stuff = None
                        elif lsl.startswith("device #"):
                            act_scsi_id = int(lsl[-1])
                            act_channel_num = -1
                            act_scsi_stuff = {}
                        elif lsl.startswith("reported channel,device"):
                            # key should be set here
                            if key.endswith(")"):
                                key, value = (key.split("(", 1)[0],
                                              value.split("(", 1)[0])
                            act_scsi_id = int(value.split(",")[-1])
                            if act_channel_num == -1:
                                act_channel_num = int(value.split(",")[-2].split()[-1])
                                ctrl_config["channel"][act_channel_num] = {}
                            ctrl_config["channel"][act_channel_num][act_scsi_id] = key
                            act_scsi_stuff["channel"] = act_channel_num
                            act_scsi_stuff["scsi_id"] = act_scsi_id
                            ctrl_config["channel"][act_channel_num][act_scsi_id] = act_scsi_stuff
                            ctrl_config["physical"].append(act_scsi_stuff)
                        elif line.count(":"):
                            if act_scsi_stuff is not None:
                                key, val = _split_config_line(line)
                                act_scsi_stuff[key] = val
                    elif act_part == "controller_information":
                        if key:
                            ctrl_config["controller"][key] = value
                    # print act_part, linea
                prev_line = line
            self._dict[ctrl_num].update(ctrl_config)
        elif com_type == "status":
            task_list = []
            act_task = None
            for line in ccs.read().split("\n"):
                lline = line.lower()
                if lline.startswith("logical device task"):
                    act_task = {"header" : lline}
                elif act_task:
                    if lline.count(":"):
                        key, value = [part.strip().lower() for part in lline.split(":", 1)]
                        act_task[key] = value
                if not lline.strip():
                    if act_task:
                        task_list.append(act_task)
                        act_task = None
            self._dict[ctrl_num]["config"]["task_list"] = task_list
        if ctrl_num == max(self._dict.keys()) and com_type == "status":
            ccs.srv_com["ips_dict_base64"] = base64.b64encode(bz2.compress(marshal.dumps(self._dict)))
    def _interpret(self, aac_dict, cur_ns):
        num_warn, num_error = (0, 0)
        ret_f = []
        for c_num, c_stuff in aac_dict.iteritems():
            # pprint.pprint(c_stuff)
            act_field = []
            if c_stuff["logical"]:
                log_field = []
                for l_num, l_stuff in c_stuff["logical"].iteritems():
                    sold_name = "status_of_logical_device" if l_stuff.has_key("status_of_logical_device") else "status_of_logical_drive"
                    log_field.append("ld%d: %s (%s, %s)" % (l_num,
                                                            logging_tools.get_size_str(int(l_stuff["size"].split()[0]) * 1000000, divider=1000).strip(),
                                                            "RAID%s" % (l_stuff["raid_level"]) if l_stuff.has_key("raid_level") else "RAID?",
                                                            l_stuff[sold_name].lower()))
                    if l_stuff[sold_name].lower() in ["degraded"]:
                        num_error += 1
                    elif l_stuff[sold_name].lower() not in ["optimal", "okay"]:
                        num_warn += 1
                act_field.extend(log_field)
            if c_stuff["physical"]:
                phys_dict = {}
                for phys in c_stuff["physical"]:
                    if phys.has_key("size"):
                        s_state = phys["state"].lower()
                        if s_state == "sby":
                            # ignore empty standby bays
                            pass
                        else:
                            if s_state not in ["onl", "hsp", "optimal", "online"]:
                                num_error += 1
                            con_info = ""
                            if phys.has_key("reported_location"):
                                cd_info = phys["reported_location"].split(",")
                                if len(cd_info) == 2:
                                    try:
                                        con_info = "c%d.%d" % (int(cd_info[0].split()[-1]),
                                                               int(cd_info[1].split()[-1]))
                                    except:
                                        con_info = "error parsing con_info %s" % (phys["reported_location"])
                            phys_dict.setdefault(s_state, []).append("c%d/id%d%s" % (phys["channel"],
                                                                                     phys["scsi_id"],
                                                                                     " (%s)" % (con_info) if con_info else ""))
                act_field.extend(["%s: %s" % (key, ",".join(phys_dict[key])) for key in sorted(phys_dict.keys())])
            if "task_list" in c_stuff:
                for act_task in c_stuff["task_list"]:
                    act_field.append("%s on logical device %s: %s, %d %%" % (act_task.get("header", "unknown task"),
                                                                             act_task.get("logical device", "?"),
                                                                             act_task.get("current operation", "unknown op"),
                                                                             int(act_task.get("percentage complete", "0"))))
            # check controller warnings
            ctrl_field = []
            if c_stuff["controller"]:
                ctrl_dict = c_stuff["controller"]
                c_stat = ctrl_dict.get("controller status", "")
                if c_stat:
                    ctrl_field.append("status %s" % (c_stat))
                    if c_stat.lower() not in ["optimal", "okay"]:
                        num_error += 1
                ov_temp = ctrl_dict.get("over temperature", "")
                if ov_temp:
                    if ov_temp == "yes":
                        num_error += 1
                        ctrl_field.append("over temperature")
            ret_f.append("c%d (%s): %s" % (c_num,
                                           ", ".join(ctrl_field) or "---",
                                           ", ".join(act_field)))
            if num_error:
                ret_state = limits.nag_STATE_CRITICAL
            elif num_warn:
                ret_state = limits.nag_STATE_WARNING
            else:
                ret_state = limits.nag_STATE_OK
        if not ret_f:
            return limits.nag_STATE_WARNING, "no controller information found"
        else:
            return ret_state, "; ".join(ret_f)

class ctrl_type_megaraid_sas(ctrl_type):
    class Meta:
        name = "megaraid_sas"
        exec_name = "megarc"
        description = "MegaRAID SAS"
    def get_exec_list(self, ctrl_list=[]):
        if ctrl_list == []:
            ctrl_list = self._dict.keys()
        return [("%s -LdPdInfo -a%d" % (self._check_exec, ctrl_id), ctrl_id, "ld") for ctrl_id in ctrl_list] + \
               [("%s -AdpBbuCmd -GetBbuStatus -a%d" % (self._check_exec, ctrl_id), ctrl_id, "bbu") for ctrl_id in ctrl_list] + \
               [("%s -EncStatus -a%d" % (self._check_exec, ctrl_id), ctrl_id, "enc") for ctrl_id in ctrl_list]
    def scan_ctrl(self):
        cur_stat, cur_lines = self.exec_command(" -AdpAllInfo -aAll", post="strip")
        if not cur_stat:
            adp_check = False
            for line in cur_lines:
                if line.lower().startswith("adapter #"):
                    line_p = line.split()
                    ctrl_num = int(line_p[-1][1:])
                    self._dict[ctrl_num] = {
                        "info"          : " ".join(line_p),
                        "logical_lines" : {}}
                    self.log("Found Controller '%s' with ID %d" % (self._dict[ctrl_num]["info"],
                                                                   ctrl_num))
    def process(self, ccs):
        com_line, ctrl_id, run_type = ccs.run_info["command"]
        ctrl_stuff = self._dict[ctrl_id]
        if run_type == "ld":
            cur_mode, mode_sense, count_dict, cont_mode = (None, True, {}, False)
            log_drive_num = None
            for line in [cur_line.rstrip() for cur_line in ccs.read().split("\n")]:
                empty_line = not line.strip()
                parts = line.lower().strip().split()
                if empty_line:
                    mode_sense = True
                else:
                    if mode_sense == True:
                        if (parts[0], cur_mode) == ("adapter", None):
                            cur_mode = "adp"
                            count_dict = {
                                "adp"  : count_dict.get("adp", -1) + 1,
                                "virt" :-1,
                                "pd"   : 0}
                        elif (parts[0], cur_mode) in [("number", "adp"), ("virtual", "pd")]:
                            cur_mode = "virt"
                            count_dict[cur_mode] += 1
                            count_dict["pd"] = -1
                            cur_dict = {"lines": []}
                            ctrl_stuff.setdefault("virt", {})[count_dict["virt"]] = cur_dict
                        elif (parts[0], cur_mode) in [("is", "virt"), ("raw", "pd")]:
                            # continuation, no change
                            pass
                        elif (parts[0], cur_mode) in [("pd:", "virt"), ("pd:", "pd")]:
                            cur_mode = "pd"
                            count_dict[cur_mode] += 1
                            cur_dict = {"lines" : []}
                            ctrl_stuff["virt"][count_dict["virt"]].setdefault("pd", {})[count_dict[cur_mode]] = cur_dict
                        elif parts[0] in ["exit"]:
                            # last line, pass
                            pass
                        else:
                            # unknown mode
                            raise ValueError, "cannot parse mode, ctrl_type_megaraid_sas: %s" % (str(line))
                        mode_sense = False
                        # print cur_mode, mode_sense, count_dict, line
                    else:
                        if line.count(":"):
                            key, value = line.split(":", 1)
                            if line.startswith(" "):
                                if cont_mode:
                                    cur_val = cur_dict["lines"][-1]
                                    cur_dict["lines"][-1] = (cur_val[0], "%s%s%s" % (
                                            cur_val[1],
                                            ", " if cur_val[1] else "",
                                            " ".join(line.strip().split())))
                            else:
                                key = key.lower().strip().replace(" ", "_")
                                if key in SAS_OK_KEYS[cur_mode]:
                                    value = value.strip()
                                    cur_dict["lines"].append((key, value))
                                cont_mode = key in SAS_CONT_KEYS
            # pprint.pprint(ctrl_stuff)
            # if line.lower().count("virtual disk:") or line.lower().count("virtual drive:"):
            #    log_drive_num = int(line.strip().split()[2])
            #    ctrl_stuff["logical_lines"][log_drive_num] = []
            # if log_drive_num is not None:
            #    if line.count(":"):
            #        ctrl_stuff["logical_lines"][log_drive_num].append([part.strip() for part in line.split(":", 1)])
        elif run_type == "enc":
            cur_mode, mode_sense, count_dict = (None, True, {})
            for line in [cur_line.rstrip() for cur_line in ccs.read().split("\n")]:
                empty_line = not line.strip()
                parts = line.lower().strip().split()
                if empty_line:
                    mode_sense = True
                else:
                    if mode_sense == True:
                        if (parts[0], cur_mode) in [("enclosure", None), ("enclosure", "run")]:
                            cur_mode = "enc"
                            count_dict = {"enc" : count_dict.get("enc", -1) + 1}
                            cur_dict = {}
                            ctrl_stuff.setdefault("enclosures", {})[count_dict["enc"]] = cur_dict
                        elif (parts[0], cur_mode) in [("number", "enc"), ("number", "run")]:
                            cur_dict = {"num"   : int(parts[-1])}
                            count_dict["sub_key"] = "_".join(parts[2:-2])
                            ctrl_stuff.setdefault("enclosures", {})[count_dict["enc"]][count_dict["sub_key"]] = cur_dict
                            cur_mode = "run"
                        elif parts[0] == "exit":
                            pass
                        elif cur_mode == "run":
                            cur_dict = {"lines" : []}
                            ctrl_stuff.setdefault("enclosures", {})[count_dict["enc"]][count_dict["sub_key"]][int(parts[-1])] = cur_dict
                        mode_sense = False
                    else:
                        if line.count(":"):
                            key, value = line.split(":", 1)
                            key = key.lower().strip().replace(" ", "_")
                            cur_dict["lines"].append((key, value.strip()))
        elif run_type == "bbu":
            ctrl_stuff["bbu_keys"] = {}
            main_key = "main"
            for line in [cur_line.rstrip() for cur_line in ccs.read().split("\n") if cur_line.strip()]:
                if not line.startswith(" "):
                    main_key = "main"
                if line.count(":"):
                    if line.endswith(":"):
                        main_key = line.strip()[:-1].lower()
                    else:
                        if main_key in ["bbu firmware status"]:
                            pass
                        else:
                            key, value = line.split(":", 1)
                            act_key = key.strip().lower()
                            value = value.strip()
                            value = {"no" : False,
                                     "yes" : True}.get(value.lower(), value)
                            ctrl_stuff["bbu_keys"].setdefault(main_key, {})[act_key] = value
            # store in ccs
            ccs.srv_com["result:ctrl_%d" % (ctrl_id)] = ctrl_stuff
    def update_ok(self, srv_com):
        if self._dict:
            return ctrl_type.update_ok(self, srv_com)
        else:
            srv_com["result"].attrib.update({"reply" : "no controller found",
                                             "state" : "%d" % (server_command.SRV_REPLY_STATE_ERROR)})
            return False
    def _interpret(self, ctrl_dict, cur_ns):
        num_c, num_d, num_e, num_w = (len(ctrl_dict.keys()), 0, 0, 0)
        ret_state = limits.nag_STATE_OK
        drive_stats = []
        num_enc = 0
        for ctrl_num, ctrl_stuff in ctrl_dict.iteritems():
            if "virt" not in ctrl_stuff:
                # rewrite from old to new format
                ctrl_stuff["virt"] = dict([(key, {"lines" : [(line[0].lower().replace(" ", "_"), line[1]) for line in value]}) for key, value in ctrl_stuff["logical_lines"].iteritems()])
            for log_num, log_stuff in ctrl_stuff.get("virt", {}).iteritems():
                # pprint.pprint(log_dict)
                log_dict = dict(log_stuff["lines"])
                num_d += 1
                num_drives = int(log_dict["number_of_drives"])
                if "state" in log_dict:
                    status = log_dict["state"]
                    if status.lower() != "optimal":
                        num_e += 1
                    drive_stats.append("ld %d (ctrl %d, %s, %s): %s" % (
                        log_num,
                        ctrl_num,
                        log_dict.get("size", "???"),
                        logging_tools.get_plural("disc", num_drives),
                        status))
                if "ongoing_progresses" in log_dict:
                    num_w += 1
                    drive_stats.append(log_dict["ongoing_progresses"])
                if "current_cache_policy" in log_dict:
                    _cur_cps = [entry.strip().lower() for entry in log_dict["current_cache_policy"].split(",") if entry.strip()]
                    if _cur_cps and _cur_cps[0] != "writeback":
                        num_e += 1
                        drive_stats.append("suboptimal cache mode: %s" % (_cur_cps[0]))
                drives_missing = []
                if "pd" in log_stuff:
                    for pd_num in xrange(num_drives):
                        if not log_stuff["pd"].get(pd_num, {}).get("lines", None):
                            drives_missing.append(pd_num)
                        else:
                            pd_dict = dict(log_stuff["pd"][pd_num]["lines"])
                            cur_state = pd_dict.get("firmware_state", "unknown")
                            if cur_state.lower() not in ["online, spun up"]:
                                drive_stats.append("drive %d: %s" % (pd_num, cur_state))
                                num_w += 1
                if drives_missing:
                    num_e += 1
                    drive_stats.append("drives missing: %s" % (", ".join(["%d" % (m_drive) for m_drive in drives_missing])))
            if not "virt" in ctrl_stuff:
                num_w += 1
            if "enclosures" in ctrl_stuff:
                for enc_num in sorted(ctrl_stuff["enclosures"].keys()):
                    num_enc += 1
                    enc_dict = ctrl_stuff["enclosures"][enc_num]
                    enc_fields = []
                    for key in sorted(enc_dict.keys()):
                        s_key = {"fans"                : "fan",
                                 "alarms"              : "alarm",
                                 "power_supplies"      : "PS",
                                 "temperature_sensors" : "temp",
                                 "slots"               : "slot"}.get(key, key)
                        cur_num = int(enc_dict[key].get("num", "0"))
                        if cur_num:
                            loc_problems = 0
                            for cur_idx in xrange(cur_num):
                                cur_stat = enc_dict[key][cur_idx]["lines"][0][1]
                                if key.count("temperature"):
                                    if int(cur_stat) > 50:
                                        problem = True
                                    else:
                                        problem = False
                                elif cur_stat.lower() in set(["ok", "not installed", "unknown", "medium speed", "normal speed", "low speed", "high speed"]):
                                    problem = False
                                else:
                                    problem = True
                                if problem:
                                    loc_problems += 1
                                    num_e += 1
                                    enc_fields.append("%s %d: %s" % (
                                        s_key,
                                        cur_idx,
                                        cur_stat))
                            if cur_num > loc_problems:
                                enc_fields.append("%s ok" % (
                                    logging_tools.get_plural(s_key, cur_num - loc_problems)
                                ))
                    drive_stats.append("enc%d: %s" % (
                        enc_num,
                        ", ".join(enc_fields)
                    ))
        if num_e:
            ret_state = limits.nag_STATE_CRITICAL
        elif num_w:
            ret_state = limits.nag_STATE_WARNING
        return ret_state, "%s on %s (%s), %s" % (
            logging_tools.get_plural("logical drive", num_d),
            logging_tools.get_plural("controller", num_c),
            logging_tools.get_plural("enclosure", num_enc),
            ", ".join(drive_stats))

class ctrl_type_megaraid(ctrl_type):
    class Meta:
        name = "megaraid"
        exec_name = "megarc"
        description = "MegaRAID"
    def get_exec_list(self, ctrl_list=[]):
        if ctrl_list == []:
            ctrl_list = self._dict.keys()
        return ["%s info %s" % (self._check_exec, ctrl_id) for ctrl_id in ctrl_list]
    def scan_ctrl(self):
        cur_stat, cur_lines = self.exec_command(" info", post="strip")
    def update_ctrl(self, ctrl_ids):
        pass
        # print ctrl_ids
    def update_ok(self, srv_com):
        if self._dict:
            return ctrl_type.update_ok(self, srv_com)
        else:
            srv_com["result"].attrib.update({"reply" : "no controller found",
                                             "state" : "%d" % (server_command.SRV_REPLY_STATE_ERROR)})
            return False
    def process(self, ccs):
        ccs.srv_com["result"] = "OK"
    def _interpret(self, ctrl_dict, cur_ns):
        num_c, num_d, num_e = (len(ctrl_dict.keys()), 0, 0)
        ret_state, ret_str = (limits.nag_STATE_OK, "OK")
        drive_stats = []
        for ctrl_num, ctrl_stuff in ctrl_dict.iteritems():
            for log_num, log_stuff in ctrl_stuff.get("logical_lines", {}).iteritems():
                num_d += 1
                for line in log_stuff:
                    if line.lower().startswith("logical drive") and line.lower().count("status"):
                        status = line.split()[-1]
                        if status.lower() != "optimal":
                            num_e += 1
                        drive_stats.append("ld %d (ctrl %d): %s" % (log_num,
                                                                    ctrl_num,
                                                                    status))
        if num_e:
            ret_state, ret_str = (limits.nag_STATE_CRITICAL, "Error")
        return ret_state, "%s: %s on %s, %s" % (ret_str,
                                                logging_tools.get_plural("logical drive", num_d),
                                                logging_tools.get_plural("controller", num_c),
                                                ", ".join(drive_stats))

class ctrl_type_gdth(ctrl_type):
    class Meta:
        name = "gdth"
        exec_name = "true"
        description = "GDTH"
    def get_exec_list(self, ctrl_list=[]):
        if ctrl_list == []:
            ctrl_list = self._dict.keys()
        return ["/bin/true %s" % (ctrl_id) for ctrl_id in ctrl_list]
    def scan_ctrl(self):
        gdth_dir = "/proc/scsi/gdth"
        if os.path.isdir(gdth_dir):
            for entry in os.listdir(gdth_dir):
                self._dict[entry] = {}
    def update_ctrl(self, ctrl_ids):
        pass
        # print ctrl_ids
    def update_ok(self, srv_com):
        if self._dict:
            return ctrl_type.update_ok(self, srv_com)
        else:
            srv_com["result"].attrib.update({"reply" : "no controller found",
                                             "state" : "%d" % (server_command.SRV_REPLY_STATE_ERROR)})
            return False
    def process(self, ccs):
        com_line, ctrl_id = ccs.run_info["command"].strip().split()
        ctrl_file = "/proc/scsi/gdth/%s" % (ctrl_id)
        last_log_line, last_log_time = ("", None)
        act_time = datetime.datetime(*time.localtime()[0:6])
        lines = [line.rstrip() for line in file(ctrl_file, "r").read().split("\n")]
        act_mode = "?"
        pd_dict, ld_dict, ad_dict, hd_dict = ({}, {}, {}, {})
        for line in lines:
            if line.lower().startswith("driver parameter"):
                act_mode = "dp"
                act_dp_dict = {}
            elif line.lower().startswith("disk array control"):
                act_mode = "ci"
            elif line.lower().startswith("physical devices"):
                act_mode = "pd"
            elif line.lower().startswith("logical drives"):
                act_mode = "ld"
                act_ld_dict = {}
            elif line.lower().startswith("array drives"):
                act_mode = "ad"
                act_ad_dict = {}
            elif line.lower().startswith("host drives"):
                act_mode = "hd"
                act_hd_dict = {}
            elif line.lower().startswith("controller even"):
                act_mode = "ce"
            elif line.strip():
                # print "%s %s" % (act_mode, line)
                if act_mode == "pd":
                    left_str, right_str = (line[0:27].strip(), line[27:].strip())
                    for act_str in [x for x in [left_str, right_str] if x]:
                        key, value = [x.strip() for x in act_str.split(":", 1)]
                        act_dp_dict[key.lower()] = value
                        if key.lower() == "grown defects":
                            pd_dict[len(pd_dict)] = act_dp_dict
                            act_dp_dict = {}
                elif act_mode == "ld":
                    left_str, right_str = (line[0:27].strip(), line[27:].strip())
                    for act_str in [x for x in [left_str, right_str] if x]:
                        key, value = [x.strip() for x in act_str.split(":", 1)]
                        act_ld_dict[key.lower()] = value
                        if key.lower().startswith("to array dr"):
                            if act_ld_dict.has_key("status"):
                                ld_dict[len(ld_dict)] = act_ld_dict
                            act_ld_dict = {}
                elif act_mode == "ad":
                    if len(line.strip()) > 10:
                        left_str, right_str = (line[0:27].strip(), line[27:].strip())
                        for act_str in [x for x in [left_str, right_str] if x]:
                            key, value = [x.strip() for x in act_str.split(":", 1)]
                            act_ad_dict[key.lower()] = value
                            if key.lower().startswith("type"):
                                ad_dict[len(ad_dict)] = act_ad_dict
                                act_ad_dict = {}
                elif act_mode == "hd":
                    left_str, right_str = (line[0:27].strip(), line[27:].strip())
                    for act_str in [x for x in [left_str, right_str] if x]:
                        key, value = [x.strip() for x in act_str.split(":", 1)]
                        act_hd_dict[key.lower()] = value
                        if key.lower().startswith("start secto"):
                            hd_dict[len(hd_dict)] = act_hd_dict
                            act_hd_dict = {}
                elif act_mode == "ce":
                    if line.strip().startswith("date-"):
                        line_p = line.strip().split(None, 2)
                        line_d, last_log_line = ([int(x) for x in line_p[1].split(":")], line_p[2])
                        time_t = datetime.timedelta(0, line_d[0] * 3600 + line_d[1] * 60 + line_d[2])
                        last_log_time = act_time - time_t
        ret_dict = {
            "pd" : pd_dict,
            "ld" : ld_dict,
            "ad" : ad_dict,
            "hd" : hd_dict,
            "log" : (last_log_time, last_log_line)}
        ccs.srv_com["result:ctrl_%s" % (ctrl_id)] = ret_dict
    def _interpret(self, ctrl_dict, cur_ns):
        if ctrl_dict.keys()[0].startswith("ctrl_"):
            ctrl_dict = ctrl_dict.values()[0]
        pd_list, ld_list, ad_list, hd_list = (ctrl_dict["pd"], ctrl_dict["ld"], ctrl_dict["ad"], ctrl_dict["hd"])
        if type(pd_list) == type({}):
            # rewrite dict to list
            pd_list = [pd_list[key] for key in sorted(pd_list.keys())]
            ld_list = [ld_list[key] for key in sorted(ld_list.keys())]
            ad_list = [ad_list[key] for key in sorted(ad_list.keys())]
            hd_list = [hd_list[key] for key in sorted(hd_list.keys())]
        last_log_time, last_log_line = ctrl_dict.get("log", (None, ""))
        out_f, num_w, num_e = ([], 0, 0)
        for l_type, what, lst in [("p", "physical disc", pd_list),
                                  ("l", "logical drive", ld_list),
                                  ("a", "array drive"  , ad_list),
                                  ("h", "host drive"   , hd_list)]:
            if lst:
                num = len(lst)
                cap = reduce(lambda x, y : x + y, [int(x["capacity [mb]"]) for x in lst if x.has_key("capacity [mb]")])
                loc_out = ["%s (%s)" % (logging_tools.get_plural(what, num),
                                        ", ".join([entry for entry in ["%.2f GB" % (float(cap) / 1024) if cap else "",
                                                                       ", ".join([x["type"] for x in lst if x.has_key("type")]) if lst[0].has_key("type") else ""] if entry]))]
                if lst[0].has_key("status"):
                    loc_warn = [x for x in lst if x["status"].lower() in ["rebuild", "build", "rebuild/patch"]]
                    loc_err = [x for x in lst if x["status"].lower() not in ["ok", "ready", "rebuild", "build", "rebuild/patch", "ready/patch"]]
                    if loc_warn:
                        num_w += 1
                        loc_out.append(", ".join(["%s %s: %s" % (what, x["number"], x["status"]) for x in loc_warn]))
                    if loc_err:
                        num_e += 1
                        loc_out.append(", ".join(["%s %s: %s" % (what, x["number"], x["status"]) for x in loc_err]))
                out_f.append(";".join(loc_out))
            else:
                out_f.append("no %ss" % (what))
        if num_e:
            ret_state, ret_str = (limits.nag_STATE_CRITICAL, "Error")
        elif num_w:
            ret_state, ret_str = (limits.nag_STATE_WARNING, "Warning")
        else:
            ret_state, ret_str = (limits.nag_STATE_OK, "OK")
        if last_log_line:
            # change ret_state if ret_state == STATE_OK:
            if ret_state == limits.nag_STATE_OK:
                lll = last_log_line.lower().strip()
                if lll.endswith("started"):
                    ret_state, ret_str = (limits.nag_STATE_WARNING, "Warning")
            out_f.append(last_log_line)
        return ret_state, "%s: %s" % (ret_str, ", ".join(out_f))

class ctrl_type_hpacu(ctrl_type):
    class Meta:
        name = "hpacu"
        exec_name = "hpacucli"
        description = "HP Acu controller"
    def get_exec_list(self, ctrl_list=[]):
        if ctrl_list == []:
            ctrl_list = self._dict.keys()
        return ["%s ctrl slot=%d show config detail" % (self._check_exec, self._dict[ctrl_id]["config"]["slot"]) for ctrl_id in ctrl_list]
    def scan_ctrl(self):
        cur_stat, cur_lines = self.exec_command(" ctrl all show", post="strip")
        if not cur_stat:
            num_ctrl = len([True for line in cur_lines if line.lower().count("smart array")])
            if num_ctrl:
                for ctrl_num in range(1, num_ctrl + 1):
                    slot_num = int(cur_lines[ctrl_num - 1].strip().split()[5])
                    c_stat, c_result = self.exec_command(" ctrl slot=%d show status" % (slot_num))
                    ctrl_stuff = {}
                    ctrl_stuff["config"] = {"slot" : slot_num}
                    for key, val in [_split_config_line(line) for line in c_result if line.count(":")]:
                        ctrl_stuff["config"][key] = val
                    self._dict[ctrl_num] = ctrl_stuff
    def update_ctrl(self, ctrl_ids):
        pass
        # print ctrl_ids
    def update_ok(self, srv_com):
        if self._dict:
            return ctrl_type.update_ok(self, srv_com)
        else:
            srv_com["result"].attrib.update({"reply" : "no controller found",
                                             "state" : "%d" % (server_command.SRV_REPLY_STATE_ERROR)})
            return False
    def process(self, ccs):
        c_dict = {}
        act_ctrl, act_array, act_log, act_phys, act_obj, act_pmgroup = (
            None, None, None, None, None, None)
        for c_line in ccs.read().split("\n"):
            l_line = c_line.lower().strip()
            if l_line.count("in slot"):
                is_idx = l_line.index("in slot")
                c_num = int(l_line[is_idx + len("in slot"):].strip().split()[0])
                act_ctrl = {
                    "info"   : c_line[0:is_idx].strip(),
                    "arrays" : {},
                    "config" : {}}
                c_dict[c_num] = act_ctrl
                act_array, act_log, act_phys, act_pmgroup = (
                    None, None, None, None)
                act_obj = act_ctrl
                continue
            if act_ctrl is not None:
                if l_line.startswith("array:"):
                    act_array = {
                        "logicals"      : {},
                        "physicals"     : {},
                        "config"        : {},
                    }
                    array_num = " ".join(c_line.split()[1:])
                    if not act_ctrl["arrays"].has_key(array_num):
                        act_ctrl["arrays"][array_num] = act_array
                    act_phys, act_log, act_pmgroup = (None, None, None)
                    act_obj = act_array
                    continue
                if act_array is not None:
                    if l_line.startswith("logical drive:"):
                        l_num = int(l_line.split()[-1])
                        act_log = {
                            "config"        : {},
                            "parity_groups" : {},
                            "mirror_groups" : {},
                            }
                        act_array["logicals"][l_num] = act_log
                        act_phys = None
                        act_obj = act_log
                        continue
                    elif l_line.startswith("physicaldrive"):
                        if act_pmgroup:
                            act_pmgroup["drives"].append(l_line.strip())
                        else:
                            pos_info = c_line.split()[-1].replace(":", "_")
                            act_phys = {
                                "config" : {},
                            }
                            act_array["physicals"][pos_info] = act_phys
                            act_log = None
                            act_obj = act_phys
                        continue
                    elif l_line.startswith("parity group"):
                        # parity and mirror groups are below logical drive, take care
                        pos_info = c_line.split()[-1].replace(":", "")
                        act_pmgroup = {"drives" : []}
                        act_log["parity_groups"][pos_info] = act_pmgroup
                        act_obj = act_pmgroup
                        continue
                    elif l_line.startswith("mirror group"):
                        pos_info = c_line.split()[-1].replace(":", "")
                        act_pmgroup = {"drives" : []}
                        act_log["mirror_groups"][pos_info] = act_pmgroup
                        act_obj = act_pmgroup
                        continue
            if not l_line.strip():
                if act_pmgroup:
                    # clear parity group
                    act_pmgroup = None
            if l_line.count(":") and act_obj:
                key, value = self._interpret_line(l_line)
                if not "config" in act_obj and act_pmgroup:
                    # data type tag after mirror / parity groups
                    act_pmgroup = None
                    act_obj = act_log
                act_obj["config"][key] = value
            # else:
            #    if l_line.count("status"):
            #        c_dict[act_ctrl]["status"][l_line.split()[0]] = " ".join(l_line.split()[2:])
        ccs.srv_com["result:ctrl"] = c_dict
    def _interpret_line(self, in_line):
        key, value = in_line.split(":", 1)
        key = key.strip()
        value = value.strip()
        key = key.replace(" ", "_")
        if key.count("temperature"):
            value = float(value)
        elif key == "logical_drive_label":
            # remove binary values from label, stupid HP
            value = "".join([cur_c for cur_c in value if ord(cur_c) > 32 and ord(cur_c) < 80])
        elif value.isdigit():
            value = int(value)
        if key.endswith("temperature_(c)"):
            key = key[:-4]
        key = key.replace("(", "").replace(")", "")
        return key, value
    def _interpret(self, ctrl_dict, cur_ns):
        num_cont, num_array, num_log, num_phys = (0, 0, 0, 0)
        array_names, size_log, size_phys = ([], [], 0)
        # pprint.pprint(c_dict)
        error_f, warn_f = ([], [])
        if "ctrl" not in ctrl_dict and len(ctrl_dict):
            ctrl_dict = {"ctrl" : ctrl_dict}
            new_style = False
        else:
            new_style = True
        for slot_num, c_stuff in ctrl_dict.get("ctrl", {}).iteritems():
            num_cont += 1
            # new code
            if new_style:
                status_dict = dict([(key, value) for key, value in c_stuff.get("config", {}).iteritems() if key.count("status") and not key.count("6_adg")])
            else:
                status_dict = dict([(key, value) for key, value in c_stuff.get("status", {}).iteritems()])
            if set(status_dict.values()) != set(["ok"]):
                error_f.append("status of controller %s (slot %d): %s" % (c_stuff["info"], slot_num, ", ".join(["%s: %s" % (key, value) for key, value in status_dict.iteritems() if value != "ok"])))
            for array_name, array_stuff in c_stuff["arrays"].iteritems():
                array_names.append("%s in slot %d" % (array_name, slot_num))
                num_array += 1
                for log_num, log_stuff in array_stuff["logicals"].iteritems():
                    num_log += 1
                    if "config" in log_stuff:
                        # new format
                        _lc = log_stuff["config"]
                        size_log.append(get_size(_lc["size"]))
                        if _lc["status"].lower() != "ok":
                            error_f.append("status of log.drive %d (array %s) is %s (%s%s)" % (
                                log_num,
                                array_name,
                                _lc["status"],
                                _lc["fault_tolerance"],
                                ", %s" % (_lc.get("parity_initialization_status", ""))))
                    else:
                        size_log.append(get_size(log_stuff["size_info"]))
                        if log_stuff["status_info"].lower() != "okx":
                            error_f.append("status of log.drive %d (array %s) is %s (%s)" % (
                                log_num,
                                array_name,
                                log_stuff["status_info"],
                                log_stuff["raid_info"],
                            ))
                for phys_num, phys_stuff in array_stuff["physicals"].iteritems():
                    num_phys += 1
                    _pc = phys_stuff["config"]
                    size_phys += get_size(_pc["size"])
                    if _pc["status"].lower() != "ok":
                        pos_info = "port %s, box %s, bay %s" % (_pc["port"], _pc["box"], _pc["bay"])
                        error_f.append("status of phys.drive %s (array %s) is %s (%s)" % (pos_info, array_name, _pc["status"], _pc["drive_type"]))
        if error_f:
            ret_state, ret_str = (limits.nag_STATE_CRITICAL, "Error")
            error_str = ", %s: %s" % (logging_tools.get_plural("error", len(error_f)), ", ".join(error_f))
        else:
            ret_state, ret_str = (limits.nag_STATE_OK, "OK")
            error_str = ""
        if num_array:
            return ret_state, "%s: %s, %s (%s), %s (%s), %s (%s)%s" % (
                ret_str,
                logging_tools.get_plural("controller", num_cont),
                logging_tools.get_plural("array", num_array),
                ", ".join(array_names),
                logging_tools.get_plural("log.drive", num_log),
                "+".join([logging_tools.get_size_str(act_size_log) for act_size_log in size_log]),
                logging_tools.get_plural("phys.drive", num_phys),
                logging_tools.get_size_str(size_phys),
                error_str)
        else:
            return ret_state, "%s: %s, %s (%s), %s (%s)%s" % (
                ret_str,
                logging_tools.get_plural("controller", num_cont),
                logging_tools.get_plural("log.drive", num_log),
                "+".join([logging_tools.get_size_str(act_size_log) for act_size_log in size_log]),
                logging_tools.get_plural("phys.drive", num_phys),
                logging_tools.get_size_str(size_phys),
                error_str)

class ctrl_type_ibmbcraid(ctrl_type):
    class Meta:
        name = "ibmbcraid"
        exec_name = "true"
        description = "IBM Raidcontroller for Bladecenter S"
    def get_exec_list(self, ctrl_list=[]):
        if ctrl_list == []:
            ctrl_list = self._dict.keys()

        _list = [(
            "/opt/python-init/lib/python2.7/site-packages/initat/host_monitoring/exe/check_ibmbcraid.py --host %s --user %s --passwd %s --target %s" % (
                ctrl_id,
                self.cur_ns.user,
                self.cur_ns.passwd,
                self._get_target_file(ctrl_id),
                ),
            ctrl_id,
            self._get_target_file(ctrl_id)) for ctrl_id in ctrl_list]
        return _list
    def _get_target_file(self, ctrl_id):
        return "/tmp/.bcraidctrl_%s" % (ctrl_id)
    def scan_ctrl(self):
        cur_stat, cur_lines = self.exec_command(" info", post="strip")
    def update_ctrl(self, ctrl_ids):
        pass
    def update_ok(self, srv_com):
        if self._dict:
            return ctrl_type.update_ok(self, srv_com)
        else:
            srv_com["result"].attrib.update({"reply" : "no controller found",
                                             "state" : "%d" % (server_command.SRV_REPLY_STATE_ERROR)})
            return False
    def started(self, ccs):
        com_line, ctrl_id, s_file = ccs.run_info["command"]
        if os.path.isfile(s_file):
            f_dt = os.stat(s_file)[stat.ST_CTIME]
            file_age = abs(time.time() - f_dt)
            if file_age > 60 * 15:
                ccs.srv_com.set_result(
                    "controller information for %s is too old: %s" % (ctrl_id, logging_tools.get_diff_time_str(file_age)),
                    server_command.SRV_REPLY_STATE_ERROR)
            else:
                # content of s_file is already marshalled
                ccs.srv_com["result:ctrl_%s" % (ctrl_id)] = base64.b64encode(file(s_file, "r").read())
        else:
            ccs.srv_com.set_result("no controller information found for %s" % (ctrl_id),
                                   server_command.SRV_REPLY_STATE_ERROR)
    def process(self, ccs):
        pass
    def _interpret(self, ctrl_dict, cur_ns):
        ctrl_dict = dict([(key.split("_")[1], marshal.loads(base64.b64decode(value))) for key, value in ctrl_dict.iteritems()])
        ctrl_keys = set(ctrl_dict.keys())
        if cur_ns.arguments:
            match_keys = set(cur_ns.arguments) & ctrl_keys
        else:
            match_keys = ctrl_keys
        if match_keys:
            for cur_key in sorted(match_keys):
                ctrl_dict = ctrl_dict[cur_key]
                ret_state = limits.nag_STATE_OK
                ret_f = []
                for ctrl_info in ctrl_dict["ctrl_list"]:
                    ret_f.append("%s (%s)" % (ctrl_info["name"],
                                              ctrl_info["status"]))
                    if ctrl_info["status"].lower() not in ["primary", "secondary"]:
                        ret_state = max(ret_state, limits.nag_STATE_CRITICAL)
                for ctrl_key in [key for key in ctrl_dict.keys() if key.split("_")[1].isdigit()]:
                    cur_dict = ctrl_dict[ctrl_key]
                    # pprint.pprint(cur_dict)
                    ctrl_f = []
                    ctrl_f.append("C%d: %s" % (int(ctrl_key.split("_")[1]),
                                               cur_dict["Current Status"]))
                    if "BBU Charging" in cur_dict:
                        if cur_dict["BBU Charging"]:
                            ctrl_f.append("BBU Charging")
                            ret_state = max(ret_state, limits.nag_STATE_WARNING)
                    else:
                        ctrl_f.append("no BBU Charge info")
                        ret_state = max(ret_state, limits.nag_STATE_WARNING)
                    if cur_dict["BBU State"].split()[0] != "1" or cur_dict["BBU Fault Code"].split()[0] != "0":
                        ctrl_f.append("BBU State/Fault Code: '%s/%s'" % (cur_dict["BBU State"],
                                                                         cur_dict["BBU Fault Code"]))
                        ret_state = max(ret_state, limits.nag_STATE_CRITICAL)
                    if cur_dict["Current Status"].lower() not in ["primary", "secondary"]:
                        ret_state = max(ret_state, limits.nag_STATE_CRITICAL)
                    vol_info = [logging_tools.get_plural("volume", len(cur_dict["volumes"]))]
                    for cur_vol in cur_dict["volumes"]:
                        if cur_vol["status"] != "VBL INI":
                            vol_info.append("%s (%d, %s): %s" % (cur_vol["name"],
                                                                 cur_vol["raidlevel"],
                                                                 cur_vol["capacity"],
                                                                 cur_vol["status"]))
                        pass
                    ctrl_f.append(",".join(vol_info))
                    ret_f.append(", ".join(ctrl_f))
            return ret_state, "; ".join(ret_f)
        else:
            return limits.nag_STATE_CRITICAL, "no controller found"

class _general(hm_classes.hm_module):
    def init_module(self):
        ctrl_type.init(self)

class tw_status_command(hm_classes.hm_command):
    info_string = "3ware controller information"
    def __init__(self, name):
        hm_classes.hm_command.__init__(self, name, positional_arguments=True)
    def __call__(self, srv_com, cur_ns):
        ctrl_type.update("tw")
        if "arguments:arg0" in srv_com:
            ctrl_list = [srv_com["arguments:arg0"].text]
        else:
            ctrl_list = []
        if ctrl_type.ctrl("tw").update_ok(srv_com):
            return ctrl_check_struct(self.log, srv_com, ctrl_type.ctrl("tw"), ctrl_list)
    def interpret(self, srv_com, cur_ns):
        return self._interpret(dict([(srv_com._interpret_tag(cur_el, cur_el.tag), srv_com._interpret_el(cur_el)) for cur_el in srv_com["result"]]), cur_ns)
    def interpret_old(self, result, parsed_coms):
        tw_dict = hm_classes.net_to_sys(result[3:])
        return self._interpret(tw_dict, parsed_coms)
    def _interpret(self, tw_dict, cur_ns):
        return ctrl_type.ctrl("tw")._interpret(tw_dict, cur_ns)

class aac_status_command(hm_classes.hm_command):
    def __init__(self, name):
        hm_classes.hm_command.__init__(self, name, positional_arguments=False)
    def __call__(self, srv_com, cur_ns):
        ctrl_type.update("ips")
        if "arguments:arg0" in srv_com:
            ctrl_list = [srv_com["arguments:arg0"].text]
        else:
            ctrl_list = []
        if ctrl_type.ctrl("ips").update_ok(srv_com):
            return ctrl_check_struct(self.log, srv_com, ctrl_type.ctrl("ips"), ctrl_list)
    def interpret(self, srv_com, cur_ns):
        return self._interpret(marshal.loads(bz2.decompress(base64.b64decode(srv_com["ips_dict_base64"].text))), cur_ns)
    def interpret_old(self, result, cur_ns):
        aac_dict = hm_classes.net_to_sys(result[3:])
        return self._interpret(aac_dict, cur_ns)
    def _interpret(self, aac_dict, cur_ns):
        return ctrl_type.ctrl("ips")._interpret(aac_dict, cur_ns)

class megaraid_sas_status_command(hm_classes.hm_command):
    def __call__(self, srv_com, cur_ns):
        ctrl_type.update("megaraid_sas")
        if ctrl_type.ctrl("megaraid_sas").update_ok(srv_com):
            return ctrl_check_struct(self.log, srv_com, ctrl_type.ctrl("megaraid_sas"), [])
    def interpret(self, srv_com, cur_ns):
        ctrl_dict = {}
        for res in srv_com["result"]:
            ctrl_dict[int(res.tag.split("}")[1].split("_")[-1])] = srv_com._interpret_el(res)
        return self._interpret(ctrl_dict, cur_ns)
    def interpret_old(self, result, cur_ns):
        ctrl_dict = hm_classes.net_to_sys(result[3:])
        return self._interpret(ctrl_dict, cur_ns)
    def _interpret(self, ctrl_dict, cur_ns):
        return ctrl_type.ctrl("megaraid_sas")._interpret(ctrl_dict, cur_ns)

class megaraid_status_command(hm_classes.hm_command):
    def server_call(self, cm):
        self.module_info.init_ctrl_dict(self.logger)
        self.module_info.update_ctrl_dict(self.logger)
        return "ok %s" % (hm_classes.sys_to_net(self.module_info.get_ctrl_config()))
    def interpret_old(self, result, cur_ns):
        ctrl_dict = hm_classes.net_to_sys(result[3:])
        return self._interpret(ctrl_dict, cur_ns)
    def _interpret(self, ctrl_dict, cur_ns):
        return ctrl_type.ctrl("megaraid")._interpret(ctrl_dict, cur_ns)

class gdth_status_command(hm_classes.hm_command):
    def __call__(self, srv_com, cur_ns):
        ctrl_type.update("gdth")
        if "arguments:arg0" in srv_com:
            ctrl_list = [srv_com["arguments:arg0"].text]
        else:
            ctrl_list = []
        if ctrl_type.ctrl("gdth").update_ok(srv_com):
            return ctrl_check_struct(self.log, srv_com, ctrl_type.ctrl("gdth"), ctrl_list)
    def _interpret(self, ctrl_dict, cur_ns):
        return ctrl_type.ctrl("gdth")._interpret(ctrl_dict, cur_ns)
    def interpret(self, srv_com, cur_ns):
        return self._interpret(dict([(srv_com._interpret_tag(cur_el, cur_el.tag), srv_com._interpret_el(cur_el)) for cur_el in srv_com["result"]]), cur_ns)
    def interpret_old(self, result, cur_ns):
        ctrl_dict = hm_classes.net_to_sys(result[3:])
        return self._interpret(ctrl_dict, cur_ns)

class hpacu_status_command(hm_classes.hm_command):
    def __call__(self, srv_com, cur_ns):
        ctrl_type.update("hpacu")
        ctrl_list = []
        return ctrl_check_struct(self.log, srv_com, ctrl_type.ctrl("hpacu"), ctrl_list)
    def interpret_old(self, result, cur_ns):
        ctrl_dict = hm_classes.net_to_sys(result[3:])
        return self._interpret(ctrl_dict, cur_ns)
    def interpret(self, srv_com, cur_ns):
        return self._interpret(dict([(srv_com._interpret_tag(cur_el, cur_el.tag), srv_com._interpret_el(cur_el)) for cur_el in srv_com["result"]]), cur_ns)
    def _interpret(self, ctrl_dict, cur_ns):
        return ctrl_type.ctrl("hpacu")._interpret(ctrl_dict, cur_ns)

class lsi_status_command(hm_classes.hm_command):
    def __init__(self, name):
        hm_classes.hm_command.__init__(self, name, positional_arguments=True)
    def __call__(self, srv_com, cur_ns):
        ctrl_type.update("lsi")
        if "arguments:arg0" in srv_com:
            ctrl_list = [srv_com["arguments:arg0"].text]
        else:
            ctrl_list = []
        return ctrl_check_struct(self.log, srv_com, ctrl_type.ctrl("lsi"), ctrl_list)
    def interpret(self, srv_com, cur_ns):
        return self._interpret(dict([(srv_com._interpret_tag(cur_el, cur_el.tag), srv_com._interpret_el(cur_el)) for cur_el in srv_com["result"]]), cur_ns)
    def _interpret(self, ctrl_dict, cur_ns):
        return ctrl_type.ctrl("lsi")._interpret(ctrl_dict, cur_ns)

class ibmbcraid_status_command(hm_classes.hm_command):
    def __init__(self, name):
        hm_classes.hm_command.__init__(self, name, positional_arguments=True)
        self.server_parser.add_argument("--user", dest="user", type=str)
        self.server_parser.add_argument("--pass", dest="passwd", type=str)
    def __call__(self, srv_com, cur_ns):
        ctrl_type.update("ibmbcraid")
        ctrl_type.cur_ns = cur_ns
        if "arguments:arg0" in srv_com:
            ctrl_list = [srv_com["arguments:arg0"].text]
        else:
            ctrl_list = []
        return ctrl_check_struct(self.log, srv_com, ctrl_type.ctrl("ibmbcraid"), ctrl_list)
    def interpret(self, srv_com, cur_ns):
        return self._interpret(dict([(srv_com._interpret_tag(cur_el, cur_el.tag), srv_com._interpret_el(cur_el)) for cur_el in srv_com["result"]]), cur_ns)
    def _interpret(self, ctrl_dict, cur_ns):
        return ctrl_type.ctrl("ibmbcraid")._interpret(ctrl_dict, cur_ns)

if __name__ == "__main__":
    print "This is a loadable module."
    sys.exit(0)
