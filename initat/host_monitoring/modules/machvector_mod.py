#!/usr/bin/python-init
#
# Copyright (C) 2001-2008,2010,2012-2014 Andreas Lang-Nevyjel
#
# Send feedback to: <lang-nevyjel@init.at>
#
# this file belongs to host-monitoring
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
""" machine vector stuff """

from initat.host_monitoring import hm_classes
from initat.host_monitoring import limits
from lxml import etree # @UnresolvedImports
from lxml.builder import E # @UnresolvedImports
import commands
import copy
import json
import logging_tools
import os
import process_tools
import re
import server_command
import shutil
import socket
import sys
import time
import zmq

MACHVECTOR_NAME = "machvector.xml"
ALERT_NAME = "alert"
COLLECTOR_PORT = 8002

MONITOR_OBJECT_INFO_LIST = ["load", "mem", "net", "vms", "num"]
MAX_MONITOR_OBJECTS = 10

class _general(hm_classes.hm_module):
    class Meta:
        priority = 5
    def __init__(self, *args, **kwargs):
        hm_classes.hm_module.__init__(self, *args, **kwargs)
    def init_module(self):
        if hasattr(self.process_pool, "register_vector_receiver"):
            # at first init the machine_vector
            self._init_machine_vector()
            # then start the polling loop
            self.process_pool.register_timer(self._update_machine_vector, 10, instant=True)
    def close_module(self):
        if hasattr(self.process_pool, "register_vector_receiver"):
            self.machine_vector.close()
    def _init_machine_vector(self):
        self.machine_vector = machine_vector(self)
    def init_machine_vector(self, mvect):
        pass
    def _update_machine_vector(self):
        self.machine_vector.update()

class get_mvector_command(hm_classes.hm_command):
    def __init__(self, name):
        hm_classes.hm_command.__init__(self, name, positional_arguments=True)
        self.parser.add_argument("--raw", dest="raw", action="store_true", default=False)
    def __call__(self, srv_com, cur_ns):
        self.module.machine_vector.store_xml(srv_com)
    def interpret(self, srv_com, cur_ns):
        if cur_ns.arguments:
            re_list = [re.compile(_arg) for _arg in cur_ns.arguments]
        else:
            re_list = []
        cur_vector = srv_com["data:machine_vector"]
        if cur_ns.raw:
            return limits.nag_STATE_OK, etree.tostring(cur_vector)
        else:
            vector_keys = sorted(srv_com.xpath(".//ns:mve/@name", start_el=cur_vector, smart_strings=False))
            used_keys = [key for key in vector_keys if any([cur_re.search(key) for cur_re in re_list]) or not re_list]
            ret_array = ["Machinevector id %s, %s, %s shown:" % (
                cur_vector.attrib["version"],
                logging_tools.get_plural("key", len(vector_keys)),
                logging_tools.get_plural("key", len(used_keys)),
                )]
            out_list = logging_tools.new_form_list()
            for mv_num, mv_key in enumerate(vector_keys):
                if mv_key in used_keys:
                    cur_xml = srv_com.xpath("//ns:mve[@name='%s']" % (mv_key), start_el=cur_vector, smart_strings=False)[0]
                    out_list.append(hm_classes.mvect_entry(cur_xml.attrib.pop("name"), **cur_xml.attrib).get_form_entry(mv_num))
            ret_array.extend(unicode(out_list).split("\n"))
            return limits.nag_STATE_OK, "\n".join(ret_array)

