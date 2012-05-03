#!/usr/bin/python-init -Ot
#
# Copyright (C) 2001,2002,2003,2004,2005,2006,2007,2008,2009,2010,2012 Andreas Lang-Nevyjel, init.at
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

import os
import stat
import sys
import commands
from host_monitoring import limits, hm_classes
import tempfile
import time
import logging_tools
import process_tools
import threading_tools
import Queue
import net_tools
import server_command

class _general(hm_classes.hm_module):
    def _parse_ecd(self, in_str):
        # parse exclude_checkdate, ecd has the form [WHHMM][-WHHMM]
        # W ... weekday, 1 ... monday, 7 ... sunday
        if in_str.count("-"):
            start_str, end_str = in_str.strip().split("-")
            if not len(start_str):
                start_str = None
            if not len(end_str):
                end_str = None
        else:
            start_str, end_str = (in_str.strip(), None)
        return (self._parse_ecd2(start_str), self._parse_ecd2(end_str))
    def _parse_ecd2(self, in_str):
        if in_str is None:
            return in_str
        else:
            if len(in_str) != 5 or not in_str.isdigit():
                raise SyntaxError, "exclude_checkdate '%s' has wrong form (not WHHMM)" % (in_str)
            weekday, hour, minute = (int(in_str[0]),
                                     int(in_str[1:3]),
                                     int(in_str[3:5]))
            if weekday < 1 or weekday > 7:
                raise SyntaxError, "exclude_checkdate '%s' has invalid weekday" % (in_str)
            if hour < 0 or hour > 23:
                raise SyntaxError, "exclude_checkdate '%s' has invalid hour" % (in_str)
            if minute < 0 or minute > 59:
                raise SyntaxError, "exclude_checkdate '%s' has invalid minute" % (in_str)
            return (weekday, hour, minute)

class check_file_command(hm_classes.hm_command):
    def __init__(self, name):
        hm_classes.hm_command.__init__(self, name, positional_arguments=True)
        self.parser.add_argument("--mod", dest="mod_diff_time", type=int)
        self.parser.add_argument("--size", dest="min_file_size", type=int)
        self.parser.add_argument("--exclude-checkdate", dest="exclude_checkdate", type=str)
    def __call__(self, srv_com, cur_ns):
        if not "arguments:arg0" in srv_com:
            srv_com["result"].attrib.update({"reply" : "need filename",
                                             "state" : "%d" % (server_command.SRV_REPLY_STATE_ERROR)})
        else:
            file_name = srv_com["arguments:arg0"].text.strip()
            if os.path.isfile(file_name):
                f_stat = os.stat(file_name)
                stat_keys = [key for key in dir(f_stat) if key.startswith("st_")]
                f_stat = dict([(key, getattr(f_stat, key)) for key in stat_keys])
                srv_com["stat_result"] = {
                    "file"       : file_name,
                    "stat"       : f_stat,
                    "local_time" : time.time()}
            else:
                srv_com["stat_result"].attrib.update({
                    "reply" : "file '%s' not found" % (file_name),
                    "state" : "%d" % (server_command.SRV_REPLY_STATE_ERROR)})
    def interpret(self, srv_com, cur_ns):
        return self._interpret(srv_com["stat_result"], cur_ns)
    def interpret_old(self, result, cur_ns):
        return self._interpret(hm_classes.net_to_sys(result[3:]), cur_ns)
    def _interpret(self, f_dict, cur_ns):
        ret_state = limits.nag_STATE_OK
        file_stat = f_dict["stat"]
        if type(file_stat) == type({}):
            file_size  = file_stat["st_size"]
            file_mtime = file_stat["st_mtime"]
        else:
            file_size  = file_stat[stat.ST_SIZE]
            file_mtime = file_stat[stat.ST_MTIME]
        add_array = ["size %s" % (logging_tools.get_size_str(file_size))]
        act_time = time.localtime()
        act_time = (act_time.tm_wday + 1,
                    act_time.tm_hour,
                    act_time.tm_min)
        act_time = act_time[2] + 60 * (act_time[1] + 24 * act_time[0])
        in_exclude_range = False
        if cur_ns.exclude_checkdate:
            for s_time, e_time in cur_ns.exclude_checkdate:
                if s_time:
                    s_time = s_time[2] + 60 * (s_time[1] + 24 * s_time[0])
                if e_time:
                    e_time = e_time[2] + 60 * (e_time[1] + 24 * e_time[0])
                if s_time and e_time:
                    if s_time <= act_time and act_time <= e_time:
                        in_exclude_range = True
                if s_time:
                    if s_time <= act_time:
                        in_exclude_range = True
                if e_time:
                    if act_time <= e_time:
                        in_exclude_range = True
        if in_exclude_range:
            add_array.append("in exclude_range")
        else:
            if cur_ns.mod_diff_time:
                md_time = abs(file_mtime - f_dict["local_time"])
                if md_time > cur_ns.mod_diff_time:
                    ret_state = max(ret_state, limits.nag_STATE_CRITICAL)
                    add_array.append("changed %s ago > %s" % (logging_tools.get_diff_time_str(md_time),
                                                              logging_tools.get_diff_time_str(cur_ns.mod_diff_time)))
                else:
                    add_array.append("changed %s ago < %s" % (logging_tools.get_diff_time_str(md_time),
                                                              logging_tools.get_diff_time_str(cur_ns.mod_diff_time)))
        return ret_state, "file %s %s" % (f_dict["file"],
                                          ", ".join(add_array))

