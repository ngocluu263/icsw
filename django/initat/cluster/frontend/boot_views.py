#!/usr/bin/python-init -Ot
# -*- coding: utf-8 -*-

""" boot views """

import json
import pprint
import logging_tools
import process_tools
from initat.cluster.frontend.helper_functions import init_logging
from initat.cluster.frontend.render_tools import render_me
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from initat.cluster.backbone.models import device_type, device_group, device, device_class, kernel, image, partition_table, status, network
from django.core.exceptions import ValidationError
from lxml import etree
from lxml.builder import E
from django.db.models import Q
import server_command
import re
import time
import net_tools
from django.core.urlresolvers import reverse
from django.db import transaction

@login_required
@init_logging
def show_boot(request):
    return render_me(
        request, "boot_overview.html",
    )()

OPTION_LIST = [("t", "target state", None),
               ("k", "kernel"      , kernel),
               ("i", "image"       , image),
               ("b", "bootdevice"  , None),
               ("p", "partition"   , partition_table)]

@login_required
@init_logging
def get_html_options(request):
    xml_resp = E.options()
    for short, long_opt, t_obj in OPTION_LIST:
        xml_resp.append(E.option(long_opt, short=short))
    request.xml_response["response"] = xml_resp
    return request.xml_response.create_response()

@login_required
@init_logging
def get_addon_info(request):
    _post = request.POST
    addon_type = _post["type"]
    addon_long, addon_class = [(long_opt, t_class) for short, long_opt, t_class in OPTION_LIST if short == addon_type][0]
    request.log("requested addon dictionary '%s'" % (addon_long))
    addon_list = E.list()
    if addon_class:
        for obj in addon_class.objects.filter(Q(enabled=True)):
            addon_list.append(obj.get_xml())
    if addon_type == "t":
        prod_nets = network.objects.filter(Q(network_type__identifier="p"))
        # add all states without production net
        for t_state in status.objects.filter(Q(prod_link=False)):
            addon_list.append(t_state.get_xml())
        # add all states with production net
        for prod_net in prod_nets:
            for t_state in status.objects.filter(Q(prod_link=True)):
                addon_list.append(t_state.get_xml(prod_net))
    request.log("returning %s" % (logging_tools.get_plural("object", len(addon_list))))
    request.xml_response["response"] = addon_list
    return request.xml_response.create_response()

@transaction.commit_manually
@login_required
@init_logging
def set_boot(request):
    _post = request.POST
    cur_dev = device.objects.get(Q(pk=_post["dev_id"].split("__")[1]))
    pprint.pprint(_post)
    boot_mac = _post["boot_mac"]
    boot_driver = _post["boot_driver"]
    dhcp_write = True if int(_post["dhcp_write"]) else False
    dhcp_mac   = True if int(_post["greedy_mode"]) else False
    any_error = False
    cur_dev.dhcp_mac = dhcp_mac
    cur_dev.dhcp_write = dhcp_write
    if cur_dev.bootnetdevice:
        bnd = cur_dev.bootnetdevice
        bnd.driver = boot_driver
        bnd.macaddr = boot_mac
        try:
            bnd.save()
        except ValidationError:
            any_error = True
            request.log("cannot save boot settings", logging_tools.LOG_LEVEL_ERROR, xml=True)
    cur_dev.save()
    transaction.commit()
    if not any_error:
        request.log("updated bootdevice settings of %s" % (unicode(cur_dev)), xml=True)
    srv_com = server_command.srv_command(command="alter_macaddr")
    srv_com["devices"] = srv_com.builder(
        "devices",
        srv_com.builder("device", name=cur_dev.name, pk="%d" % (cur_dev.pk)))
    net_tools.zmq_connection("boot_webfrontend", timeout=10).add_connection("tcp://localhost:8000", srv_com)
    return request.xml_response.create_response()

