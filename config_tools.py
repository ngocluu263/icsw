#!/usr/bin/python-init -OtW error
#
# Copyright (C) 2007,2008,2012,2013 Andreas Lang-Nevyjel, init.at
#
# this file is part of python-modules-base
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
"""
module to operate with config and ip relationsships in the database. This
module gets included from configfile
"""

import sys
import re
import os
import pprint
import configfile
import array
import process_tools
import time
import logging_tools
from initat.cluster.backbone.models import config, device, net_ip, device_config, \
     device_group, config_str, config_blob, config_int, config_bool, route_generation, netdevice, \
     peer_information
from django.db.models import Q
import networkx

class router_object(object):
    def __init__(self, log_com):
        self.__log_com = log_com
        self.__cur_gen = 0
        self.nx = None
        self._update()
    def add_nodes(self):
        self.nx.add_nodes_from(self.nd_dict.keys())
    def add_edges(self):
        for node_pair, penalty in self.simple_peer_dict.iteritems():
            src_node, dst_node = node_pair
            self.nx.add_edge(src_node, dst_node, weight=penalty)
    def _update(self):
        latest_gen = route_generation.objects.all().order_by("-generation")
        if latest_gen:
            latest_gen = latest_gen[0].generation
        else:
            latest_gen = route_generation(generation=1)
            latest_gen.save()
            latest_gen = latest_gen.generation
        if latest_gen != self.__cur_gen:
            s_time = time.time()
            self.all_nds = netdevice.objects.exclude(Q(device__device_type__identifier="MD")).filter(Q(device__enabled=True) & Q(device__device_group__enabled=True)).values_list("idx", "device", "routing", "penalty")
            self.dev_dict = {}
            for cur_nd in self.all_nds:
                if cur_nd[1] not in self.dev_dict:
                    self.dev_dict[cur_nd[1]] = []
                self.dev_dict[cur_nd[1]].append(cur_nd)
            self.nd_lut = dict([(value[0], value[1]) for value in netdevice.objects.all().values_list("pk", "device") if value[1] in self.dev_dict])
            self.nd_dict = dict([(cur_nd[0], cur_nd) for cur_nd in self.all_nds])
            self.log("init router helper object, %s / %s" % (
                logging_tools.get_plural("netdevice", len(self.all_nds)),
                logging_tools.get_plural("peer information", peer_information.objects.count())))
            # peer dict
            self.peer_dict, self.simple_peer_dict = ({}, {})
            all_peers = peer_information.objects.all().values_list("s_netdevice_id", "d_netdevice_id", "penalty")
            for s_nd_id, d_nd_id, penalty in all_peers:
                if s_nd_id in self.nd_lut and d_nd_id in self.nd_lut:
                    self.peer_dict[(s_nd_id, d_nd_id)] = penalty + self.nd_dict[s_nd_id][2] + self.nd_dict[d_nd_id][2]
                    self.peer_dict[(d_nd_id, s_nd_id)] = penalty + self.nd_dict[s_nd_id][2] + self.nd_dict[d_nd_id][2]
                    self.simple_peer_dict[(s_nd_id, d_nd_id)] = penalty
            # add simple peers for device-internal networks
            for nd_list in self.dev_dict.itervalues():
                route_nds = [cur_nd for cur_nd in nd_list if cur_nd[2]]
                if len(route_nds) > 1:
                    for s_idx in xrange(len(route_nds)):
                        for d_idx in xrange(s_idx + 1, len(route_nds)):
                            s_pk, d_pk = (route_nds[s_idx][0], route_nds[d_idx][0])
                            int_penalty = 1
                            self.peer_dict[(s_pk, d_pk)] = int_penalty
                            self.peer_dict[(d_pk, s_pk)] = int_penalty
                            self.simple_peer_dict[(s_pk, d_pk)] = int_penalty
            if self.nx:
                del self.nx
            self.nx = networkx.Graph()
            self.add_nodes()
            self.add_edges()
            if self.__cur_gen:
                self.log("update generation from %d to %d in %s" % (
                    self.__cur_gen,
                    latest_gen,
                    logging_tools.get_diff_time_str(time.time() - s_time),
                ))
            else:
                self.log("init with generation %d in %s" % (
                    latest_gen,
                    logging_tools.get_diff_time_str(time.time() - s_time),
                ))
            self.__cur_gen = latest_gen
    def check_for_update(self):
        self._update()
    def get_penalty(self, in_path):
        return sum([self.peer_dict[(in_path[idx], in_path[idx + 1])] for idx in xrange(len(in_path) - 1)])
    def add_penalty(self, in_path):
        return (self.get_penalty(in_path), in_path)
    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__log_com("[router] %s" % (what), log_level)
    def get_ndl_ndl_pathes(self, s_list, d_list, **kwargs):
        """
        returns all pathes between s_list and d_list (:: net_device)
        """
        all_paths = []
        for s_ndev in s_list:
            for d_ndev in d_list:
                try:
                    all_paths.append(networkx.all_shortest_paths(self.nx, s_ndev, d_ndev, weight="weight"))
                except networkx.exception.NetworkXNoPath:
                    pass
        if kwargs.get("add_penalty", False):
            if kwargs.get("only_endpoints", False):
                all_paths = [(self.get_penalty(cur_path), cur_path[0], cur_path[-1]) for cur_path in all_paths]
            else:
                all_paths = [(self.get_penalty(cur_path), cur_path) for cur_path in all_paths]
        elif kwargs.get("only_endpoints", False):
            all_paths = [(cur_path[0], cur_path[-1]) for cur_path in all_paths]
        return all_paths
    def map_path_to_device(self, in_path):
        return [self.nd_lut[value] for value in in_path]

