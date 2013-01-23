#!/usr/bin/python-init -Ot
#
# Copyright (C) 2008,2009,2010,2012,2013 Andreas Lang-Nevyjel, init.at
#
# this file is part of nagios-config-server
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
""" special tasks for generating md-config-server """

import sys
import pprint
import re
import logging_tools
import os
import process_tools
from initat.md_config_server.config import global_config
from host_monitoring import ipc_comtools
from host_monitoring.modules import supermicro_mod
from initat.cluster.backbone.models import partition, partition_disc, partition_table, partition_fs, \
     netdevice, net_ip, network, lvm_vg, lvm_lv, device, device_variable
from django.db.models import Q
import time
import bz2
import base64

EXPECTED_FILE = "/etc/sysconfig/host-monitoring.d/openvpn_expected"

def parse_expected():
    ret_dict = {}
    if os.path.isfile(EXPECTED_FILE):
        in_field = open(EXPECTED_FILE, "r").read().split("\n")
        lines = [line.strip() for line in in_field if line.strip() and not line.strip().startswith("#")]
        for line in lines:
            if line.count("=") == 1:
                dev_name, dev_stuff = line.split("=", 1)
                dev_dict = {}
                ret_dict[dev_name.strip()] = dev_dict
                instances = dev_stuff.split()
                for instance in instances:
                    inst_parts = instance.split(":")
                    inst_dict = {}
                    dev_dict[inst_parts.pop(0)] = inst_dict
                    for inst_part in inst_parts:
                        c_parts = inst_part.split(",")
                        client_name = c_parts.pop(0)
                        inst_dict[client_name] = True
                        #inst_dict[client_name] = limits.nag_STATE_CRITICAL
                        #if c_parts and c_parts[0].lower() in ["w"]:
                        #    inst_dict[client_name] = limits.nag_STATE_WARNING
    return ret_dict

