#!/usr/bin/python-init -Ot
#
# Copyright (C) 2009 Andreas Lang-Nevyjel, init.at
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
import limits
import hm_classes
import pprint
import logging_tools
import process_tools
import time
import socket

class my_modclass(hm_classes.hm_fileinfo):
    def __init__(self, **args):
        hm_classes.hm_fileinfo.__init__(self,
                                        "snmp",
                                        "tools for sending snmp_requests to network devices",
                                        **args)
        self.host_dict = {}
    def process_client_args(self, opts, hmb):
        ok, why = (1, "")
        my_lim = limits.limits()
        my_lim.set_add_var("community", "public")
        my_lim.set_add_var("version", 1)
        my_lim.set_add_var("timeout", 30)
        my_lim.set_add_var("scheme", "")
        for opt, arg in opts:
            #print opt, arg
            if opt == "-C":
                my_lim.set_add_var("community", arg)
            elif opt == "-w":
                my_lim.set_warn_val(arg)
            elif opt == "-c":
                my_lim.set_crit_val(arg)
            elif opt == "-V":
                try:
                    my_lim.set_add_var("version", int(arg))
                except:
                    ok, why = (False, "error parsing version '%s'" % (arg))
            elif opt == "-t":
                try:
                    my_lim.set_add_var("timeout", int(arg))
                except:
                    ok, why = (False, "error parsing timeout '%s'" % (arg))
            elif opt == "-S":
                my_lim.set_add_var("scheme", arg)
            elif opt.startswith("--arg"):
                my_lim.set_add_var(opt[2:], arg)
            elif opt == "--raw":
                my_lim.set_add_var(opt[2:], True)
        return ok, why, my_lim
    def get_all_schemes(self):
        return sorted([name[:-7] for name in globals() if name.endswith("_scheme")])
    def get_scheme(self, scheme_name):
        full_name = "%s_scheme" % (scheme_name)
        if full_name in globals():
            new_scheme = globals()[full_name]()
            new_scheme.set_module_info(self)
            return new_scheme
        else:
            return None
    def get_host_object(self, host_name, host_ip):
        if not (host_name, host_ip) in self.host_dict:
            new_host_object = host_object(host_name, host_ip)
            self.log("Initialised new host_object '%s' (IP %s)" % (host_name, host_ip))
            self.host_dict[(host_name, host_ip)] = new_host_object
        return self.host_dict[(host_name, host_ip)]

class snmp_command(hm_classes.hmb_command):
    def __init__(self, **args):
        hm_classes.hmb_command.__init__(self, "snmp", **args)
        self.help_str = "queries the given host via a given SNMP-scheme"
        self.short_client_info = "OPTIONS"
        self.long_client_info = "OPTIONS is a list of snmp_options, depending on the scheme, common to all is -C community, -V version, -t timeout and -S scheme"
        self.short_client_opts = "C:V:t:S:w:c:"
        self.long_client_opts = ["arg0=", "arg1=", "arg2=", "raw"]
        self.relay_call = True
        self.special_hook = "snmp"
    def client_call(self, result, parsed_coms):
        return limits.nag_STATE_OK, result

class cache_object(object):
    caches_total = 0
    caches_open = 0
    def __init__(self, max_timeout):
        cache_object.caches_open += 1
        cache_object.caches_total += 1
        print time.ctime(), "new cache_object, %d total, %d open" % (cache_object.caches_total,
                                                                     cache_object.caches_open)
        self.__max_timeout = max_timeout
        self.__last_set = time.time() - 2 * self.__max_timeout
        self.__pending = False
        self.__cached_object = None
        self.__any_set = False
    def __del__(self):
        cache_object.caches_open -= 1
        print time.ctime(), "del cache_object, %d total, %d open" % (cache_object.caches_total,
                                                                     cache_object.caches_open)
    def set_object(self, obj):
        self.__cached_object = obj
        self.__last_set = time.time()
        self.__pending = False
        # any object set
        self.__any_set = True
    def timeout(self):
        # timeout while waiting for request
        self.__pending = False
    def object_valid(self):
        return self.__any_set
    def get_object(self):
        return self.__cached_object
    def is_valid(self):
        return abs(time.time() - self.__last_set) < self.__max_timeout
    def is_pending(self):
        return self.__pending
    def set_pending(self):
        self.__pending = True
        
class host_object(object):
    hosts_total = 0
    hosts_open = 0
    def __init__(self, name, ip):
        host_object.hosts_total += 1
        host_object.hosts_open += 1
        print time.ctime(), "new host_object, %d total, %d open" % (host_object.hosts_total,
                                                                    host_object.hosts_open)
        self.name = name
        self.ip   = ip
        # info dict, to save various information (trunk info, ...)
        self.info_dict = {}
    def __del__(self):
        host_object.hosts_open -= 1
        print time.ctime(), "del host_object, %d total, %d open" % (host_object.hosts_total,
                                                                    host_object.hosts_open)

class snmp_request(object):
    def __init__(self, r_type, oid_list, **args):
        print time.ctime(), "new snmp_req"
        self.request_type = r_type
        self.oid_list = oid_list
        self.cb_func = args.get("cb_func", None)
    def __del__(self):
        print time.ctime(), "del snmp_req"
        
class snmp_scheme(object):
    schemes_total = 0
    schemes_open = 0
    def __init__(self, name, max_steps):
        snmp_scheme.schemes_open += 1
        snmp_scheme.schemes_total += 1
        print time.ctime(), "new snmp_scheme"
        self.name = name
        self.step, self.max_steps = (0, max_steps)
        self.snmp_request, self.snmp_result = ({}, {})
        self.finished = False
        self.send_early_return = False
        self.set_state()
    def __del__(self):
        snmp_scheme.schemes_open -= 1
        print time.ctime(), "del snmp_scheme, %d total, %d open" % (snmp_scheme.schemes_total,
                                                                    snmp_scheme.schemes_open)
    def set_arguments(self, args):
        self.arguments = args
    def set_module_info(self, mod_info):
        self.module_info = mod_info
    def set_host_ip(self, host_name, host_ip):
        self.host_object = self.module_info.get_host_object(host_name, host_ip)
        self._host_object_set()
    def _host_object_set(self):
        pass
    def set_state(self, state=limits.nag_STATE_CRITICAL, result="result not processed"):
        self.__state = (state, result)
    def get_state(self):
        return self.__state
    def get(self):
        if self.step < self.max_steps:
            # gets the next snmp-request
            self.__act_request = self.snmp_request[self.step]
        else:
            self.__act_request = None
        return self.__act_request
    def set(self, res_dict):
        self.snmp_result[self.step] = res_dict
        if len(self.__act_request.oid_list) != len(res_dict.keys()):
            # error, something missing
            self.set_state(limits.nag_STATE_CRITICAL, "something missing in step %d" % (self.step))
            self.finished = True
        else:
            if self.__act_request.cb_func:
                self.__act_request.cb_func(res_dict)
            self.step += 1
            if self.step == self.max_steps:
                self.finished = True
        return self.finished
    def remove(self):
        # remove references
        self.snmp_request, self.snmp_result = (None, None)
        self.arguments = None
        self.module_info, self.host_ip, self.host_object = (None, None, None)
        self.__act_request = None
    
class load_scheme(snmp_scheme):
    def __init__(self):
        snmp_scheme.__init__(self, "load", 3)
        # T for table, G for get
        self.snmp_request[0] = snmp_request("T", [(1, 3, 6, 1, 2, 1, 25, 2, 3, 1, 5)], cb_func=self._r0)
        self.snmp_request[1] = snmp_request("T", [(1, 3, 6, 1, 2, 1, 25, 2, 3, 1, 5)])
        self.snmp_request[2] = snmp_request("G", [(1, 3, 6, 1, 2, 1, 25, 2, 3, 1, 3, 37),
                                                  (1, 3, 6, 1, 2, 1, 25, 2, 3, 1, 3, 34)])
    def __del__(self):
        snmp_scheme.__del__(self)
    def _r0(self, res_dict):
        print "r0", res_dict.values()