class topology_object(object):
    def __init__(self, log_com):
        self.__log_com = log_com
        self.nx = None
        self._update()
    def add_nodes(self):
        self.nx.add_nodes_from(self.dev_dict.keys())
    def add_edges(self):
        for node_pair, network_idx_list in self.simple_peer_dict.iteritems():
            src_node, dst_node = node_pair
            self.nx.add_edge(src_node, dst_node, networkidx=sum(network_idx_list))
    def _update(self):
        s_time = time.time()
        self.all_devs = device.objects.exclude(Q(device_type__identifier="MD")).filter(Q(enabled=True) & Q(device_group__enabled=True)).values_list("idx", "name")
        self.dev_dict = dict([(cur_dev[0], cur_dev) for cur_dev in self.all_devs])
        nd_dict = dict([(value[0], value[1]) for value in netdevice.objects.all().values_list("pk", "device")])
        ip_dict = dict([(value[0], (value[1], value[2])) for value in net_ip.objects.all().values_list("pk", "netdevice", "network")])
        # reorder ip_dict
        nd_lut = {}
        for net_ip_pk, (nd_pk, nw_pk) in ip_dict.iteritems():
            nd_lut.setdefault(nd_pk, []).append(nw_pk)
        self.log("init topology helper object, %s / %s" % (
            logging_tools.get_plural("device", len(self.all_devs)),
            logging_tools.get_plural("peer information", peer_information.objects.count())))
        # peer dict
        self.peer_dict, self.simple_peer_dict = ({}, {})
        all_peers = peer_information.objects.all().values_list("s_netdevice_id", "d_netdevice_id")
        for s_nd_id, d_nd_id in all_peers:
            if nd_dict[s_nd_id] in self.dev_dict and nd_dict[d_nd_id] in self.dev_dict:
                src_device_id = nd_dict[s_nd_id]
                dst_device_id = nd_dict[d_nd_id]
                src_device_id, dst_device_id = (min(src_device_id, dst_device_id),
                                                max(src_device_id, dst_device_id))
                self.simple_peer_dict.setdefault((src_device_id, dst_device_id), set()).update(set(nd_lut.get(s_nd_id, [])) | set(nd_lut.get(d_nd_id, [])))
        if self.nx:
            del self.nx
        self.nx = networkx.Graph()
        self.add_nodes()
        self.add_edges()
    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__log_com("[topology] %s" % (what), log_level)

def get_config_var_list(config_obj, config_dev):
    r_dict = {}
    # dict of local vars without specified host
    l_var_wo_host = {}
    for short in ["str",
                  "int",
                  "blob",
                  "bool"]:
        src_sql_obj = globals()["config_%s" % (short)].objects
        for db_rec in src_sql_obj.filter(
            (Q(device=0) | Q(device=None) | Q(device=config_dev.pk)) &
            (Q(config=config_obj)) &
            (Q(config__device_config__device=config_dev))):
            if db_rec.name.count(":"):
                var_global = False
                local_host_name, var_name = db_rec.name.split(":", 1)
            else:
                var_global = True
                local_host_name, var_name = (config_dev.name, db_rec.name)
            if type(db_rec.value) == type(array.array("b")):
                new_val = configfile.str_c_var(db_rec.value.tostring(), source="%s_table" % (short))
            elif short == "int":
                new_val = configfile.int_c_var(int(db_rec.value), source="%s_table" % (short))
            elif short == "bool":
                new_val = configfile.bool_c_var(bool(db_rec.value), source="%s_table" % (short))
            else:
                new_val = configfile.str_c_var(db_rec.value, source="%s_table" % (short))
            new_val.is_global = var_global
            r_dict[var_name.upper()] = new_val
    return r_dict
        
