# -*- coding: utf-8 -*-
#
# Copyright (C) 2012-2014 Andreas Lang-Nevyjel
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of webfrontend
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

""" REST views """

from django.apps import apps
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.db.models import Q
from initat.cluster.backbone import serializers as model_serializers
from initat.cluster.backbone.models.functions import can_delete_obj
from initat.cluster.backbone.models import get_related_models, get_change_reset_list, device, \
    domain_name_tree, category_tree, device_selection, device_config, home_export_list, \
    csw_permission, netdevice, cd_connection, ext_license_state_coarse, ext_license_check_coarse, \
    ext_license_version_state_coarse, ext_license_version, ext_license_user, ext_license_client, \
    ext_license_usage_coarse
from initat.cluster.backbone.serializers import device_serializer, \
    device_selection_serializer, partition_table_serializer_save, partition_disc_serializer_save, \
    partition_disc_serializer_create, device_config_help_serializer, device_serializer_only_boot, network_with_ip_serializer
from initat.cluster.frontend import forms
from initat.cluster.backbone.render import render_string
from rest_framework import mixins, generics, status, viewsets, serializers
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import exception_handler, APIView
import json
import logging
import logging_tools
import operator
import pprint  # @UnusedImport
import process_tools
import time
import types

logger = logging.getLogger("cluster.rest")

# build REST_LIST from models content
REST_LIST = []
_ser_keys = dir(model_serializers)
for key in _ser_keys:
    if key.endswith("_serializer") and key not in ["device_selection_serializer"]:
        REST_LIST.append((model_serializers, "_".join(key.split("_")[:-1])))
    elif key.endswith("Serializer"):
        REST_LIST.append((model_serializers, key[:10]))

init_apps = [_app for _app in settings.INSTALLED_APPS if _app.startswith("initat.cluster")]

if "initat.cluster.liebherr" in init_apps:
    # from initat.cluster.liebherr import models as liebherr_models
    from initat.cluster.liebherr import serializers as liebherr_serializers
    for key in dir(liebherr_serializers):
        if key.endswith("_serializer") and key not in ["device_selection_serializer"]:
            REST_LIST.append((liebherr_serializers, "_".join(key.split("_")[:-1])))

# @api_view(('GET',))
# def api_root(request, format=None):
#    return Response({
#        'user'         : reverse('rest:user_list_h', request=request),
#        'group'        : reverse('rest:group_list_h', request=request),
#        # 'network_type' : reverse('rest:network_type_list_h', request=request),
#    })


def csw_exception_handler(exc):
    response = exception_handler(exc)
    if response is None:
        detail_str, detail_info = (exc.__class__.__name__, [])
        if hasattr(exc, "messages"):
            detail_info.extend([unicode(_part) for _part in exc.messages])
        if hasattr(exc, "message"):
            detail_info.append(unicode(exc.message))
        if hasattr(exc, "args"):
            for entry in exc.args:
                detail_info.append(unicode(entry))
        detail_info = list(set([_entry for _entry in [_part.strip() for _part in detail_info if _part.strip()] if _entry not in ["()"]]))
        response = Response(
            {
                "detail": "{}{}".format(
                    detail_str,
                    " ({})".format(", ".join(detail_info)) if detail_info else ""
                ),
            },
            status=status.HTTP_406_NOT_ACCEPTABLE,
        )
    return response


class rest_logging(object):
    def __init__(self, func):
        self._func = func
        self.__name__ = self._func.__name__
        self.__obj_name = None

    def __get__(self, obj, owner_class=None):
        # magic ...
        return types.MethodType(self, obj)

    def log(self, what="", log_level=logging_tools.LOG_LEVEL_OK):
        logger.log(
            log_level,
            u"[{}{}] {}".format(
                self.__name__,
                u" {}".format(self.__obj_name) if self.__obj_name else "",
                what
            )
        )

    def __call__(self, *args, **kwargs):
        s_time = time.time()
        if hasattr(args[0], "model") and args[0].model is not None:
            self.__obj_name = args[0].model._meta.object_name
        else:
            self.__obj_name = getattr(args[0], "display_name", "unknown")
        try:
            result = self._func(*args, **kwargs)
        except:
            self.log(
                "exception: {}".format(
                    process_tools.get_except_info()
                ),
                logging_tools.LOG_LEVEL_ERROR
            )
            exc_info = process_tools.exception_info()
            for line in exc_info.log_lines:
                self.log("  {}".format(line))
            raise
        e_time = time.time()
        self.log("call took {}".format(
            logging_tools.get_diff_time_str(e_time - s_time)))
        return result


