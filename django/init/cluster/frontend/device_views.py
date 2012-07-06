#!/usr/bin/python-init -Ot
# -*- coding: utf-8 -*-

""" device views """

import json
import pprint
import logging_tools
import process_tools
from init.cluster.frontend.helper_functions import init_logging
from init.cluster.frontend.render_tools import render_me
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from init.cluster.backbone.models import device_type, device_group, device, device_class
from django.core.exceptions import ValidationError
from lxml import etree
from lxml.builder import E
from django.db.models import Q
import re
import time
from django.core.urlresolvers import reverse

@login_required
@init_logging
def device_tree(request):
    return render_me(request ,"device_tree.html", hide_sidebar=True)()

@login_required
@init_logging
def get_json_tree(request):
    _post = request.POST
    # build list for device_selection -> group lookup
    sel_list = request.session.get("sel_list", [])
    dg_list = device_group.objects.filter(Q(device_group__in=[cur_sel.split("_")[-1] for cur_sel in sel_list if cur_sel.startswith("dev_")])).values_list("pk", flat=True)
    full_tree = device_group.objects.order_by("-cluster_device_group", "name")
    json_struct = []
    for cur_dg in full_tree:
        key = "dg__%d" % (cur_dg.pk)
        cur_jr = {
            "title"    : unicode(cur_dg),
            "isFolder" : True,
            "isLazy"   : True,
            "select"   : key in sel_list,
            "expand"   : cur_dg.pk in dg_list,
            "key"      : key,
            "url"      : reverse("device:get_json_devlist"),
            "data"     : {"dg_idx" : cur_dg.pk},
            "children" : _get_device_list(request, cur_dg.pk) if cur_dg.pk in dg_list else []
        }
        json_struct.append(cur_jr)
    return HttpResponse(json.dumps(json_struct),
                        mimetype="application/json")

def _get_device_list(request, dg_idx):
    cur_devs = device.objects.filter(Q(device_group=dg_idx)).select_related("device_type").order_by("name")
    sel_list = request.session.get("sel_list", [])
    json_struct = []
    for sub_dev in cur_devs:
        if sub_dev.device_type.identifier not in ["MD"]:
            key = "dev__%d" % (sub_dev.pk)
            json_struct.append({
                "title"  : unicode(sub_dev),
                "select" : True if key in sel_list else False,
                "key"    : key
            })
    return json_struct
    
@login_required
@init_logging
def get_json_devlist(request):
    _post = request.POST
    return HttpResponse(json.dumps(_get_device_list(request, _post["dg_idx"])),
                        mimetype="application/json")

@login_required
@init_logging
def get_xml_tree(request):
    _post = request.POST
    full_tree = device_group.objects.all().prefetch_related("device", "device_group").distinct().order_by("-cluster_device_group", "name")
    xml_resp = E.response()
    for cur_dg in full_tree:
        dev_list = E.devices()
        for cur_d in cur_dg.device_group.all():
            d_el = E.device(
                unicode(cur_d),
                name=cur_d.name,
                comment=cur_d.comment,
                device_type="%d" % (cur_d.device_type_id),
                device_group="%d" % (cur_d.device_group_id),
                idx="%d" % (cur_d.pk),
                key="dev__%d" % (cur_d.pk)
            )
            dev_list.append(d_el)
        dg_el = E.device_group(
            dev_list,
            unicode(cur_dg),
            name=cur_dg.name,
            description=cur_dg.description,
            key="dg__%d" % (cur_dg.pk),
            idx="%d" % (cur_dg.pk),
            is_cdg="1" if cur_dg.cluster_device_group else "0")
        xml_resp.append(dg_el)
    # add device type
    xml_resp.append(
        E.device_types(
            *[E.device_type(name=cur_dt.description,
                            identifier=cur_dt.identifier, idx="%d" % (cur_dt.pk))
              for cur_dt in device_type.objects.all()]
        )
    )
    request.xml_response["response"] = xml_resp
    #request.log("catastrophic error", logging_tools.LOG_LEVEL_ERROR, xml=True)
    return request.xml_response.create_response()