def k_str(i_val):
    f_val = float(i_val)
    if f_val < 1024:
        return "%0.f kB" % (f_val)
    f_val /= 1024.
    if f_val < 1024.:
        return "%.2f MB" % (f_val)
    f_val /= 1024.
    return "%.2f GB" % (f_val)

class check_snmp_qos_scheme(snmp_scheme):
    def __init__(self):
        snmp_scheme.__init__(self, "check_snmp_qos")
    def __del__(self):
        snmp_scheme.__del__(self)

class port_info_scheme(snmp_scheme):
    def __init__(self):
        snmp_scheme.__init__(self, "port_info", 0)
        self.__th_mac  = (1, 3, 6, 1, 2, 1, 17, 4, 3, 1, 2)
        self.__th_type = (1, 3, 6, 1, 2, 1, 17, 4, 3, 1, 3)
    def __del__(self):
        snmp_scheme.__del__(self)
    def _host_object_set(self):
        use_cached = False
        pco = self.host_object.info_dict.get("port_dict", None)
        if not pco:
            pco = cache_object(120)
            self.host_object.info_dict["port_dict"] = pco
        #print self.host_object.name, pco.is_valid(), pco.object_valid(), pco.is_pending()
        if pco.is_valid():
            self._write_return()
        elif not pco.is_pending():
            # caching not pending
            pco.set_pending()
            self.max_steps = 1
            self.snmp_request[0] = snmp_request("T", [self.__th_mac,
                                                      self.__th_type], cb_func=self._port_info)
            if pco.object_valid():
                # any object valid, send early_return but continue to ask switch
                self.send_early_return = True
                self._write_return()
        elif pco.object_valid():
            # any object valid
            self._write_return()
        else:            
            # caching pending, wait
            self.set_state(limits.nag_STATE_WARNING, "waiting for cache")
    def _transform_macs(self, mac_list):
        arp_dict = process_tools.get_arp_dict()
        host_list, ip_list, new_mac_list = ([], [], [])
        for mac in mac_list:
            if mac in arp_dict:
                try:
                    host = socket.gethostbyaddr(arp_dict[mac])
                except:
                    ip_list.append(arp_dict[mac])
                else:
                    host_list.append(host[0])
            else:
                new_mac_list.append(mac)
        return sorted(new_mac_list), sorted(ip_list), sorted(host_list)
    def _port_info(self, in_dict):
        port_ref_dict = {}
        for key, value in in_dict[self.__th_mac].iteritems():
            mac = ":".join(["%02x" % (int(val)) for val in key.prettyPrint().split(".")])
            port_ref_dict.setdefault(int(value), []).append((mac, int(in_dict[self.__th_type].get(key, 5))))
        self.host_object.info_dict["port_dict"].set_object(port_ref_dict)
        self._write_return()
    def _write_return(self):
        if self.arguments.has_add_var("arg0"):
            p_num = self.arguments.get_add_var("arg0")
            try:
                p_num = int(p_num)
            except:
                self.set_state(limits.nag_STATE_CRITICAL, "error decoding port_num '%s': %s" % (p_num,
                                                                                                process_tools.get_except_info()))
            else:
                p_dict = self.host_object.info_dict["port_dict"].get_object()
                # check for trunks
                is_trunk_port = False
                trunk_dict = self.host_object.info_dict.get("trunk_info", {})
                if trunk_dict:
                    trunk_ports = sum([value.keys() for value in trunk_dict.values()], [])
                    if p_num in trunk_ports:
                        is_trunk_port = True
                        trunk_id = [key for key, value in trunk_dict.iteritems() if p_num in value.keys()][0]
                if is_trunk_port:
                    self.set_state(limits.nag_STATE_OK, "port %d: Trunk (ID %s)" % (p_num, str(trunk_id)))
                else:
                    macs = [mac for mac, p_type in p_dict.get(p_num, []) if p_type == 3]
                    if macs:
                        mac_list, ip_list, host_list = self._transform_macs(macs)
                        self.set_state(limits.nag_STATE_OK, "port %d (%s): %s" % (p_num,
                                                                                  ", ".join([logging_tools.get_plural(name, len(what_list)) for name, what_list in [("Host", host_list),
                                                                                                                                                                    ("IP"  , ip_list  ),
                                                                                                                                                                    ("MAC" , mac_list )] if len(what_list)]),
                                                                                  ", ".join(host_list + ip_list + mac_list)))
                    else:
                        self.set_state(limits.nag_STATE_OK, "port %d: ---" % (p_num))
        else:
            self.set_state(limits.nag_STATE_CRITICAL, "error Port missing")

class trunk_info_scheme(snmp_scheme):
    def __init__(self):
        snmp_scheme.__init__(self, "trunk_info", 0)
        self.__th0 = (1, 0, 8802, 1, 1, 2, 1, 4, 1, 1)
    def __del__(self):
        snmp_scheme.__del__(self)
    def _host_object_set(self):
        use_cached = False
        pco = self.host_object.info_dict.get("trunk_dict", None)
        if not pco:
            pco = cache_object(120)
            self.host_object.info_dict["trunk_dict"] = pco
        #print self.host_object.name, pco.is_valid(), pco.object_valid(), pco.is_pending()
        if pco.is_valid():
            self._write_return()
        elif not pco.is_pending():
            # caching not pending
            pco.set_pending()
            self.max_steps = 1
            self.snmp_request[0] = snmp_request("T", [self.__th0], cb_func=self._port_info)
            if pco.object_valid():
                # any object valid, send early_return but continue to ask switch
                self.send_early_return = True
                self._write_return()
        elif pco.object_valid():
            # any object valid
            self._write_return()
        else:            
            # caching pending, wait
            self.set_state(limits.nag_STATE_WARNING, "waiting for cache")
    def _port_info(self, in_dict):
        trunk_dict = {}
        for key, value in in_dict[self.__th0].iteritems():
            sub_idx, trunk_id, port_num, idx = key
            trunk_dict.setdefault(trunk_id, {}).setdefault(port_num, {})[sub_idx] = value
        self.host_object.info_dict["trunk_dict"].set_object(trunk_dict)
        self._write_return()
    def _write_return(self):
        trunk_dict = self.host_object.info_dict["trunk_dict"].get_object()
        t_array = []
        for t_key in sorted(trunk_dict.keys()):
            t_stuff = trunk_dict[t_key]
            t_ports = sorted(t_stuff.keys())
            try:
                port_map = dict([(port, int(t_stuff[port][7].prettyPrint()[1:-1])) for port in t_ports])
            except:
                t_array.append("error decoding port_num: %s" % (process_tools.get_except_info()))
            else:
                dest_name = t_stuff[t_ports[0]][9].prettyPrint()[1:-1]
                dest_hw   = t_stuff[t_ports[0]][10].prettyPrint()[1:-1]
                t_array.append("%s [%s]: %s to %s (%s)" % (logging_tools.get_plural("port", len(t_ports)),
                                                           str(t_key),
                                                           "/".join(["%d-%d" % (port, port_map[port]) for port in t_ports]),
                                                           dest_name,
                                                           dest_hw))
        self.host_object.info_dict["trunk_info"] = trunk_dict
        if t_array:
            self.set_state(limits.nag_STATE_OK, "%s: %s" % (logging_tools.get_plural("trunk", len(t_array)),
                                                            ", ".join(t_array)))
        else:
            self.set_state(limits.nag_STATE_OK, "no trunks")