class db_prefetch_mixin(object):
    def _kernel_prefetch(self):
        return ["initrd_build_set", "kernel_build_set", "new_kernel", "act_kernel"]

    def _image_prefetch(self):
        return ["new_image", "act_image"]

    def _partition_table_prefetch(self):
        return [
            "new_partition_table", "act_partition_table", "sys_partition_set",
            "lvm_lv_set__partition_fs", "lvm_vg_set", "partition_disc_set__partition_set__partition_fs"
        ]

    def _mon_period_prefetch(self):
        return ["service_check_period"]

    def _device_related(self):
        return ["domain_tree_node", "device_type", "device_group", "mon_ext_host"]

    def _device_prefetch(self):
        return ["snmp_schemes__snmp_scheme_vendor", "DeviceSNMPInfo", "snmp_schemes__snmp_scheme_tl_oid_set"]

    def _mon_check_command_prefetch(self):
        return ["exclude_devices", "categories"]

    def _mon_host_cluster_prefetch(self):
        return ["devices"]

    def _mon_host_dependency_prefetch(self):
        return ["devices", "dependent_devices"]

    def _network_prefetch(self):
        return ["network_device_type", "net_ip_set"]

    def _virtual_desktop_protocol_prefetch(self):
        return ["devices"]

    def _window_manager_prefetch(self):
        return ["devices"]

    def _netdevice_prefetch(self):
        return ["net_ip_set"]

    def _user_related(self):
        return ["group"]

    def _background_job_related(self):
        return ["initiator__domain_tree_node", "user"]

    def _user_prefetch(self):
        return [
            "user_permission_set", "user_object_permission_set__csw_object_permission", "secondary_groups",
            "allowed_device_groups", "user_quota_setting_set", "user_scan_run_set__user_scan_result_set",
        ]

    def _group_related(self):
        return ["parent_group"]

    def _group_prefetch(self):
        return ["group_permission_set", "group_object_permission_set", "group_object_permission_set__csw_object_permission", "allowed_device_groups"]

    def _config_prefetch(self):
        return [
            "categories", "config_str_set", "config_int_set", "config_blob_set",
            "config_bool_set", "config_script_set", "mon_check_command_set__categories", "mon_check_command_set__exclude_devices",
            "device_config_set"]

    def _cransys_dataset_prefetch(self):
        return ["cransys_job_set", "cransys_job_set__cransys_run_set"]

    def _config_hint_prefetch(self):
        return [
            "config_var_hint_set",
            "config_script_hint_set",
        ]

    def _mon_dist_master_prefetch(self):
        return ["mon_dist_slave_set"]

    def _macbootlog_related(self):
        return ["device__domain_tree_node"]

    def _device_mon_location_related(self):
        return ["device__domain_tree_node"]

    def _location_gfx_put(self, req_changes, prev_model):
        print req_changes
        req_changes.update(
            {
                key: getattr(prev_model, key) for key in ["image_count"]
            }
        )
        print req_changes
        return req_changes


