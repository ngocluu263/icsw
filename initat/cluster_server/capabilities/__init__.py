# Copyright (C) 2001-2008,2012-2014,2016 Andreas Lang-Nevyjel
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License Version 3 as
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
""" cluster-server, capability process """

from __future__ import unicode_literals, print_function

import importlib
import inspect
import os
import time

import zmq
from django.db.models import Q
from lxml import etree

from initat.cluster.backbone import db_tools, factories
from initat.cluster.backbone.models import config_catalog, icswEggConsumer
from initat.cluster.backbone.server_enums import icswServiceEnum
from initat.cluster_server.capabilities import base
from initat.cluster_server.config import global_config
from initat.host_monitoring import hm_classes
from initat.icsw.service.instance import InstanceXML
from initat.tools import config_tools, logging_tools, process_tools, server_command, threading_tools


class CapabilityProcess(threading_tools.process_obj):
    def process_init(self):
        global_config.close()
        self.__log_template = logging_tools.get_logger(
            global_config["LOG_NAME"],
            global_config["LOG_DESTINATION"],
            zmq=True,
            context=self.zmq_context
        )
        db_tools.close_connection()
        self._instance = InstanceXML(log_com=self.log)
        self._init_network()
        self._init_capabilities()
        self.__last_user_scan = None
        self.__scan_running = False
        self.register_timer(self._update, 2 if global_config["DEBUG"] else 30, instant=True)

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__log_template.log(log_level, what)

    def loop_post(self):
        self.collectd_socket.close()
        self.vector_socket.close()
        self.__log_template.close()

    def _init_network(self):
        # connection to local collserver socket
        conn_str = process_tools.get_zmq_ipc_name("vector", s_name="collserver", connect_to_root_instance=True)
        vector_socket = self.zmq_context.socket(zmq.PUSH)  # @UndefinedVariable
        vector_socket.setsockopt(zmq.LINGER, 0)  # @UndefinedVariable
        vector_socket.connect(conn_str)
        self.vector_socket = vector_socket
        self.log("connected vector_socket to {}".format(conn_str))
        # connection to local collectd server
        _cc_str = "tcp://localhost:{:d}".format(
            # get receive port for collectd-server drop
            self._instance.get_port_dict(icswServiceEnum.collectd_server, ptype="receive")
        )
        collectd_socket = self.zmq_context.socket(zmq.PUSH)
        collectd_socket.setsockopt(zmq.LINGER, 0)
        collectd_socket.connect(_cc_str)
        self.log("connected collectd_socket to {}".format(_cc_str))
        self.collectd_socket = collectd_socket

    def _init_capabilities(self):
        self.__cap_list = []
        if global_config["BACKUP_DATABASE"]:
            self.log("doing database backup, ignoring capabilities", logging_tools.LOG_LEVEL_WARN)
        else:
            # read caps
            _dir = os.path.dirname(__file__)
            self.log("init server capabilities from directory {}".format(_dir))
            SRV_CAPS = []
            for entry in os.listdir(_dir):
                if entry.endswith(".py") and entry not in ["__init__.py"]:
                    _imp_name = "initat.cluster_server.capabilities.{}".format(entry.split(".")[0])
                    _mod = importlib.import_module(_imp_name)
                    for _key in dir(_mod):
                        _value = getattr(_mod, _key)
                        if inspect.isclass(_value) and issubclass(_value, base.BackgroundBase) and _value != base.BackgroundBase:
                            SRV_CAPS.append(_value)
            self.log("checking {}".format(logging_tools.get_plural("capability", len(SRV_CAPS))))
            self.__server_cap_dict = {}
            self.__cap_list = []
            try:
                sys_cc = config_catalog.objects.get(Q(system_catalog=True))
            except config_catalog.DoesNotExist:
                sys_cc = factories.ConfigCatalog(name="local", system_catalog=True)
            for _srv_cap in SRV_CAPS:
                cap_name = _srv_cap.Meta.name
                try:
                    cap_descr = _srv_cap.Meta.description
                except:
                    self.log("capability {} has no description set, ignoring...".format(cap_name), logging_tools.LOG_LEVEL_ERROR)
                else:
                    _new_c = factories.Config(
                        name=cap_name,
                        description=cap_descr,
                        config_catalog=sys_cc,
                        server_config=True,
                        # system_config=True,
                    )
                    _sql_info = config_tools.server_check(server_type=cap_name)
                    if _sql_info.effective_device:
                        self.__cap_list.append(cap_name)
                        self.__server_cap_dict[cap_name] = _srv_cap(self, _sql_info)
                        self.log(
                            "capability {} is enabled on {}".format(
                                cap_name,
                                unicode(_sql_info.effective_device),
                            )
                        )
                    else:
                        self.log("capability {} is disabled".format(cap_name))

    def add_ova_statistics(self, cur_time, drop_com):
        _bldr = drop_com.builder
        # print "*", cur_time, drop_com, _bldr
        my_vector = _bldr("values")
        for _csr in icswEggConsumer.objects.all():
            my_vector.append(
                hm_classes.mvect_entry(
                    "icsw.ova.{}.{}".format(_csr.content_type.model, _csr.action),
                    info="Ova consumed by {} on {}".format(_csr.action, _csr.content_type.model),
                    default=0,
                    value=_csr.consumed,
                    factor=1,
                    base=1,
                    valid_until=cur_time + 3600,
                ).build_xml(_bldr)
            )
        drop_com["vector_ova"] = my_vector
        drop_com["vector_ova"].attrib["type"] = "vector"

    def _update(self):
        cur_time = time.time()
        drop_com = server_command.srv_command(command="set_vector")

        mach_vectors = []
        for cap_name in self.__cap_list:
            self.__server_cap_dict[cap_name](cur_time, drop_com, mach_vectors)
        self.add_ova_statistics(cur_time, drop_com)
        self.vector_socket.send_unicode(unicode(drop_com))
        # print drop_com.pretty_print()
        for _mv in mach_vectors:
            try:
                self.collectd_socket.send_unicode(etree.tostring(_mv))
            except:
                self.log(
                    "unable to send machvector to collectd: {}".format(
                        process_tools.get_except_info(),
                    ),
                    logging_tools.LOG_LEVEL_ERROR,
                )
