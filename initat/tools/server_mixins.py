# -*- coding: utf-8 -*-
#
# Copyright (c) 2001-2007,2009-2016 Andreas Lang-Nevyjel, init.at
#
# this file is part of python-modules-base
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; Version 3 of the License
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
""" usefull server mixins """

from __future__ import unicode_literals, print_function

import re
import sys
import time

import zmq
from enum import IntEnum

from initat.icsw.service.instance import InstanceXML
from initat.tools import logging_tools, process_tools, threading_tools, server_command, \
    configfile, config_store, uuid_tools, logging_functions

MAX_RESEND_COUNTER = 5


# simple EggConsume Cache
class EggConsumeCache(object):
    def __init__(self, cache_time=60):
        self._cache_time = cache_time
        self._dict = {}

    def add_consumers(self, con_list):
        for _con in con_list:
            self._dict[_con] = {}

    def get(self, action, key):
        cur_time = time.time()
        if key in self._dict[action]:
            _ce = self._dict[action][key]
            if abs(_ce[0] - cur_time) < self._cache_time:
                return _ce[1]
        return None

    def set(self, action, key, result):
        self._dict[action][key] = (time.time(), result)


class EggConsumeObject(object):
    def __init__(self, parent):
        # process or any instance with a log facility attached
        self.__parent = parent
        self._cache = EggConsumeCache()

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__parent.log("[EC] {}".format(what), log_level)

    def init(self, global_config):
        from django.db.models import Q
        from initat.cluster.backbone.models import icswEggConsumer
        self.__global_config = global_config
        _my_consumers = icswEggConsumer.objects.filter(Q(config_service_enum__enum_name=self.__global_config["SERVICE_ENUM_NAME"]))
        self.consumers = {_ec.action: _ec for _ec in _my_consumers}
        self._cache.add_consumers(self.consumers.keys())

    def _get_pk_from_object(self, obj_def):
        if type(obj_def) in [int, long]:
            return obj_def
        else:
            return obj_def.idx

    def get_result_struct(self, obj_def, value):
        if type(obj_def) == list:
            return [value for _entry in obj_def]
        else:
            return value

    def consume(self, action, obj_def):
        from django.db.models import Q
        from initat.cluster.backbone.models import icswEggRequest
        if type(obj_def) == list:
            obj_def_list = obj_def
        else:
            obj_def_list = [obj_def]
        if action in self.consumers:
            _con = self.consumers[action]
            _result = []
            # get all pks
            pk_list = [self._get_pk_from_object(cur_obj) for cur_obj in obj_def_list]
            # ToDo, implement code for partially updates
            # print("*", pk_list)
            # egg_reqs = {
            #     entry.object_id: entry for entry in icswEggRequest.objects.filter(Q(egg_consumer=_con) & Q(object_id__in=pk_list))
            # }
            # print(egg_reqs)
            for _pk, cur_obj in zip(pk_list, obj_def_list):
                _allowed = self._cache.get(action, _pk)
                if _allowed is None:
                    try:
                        _cur_req = icswEggRequest.objects.get(
                            Q(egg_consumer=_con) &
                            Q(object_id=_pk),
                        )
                    except icswEggRequest.DoesNotExist:
                        _cur_req = icswEggRequest.objects.create(
                            egg_consumer=_con,
                            object_id=_pk,
                        )
                    except icswEggRequest.MultipleObjectsReturned:
                        _cur_reqs = icswEggRequest.objects.filter(
                            Q(egg_consumer=_con) &
                            Q(object_id=_pk),
                        )
                        # print len(_cur_reqs)
                        _cur_req = _cur_reqs[0]
                    _allowed = _con.consume(_cur_req)
                    if not _allowed:
                        self.log(
                            "action {} on {} not allowed".format(
                                action,
                                unicode(cur_obj),
                            ),
                            logging_tools.LOG_LEVEL_ERROR
                        )
                    self._cache.set(action, _pk, _allowed)
                _result.append(_allowed)
            if type(obj_def) != list:
                _result = _result[0]
        else:
            self.log(
                "unknown consume action '{}' for {} (known actions: {})".format(
                    action,
                    unicode(obj_def),
                    ", ".join(sorted(self.consumers.keys())) or "none",
                ),
                logging_tools.LOG_LEVEL_CRITICAL
            )
            _result = self.get_result_struct(obj_def, False)
        return _result


