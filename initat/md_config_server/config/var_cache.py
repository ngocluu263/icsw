# Copyright (C) 2008-2016 Andreas Lang-Nevyjel, init.at
#
# this file is part of md-config-server
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
""" config part of md-config-server """

from django.db.models import Q
from initat.cluster.backbone.models import device_variable


__all__ = [
    "monVarCache",
]


# a similiar structure is used in the server process of rrd-grapher
class monVarCache(dict):
    def __init__(self, cdg, prefill=False):
        super(monVarCache, self).__init__(self)
        self.__cdg = cdg
        self.__prefill = prefill
        if prefill:
            self._prefill()

    def get_global_def_dict(self):
        return {
            "SNMP_VERSION": 2,
            "SNMP_READ_COMMUNITY": "public",
            "SNMP_WRITE_COMMUNITY": "private",
        }

    def _prefill(self):
        for _var in device_variable.objects.all().select_related("device"):
            if _var.device.is_meta_device:
                if _var.device.device_group_id == self.__cdg.pk:
                    _key = "GLOBAL"
                    if _key not in self:
                        self[_key] = {g_key: (g_value, True) for g_key, g_value in self.get_global_def_dict().iteritems()}
                else:
                    _key = "g__{:d}".format(_var.device.device_group_id)
            else:
                _key = "d__{:d}".format(_var.device_id)
            self.setdefault(_key, {})[_var.name] = (_var.value, _var.inherit)

    def add_variable(self, new_var):
        v_key = "d__{:d}".format(new_var.device_id)
        self.setdefault(v_key, {})[new_var.name] = (new_var.value, new_var.inherit)

    def set_variable(self, dev, var_name, var_value):
        # update db
        dev_variable = device_variable.objects.get(Q(name=var_name) & Q(device=dev))
        dev_variable.value = var_value
        dev_variable.save()
        # update dict
        self["d__{:d}".format(dev.pk)][var_name] = (var_value, dev_variable.inherit)

    def get_vars(self, cur_dev):
        global_key, dg_key, dev_key = (
            "GLOBAL",
            "g__{:d}".format(cur_dev.device_group_id),
            "d__{:d}".format(cur_dev.pk)
        )
        if global_key not in self:
            def_dict = self.get_global_def_dict()
            # read global configs
            self[global_key] = {
                cur_var.name: (cur_var.get_value(), cur_var.inherit) for cur_var in device_variable.objects.filter(Q(device=self.__cdg))
            }
            # update with def_dict
            for key, value in def_dict.iteritems():
                if key not in self[global_key]:
                    self[global_key][key] = (value, True)
        if not self.__prefill:
            # do not query the devices
            if dg_key not in self:
                # read device_group configs
                self[dg_key] = {
                    cur_var.name: (cur_var.get_value(), cur_var.inherit) for cur_var in device_variable.objects.filter(
                        Q(device=cur_dev.device_group.device)
                    )
                }
            if dev_key not in self:
                # read device configs
                self[dev_key] = {
                    cur_var.name: (cur_var.get_value(), cur_var.inherit) for cur_var in device_variable.objects.filter(
                        Q(device=cur_dev)
                    )
                }
        ret_dict, info_dict = ({}, {})
        # for s_key in ret_dict.iterkeys():
        for key, key_n, ignore_inh in [
            (dev_key, "d", True),
            (dg_key, "g", False),
            (global_key, "c", False),
        ]:
            info_dict[key_n] = 0
            for s_key, (s_value, inherit) in self.get(key, {}).iteritems():
                if (inherit or ignore_inh) and (s_key not in ret_dict):
                    ret_dict[s_key] = s_value
                    info_dict[key_n] += 1
        # print cur_dev, ret_dict, info_dict
        return ret_dict, info_dict