class snmp_info_scheme(snmp_scheme):
    def __init__(self):
        snmp_scheme.__init__(self, "snmp_info", 1)
        # T for table, G for get
        self.__info_oid = (1, 3, 6, 1, 2, 1, 1)
        self.snmp_request[0] = snmp_request("T", [self.__info_oid], cb_func=self._info_dict)
    def __del__(self):
        snmp_scheme.__del__(self)
    def _info_dict(self, res_dict):
        use_dict = res_dict[self.__info_oid]
        ret_state = limits.nag_STATE_OK
        needed_keys = [(4, 0), (5, 0), (6, 0)]
        missing_keys = [key for key in needed_keys if not key in use_dict]
        if missing_keys:
            self.set_state(limits.nag_STATE_CRITICAL, "%s missing: %s" % (logging_tools.get_plural("key", len(missing_keys)),
                                                                          ", ".join([str(key) for key in sorted(missing_keys)])))
        else:
            self.set_state(ret_state, "%s: SNMP Info: contact %s, name %s, location %s" % (limits.get_state_str(ret_state),
                                                                                           use_dict[(4, 0)].prettyPrint(),
                                                                                           use_dict[(5, 0)].prettyPrint(),
                                                                                           use_dict[(6, 0)].prettyPrint()))
            
class usv_apc_load_scheme(snmp_scheme):
    def __init__(self):
        snmp_scheme.__init__(self, "usv_apc_load", 1)
        # T for table, G for get
        self.__output_oid = (1, 3, 6, 1, 4, 1, 318, 1, 1, 1, 4, 2)
        self.snmp_request[0] = snmp_request("T", [self.__output_oid], cb_func=self._info_dict)
    def __del__(self):
        snmp_scheme.__del__(self)
    def _info_dict(self, res_dict):
        WARN_LOAD, CRIT_LOAD = (70, 85)
        use_dict = res_dict[self.__output_oid]
        try:
            act_load = int(use_dict[(3, 0)])
        except KeyError:
            self.set_state(limits.nag_STATE_CRITICAL, "error getting load")
        else:
            ret_state, prob_f = (limits.nag_STATE_OK, [])
            if act_load > CRIT_LOAD:
                ret_state = max(ret_state, limits.nag_STATE_CRITICAL)
                prob_f.append("load is very high (> %d)" % (CRIT_LOAD))
            elif act_load > WARN_LOAD:
                ret_state = max(ret_state, limits.nag_STATE_WARNING)
                prob_f.append("load is high (> %d)" % (WARN_LOAD))
            self.set_state(ret_state, "%s: load is %d %%%s" % (limits.get_state_str(ret_state),
                                                               act_load,
                                                               ": %s" % ("; ".join(prob_f)) if prob_f else ""))

class usv_apc_output_scheme(snmp_scheme):
    def __init__(self):
        snmp_scheme.__init__(self, "usv_apc_output", 1)
        # T for table, G for get
        self.__output_oid = (1, 3, 6, 1, 4, 1, 318, 1, 1, 1, 4, 2)
        self.snmp_request[0] = snmp_request("T", [self.__output_oid], cb_func=self._info_dict)
    def __del__(self):
        snmp_scheme.__del__(self)
    def _info_dict(self, res_dict):
        MIN_HZ, MAX_HZ = (49, 52)
        MIN_VOLT, MAX_VOLT = (219, 235)
        out_dict = res_dict[self.__output_oid]
        out_freq, out_voltage = (int(out_dict[(2, 0)]),
                                 int(out_dict[(1, 0)]))
        ret_state, prob_f = (limits.nag_STATE_OK, [])
        if out_freq not in xrange(MIN_HZ, MAX_HZ):
            ret_state = max(ret_state, limits.nag_STATE_WARNING)
            prob_f.append("output frequency not ok [%d, %d]" % (MIN_HZ,
                                                                MAX_HZ))
        if out_voltage not in xrange(MIN_VOLT, MAX_VOLT):
            ret_state = max(ret_state, limits.nag_STATE_WARNING)
            prob_f.append("output voltage is not in range [%d, %d]" % (MIN_VOLT,
                                                                       MAX_VOLT))
        self.set_state(ret_state, "%s: output is %d V at %d Hz%s" % (limits.get_state_str(ret_state),
                                                                     out_voltage,
                                                                     out_freq,
                                                                     ": %s" % ("; ".join(prob_f)) if prob_f else ""))

class usv_apc_input_scheme(snmp_scheme):
    def __init__(self):
        snmp_scheme.__init__(self, "usv_apc_input", 1)
        # T for table, G for get
        self.__input_oid = (1, 3, 6, 1, 4, 1, 318, 1, 1, 1, 3, 2)
        self.snmp_request[0] = snmp_request("T", [self.__input_oid], cb_func=self._info_dict)
    def __del__(self):
        snmp_scheme.__del__(self)
    def _info_dict(self, res_dict):
        MIN_HZ, MAX_HZ = (49, 52)
        MIN_VOLT, MAX_VOLT = (216, 235)
        in_dict = res_dict[self.__input_oid]
        in_freq, in_voltage = (int(in_dict[(4, 0)]),
                               int(in_dict[(1, 0)]))
        ret_state, prob_f = (limits.nag_STATE_OK, [])
        if in_freq not in xrange(MIN_HZ, MAX_HZ):
            ret_state = max(ret_state, limits.nag_STATE_WARNING)
            prob_f.append("input frequency not ok [%d, %d]" % (MIN_HZ,
                                                               MAX_HZ))
        if in_voltage not in xrange(MIN_VOLT, MAX_VOLT):
            ret_state = max(ret_state, limits.nag_STATE_WARNING)
            prob_f.append("input voltage is not in range [%d, %d]" % (MIN_VOLT,
                                                                      MAX_VOLT))
        self.set_state(ret_state, "%s: input is %d V at %d Hz%s" % (limits.get_state_str(ret_state),
                                                                    in_voltage,
                                                                    in_freq,
                                                                    ": %s" % ("; ".join(prob_f)) if prob_f else ""))

class usv_apc_battery_scheme(snmp_scheme):
    def __init__(self):
        snmp_scheme.__init__(self, "usv_apc_battery", 1)
        # T for table, G for get
        self.__battery_oid = (1, 3, 6, 1, 4, 1, 318, 1, 1, 1, 2, 2)
        self.snmp_request[0] = snmp_request("T", [self.__battery_oid], cb_func=self._info_dict)
    def __del__(self):
        snmp_scheme.__del__(self)
    def _info_dict(self, res_dict):
        if self.arguments.has_add_var("arg0"):
            warn_temp = int(self.arguments.get_add_var("arg0"))
        else:
            warn_temp = 45
        if self.arguments.has_add_var("arg1"):
            crit_temp = int(self.arguments.get_add_var("arg1"))
        else:
            crit_temp = 50
        warn_load, crit_load = (90, 50)
        bat_dict = res_dict[self.__battery_oid]
        run_time, act_temp, act_load = (int(bat_dict[(3, 0)]),
                                        int(bat_dict[(2, 0)]),
                                        int(bat_dict[(1, 0)]))
        ret_state, prob_f = (limits.nag_STATE_OK, [])
        if act_temp > warn_temp:
            ret_state = max(ret_state, limits.nag_STATE_WARNING)
            prob_f.append("temperature is high (th %d)" % (warn_temp))
        if act_temp > crit_temp:
            ret_state = max(ret_state, limits.nag_STATE_CRITICAL)
            prob_f.append("temperature is very high (th %d)" % (crit_temp))
        if act_load < warn_load:
            ret_state = max(ret_state, limits.nag_STATE_WARNING)
            prob_f.append("not fully loaded (th %d)" % (warn_load))
        if act_load < crit_load:
            ret_state = max(ret_state, limits.nag_STATE_CRITICAL)
            prob_f.append("very low load (th %d)" % (crit_load))
        # run time in seconds
        run_time = run_time / 100.
        if run_time < 10 * 60:
            ret_state = max(ret_state, limits.nag_STATE_WARNING)
            prob_f.append("run time below 10 minutes")
        if run_time < 5 * 60:
            ret_state = max(ret_state, limits.nag_STATE_CRITICAL)
            prob_f.append("run time below 5 minutes")
        self.set_state(ret_state, "%s: bat temperatur is %d C, load is %d %%, support time is %s %s%s" % (limits.get_state_str(ret_state),
                                                                                                          act_temp,
                                                                                                          act_load,
                                                                                                          logging_tools.get_plural("min", int(run_time / 60)),
                                                                                                          logging_tools.get_plural("sec", int(run_time % 60)),
                                                                                                          ": %s" % ("; ".join(prob_f)) if prob_f else ""))
        