class alert_object(object):
    def __init__(self, key, logger, num_dp, th_class, th, command):
        self.__key = key
        self.__logger = logger
        self.__th_class = th_class
        self.__th = th
        self.__command = command
        self.init_buffer(num_dp)
    def init_buffer(self, num_dp):
        self.__val_buffer = []
        self.__num_dp = num_dp
        self.log("init val_buffer, max_size is %d" % (num_dp))
    def add_value(self, val):
        self.__val_buffer.append(val)
        if len(self.__val_buffer) > self.__num_dp:
            self.__val_buffer.pop(0)
        if len(self.__val_buffer) == self.__num_dp:
            # check for alert
            if self.__th_class == "U":
                alert = len([1 for x in self.__val_buffer if x > self.__th]) == self.__num_dp
            else:
                alert = len([1 for x in self.__val_buffer if x < self.__th]) == self.__num_dp
            if alert:
                self.log("*** alert, threshold %.2f, %s: %s" % (self.__th, logging_tools.get_plural("value", self.__num_dp), ", ".join(["%.2f" % (x) for x in self.__val_buffer])))
                act_com = self.__command
                for src, dst in [("%k", self.__key),
                                 ("%v", ", ".join(["%.2f" % (x) for x in self.__val_buffer])),
                                 ("%t", "%.2f" % (self.__th)),
                                 ("%c" , self.__th_class)]:
                    act_com = act_com.replace(src, dst)
                stat, out = commands.getstatusoutput(act_com)
                lines = [x.rstrip() for x in out.split("\n") if x.rstrip()]
                self.log("*** calling command '%s' returned %d (%s):" % (act_com, stat, logging_tools.get_plural("line", len(lines))))
                for line in lines:
                    self.log("*** - %s" % (line))
        # print self.__key, self.__val_buffer
    def log(self, what):
        self.__logger.info("[mvect / ao %s, cl %s] %s" % (self.__key, self.__th_class, what))