@login_required
@init_logging
def create_device_group(request):
    _post = request.POST
    name = _post["name"]
    try:
        new_dg = device_group(name=name,
                              description=_post["description"])
        new_dg.save()
    except:
        request.log("cannot create device_group %s" % (name),
                    logging_tools.LOG_LEVEL_ERROR,
                    xml=True)
        request.log(" - %s" % (process_tools.get_except_info()), logging_tools.LOG_LEVEL_ERROR)
    else:
        new_dg.add_meta_device()
    return request.xml_response.create_response()

@login_required
@init_logging
def delete_device_group(request):
    pk = request.POST["idx"]
    try:
        device_group.objects.get(Q(pk=pk)).delete()
    except:
        request.log("cannot delete device_group",
                    logging_tools.LOG_LEVEL_ERROR,
                    xml=True)
        request.log(" - %s" % (process_tools.get_except_info()), logging_tools.LOG_LEVEL_ERROR)
    return request.xml_response.create_response()

@login_required
@init_logging
def create_device(request):
    _post = request.POST
    range_re = re.compile("^(?P<name>.+)\[(?P<start>\d+)-(?P<end>\d+)\](?P<post>.*)$")
    name = request.POST["name"]
    range_m = range_re.match(name)
    if range_m is None:
        create_list = [name]
    else:
        num_dig = max(len(range_m.group("start")),
                      len(range_m.group("end")))
        start_idx, end_idx = (int(range_m.group("start")),
                              int(range_m.group("end")))
        start_idx, end_idx = (min(start_idx, end_idx),
                              max(start_idx, end_idx))
        start_idx, end_idx = (min(max(start_idx, 1), 1000),
                              min(max(end_idx, 1), 1000))
        request.log("range has %s (%d -> %d)" % (logging_tools.get_plural("digit", num_dig),
                                                 start_idx,
                                                 end_idx))
        form_str = "%s%%0%dd%s" % (range_m.group("name"),
                                   num_dig,
                                   range_m.group("post"))
        create_list = [form_str % (cur_idx) for cur_idx in xrange(start_idx, end_idx + 1)]
    for create_dev in sorted(create_list):
        try:
            new_dev = device(name=create_dev,
                             device_group=device_group.objects.get(Q(pk=_post["group"])),
                             comment=_post["comment"],
                             device_type=device_type.objects.get(Q(pk=_post["type"])),
                             device_class=device_class.objects.get(Q(pk=1)))
            new_dev.save()
        except ValidationError, what:
            request.log("error creating: %s" % (unicode(what.messages[0])), logging_tools.LOG_LEVEL_ERROR, xml=True)
            break
        else:
            pass
    return request.xml_response.create_response()

@login_required
@init_logging
def delete_device(request):
    pk = request.POST["idx"]
    try:
        device.objects.get(Q(pk=pk)).delete()
    except:
        request.log("cannot delete device",
                    logging_tools.LOG_LEVEL_ERROR,
                    xml=True)
        request.log(" - %s" % (process_tools.get_except_info()), logging_tools.LOG_LEVEL_ERROR)
    else:
        request.log("deleted device", xml=True)
    return request.xml_response.create_response()
    
@login_required
@init_logging
def clear_selection(request):
    request.session["sel_list"] = []
    request.session.save()
    return request.xml_response.create_response()
    
@login_required
@init_logging
def add_selection(request):
    cur_list = request.session.get("sel_list", [])
    _post = request.POST
    add_flag, add_sel = (int(_post["add"]), _post["key"])
    if add_flag and add_sel not in cur_list:
        cur_list.append(add_sel)
    elif not add_flag and add_sel in cur_list:
        cur_list.remove(add_sel)
    if add_sel.startswith("dg_"):
        # emulate toggle of device_group
        request.log("toggle selection of device_group %d" % (int(add_sel.split("__")[1])))
        toggle_devs = ["dev__%d" % (cur_pk) for cur_pk in device.objects.filter(Q(device_group=add_sel.split("__")[1])).values_list("pk", flat=True)]
        for toggle_dev in toggle_devs:
            if toggle_dev in cur_list:
                cur_list.remove(toggle_dev)
            else:
                cur_list.append(toggle_dev)
    request.session["sel_list"] = cur_list
    request.session.save()
    request.log("%s in list" % (logging_tools.get_plural("selection", len(cur_list))))
    return request.xml_response.create_response()

