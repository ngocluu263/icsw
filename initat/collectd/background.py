#
# this file is part of collectd-init
#
# Copyright (C) 2014 Andreas Lang-Nevyjel init.at
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

""" background job for collectd-init """

from initat.collectd.collectd_structs import ext_com
from initat.collectd.collectd_types import * # @UnusedWildImport
from initat.collectd.config import IPC_SOCK, RECV_PORT, log_base
from lxml import etree # @UnresolvedImports
from lxml.builder import E # @UnresolvedImports
import logging_tools
import multiprocessing
import server_command
import process_tools
import threading
import signal
import zmq
import time

IPMI_LIMITS = ["ln", "lc", "lw", "uw", "uc", "un"]
# IPMI_LONG_LIMITS = ["{}{}".format({"l" : "lower", "u" : "upper"}[key[0]], key[1:]) for key in IPMI_LIMITS]

def parse_ipmi_type(name, sensor_type):
    key, info, unit, base = ("", "", "", 1)
    parts = name.strip().split()
    lparts = name.strip().lower().split()
    key_str = "_".join([_p.replace(".", ",") for _p in lparts])
    # print "parse", name, sensor_type, parts
    if sensor_type == "rpm":
        if lparts[-1] == "tach":
            lparts.pop(-1)
        key = "fan.{}".format(key_str)
        info = "rotation of fan {}".format(" ".join(parts))
        unit = "RPM"
        base = 1000
    elif sensor_type == "degrees c":
        key = "temp.{}".format(key_str)
        info = "Temperature of {}".format(" ".join(parts))
        unit = "C"
    elif sensor_type == "volts":
        key = "volts.{}".format(key_str)
        info = "Voltage of {}".format(" ".join(parts))
        unit = "V"
    elif sensor_type == "watts":
        key = "watts.{}".format(key_str)
        info = "Power usage of {}".format(" ".join(parts))
        unit = "W"
    return key, info, unit, base

def parse_ipmi(in_lines):
    result = {}
    for line in in_lines:
        parts = [_part.strip() for _part in line.split("|")]
        if len(parts) == 10:
            s_type = parts[2].lower()
            if s_type not in ["discrete"] and parts[1].lower() not in ["na"]:
                key, info, unit, base = parse_ipmi_type(parts[0], s_type)
                if key:
                    # limit dict,
                    limits = {key : l_val for key, l_val in zip(IPMI_LIMITS, [{"na" : ""}.get(value, value) for value in parts[4:10]])}
                    result[key] = (float(parts[1]), info, unit, base, limits)
    return result

class ipmi_builder(object):
    def __init__(self):
        pass
    def build(self, in_lines, **kwargs):
        ipmi_dict = parse_ipmi(in_lines.split("\n"))
        _tree = E.machine_vector(
            simple="0",
            **kwargs
        )
        for key, value in ipmi_dict.iteritems():
            _val = E.mve(
                info=value[1],
                unit=value[2],
                base="{:d}".format(value[3]),
                v_type="f",
                value="{:.6f}".format(value[0]),
                name="ipmi.{}".format(key),
            )
            _tree.append(_val)
        return _tree
    def get_comline(self, _dev_xml):
        return "/usr/bin/ipmitool -H {} -U {} -P {} sensor list".format(
            _dev_xml.get("ip"),
            _dev_xml.get("ipmi_username"),
            _dev_xml.get("ipmi_password"),
        ),