class linux_memory_scheme(snmp_scheme):
    def __init__(self):
        snmp_scheme.__init__(self, "linux_memory", 1)
        # T for table, G for get
        self.__mem_oid = (1, 3, 6, 1, 2, 1, 25, 2, 3, 1)
        self.centos = False
        self.snmp_request[0] = snmp_request("T", [self.__mem_oid], cb_func=self._mem_dict)
    def __del__(self):
        snmp_scheme.__del__(self)
    def _mem_dict_centos(self, res_dict):
        use_dict = dict([(key[0], value) for key, value in res_dict[self.__mem_oid].iteritems()])
        phys_total, phys_free = (use_dict[5], use_dict[6])
        swap_total, swap_free = (use_dict[3], use_dict[4])
        try:
            cached, buffers = (use_dict[15], use_dict[14])
        except:
            cached, buffers = (0, 0)
        cb_size = cached + buffers
        phys_free += cb_size
        phys_used = phys_total - phys_free
        swap_used = swap_total - swap_free
        all_used = phys_used + swap_used
        all_total, all_free = (phys_total + swap_total,
                               phys_free + swap_free)
        if phys_total == 0:
            memp = 100
        else:
            memp = 100 * phys_used / phys_total
        if all_total == 0:
            allp = 100
        else:
            allp = 100 * all_used / all_total
        state = "OK"
        self.set_state(limits.nag_STATE_OK, "%s: meminfo: %d %% of %s phys, %d %% of %s tot" % (state, memp, k_str(phys_total), allp, k_str(all_total)))
    def _mem_dict(self, res_dict):
        #return
        use_dict = res_dict[self.__mem_oid]
        try:
            use_dict = dict([(use_dict[(3, key)].prettyPrint()[1:-1].lower(), {"allocation_units" : use_dict[(4, key)],
                                                                               "size"             : use_dict[(5, key)],
                                                                               "used"             : use_dict.get((6, key), None)
                                                                               }) for key in [key[1] for key in use_dict.keys() if key[0] == 1] if not use_dict[(3, key)].prettyPrint().startswith("'/")])
            if "cached memory" in use_dict:
                phys_total, phys_used = (use_dict["physical memory"]["size"],
                                         use_dict["physical memory"]["used"])
                cached  = use_dict["cached memory"]["size"]
                buffers = use_dict["memory buffers"]["size"]
                cb_size = cached + buffers
                swap_total, swap_used = (use_dict["swap space"]["size"],
                                         use_dict["swap space"]["used"])
                # sub buffers and cache from phys_used
                phys_used -= cb_size
                all_used = phys_used + swap_used
                phys_free, swap_free = (phys_total - phys_used,
                                        swap_total - swap_used)
                all_total, all_free = (phys_total + swap_total,
                                       phys_free + swap_free)
                if phys_total == 0:
                    memp = 100
                else:
                    memp = 100 * phys_used / phys_total
                if all_total == 0:
                    allp = 100
                else:
                    allp = 100 * all_used / all_total
                state = "OK"
                self.set_state(limits.nag_STATE_OK, "%s: meminfo: %d %% of %s phys, %d %% of %s tot" % (state, memp, k_str(phys_total), allp, k_str(all_total)))
            else:
                # centos type, ask again
                self.__mem_oid = (1, 3, 6, 1, 4, 1, 2021, 4)
                self.step -= 1
                self.centos = True
                self.snmp_request[0] = snmp_request("T", [self.__mem_oid], cb_func=self._mem_dict_centos)
        except KeyError:
            self.set_state(limits.nag_STATE_WARNING,
                           "Warning: error getting key (%s)" % (process_tools.get_except_info()))

class eonstor_object(object):
    def __init__(self, type_str, in_dict, **args):
        print time.ctime(), "new eonstor_object"
        self.type_str = type_str
        self.name = in_dict[8].prettyPrint()
        self.state = int(in_dict[args.get("state_key", 13)])
        # default values
        self.nag_state, self.state_strs = (limits.nag_STATE_OK, [])
        self.out_string = ""
        self.long_string = ""
    def __del__(self):
        print time.ctime(), "del eonstor_object"
    def set_error(self, err_str):
        self.nag_state = max(self.nag_state, limits.nag_STATE_CRITICAL)
        self.state_strs.append(err_str)
    def set_warn(self, warn_str):
        self.nag_state = max(self.nag_state, limits.nag_STATE_WARNING)
        self.state_strs.append(warn_str)
    def get_state_str(self):
        return ", ".join(self.state_strs) or "ok"
    def get_ret_str(self, **args):
        out_str = self.long_string if (self.long_string and args.get("long_version", False)) else self.out_string
        if self.nag_state == limits.nag_STATE_OK and out_str:
            return "%s: %s" % (self.name,
                               out_str)
        elif self.nag_state:
            return "%s: %s%s" % (self.name,
                                 self.get_state_str(),
                                 " (%s)" % (out_str) if out_str else "")
        else:
            return ""

class eonstor_disc(eonstor_object):
    lu_dict = {0 : ("New Drive", limits.nag_STATE_OK),
               1 : ("On-Line Drive", limits.nag_STATE_OK),
               2 : ("Used Drive", limits.nag_STATE_OK),
               3 : ("Spare Drive", limits.nag_STATE_OK),
               4 : ("Drive Initialization in Progress", limits.nag_STATE_WARNING),
               5 : ("Drive Rebuild in Progress", limits.nag_STATE_WARNING),
               6 : ("Add Drive to Logical Drive in Progress", limits.nag_STATE_WARNING),
               9 : ("Global Spare Drive", limits.nag_STATE_OK),
               int("11", 16) : ("Drive is in process of Cloning another Drive", limits.nag_STATE_WARNING),
               int("12", 16) : ("Drive is a valid Clone of another Drive", limits.nag_STATE_OK),
               int("13", 16) : ("Drive is in process of Copying from another Drive", limits.nag_STATE_WARNING),
               int("3f", 16) : ("Drive Absent", limits.nag_STATE_WARNING),
               #int("8x", 16) : "SCSI Device (Type x)",
               int("fc", 16) : ("Missing Global Spare Drive", limits.nag_STATE_CRITICAL),
               int("fd", 16) : ("Missing Spare Drive", limits.nag_STATE_CRITICAL),
               int("fe", 16) : ("Missing Drive", limits.nag_STATE_CRITICAL),
               int("ff", 16) : ("Failed Drive",  limits.nag_STATE_CRITICAL)}
    def __init__(self, in_dict):
        eonstor_object.__init__(self, "disc", in_dict, state_key=11)
        disk_num = int(in_dict[13])
        self.name = "Disc%d" % (disk_num)
        if self.state in self.lu_dict:
            state_str, state_val = self.lu_dict[self.state]
            if state_val == limits.nag_STATE_WARNING:
                self.set_warn(state_str)
            elif state_val == limits.nag_STATE_CRITICAL:
                self.set_error(state_str)
        else:
            self.set_warn("unknown state %d" % (self.state))
        # generate long string
        # ignore SCSIid and SCSILun
        disk_size = (2 ** int(in_dict[8])) * int(in_dict[7])
        vers_str = "%s (%s)" % ((" ".join((in_dict[15].prettyPrint()).split())).strip(),
                                (in_dict[16].prettyPrint()).strip())
        self.long_string = "%s, LC %d, PC %d, %s" % (logging_tools.get_size_str(disk_size, divider=1000),
                                                     int(in_dict[2]),
                                                     int(in_dict[3]),
                                                     vers_str)
    def __repr__(self):
        return "%s, state 0x%x (%d, %s)" % (self.name, self.state, self.nag_state, self.get_state_str())