class my_modclass(hm_classes.hm_fileinfo):
    def __init__(self, **args):
        hm_classes.hm_fileinfo.__init__(self,
                                        "config",
                                        "provides an interface to control the node-configuration",
                                        **args)
        self.priority = -10
    def process_client_args(self, opts, hmb):
        ok, why = (1, "")
        ret_dict = {"mod_diff_time"     : None,
                    "file_size"         : None,
                    "exclude_checkdate" : []}
        my_lim = limits.limits()
        for opt, arg in opts:
            if opt == "--mod":
                ret_dict["mod_diff_time"] = int(arg)
            if opt == "--size":
                ret_dict["min_file_size"] = int(arg)
            if opt == "--exclude-checkdate":
                ret_dict["exclude_checkdate"].append(self._parse_ecd(arg))
                #ret_dict["min_file_size"] = int(arg)
        return ok, why, [my_lim, ret_dict]
    def _parse_ecd(self, in_str):
        # parse exclude_checkdate, ecd has the form [WHHMM][-WHHMM]
        # W ... weekday, 1 ... monday, 7 ... sunday
        if in_str.count("-"):
            start_str, end_str = in_str.strip().split("-")
            if not len(start_str):
                start_str = None
            if not len(end_str):
                end_str = None
        else:
            start_str, end_str = (in_str.strip(), None)
        return (self._parse_ecd2(start_str), self._parse_ecd2(end_str))
    def _parse_ecd2(self, in_str):
        if in_str is None:
            return in_str
        else:
            if len(in_str) != 5 or not in_str.isdigit():
                raise SyntaxError, "exclude_checkdate '%s' has wrong form (not WHHMM)" % (in_str)
            weekday, hour, minute = (int(in_str[0]),
                                     int(in_str[1:3]),
                                     int(in_str[3:5]))
            if weekday < 1 or weekday > 7:
                raise SyntaxError, "exclude_checkdate '%s' has invalid weekday" % (in_str)
            if hour < 0 or hour > 23:
                raise SyntaxError, "exclude_checkdate '%s' has invalid hour" % (in_str)
            if minute < 0 or minute > 59:
                raise SyntaxError, "exclude_checkdate '%s' has invalid minute" % (in_str)
            return (weekday, hour, minute)
    def process_server_args(self, glob_config, logger):
        self.__logger = logger
        return (True, "")
    def init(self, mode, logger, basedir_name, **args):
        if mode == "i":
            self.__thread_pool = None
        elif mode == "s":
            self.__thread_pool = args["thread_pool"]
    def start_resync(self):
        if not self.__thread_pool:
            return "error no thread_pool defined"
        elif "config" in self.__thread_pool.get_thread_names():
            return "error sync_thread already running"
        else:
            loc_queue = Queue.Queue(10)
            t_obj = self.__thread_pool.add_thread(config_subthread(loc_queue, self.__logger), start_thread=True)
            if t_obj:
                return loc_queue.get()
            else:
                return "error cannot start sync_thread"
    
