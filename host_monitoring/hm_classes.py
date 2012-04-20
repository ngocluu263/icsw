#!/usr/bin/python-init -Ot
#
# Copyright (C) 2001,2002,2003,2004,2005,2006,2007,2008,2010,2011,2012 Andreas Lang-Nevyjel, init.at
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
""" base class for host-monitoring modules """

import sys
import marshal
import cPickle
import time
import logging_tools
import process_tools
import argparse
import subprocess
import server_command
import zmq
import types

def net_to_sys(in_val):
    try:
        result = cPickle.loads(in_val)
    except:
        try:
            result = marshal.loads(in_val)
        except:
            raise
    return result

def sys_to_net(in_val):
    return cPickle.dumps(in_val)

class subprocess_struct(object):
    def __init__(self, srv_com, com_line, cb_func=None):
        self.srv_com = srv_com
        self.command = srv_com["command"].text
        self.command_line = com_line
        self.multi_command = type(self.command_line) == list
        self.com_num = 0
        self.popen = None
        self.cb_func = cb_func
        self._init_time = time.time()
        # if not a popen call
        self.terminated = False
    def run(self):
        run_info = {}
        if self.multi_command:
            if self.command_line:
                cur_cl = self.command_line[self.com_num]
                if type(cur_cl) == type(()):
                    # in case of tuple
                    run_info["comline"] = cur_cl[0]
                else:
                    run_info["comline"] = cur_cl
                run_info["command"] = cur_cl
                run_info["run"] = self.com_num
                self.com_num += 1
            else:
                run_info["comline"] = None
        else:
            run_info["comline"] = self.command_line
        self.run_info = run_info
        if run_info["comline"]:
            self.popen = subprocess.Popen(run_info["comline"], shell=True, stderr=subprocess.STDOUT, stdout=subprocess.PIPE)
    def set_send_stuff(self, src_id, zmq_sock):
        self.src_id = src_id
        self.zmq_sock = zmq_sock
    def read(self):
        if self.popen:
            return self.popen.stdout.read()
        else:
            return None
    def finished(self):
        if self.run_info["comline"] is None:
            self.run_info["result"] = 0
            # empty list of commands
            fin = True
        else:
            self.run_info["result"] = self.popen.poll()
            fin = False
            if self.run_info["result"] is not None:
                self.process()
                if self.multi_command:
                    if self.com_num == len(self.command_line):
                        # last command
                        fin = True
                    else:
                        # next command
                        self.run()
                else:
                    fin = True
        return fin
    def process(self):
        if self.cb_func:
            self.cb_func(self)
        else:
            self.srv_com["result"].attrib.update({
                "reply" : "default process() call",
                "state" : "%d" % (server_command.SRV_REPLY_STATE_ERROR)})
    def terminate(self):
        self.popen.kill()
        self.srv_com["result"].attrib.update({
            "reply" : "runtime (%s) exceeded" % (logging_tools.get_plural("second", self.Meta.max_runtime)),
            "state" : "%d" % (server_command.SRV_REPLY_STATE_ERROR)})
    def send_return(self):
        self.zmq_sock.send_unicode(self.src_id, zmq.SNDMORE)
        self.zmq_sock.send_unicode(unicode(self.srv_com))
        del self.srv_com
        del self.zmq_sock
        if self.popen:
            del self.popen
    class Meta:
        max_usage = 2
        twisted = False
        max_runtime = 300
        use_popen = True

class hm_module(object):
    class Meta:
        priority = 0
    def __init__(self, name, mod_obj):
        self.name = name
        self.obj = mod_obj
        self.__commands = {}
    def add_command(self, com_name, call_obj):
        if type(call_obj) == type:
            if com_name.endswith("_command"):
                com_name = com_name[:-8]
            new_co = call_obj(com_name)
            new_co.module = self
            self.__commands[com_name] = new_co
    @property
    def commands(self):
        return self.__commands
    def register_server(self, proc_pool):
        self.process_pool = proc_pool
    def init_module(self):
        pass
    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.process_pool.log("[%s] %s" % (self.name, what), log_level)