class ConfigCheckObject(object):
    def __init__(self, proc):
        self.__process = proc
        # self.log = self.__process.log

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__process.log("[CC] {}".format(what), log_level)

    def init(self, srv_type_enum, global_config, add_config_store=True, init_logging=True, native_logging=False, init_msi_block=True, log_name_postfix=None):
        if srv_type_enum is None:
            # srv_type_enum is None, use value stored in global config
            from initat.cluster.backbone.server_enums import icswServiceEnum
            # force reload of global-config
            global_config.close()
            srv_type_enum = getattr(icswServiceEnum, global_config["SERVICE_ENUM_NAME"])
        self.srv_type_enum = srv_type_enum
        self.global_config = global_config
        self.__native_logging = native_logging
        self.__init_msi_block = init_msi_block
        self._inst_xml = InstanceXML(self.log)
        if self.__init_msi_block:
            # init MSI block
            self.__msi_block = None
        if add_config_store:
            self.__cs = config_store.ConfigStore("client", self.log)
        else:
            self.__cs = None
        global_config.add_config_entries(
            [
                ("SERVICE_ENUM_NAME", configfile.str_c_var(self.srv_type_enum.name))
            ]
        )
        if init_logging:
            if "LOG_DESTINATION" not in global_config:
                global_config.add_config_entries(
                    [
                        ("LOG_DESTINATION", configfile.str_c_var("uds:/var/lib/logging-server/py_log_zmq")),
                    ]
                )

            if "LOG_NAME" not in global_config:
                _log_name = self._inst_xml[self.srv_type_enum.value.instance_name].attrib["name"]
                if log_name_postfix:
                    _log_name = "{}-{}".format(
                        _log_name,
                        log_name_postfix,
                    )
                global_config.add_config_entries(
                    [
                        (
                            "LOG_NAME",
                            configfile.str_c_var(
                                _log_name,
                                source="instance"
                            )
                        )
                    ]
                )
            if self.__native_logging:
                # build logger name
                logger_name = "{}.{}".format(
                    process_tools.get_machine_name(),
                    global_config["LOG_NAME"]
                )
                # get logger
                self.__process.log_template = logging_functions.get_logger(
                    self.__cs,
                    logger_name.replace(".", "/"),
                    logger_name,
                )
            else:
                self.__process.log_template = logging_tools.get_logger(
                    global_config["LOG_NAME"],
                    global_config["LOG_DESTINATION"],
                    context=self.__process.zmq_context,
                )

    def create_hfp(self):
        from initat.tools import hfp_tools
        _cur_hfp = hfp_tools.create_db_entry(
            self.__sql_info.effective_device,
            hfp_tools.get_local_hfp()
        )

    @property
    def CS(self):
        return self.__cs

    @property
    def Instance(self):
        return self._inst_xml

    def check_config(self):
        # late import (for clients without django)
        if self.srv_type_enum.value.server_service:
            from initat.tools import config_tools
            from django.db.models import Q
            from initat.cluster.backbone.models import LogSource
        if self.srv_type_enum.value.instance_name is None:
            raise KeyError("No instance_name set for srv_type_enum '{}'".format(self.srv_type_enum.name))
        self._instance = self._inst_xml[self.srv_type_enum.value.instance_name]
        # conf_names = self._inst_xml.get_config_names(self._instance)
        self.log(
            "check for service_type {} (==enum {})".format(
                self.srv_type_enum.value.name,
                self.srv_type_enum.name,
            )
        )
        _opts = [
            (
                "PID_NAME",
                configfile.str_c_var(self._inst_xml.get_pid_file_name(self._instance), source="instance", database=False)
            ),
        ]
        for _name, _value in self._inst_xml.get_port_dict(self._instance).iteritems():
            _opts.append(
                (
                    "{}_PORT".format(_name.upper()),
                    configfile.int_c_var(_value, source="instance", database=False)
                ),
            )
        if self.srv_type_enum.value.server_service:
            self.__sql_info = config_tools.server_check(service_type_enum=self.srv_type_enum)
            if self.__sql_info is None or not self.__sql_info.effective_device:
                # this can normally not happen due to start / stop via meta-server
                self.log("Not a valid {}".format(self.srv_type_enum.name), logging_tools.LOG_LEVEL_ERROR)
                sys.exit(5)
            else:
                # check eggConsumers
                # set values
                _opts.extend(
                    [
                        (
                            "SERVICE_ENUM_NAME",
                            configfile.str_c_var(self.srv_type_enum.name),
                        ),
                        (
                            "SERVER_SHORT_NAME",
                            configfile.str_c_var(process_tools.get_machine_name(True)),
                        ),
                        (
                            "SERVER_IDX",
                            configfile.int_c_var(self.__sql_info.device.pk, database=False, source="instance")
                        ),
                        (
                            "CONFIG_IDX",
                            configfile.int_c_var(self.__sql_info.config.pk, database=False, source="instance")
                        ),
                        (
                            "EFFECTIVE_DEVICE_IDX",
                            configfile.int_c_var(self.__sql_info.effective_device.pk, database=False, source="instance")
                        ),
                        (
                            "LOG_SOURCE_IDX",
                            configfile.int_c_var(
                                LogSource.new(self.srv_type_enum.name, device=self.__sql_info.effective_device).pk,
                                source="instance",
                            )
                        ),
                        (
                            "MEMCACHE_PORT",
                            configfile.int_c_var(self._inst_xml.get_port_dict("memcached", command=True), source="instance")
                        ),
                    ]
                )
        self.global_config.add_config_entries(_opts)

        if self.__init_msi_block:
            self.__pid_name = self.global_config["PID_NAME"]
            process_tools.save_pid(self.__pid_name)
            self.log("init MSI Block")
            self.__msi_block = process_tools.MSIBlock(self.srv_type_enum.value.msi_block_name)
            self.__msi_block.add_actual_pid(process_name="main")
            self.__msi_block.save()

    def process_added(self, src_process, src_pid):
        if self.__init_msi_block:
            process_tools.append_pids(self.__pid_name, src_pid)
            self.__msi_block.add_actual_pid(src_pid, process_name=src_process)
            self.__msi_block.save()

    def process_removed(self, src_pid):
        if self.__init_msi_block:
            process_tools.remove_pids(self.__pid_name, src_pid)
            self.__msi_block.remove_actual_pid(src_pid)
            self.__msi_block.save()

    # property functions to access device and config
    @property
    def server(self):
        return self.__sql_info.device

    @property
    def config(self):
        return self.__sql_info.config

    @property
    def msi_block(self):
        if self.__init_msi_block:
            return self.__msi_block
        else:
            raise AttributeError("No MSI Block defined")

    def close(self):
        if self.__init_msi_block and self.__msi_block:
            process_tools.delete_pid(self.__pid_name)
            self.__msi_block.remove()
            self.__msi_block = None
        if not self.__native_logging:
            self.__process.log_template.close()
        if isinstance(self.__process, threading_tools.process_pool):
            # remove global config if we were called from the process poll
            self.global_config.delete()

    def log_config(self):
        _log = self.global_config.get_log(clear=True)
        if len(_log):
            self.log(
                "Config log ({}):".format(
                    logging_tools.get_plural("line", len(_log)),
                )
            )
            for line, log_level in _log:
                self.log(" - clf: [{:d}] {}".format(log_level, line))
        else:
            self.log("no Config log")
        conf_info = self.global_config.get_config_info()
        self.log(
            "Found {}:".format(
                logging_tools.get_plural("valid config-line", len(conf_info))
            )
        )
        for conf in conf_info:
            self.log("Config : {}".format(conf))

    def read_config_from_db(self, default_list=[]):
        from initat.tools import cluster_location
        cluster_location.read_config_from_db(
            self.global_config,
            self.__sql_info,
            default_list,
        )

    def re_insert_config(self):
        if self.__sql_info:
            from initat.tools import cluster_location
            self.log(
                "re-inserting config for srv_type {} (config_name is {})".format(
                    self.srv_type_enum.name,
                    self.__sql_info.config_name,
                )
            )
            cluster_location.write_config_to_db(
                self.global_config,
                self.__sql_info,
            )
        else:
            self.log(
                "refuse to re-insert config because sql_info is None (srv_type={})".format(
                    self.srv_type,
                ),
                logging_tools.LOG_LEVEL_ERROR
            )