class config_subthread(threading_tools.thread_obj):
    def __init__(self, loc_queue, logger):
        self.__logger = logger
        threading_tools.thread_obj.__init__(self, "config", queue_size=100, loop_function=self._run)
        self.__loc_queue = loc_queue
    def thread_running(self):
        self.send_pool_message(("new_pid", os.getpid()))
    def log(self, what, lev=logging_tools.LOG_LEVEL_OK):
        self.__logger.log(lev, what)
    def _run(self):
        boot_server_name = "/etc/motherserver"
        if os.path.isfile(boot_server_name):
            try:
                self.__boot_server = file(boot_server_name, "r").read().split("\n")[0].strip()
            except:
                init_message = "error unable to read motherserver from in %s" % (boot_server_name)
                self.log("error reading motherserver from %s: %s" % (boot_server_name,
                                                                     process_tools.get_except_info()),
                         logging_tools.LOG_LEVEL_ERROR)
            else:
                init_message = "ok syncing config from %s" % (self.__boot_server)
                self.log(init_message)
        else:
            init_message = "no motherserver defined via %s" % (boot_server_name)
            self.log(init_message, logging_tools.LOG_LEVEL_ERROR)
        self.__loc_queue.put(init_message)
        # get target_sn
        act_stat, act_out = self._net_command("get_target_sn")
        if not act_stat:
            act_stat, act_out = self._interpret_target_sn(act_out)
            print act_out
        self.get_thread_pool().stop_thread(self.name)
    def _net_command(self, command, **args):
        port = args.get("port", 8006)
        timeout = args.get("timeout", 10)
        s_time = time.time()
        self.log("sending '%s' to %s (port %d)" % (command,
                                                   self.__boot_server,
                                                   port))
        act_stat, act_out = net_tools.single_connection(mode="tcp",
                                                        host=self.__boot_server,
                                                        port=port,
                                                        command=command,
                                                        timeout=timeout,
                                                        protocoll=1).iterate()
        e_time = time.time()
        self.log("  got result after %s (stat is %d)%s" % (logging_tools.get_diff_time_str(e_time - s_time),
                                                           act_stat,
                                                           ": %s" % (act_out) if act_stat else ""),
                 logging_tools.LOG_LEVEL_ERROR if act_stat else logging_tools.LOG_LEVEL_OK)
        return act_stat, act_out
    def _interpret_target_sn(self, in_str):
        return 1, in_str
        