class hm_command(object):
    def __init__(self, name, **kwargs):
        self.name = name
        self.parser = argparse.ArgumentParser(description="help for command %s" % (self.name))
        self.server_parser = argparse.ArgumentParser(description="help for command %s" % (self.name))
        parg_flag = kwargs.get("positional_arguments", False)
        self.server_arguments = kwargs.get("server_arguments", False)
        # used to pass commandline arguments to the server
        self.partial = kwargs.get("partial", False)
        if parg_flag is not False:
            if parg_flag is True:
                self.parser.add_argument("arguments", nargs="*", help="additional arguments")
                self.server_parser.add_argument("arguments", nargs="*", help="additional arguments")
            elif parg_flag == 1:
                self.parser.add_argument("arguments", nargs="+", help="additional arguments")
                self.server_parser.add_argument("arguments", nargs="+", help="additional arguments")
            else:
                raise ValueError, "positonal_argument flag not in [1, True, False]"
        # monkey patch parsers
        self.parser.exit = self._parser_exit
        self.parser.error = self._parser_error
        self.server_parser.exit = self._parser_exit
        self.server_parser.error = self._parser_error
    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.module.process_pool.log("[%s] %s" % (self.name, what), log_level)
    def _parser_exit(self, status=0, message=None):
        raise ValueError, (status, message)
    #self.parser_exit, self.parser_message = (status, message)
    def _parser_error(self, message):
        raise ValueError, (2, message)
        self.parser_exit, self.parser_message = (2, message)
    def handle_server_commandline(self, arg_list):
        return self.server_parser.parse_args(arg_list)
    def handle_commandline(self, arg_list):
        # for arguments use "--" to separate them from the commandline arguments
        if self.partial or self.server_arguments:
            res_ns, unknown = self.parser.parse_known_args(arg_list)
        else:
            res_ns, unknown = self.parser.parse_args(arg_list), []
        if hasattr(res_ns, "arguments"):
            unknown.extend(res_ns.arguments)
        return res_ns, unknown

class hm_fileinfo(object):
    def __init__(self, name, info, **args):
        self.name, self.info = (name, info)
        self.logger = args.get("logger", None)
        self.module = args.get("module", None)
        self.commands = {}
        self.priority = 0
        self.has_own_thread = False
    def add_command(self, com):
        self.commands[com.name] = com
    def log(self, what, level=logging_tools.LOG_LEVEL_OK):
        self.logger.log(level, what)
    def check_global_config(self, gc):
        return 1
    def process_server_args(self, basedir_name, logger):
        return (1, "ok")
    def process_client_args(self, opts, hmb):
        return (1, "ok", [])
    def needs_hourly_wakeup_call(self):
        return False
    
class hmb_command(object):
    def __init__(self, name, **args):
        self.name = name
        self.module_info = args.get("module", None)
        self.module_name = args.get("module_name", "mn not set")
        self.relay_call = False
        self.net_only = False
        self.help_str = "not set"
        # sever stuff
        self.short_server_info = ""
        self.long_server_info = ""
        # client stuff
        self.short_client_info = ""
        self.long_client_info = ""
        self.short_client_opts = ""
        self.long_client_opts = []
        # stuff
        self.is_immediate = True
        self.timeout = 5.
        self.log_level = 0
        self.cache_timeout = 60
        self.special_hook = None
    def process_client_args(self, opts):
        return self.module_info.process_client_args(opts, self)
    def log(self, what, lev=logging_tools.LOG_LEVEL_OK):
        self.logger.log(lev, what)
    def __call__(self, comline, logger, **in_args):
        addr = in_args.get("addr", ("local", 0))
        self.thread_pool = in_args.get("thread_pool", None)
        args = comline.split()
        try:
            # remove command
            args.pop(0)
            self.source_host, self.source_port = addr
            if self.log_level:
                start_time = time.time()
                self.module_info.log("calling %s in module %s from %s (%s)" % (self.name,
                                                                               self.module_name,
                                                                               self.source_port and "%s (port %d)" % (self.source_host, self.source_port) or self.source_host,
                                                                               args and "args: %s" % (" ".join(args)) or "no args"))
            self.logger = logger
            result = self.server_call(args)
            self.logger = None
            if self.log_level:
                end_time = time.time()
                self.module_info.log("  - %s took %s" % (self.name,
                                                         logging_tools.get_diff_time_str(end_time - start_time)))
        except:
            result = "error server throw an exception: %s" % (process_tools.get_except_info())
            self.module_info.log(result, logging_tools.LOG_LEVEL_CRITICAL)
            exc_info = process_tools.exception_info()
            for line in exc_info.log_lines:
                self.module_info.log(line, logging_tools.LOG_LEVEL_CRITICAL)
        else:
            if not result:
                result = "error server returned None"
        # cleanup
        self.thread_pool = None
        return result
        
class mvect_entry(object):
    __slots__ = ["name", "default", "info", "unit", "base", "value", "factor", "v_type", "valid_until"]
    def __init__(self, name, **kwargs):
        self.name = name
        # info, description for user
        self.info = kwargs["info"]
        # unit, can be 1, B, ...
        self.unit = kwargs.get("unit", "1")
        # base, 1, 1000 or 1024
        self.base = int(kwargs.get("base", 1))
        # factor to mulitply value with to get real value
        self.factor = int(kwargs.get("factor", 1))
        if "v_type" in kwargs:
            self.factor = int(self.factor)
            self.base = int(self.base)
            # value
            self.v_type = kwargs["v_type"]
            if self.v_type == "i":
                self.value = int(kwargs["value"])
            elif self.v_type == "f":
                self.value = float(kwargs["value"])
            else:
                self.value = kwargs["value"]
            self.default = self.value
        else:
            # default value, to get type
            self.default = kwargs["default"]
            # value
            self.value = kwargs.get("value", self.default)
            self.v_type = {type(0)   : "i",
                           type(0L)  : "i",
                           type(0.0) : "f"}.get(type(self.default), "s")
        self.valid_until = kwargs.get("valid_until", None)
        if self.valid_until:
            self.valid_until = int(self.valid_until)
    def update(self, value):
        if value is None:
            # unknown
            self.value = value
        elif type(value) == type(self.default):
            self.value = value
        else:
            try:
                if self.v_type == "i":
                    # is integer
                    self.value = int(value)
                elif self.v_type == "f":
                    self.value = float(value)
                else:
                    self.value = value
            except:
                # cast to None
                self.value = None