class eonstor_ld(eonstor_object):
    lu_dict = {0 : ("Good", limits.nag_STATE_OK),
               1 : ("Rebuilding", limits.nag_STATE_WARNING),
               2 : ("Initializing", limits.nag_STATE_WARNING),
               3 : ("Degraded", limits.nag_STATE_CRITICAL),
               4 : ("Dead", limits.nag_STATE_CRITICAL),
               5 : ("Invalid", limits.nag_STATE_CRITICAL),
               6 : ("Incomplete", limits.nag_STATE_CRITICAL),
               7 : ("Drive missing", limits.nag_STATE_CRITICAL)}
    def __init__(self, in_dict):
        eonstor_object.__init__(self, "ld", in_dict, state_key=7)
        self.name = "LD"
        state_str, state_val = self.lu_dict[int(in_dict[6]) & 7]
        if state_val == limits.nag_STATE_WARNING:
            self.set_warn(state_str)
        elif state_val == limits.nag_STATE_CRITICAL:
            self.set_error(state_str)
        if self.state & 1:
            self.set_warn("rebuilding")
        if self.state & 2:
            self.set_warn("expanding")
        if self.state & 4:
            self.set_warn("adding drive(s)")
        if self.state & 64:
            self.set_warn("SCSI drives operation paused")
        # opmode
        op_mode = int(in_dict[5]) & 15
        op_mode_str = {0 : "Single Drive",
                       1 : "NON-RAID",
                       2 : "RAID 0",
                       3 : "RAID 1",
                       4 : "RAID 3",
                       5 : "RAID 4",
                       6 : "RAID 5"}.get(op_mode, "NOT DEFINED")
        op_mode_extra_bits = int(in_dict[5]) - op_mode
        ld_size = (2 ** int(in_dict[4])) * (int(in_dict[3]))
        vers_str = "id %d" % (int(in_dict[2]))
        drv_total, drv_online, drv_spare, drv_failed = (int(in_dict[8]),
                                                        int(in_dict[9]),
                                                        int(in_dict[10]),
                                                        int(in_dict[11]))
        if drv_failed:
            self.set_error("%s failed" % (logging_tools.get_plural("drive", drv_failed)))
        drv_info = "%d total, %d online%s" % (drv_total,
                                              drv_online,
                                              ", %d spare" % (drv_spare) if drv_spare else "")
        self.long_string = "%s (0x%x) %s, %s, %s" % (op_mode_str,
                                                     op_mode_extra_bits,
                                                     logging_tools.get_size_str(ld_size, divider=1000),
                                                     drv_info,
                                                     vers_str)
    def __repr__(self):
        return "%s, state 0x%x (%d, %s)" % (self.name, self.state, self.nag_state, self.get_state_str())

class eonstor_slot(eonstor_object):
    def __init__(self, in_dict):
        eonstor_object.__init__(self, "slot", in_dict)
        if self.state & 1:
            self.set_error("Sense circuitry malfunction")
        if self.state & 2:
            self.set_error("marked BAD, waiting for replacement")
        if self.state & 4:
            self.set_warn("not activated")
        if self.state & 64:
            self.set_warn("ready for insertion / removal")
        if self.state & 128:
            self.set_warn("slot is empty")
    def __del__(self):
        eonstor_object.__del__(self)
    def __repr__(self):
        return "slot %s, state 0x%x (%d, %s)" % (self.name, self.state, self.nag_state, self.get_state_str())

class eonstor_psu(eonstor_object):
    def __init__(self, in_dict):
        eonstor_object.__init__(self, "PSU", in_dict)
        if self.state & 1:
            self.set_error("PSU malfunction")
        if self.state & 64:
            self.set_warn("PSU is OFF")
        if self.state & 128:
            self.set_warn("PSU not present")
    def __del__(self):
        eonstor_object.__del__(self)
    def __repr__(self):
        return "PSU %s, state 0x%x (%d, %s)" % (self.name, self.state, self.nag_state, self.get_state_str())

class eonstor_bbu(eonstor_object):
    def __init__(self, in_dict):
        eonstor_object.__init__(self, "BBU", in_dict)
        if self.state & 1:
            self.set_error("BBU malfunction")
        if self.state & 2:
            self.set_warn("BBU charging")
        if self.state & 64:
            self.set_warn("BBU disabled")
        if self.state & 128:
            self.set_warn("BBU not present")
        # check load state
        load_state = (self.state >> 2) & 7
        if load_state == 1:
            self.set_warn("not fully charged")
        elif load_state == 2:
            self.set_error("charge critically low")
        elif load_state == 3:
            self.set_error("completely drained")
    def __del__(self):
        eonstor_object.__del__(self)
    def __repr__(self):
        return "BBU %s, state 0x%x (%d, %s)" % (self.name, self.state, self.nag_state, self.get_state_str())

class eonstor_ups(eonstor_object):
    def __init__(self, in_dict):
        eonstor_object.__init__(self, "UPS", in_dict)
        if self.state & 128:
            self.set_warn("UPS not present")
        else:
            if self.state & 1:
                self.set_error("UPS malfunction")
            if self.state & 2:
                self.set_error("AC Power not present")
            if self.state & 64:
                self.set_warn("UPS is off")
        # check load state
        load_state = (self.state >> 2) & 7
        if load_state == 1:
            self.set_warn("not fully charged")
        elif load_state == 2:
            self.set_error("charge critically low")
        elif load_state == 3:
            self.set_error("completely drained")
    def __del__(self):
        eonstor_object.__del__(self)
    def __repr__(self):
        return "UPS %s, state 0x%x (%d, %s)" % (self.name, self.state, self.nag_state, self.get_state_str())

class eonstor_fan(eonstor_object):
    def __init__(self, in_dict):
        eonstor_object.__init__(self, "Fan", in_dict)
        if self.state & 1:
            self.set_error("Fan malfunction")
        if self.state & 64:
            self.set_warn("Fan is OFF")
        if self.state & 128:
            self.set_warn("Fan not present")
        if not self.state:
            self.out_string = "%.2f RPM" % (float(in_dict[9]) / 1000)
    def __del__(self):
        eonstor_object.__del__(self)
    def __repr__(self):
        return "fan %s, state 0x%x (%d, %s), %s" % (self.name, self.state, self.nag_state, self.get_state_str(), self.out_string)

class eonstor_temperature(eonstor_object):
    def __init__(self, in_dict):
        eonstor_object.__init__(self, "temp", in_dict)
        if self.state & 1:
            self.set_error("Sensor malfunction")
        if self.state & 64:
            self.set_warn("Sensor not active")
        if self.state & 128:
            self.set_warn("Sensor not present")
        # check threshold
        sensor_th = (self.state >> 1) & 7
        if sensor_th in [2, 3]:
            self.set_warn("Sensor %s warning" % ({2 : "cold",
                                                  3 : "hot"}[sensor_th]))
        elif sensor_th in [4, 5]:
            self.set_error("Sensor %s limit exceeded" % ({4 : "cold",
                                                          5 : "hot"}[sensor_th]))
        if not self.state and int(in_dict[9]):
            self.out_string = "%.2f C" % (float(in_dict[9]) / 1000000)
    def __del__(self):
        eonstor_object.__del__(self)
    def __repr__(self):
        return "temperature %s, state 0x%x (%d, %s), %s" % (self.name, self.state, self.nag_state, self.get_state_str(), self.out_string)
    
