# Copyright (C) 2014-2016 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# this file is part of discovery-server
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
""" discovery-server, server part """

import zmq
from django.db.models import Q

from initat.cluster.backbone.server_enums import icswServiceEnum
from initat.cluster.backbone import db_tools
from initat.cluster.backbone.models import device, DeviceScanLock
from initat.discovery_server.event_log.event_log_poller import EventLogPollerProcess
from initat.discovery_server.generate_assets_process import GenerateAssetsProcess
from initat.snmp.process import snmp_process_container
from initat.tools import cluster_location, configfile, logging_tools, process_tools, \
    server_command, server_mixins, threading_tools, net_tools
from initat.tools.server_mixins import RemoteCall
from .config import global_config, IPC_SOCK_SNMP
from .discovery import DiscoveryProcess


@server_mixins.RemoteCallProcess
class server_process(server_mixins.ICSWBasePool, server_mixins.RemoteCallMixin):
    def __init__(self):
        threading_tools.process_pool.__init__(self, "main", zmq=True)
        self.register_exception("int_error", self._int_error)
        self.register_exception("term_error", self._int_error)
        self.CC.init(icswServiceEnum.discovery_server, global_config)
        self.CC.check_config()
        self.__pid_name = global_config["PID_NAME"]
        # close connection (daemonize)
        db_tools.close_connection()
        self.CC.read_config_from_db(
            [
                ("SNMP_PROCESSES", configfile.int_c_var(4, help_string="number of SNMP processes [%(default)d]", short_options="n")),
                ("MAX_CALLS", configfile.int_c_var(100, help_string="number of calls per helper process [%(default)d]")),
            ]
        )
        self.CC.re_insert_config()
        self._log_config()
        self.__msi_block = self._init_msi_block()
        self.add_process(DiscoveryProcess("discovery"), start=True)
        self.add_process(EventLogPollerProcess(EventLogPollerProcess.PROCESS_NAME), start=True)
        self.add_process(GenerateAssetsProcess("generate_assets"), start=True)
        self._init_network_sockets()
        self.register_func("snmp_run", self._snmp_run)
        self.register_func("generate_assets", self._generate_assets)
        self.register_func("send_msg", self.send_msg)
        db_tools.close_connection()
        self.__max_calls = global_config["MAX_CALLS"] if not global_config["DEBUG"] else 5
        self.__snmp_running = True
        self._init_processes()
        # not really necessary
        self.install_remote_call_handlers()
        # clear pending scans
        self.clear_pending_scans()
        self.__run_idx = 0
        self.__pending_commands = {}
        if process_tools.get_machine_name() == "eddiex" and global_config["DEBUG"]:
            self._test()

    def clear_pending_scans(self):
        pending_locks = DeviceScanLock.objects.filter(Q(server=global_config["SERVER_IDX"]) & Q(active=True))
        if pending_locks.count():
            self.log("clearing {}".format(logging_tools.get_plural("active scan", pending_locks.count())))
            for _lock in pending_locks:
                [self.log(_what, _level) for _what, _level in _lock.close()]

    def _int_error(self, err_cause):
        if not self.__snmp_running:
            self.log("exit already requested, ignoring", logging_tools.LOG_LEVEL_WARN)
        else:
            self.spc.stop()
            self.__snmp_running = False
            self["exit_requested"] = True

    def _all_snmps_stopped(self):
        self["exit_requested"] = True

    def _snmp_process_start(self, **kwargs):
        self.__msi_block.add_actual_pid(
            kwargs["pid"],
            mult=kwargs.get("mult", 3),
            process_name=kwargs["process_name"],
            fuzzy_ceiling=kwargs.get("fuzzy_ceiling", 3)
        )
        self.__msi_block.save_block()
        process_tools.append_pids(self.__pid_name, kwargs["pid"], mult=kwargs.get("mult", 3))

    def _snmp_process_exit(self, **kwargs):
        self.__msi_block.remove_actual_pid(kwargs["pid"], mult=kwargs.get("mult", 3))
        self.__msi_block.save_block()
        process_tools.remove_pids(self.__pid_name, kwargs["pid"], mult=kwargs.get("mult", 3))

    def _init_processes(self):
        self.spc = snmp_process_container(
            IPC_SOCK_SNMP,
            self.log,
            global_config["SNMP_PROCESSES"],
            self.__max_calls,
            {
                "VERBOSE": global_config["VERBOSE"],
                "LOG_NAME": global_config["LOG_NAME"],
                "LOG_DESTINATION": global_config["LOG_DESTINATION"],
            },
            {
                "process_start": self._snmp_process_start,
                "process_exit": self._snmp_process_exit,
                "all_stopped": self._all_snmps_stopped,
                "finished": self._snmp_finished,
            }
        )

        _snmp_sock = self.spc.create_ipc_socket(self.zmq_context, IPC_SOCK_SNMP)
        self.register_poller(_snmp_sock, zmq.POLLIN, self.spc.handle_with_socket)  # @UndefinedVariable
        self.spc.check()

    def _log_config(self):
        self.log("Config info:")
        for line, log_level in global_config.get_log(clear=True):
            self.log(" - clf: [%d] %s" % (log_level, line))
        conf_info = global_config.get_config_info()
        self.log("Found {:d} valid config-lines:".format(len(conf_info)))
        for conf in conf_info:
            self.log("Config : {}".format(conf))

    def process_start(self, src_process, src_pid):
        mult = 3
        fuzzy_ceiling = 0
        if src_process == EventLogPollerProcess.PROCESS_NAME:
            fuzzy_ceiling = 5
        process_tools.append_pids(self.__pid_name, src_pid, mult=mult)
        self.__msi_block.add_actual_pid(src_pid, mult=mult, fuzzy_ceiling=fuzzy_ceiling, process_name=src_process)
        self.__msi_block.save_block()

    def _init_msi_block(self):
        process_tools.save_pid(self.__pid_name, mult=4)
        self.log("Initialising meta-server-info block")
        msi_block = process_tools.meta_server_info("discovery-server")
        msi_block.add_actual_pid(mult=3, fuzzy_ceiling=4)
        msi_block.kill_pids = True
        msi_block.save_block()
        return msi_block

    def loop_end(self):
        self.spc.close()
        process_tools.delete_pid(self.__pid_name)
        self.__msi_block.remove_meta_block()

    def loop_post(self):
        self.network_unbind()
        self.CC.close()

    def _init_network_sockets(self):
        self.network_bind(
            need_all_binds=False,
            bind_port=global_config["COMMAND_PORT"],
            bind_to_localhost=True,
            server_type="discovery",
            simple_server_bind=True,
            pollin=self.remote_call,
        )
        # dict for external connections
        self.__ext_con_dict = {}

    def send_msg(self, *args, **kwargs):
        _from_name, _from_pid, run_idx, conn_str, srv_com = args
        srv_com = server_command.srv_command(source=srv_com)
        srv_com["discovery_run_idx"] = "{:d}".format(run_idx)
        _new_con = net_tools.zmq_connection(
            "ext_con_discovery_{:d}".format(run_idx),
            context=self.zmq_context,
            poller_base=self,
            callback=self._ext_receive,
        )
        self.__ext_con_dict[run_idx] = _new_con
        _new_con.add_connection(conn_str, srv_com)

    def _ext_receive(self, *args):
        srv_reply = args[0]
        run_idx = int(srv_reply["*discovery_run_idx"])
        del self.__ext_con_dict[run_idx]
        self.send_to_process("discovery", "ext_con_result", run_idx, unicode(srv_reply))

    @RemoteCall()
    def status(self, srv_com, **kwargs):
        return self.server_status(srv_com, self.__msi_block, global_config, spc=self.spc)

    @RemoteCall(target_process="discovery")
    def scan_system_info(self, srv_com, **kwargs):
        return srv_com

    @RemoteCall(target_process="discovery")
    def scan_network_info(self, srv_com, **kwargs):
        return srv_com

    @RemoteCall(target_process="discovery")
    def snmp_basic_scan(self, srv_com, **kwargs):
        return srv_com

    @RemoteCall(target_process="discovery")
    def base_scan(self, srv_com, **kwargs):
        return srv_com

    @RemoteCall(target_process="discovery")
    def wmi_scan(self, srv_com, **kwargs):
        return srv_com

    @RemoteCall(target_process="discovery")
    def nrpe_scan(self, srv_com, **kwargs):
        return srv_com

    def _snmp_finished(self, args):
        self.send_to_process("discovery", "snmp_result", *args["args"])

    def _test(self):
        _srv_com = server_command.srv_command(command="snmp_basic_scan")
        _srv_com["devices"] = _srv_com.builder(
            "device",
            snmp_version="1",
            pk="{:d}".format(device.objects.get(Q(name='eddie')).pk),
            snmp_community="public",
            snmp_address="127.0.0.1",
            # snmp_address="192.168.1.50",
            # snmp_address="192.168.2.12",
        )
        self.send_to_process("discovery", _srv_com["*command"], unicode(_srv_com))

    def _snmp_run(self, *args, **kwargs):
        # ignore src specs
        _src_proc, _src_pid = args[0:2]
        self.spc.start_batch(*args[2:], **kwargs)

    def _generate_assets(self, *args, **kwargs):
        # send to generate_assets process
        self.send_to_process("generate_assets", "process_assets", args[2])