@transaction.commit_manually
@login_required
@init_logging
def set_kernel(request):
    _post = request.POST
    cur_dev = device.objects.get(Q(pk=_post["dev_id"].split("__")[1]))
    if int(_post["new_kernel"]) == 0:
        cur_dev.new_kernel = None
    else:
        cur_dev.new_kernel = kernel.objects.get(Q(pk=_post["new_kernel"]))
    cur_dev.stage1_flavour = _post["kernel_flavour"]
    cur_dev.kernel_append = _post["kernel_append"]
    cur_dev.save()
    # very important
    transaction.commit()
    srv_com = server_command.srv_command(command="refresh")
    srv_com["devices"] = srv_com.builder(
        "devices",
        srv_com.builder("device", pk="%d" % (cur_dev.pk)))
    net_tools.zmq_connection("boot_webfrontend", timeout=10).add_connection("tcp://localhost:8000", srv_com)
    request.log("updated kernel settings of %s" % (unicode(cur_dev)), xml=True)
    return request.xml_response.create_response()
    
@transaction.commit_manually
@login_required
@init_logging
def set_target_state(request):
    _post = request.POST
    cur_dev = device.objects.get(Q(pk=_post["dev_id"].split("__")[1]))
    t_state, t_prod_net = [int(value) for value in _post["target_state"].split("__")]
    if t_state == 0:
        cur_dev.new_state = None
        cur_dev.prod_link = None
    else:
        cur_dev.new_state = status.objects.get(Q(pk=t_state))
        if t_prod_net:
            cur_dev.prod_link = network.objects.get(Q(pk=t_prod_net))
        else:
            cur_dev.prod_link = None
    cur_dev.save()
    # very important
    transaction.commit()
    srv_com = server_command.srv_command(command="refresh")
    srv_com["devices"] = srv_com.builder(
        "devices",
        srv_com.builder("device", pk="%d" % (cur_dev.pk)))
    net_tools.zmq_connection("boot_webfrontend", timeout=10).add_connection("tcp://localhost:8000", srv_com)
    request.log("updated target state of %s" % (unicode(cur_dev)), xml=True)
    return request.xml_response.create_response()

@login_required
@init_logging
def get_boot_info(request):
    _post = request.POST
    option_dict = dict([(short, True if _post.get("opt_%s" % (short)) in ["true"] else False) for short, long_opt, t_class in OPTION_LIST])
    sel_list = _post.getlist("sel_list[]")
    dev_result = device.objects.filter(Q(name__in=sel_list))
    # to speed up things while testing
    result = None
    if False:
        srv_com = server_command.srv_command(command="status")
        srv_com["devices"] = srv_com.builder(
            "devices",
            *[srv_com.builder("device", pk="%d" % (cur_dev.pk)) for cur_dev in dev_result])
        result = net_tools.zmq_connection("boot_webfrontend", timeout=10).add_connection("tcp://localhost:8000", srv_com)
        if not result:
            request.log("error contacting server", logging_tools.LOG_LEVEL_ERROR, xml=True)
        else:
            pass
    xml_resp = E.boot_info()
    def_dict = {"network"       : "unknown",
                "network_state" : "error"}
    for cur_dev in dev_result:
        dev_info = cur_dev.get_xml(full=False)
        for cur_info in ["recvstate", "reqstate"]:
            dev_info.attrib[cur_info] = getattr(cur_dev, cur_info)
        if result is not None:
            # copy from mother
            dev_node = result.xpath(None, ".//ns:device[@pk='%d']" % (cur_dev.pk))
            if len(dev_node):
                dev_node = dev_node[0]
            else:
                dev_node = None
        else:
            dev_node = None
        if dev_node is not None:
            dev_info.attrib.update(dict([(key, dev_node.attrib.get(key, value)) for key, value in def_dict.iteritems()]))
        else:
            dev_info.attrib.update(def_dict)
        xml_resp.append(dev_info)
    # add option-dict related stuff
    request.xml_response["response"] = xml_resp
    return request.xml_response.create_response()