class ConfigCheckMixin(threading_tools.ICSWAutoInit):
    def __init__(self):
        self.__log_cache, self.__log_template = ([], None)
        self.CC = ConfigCheckObject(self)

    def log(self, what, lev=logging_tools.LOG_LEVEL_OK):
        if self.__log_template:
            self.__log_template.log(lev, what)
        else:
            self.__log_cache.append((lev, what))

    @property
    def log_template(self):
        return self.__log_template

    @log_template.setter
    def log_template(self, lt):
        self.__log_template = lt
        self._flush_log_cache()

    def _flush_log_cache(self):
        while self.__log_cache:
            self.__log_template.log(*self.__log_cache.pop(0))


class EggConsumeMixin(threading_tools.ICSWAutoInit):
    def __init__(self):
        self.EC = EggConsumeObject(self)


class ServerStatusMixin(object):
    # populates the srv_command with the current server stats
    def server_status(self, srv_com, msi_block, global_config=None, spc=None):
        # spc is an optional snmp_process_container
        _status = msi_block.check_block()
        _proc_info_dict = self.get_info_dict()
        # add configfile manager
        if spc is not None:
            spc.salt_proc_info_dict(_proc_info_dict)
        _pid_info = msi_block.pid_check_string(_proc_info_dict)
        if global_config is not None:
            try:
                _vers = global_config["VERSION"]
            except:
                pass
            else:
                _pid_info = "{}, Version: {}".format(
                    _pid_info,
                    _vers,
                )

        srv_com.set_result(
            _pid_info,
            server_command.SRV_REPLY_STATE_OK if _status else server_command.SRV_REPLY_STATE_ERROR,
        )
        return srv_com


# exception mixin
class OperationalErrorMixin(threading_tools.ExceptionHandlingBase):
    def __init__(self):
        # init by ExceptionHandlingMixin
        self.register_exception("OperationalError", self._op_error)

    def _op_error(self, info):
        from initat.cluster.backbone import db_tools
        try:
            from django.db import connection
        except:
            self.log("cannot import connection from django.db", logging_tools.LOG_LEVEL_ERROR)
        else:
            self.log("operational error, closing db connection", logging_tools.LOG_LEVEL_ERROR)
            try:
                db_tools.close_connection()
            except:
                pass


