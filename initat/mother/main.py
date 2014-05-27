# -*- coding: utf-8 -*-
#
# Copyright (C) 2001-2009,2012-2014 Andreas Lang-Nevyjel, init.at
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
""" mother daemon, main part """

from initat.cluster.backbone.models import log_source
from initat.mother.config import global_config
from initat.mother.version import VERSION_STRING
import cluster_location
import config_tools
import configfile
import initat.mother.server
import os
import process_tools
import sys

def main():
    _long_host_name, mach_name = process_tools.get_fqdn()
    prog_name = global_config.name()
    global_config.add_config_entries([
        ("DEBUG"               , configfile.bool_c_var(False, help_string="enable debug mode [%(default)s]", short_options="d", only_commandline=True)),
        ("ZMQ_DEBUG"           , configfile.bool_c_var(False, help_string="enable 0MQ debugging [%(default)s]", only_commandline=True)),
        ("PID_NAME"            , configfile.str_c_var(os.path.join(prog_name, prog_name))),
        ("KILL_RUNNING"        , configfile.bool_c_var(True, help_string="kill running instances [%(default)s]")),
        ("FORCE"               , configfile.bool_c_var(False, help_string="force running [%(default)s]", action="store_true", only_commandline=True)),
        ("CHECK"               , configfile.bool_c_var(False, help_string="only check for server status", action="store_true", only_commandline=True, short_options="C")),
        ("LOG_DESTINATION"     , configfile.str_c_var("uds:/var/lib/logging-server/py_log_zmq")),
        ("LOG_NAME"            , configfile.str_c_var(prog_name)),
        ("USER"                , configfile.str_c_var("root", help_string="user to run as [%(default)s]")),
        ("GROUP"               , configfile.str_c_var("root", help_string="group to run as [%(default)s]")),
        ("LOG_DESTINATION"     , configfile.str_c_var("uds:/var/lib/logging-server/py_log_zmq")),
        ("LOG_NAME"            , configfile.str_c_var(prog_name)),
        ("MODIFY_NFS_CONFIG"   , configfile.bool_c_var(True, help_string="modify /etc/exports [%(default)s]", action="store_true")),
        ("VERBOSE"             , configfile.int_c_var(0, help_string="set verbose level [%(default)d]", short_options="v", only_commandline=True)),
        ("SERVER_PUB_PORT"     , configfile.int_c_var(8000, help_string="server publish port [%(default)d]")),
        ("SERVER_PULL_PORT"    , configfile.int_c_var(8001, help_string="server pull port [%(default)d]")),
    ])
    global_config.parse_file()
    _options = global_config.handle_commandline(
        description="%s, version is %s" % (
            prog_name,
            VERSION_STRING),
        add_writeback_option=True,
        positional_arguments=False)
    global_config.write_file()
    sql_info = config_tools.server_check(server_type="mother_server")
    if not sql_info.effective_device:
        print "not a mother_server"
        sys.exit(5)
    if global_config["CHECK"]:
        sys.exit(0)
    if global_config["KILL_RUNNING"]:
        _log_lines = process_tools.kill_running_processes(prog_name + ".py", exclude=configfile.get_manager_pid())
    cluster_location.read_config_from_db(global_config, "mother_server", [
        ("TFTP_LINK"                 , configfile.str_c_var("/tftpboot")),
        ("TFTP_DIR"                  , configfile.str_c_var("/opt/cluster/system/tftpboot")),
        ("CLUSTER_DIR"               , configfile.str_c_var("/opt/cluster")),
        ("NODE_PORT"                 , configfile.int_c_var(2001)),
        # in 10th of seconds
        ("NODE_BOOT_DELAY"           , configfile.int_c_var(50)),
        ("FANCY_PXE_INFO"            , configfile.bool_c_var(False)),
        ("SERVER_SHORT_NAME"         , configfile.str_c_var(mach_name))])
    global_config.add_config_entries([
        ("CONFIG_DIR"   , configfile.str_c_var("%s/%s" % (global_config["TFTP_DIR"], "config"))),
        ("ETHERBOOT_DIR", configfile.str_c_var("%s/%s" % (global_config["TFTP_DIR"], "etherboot"))),
        ("KERNEL_DIR"   , configfile.str_c_var("%s/%s" % (global_config["TFTP_DIR"], "kernels")))])
    global_config.add_config_entries([
        ("LOG_SOURCE_IDX", configfile.int_c_var(log_source.create_log_source_entry("mother", "Mother Server", device=sql_info.device).pk)),
        ("NODE_SOURCE_IDX", configfile.int_c_var(log_source.create_log_source_entry("node", "Clusternode").pk)),
    ])
    process_tools.renice()
    if not global_config["DEBUG"]:
        # become daemon and wait 2 seconds
        process_tools.become_daemon(wait=2)
        process_tools.set_handles({"out" : (1, "mother.out"),
                                   "err" : (0, "/var/lib/logging-server/py_err")})
    else:
        print "Debugging mother"
    ret_state = initat.mother.server.server_process().loop()
    sys.exit(ret_state)