class eonstor_voltage(eonstor_object):
    def __init__(self, in_dict):
        eonstor_object.__init__(self, "Voltage", in_dict)
        if self.state & 1:
            self.set_error("Sensor malfunction")
        if self.state & 64:
            self.set_warn("Sensor not active")
        if self.state & 128:
            self.set_warn("Sensor not present")
        # check threshold
        sensor_th = (self.state >> 1) & 7
        if sensor_th in [2, 3]:
            self.set_warn("Sensor %s warning" % ({2 : "low",
                                                  3 : "high"}[sensor_th]))
        elif sensor_th in [4, 5]:
            self.set_error("Sensor %s limit exceeded" % ({4 : "low",
                                                          5 : "high"}[sensor_th]))
        if not self.state:
            self.out_string = "%.2f V" % (float(in_dict[9]) / 1000)
    def __del__(self):
        eonstor_object.__del__(self)
    def __repr__(self):
        return "voltage %s, state 0x%x (%d, %s), %s" % (self.name, self.state, self.nag_state, self.get_state_str(), self.out_string)
    
class eonstor_info_scheme(snmp_scheme):
    def __init__(self):
        snmp_scheme.__init__(self, "eonstor_info", 1)
        self.__th_system = (1, 3, 6, 1, 4, 1, 1714, 1, 9, 1)
        self.__th_disc   = (1, 3, 6, 1, 4, 1, 1714, 1, 6, 1)
        self.snmp_request[0] = snmp_request("T", [self.__th_system,
                                                  self.__th_disc], cb_func=self._dev_info)
    def __del__(self):
        snmp_scheme.__del__(self)
    def _dev_info(self, in_dict):
        pre_dict = {}
        for key, value in in_dict[self.__th_system].iteritems():
            sub_idx, part_idx = key
            pre_dict.setdefault(part_idx, {})[sub_idx] = value
        # device dict (also for discs)
        dev_dict = {}
        for dev_idx, dev_stuff in pre_dict.iteritems():
            if dev_stuff[6] == 17:
                # slot
                dev_dict[dev_idx] = eonstor_slot(dev_stuff)
            elif dev_stuff[6] == 2:
                # fan
                dev_dict[dev_idx] = eonstor_fan(dev_stuff)
            elif dev_stuff[6] == 3:
                # temperature
                dev_dict[dev_idx] = eonstor_temperature(dev_stuff)
            elif dev_stuff[6] == 1:
                # power supply
                dev_dict[dev_idx] = eonstor_psu(dev_stuff)
            elif dev_stuff[6] == 11:
                # battery backup unit
                dev_dict[dev_idx] = eonstor_bbu(dev_stuff)
            elif dev_stuff[6] == 4:
                # UPS
                dev_dict[dev_idx] = eonstor_ups(dev_stuff)
            elif dev_stuff[6] == 5:
                # voltage
                dev_dict[dev_idx] = eonstor_voltage(dev_stuff)
        pre_dict = {}
        for key, value in in_dict[self.__th_disc].iteritems():
            sub_idx, part_idx = key
            pre_dict.setdefault(part_idx, {})[sub_idx] = value
        for disc_idx, disc_stuff in pre_dict.iteritems():
            dev_dict["d%d" % (disc_idx)] = eonstor_disc(disc_stuff)
        ret_state, ret_field = (limits.nag_STATE_OK, [])
        for key in sorted(dev_dict.keys()):
            value = dev_dict[key]
            if value.nag_state:
                # only show errors and warnings
                ret_state = max(ret_state, value.nag_state)
                ret_field.append(value.get_ret_str())
        ret_field.sort()
        self.set_state(ret_state, "%s: %s" % (limits.get_state_str(ret_state),
                                              "; ".join(ret_field) or "no errors or warnings"))

class eonstor_proto_scheme(snmp_scheme):
    def __init__(self, name, **args):
        snmp_scheme.__init__(self, name, 1)
        self.__table_usage = {"sys"  : args.get("sys_table", True),
                              "disc" : args.get("disc_table", False),
                              "ld"   : args.get("ld_table", False)}
        self.table_header = {"sys"  : (1, 3, 6, 1, 4, 1, 1714, 1, 9, 1),
                             "disc" : (1, 3, 6, 1, 4, 1, 1714, 1, 6, 1),
                             "ld"   : (1, 3, 6, 1, 4, 1, 1714, 1, 2, 1)}
        self.max_steps = 0
    def __del__(self):
        snmp_scheme.__del__(self)
    def _host_object_set(self):
        pco = self.host_object.info_dict.get("eonstore_dict", None)
        if not pco:
            pco = cache_object(30)
            self.host_object.info_dict["eonstore_dict"] = pco
        #print self.host_object.name, pco.is_valid(), pco.object_valid(), pco.is_pending()
        if pco.is_valid():
            self._write_return()
        elif not pco.is_pending():
            # caching not pending
            pco.set_pending()
            self.max_steps = 1
            headers = [table_header for key, table_header in self.table_header.iteritems()]
            self.snmp_request[0] = snmp_request("T", headers, cb_func=self._set_dict)
            if pco.object_valid():
                # any object valid, send early_return but continue to ask switch
                self.send_early_return = True
                self._write_return()
        elif pco.object_valid():
            # any object valid
            self._write_return()
        else:            
            # caching pending, wait
            self.set_state(limits.nag_STATE_WARNING, "waiting for cache")
    def _set_dict(self, in_dict):
        pre_dict = {"sys"  : {},
                    "disc" : {},
                    "ld"   : {}}
        for table_key, table_usage in self.__table_usage.iteritems():
            for key, value in in_dict[self.table_header[table_key]].iteritems():
                sub_idx, part_idx = key
                pre_dict[table_key].setdefault(part_idx, {})[sub_idx] = value
        #for key, value in in_dict[self.th_disc].iteritems():
            #sub_idx, part_idx = key
            #pre_dict["disc"].setdefault(part_idx, {})[sub_idx] = value
        #for key, value in in_dict[self.ld_table].iteritems():
            #sub_idx, part_idx = key
            #pre_dict["ld"].setdefault(part_idx, {})[sub_idx] = value
        self.host_object.info_dict["eonstore_dict"].set_object(pre_dict)
        self._write_return()
    def _write_return(self):
        if self.__table_usage["disc"]:
            self.handle_dict(self.host_object.info_dict["eonstore_dict"].get_object()["disc"])
        elif self.__table_usage["ld"]:
            self.handle_dict(self.host_object.info_dict["eonstore_dict"].get_object()["ld"])
        else:
            self.handle_dict(self.host_object.info_dict["eonstore_dict"].get_object()["sys"])
    def _generate_return(self, dev_dict):
        if self.arguments.has_add_var("arg0"):
            try:
                dev_idx = int(self.arguments.get_add_var("arg0"))
            except:
                dev_idx = 0
        else:
            dev_idx = 0
        ret_state, ret_field = (limits.nag_STATE_OK, [])
        raw_dict = {}
        if dev_idx:
            if dev_idx in dev_dict:
                if self.arguments.has_add_var("raw"):
                    raw_dict = dict([(key, int(value) if key not in [8] else value.prettyPrint()) for key, value in self.host_object.info_dict["eonstore_dict"].get_object()["sys"][dev_idx].iteritems()])
                else:
                    value = dev_dict[dev_idx]
                    ret_state = value.nag_state
                    ret_field.append(value.get_ret_str(long_version=True) or "%s is OK" % (value.name))
            else:
                ret_state = limits.nag_STATE_CRITICAL
                ret_field.append("idx %d not found in dict" % (dev_idx))
        else:
            for key in sorted(dev_dict.keys()):
                value = dev_dict[key]
                ret_state = max(ret_state, value.nag_state)
                act_ret_str = value.get_ret_str() or "%s is OK" % (value.name)
                ret_field.append(act_ret_str)
            ret_field.sort()
        if raw_dict:
            self.set_state(limits.nag_STATE_OK, hm_classes.sys_to_net(raw_dict))
        else:
            self.set_state(ret_state, "%s: %s" % (limits.get_state_str(ret_state),
                                                  "; ".join(ret_field) or "no errors or warnings"))
            