class NetworkBindMixin(object):
    def network_bind(self, **kwargs):
        _need_all_binds = kwargs.get("need_all_binds", False)
        pollin = kwargs.get("pollin", None)
        ext_call = kwargs.get("ext_call", False)
        immediate = kwargs.get("immediate", True)
        if "server_type" in kwargs:
            _inst = InstanceXML(log_com=self.log)
            _srv_type = kwargs["server_type"]
            bind_port = _inst.get_port_dict(_srv_type, ptype="command")
        elif "service_type_enum" in kwargs:
            _inst = InstanceXML(log_com=self.log)
            _srv_type = kwargs["service_type_enum"]
            bind_port = _inst.get_port_dict(_srv_type, ptype="command")
        elif "bind_port" in kwargs:
            bind_port = kwargs["bind_port"]
        else:
            raise KeyError("neither bind_port, service_type_enum nor server_type defined in kwargs")
        main_socket_name = kwargs.get("main_socket_name", "main_socket")
        virtual_sockets_name = kwargs.get("virtual_sockets_name", "virtual_sockets")
        bind_to_localhost = kwargs.get("bind_to_localhost", False)
        _sock_type = kwargs.get("socket_type", "ROUTER")
        if "client_type" in kwargs:
            uuid = uuid_tools.get_uuid().get_urn()
            if not uuid.startswith("urn"):
                uuid = "urn:uuid:{}".format(uuid)
            self.bind_id = "{}:{}:".format(
                uuid,
                InstanceXML(quiet=True).get_uuid_postfix(kwargs["client_type"]),
            )
            dev_r = None
        else:
            from initat.tools import cluster_location
            from initat.cluster.backbone.routing import get_server_uuid
            self.bind_id = get_server_uuid(_srv_type)
            if kwargs.get("simple_server_bind", False):
                dev_r = None
            else:
                # device recognition
                dev_r = cluster_location.DeviceRecognition()
        # virtual sockets
        if hasattr(self, virtual_sockets_name):
            _virtual_sockets = getattr(self, virtual_sockets_name)
        else:
            _virtual_sockets = []
        # main socket
        _main_socket = None
        # create bind list
        if dev_r and dev_r.device_dict:
            _bind_ips = set(
                list(dev_r.local_ips) + sum(
                    [
                        _list for _dev, _list in dev_r.ip_r_lut.iteritems()
                    ],
                    []
                )
            )
            # complex bind
            master_bind_list = [
                (
                    True,
                    [
                        "tcp://{}:{:d}".format(_local_ip, bind_port) for _local_ip in dev_r.local_ips
                    ],
                    self.bind_id,
                    None,
                )
            ]
            _virt_list = []
            for _dev, _ip_list in dev_r.ip_r_lut.iteritems():
                if _dev.pk != dev_r.device.pk:
                    _virt_list.append(
                        (
                            False,
                            [
                                "tcp://{}:{:d}".format(_virtual_ip, bind_port) for _virtual_ip in _ip_list
                            ],
                            # ignore local device
                            get_server_uuid(_srv_type, _dev.uuid),
                            _dev,
                        )
                    )
                else:
                    self.log(
                        "ignoring virtual IP list ({}) (same device)".format(
                            ", ".join(sorted(_ip_list)),
                        )
                    )
            master_bind_list.extend(_virt_list)
            # we have to bind to localhost but localhost is not present in bind_list, add master_bind
            if bind_to_localhost and not any([_ip.startswith("127.") for _ip in _bind_ips]):
                self.log(
                    "bind_to_localhost is set but not IP in range 127.0.0.0/8 found in list, adding virtual_bind",
                    logging_tools.LOG_LEVEL_WARN
                )
                master_bind_list.append(
                    (
                        False,
                        [
                            "tcp://127.0.0.1:{:d}".format(bind_port)
                        ],
                        self.bind_id,
                        None,
                    )
                )
        else:
            # simple bind
            master_bind_list = [
                (
                    True,
                    [
                        "tcp://*:{:d}".format(bind_port)
                    ],
                    self.bind_id,
                    None,
                )
            ]
        _errors = []
        # pprint.pprint(master_bind_list)
        bound_list = set()
        for master_bind, bind_list, bind_id, bind_dev in master_bind_list:
            client = process_tools.get_socket(
                self.zmq_context,
                _sock_type,
                identity=bind_id,
                immediate=immediate
            )
            for _bind_str in bind_list:
                if _bind_str in bound_list:
                    self.log(
                        "bind_str '{}' (for {}) already used, skipping ...".format(
                            _bind_str,
                            " device '{}'".format(bind_dev) if bind_dev is not None else " master device",
                        ),
                        logging_tools.LOG_LEVEL_ERROR
                    )
                else:
                    bound_list.add(_bind_str)
                    try:
                        client.bind(_bind_str)
                    except zmq.ZMQError:
                        self.log(
                            "error binding to {}: {}".format(
                                _bind_str,
                                process_tools.get_except_info(),
                            ),
                            logging_tools.LOG_LEVEL_CRITICAL
                        )
                        _errors.append(_bind_str)
                    else:
                        self.log("bound {} to {} with id {}".format(_sock_type, _bind_str, bind_id))
                        if pollin:
                            self.register_poller(client, zmq.POLLIN, pollin, ext_call=ext_call, bind_id=bind_id)
            if master_bind:
                _main_socket = client
            else:
                _virtual_sockets.append(client)
        setattr(self, main_socket_name, _main_socket)
        setattr(self, virtual_sockets_name, _virtual_sockets)
        if _errors and _need_all_binds:
            raise ValueError("{} went wrong: {}".format(logging_tools.get_plural("bind", len(_errors)), ", ".join(_errors)))

    def network_unbind(self, **kwargs):
        main_socket_name = kwargs.get("main_socket_name", "main_socket")
        virtual_sockets_name = kwargs.get("virtual_sockets_name", "virtual_sockets")
        _main_sock = getattr(self, main_socket_name, None)
        if _main_sock is not None:
            self.log("closing socket '{}'".format(main_socket_name))
            _main_sock.close()
            setattr(self, main_socket_name, None)
        _virt_socks = getattr(self, virtual_sockets_name, [])
        if _virt_socks:
            self.log("closing {}".format(logging_tools.get_plural("virtual socket", len(_virt_socks))))
            [_virt.close() for _virt in _virt_socks]
            setattr(self, virtual_sockets_name, [])