class detail_view(mixins.RetrieveModelMixin,
                  mixins.UpdateModelMixin,
                  mixins.DestroyModelMixin,
                  generics.SingleObjectAPIView,
                  db_prefetch_mixin):
    @rest_logging
    def get(self, request, *args, **kwargs):
        return self.retrieve(request, *args, **kwargs)

    @rest_logging
    def get_serializer_class(self):
        if self.model._meta.object_name == "partition_table":
            return partition_table_serializer_save
        if self.model._meta.object_name == "partition_disc":
            return partition_disc_serializer_save
        else:
            return self.serializer_class

    @rest_logging
    def get_queryset(self):
        model_name = self.model._meta.model_name
        related_fields, prefetch_fields = (
            getattr(self, "_{}_related".format(model_name), lambda: [])(),
            getattr(self, "_{}_prefetch".format(model_name), lambda: [])(),
        )
        res = self.model.objects
        return res.select_related(*related_fields).prefetch_related(*prefetch_fields)

    @rest_logging
    def put(self, request, *args, **kwargs):
        model_name = self.model._meta.model_name
        prev_model = self.model.objects.get(Q(pk=kwargs["pk"]))
        req_changes = getattr(self, "_{}_put".format(model_name), lambda changed, prev: changed)(request.DATA, prev_model)
        # try:
        resp = self.update(request, *args, **kwargs)
        # except ValidationError as cur_exc:
        #    print cur_exc
        # print dir(resp), resp.data
        new_model = self.model.objects.get(Q(pk=kwargs["pk"]))
        if self.model._meta.object_name == "device":
            root_pwd = new_model.crypt(req_changes.get("root_passwd", ""))
            if root_pwd:
                new_model.root_passwd = root_pwd
                new_model.save()
        c_list, r_list = get_change_reset_list(prev_model, new_model, req_changes)
        # print c_list, r_list
        resp.data["_change_list"] = c_list
        resp.data["_reset_list"] = r_list
        return resp

    @rest_logging
    def delete(self, request, *args, **kwargs):
        # just be careful
        cur_obj = self.model.objects.get(Q(pk=kwargs["pk"]))
        if can_delete_obj(cur_obj, logger): # this also throws on negative answer
            return self.destroy(request, *args, **kwargs)
            # it makes no sense to return something meaningful because the DestroyModelMixin returns
            # a 204 status on successful deletion
            # print "****", "del"
            # print unicode(cur_obj), resp.data
            # if not resp.data:
            #    resp.data = {}
            # resp.data["_messages"] = [u"deleted '%s'" % (unicode(cur_obj))]
            # return resp


class list_view(mixins.ListModelMixin,
                mixins.CreateModelMixin,
                generics.MultipleObjectAPIView,
                db_prefetch_mixin
                ):
    @rest_logging
    def get(self, request, *args, **kwargs):
        return self.list(request, *args, **kwargs)

    @rest_logging
    def post(self, request, *args, **kwargs):
        resp = self.create(request, *args, **kwargs)
        if resp.status_code in [200, 201, 202, 203]:
            resp.data["_messages"] = [u"created '{}'".format(unicode(self.object))]
        return resp

    @rest_logging
    def get_serializer_class(self):
        if self.request.method == "POST":
            if self.model._meta.object_name == "partition_disc":
                return partition_disc_serializer_create
        elif self.request.method == "GET":
            if self.model._meta.object_name == "network":
                if "_with_ip_info" in self.request.QUERY_PARAMS:
                    return network_with_ip_serializer
        return self.serializer_class

    @rest_logging
    def get_queryset(self):
        model_name = self.model._meta.model_name
        if model_name == "domain_tree_node":
            return domain_name_tree()
        elif model_name == "category":
            return category_tree(with_ref_count=True)
        related_fields, prefetch_fields = (
            getattr(self, "_{}_related".format(model_name), lambda: [])(),
            getattr(self, "_{}_prefetch".format(model_name), lambda: [])(),
        )
        res = self.model.objects.all()
        filter_list = []
        special_dict = {}
        for key, value in self.request.QUERY_PARAMS.iteritems():
            if key.startswith("_"):
                special_dict[key[1:]] = value
            else:
                if key.endswith("__in"):
                    filter_list.append(Q(**{key: json.loads(value)}))
                else:
                    filter_list.append(Q(**{key: value}))
        if filter_list:
            res = res.filter(reduce(operator.iand, filter_list))
        res = res.select_related(*related_fields).prefetch_related(*prefetch_fields)
        if "distinct" in special_dict:
            res = res.distinct()
        if "order_by" in special_dict:
            res = res.order_by(special_dict["order_by"])
        if "num_entries" in special_dict:
            res = res[0:special_dict["num_entries"]]
        return res