class special_base(object):
    class Meta:
        # number of retries in case of error
        retries = 1
        timeout = 15
    def __init__(self, build_proc, s_check, host, valid_ip, global_config):
        for key in dir(special_base.Meta):
            if not key.startswith("__") and not hasattr(self.Meta, key):
                setattr(self.Meta, key, getattr(special_base.Meta, key))
        self.build_process = build_proc
        self.s_check = s_check
        self.host = host
        self.valid_ip = valid_ip
    def _cache_name(self):
        return "/tmp/.md-config-server/%s_%s" % (self.host.name,
                                                 self.valid_ip)
    def _store_cache(self):
        c_name = self._cache_name()
        if not os.path.isdir(os.path.dirname(c_name)):
            os.makedirs(os.path.dirname(c_name))
        _coded = [base64.b64encode(unicode(srv_reply)) for srv_reply in self.__server_results]
        file(c_name, "wb").write(bz2.compress("".join([u"%08d%s" % (len(b64), b64) for b64 in _coded])))
        self.log("stored cached in %s" % (c_name))
    def _load_cache(self):
        self.__cache = []
        self.__use_cache = False
        c_name = self._cache_name()
        if os.path.isfile(c_name):
            c_content = bz2.decompress(file(c_name, "rb").read())
            while c_content:
                b64_len = len(c_content[0:8])
                self.__cache.append(base64.b64decode(c_content[8:b64_len + 8]))
                c_content = c_content[b64_len + 8:]
            self.log("loaded cache from %s" % (c_name))
    def cleanup(self):
        self.build_process = None
    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.build_process.mach_log("[sc] %s" % (what), log_level)
    def collrelay(self, command, *args, **kwargs):
        return self._call_server(
            command,
            "collrelay",
            *args,
            **kwargs
        )
    def snmprelay(self, command, *args, **kwargs):
        return self._call_server(
            command,
            "snmp_relay",
            *args,
            snmp_community=kwargs.pop("snmp_community", "public"),
            snmp_version=kwargs.pop("snmp_version", 1),
            **kwargs
        )
    def _call_server(self, command, server_name, *args, **kwargs):
        self.log("calling server '%s' for %s, command is '%s', %s, %s" % (
            server_name,
            self.valid_ip,
            command,
            "args is '%s'" % (", ".join([str(value) for value in args])) if args else "no arguments",
            ", ".join(["%s='%s'" % (key, value) for key, value in kwargs.iteritems()]) if kwargs else "no kwargs"
        ))
        connect_to_localhost = kwargs.pop("connect_to_localhost", False)
        conn_ip = "127.0.0.1" if connect_to_localhost else self.valid_ip
        for cur_iter in xrange(self.Meta.retries):
            self.log("iteration %d of %d" % (cur_iter, self.Meta.retries))
            try:
                srv_reply = ipc_comtools.send_and_receive_zmq(
                    conn_ip,
                    command,
                    *args,
                    server=server_name,
                    zmq_context=self.build_process.zmq_context,
                    port=2001,
                    **kwargs)
            except:
                self.log("error connecting to '%s' (%s, %s): %s" % (
                    server_name,
                    conn_ip,
                    command,
                    process_tools.get_except_info()),
                         logging_tools.LOG_LEVEL_ERROR)
                srv_reply = None
            else:
                srv_error = srv_reply.xpath(None, ".//ns:result[@state != '0']")
                if srv_error:
                    self.log("got an error (%d): %s" % (
                        int(srv_error[0].attrib["state"]),
                        srv_error[0].attrib["reply"]),
                             logging_tools.LOG_LEVEL_ERROR)
                    srv_reply = None
                else:
                    self.__server_results.append(srv_reply)
            if srv_reply is not None:
                break
            self.log("waiting for %d seconds" % (self.Meta.timeout), logging_tools.LOG_LEVEL_WARN)
            time.sleep(self.Meta.timeout)
        if srv_reply == None and self.__server_calls == 0 and len(self.__cache):
            self.__use_cache = True
        if self.__use_cache:
            if len(self.__cache) > self.__server_calls:
                srv_reply = self.__cache[self.__server_calls]
                self.log("take result from cache [index %d]" % (
                    self.__server_calls
                ))
            else:
                self.log(
                    "cache too small (%d <= %d)" % (
                        len(self.__cache),
                        self.__server_calls),
                    logging_tools.LOG_LEVEL_WARN)
        self.__server_calls += 1
        return srv_reply
    def real_parameter_name(self, in_name):
        return "{MDC}_%s" % (in_name)
    def get_parameter(self, para_name, xpath_str, command, *args, **kwargs):
        """
        get a paramter, by default as device_variable
        """
        server_type = kwargs.pop("target_server", "collrelay")
        var_type = kwargs.pop("var_type", "s")
        r_para_name = self.real_parameter_name(para_name)
        try:
            cur_var = device_variable.objects.get(Q(device=self.host) & Q(name=r_para_name))
        except device_variable.DoesNotExist:
            srv_result = getattr(self, server_type)(command, *args)
            if srv_result is None:
                self.log("no result, returning None vor parameter %s" % (para_name), 
                         logging_tools.LOG_LEVEL_ERROR)
                cur_var = None
            else:
                self.log("requested parameter %s from device via %s" % (para_name, server_type))
                cur_val = srv_result.xpath(None, xpath_str)[0].text
                if var_type == "i":
                    cur_val = int(cur_val)
                cur_var = device_variable(
                    device=self.host,
                    is_public=True,
                    name=r_para_name,
                    description="requested from md-config-server",
                    var_type=var_type,
                )
                cur_var.set_value(cur_val)
                cur_var.save()
        else:
            self.log("read parameter %s from database" % (para_name))
        if cur_var is None:
            return cur_var
        else:
            return cur_var.get_value()
    def __call__(self):
        s_name = self.__class__.__name__.split("_", 1)[1]
        self.log("starting %s for %s" % (s_name, self.host.name))
        s_time = time.time()
        self._load_cache()
        # init result list and number of server calls
        self.__server_results, self.__server_calls = ([], 0)
        cur_ret = self._call()
        e_time = time.time()
        self.log("took %s, (%d of %d ok)" % (logging_tools.get_diff_time_str(e_time - s_time),
                                             len(self.__server_results),
                                             self.__server_calls))
        if len(self.__server_results) == self.__server_calls and self.__server_calls:
            self._store_cache()
        return cur_ret
    def get_arg_template(self, *args, **kwargs):
        return arg_template(self, *args, **kwargs)
    
