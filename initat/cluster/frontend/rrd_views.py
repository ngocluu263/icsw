#!/usr/bin/python -Ot
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

""" RRD views """

from django.utils.decorators import method_decorator
from django.views.generic import View
from initat.cluster.frontend.helper_functions import xml_wrapper, contact_server
from lxml.builder import E # @UnresolvedImports
import datetime
import dateutil.parser
import dateutil.tz
import json
import logging
import server_command

logger = logging.getLogger("cluster.rrd")

class device_rrds(View):
    # @method_decorator(login_required)
    # def get(self, request):
    #    return render_me(
    #        request, "rrd_class_overview.html",
    #    )()
    @method_decorator(xml_wrapper)
    def post(self, request):
        srv_com = server_command.srv_command(command="get_node_rrd")
        dev_pks = json.loads(request.POST["pks"])
        srv_com["device_list"] = E.device_list(
            *[E.device(pk="%d" % (int(dev_pk))) for dev_pk in dev_pks],
            merge_results="1"
        )
        result = contact_server(request, "grapher", srv_com, timeout=30)
        if result:
            node_results = result.xpath(".//node_results", smart_strings=False)
            if len(node_results):
                node_results = node_results[0]
                if len(node_results):
                    # first device
                    node_result = node_results[0]
                    request.xml_response["result"] = node_result
                else:
                    request.xml_response.error("no node_results", logger=logger)
            else:
                request.xml_response.error("no node_results", logger=logger)

class graph_rrds(View):
    @method_decorator(xml_wrapper)
    def post(self, request):
        _post = request.POST
        srv_com = server_command.srv_command(command="graph_rrd")
        pk_list, graph_keys = (json.loads(_post["pks"]), json.loads(_post["keys"]))
        srv_com["device_list"] = E.device_list(
            *[E.device(pk="%d" % (int(dev_pk))) for dev_pk in pk_list]
        )
        srv_com["graph_key_list"] = E.graph_key_list(
            *[E.graph_key(graph_key) for graph_key in graph_keys if not graph_key.startswith("_")]
        )
        if "start_time" in _post:
            start_time = dateutil.parser.parse(_post["start_time"])
            end_time = dateutil.parser.parse(_post["end_time"])
        else:
            start_time = datetime.datetime.now(dateutil.tz.tzutc()) - datetime.timedelta(4 * 3600)
            end_time = datetime.datetime.now(dateutil.tz.tzutc())
        srv_com["parameters"] = E.parameters(
            E.start_time(unicode(start_time)),
            E.end_time(unicode(end_time)),
            E.size(_post.get("size", "400x200")),
            E.hide_zero("1" if _post.get("hide_zero").lower() in ["1", "true"] else "0"),
        )
        result = contact_server(request, "grapher", srv_com, timeout=30)
        if result:
            graph_list = result.xpath(".//graph_list", smart_strings=False)
            if len(graph_list):
                graph_list = graph_list[0]
                if len(graph_list):
                    # first device
                    request.xml_response["result"] = graph_list
                else:
                    request.xml_response.error("no node_results", logger=logger)
            else:
                request.xml_response.error("no node_results", logger=logger)