class form_serializer(serializers.Serializer):
    name = serializers.CharField()
    form = serializers.CharField()


class ext_peer_object(dict):
    def __init__(self, *args, **kwargs):
        dict.__init__(self, **kwargs)
        self["fqdn"] = "{}{}".format(
            self["device__name"],
            ".{}".format(self["device__domain_tree_node__full_name"]) if self["device__domain_tree_node__full_name"] else "",
            )


class ext_peer_serializer(serializers.Serializer):
    idx = serializers.IntegerField(source="pk")
    penalty = serializers.IntegerField()
    device_name = serializers.CharField(source="device__name")
    device_group_name = serializers.CharField(source="device__device_group__name")
    devname = serializers.CharField()
    routing = serializers.BooleanField()
    fqdn = serializers.CharField()


class netdevice_peer_list(viewsets.ViewSet):
    display_name = "netdevice_peer_list"

    @rest_logging
    def list(self, request):
        ext_list = [
            ext_peer_object(**_obj) for _obj in netdevice.objects.filter(
                Q(device__enabled=True) & Q(device__device_group__enabled=True)
            ).filter(
                Q(enabled=True)
            ).filter(
                Q(peer_s_netdevice__gt=0) | Q(peer_d_netdevice__gt=0) | Q(routing=True)
            ).distinct().order_by(
                "device__device_group__name",
                "device__name",
                "devname",
            ).select_related(
                "device",
                "device__device_group",
                "device__domain_tree_node"
            ).values("pk", "devname", "penalty", "device__name", "device__device_group__name", "routing", "device__domain_tree_node__full_name")
        ]
        # .filter(Q(net_ip__network__network_type__identifier="x") | Q(net_ip__network__network_type__identifier__in=["p", "o", "s", "b"])) \
        _ser = ext_peer_serializer(ext_list, many=True)
        return Response(_ser.data)


class rest_home_export_list(mixins.ListModelMixin,
                            generics.MultipleObjectAPIView):
    authentication_classes = (SessionAuthentication,)
    permission_classes = (IsAuthenticated,)
    model = device_config

    @rest_logging
    def get_serializer_class(self):
        return device_config_help_serializer

    @rest_logging
    def get(self, request, *args, **kwargs):
        # print self.list(request, *args, **kwargs)
        return self.list(request, *args, **kwargs)

    @rest_logging
    def get_queryset(self):
        return home_export_list().all()


class csw_object_serializer(serializers.Serializer):
    idx = serializers.IntegerField()
    name = serializers.CharField()
    group = serializers.CharField()
    tr_class = serializers.CharField()


class csw_object_group_serializer(serializers.Serializer):
    content_label = serializers.CharField()
    content_type = serializers.IntegerField()
    object_list = csw_object_serializer(many=True)


class csw_object_group(object):
    def __init__(self, ct_label, ct_idx, obj_list):
        self.content_label = ct_label
        self.content_type = ct_idx
        self.object_list = obj_list


class csw_object(object):
    def __init__(self, idx, name, group, tr_class):
        self.idx = idx
        self.name = name
        self.group = group
        self.tr_class = tr_class


class min_access_levels(viewsets.ViewSet):
    # returns minimum levels of access for a given object type / object list
    display_name = "min_access_levels"

    @rest_logging
    def list(self, request):
        obj_list = json.loads(request.QUERY_PARAMS["obj_list"])
        min_dict = None
        for _dev in apps.get_model("backbone", request.QUERY_PARAMS["obj_type"]).objects.filter(Q(pk__in=obj_list)):
            _cur_dict = request.user.get_object_access_levels(_dev)
            if min_dict is None:
                min_dict = _cur_dict
            else:
                for key, value in _cur_dict.iteritems():
                    min_dict[key] = min(min_dict.get(key, -1), value)
        if min_dict is None:
            min_dict = {}
        min_dict = {_key: _value for _key, _value in min_dict.iteritems() if _value >= 0}
        return Response(min_dict)