class arg_template(dict):
    def __init__(self, s_base, *args, **kwargs):
        dict.__init__(self)
        self.info = args[0]
        if s_base is not None:
            self.__arg_lut, self.__arg_list = s_base.s_check.arg_ll
        else:
            self.__arg_lut, self.__arg_list = ({}, [])
        # set defaults
        self.argument_names = sorted(list(set(self.__arg_list) | set(self.__arg_lut.values())))
        for arg_name in self.argument_names:
            dict.__setitem__(self, arg_name, "")
        for key, value in kwargs.iteritems():
            self[key] = value
    def __setitem__(self, key, value):
        l_key = key.lower()
        if l_key.startswith("arg"):
            if l_key.startswith("arg_"):
                key = "arg%d" % (len(self.argument_names) + 1 - int(l_key[4:]))
            if key.upper() not in self.argument_names:
                raise KeyError, "key '%s' not defined in arg_list (%s, %s)" % (
                    key,
                    self.info,
                    ", ".join(self.argument_names)
                )
            else:
                dict.__setitem__(self, key.upper(), value)
        else:
            if key in self.__arg_lut:
                dict.__setitem__(self, self.__arg_lut[key].upper(), value)
            elif "-%s" % (key) in self.__arg_lut:
                dict.__setitem__(self, self.__arg_lut["-%s" % (key)].upper(), value)
            elif "--%s" % (key) in self.__arg_lut:
                dict.__setitem__(self, self.__arg_lut["--%s" % (key)].upper(), value)
            else:
                raise KeyError, "key '%s' not defined in arg_list (%s)" % (
                    key,
                    self.info)

class special_openvpn(special_base):
    def _call(self):
        sc_array = []
        exp_dict = parse_expected()
        if exp_dict.has_key(self.host.name):
            exp_dict = {}#exp_dict[host["name"]]
        else:
            exp_dict = {}
        if not exp_dict:
            # no expected_dict found, try to get the actual config from the server
            srv_result = self.collrelay("openvpn_status")
            if srv_result is not None:
                if "openvpn_instances" in srv_result:
                    ovpn_dict = srv_result["openvpn_instances"]
                    # build exp_dict
                    for inst_name in ovpn_dict:
                        if ovpn_dict[inst_name]["type"] == "server":
                            for c_name in ovpn_dict[inst_name]["dict"]:
                                exp_dict.setdefault(inst_name, {})[c_name] = True
        if exp_dict:
            for inst_name in sorted(exp_dict):
                for peer_name in sorted(exp_dict[inst_name]):
                    sc_array.append(self.get_arg_template("OpenVPN peer %s on %s" % (peer_name, inst_name),
                                                          arg1=inst_name,
                                                          arg2=peer_name))
        if not sc_array:
            sc_array.append(self.get_arg_template("OpenVPN", arg1="ALL", arg2="ALL"))
        return sc_array

