# Copyright (C) 2015 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file belongs to the collectd-init package
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
""" db-syncer for the NESTOR / CORVUS / NOCTUA graphing solution """

from django.db import connection
from django.db.models import Q
from initat.cluster.backbone.models import device, MachineVector, MVStructEntry, MVValue
from initat.collectd.config import global_config
import logging_tools
import server_mixins
import threading_tools
import server_command
from lxml import etree


class GenCache(object):
    class Meta:
        name = "GenCache"

    def __init__(self, log_com, return_none=True, parent=None):
        self.__lut = {}
        self.__return_none = return_none
        self.__log_com = log_com
        # for parenting
        self.parent = parent

    @property
    def log_com(self):
        return self.__log_com

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__log_com("[{}] {}".format(self.Meta.name, what), log_level)

    def resolve(self, key):
        pass

    def __setitem__(self, key, value):
        self.__lut[key] = value

    def __getitem__(self, key):
        if key not in self.__lut:
            try:
                self.resolve(key)
            except KeyError:
                pass
        if key in self.__lut:
            return self.__lut[key]
        else:
            if self.__return_none:
                return None
            else:
                raise KeyError("key {} not resolvable".format(key))


class UUIDCache(GenCache):
    class Meta:
        name = "UUIDCache"

    def resolve(self, in_value):
        try:
            _dev = device.objects.get(Q(uuid=in_value))
        except device.DoesNotExist:
            _err_str = "no device with uuid '{}' found".format(in_value)
            self.log(_err_str, logging_tools.LOG_LEVEL_ERROR)
            raise KeyError(_err_str)
        else:
            self[in_value] = _dev


class MachineVectorCache(GenCache):
    class Meta:
        name = "MVCache"

    def resolve(self, in_value):
        try:
            _mv = MachineVector.objects.get(Q(device=in_value))
        except MachineVector.DoesNotExist:
            _mv = MachineVector(
                device=in_value,
                dir_name=in_value.uuid,
            )
            _mv.save()
            self.log("created MachineVector for {}".format(unicode(in_value)))
        # install caching instance
        _mv.mvse_cache = MVStructEntryCache(self.log_com, parent=_mv)
        self[in_value] = _mv


class MVStructEntryCache(GenCache):
    class Meta:
        name = "MVStructEntryCache"

    def resolve(self, key):
        try:
            _mvs = MVStructEntry.objects.get(
                Q(machine_vector=self.parent) & Q(se_type=key[0]) & Q(key=key[1])
            )
        except MVStructEntry.DoesNotExist:
            _mvs = MVStructEntry(
                machine_vector=self.parent,
                se_type=key[0],
                key=key[1],
            )
            _mvs.save()
        # install caching instance
        _mvs.mvv_cache = MVValueCache(self.log_com, parent=_mvs)
        self[key] = _mvs


class MVValueCache(GenCache):
    class Meta:
        name = "MVValueCache"

    def resolve(self, key):
        try:
            _mvv = MVValue.objects.get(
                Q(mv_struct_entry=self.parent) & Q(key=key[0])
            )
        except MVValue.DoesNotExist:
            _mvv = MVValue(
                mv_struct_entry=self.parent,
                key=key[0],
            )
            _mvv.save()
        self[key] = _mvv


