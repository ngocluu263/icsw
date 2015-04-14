# Copyright (C) 2013-2014 Andreas Lang-Nevyjel
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
""" SNMP relayer """

from io_stream_helper import io_stream
import configfile
import daemon
import os
import process_tools
import sys


def run_code():
    from initat.snmp_relay.server import server_process
    server_process().loop()


def main():
    # read global configfile
    global_config = configfile.configuration(process_tools.get_programm_name(), single_process_mode=True)
    prog_name = global_config.name()
    global_config.add_config_entries([
        ("BASEDIR_NAME", configfile.str_c_var("/etc/sysconfig/snmp-relay.d")),
        ("DEBUG", configfile.bool_c_var(False, help_string="enable debug mode [%(default)s]", short_options="d", only_commandline=True)),
        ("ZMQ_DEBUG", configfile.bool_c_var(False, help_string="enable 0MQ debugging [%(default)s]", only_commandline=True)),
        ("VERBOSE", configfile.int_c_var(0)),
        ("DAEMONIZE", configfile.bool_c_var(True)),
        ("SNMP_PROCESSES", configfile.int_c_var(4, help_string="number of SNMP processes [%(default)d]", short_options="n")),
        ("MAIN_TIMER", configfile.int_c_var(60, help_string="main timer [%(default)d]")),
        ("KILL_RUNNING", configfile.bool_c_var(True)),
        ("BACKLOG_SIZE", configfile.int_c_var(5, help_string="backlog size for 0MQ sockets [%(default)d]")),
        ("LOG_NAME", configfile.str_c_var("snmp-relay")),
        ("LOG_DESTINATION", configfile.str_c_var("uds:/var/lib/logging-server/py_log_zmq")),
        ("MAX_CALLS", configfile.int_c_var(100, help_string="number of calls per helper process [%(default)d]")),
        ("VERBOSE", configfile.int_c_var(0, help_string="set verbose level [%(default)d]", short_options="v", only_commandline=True)),
        (
            "PID_NAME",
            configfile.str_c_var(
                "%s/%s" % (
                    prog_name,
                    prog_name
                )
            )
        )
    ])
    global_config.parse_file()
    _options = global_config.handle_commandline(
        positional_arguments=False,
        partial=False,
        add_writeback_option=True,
    )
    global_config.write_file()
    if global_config["KILL_RUNNING"]:
        process_tools.kill_running_processes()
    process_tools.ALLOW_MULTIPLE_INSTANCES = False
    process_tools.renice()
    if global_config["DAEMONIZE"] and not global_config["DEBUG"]:
        with daemon.DaemonContext():
            sys.stdout = io_stream("/var/lib/logging-server/py_log_zmq")
            sys.stderr = io_stream("/var/lib/logging-server/py_err_zmq")
            global_config = configfile.get_global_config(prog_name, parent_object=global_config)
            run_code()
            configfile.terminate_manager()
        # exit
        os._exit(0)
    else:
        print "Debugging snmp-relayer"
        global_config = configfile.get_global_config(prog_name, parent_object=global_config)
        run_code()
    sys.exit(0)