class csw_object_list(viewsets.ViewSet):
    display_name = "csw_object_groups"

    @rest_logging
    def list(self, request):
        all_db_perms = csw_permission.objects.filter(Q(valid_for_object_level=True)).select_related("content_type")
        perm_cts = ContentType.objects.filter(Q(pk__in=[cur_perm.content_type_id for cur_perm in all_db_perms])).order_by("name")
        group_list = []
        for perm_ct in perm_cts:
            cur_group = csw_object_group(
                "{}.{}".format(perm_ct.app_label, perm_ct.name),
                perm_ct.pk,
                self._get_objects(perm_ct, [ct_perm for ct_perm in all_db_perms if ct_perm.content_type_id == perm_ct.pk])
            )
            group_list.append(cur_group)
        _ser = csw_object_group_serializer(group_list, many=True)
        return Response(_ser.data)

    def _get_objects(self, cur_ct, perm_list):
        cur_model = apps.get_model(cur_ct.app_label, cur_ct.name)
        _q = cur_model.objects
        _key = "{}.{}".format(cur_ct.app_label, cur_ct.name)
        if _key == "backbone.device":
            _q = _q.select_related("device_type", "device_group"). \
                filter(Q(enabled=True, device_group__enabled=True)). \
                order_by("-device_group__cluster_device_group", "device_group__name", "-device_type__priority", "name")
        if _key == "backbone.user":
            _q = _q.select_related("group")
        return [csw_object(cur_obj.pk, self._get_name(_key, cur_obj), self._get_group(_key, cur_obj), self._tr_class(_key, cur_obj)) for cur_obj in _q.all()]

    def _get_name(self, _key, cur_obj):
        if _key == "backbone.device":
            if cur_obj.device_type.identifier == "MD":
                return unicode(cur_obj)[8:] + (" [CDG]" if cur_obj.device_group.cluster_device_group else " [MD]")
        return unicode(cur_obj)

    def _get_group(self, _key, cur_obj):
        if _key == "backbone.device":
            return unicode(cur_obj.device_group)
        elif _key == "backbone.user":
            return unicode(cur_obj.group)
        else:
            return "top"

    def _tr_class(self, _key, cur_obj):
        _lt = ""
        if _key == "backbone.device":
            if cur_obj.device_type.identifier == "MD":
                _lt = "warning"
        return _lt


class device_tree_mixin(object):
    def _get_post_boolean(self, name, default):
        if name in self.request.QUERY_PARAMS:
            p_val = self.request.QUERY_PARAMS[name]
            if p_val.lower() in ["1", "true"]:
                return True
            else:
                return False
        else:
            return default

    @rest_logging
    def _get_serializer_context(self):
        ctx = {"request": self.request}
        if self.request.QUERY_PARAMS.get("olp", ""):
            ctx["olp"] = self.request.QUERY_PARAMS["olp"]
        _fields = []
        if self._get_post_boolean("with_disk_info", False):
            _fields.extend(["partition_table", "act_partition_table"])
        if self._get_post_boolean("with_network", False):
            _fields.append("netdevice_set")
        if self._get_post_boolean("with_monitoring_hint", False):
            _fields.append("monitoring_hint_set")
        if self._get_post_boolean("with_categories", False):
            _fields.append("categories")
        if self._get_post_boolean("with_variables", False):
            _fields.append("device_variable_set")
        if self._get_post_boolean("with_device_configs", False):
            _fields.append("device_config_set")
        if self._get_post_boolean("with_mon_locations", False):
            _fields.append("device_mon_location_set")
        if self._get_post_boolean("package_state", False):
            _fields.extend(["package_device_connection_set", "latest_contact", "client_version"])
        if self._get_post_boolean("monitor_server_type", False):
            _fields.append("monitor_type")
        if _fields:
            ctx["fields"] = _fields
        return ctx