class bg_job(object):
    def __init__(self, id_str, comline, builder, **kwargs):
        self.id_str = id_str
        bg_job.add_job(self)
        self.device_name = kwargs.get("device_name", "")
        self.uuid = kwargs.get("uuid", "")
        self.comline = comline
        self.builder = builder
        self.max_runtime = kwargs.get("max_runtime", 60)
        self.run_every = kwargs.get("run_every", 60 * 2)
        self.counter = 0
        self.last_start = None
        self.running = False
        # to remove from list
        self.to_remove = False
        self.log("new job {}, commandline is '{}'".format(self.id_str, self.comline))
        self.check()
    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        bg_job.bg_proc.log(u"[bgj {:d}] {}".format(self.idx, what), log_level)
    def update_attribute(self, attr_name, attr_value):
        if getattr(self, attr_name) != attr_value:
            self.log("changed attribute {} from '{}' to '{}'".format(
                attr_name,
                getattr(self, attr_name),
                attr_value,
                ))
            setattr(self, attr_name, attr_value)
    def _start_ext_com(self):
        self.counter += 1
        self.last_start = time.time()
        self.running = True
        self.__ec = ext_com(
            self.log,
            self.comline,
        )
        self.result = None
        self.__ec.run()
        return self.__ec
    def check_for_timeout(self):
        diff_time = int(abs(time.time() - self.last_start))
        if  diff_time > self.max_runtime:
            self.log("timeout ({:d} > {:d})".format(diff_time, self.max_runtime), logging_tools.LOG_LEVEL_WARN)
            return True
        else:
            return False
    def terminate(self):
        self.log("terminating job", logging_tools.LOG_LEVEL_ERROR)
        self.__ec.terminate()
    def check(self):
        # return True if process is still running
        if self.running:
            self.result = self.__ec.finished()
            if self.result is None:
                if self.check_for_timeout():
                    self.terminate()
            else:
                self.running = False
                stdout, stderr = self.__ec.communicate()
                self.log(
                    "done (RC={:d}) in {} (stdout: {}, stderr: {})".format(
                        self.result,
                        logging_tools.get_diff_time_str(self.__ec.end_time - self.__ec.start_time),
                        logging_tools.get_plural("byte", len(stdout)),
                        logging_tools.get_plural("byte", len(stderr)),
                    )
                )
                if stdout and self.result == 0:
                    if self.builder is not None:
                        _tree = self.builder.build(stdout, name=self.device_name, uuid=self.uuid, time="{:d}".format(int(self.last_start)))
                        bg_job.bg_proc.send_to_net(etree.tostring(_tree))
                    else:
                        bg_job.log("no builder set", logging_tools.LOG_LEVEL_ERROR)
                if stderr:
                    for line_num, line in enumerate(stderr.strip().split("\n")):
                        self.log("  {:3d} {}".format(line_num + 1 , line), logging_tools.LOG_LEVEL_ERROR)
        else:
            if self.last_start is None or abs(int(time.time() - self.last_start)) >= self.run_every and not self.to_remove:
                self._start_ext_com()
        return self.running
    # static methods
    @staticmethod
    def setup(bg_proc):
        bg_job.run_idx = 0
        bg_job.bg_proc = bg_proc
        bg_job.ref_dict = {}
    @staticmethod
    def g_log(what, log_level=logging_tools.LOG_LEVEL_OK):
        bg_job.bg_proc.log(u"[bgj] {}".format(what), log_level)
    @staticmethod
    def add_job(new_job):
        bg_job.run_idx += 1
        new_job.idx = bg_job.run_idx
        bg_job.ref_dict[new_job.id_str] = new_job
    @staticmethod
    def get_job(job_id):
        return bg_job.ref_dict[job_id]
    @staticmethod
    def sync_jobs_with_id_list(id_list):
        # sync the currently configures jobs with the new id_list
        _cur = set(bg_job.ref_dict.keys())
        _new = set(id_list)
        _to_remove = _cur - _new
        _same = _cur & _new
        _to_create = _new - _cur
        if _to_remove:
            bg_job.g_log("{} to remove: {}".format(logging_tools.get_plural("background job", len(_to_remove)), ", ".join(sorted(list(_to_remove)))))
            for _rem in _to_remove:
                bg_job.ref_dict[_rem].to_remove = True
        return _to_create, _to_remove, _same
    @staticmethod
    def check_jobs():
        _to_delete = []
        for id_str, job in bg_job.ref_dict.iteritems():
            job.check()
            if job.to_remove and not job.running:
                _to_delete.append(id_str)
        if _to_delete:
            bg_job.g_log("removing {}: {}".format(logging_tools.get_plural("background job", len(_to_delete)), ", ".join(sorted(_to_delete))), logging_tools.LOG_LEVEL_WARN)
            for _del in _to_delete:
                del bg_job.ref_dict[_del]