class server_check(object):
    """ is called server_check, but can also be used for nodes """
    def __init__(self, **kwargs):
        # server_type: name of server, no wildcards supported (!)
        self.__server_type = kwargs["server_type"]
        if self.__server_type.count("%"):
            raise SyntaxError, "no wildcards supported in server_check, use device_with_config"
        self.short_host_name = kwargs.get("short_host_name", process_tools.get_machine_name())
        self.__fetch_network_info = kwargs.get("fetch_network_info", True)
        self.__network_info_fetched = False
        #self.set_hopcount_cache()
        self._check(**kwargs)
    #def set_hopcount_cache(self, in_cache=[]):
        #self.__hc_cache = in_cache
    def _check(self, **kwargs):
        # device from database or None
        self.device = None
        # device for which the config is set
        self.effective_device = None
        # config or None
        self.config = None
        # server origin, one of unknown,
        # ...... real (hostname matches and config set local)
        # ...... meta (hostname matches and config set to meta_device)
        # ...... virtual (hostname mismatch, ip match)
        # ...... virtual meta (hostname mismatch, ip match, config set to meta_device)
        self.server_origin = "unknown"
        # info string
        self.server_info_str = "not set"
        # list of ip-addresses for server
        self.ip_list = []
        # list of netdevice-idxs for server
        self.netdevice_idx_list = []
        # lookup table netdevice_idx -> list of ips
        self.netdevice_ip_lut = {}
        # lookup table ip -> netdevice_idx
        self.ip_netdevice_lut = {}
        # lookup table ip -> network identifier
        self.ip_identifier_lut = {}
        # lookup table netdev_pk -> netdev
        self.nd_lut = {}
        # lookup table network_identifier -> ip_list
        self.identifier_ip_lut = {}
        self.real_server_name = self.__server_type
        # set dummy config_name
        self.config_name = self.__server_type
        # config variable dict
        self.__config_vars = {}
        self._db_check(**kwargs)
    def _db_check(self, **kwargs):
        if "device" in kwargs:
            # got device, no need to query
            self.config = kwargs["config"]
            self.device = kwargs["device"]
            self.effective_device = kwargs.get("effective_device", kwargs["device"])
        else:
            try:
                self.device = device.objects.prefetch_related(
                    # intermediate sets not needed
                    #"netdevice_set",
                    #"netdevice_set__net_ip_set",
                    #"netdevice_set__net_ip_set__network",
                    "netdevice_set__net_ip_set__network__network_type").get(Q(name=self.short_host_name))
            except device.DoesNotExist:
                self.device = None
            else:
                try:
                    self.config = config.objects.get(
                        Q(name=self.__server_type) & Q(device_config__device=self.device))
                except config.DoesNotExist:
                    try:
                        self.config = config.objects.get(
                            Q(name=self.__server_type) & Q(device_config__device__device_type__identifier="MD") & 
                            Q(device_config__device__device_group=self.device.device_group_id))
                    except config.DoesNotExist:
                        self.config = None
                    else:
                        self.effective_device = device.objects.get(Q(device_group=self.device.device_group_id) & Q(device_type__identifier="MD"))
                else:
                    self.effective_device = self.device
        #self.num_servers = len(all_servers)
        if self.config:
            # name matches -> 
            self._set_srv_info("real" if self.device.pk == self.effective_device.pk else "meta",
                               "hostname '%s'" % (self.short_host_name))
            if self.__fetch_network_info:
                # fetch ip_info only if needed
                self._fetch_network_info()
        elif self.device:
            # we need at least a device to check
            # fetch ip_info
            self._fetch_network_info()
            self._db_check_ip()
    def fetch_config_vars(self):
        self.__config_vars.update(get_config_var_list(self.config, self.effective_device))
    # FIXME, deprecated due to circular import problem
