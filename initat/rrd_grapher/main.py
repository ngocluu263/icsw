#!/usr/bin/python-init -Ot
#
# Copyright (C) 2007,2008,2009,2013 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file belongs to the rrd-server package
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
""" rrd-grapher for graphing rrd-data """

import os
import sys

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "initat.cluster.settings")

from django.conf import settings
from initat.rrd_grapher.config import global_config
from initat.rrd_grapher.server import server_process
import cluster_location
import config_tools
import configfile
import process_tools

try:
    from initat.rrd_grapher.version import VERSION_STRING
except ImportError:
    VERSION_STRING = "?.?"

SERVER_COM_PORT = 8003

def _create_dirs():
    graph_root = global_config["GRAPH_ROOT"]
    if not os.path.isdir(graph_root):
        try:
            os.makedirs(graph_root)
        except:
            print("*** cannot create graph_root '%s': %s" % (graph_root, process_tools.get_except_info()))
        else:
            print("created graph_root '%s'" % (graph_root))

def main():
    long_host_name, _mach_name = process_tools.get_fqdn()
    prog_name = global_config.name()
    global_config.add_config_entries([
        ("DEBUG"               , configfile.bool_c_var(False, help_string="enable debug mode [%(default)s]", short_options="d", only_commandline=True)),
        ("ZMQ_DEBUG"           , configfile.bool_c_var(False, help_string="enable 0MQ debugging [%(default)s]", only_commandline=True)),
        ("KILL_RUNNING"        , configfile.bool_c_var(True, help_string="kill running instances [%(default)s]")),
        ("CHECK"               , configfile.bool_c_var(False, short_options="C", help_string="only check for server status", action="store_true", only_commandline=True)),
        ("USER"                , configfile.str_c_var("idrrd", help_string="user to run as [%(default)s")),
        ("GROUP"               , configfile.str_c_var("idg", help_string="group to run as [%(default)s]")),
        ("GROUPS"              , configfile.array_c_var([])),
        ("LOG_DESTINATION"     , configfile.str_c_var("uds:/var/lib/logging-server/py_log_zmq")),
        ("LOG_NAME"            , configfile.str_c_var(prog_name)),
        ("PID_NAME"            , configfile.str_c_var(os.path.join(prog_name,
                                                                   prog_name))),
        ("COM_PORT"            , configfile.int_c_var(SERVER_COM_PORT)),
        ("SERVER_PATH"         , configfile.bool_c_var(False, help_string="set server_path to store RRDs [%(default)s]", only_commandline=True)),
        ("VERBOSE"             , configfile.int_c_var(0, help_string="set verbose level [%(default)d]", short_options="v", only_commandline=True)),
        ("RRD_DIR"             , configfile.str_c_var("/var/cache/rrd", help_string="directory of rrd-files on local disc")),
        ("COLORTABLE_FILE"     , configfile.str_c_var("/opt/cluster/share/colortables.xml", help_string="name of colortable file")),
        ("COLORRULES_FILE"     , configfile.str_c_var("/opt/cluster/share/color_rules.xml", help_string="name of color_rules file")),
    ])
    global_config.parse_file()
    options = global_config.handle_commandline(
        description="%s, version is %s" % (prog_name,
                                           VERSION_STRING),
        add_writeback_option=True,
        positional_arguments=False)
    global_config.write_file()
    sql_info = config_tools.server_check(server_type="rrd_server")
    if not sql_info.effective_device:
        print "not an rrd_server"
        sys.exit(5)
    else:
        global_config.add_config_entries([("SERVER_IDX", configfile.int_c_var(sql_info.effective_device.pk, database=False))])
    if global_config["CHECK"]:
        sys.exit(0)
    if global_config["KILL_RUNNING"]:
        _log_lines = process_tools.kill_running_processes(
            "%s.py" % (prog_name),
            ignore_names=[],
            exclude=configfile.get_manager_pid())

    cur_dir = os.path.dirname(os.path.abspath(__file__))
    global_config.add_config_entries(
        [
            ("LOG_SOURCE_IDX", configfile.int_c_var(cluster_location.log_source.create_log_source_entry("rrd-server", "Cluster RRDServer", device=sql_info.effective_device).pk)),
            ("GRAPH_ROOT"    , configfile.str_c_var(
                os.path.abspath(os.path.join(
                    settings.STATIC_ROOT_DEBUG if global_config["DEBUG"] else settings.STATIC_ROOT, # if (not global_config["DEBUG"] or options.SERVER_PATH) else "/usr/local/share/home/local/development/git/webfrontend/django/initat/cluster",
                    "graphs"))))
        ]
    )
    _create_dirs()

    process_tools.renice()
    process_tools.fix_directories(global_config["USER"], global_config["GROUP"], ["/var/run/rrd-grapher", global_config["GRAPH_ROOT"]])
    global_config.set_uid_gid(global_config["USER"], global_config["GROUP"])
    process_tools.change_user_group(global_config["USER"], global_config["GROUP"], global_config["GROUPS"], global_config=global_config)
    if not global_config["DEBUG"]:
        process_tools.become_daemon()
    else:
        print "Debugging rrd-grapher on %s" % (long_host_name)
    ret_state = server_process().loop()
    sys.exit(ret_state)