class resync_config_command(hm_classes.hmb_command):
    def __init__(self, **args):
        hm_classes.hmb_command.__init__(self, "resync_config", **args)
        self.help_str = "call /root/bin/resync_config.sh (if present)"
        self.timeout = 30
        self.net_only = True
    def server_call(self, cm):
        return self.module_info.start_resync()
        boot_server_name = "/etc/motherserver"
        mount_options = "-o noacl,udp"
        try:
            boot_server = file(boot_server_name, "r").read().split("\n")[0].strip()
        except IOError:
            return "error no motherserver defined in %s" % (boot_server_name)
        # call get_target_state
        stat, com_out = msock.single_tcp_connection((boot_server, 8006, "get_target_sn"), None, 30, 1)
        if stat:
            self.log("Something bad happend while sending get_target_sn to config_server (%d):" % (stat))
            for l in com_out.split("\n"):
                self.log(" - %s" % (l.rstrip()))
        else:
            com_parts = com_out.strip().split()
            target_state, prod_net, dev_name = (com_parts[1], com_parts[2], com_parts[5])
            self.log("Target state is '%s', target network is '%s', device_name is '%s'" % (target_state, prod_net, dev_name))
            # call create_config
            stat, com_out = msock.single_tcp_connection((boot_server, 8006, "create_config"), None, 30, 1)
            if stat:
                self.log("Something bad happend while sending create_config to config_server (%d):" % (stat))
                for l in com_out.split("\n"):
                    self.log(" - %s" % (l.rstrip()))
            else:
                time.sleep(2)
                while 1:
                    stat, com_out = msock.single_tcp_connection((boot_server, 8006, "ack_config"), None, 30, 1)
                    if stat:
                        self.log("Something bad happend while sending create_config to config_server (%d):" % (stat))
                        for l in com_out.split("\n"):
                            self.log(" - %s" % (l.rstrip()))
                        break
                    if com_out.startswith("wait"):
                        time.sleep(5)
                    else:
                        break
                if not stat:
                    self.log("Config is ready")
                    temp_dir = tempfile.mkdtemp("rc", ".rc_")
                    self.log("trying to mount config for device %s from %s with options %s to %s" % (dev_name, boot_server, mount_options, temp_dir))
                    mount_com = "mount -o noacl %s:/tftpboot/config/%s %s" % (boot_server, dev_name, temp_dir)
                    umount_com = "umount %s" % (temp_dir)
                    stat, com_out = commands.getstatusoutput(mount_com)
                    if stat:
                        self.log("Something bad happend while trying to do '%s' (%d):" % (mount_com, stat))
                        for l in com_out.split("\n"):
                            self.log(" - %s" % (l.rstrip()))
                        ret_str = "error mounting (%s)" % (mount_com)
                    else:
                        self.log("Successfully mounted config")
                        try:
                            old_config_files = [x.strip() for x in file("%s/.config_files" % (temp_dir), "r").read().split("\n")]
                        except IOError:
                            self.log("No old config-files found")
                        else:
                            self.log("Found %s, deleting them now ..." % (logging_tools.get_plural("file", len(old_config_files))))
                            num_del_ok, error_dels = (0, [])
                            for f_name in old_config_files:
                                try:
                                    os.unlink("%s+" % (f_name))
                                except (IOError, OSError):
                                    error_dels += [f_name]
                                else:
                                    num_del_ok += 1
                            self.log("successfully deleted %s, %s: %s" % (logging_tools.get_plural("file", num_del_ok),
                                                                          logging_tools.get_plural("error file", len(error_dels)),
                                                                          ", ".join(error_dels)))
                            os.unlink("%s/.config_files" % (temp_dir))
                        generated, error_objs = ([], [])
                        if os.path.isfile("%s/config_dirs_%s" % (temp_dir, prod_net)):
                            self.log("Generating directories ...")
                            for new_dir in [x.strip() for x in file("%s/config_dirs_%s" % (temp_dir, prod_net), "r").read().split("\n") if x.strip()]:
                                dir_num, dir_uid, dir_gid, dir_mode, dir_name = new_dir.split()
                                dir_uid, dir_gid, int_dir_mode = (int(dir_uid), int(dir_gid), int(dir_mode, 8))
                                try:
                                    os.makedirs(dir_name)
                                    os.chmod(dir_name, int_dir_mode)
                                    os.chown(dir_name, dir_uid, dir_gid)
                                except OSError:
                                    self.log(" * some error occured while trying to generate %s (uid %d, gid %d, mode %s): %s" % (dir_name, dir_uid, dir_gid, dir_mode, sys.exc_info()[1]))
                                else:
                                    self.log(" - generated dir %s (uid %d, gid %d, mode %s)" % (dir_name, dir_uid, dir_gid, dir_mode))
                        if os.path.isfile("%s/config_files_%s" % (temp_dir, prod_net)):
                            self.log("Generating files ...")
                            for new_file in [x.strip() for x in file("%s/config_files_%s" % (temp_dir, prod_net), "r").read().split("\n") if x.strip()]:
                                file_num, file_uid, file_gid, file_mode, file_name = new_file.split()
                                file_num, file_uid, file_gid, int_file_mode = (int(file_num), int(file_uid), int(file_gid), int(file_mode, 8))
                                file_dir = os.path.dirname(file_name)
                                if not os.path.isdir(file_dir):
                                    try:
                                        os.makedirs(file_dir)
                                    except IOError:
                                        self.log(" * error creating directory %s for file %s: %s" % (file_dir, file_name, sys.exc_info()[1]))
                                    else:
                                        self.log(" - created directory %s for file %s" % (file_dir, file_name))
                                if os.path.isdir(file_dir):
                                    try:
                                        file(file_name, "w").write(file("%s/content_%s/%d" % (temp_dir, prod_net, file_num), "r").read())
                                        os.chmod(file_name, int_file_mode)
                                        os.chown(file_name, file_uid, file_gid)
                                    except:
                                        self.log(" * some error occured while trying to generate %s (uid %d, gid %d, mode %s): %s" % (file_name, file_uid, file_gid, file_mode, sys.exc_info()[1]))
                                        error_objs.append(file_name)
                                    else:
                                        self.log(" - generated file %s (uid %d, gid %d, mode %s)" % (file_name, file_uid, file_gid, file_mode))
                                        generated.append(file_name)
                                else:
                                    error_objs.append(file_name)
                        if os.path.isfile("%s/config_links_%s" % (temp_dir, prod_net)):
                            self.log("Generating links ...")
                            for new_link in [x.strip() for x in file("%s/config_links_%s" % (temp_dir, prod_net), "r").read().split("\n") if x.strip()]:
                                link_dest, link_src = new_link.split()
                                if os.path.islink(link_src):
                                    try:
                                        os.unlink(link_src)
                                    except IOError:
                                        self.log(" * error removing old link source %s" % (link_src))
                                    else:
                                        self.log(" - removed old link source %s" % (link_src))
                                if not os.path.isfile(link_src) and not os.path.islink(link_src):
                                    try:
                                        os.symlink(link_dest, link_src)
                                    except IOError:
                                        self.log(" * error generating link '%s' pointing to '%s'" % (link_src, link_dest))
                                        error_objs.append(link_src)
                                    else:
                                        self.log(" - generated link '%s' pointing to '%s'" % (link_src, link_dest))
                                        generated.append(link_src)
                                else:
                                    self.log(" * error old link source %s still present" % (link_src))
                                    error_objs.append(link_src)
                        self.log("%s generated successfully, %s" % (logging_tools.get_plural("object", len(generated)),
                                                                    logging_tools.get_plural("problem object", len(error_objs))))
                        stat, com_out = commands.getstatusoutput(umount_com)
                        if stat:
                            self.log("Something bad happend while trying to do '%s' (%d):" % (mount_com, stat))
                            for l in com_out.split("\n"):
                                self.log(" - %s" % (l.rstrip()))
                            ret_str = "error umounting (%s)" % (umount_com)
                        else:
                            self.log("Successfully unmounted config")
                            if error_objs:
                                ret_str = "warn %s with problems, %d ok" % (logging_tools.get_plural("object", len(error_objs)), len(generated))
                            else:
                                ret_str = "ok %s generated" % (logging_tools.get_plural("object", len(generated)))
        return ret_str
    def client_call(self, result, parsed_coms):
        if result.startswith("error"):
            return limits.nag_STATE_CRITICAL, result
        else:
            return limits.nag_STATE_OK, result

