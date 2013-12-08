#!/usr/bin/python-init -Ot
# -*- coding: utf-8 -*-
#
# Copyright (C) 2001,2002,2003,2004,2005,2006,2007,2008,2010,2011,2012,2013 Andreas Lang-Nevyjel
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of meta-server
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
""" meta-server, main part """

from initat.meta_server.config import global_config
from initat.meta_server.server import main_process
import configfile
import process_tools
import socket
import sys

try:
    from initat.meta_server.version import VERSION_STRING
except ImportError:
    VERSION_STRING = "?.?"

def main():
    long_host_name, _mach_name = process_tools.get_fqdn()
    global_config.add_config_entries([
        ("MAILSERVER"          , configfile.str_c_var("localhost", info="Mail Server")),
        ("DEBUG"               , configfile.bool_c_var(False, help_string="enable debug mode [%(default)s]", short_options="d", only_commandline=True)),
        ("ZMQ_DEBUG"           , configfile.bool_c_var(False, help_string="enable 0MQ debugging [%(default)s]", only_commandline=True)),
        ("COM_PORT"            , configfile.int_c_var(8012, info="listening Port", help_string="port to communicate [%(default)i]", short_options="p")),
        ("LOG_DESTINATION"     , configfile.str_c_var("uds:/var/lib/logging-server/py_log")),
        ("LOG_NAME"            , configfile.str_c_var("meta-server")),
        ("MAIN_DIR"            , configfile.str_c_var("/var/lib/meta-server")),
        ("KILL_RUNNING"        , configfile.bool_c_var(True)),
        ("FROM_NAME"           , configfile.str_c_var("meta-server")),
        ("FROM_ADDR"           , configfile.str_c_var(socket.getfqdn())),
        ("TO_ADDR"             , configfile.str_c_var("lang-nevyjel@init.at", help_string="mail address to send error-emails to [%(default)s]", short_options="t")),
        ("FAILED_CHECK_TIME"   , configfile.int_c_var(120, info="time in seconds to wait befor we do something")),
        ("TRACK_CSW_MEMORY"    , configfile.bool_c_var(False, help_string="enable tracking of the memory usage of the CSW [%(default)b]", action="store_true")),
        ("MIN_CHECK_TIME"      , configfile.int_c_var(6, info="minimum time between two checks")),
        ("KILL_RUNNING"        , configfile.bool_c_var(True)),
        ("SERVER_FULL_NAME"    , configfile.str_c_var(long_host_name)),
        ("PID_NAME"            , configfile.str_c_var("meta-server"))])
    global_config.parse_file()
    options = global_config.handle_commandline(description="meta-server, version is %s" % (VERSION_STRING))
    global_config.write_file()
    if global_config["KILL_RUNNING"]:
        if global_config.single_process_mode():
            process_tools.kill_running_processes()
        else:
            process_tools.kill_running_processes(exclude=configfile.get_manager_pid())
    # process_tools.fix_directories("root", "root", [(glob_config["MAIN_DIR"], 0777)])
    if not options.DEBUG:
        process_tools.become_daemon()
    else:
        print "Debugging meta-server on %s" % (global_config["SERVER_FULL_NAME"])
    main_process().loop()
    sys.exit(0)

