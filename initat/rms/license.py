# Copyright (C) 2001-2014 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of rms-tools
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

""" rms-server, license monitoring part """

from django.db import connection
from initat.host_monitoring import hm_classes
from initat.rms.config import global_config
from lxml import etree  # @UnresolvedImport @UnusedImport
from lxml.builder import E  # @UnresolvedImport
import commands
import logging_tools
import os
import process_tools
import server_command
import sge_license_tools
import license_tool
import threading_tools
import time
import zmq


def call_command(command, log_com=None):
    start_time = time.time()
    stat, out = commands.getstatusoutput(command)
    end_time = time.time()
    log_lines = ["calling '{}' took {}, result (stat {:d}) is {} ({})".format(
        command,
        logging_tools.get_diff_time_str(end_time - start_time),
        stat,
        logging_tools.get_plural("byte", len(out)),
        logging_tools.get_plural("line", len(out.split("\n"))))]
    if log_com:
        for log_line in log_lines:
            log_com(" - {}".format(log_line))
        if stat:
            for log_line in out.split("\n"):
                log_com(" - {}".format(log_line))
        return stat, out
    else:
        if stat:
            # append output to log_lines if error
            log_lines.extend([" - {}".format(line) for line in out.split("\n")])
        return stat, out, log_lines


class license_process(threading_tools.process_obj):
    def process_init(self):
        self.__log_template = logging_tools.get_logger(
            global_config["LOG_NAME"],
            global_config["LOG_DESTINATION"],
            zmq=True,
            context=self.zmq_context,
            init_logger=True
        )
        connection.close()
        self._init_sge_info()
        self._init_network()
        # job stop/start info
        self.register_timer(self._update, 30, instant=True)

    def _init_sge_info(self):
        self._license_base = global_config["LICENSE_BASE"]
        self._track = global_config["TRACK_LICENSES"]
        self._modify_sge = global_config["MODIFY_SGE_GLOBAL"]
        # store currently configured values, used for logging
        self._sge_lic_set = {}
        self.__lc_dict = {}
        self.log(
            "init sge environment for license tracking in {} ({})".format(
                self._license_base,
                "enabled" if self._track else "disabled",
            )
        )
        # set environment
        os.environ["SGE_ROOT"] = global_config["SGE_ROOT"]
        os.environ["SGE_CELL"] = global_config["SGE_CELL"]
        # get sge environment
        self._sge_dict = sge_license_tools.get_sge_environment()
        self.log(sge_license_tools.get_sge_log_line(self._sge_dict))

    def _init_network(self):
        _v_conn_str = process_tools.get_zmq_ipc_name("vector", s_name="collserver", connect_to_root_instance=True)
        vector_socket = self.zmq_context.socket(zmq.PUSH)
        vector_socket.setsockopt(zmq.LINGER, 0)
        vector_socket.connect(_v_conn_str)
        self.vector_socket = vector_socket

    def _update(self):
        if not self._track:
            return
        _act_site_file = sge_license_tools.text_file(
            os.path.join(sge_license_tools.BASE_DIR, sge_license_tools.ACT_SITE_NAME),
            ignore_missing=True,
        )
        if _act_site_file.lines:
            self._update_lic(_act_site_file.lines[0])
        else:
            self.log("no actual site defined, no license tracking". logging_tools.LOG_LEVEL_ERROR)

    def _update_lic(self, act_site):
        actual_licenses = sge_license_tools.parse_license_lines(
            sge_license_tools.text_file(
                sge_license_tools.get_site_license_file_name(self._license_base, act_site),
                ignore_missing=True,
                strip_empty=False,
                strip_hash=False,
            ).lines,
            act_site
        )
        act_conf = sge_license_tools.text_file(
            sge_license_tools.get_site_config_file_name(self._license_base, act_site),
            content=sge_license_tools.DEFAULT_CONFIG,
            create=True,
        ).dict
        self._parse_actual_license_usage(actual_licenses, act_conf)
        sge_license_tools.set_sge_used(actual_licenses, self._sge_dict)
        for log_line, log_level in sge_license_tools.handle_complex_licenses(actual_licenses):
            if log_level > logging_tools.LOG_LEVEL_WARN:
                self.log(log_line, log_level)
        configured_lics = [_key for _key, _value in actual_licenses.iteritems() if _value.is_used]
        self.write_ext_data(actual_licenses)
        if self._modify_sge:
            self._set_sge_global_limits(actual_licenses, configured_lics)

    def _set_sge_global_limits(self, actual_licenses, configured_lics):
        _new_dict = {}
        for _cl in configured_lics:
            _lic = actual_licenses[_cl]
            _new_dict[_lic.name] = _lic.get_sge_available()
        # log differences
        _diff_keys = [_key for _key in _new_dict.iterkeys() if _new_dict[_key] != self._sge_lic_set.get(_key, None)]
        if _diff_keys:
            self.log(
                "changing {}: {}".format(
                    logging_tools.get_plural("global exec_host complex", len(_diff_keys)),
                    ", ".join(
                        [
                            "{}: {}".format(
                                _key,
                                "{:d} -> {:d}".format(
                                    self._sge_lic_set[_key],
                                    _new_dict[_key],
                                ) if _key in self._sge_lic_set else "{:d}".format(_new_dict[_key])
                            ) for _key in sorted(_diff_keys)
                        ]
                    )
                )
            )
        ac_str = ",".join(["{}={:d}".format(_lic_to_use, _new_dict[_lic_to_use]) for _lic_to_use in configured_lics])
        if ac_str:
            _mod_stat, _mod_out = sge_license_tools.call_command(
                "{} -mattr exechost complex_values {} global".format(self._sge_dict["QCONF_BIN"], ac_str),
                0,
                True,
                self.log
            )

    def _parse_actual_license_usage(self, actual_licenses, act_conf):
        if not os.path.isfile(act_conf["LMUTIL_PATH"]):
            self.log("Error: LMUTIL_PATH '{}' is not a file".format(act_conf["LMUTIL_PATH"]))
        else:
            # build different license-server calls
            all_server_addrs = set(
                [
                    "{:d}@{}".format(act_lic.get_port(), act_lic.get_host()) for act_lic in actual_licenses.values() if act_lic.license_type == "simple"
                ]
            )
            # print "asa:", all_server_addrs
            q_s_time = time.time()
            for server_addr in all_server_addrs:
                if server_addr not in self.__lc_dict:
                    self.log("init new license_check object for server {}".format(server_addr))
                    self.__lc_dict[server_addr] = license_tool.license_check(
                        lmutil_path=os.path.join(
                            act_conf["LMUTIL_PATH"]
                        ),
                        port=int(server_addr.split("@")[0]),
                        server=server_addr.split("@")[1],
                        log_com=self.log
                    )
                srv_result = self.__lc_dict[server_addr].check(license_names=actual_licenses)
            q_e_time = time.time()
            self.log(
                "{} to query, took {}: {}".format(
                    logging_tools.get_plural("license server", len(all_server_addrs)),
                    logging_tools.get_diff_time_str(q_e_time - q_s_time),
                    ", ".join(all_server_addrs)
                )
            )
            sge_license_tools.update_usage(actual_licenses, srv_result)

    def write_ext_data(self, actual_licenses):
        drop_com = server_command.srv_command(command="set_vector")
        add_obj = drop_com.builder("values")
        cur_time = time.time()
        for lic_stuff in actual_licenses.itervalues():
            for cur_mve in lic_stuff.get_mvect_entries(hm_classes.mvect_entry):
                cur_mve.valid_until = cur_time + 120
                add_obj.append(cur_mve.build_xml(drop_com.builder))
        drop_com["vector_loadsensor"] = add_obj
        drop_com["vector_loadsensor"].attrib["type"] = "vector"
        send_str = unicode(drop_com)
        self.log("sending {:d} bytes to vector_socket".format(len(send_str)))
        self.vector_socket.send_unicode(send_str)

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__log_template.log(log_level, what)

    def loop_post(self):
        self.vector_socket.close()
        self.__log_template.close()