class call_script_command(hm_classes.hm_command):
    def __init__(self, name):
        hm_classes.hm_command.__init__(self, name, positional_arguments=True, server_arguments=True)
        self.server_parser.add_argument("--at-time", dest="time", type=int, default=0)
        self.server_parser.add_argument("--use-at", dest="use_at", default=False, action="store_true")
    def __call__(self, srv_com, cur_ns):
        if not "arguments:arg0" in srv_com:
            srv_com["result"].attrib.update({
                "reply" : "missing argument",
                "state" : "%d" % (server_command.SRV_REPLY_STATE_ERROR)})
        else:
            script_name = srv_com["arguments:arg0"].text
            args = []
            while "arguments:arg%d" % (len(args) + 1) in srv_com:
                args.append(srv_com["arguments:arg%d" % (len(args) + 1)].text)
            if os.path.isfile(script_name):
                if cur_ns.time:
                    cur_ns.use_at = True
                info_str = "Starting script %s with %s: %s" % (
                    script_name,
                    logging_tools.get_plural("argument", len(args)),
                    " ".join(args))
                if cur_ns.use_at:
                    info_str = "%s after %s" % (
                        info_str,
                        logging_tools.get_plural("minute", cur_ns.time))
                self.log(info_str)
                if cur_ns.use_at:
                    c_stat, log_lines = process_tools.submit_at_command(
                        " ".join([script_name] + args),
                        cur_ns.time)
                    ipl = "\n".join(log_lines)
                else:
                    c_stat, ipl = commands.getstatusoutput(
                        " ".join([script_name] + args))
                    log_lines = ipl.split("\n")
                self.log(" - gave stat %d (%s):" % (c_stat,
                                                    logging_tools.get_plural("log line", len(log_lines))))
                for line in map(lambda s_line: s_line.strip(), log_lines):
                    self.log("   - %s" % (line))
                if c_stat:
                    srv_com["result"].attrib.update({
                        "reply" : "problem while executing %s: %s" % (script_name, ipl),
                        "state" : "%d" % (server_command.SRV_REPLY_STATE_ERROR)})
                else:
                    srv_com["result"].attrib.update({
                        "reply" : "script %s gave: %s" % (script_name, ipl),
                        "state" : "%d" % (server_command.SRV_REPLY_STATE_OK)})
            else:
                srv_com["result"].attrib.update({
                    "reply" : "script  %s not found" % (script_name),
                    "state" : "%d" % (server_command.SRV_REPLY_STATE_ERROR)})
    def interpret(self, srv_com, cur_ns):
        return limits.nag_STATE_OK, srv_com["result"].attrib["reply"]