class machine_vector(object):
    def __init__(self, module):
        self.module = module
        # actual dictionary, including full-length dictionary keys
        self.__act_dict = {}
        # actual keys, last keys
        self.__act_keys = set()
        # init external_sources
        # self.__alert_dict, self.__alert_dict_time = ({}, time.time())
        # key is in fact the timestamp
        self.__act_key, self.__changed = (0, True)
        self.__verbosity = module.process_pool.global_config["VERBOSE"]
        # socket dict for mv-sending
        self.__socket_dict = {}
        # read machine vector config
        self.conf_name = os.path.join("/etc/sysconfig/host-monitoring.d", MACHVECTOR_NAME)
        if not os.path.isfile(self.conf_name):
            self.log("create %s" % (self.conf_name))
            # create default file
            def_xml = E.mv_targets(
                E.mv_target(
                    # enabled or disabled
                    enabled="0",
                    # target (== server)
                    target="127.0.0.1",
                    # target port
                    port="8002",
                    # name used for sending, if unset use process_tools.get_machine_name()
                    send_name="",
                    # send every X seconds
                    send_every="30",
                    # every Y iteration send a full dump
                    full_info_every="10",
                    # send immediately
                    immediate="0",
                    # format, json or xml
                    format="xml",
                )
            )
            file(self.conf_name, "w").write(
                etree.tostring(
                    def_xml,
                    pretty_print=True,
                    xml_declaration=True))
        try:
            xml_struct = etree.fromstring(file(self.conf_name, "r").read())
        except:
            self.log("cannot read %s: %s" % (
                self.conf_name,
                process_tools.get_except_info()),
                     logging_tools.LOG_LEVEL_ERROR)
            xml_struct = None
        else:
            send_id = 0
            p_pool = self.module.process_pool
            for mv_target in xml_struct.xpath(".//mv_target[@enabled='1']", smart_strings=False):
                send_id += 1
                mv_target.attrib["send_id"] = "%d" % (send_id)
                mv_target.attrib["sent"] = "0"
                p_pool.register_timer(self._send_vector, int(mv_target.get("send_every", "30")), data=send_id, instant=int(mv_target.get("immediate", "0")) == 1)
                # zmq sending, not needed any more (now using UDP/collectd)
                if True: # False:
                    t_sock = p_pool.zmq_context.socket(zmq.PUSH)
                    t_sock.setsockopt(zmq.LINGER, 0)
                    t_sock.setsockopt(zmq.SNDHWM, 16)
                    t_sock.setsockopt(zmq.BACKLOG, 4)
                    t_sock.setsockopt(zmq.SNDTIMEO, 1000)
                    # to stop 0MQ trashing the target socket
                    t_sock.setsockopt(zmq.RECONNECT_IVL, 1000)
                    t_sock.setsockopt(zmq.RECONNECT_IVL_MAX, 30000)
                    target_str = "tcp://%s:%d" % (
                        mv_target.get("target", "127.0.0.1"),
                        int(mv_target.get("port", "8002")))
                    self.log("creating zmq.PUSH socket for %s" % (target_str))
                    t_sock.connect(target_str)
                else:
                    t_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                self.__socket_dict[send_id] = t_sock
        self.__xml_struct = xml_struct
        module.process_pool.register_vector_receiver(self._recv_vector)
        # self.__module_dict = module_dict
        for module in module.process_pool.module_list:
            if hasattr(module, "init_machine_vector"):
                if self.__verbosity:
                    self.log("calling init_machine_vector for module '%s'" % (module.name))
                try:
                    module.init_machine_vector(self)
                except:
                    self.log("error: %s" % (process_tools.get_except_info()), logging_tools.LOG_LEVEL_CRITICAL)
                    raise
        # delete external directories
        old_dir = "/tmp/.machvect_es"
        if os.path.isdir(old_dir):
            try:
                shutil.rmtree(old_dir)
            except:
                self.log("error removing old external directory %s: %s" % (old_dir,
                                                                           process_tools.get_except_info()),
                         logging_tools.LOG_LEVEL_ERROR)
            else:
                self.log("removed old external directory %s" % (old_dir))
    def _send_vector(self, *args, **kwargs):
        cur_xml = self.__xml_struct.find(".//mv_target[@send_id='%d']" % (args[0]))
        cur_id = int(cur_xml.attrib["sent"])
        full = cur_id % int(cur_xml.attrib.get("full_info_every", "10")) == 0
        cur_id += 1
        cur_xml.attrib["sent"] = "%d" % (cur_id)
        try:
            fqdn, _short_name = process_tools.get_fqdn()
        except:
            fqdn = process_tools.get_machine_name()
        send_format = cur_xml.attrib.get("format", "xml")
        if send_format == "xml":
            send_vector = self.build_xml(E, simple=not full)
            send_vector.attrib["name"] = (cur_xml.get("send_name", fqdn) or fqdn)
            send_vector.attrib["interval"] = cur_xml.get("send_every")
            send_vector.attrib["uuid"] = self.module.process_pool.zeromq_id
        else:
            send_vector = self.build_json(simple=not full)
            send_vector[1]["name"] = cur_xml.get("send_name", fqdn) or fqdn
            send_vector[1]["interval"] = int(cur_xml.get("send_every"))
            send_vector[1]["uuid"] = self.module.process_pool.zeromq_id
        # send to server
        t_host, t_port = (
            cur_xml.get("target", "127.0.0.1"),
            int(cur_xml.get("port", "8002"))
        )
        try:
            send_id = int(cur_xml.attrib["send_id"])
            if send_format == "xml":
                self.__socket_dict[send_id].send_unicode(unicode(etree.tostring(send_vector)))
            else:
                # print json.dumps(send_vector)
                self.__socket_dict[send_id].send_unicode(json.dumps(send_vector))
        except:
            exc_info = process_tools.get_except_info()
            # ignore errors
            self.log(
                "error sending to (%s, %d): %s" % (
                    t_host,
                    t_port,
                    exc_info), logging_tools.LOG_LEVEL_ERROR)
            if exc_info.count("int_error"):
                raise
        # print etree.tostring(send_vector, pretty_print=True)
    def close(self):
        for _s_id, t_sock in self.__socket_dict.iteritems():
            t_sock.close()
    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.module.process_pool.log("[mvect] %s" % (what), log_level)
    def _recv_vector(self, zmq_sock):
        try:
            rcv_com = server_command.srv_command(source=zmq_sock.recv_unicode())
        except:
            self.log("error interpreting data as srv_command: %s" % (process_tools.get_except_info()),
                     logging_tools.LOG_LEVEL_ERROR)
        else:
            for in_vector in rcv_com.xpath(".//*[@type='vector']", smart_strings=False):
                for values_list in in_vector:
                    for cur_value in values_list:
                        self.set_from_external(hm_classes.mvect_entry(**cur_value.attrib))
            self.check_timeout()
            self.check_changed()
    def set_from_external(self, mvec):
        if mvec.name not in self:
            # register entry
            self.__act_dict[mvec.name] = mvec
            self.__changed = True
        else:
            # only update value
            self[mvec.name].update_from_mvec(mvec)
    def register_entry(self, name, default, info, unit="1", base=1, factor=1, **kwargs):
        # name is the key (first.second.third.fourth)
        # default is a default value
        # info is a description of the entry
        # unit is the (SI ;-))-symbol for the entry
        # base is the divider to derive the k/M/G-Values (1, 1000 or 1024)
        # factor is a number the values have to be multipilicated with in order to lead to a meaningful number (for example memory or df)
        self.__changed = True
        self.__act_dict[name] = hm_classes.mvect_entry(name, default=default, info=info, unit=unit, base=base, factor=factor)
    def get(self, name, default_value=None):
        return self.__act_dict.get(name, default_value)
    def __getitem__(self, key):
        return self.__act_dict[key]
    def has_key(self, key):
        return self.__act_dict.has_key(key)
    def keys(self):
        return self.__act_dict.keys()
    def __contains__(self, key):
        return key in self.__act_dict
    def unregister_tree(self, key_prefix):
        self.__changed = True
        del_keys = [key for key in self.keys() if key.startswith(key_prefix)]
        for del_key in del_keys:
            del self.__act_dict[del_key]
    def unregister_entry(self, name):
        self.__changed = True
        if self.__act_dict.has_key(name):
            # print "Unregister "+name
            del self.__act_dict[name]
        else:
            self.log("Error: entry %s not defined" % (name), logging_tools.LOG_LEVEL_ERROR)
    def __setitem__(self, name, value):
        self.__act_dict[name].update(value)
    def _reg_update(self, log_t, name, value):
        if self.__act_dict.has_key(name):
            self.__act_dict[name].update(value)
        else:
            log_t.error("Error: unknown machvector-name '%s'" % (name))
    def _optimize_list(self, in_list):
        new_list = []
        for entry in in_list:
            if new_list and new_list[-1][0] == entry[0]:
                new_list[-1][1].append(entry[1:])
            else:
                if len(entry) > 1:
                    new_list.append([entry[0], [entry[1:]]])
                else:
                    new_list.append([entry[0], []])
        new_list = [[entry[0], self._optimize_list(entry[1])] if len(entry) > 1 else entry for entry in new_list]
        return new_list
    def _beautify_list(self, in_list):
        return ",".join(["%s%s" % (entry[0], ".(%s)" % (self._beautify_list(entry[1])) if entry[1] else "") for entry in in_list])
    def optimize_list(self, in_list):
        in_list = [entry.split(".") for entry in sorted(in_list)]
        return self._beautify_list(self._optimize_list(in_list))
    def check_changed(self):
        if self.__changed:
            # attention ! dict.keys() != copy.deppcopy(dict).keys()
            last_keys = copy.deepcopy(self.__act_keys)
            self.__act_keys = set(self.__act_dict.keys())
            self.__changed = False
            new_key = int(time.time())
            if new_key == self.__act_key:
                new_key += 1
            self.__act_key = new_key
            new_keys = self.__act_keys - last_keys
            lost_keys = last_keys - self.__act_keys
            if new_keys:
                self.log("%s:" % (logging_tools.get_plural("new key", len(new_keys))))
                self.log(self.optimize_list(new_keys))
                # for key_num, key in enumerate(sorted(new_keys)):
                #    self.log(" %3d : %s" % (key_num, key))
            if lost_keys:
                self.log("%s:" % (logging_tools.get_plural("lost key", len(lost_keys))))
                self.log(self.optimize_list(lost_keys))
                # for key_num, key in enumerate(sorted(lost_keys)):
                #    self.log(" %3d : %s" % (key_num, key))
            self.log("Machine_vector has changed, setting actual key to %d (%d keys)" % (self.__act_key, len(self.__act_dict)))
    def check_timeout(self):
        cur_time = time.time()
        rem_keys = [key for key, value in self.__act_dict.iteritems() if value.check_timeout(cur_time)]
        if rem_keys:
            self.log("removing %s because of timeout: %s" % (
                logging_tools.get_plural("key", len(rem_keys)),
                ", ".join(sorted(rem_keys))))
            for rem_key in rem_keys:
                self.unregister_entry(rem_key)
            self.__changed = True
    def store_xml(self, srv_com):
        srv_com["data"] = self.build_xml(srv_com.builder)
    def build_json(self, simple=False):
        mach_vect = ["machine_vector", {"version" : self.__act_key, "time" : int(time.time()), "simple" : 1 if simple else 0}]
        if simple:
            mach_vect.extend([cur_mve.build_simple_json() for cur_mve in self.__act_dict.itervalues()])
        else:
            mach_vect.extend([cur_mve.build_json() for cur_mve in self.__act_dict.itervalues()])
        return mach_vect
    def build_xml(self, builder, simple=False):
        mach_vect = builder(
            "machine_vector",
            version="%d" % (self.__act_key),
            time="%d" % (int(time.time())),
            simple="1" if simple else "0",
        )
        if simple:
            mach_vect.extend([cur_mve.build_simple_xml(builder) for cur_mve in self.__act_dict.itervalues()])
        else:
            mach_vect.extend([cur_mve.build_xml(builder) for cur_mve in self.__act_dict.itervalues()])
        return mach_vect
    def get_send_mvector(self):
        return (time.time(), self.__act_key, [self.__act_dict[key].value for key in self.__act_keys])
    # def flush_cache(self, name):
    #    self.__dict_list[name] = []
    def get_actual_key(self):
        return self.__act_key
    def get_act_dict(self):
        return self.__act_dict
    def update(self): # , esd=""):
        self.check_changed()
        # copy ref_dict to act_dict
        [value.update_default() for value in self.__act_dict.itervalues()]
        self.check_timeout()
        # if esd:
        #    self.check_external_sources(log_t, esd)
        # self.check_for_alert_file_change(log_t)
        for module in self.module.process_pool.module_list:
            if hasattr(module, "update_machine_vector"):
                module.update_machine_vector(self)
        self.check_changed()
        # self.check_for_alerts(log_t)