##    def fetch_config_vars(self, dc):
##        if self.config_idx:
##            # dict of local vars without specified host
##            l_var_wo_host = {}
##            # code from configfile.py
##            for short, what_value in [("str" , configfile_old.str_c_var),
##                                      ("int" , configfile_old.int_c_var),
##                                      ("blob", configfile_old.str_c_var)]:
##                sql_str = "SELECT cv.* FROM config_%s cv WHERE cv.new_config=%d ORDER BY cv.name" % (short, self.config_idx)
##                dc.execute(sql_str)
##                for db_rec in [rec for rec in dc.fetchall() if rec["name"]]:
##                    if db_rec["name"].count(":"):
##                        var_global = False
##                        local_host_name, var_name = db_rec["name"].split(":", 1)
##                    else:
##                        var_global = True
##                        local_host_name, var_name = (self.short_host_name, db_rec["name"])
##                    if type(db_rec["value"]) == type(array.array("b")):
##                        new_val = what_value(db_rec["value"].tostring(), source="%s_table" % (short))
##                    elif short == "int":
##                        new_val = what_value(int(db_rec["value"]), source="%s_table" % (short))
##                    else:
##                        new_val = what_value(db_rec["value"], source="%s_table" % (short))
##                    new_val.set_is_global(var_global)
##                    if local_host_name == self.short_host_name:
##                        if var_name.upper() in self and self.is_fixed(var_name.upper()):
##                            # present value is fixed, keep value, only copy global / local status
##                            self.copy_flag(var_name.upper(), new_val)
##                        else:
##                            self[var_name.upper()] = new_val
##                    elif local_host_name == "":
##                        l_var_wo_host[var_name.upper()] = new_val
##            # check for vars to insert
##            for wo_var_name, wo_var in l_var_wo_host.iteritems():
##                if not wo_var_name in self or self.get_source(wo_var_name) == "default":
##                    self[wo_var_name] = wo_var
    def has_key(self, var_name):
        return var_name in self.__config_vars
    def __contains__(self, var_name):
        return var_name in self.__config_vars
    def keys(self):
        return self.__config_vars.keys()
    def is_fixed(self, var_name):
        return self.__config_vars[var_name].fixed
    def copy_flag(self, var_name, new_var):
        self.__config_vars[var_name].set_is_global(new_var.is_global())
    def get_source(self, var_name):
        return self.__config_vars[var_name].source
    def __setitem__(self, var_name, var_value):
        self.__config_vars[var_name] = var_value
    def __getitem__(self, var_name):
        return self.__config_vars[var_name].value
    def _set_srv_info(self, sdsc, s_info_str):
        self.server_origin = sdsc
        self.server_info_str = "%s '%s'-server via %s" % (self.server_origin,
                                                          self.__server_type,
                                                          s_info_str)
    # utility funcitions
    @property
    def simple_ip_list(self):
        return [cur_ip.ip for cur_ip in self.ip_list]
    def _fetch_network_info(self, **kwargs):
        # commented force_flag, FIXME
        if not self.__network_info_fetched or kwargs.get("force", False):
            for net_dev in self.device.netdevice_set.all():
                self.netdevice_idx_list.append(net_dev.pk)
                self.netdevice_ip_lut[net_dev.pk] = []
                self.nd_lut[net_dev.pk] = net_dev
                for net_ip in net_dev.net_ip_set.all():
                    self.ip_list.append(net_ip)
                    self.netdevice_ip_lut[net_dev.pk].append(net_ip)
                    self.ip_netdevice_lut[net_ip.ip] = net_dev
                    self.ip_identifier_lut[net_ip.ip] = net_ip.network.network_type.identifier
                    self.identifier_ip_lut.setdefault(net_ip.network.network_type.identifier, []).append(net_ip)
            self.__network_info_fetched = True
    def _db_check_ip(self):
        # get local ip-addresses
        my_ips = set(net_ip.objects.exclude(
            Q(network__network_type__identifier='l')
            ).filter(
                Q(netdevice__device=self.device)).select_related("netdevice", "network", "network__network_type").values_list("ip", flat=True))
        # check for virtual-device
        # get all real devices with the requested config, no meta-device handling possible
        dev_list = device.objects.filter(Q(device_config__config__name=self.__server_type))
        if not dev_list:
            # no device(s) found with IP and requested config
            return
        # find matching IP-adresses
        for cur_dev in dev_list:
            dev_ips = set(net_ip.objects.exclude(
                Q(network__network_type__identifier='l')
                ).filter(
                    Q(netdevice__device=cur_dev)).values_list("ip", flat=True))
            match_ips = my_ips & dev_ips
            if match_ips:
                self.device = cur_dev
                # always working ?
                self.config = config.objects.get(Q(name=self.__server_type))
                self.effective_device = cur_dev
                self.short_host_name = cur_dev.name
                self._set_srv_info("virtual", "IP address '%s'" % (list(match_ips)[0]))
                break
    def get_route_to_other_device(self, router_obj, other, **kwargs):
        filter_ip = kwargs.get("filter_ip", None)
        # at first fetch the network info if necessary
        self._fetch_network_info()
        other._fetch_network_info()
        # format of return list: value, network_id, (self.netdevice_idx, [list of self.ips]), (other.netdevice_idx, [list of other.ips])
        ret_list = []
        if self.netdevice_idx_list and other.netdevice_idx_list:
            # skip if any of both netdevice_idx_lists are empty
            # get peer_information
            all_pathes = router_obj.get_ndl_ndl_pathes(self.netdevice_idx_list, other.netdevice_idx_list, add_penalty=True, only_endpoints=True)
            #if self.__hc_cache:
                #all_hcs = self.__hc_cache
            #else:
                #latest_gen = route_generation.objects.filter(Q(valid=True)).order_by("-pk")
                #if len(latest_gen):
                    #latest_gen = latest_gen[0]
                    #all_hcs = hopcount.objects.filter(
                        #Q(route_generation=latest_gen) & 
                        #Q(s_netdevice__in=self.netdevice_idx_list) &
                        #Q(d_netdevice__in=other.netdevice_idx_list)).distinct().order_by("value").values_list("s_netdevice", "d_netdevice", "value")
                #else:
                    #all_hcs = []
            for penalty, s_nd_pk, d_nd_pk in all_pathes:
                # dicts identifier -> ips
                source_ip_lut, dest_ip_lut = ({}, {})
                for s_ip in self.netdevice_ip_lut[s_nd_pk]:
                    source_ip_lut.setdefault(self.ip_identifier_lut[unicode(s_ip)], []).append(unicode(s_ip))
                for d_ip in other.netdevice_ip_lut[d_nd_pk]:
                    dest_ip_lut.setdefault(other.ip_identifier_lut[unicode(d_ip)], []).append(unicode(d_ip))
                common_identifiers = set(source_ip_lut.keys()) & set(dest_ip_lut.keys())
                if common_identifiers:
                    for act_id in common_identifiers:
                        add_actual = True
                        if filter_ip:
                            if filter_ip not in source_ip_lut[act_id] and filter_ip not in dest_ip_lut[act_id]:
                                add_actual = False
                        if add_actual:
                            ret_list.append((penalty,
                                             act_id,
                                             (s_nd_pk, source_ip_lut[act_id]),
                                             (d_nd_pk, dest_ip_lut[act_id])))
                else:
                    if kwargs.get("allow_route_to_other_networks", False):
                        if "p" in dest_ip_lut and "o" in source_ip_lut:
                            add_actual = True
                            if filter_ip:
                                if filter_ip not in source_ip_lut["o"] and filter_ip not in dest_ip_lut["p"]:
                                    add_actual = False
                            if add_actual:
                                ret_list.append((penalty,
                                                 "o",
                                                 (s_nd_pk, source_ip_lut["o"]),
                                                 (d_nd_pk, dest_ip_lut["p"])))
        return ret_list
    def report(self):
        #print self.effective_device
        if self.effective_device:
            return "short_host_name is %s (idx %d), server_origin is %s, effective_device_idx is %d, config_idx is %d, info_str is \"%s\"" % (
                self.short_host_name,
                self.device.pk,
                self.server_origin,
                self.effective_device.pk,
                self.config.pk,
                self.server_info_str)
        else:
            return "short_host_name is %s (idx %d), server_origin is %s, info_str is \"%s\"" % (
                self.short_host_name,
                self.device.pk,
                self.server_origin,
                self.server_info_str)
        