class eonstor_ld_info_scheme(eonstor_proto_scheme):
    def __init__(self):
        eonstor_proto_scheme.__init__(self, "eonstor_ld_info", ld_table=True)
    def __del__(self):
        eonstor_proto_scheme.__del__(self)
    def handle_dict(self, pre_dict):
        dev_dict = dict([(dev_idx, eonstor_ld(dev_stuff)) for dev_idx, dev_stuff in pre_dict.iteritems()])
        self._generate_return(dev_dict)

class eonstor_fan_info_scheme(eonstor_proto_scheme):
    def __init__(self):
        eonstor_proto_scheme.__init__(self, "eonstor_fan_info")
    def __del__(self):
        eonstor_proto_scheme.__del__(self)
    def handle_dict(self, pre_dict):
        dev_dict = dict([(dev_idx, eonstor_fan(dev_stuff)) for dev_idx, dev_stuff in pre_dict.iteritems() if dev_stuff[6] == 2])
        self._generate_return(dev_dict)

class eonstor_temperature_info_scheme(eonstor_proto_scheme):
    def __init__(self):
        eonstor_proto_scheme.__init__(self, "eonstor_temperature_info")
    def __del__(self):
        eonstor_proto_scheme.__del__(self)
    def handle_dict(self, pre_dict):
        dev_dict = dict([(dev_idx, eonstor_temperature(dev_stuff)) for dev_idx, dev_stuff in pre_dict.iteritems() if dev_stuff[6] == 3])
        self._generate_return(dev_dict)

class eonstor_psu_info_scheme(eonstor_proto_scheme):
    def __init__(self):
        eonstor_proto_scheme.__init__(self, "eonstor_psu_info")
    def __del__(self):
        eonstor_proto_scheme.__del__(self)
    def handle_dict(self, pre_dict):
        dev_dict = dict([(dev_idx, eonstor_psu(dev_stuff)) for dev_idx, dev_stuff in pre_dict.iteritems() if dev_stuff[6] == 1])
        self._generate_return(dev_dict)

class eonstor_ups_info_scheme(eonstor_proto_scheme):
    def __init__(self):
        eonstor_proto_scheme.__init__(self, "eonstor_ups_info")
    def __del__(self):
        eonstor_proto_scheme.__del__(self)
    def handle_dict(self, pre_dict):
        dev_dict = dict([(dev_idx, eonstor_ups(dev_stuff)) for dev_idx, dev_stuff in pre_dict.iteritems() if dev_stuff[6] == 4])
        self._generate_return(dev_dict)

class eonstor_bbu_info_scheme(eonstor_proto_scheme):
    def __init__(self):
        eonstor_proto_scheme.__init__(self, "eonstor_bbu_info")
    def __del__(self):
        eonstor_proto_scheme.__del__(self)
    def handle_dict(self, pre_dict):
        dev_dict = dict([(dev_idx, eonstor_bbu(dev_stuff)) for dev_idx, dev_stuff in pre_dict.iteritems() if dev_stuff[6] == 11])
        self._generate_return(dev_dict)

class eonstor_voltage_info_scheme(eonstor_proto_scheme):
    def __init__(self):
        eonstor_proto_scheme.__init__(self, "eonstor_voltage_info")
    def __del__(self):
        eonstor_proto_scheme.__del__(self)
    def handle_dict(self, pre_dict):
        dev_dict = dict([(dev_idx, eonstor_voltage(dev_stuff)) for dev_idx, dev_stuff in pre_dict.iteritems() if dev_stuff[6] == 5])
        self._generate_return(dev_dict)

class eonstor_slot_info_scheme(eonstor_proto_scheme):
    def __init__(self):
        eonstor_proto_scheme.__init__(self, "eonstor_slot_info")
    def __del__(self):
        eonstor_proto_scheme.__del__(self)
    def handle_dict(self, pre_dict):
        dev_dict = dict([(dev_idx, eonstor_slot(dev_stuff)) for dev_idx, dev_stuff in pre_dict.iteritems() if dev_stuff[6] == 17])
        self._generate_return(dev_dict)

class eonstor_disc_info_scheme(eonstor_proto_scheme):
    def __init__(self):
        eonstor_proto_scheme.__init__(self, "eonstor_disc_info", disc_table=True)
    def __del__(self):
        eonstor_proto_scheme.__del__(self)
    def handle_dict(self, pre_dict):
        dev_dict = dict([(dev_idx, eonstor_disc(dev_stuff)) for dev_idx, dev_stuff in pre_dict.iteritems()])
        self._generate_return(dev_dict)

class eonstor_get_counter_scheme(eonstor_proto_scheme):
    def __init__(self):
        eonstor_proto_scheme.__init__(self, "eonstor_get_counter")
    def __del__(self):
        eonstor_proto_scheme.__del__(self)
    def _write_return(self):
        sys_dict, disc_dict = (self.host_object.info_dict["eonstore_dict"].get_object()["sys"],
                               self.host_object.info_dict["eonstore_dict"].get_object()["disc"])
        # number of discs
        info_dict = {"disc_ids" : disc_dict.keys()}
        for idx, value in sys_dict.iteritems():
            ent_name = {1 : "psu",
                        2 : "fan",
                        3 : "temperature",
                        4 : "ups",
                        5 : "voltage",
                        11 : "bbu",
                        17 : "slot"}.get(value[6], None)
            if ent_name:
                info_dict.setdefault("ent_dict", {}).setdefault(ent_name, {})[idx] = value[8].prettyPrint()
        info_dict["ld_ids"] = self.host_object.info_dict["eonstore_dict"].get_object()["ld"].keys()
        self.set_state(limits.nag_STATE_OK, hm_classes.sys_to_net(info_dict))

class netapp_uptime_scheme(snmp_scheme):
    def __init__(self):
        snmp_scheme.__init__(self, "netapp_uptime", 1)
        self.__netapp_uptime = (1, 3, 6, 1, 2, 1, 1, 3, 0)
        self.snmp_request[0] = snmp_request("G",
                                            [self.__netapp_uptime],
                                            cb_func=self._uptime)
    def __del__(self):
        snmp_scheme.__del__(self)
    def _uptime(self, in_dict):
        uptime = int(in_dict.values()[0].values()[0]) / 100
        days = int(uptime / (3600 * 24))
        uptime -= 3600 * 24 * days
        hours = int(uptime / 3600)
        uptime -= 3600 * hours
        minutes = int(uptime / 60)
        uptime -= 60 * minutes
        seconds = uptime
        self.set_state(limits.nag_STATE_OK, "OK up for %s, %s %02d:%02d" % (logging_tools.get_plural("day", days),
                                                                            logging_tools.get_plural("hour", hours),
                                                                            minutes,
                                                                            seconds))
class netapp_cpuload_scheme(snmp_scheme):
    def __init__(self):
        snmp_scheme.__init__(self, "netapp_cpuload", 1)
        self.__netapp_cpuload = (1, 3, 6, 1, 4, 1, 789, 1, 2, 1, 3, 0)
        self.snmp_request[0] = snmp_request("G",
                                            [self.__netapp_cpuload],
                                            cb_func=self._cpuload)
    def __del__(self):
        snmp_scheme.__del__(self)
    def _cpuload(self, in_dict):
        value = int(in_dict[self.__netapp_cpuload].values()[0])
        ret_state, ret_str = self.arguments.check_ceiling(value)
        self.set_state(ret_state, "%s CPU load is %d %%" % (ret_str,
                                                            value))