class background(multiprocessing.Process, log_base):
    def __init__(self):
        multiprocessing.Process.__init__(self, target=self._code, name="collectd_background")
    def _init(self):
        threading.currentThread().name = "background"
        # init zmq_context and logging
        self.zmq_context = zmq.Context()
        log_base.__init__(self)
        self.log("background started")
        # ignore signals
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        self._init_sockets()
        self.__ipmi_list = []
        bg_job.setup(self)
        # bg_job("a", "/usr/bin/ipmitool -H 192.168.2.21 -U USERID -P PASSW0RD sensor list", ipmi_builder())
        # bg_job("b", "/usr/bin/ipmitool -H 192.168.2.22 -U USERID -P PASSW0RD sensor list", ipmi_builder())
    def _init_sockets(self):
        self.com = self.zmq_context.socket(zmq.ROUTER)
        self.poller = zmq.Poller()
        self.com.setsockopt(zmq.IDENTITY, "bg")
        self.com.connect(IPC_SOCK)
        self.net_target = self.zmq_context.socket(zmq.PUSH)
        listener_url = "tcp://127.0.0.1:{:d}".format(RECV_PORT)
        self.net_target.connect(listener_url)
        self.poller.register(self.com, zmq.POLLIN)
    def _close(self):
        self._close_sockets()
    def _close_sockets(self):
        self.com.close()
        self.net_target.close()
        self.log("background finished")
        self.close_log()
        self.zmq_context.term()
    def send_to_net(self, _send_str):
        self.net_target.send_unicode(_send_str)
    def _code(self):
        self._init()
        try:
            self._loop()
        except:
            exc_info = process_tools.exception_info()
            for line in exc_info.log_lines:
                self.log(line, logging_tools.LOG_LEVEL_ERROR)
    def _loop(self):
        self.__run = True
        while self.__run:
            try:
                _rcv_list = self.poller.poll(timeout=1000)
            except:
                self.log("exception raised in poll:", logging_tools.LOG_LEVEL_ERROR)
                exc_info = process_tools.exception_info()
                for line in exc_info.log_lines:
                    self.log(line, logging_tools.LOG_LEVEL_ERROR)
            else:
                if len(_rcv_list):
                    src_id = self.com.recv_unicode()
                    data = self.com.recv_pyobj()
                    if data == "exit":
                        self.__run = False
                    elif data.startswith("<"):
                        _in_xml = server_command.srv_command(source=data)
                        self._handle_xml(_in_xml)
                    else:
                        self.log("got unknown data {} from {}".format(str(data), src_id), logging_tools.LOG_LEVEL_WARN)
                else:
                    # timeout, update background jobs
                    bg_job.check_jobs()
        self._close()
    def _handle_xml(self, in_com):
        com_text = in_com["*command"]
        if com_text == "ipmi_hosts":
            # create ids
            _id_dict = {"{}:IPMI".format(_dev.attrib["uuid"]) : _dev for _dev in in_com.xpath(".//ns:device_list/ns:device")}
            _new_list, _remove_list, _same_list = bg_job.sync_jobs_with_id_list(_id_dict.keys())
            for new_id in _new_list:
                _dev = _id_dict[new_id]
                bg_job(
                    new_id,
                    ipmi_builder().get_comline(_dev),
                    ipmi_builder(),
                    device_name=_dev.get("full_name"),
                    uuid=_dev.get("uuid"),
                )
            for same_id in _same_list:
                _dev = _id_dict[same_id]
                _job = bg_job.get_job(same_id)
                for attr_name, attr_value in [
                    ("comline", ipmi_builder().get_comline(_dev)),
                    ("device_name", _dev.get("full_name")),
                    ("uuid", _dev.get("uuid")),
                ]:
                    _job.update_attribute(attr_name, attr_value)
        else:
            self.log("got server_command with unknown command {}".format(com_text), logging_tools.LOG_LEVEL_ERROR)