from django.db import connection

class device_with_config(dict):
    def __init__(self, config_name, **kwargs):
        dict.__init__(self)
        self.__config_name = config_name
        if self.__config_name.count("%"):
            self.__match_str = "name__icontains"
            self.__m_config_name = self.__config_name.replace("%", "")
        else:
            self.__match_str = "name"
            self.__m_config_name = self.__config_name
        self._check(**kwargs)
    def _check(self, **kwargs):
        # locates devices with the given config_name
        # right now we are fetching a little bit too much ...
        #print "*** %s=%s" % (self.__match_str, self.__m_config_name)
        exp_group = set()
        direct_list = device_config.objects.filter(
            Q(**{"config__%s" % (self.__match_str) : self.__m_config_name})).select_related(
                "device",
                "config",
                "device__device_group",
                "device__device_type").values_list(
                    "config__name",
                    "config",
                    "device__name",
                    "device",
                    "device__device_group",
                    "device__device_type__identifier", "device__device_type__identifier")
        exp_group = set([cur_entry[4] for cur_entry in direct_list if cur_entry[5] == "MD"])
        conf_pks = set([cur_entry[1] for cur_entry in direct_list])
        # expand device groups
        group_dict, md_set, group_md_lut = ({}, set(), {})
        if exp_group:
            for group_dev in device.objects.filter(Q(device_group__in=exp_group)).values_list("name", "pk", "device_group", "device_type__identifier"):
                if group_dev[3] != "MD":
                    group_dict.setdefault(group_dev[2], []).append(group_dev)
                else:
                    # lut: device_group -> md_device
                    group_md_lut[group_dev[2]] = group_dev[1]
                    md_set.add(group_dev[1])
        all_list = []
        for cur_entry in direct_list:
            if cur_entry[5] == "MD":
                all_list.extend([(cur_entry[0], cur_entry[1], g_list[0], g_list[1], g_list[2], g_list[3], "MD") for g_list in group_dict[cur_entry[4]]])
            else:
                all_list.append(cur_entry)
        # list format:
        # config_name, config_pk, device_name, device_pk, device_group, device_identifier, orig_device_identifier (may be MD)
        # dict: device_name, device_pk, device_group, identifier -> config_list (config, config_pk, identifier, source_identifier)
        dev_conf_dict = {}
        for cur_entry in all_list:
            dev_conf_dict.setdefault(tuple(cur_entry[2:6]), []).append((cur_entry[0], cur_entry[1], cur_entry[5], cur_entry[6]))
        dev_dict = dict([(cur_dev.pk, cur_dev) for cur_dev in device.objects.filter(Q(pk__in=[key[1] for key in dev_conf_dict.iterkeys()] + list(md_set))).prefetch_related(
            # intermediates not needed
            #"netdevice_set",
            #"netdevice_set__net_ip_set",
            #"netdevice_set__net_ip_set__network",
            "netdevice_set__net_ip_set__network__network_type")])
        conf_dict = dict([(cur_conf.pk, cur_conf) for cur_conf in config.objects.filter(Q(pk__in=conf_pks))])
        for dev_key, conf_list in dev_conf_dict.iteritems():
            dev_name, dev_pk, devg_pk, dev_type = dev_key
            for conf_name, conf_pk, m_type, src_type in conf_list:
                #print "%s (%s/%s), %s" % (conf_name, m_type, src_type, dev_key[0])
                cur_struct = server_check(
                    short_host_name=dev_name,
                    server_type=conf_name,
                    config=conf_dict[conf_pk],
                    device=dev_dict[dev_pk],
                    effective_device=dev_dict[dev_pk] if m_type == src_type else dev_dict[group_md_lut[devg_pk]],
                )
                self.setdefault(conf_name, []).append(cur_struct)
    #def prefetch_hopcount_table(self, d_dev):
        #dev_pks = set()
        #for conf, srv_list in self.iteritems():
            #dev_pks |= set([cur_str.device.pk for cur_str in srv_list])
        #latest_gen = route_generation.objects.filter(Q(valid=True)).order_by("-pk")[0]
        #all_hcs = hopcount.objects.filter(
            #Q(route_generation=latest_gen) & 
            #Q(s_netdevice__device__in=dev_pks) &
            #Q(d_netdevice__in=d_dev.netdevice_idx_list)).distinct().order_by("value").values_list("s_netdevice__device", "s_netdevice", "d_netdevice", "value")
        #dev_dict = {}
        #for in_list in all_hcs:
            #dev_dict.setdefault(in_list[0], []).append(tuple(in_list[1:]))
        #for conf, srv_list in self.iteritems():
            #[cur_srv.set_hopcount_cache(dev_dict.get(cur_srv.device.pk, [])) for cur_srv in srv_list]
    def set_key_type(self, k_type):
        print "deprecated, only one key_type (config) supported"
        sys.exit(0)

if __name__ == "__main__":
    print "Loadable module, exiting ..."
    sys.exit(1)