class special_supermicro(special_base):
    def _call(self):
        # parameter list
        para_list = ["num_ibqdr", "num_power", "num_gigabit", "num_blade", "num_cmm"]
        para_dict = {}
        for para_name in para_list:
            r_para_name = self.real_parameter_name(para_name)
            try:
                cur_var = device_variable.objects.get(Q(device=self.host) & Q(name=r_para_name))
            except device_variable.DoesNotExist:
                self.log("variable %s does not exist, requesting info from BMC" % (r_para_name), logging_tools.LOG_LEVEL_WARN)
                break
            else:
                para_dict[para_name] = cur_var.get_value()
        if len(para_list) != len(para_dict):
            self.log("updating info from BMC")
            srv_result = self.collrelay("smcipmi",  "--ip", self.valid_ip, "counter", connect_to_localhost=True)
            # xpath string origins in supermiro_mod, server part (scmipmi_struct)
            r_dict = supermicro_mod.generate_dict(srv_result.xpath(None, ".//ns:output/text()")[0].split("\n"))
            for para_name in para_list:
                r_para_name = self.real_parameter_name(para_name)
                s_name = para_name.split("_", 1)[1]
                if s_name in r_dict:
                    v_val = r_dict[s_name]["present"]
                    self.log("parameter %s: %d" % (para_name, v_val))
                else:
                    v_val = 0
                    self.log("parameter %s: %d (not found in dict)" % (para_name, v_val), logging_tools.LOG_LEVEL_WARN)
                try:
                    cur_var = device_variable.objects.get(Q(device=self.host) & Q(name=r_para_name))
                except device_variable.DoesNotExist:
                    cur_var = device_variable(
                        device=self.host,
                        name=r_para_name,
                        is_public=True,
                        description="Read from BMC",
                        var_type="i",
                        val_int=v_val)
                else:
                    cur_var.set_value(v_val)
                cur_var.save()
                para_dict[para_name] = cur_var.get_value()
        self.log("para_dict: %s" % (", ".join(["%s=%d" % (key, value) for key, value in para_dict.iteritems()])))
        sc_array = []
        sc_array.append(self.get_arg_template("Overview", arg1="counter"))
        for ps_num in xrange(para_dict.get("num_power", 0)):
            sc_array.append(self.get_arg_template(
                "Power supply %2d" % (ps_num + 1),
                arg1="power %d" % (ps_num + 1)
            )
                            )
        for blade_num in xrange(para_dict.get("num_blade", 0)):
            sc_array.append(self.get_arg_template(
                "Blade %2d" % (blade_num + 1),
                arg1="blade %d" % (blade_num + 1)
            )
                            )
        return sc_array
    
class special_disc_all(special_base):
    def _call(self):
        sc_array = [self.get_arg_template("All partitions", arg3="ALL")]
        return sc_array