##        if self.__monitor:
##            self.min_value = min(self.min_value, self.value)
##            self.max_value = max(self.max_value, self.value)
##            self.total_value += self.value
##            self.num += 1
    def update_default(self):
        # init value with default value for entries without valid_until settings
        if not self.valid_until:
            self.value = self.default
    def check_timeout(self, cur_time):
        return True if (self.valid_until and cur_time > self.valid_until) else False
    def get_form_entry(self, idx):
        act_line = []
        sub_keys = (self.name.split(".") + ["", "", ""])[0:4]
        for key_idx, sub_key in zip(xrange(4), sub_keys):
            act_line.append(logging_tools.form_entry("%s%s" % ("" if (key_idx == 0 or sub_key == "") else ".", sub_key), header="key%d" % (key_idx)))
        # check for unknow
        if self.value is None:
            # unknown value
            act_pf, val_str = ("", "<unknown>")
        else:
            act_pf, val_str = self._get_val_str(self.value * self.factor)
        act_line.extend([logging_tools.form_entry_right(val_str, header="value"),
                         logging_tools.form_entry_right(act_pf, header=" "),
                         logging_tools.form_entry(self.unit, header="unit"),
                         logging_tools.form_entry("(%3d)" % (idx), header="idx"),
                         logging_tools.form_entry("%d" % (self.valid_until) if self.valid_until else "---", header="valid_until"),
                         logging_tools.form_entry(self._build_info_string(), header="info")])
        return act_line
    def _get_val_str(self, val):
        act_pf = ""
        pf_list = ["k", "M", "G", "T", "E", "P"]
        if self.base != 1:
            while val > self.base * 4:
                act_pf = pf_list.pop(0)
                val = float(val) / self.base
        if self.v_type == "i":
            val_str = "%10d    " % (val)
        elif self.v_type == "f":
            val_str = "%14.3f" % (val)
        else:
            val_str = "%-14s" % (str(val))
        return act_pf, val_str
##    def get_monitor_form_entry(self):
##        act_line = []
##        sub_keys = (self.name.split(".") + ["", "", ""])[0:4]
##        for key_idx, sub_key in zip(xrange(4), sub_keys):
##            act_line.append(logging_tools.form_entry("%s%s" % ("" if (key_idx == 0 or sub_key == "") else ".", sub_key), header="key%d" % (key_idx)))
##        act_line.extend([logging_tools.form_entry(self.num, header="count"),
##                         logging_tools.form_entry_right(self._get_val_str(self.value)[0], header="value"),
##                         logging_tools.form_entry_right(self._get_val_str(self.value)[1], header=" "),
##                         logging_tools.form_entry_right(self._get_val_str(self.min_value)[0], header="min_value"),
##                         logging_tools.form_entry_right(self._get_val_str(self.min_value)[1], header=" "),
##                         logging_tools.form_entry_right(self._get_val_str(self.max_value)[0], header="max_value"),
##                         logging_tools.form_entry_right(self._get_val_str(self.max_value)[1], header=" "),
##                         logging_tools.form_entry_right(self._get_val_str(self.total_value / self.num)[0], header="mean_value"),
##                         logging_tools.form_entry_right(self._get_val_str(self.total_value / self.num)[1], header=" "),
##                         logging_tools.form_entry(self.unit, header="unit"),
##                         logging_tools.form_entry(self._build_info_string(), header="info")])
##        return act_line
    def _build_info_string(self):
        ret_str = self.info
        ref_p = self.name.split(".")
        for idx in xrange(len(ref_p)):
            ret_str = ret_str.replace("$%d" % (idx + 1), ref_p[idx])
        return ret_str
    def build_xml(self, builder):
        kwargs = {"name"   : self.name,
                  "info"   : self.info,
                  "unit"   : self.unit,
                  "v_type" : self.v_type,
                  "value"  : str(self.value)}
        for key, ns_value in [("valid_until", None),
                              ("base"       , 1   ),
                              ("factor"     , 1   )]:
            if getattr(self, key) != ns_value:
                kwargs[key] = "%d" % (getattr(self, key))
        return builder("mve", **kwargs)

if __name__ == "__main__":
    print "Loadable module, exiting..."
    sys.exit(-2)