class SyncProcess(threading_tools.process_obj, server_mixins.operational_error_mixin):
    def process_init(self):
        self.__log_template = logging_tools.get_logger(
            global_config["LOG_NAME"],
            global_config["LOG_DESTINATION"],
            zmq=True,
            context=self.zmq_context,
            init_logger=True
        )
        connection.close()
        self.__debug = global_config["DEBUG"]
        self.register_func("mvector", self._mvector)
        self.register_func("perfdata", self._perfdata)
        self._uuid_cache = UUIDCache(self.log)
        self._mvector_cache = MachineVectorCache(self.log)
        # self.register_timer(self.aggregate, 30, instant=False, first_timeout=1)

    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__log_template.log(log_level, what)

    def loop_post(self):
        self.__log_template.close()

    def get_machine_vector(self, uuid):
        _dev = self._uuid_cache[uuid]
        if _dev is not None:
            mv = self._mvector_cache[_dev]
        else:
            mv = None
        return mv

    def _get_mvs_key(self, entry, parent_entry):
        # return a unique key for MVStructEntry base on the input entry
        if entry.tag == "mve":
            _key = (entry.tag, entry.attrib["name"])
        elif entry.tag == "mvl":
            _key = (entry.tag, entry.attrib["name"])
        elif entry.tag == "perfdata_info":
            _key = ("pde", parent_entry.attrib["pd_type"])
        return _key

    def _get_mvv_key(self, entry, parent_entry):
        # return a unique key for MVValue base on the input entry
        if entry.tag == "mve":
            _key = ("",)
        elif parent_entry.tag == "mvl":
            _key = (entry.attrib["key"],)
        elif parent_entry.tag == "perfdata_info":
            _key = (entry.attrib["key"],)
        return _key

    def update_mvse(self, mvse, entry, parent_entry):
        # compare MVStructEntry with XML
        # list to compare
        if entry.tag == "mve":
            _list = [
                ("type_instance", ""),
                ("file_name", entry.get("file_name")),
            ]
        elif entry.tag == "mvl":
            _list = [
                ("type_instance", ""),
                ("file_name", entry.get("file_name")),
            ]
        elif entry.tag == "perfdata_info":
            _list = [
                ("type_instance", parent_entry.get("type_instance", "")),
                ("file_name", parent_entry.get("file_name")),
            ]
        _changed = False
        for _key, _value in _list:
            if getattr(mvse, _key) != _value:
                setattr(mvse, _key, _value)
                _changed = True
        if _changed:
            self.mvse_changed += 1
            mvse.save()

    def update_mvv(self, mvv, entry):
        # compare MVValue with XML
        # list to compare
        # print entry.attrib
        _list = [
            ("base", int(entry.get("base", "1"))),
            ("factor", int(entry.get("factor", "1"))),
            ("unit", entry.get("unit", "")),
            ("v_type", entry.get("v_type")),
            ("info", entry.get("info", "")),
        ]
        _changed = False
        for _key, _value in _list:
            if getattr(mvv, _key) != _value:
                setattr(mvv, _key, _value)
                _changed = True
        if _changed:
            self.mvv_changed += 1
            mvv.save()

    def get_sub_entry(self, entry):
        if entry.tag == "mve":
            return [entry]
        else:
            return [_se for _se in entry]

    def _mvector(self, *args, **kwargs):
        _xml = etree.fromstring(args[0])
        # print "M", etree.tostring(_xml, pretty_print=True)
        self._handle_xml(_xml)

    def _perfdata(self, *args, **kwargs):
        _xml = etree.fromstring(args[0])
        # print "P", etree.tostring(_xml, pretty_print=True)
        self._handle_xml(_xml)

    def _handle_xml(self, _xml):
        self.mvse_changed = 0
        self.mvv_changed = 0
        mv = self.get_machine_vector(_xml.attrib["uuid"])
        if mv:
            for entry in _xml:
                _mvs_key = self._get_mvs_key(entry, _xml)
                mvse = mv.mvse_cache[_mvs_key]
                self.update_mvse(mvse, entry, _xml)
                for sub_entry in self.get_sub_entry(entry):
                    _mvv_key = self._get_mvv_key(sub_entry, entry)
                    mvv = mvse.mvv_cache[_mvv_key]
                    self.update_mvv(mvv, sub_entry)
            if self.mvse_changed:
                self.log(
                    "changed {} for {}".format(
                        logging_tools.get_plural("MVStructEntry", self.mvse_changed),
                        unicode(mv),
                    )
                )
            if self.mvv_changed:
                self.log(
                    "changed {} for {}".format(
                        logging_tools.get_plural("MVValue", self.mvv_changed),
                        unicode(mv),
                    )
                )