class monitor_object(object):
    def __init__(self, name):
        self.__name = name
        self.__start_time, self.__counter = (time.time(), 0)
        self.__cache = {}
    def update(self, mv):
        self.__counter += 1
        for key, value in mv.get_act_dict().iteritems():
            if [True for item in MONITOR_OBJECT_INFO_LIST if key.startswith(item)]:
                if not self.__cache.has_key(key):
                    self.__cache[key] = hm_classes.mvect_entry(key,
                                                               default=value.default,
                                                               info=value.info,
                                                               base=value.base,
                                                               factor=value.factor,
                                                               unit=value.unit,
                                                               value=value.value,
                                                               monitor_value=True)
                else:
                    self.__cache[key].update(value.value)
    def get_start_time(self):
        return self.__start_time
    def get_info(self):
        return {"start_time" : self.__start_time,
                "cache"      : self.__cache}

def pretty_print(val, base):
    pf_idx = 0
    if base != 1:
        while val > base * 4:
            pf_idx += 1
            val = float(val) / base
    return val, ["", "k", "M", "G", "T", "E", "P"][pf_idx]

def pretty_print2(value):
    if value.has_key("u"):
        act_v, p_str = pretty_print(value["v"] * value["f"], value["b"])
        unit = value["u"]
    else:
        act_v, p_str = (value["v"], "")
        unit = "???"
    if type(act_v) in [type(0), type(0L)]:
        val = "%10d   " % (act_v)
    else:
        val = "%13.2f" % (act_v)
    return val, p_str, unit

def build_info_string(ref, info):
    ret_str = info
    refp = ref.split(".")
    for idx in range(len(refp)):
        ret_str = ret_str.replace("$%d" % (idx + 1), refp[idx])
    return ret_str

if __name__ == "__main__":
    print "Not an executable python script, exiting..."
    sys.exit(-2)