class device_tree_detail(detail_view, device_tree_mixin):
    model = device

    @rest_logging
    def get_serializer_context(self):
        return self._get_serializer_context()

    @rest_logging
    def get_serializer_class(self):
        if self._get_post_boolean("tree_mode", False):
            return device_serializer
        if self._get_post_boolean("only_boot", False):
            return device_serializer_only_boot
        else:
            return device_serializer


class device_tree_list(mixins.ListModelMixin,
                       mixins.CreateModelMixin,
                       generics.MultipleObjectAPIView,
                       device_tree_mixin,
                       ):
    authentication_classes = (SessionAuthentication,)
    permission_classes = (IsAuthenticated,)
    model = device

    @rest_logging
    def get_serializer_context(self):
        return self._get_serializer_context()

    @rest_logging
    def get_serializer_class(self):
        return device_serializer

    @rest_logging
    def get(self, request, *args, **kwargs):
        # print self.list(request, *args, **kwargs)
        return self.list(request, *args, **kwargs)

    @rest_logging
    def post(self, request, *args, **kwargs):
        resp = self.create(request, *args, **kwargs)
        if resp.status_code in [200, 201, 202, 203]:
            resp.data["_messages"] = [u"created '{}'".format(unicode(self.object))]
        return resp

    @rest_logging
    def get_queryset(self):
        # with_variables = self._get_post_boolean("with_variables", False)
        package_state = self._get_post_boolean("package_state", False)
        _q = device.objects
        # permission handling
        if not self.request.user.is_superuser:
            if self.request.QUERY_PARAMS.get("olp", ""):
                # object permissions needed for devices, get a list of all valid pks
                allowed_pks = self.request.user.get_allowed_object_list(self.request.QUERY_PARAMS["olp"])
                dg_list = list(
                    device.objects.filter(
                        Q(pk__in=allowed_pks)
                    ).values_list("pk", "device_group", "device_group__device", "device_type__identifier")
                )
                # meta_list, device group selected
                meta_list = Q(device_group__in=[devg_idx for dev_idx, devg_idx, md_idx, dt in dg_list if dt == "MD"])
                # device list, direct selected
                device_list = Q(pk__in=set(sum([[dev_idx, md_idx] for dev_idx, devg_idx, md_idx, dt in dg_list if dt != "MD"], [])))
                _q = _q.filter(meta_list | device_list)
            if not self.request.user.has_perm("backbone.device.all_devices"):
                _q = _q.filter(Q(device_group__in=self.request.user.allowed_device_groups.all()))
        if self._get_post_boolean("monitor_server_type", False):
            _q = _q.filter(Q(device_config__config__name__in=["monitor_server", "monitor_slave"]))
        elif self._get_post_boolean("all_mother_servers", False):
            _q = _q.filter(Q(device_config__config__name__in=["mother_server", "mother"]))
        elif self._get_post_boolean("all_devices", False):
            pass
        else:
            # flags
            # ignore meta devices (== device groups)
            ignore_md = self._get_post_boolean("ignore_meta_devices", False)
            # ignore the cluster device group
            ignore_cdg = self._get_post_boolean("ignore_cdg", True)
            # always add the meta_devices
            with_md = self._get_post_boolean("with_meta_devices", False)
            if with_md:
                ignore_md = False
            if "pks" in self.request.QUERY_PARAMS:
                dev_keys = json.loads(self.request.QUERY_PARAMS["pks"])
                if self._get_post_boolean("cd_connections", False):
                    cd_con_pks = set(sum([[_v[0], _v[1]] for _v in cd_connection.objects.all().values_list("parent", "child")], []))
                    dev_keys = list(set(dev_keys) | cd_con_pks)
            else:
                # only selected ones
                # normally (frontend in-sync with backend) meta-devices have the same selection state
                # as their device_groups, devg_keys are in fact redundant ...
                if self._get_post_boolean("ignore_selection", False):
                    # take all devices the user is allowed to access
                    dev_keys = device.objects.all().values_list("pk", flat=True)
                else:
                    dev_keys = [key.split("__")[1] for key in self.request.session.get("sel_list", []) if key.startswith("dev_")]
            # devg_keys = [key.split("__")[1] for key in self.request.session.get("sel_list", []) if key.startswith("devg_")]
            if ignore_cdg:
                # ignore cluster device group
                _q = _q.exclude(Q(device_group__cluster_device_group=True))
            if ignore_md:
                # ignore all meta-devices
                _q = _q.exclude(Q(device_type__identifier="MD"))
            if with_md:
                md_pks = set(device.objects.filter(Q(pk__in=dev_keys)).values_list("device_group__device", flat=True))
                dev_keys.extend(md_pks)
                if not ignore_cdg:
                    dev_keys.extend(device.objects.filter(Q(device_group__cluster_device_group=True)).values_list("pk", flat=True))
            _q = _q.filter(Q(pk__in=dev_keys))
        if not self._get_post_boolean("ignore_disabled", False):
            _q = _q.filter(Q(enabled=True) & Q(device_group__enabled=True))
        _q = _q.select_related(
            "domain_tree_node",
            "device_type",
            "device_group",
        ).prefetch_related(
            "snmp_schemes__snmp_scheme_vendor",
            "DeviceSNMPInfo",
            "snmp_schemes__snmp_scheme_tl_oid_set",
        )
        if package_state:
            _q = _q.prefetch_related(
                "package_device_connection_set",
                "device_variable_set",
                "package_device_connection_set__kernel_list",
                "package_device_connection_set__image_list",
            )
        if self._get_post_boolean("with_categories", False):
            _q = _q.prefetch_related("categories")
        if self._get_post_boolean("with_variables", False):
            _q = _q.prefetch_related("device_variable_set")
        if self._get_post_boolean("with_device_configs", False):
            _q = _q.prefetch_related("device_config_set")
        if self._get_post_boolean("with_mon_locations", False):
            _q = _q.prefetch_related("device_mon_location_set")
        if self._get_post_boolean("with_disk_info", False):
            _q = _q.prefetch_related(
                "partition_table__partition_disc_set__partition_set",
                "partition_table__lvm_vg_set",
                "partition_table__lvm_lv_set",
                "partition_table__sys_partition_set",
                "partition_table__new_partition_table",
                "partition_table__act_partition_table",
                "act_partition_table__partition_disc_set__partition_set",
                "act_partition_table__lvm_vg_set",
                "act_partition_table__lvm_lv_set",
                "act_partition_table__sys_partition_set",
                "act_partition_table__new_partition_table",
                "act_partition_table__act_partition_table",
            )
        if self._get_post_boolean("with_network", False):
            _q = _q.prefetch_related(
                "netdevice_set__net_ip_set__network__network_type",
                "netdevice_set__net_ip_set__network__network_device_type",
                )
        # ordering: at first cluster device group, then by group / device_type / name
        _q = _q.order_by("-device_group__cluster_device_group", "device_group__name", "-device_type__priority", "name")
        # print _q.count(), self.request.QUERY_PARAMS, self.request.session.get("sel_list", [])
        return _q


class device_selection_list(APIView):
    authentication_classes = (SessionAuthentication,)
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        ser = device_selection_serializer([device_selection(cur_sel) for cur_sel in request.session.get("sel_list", [])], many=True)
        return Response(ser.data)

for src_mod, obj_name in REST_LIST:
    if obj_name[0].lower() != obj_name[0]:
        ser_name = "{}Serializer".format(obj_name)
    else:
        ser_name = "{}_serializer".format(obj_name)
    ser_class = getattr(src_mod, ser_name)
    for mode in ["list", "detail"]:
        class_name = "{}_{}".format(obj_name, mode)
        globals()[class_name] = type(
            class_name,
            (detail_view,) if mode == "detail" else (list_view,),
            {
                "authentication_classes": (SessionAuthentication,),
                "permission_classes": (IsAuthenticated,),
                "model": ser_class.Meta.model,
                "serializer_class": ser_class
            }
        )