class create_file(hm_classes.hmb_command):
    def __init__(self, **args):
        hm_classes.hmb_command.__init__(self, "create_file", **args)
        self.help_str = "creates a (preferable small) file"
        self.short_client_info = "[KEY:value] file content"
    def server_call(self, cm):
        if len(cm) < 2:
            return "error need at least filename and content"
        file_content = cm.pop()
        file_name = cm.pop()
        if not file_name.startswith("/"):
            return "error file_name has to start with '/'"
        dir_name, file_name = (os.path.dirname(file_name), 
                               os.path.basename(file_name))
        if not os.path.isdir(dir_name):
            return "error directory '%s' does not exist" % (dir_name)
        file_dict = {"uid"         : 0,
                     "gid"         : 0,
                     "overwrite"   : False,
                     "add_newline" : False}
        # parse keys
        for key in cm:
            if key.count(":"):
                key, value = key.split(":", 1)
            else:
                value = True
            if key not in file_dict:
                return "error key '%s' not known (has to be one of: %s)" % (key,
                                                                            ", ".join(sorted(file_dict.keys())))
            orig_value = file_dict[key]
            try:
                if type(orig_value) == type(True):
                    dest_type = "bool"
                    value = bool(value)
                elif type(orig_value) == type(0):
                    dest_type = "int"
                    value = int(value)
                else:
                    dest_type = "string"
            except:
                return "error casting value '%s' (type %s) of key %s" % (str(value),
                                                                         dest_type,
                                                                         key)
            file_dict[key] = value
        full_name = os.path.join(dir_name, file_name)
        if os.path.exists(full_name) and not file_dict["overwrite"]:
            return "error file '%s' already exists" % (full_name)
        self.log("trying to create file '%s' (content is '%s'), dict has %s:" % (full_name,
                                                                                 file_content,
                                                                                 logging_tools.get_plural("key", len(file_dict.keys()))))
        for key, entry in file_dict.iteritems():
            self.log(" - %-20s: %s" % (key, str(entry)))
        try:
            file(full_name, "w").write("%s%s" % (file_content,
                                                 "\n" if file_dict["add_newline"] else ""))
        except:
            err_str = "error creating file '%s': %s" % (full_name,
                                                        process_tools.get_except_info())
            self.log(err_str, logging_tools.LOG_LEVEL_ERROR)
            return err_str
        try:
            os.chown(full_name, file_dict["uid"], file_dict["gid"])
        except:
            pass
        return "ok created file '%s'" % (full_name)
    def client_call(self, result, parsed_coms):
        if result.startswith("error"):
            return limits.nag_STATE_CRITICAL, result
        else:
            return limits.nag_STATE_OK, result

class check_dir(hm_classes.hmb_command):
    def __init__(self, **args):
        hm_classes.hmb_command.__init__(self, "check_dir", **args)
        self.help_str = "checks a directory and returns it stat"
        self.short_client_info = "dir"
        self.long_client_info = "dir checker"
        self.short_client_opts = ""
        self.long_client_opts = []
    def server_call(self, cm):
        if len(cm) < 1:
            return "error need dirname"
        dir_name = cm[0]
        link_followed = False
        while os.path.islink(dir_name):
            link_followed = True
            dir_name = os.readlink(dir_name)
        if os.path.isdir(dir_name):
            f_stat = os.stat(dir_name)
            return "ok %s" % (hm_classes.sys_to_net({"dir"           : dir_name,
                                                     "stat"          : f_stat,
                                                     "link_followed" : link_followed,
                                                     "local_time"    : time.time()}))
        else:
            return "error dir %s not found%s" % (dir_name,
                                                 " (link_followed)" if link_followed else "")
    def client_call(self, result, parsed_coms):
        if result.startswith("error"):
            return limits.nag_STATE_CRITICAL, result
        else:
            f_dict = hm_classes.net_to_sys(result[3:])
            ret_state = limits.nag_STATE_OK
            dir_stat = f_dict["stat"]
            return ret_state, "%s dir %s exists" % (limits.get_state_str(ret_state),
                                                    f_dict["dir"])

if __name__ == "__main__":
    print "This is a loadable module."
    sys.exit(0)