class RemoteAsyncHelper(object):
    def __init__(self, inst):
        self.__inst = inst
        self.log("init RemoteAsyncHelper")
        self.__async_id = 0
        self.__lut = {}

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__inst.log("[RAH] {}".format(what), log_level)

    def register(self, rcs, src_id, srv_com, zmq_sock, msg_type):
        self.__async_id += 1
        srv_com["async_helper_id"] = self.__async_id
        self.__lut[self.__async_id] = (rcs.func_name, src_id, zmq_sock, msg_type, time.time())

    def result(self, srv_com):
        if "async_helper_id" not in srv_com:
            self.log(
                "no asnyc_helper_id found in srv_com, discarding message",
                logging_tools.LOG_LEVEL_ERROR
            )
            return None, None, None, None
        else:
            async_id = int(srv_com["*async_helper_id"])
            if async_id not in self.__lut:
                self.log(
                    "asnyc_id {:d} not defined in lut, discarding message".format(
                        async_id
                    ),
                    logging_tools.LOG_LEVEL_ERROR
                )
                return None, None, None, None
            else:
                func_name, src_id, zmq_sock, msg_type, s_time = self.__lut[async_id]
                e_time = time.time()
                del self.__lut[async_id]
                del srv_com["async_helper_id"]
                _log_str = "finished async call {} ({:d}) in {}".format(
                    func_name,
                    async_id,
                    logging_tools.get_diff_time_str(e_time - s_time),
                )
                if zmq_sock is None:
                    self.log(_log_str)
                return zmq_sock, src_id, srv_com, msg_type, _log_str


def RemoteCallProcess(klass):
    # print "*" * 20, klass
    # print dir(klass)
    # build list of lookup
    _lut_dict = {}
    _id_filter_dict = {}
    for _name in dir(klass):
        _obj = getattr(klass, _name)
        if isinstance(_obj, RemoteCallSignature):
            _obj.link(_lut_dict, _id_filter_dict)
    # print _lut_dict
    klass.remote_call_lut = _lut_dict
    klass.remote_call_id_filter_dict = _id_filter_dict
    # klass.remote_async_helper = RemoteAsyncHelper()
    return klass