class special_disc(special_base):
    def _call(self):
        part_dev = self.host.partdev
        df_settings_dir = "%s/etc/df_settings" % (global_config["MD_BASEDIR"])
        df_sd_ok = os.path.isdir(df_settings_dir)
        self.log("part_dev '%s', df_settings_dir is '%s' (%s)" % (
            part_dev or "NOT SET (Empty)",
            df_settings_dir,
            "OK" if df_sd_ok else "not reachable"))
        first_disc = None
        part_list = []
        #print self.get_parameter("num_discs", "df", "/dev/sda1")
        #print self.get_parameter("num_discs", ".//ns:load1", "load")
        for part_p in partition.objects.filter(Q(partition_disc__partition_table=self.host.act_partition_table)).select_related(
            "partition_fs").order_by(
                "partition_disc__disc",
                "pnum"):
            if part_p.partition_fs.hexid == "82":
                # swap partiton
                pass
            else:
                act_disc, act_pnum = (part_p.partition_disc.disc, part_p.pnum)
                if not first_disc:
                    first_disc = act_disc
                if act_disc == first_disc and part_dev:
                    act_disc = part_dev
                part_pf = "p" if ("cciss" in act_disc or "ida" in act_disc) else ""
                act_part = "%s%s%d" % (act_disc, part_pf, act_pnum)
                # which partition to check
                check_part = act_part
                # check for lut_blob
                lut_blob = None#part_p.get("lut_blob", None)
                #if lut_blob:
                #    lut_blob = process_tools.net_to_sys(lut_blob)
                #    if lut_blob:
                #        if lut_blob.has_key("id"):
                #            scsi_id = [act_id for act_id in lut_blob["id"] if act_id.startswith("scsi")]
                #            if scsi_id:
                #                scsi_id = scsi_id[0]
                #                check_part = "/dev/disk/by-id/%s" % (scsi_id)
                if check_part.startswith("/"):
                    warn_level, crit_level = (
                        part_p.warn_threshold,
                        part_p.crit_threshold)
                    # if not set use 100 as warn/crit level
                    warn_level_str, crit_level_str = (
                        "%d" % (warn_level if warn_level else 100),
                        "%d" % (crit_level if crit_level else 100))
                    part_list.append((part_p.mountpoint,
                                      check_part, warn_level_str, crit_level_str))
                else:
                    self.log("Diskcheck on host %s requested an illegal partition %s -> skipped" % (self.host["name"], act_part), logging_tools.LOG_LEVEL_WARN)
        # LVM-partitions
        for lvm_part in lvm_lv.objects.filter(Q(lvm_vg__partition_table=self.host.act_partition_table)).select_related("lvm_vg").order_by("name"):
            if lvm_part.mountpoint:
                warn_level, crit_level = (lvm_part.warn_threshold or 0,
                                          lvm_part.crit_threshold or 0)
                warn_level_str, crit_level_str = (
                    "%d" % (warn_level if warn_level else 100),
                    "%d" % (crit_level if crit_level else 100))
                part_list.append((
                    "%s (LVM)" % (lvm_part.mountpoint),
                    "/dev/mapper/%s-%s" % (lvm_part.lvm_vg.name, lvm_part.name),
                    warn_level_str,
                    crit_level_str))
        # manual setting-dict for df
        set_dict = {}
        if df_sd_ok and os.path.isfile("%s/%s" % (df_settings_dir, self.host.name)):
            lines = [line for line in file("%s/%s" % (df_settings_dir, self.host.name), "r").read().split("\n") if line.strip() and not line.strip().startswith("#")]
            for line in lines:
                parts = line.strip().split()
                if len(parts) == 3:
                    if parts[0].startswith("/") and parts[1].isdigit() and parts[2].isdigit():
                        set_dict[parts[0]] = (int(parts[1]), int(parts[2]))
        sc_array = []
        for info_name, p_name, w_lev, c_lev in part_list:
            if p_name in set_dict:
                w_lev, c_lev = set_dict[p_name]
                self.log("    setting w/c to %d/%d" % (w_lev, c_lev))
                w_lev, c_lev = (str(w_lev) if w_lev > 0 else "", str(c_lev) if c_lev > 0 else "")
            self.log("  P: %-40s: %-40s (w: %-5s, c: %-5s)" % (
                info_name,
                p_name,
                w_lev or "N/S",
                c_lev or "N/S"))
            sc_array.append(self.get_arg_template(info_name, arg3=p_name, w=w_lev, c=c_lev))
        return sc_array
    
class special_net(special_base):
    def _call(self):
        sc_array = []
        eth_check = True if re.match(".*ethtool.*", self.s_check["command_name"]) else False
        virt_check = re.compile("^.*:\S+$")
        self.log("eth_check is %s" % ("on" if eth_check else "off"))
        # never check duplex and stuff for a loopback-device
        if eth_check:
            nd_list = netdevice.objects.exclude(Q(devname='lo')).filter(Q(device=self.host) & Q(netdevice_speed__check_via_ethtool=True)).order_by("devname").select_related("netdevice_speed")
        else:
            nd_list = netdevice.objects.filter(Q(device=self.host) & (Q(devname='lo') | Q(netdevice_speed__check_via_ethtool=False)))
        for net_dev in nd_list:
            if not virt_check.match(net_dev.devname):
                name_with_descr = "%s%s" % (
                    net_dev.devname,
                    " (%s)" % (net_dev.description) if net_dev.description else "")
                cur_temp = self.get_arg_template(
                    name_with_descr,
                    w="%.0f" % (net_dev.netdevice_speed.speed_bps * 0.9),
                    c="%.0f" % (net_dev.netdevice_speed.speed_bps * 0.95),
                    arg_1=net_dev.devname,
                )
                if eth_check:
                    cur_temp["duplex"] = net_dev.netdevice_speed.full_duplex and "full" or "half"
                    cur_temp["s"]      = "%d" % (net_dev.netdevice_speed.speed_bps)
                self.log(" - netdevice %s with %s: %s" % (
                    name_with_descr,
                    logging_tools.get_plural("option", len(cur_temp.argument_names)),
                    ", ".join(cur_temp.argument_names)))
                sc_array.append(cur_temp)
                #sc_array.append((name_with_descr, eth_opts))
        return sc_array