class netapp_overtemp_scheme(snmp_scheme):
    def __init__(self):
        snmp_scheme.__init__(self, "netapp_overtemp", 1)
        self.__netapp_overtemp = (1, 3, 6, 1, 4, 1, 789, 1, 2, 4, 1, 0)
        self.snmp_request[0] = snmp_request("G",
                                            [self.__netapp_overtemp],
                                            cb_func=self._overtemp)
    def __del__(self):
        snmp_scheme.__del__(self)
    def _overtemp(self, in_dict):
        value = int(in_dict[self.__netapp_overtemp].values()[0])
        if value == 1:
            self.set_state(limits.nag_STATE_OK, "OK no overtemperature")
        else:
            self.set_state(limits.nag_STATE_CRITICAL, "Critical Overtemperature")

class netapp_nvram_battery_scheme(snmp_scheme):
    def __init__(self):
        snmp_scheme.__init__(self, "netapp_nvram_battery", 1)
        self.__netapp_battery = (1, 3, 6, 1, 4, 1, 789, 1, 2, 5, 1, 0)
        self.snmp_request[0] = snmp_request("G",
                                            [self.__netapp_battery],
                                            cb_func=self._nvram_battery)
    def __del__(self):
        snmp_scheme.__del__(self)
    def _nvram_battery(self, in_dict):
        value = int(in_dict[self.__netapp_battery].values()[0])
        ret_state, info_str = {1 : (limits.nag_STATE_OK      , "OK"),
                               2 : (limits.nag_STATE_WARNING , "partially discharged"),
                               3 : (limits.nag_STATE_CRITICAL, "fully discharged"),
                               4 : (limits.nag_STATE_CRITICAL, "not present"),
                               5 : (limits.nag_STATE_WARNING , "near end of life"),
                               6 : (limits.nag_STATE_CRITICAL, "at end of life"),
                               7 : (limits.nag_STATE_CRITICAL, "unknown"),
                               8 : (limits.nag_STATE_CRITICAL, "over charged"),
                               9 : (limits.nag_STATE_OK      , "fully charged")}.get(value, (limits.nag_STATE_CRITICAL, "unknown value %d" % (value)))
        self.set_state(ret_state, "%s NVRAM battery is %s" % (limits.get_state_str(ret_state),
                                                              info_str))

class netapp_failed_fan_scheme(snmp_scheme):
    def __init__(self):
        snmp_scheme.__init__(self, "netapp_failed_fan", 1)
        self.__netapp_fans = (1, 3, 6, 1, 4, 1, 789, 1, 2, 4, 2, 0)
        self.snmp_request[0] = snmp_request("G",
                                            [self.__netapp_fans],
                                            cb_func=self._fans)
    def __del__(self):
        snmp_scheme.__del__(self)
    def _fans(self, in_dict):
        num_failed = int(in_dict[self.__netapp_fans].values()[0])
        if num_failed:
            self.set_state(limits.nag_STATE_CRITICAL, "Critical Failed fans: %d" % (num_failed))
        else:
            self.set_state(limits.nag_STATE_OK, "OK no fans failed")

class netapp_failed_disk_scheme(snmp_scheme):
    def __init__(self):
        snmp_scheme.__init__(self, "netapp_failed_disk", 1)
        self.__netapp_disks = (1, 3, 6, 1, 4, 1, 789, 1, 6, 4, 7, 0)
        self.snmp_request[0] = snmp_request("G",
                                            [self.__netapp_disks],
                                            cb_func=self._disks)
    def __del__(self):
        snmp_scheme.__del__(self)
    def _disks(self, in_dict):
        num_failed = int(in_dict[self.__netapp_disks].values()[0])
        if num_failed:
            self.set_state(limits.nag_STATE_CRITICAL, "Critical Failed disks: %d" % (num_failed))
        else:
            self.set_state(limits.nag_STATE_OK, "OK no disks failed")

class netapp_failed_powersupply_scheme(snmp_scheme):
    def __init__(self):
        snmp_scheme.__init__(self, "netapp_failed_powersupply", 1)
        self.__netapp_powersupplys = (1, 3, 6, 1, 4, 1, 789, 1, 2, 4, 4, 0)
        self.snmp_request[0] = snmp_request("G",
                                            [self.__netapp_powersupplys],
                                            cb_func=self._powersupplys)
    def __del__(self):
        snmp_scheme.__del__(self)
    def _powersupplys(self, in_dict):
        num_failed = int(in_dict[self.__netapp_powersupplys].values()[0])
        if num_failed:
            self.set_state(limits.nag_STATE_CRITICAL, "Critical Failed powersupplies: %d" % (num_failed))
        else:
            self.set_state(limits.nag_STATE_OK, "OK no powersupplies failed")

class netapp_throughput_scheme(snmp_scheme):
    def __init__(self):
        snmp_scheme.__init__(self, "netapp_throughput", 0)
        self.__netapp_tput  = (1, 3, 6, 1, 4, 1, 789, 1, 2, 2)
    def __del__(self):
        snmp_scheme.__del__(self)
    def _host_object_set(self):
        use_cached = False
        # caching not pending
        self.max_steps = 1
        self.snmp_request[0] = snmp_request("T",
                                            [self.__netapp_tput],
                                            cb_func=self._netapp_throughput)
    def _netapp_throughput(self, in_dict):
        in_dict = dict([(int(key.prettyPrint().split(".")[0]), value) for key, value in in_dict.values()[0].iteritems()])
        self.host_object.info_dict.setdefault("tput_list", []).append((time.time(), in_dict))
        if len(self.host_object.info_dict["tput_list"]) > 2:
            self.host_object.info_dict["tput_list"].pop(0)
        self._write_return()
    def _write_return(self):
        if len(self.host_object.info_dict["tput_list"]) < 2:
            self.set_state(limits.nag_STATE_WARNING, "warning need second read")
        else:
            if self.arguments.has_add_var("arg0"):
                (ts0, dict0), (ts1, dict1) = self.host_object.info_dict["tput_list"]
                diff_time = max(abs(ts1 - ts0), 1)
                key = self.arguments.get_add_var("arg0")
                if key.isdigit():
                    key = int(key)
                    key_str = {5 : "NFS",
                               7 : "CIFS",
                               9 : "HTTP",
                               11 : "Net received",
                               13 : "Net sent",
                               15 : "Disk read",
                               17 : "Disk write",
                               19 : "Tape read",
                               21 : "Tape write"}.get(key, "")
                    if key_str:
                        if key < 11:
                            info_str = "Ops"
                        else:
                            info_str = "Bs"
                        if key in dict0 and key in dict1:
                            value = abs(((int(dict1[key]) << 32) + int(dict1[key + 1])) - ((int(dict0[key]) << 32) + int(dict0[key + 1]))) / diff_time
                            self.set_state(limits.nag_STATE_OK, "OK %s %s%s / sec" % (key_str, logging_tools.get_size_str(value)[:-1], info_str))
                        else:
                            self.set_state(limits.nag_STATE_CRITICAL, "error key %d (%s) not set" % (key, key_str))
                    else:
                        self.set_state(limits.nag_STATE_CRITICAL, "error invalid key %d" % (key))
                else:
                        self.set_state(limits.nag_STATE_CRITICAL, "error key %s is not an integer" % (key))
            else:
                self.set_state(limits.nag_STATE_CRITICAL, "error need index")

if __name__ == "__main__":
    print "This is a loadable module."
    sys.exit(0)