class RemoteCallMixin(object):
    def remote_call(self, zmq_sock, **kwargs):
        in_data = []
        while True:
            in_data.append(zmq_sock.recv())
            if not zmq_sock.getsockopt(zmq.RCVMORE):  # @UndefinedVariable
                break
        com_type = "router" if len(in_data) == 2 else "pull"
        if com_type in self.remote_call_lut:
            if com_type == "router":
                src_id, data = in_data
            else:
                src_id, data = (None, in_data[0])
            msg_lut = self.remote_call_lut[com_type]
            if RemoteCallMessageType.xml in msg_lut:
                # try to interpret as server_command
                try:
                    srv_com = server_command.srv_command(source=data)
                except:
                    srv_com = None
                    msg_type = RemoteCallMessageType.flat
                else:
                    msg_type = RemoteCallMessageType.xml
            else:
                msg_type = RemoteCallMessageType.flat
            # set com_name to None
            com_name = None
            if self.remote_call_id_filter_dict and src_id is not None:
                _match = [_value for _key, _value in self.remote_call_id_filter_dict.iteritems() if _key.match(src_id)]
                if _match:
                    com_name = _match[0].func_name
            if com_name is None:
                # com name still none, parse data
                if msg_type == RemoteCallMessageType.flat:
                    com_name = data.strip().split()[0]
                else:
                    com_name = srv_com["*command"]

            com_name = com_name.replace("-", "_")  # can't have '-' in python method names
            # if msg_type in msg_lut:
            if com_name in msg_lut.get(msg_type, {}):
                rcs = msg_lut[msg_type][com_name]
                if rcs.sync:
                    if msg_type == RemoteCallMessageType.flat:
                        result = rcs.handle(self, src_id, data)
                    else:
                        result = rcs.handle(self, src_id, srv_com, **kwargs)
                    if com_type == "router" and result is not None:
                        # send reply
                        self._send_remote_call_reply(zmq_sock, src_id, result, msg_type)
                else:
                    if rcs.send_async_return:
                        if not hasattr(self, "remote_async_helper"):
                            self.install_remote_call_handlers()
                        self.remote_async_helper.register(rcs, src_id, srv_com, zmq_sock, msg_type)
                    if msg_type == RemoteCallMessageType.flat:
                        rcs.handle(self, src_id, data)
                    else:
                        rcs.handle(self, src_id, srv_com, **kwargs)
            else:
                self.log(
                    "no matching signature found for msg_type {} (command='{}', src_id='{}')".format(
                        msg_type,
                        com_name,
                        src_id or "N/A",
                    ),
                    logging_tools.LOG_LEVEL_ERROR,
                )
                if com_type == "router":
                    # check sendcounter
                    if msg_type == RemoteCallMessageType.xml and srv_com.sendcounter > MAX_RESEND_COUNTER:
                        self.log(
                            "sendcounter is too high ({:d} > {:d}, com '{}'), no reply sent, communication loop ?".format(
                                srv_com.sendcounter,
                                MAX_RESEND_COUNTER,
                                com_name,
                            ),
                            logging_tools.LOG_LEVEL_CRITICAL
                        )
                    else:
                        if msg_type == RemoteCallMessageType.flat:
                            _reply = "unknown command '{}'".format(com_name)
                        else:
                            srv_com.set_result(
                                "unknown command '{}'".format(com_name),
                                server_command.SRV_REPLY_STATE_ERROR
                            )
                            _reply = srv_com
                        self._send_remote_call_reply(zmq_sock, src_id, _reply, msg_type)
        else:
            msg_type = RemoteCallMessageType.unknown
            self.log(
                "unable to handle message type '{}' (# of data frames: {:d})".format(
                    com_type,
                    len(in_data),
                ),
                logging_tools.LOG_LEVEL_ERROR
            )
            if com_type == "router":
                _reply = server_command.srv_command()
                _reply.set_result(
                    "no remote_calls with com_type == 'router' defined",
                    server_command.SRV_REPLY_STATE_ERROR,
                )
                self._send_remote_call_reply(zmq_sock, in_data[0], _reply, msg_type)

    def install_remote_call_handlers(self):
        if not hasattr(self, "remote_async_helper"):
            self.remote_async_helper = RemoteAsyncHelper(self)
            # callback to send result
            self.register_func("remote_call_async_result", self.remote_call_async_result)
            # callback to forget async helper entry
            self.register_func("remote_call_async_done", self.remote_call_async_done)

    def _send_remote_call_reply(self, zmq_sock, src_id, reply, msg_type, add_log=None):
        add_log = " ({})".format(add_log) if add_log is not None else ""
        if msg_type == RemoteCallMessageType.xml:
            # set source
            reply.update_source()
        # send return
        _send_str = unicode(reply)
        try:
            zmq_sock.send_unicode(src_id, zmq.SNDMORE)
            zmq_sock.send_unicode(_send_str)
        except:
            self.log(
                "error sending reply to {} ({}): {}{}".format(
                    src_id,
                    logging_tools.get_size_str(len(_send_str)),
                    process_tools.get_except_info(),
                    add_log
                ),
                logging_tools.LOG_LEVEL_ERROR
            )
        else:
            self.log(
                "sent {} to {}{}".format(
                    logging_tools.get_size_str(len(_send_str)),
                    src_id,
                    add_log,
                )
            )

    def remote_call_async_result(self, *args, **kwargs):
        _src_proc, _src_pid, srv_com = args
        srv_com = server_command.srv_command(source=srv_com)
        _sock, _src_id, _reply, _msg_type, _log_str = self.remote_async_helper.result(srv_com)
        if _sock is not None:
            self._send_remote_call_reply(_sock, _src_id, _reply, _msg_type, _log_str)

    def remote_call_async_done(self, *args, **kwargs):
        _src_proc, _src_pid, srv_com = args
        srv_com = server_command.srv_command(source=srv_com)
        self.remote_async_helper.result(srv_com)


class RemoteCallMessageType(IntEnum):
    xml = 1
    flat = 2
    unknown = 99