class special_libvirt(special_base):
    def _call(self):
        sc_array = []
        srv_result = self.collrelay("domain_overview")
        if srv_result is not None:
            if "domain_overview" in srv_result:
                domain_info = srv_result["domain_overview"]
                if "running" in domain_info and "defined" in domain_info:
                    domain_info = domain_info["running"]
                # build sc_array
                for inst_id in domain_info:
                    d_dict = domain_info[inst_id]
                    sc_array.append(
                        self.get_arg_template(
                            "Domain %s" % (d_dict["name"]),
                            arg1=d_dict["name"])
                    )
        return sc_array
        
class special_eonstor(special_base):
    class Meta:
        retries = 4
    def _call(self):
        sc_array = []
        srv_reply = self.snmprelay(
            "eonstor_get_counter",
            snmp_community="public",
            snmp_version="1")
        if srv_reply and "eonstor_info" in srv_reply:
            info_dict = srv_reply["eonstor_info"]
            # disks
            for disk_id in sorted(info_dict.get("disc_ids", [])):
                sc_array.append(("Disc %2d" % (disk_id), ["eonstor_disc_info", "%d" % (disk_id)]))
            # lds
            for ld_id in sorted(info_dict.get("ld_ids", [])):
                sc_array.append(("LD %2d" % (ld_id), ["eonstor_ld_info", "%d" % (ld_id)]))
            # env_dicts
            for env_dict_name in sorted(info_dict.get("ent_dict", {}).keys()):
                env_dict = info_dict["ent_dict"][env_dict_name]
                for idx in sorted(env_dict.keys()):
                    nag_name = env_dict[idx]
                    add_check = True
                    # get info for certain environment types
                    if env_dict_name in ["ups", "bbu"]:
                        act_com = "eonstor_%s_info" % (env_dict_name)
                        srv_reply = self.snmprelay(
                            act_com,
                            "%d" % (idx),
                            snmp_version="1",
                            snmp_community="public")
                        if srv_reply and "eonstor_info:state" in srv_reply:
                            act_state = int(srv_reply["eonstor_info:state"].text)
                            self.log("state for %s:%d is %d" % (act_com, idx, act_state))
                            if env_dict_name == "ups":
                                # check for inactive psus
                                if act_state & 128:
                                    self.log("disabling psu with idx %d because not present" % (idx),
                                             logging_tools.LOG_LEVEL_ERROR)
                                    add_check = False
                            elif env_dict_name == "bbu":
                                if act_state & 128:
                                    self.log("disabling bbu with idx %d because not present" % (idx),
                                             logging_tools.LOG_LEVEL_ERROR)
                                    add_check = False
                    if add_check:
                        if not nag_name.lower().startswith(env_dict_name):
                            nag_name = "%s %s" % (env_dict_name, nag_name)
                        sc_array.append(
                            self.get_arg_template(
                                nag_name,
                                # not correct, fixme
                                arg1="eonstor_%s_info" % (env_dict_name),
                                arg2="%d" % (idx)
                            )
                        )
        # rewrite sc_array to include community and version
        #sc_array = [(name, ["", ""] + var_list) for name, var_list in sc_array]
        self.log("sc_array has %s" % (logging_tools.get_plural("entry", len(sc_array))))
        return sc_array
        
if __name__ == "__main__":
    print "Loadable module, exiting"
    sys.exit(0)
    