class RemoteCallSignature(object):
    def __init__(self, *args, **kwargs):
        self.com_type = kwargs.get("com_type", "router")
        self.target_process = kwargs.get("target_process", None)
        self.target_process_func = kwargs.get("target_process_func", None)
        # only for async calls
        self.send_async_return = kwargs.get("send_async_return", True)
        self.msg_type = kwargs.get("msg_type", RemoteCallMessageType.xml)
        self.id_filter = kwargs.get("id_filter", None)
        self.debug = kwargs.get("debug", None)

        # sync should default to False when using a target process, else be True
        sync_default = not self.target_process

        self.sync = kwargs.get("sync", sync_default)

        if not self.sync and (self.com_type, self.msg_type, self.send_async_return) not in [
            ("router", RemoteCallMessageType.xml, True),
            ("router", RemoteCallMessageType.xml, False),
            ("router", RemoteCallMessageType.flat, False),
        ]:
            raise ValueError("async calls only possible for XML router calls or calls without return message")
        # if not self.sync and not self.target_process:
        #     raise ValueError("need target process for async calls")
        if "sync" in kwargs and kwargs["sync"] and self.target_process:  # only check this if sync is set explicitly
            raise ValueError("call must by asynchronous when forwarding to target process")

    @property
    def func_name(self):
        return self.func.__name__

    def link(self, lut, id_filter_dict):
        lut.setdefault(
            self.com_type,
            {}
        ).setdefault(
            self.msg_type,
            {}
        )[self.func_name] = self
        if self.id_filter:
            id_filter_dict[re.compile(self.id_filter)] = self

    def handle(self, instance, src_id, srv_com, **kwargs):
        # print 'RemoteCall handle', self, instance, src_id, srv_com, 'target', self.target_process, self.func.__name__
        _result = self.func(instance, srv_com, src_id=src_id, **kwargs)
        if self.sync:
            return _result
        else:
            if self.target_process:
                effective_target_func_name = self.target_process_func or self.func_name
                # print 'effective target name', effective_target_func_name
                instance.send_to_process(self.target_process, effective_target_func_name, unicode(_result), src_id=src_id)
            else:
                # local async call
                pass


class RemoteServerAddressBase(object):
    def __init__(self, mixin, srv_type_enum):
        self.mixin = mixin
        self.srv_type_enum = srv_type_enum
        self._connected = False
        self.__latest_router_error = None
        self._address = None

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.mixin.log("[RSAb {}] {}".format(self.srv_type_enum.name, what), log_level)

    @property
    def valid(self):
        return True if self._address else False

    @property
    def connected(self):
        return self._connected

    @property
    def connection_string(self):
        return "tcp://{}:{:d}".format(self._address, self._port)

    def connect(self):
        if not self._connected:
            _conn_str = self.connection_string
            try:
                self.mixin.strs_com_socket.connect(self.connection_string)
            except:
                self.log(
                    "error connecting to {}: {}".format(
                        _conn_str,
                        process_tools.get_except_info()
                    ),
                    logging_tools.LOG_LEVEL_ERROR
                )
            else:
                self.log(
                    "connected to {}".format(_conn_str),
                )
                self._connected = True
                self._last_error = None
                self._first_send = True

    def send(self, send_obj):
        cur_time = time.time()
        if self._last_error and abs(self._last_error - cur_time) < 10:
            # last send error only 10 seconds ago, fail silently
            pass
        else:
            _loop, _idx, _error = (True, 0, True)
            while _loop and _idx < 5:
                _idx += 1
                _loop = False
                # time.sleep(1)
                try:
                    self.mixin.strs_com_socket.send_unicode(self._uuid, zmq.DONTWAIT | zmq.SNDMORE)
                    self.mixin.strs_com_socket.send_unicode(unicode(send_obj), zmq.DONTWAIT)
                except zmq.error.ZMQError as e:
                    self.log(
                        "cannot send to '{}': {}".format(
                            self.connection_string,
                            process_tools.get_except_info()
                        ),
                        logging_tools.LOG_LEVEL_CRITICAL
                    )
                    if e.errno == 113:
                        _loop = True
                        time.sleep(0.1)
                    self._last_error = cur_time
                else:
                    self._last_error = None
                    _error = False
                    break

            if _idx > 1 or self._first_send:
                _rf = []
                if _idx > 1:
                    _rf.append("after {:d} tries".format(_idx))
                if self._first_send:
                    _rf.append("for the first time")
                self.log("sent {}".format(", ".join(_rf)), logging_tools.LOG_LEVEL_WARN)
            self._first_send = False


class RemoteServerAddress(RemoteServerAddressBase):
    def __init__(self, mixin, srv_type_enum):
        RemoteServerAddressBase.__init__(self, mixin, srv_type_enum)
        self._uuid, self._port = (None, None)
        self.log("init for {}".format(self.srv_type_enum.name))
        self.__latest_router_error = None

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.mixin.log("[RSA {}] {}".format(self.srv_type_enum.name, what), log_level)

    def check_for_address(self, router):
        if not self.valid:
            router.update()
            if self.srv_type_enum.name in router:
                _addresses = router[self.srv_type_enum.name]
                if len(_addresses):
                    from initat.cluster.backbone.models import device
                    from django.db.models import Q
                    _addr = _addresses[0]
                    self._address = _addr[1]
                    _dev = device.objects.get(Q(pk=_addr[2]))
                    self._port = self.mixin.CC.Instance.get_port_dict(self.srv_type_enum, command=True)
                    self._postfix = self.mixin.CC.Instance.get_uuid_postfix(self.srv_type_enum)
                    self._uuid = "{}:{}:".format(_dev.com_uuid, self._postfix)
                    self.log(
                        "set address to {} (device {}, port {:d}, COM-UUID {})".format(
                            self._address,
                            unicode(_dev),
                            self._port,
                            self._uuid,
                        )
                    )
                else:
                    self.log("got no valid addresses", logging_tools.LOG_LEVEL_ERROR)
            else:
                cur_time = time.time()
                # reduce log flooding
                if self.__latest_router_error and abs(self.__latest_router_error - cur_time) < 5:
                    pass
                else:
                    self.log("not found in router".format(self.srv_type_enum.name), logging_tools.LOG_LEVEL_ERROR)
                    self.__latest_router_error = cur_time


class RemoteServerAddressIP(RemoteServerAddressBase):
    def __init__(self, mixin, srv_type_enum):
        RemoteServerAddressBase.__init__(self, mixin, srv_type_enum)
        self._uuid, self._port = (None, None)
        self.log("init")
        self.__latest_router_error = None

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.mixin.log("[RSAIP {}] {}".format(self.srv_type_enum.name, what), log_level)

    def check_for_address(self, instance, addr, dev_uuid):
        if not self.valid:
            self._uuid = instance.get_uuid_postfix(self.srv_type_enum)
            if dev_uuid:
                self._uuid = "{}:{}:".format(
                    dev_uuid,
                    self._uuid,
                )
            self._address = addr
            self._port = instance.get_port_dict(self.srv_type_enum, command=True)
            self.log(
                "set address to {} (port {:d}, COM-UUID {})".format(
                    self._address,
                    self._port,
                    self._uuid,
                )
            )


class SendToRemoteServerMixin(threading_tools.ICSWAutoInit):
    def __init__(self):
        # requires ConfigCheckMixin, clear dict
        self.__target_dict = None
        self.STRS_SOCKET_NAME = "main_socket"

    # helper property, only used until collectd is rewritten to use RemoteCall Mixin
    @property
    def strs_com_socket(self):
        return getattr(self, self.STRS_SOCKET_NAME)

    def send_to_remote_server(self, srv_type_enum, send_obj):
        from initat.cluster.backbone import routing
        if self.__target_dict is None:
            from initat.cluster.backbone import db_tools
            db_tools.close_connection()
            self.__target_dict = {}
            self.__strs_router = routing.SrvTypeRouting(log_com=self.log)
        if srv_type_enum not in self.__target_dict:
            self.__target_dict[srv_type_enum] = RemoteServerAddress(self, srv_type_enum)
        _rsa = self.__target_dict[srv_type_enum]
        _rsa.check_for_address(self.__strs_router)
        return self.send_to_remote_server_int(_rsa, send_obj)

    def send_to_remote_server_ip(self, srv_addr, dev_uuid, srv_type_enum, send_obj):
        if self.__target_dict is None:
            from initat.icsw.service.instance import InstanceXML
            self.__target_dict = {}
            self.__strs_instance = InstanceXML(quiet=True)
        if srv_type_enum not in self.__target_dict:
            self.__target_dict[srv_type_enum] = RemoteServerAddressIP(self, srv_type_enum)
        _rsa = self.__target_dict[srv_type_enum]
        _rsa.check_for_address(self.__strs_instance, srv_addr, dev_uuid)
        return self.send_to_remote_server_int(_rsa, send_obj)

    def send_to_remote_server_int(self, rsa, send_obj):
        if rsa.valid:
            rsa.connect()
            if rsa.connected:
                rsa.send(send_obj)
            else:
                self.log("unable to send, not connected", logging_tools.LOG_LEVEL_WARN)
        else:
            self.log("unable to send, not valid", logging_tools.LOG_LEVEL_WARN)


class RemoteCall(object):
    def __init__(self, *args, **kwargs):
        self.rc_signature = RemoteCallSignature(*args, **kwargs)

    def __call__(self, inst_method):
        self.rc_signature.func = inst_method
        return self.rc_signature


class ICSWBasePool(threading_tools.process_pool, NetworkBindMixin, ServerStatusMixin, ConfigCheckMixin, OperationalErrorMixin):
    def __init__(self):
        pass

    # to use the log-function of the ConfigCheckMixin
    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        ConfigCheckMixin.log(self, what, log_level)


# baseprocess for all child process on server side
class ICSWBaseProcess(threading_tools.process_obj, ConfigCheckMixin, OperationalErrorMixin):
    def __init__(self, name=None):
        # this is not very elegant, on child process we get called twice
        # because of the class iterater in ICSWAutoInit so we call the __init__
        # of process_obj only if name is set
        if name is not None:
            # manually init process_obj
            threading_tools.process_obj.__init__(self, name)

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        ConfigCheckMixin.log(self, what, log_level)


# basepool for clients (without operationalerrormixin)
class ICSWBasePoolClient(threading_tools.process_pool, NetworkBindMixin, ServerStatusMixin, ConfigCheckMixin):
    def __init__(self):
        pass

    # to use the log-function of the ConfigCheckMixin
    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        ConfigCheckMixin.log(self, what, log_level)
