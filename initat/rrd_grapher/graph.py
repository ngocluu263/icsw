# Copyright (C) 2007-2009,2013-2014 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file belongs to the rrd-server package
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
""" grapher part of rrd-grapher service """

from django.conf import settings
from django.db import connection
from django.db.models import Q
from initat.cluster.backbone.models import device
from initat.rrd_grapher.config import global_config
from lxml import etree # @UnresolvedImport
from lxml.builder import E # @UnresolvedImport
import datetime
import logging_tools
import os
import pprint
import process_tools
import re
import rrdtool # @UnresolvedImport
import server_command
import threading_tools
import time

class colorizer(object):
    def __init__(self, g_proc):
        self.graph_process = g_proc
        self.def_color_table = "dark28"
        self._read_files()
    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.graph_process.log("[col] {}".format(what), log_level)
    def _read_files(self):
        self.colortables = etree.fromstring(file(global_config["COLORTABLE_FILE"], "r").read())
        self.color_tables = {}
        for c_table in self.colortables.findall(".//colortable[@name]"):
            self.color_tables[c_table.get("name")] = ["#{:d}".format(color.get("rgb")) for color in c_table if self._check_color(color)]
        self.log("read colortables from {}".format(global_config["COLORTABLE_FILE"]))
        self.color_rules = etree.fromstring(file(global_config["COLORRULES_FILE"], "r").read())
        self.log("read colorrules from {}".format(global_config["COLORRULES_FILE"]))
        self.match_re_keys = [
            (re.compile("^{}".format(entry.attrib["key"].replace(".", r"\."))),
             entry) for entry in self.color_rules.xpath(".//entry[@key]", smart_strings=False)]
        # fast lookup table, store computed lookups
        self.fast_lut = {}
    def _check_color(self, color):
        cur_c = "#{}".format(color.get("rgb"))
        return (int(cur_c[1:3], 16) + int(cur_c[3:5], 16) + int(cur_c[5:7], 16)) < 3 * 224
    def reset(self):
        # reset values for next graph
        self.table_offset = {}
    def get_color_and_style(self, entry):
        t_name, s_dict = self.get_table_name(entry)
        if t_name not in self.table_offset:
            self.table_offset[t_name] = 0
        self.table_offset[t_name] += 1
        if self.table_offset[t_name] == len(self.color_tables[t_name]):
            self.table_offset[t_name] = 0
        return self.color_tables[t_name][self.table_offset[t_name]], s_dict
    def get_table_name(self, entry):
        s_dict = {}
        key_name = entry.get("full", entry.get("name"))
        if key_name not in self.fast_lut:
            for c_re, c_entry in self.match_re_keys:
                if c_re.match(key_name):
                    self.fast_lut[key_name] = c_entry
        t_name = self.def_color_table
        if key_name in self.fast_lut:
            c_xml = self.fast_lut[key_name]
            if c_xml.find(".//range[@colortable]") is not None:
                t_name = c_xml.find(".//range[@colortable]").get("colortable")
            for modify_xml in c_xml.findall("modify"):
                if re.match(modify_xml.get("key_match"), key_name):
                    s_dict[modify_xml.attrib["attribute"]] = modify_xml.attrib["value"]
        return t_name, s_dict

class graph_var(object):
    var_idx = 0
    def __init__(self, entry, dev_name="", graph_width=800):
        self.entry = entry
        self.dev_name = dev_name
        self.width = graph_width
        self.max_info_width = 60 + int((self.width - 800) / 8)
        graph_var.var_idx += 1
        self.name = "v{:d}".format(graph_var.var_idx)
    def __getitem__(self, key):
        return self.entry.attrib[key]
    def __contains__(self, key):
        return key in self.entry.attrib
    def get(self, key, default):
        return self.entry.attrib.get(key, default)
    @staticmethod
    def init(clrz):
        graph_var.var_idx = 0
        graph_var.colorizer = clrz
        graph_var.colorizer.reset()
    @property
    def info(self):
        info = self["info"]
        parts = self["name"].split(".")
        for idx in xrange(len(parts)):
            info = info.replace("${:d}".format(idx + 1), parts[idx])
        if self.dev_name:
            info = "{} ({})".format(info, str(self.dev_name))
        return info
    def get_color_and_style(self):
        self.color, self.style_dict = graph_var.colorizer.get_color_and_style(self.entry)
    @property
    def config(self):
        self.get_color_and_style()
        if self.entry.tag == "value":
            # pde entry
            c_lines = [
                "DEF:{}={}:{}:AVERAGE".format(self.name, self["file_name"], self["part"]),
            ]
        else:
            # machvector entry
            c_lines = [
                "DEF:{}={}:v:AVERAGE".format(self.name, self["file_name"]),
            ]
        if int(self.get("invert", "0")):
            c_lines.append(
                "CDEF:{}inv={},-1,*".format(self.name, self.name),
            )
            draw_name = "{}inv".format(self.name)
        else:
            draw_name = self.name
        c_lines.append(
            "{}:{}{}:<tt>{}</tt>".format(
                self.style_dict.get("draw_type", "LINE1"),
                draw_name,
                self.color,
                ("{{:-{:d}s}}".format(self.max_info_width)).format(self.info)[:self.max_info_width]),
        )
        for rep_name, cf in [
            ("min"  , "MINIMUM"),
            ("ave"  , "AVERAGE"),
            ("max"  , "MAXIMUM"),
            ("last" , "LAST"),
            ("total", "TOTAL")]:
            c_lines.extend(
                [
                    "VDEF:{}{}={},{}".format(self.name, rep_name, self.name, cf),
                    "GPRINT:{}{}:<tt>%6.1lf%s</tt>{}".format(
                        self.name, rep_name,
                        r"\l" if rep_name == "total" else r""
                        ),
                ]
            )
        return c_lines
    @property
    def header_line(self):
        return "COMMENT:<tt>{}{}</tt>\\n".format(
            ("{{:-{:d}s}}".format(self.max_info_width + 2)).format("value"),
            "".join(["{:9s}".format(rep_name) for rep_name in ["min", "ave", "max", "latest", "total"]])
        )

class graph_process(threading_tools.process_obj):
    def process_init(self):
        self.__log_template = logging_tools.get_logger(global_config["LOG_NAME"], global_config["LOG_DESTINATION"], zmq=True, context=self.zmq_context, init_logger=True)
        connection.close()
        self.register_func("graph_rrd", self._graph_rrd)
        self.register_func("xml_info", self._xml_info)
        self.vector_dict = {}
        self.graph_root = global_config["GRAPH_ROOT"]
        self.log("graphs go into {}".format(self.graph_root))
        self.colorizer = colorizer(self)
    def log(self, what, log_level=logging_tools.LOG_LEVEL_OK):
        self.__log_template.log(log_level, what)
    def loop_post(self):
        self._close()
        self.__log_template.close()
    def _close(self):
        pass
    def _xml_info(self, *args, **kwargs):
        dev_id, xml_str = (args[0], etree.fromstring(args[1]))
        self.vector_dict[dev_id] = xml_str # self._struct_vector(xml_str)
    def _create_graph_keys(self, graph_keys):
        # graph_keys ... list of keys
        first_level_keys = set([key.split(".")[0].split(":")[-1] for key in graph_keys])
        g_key_dict = dict([(flk, sorted([key for key in graph_keys if key.split(".")[0].split(":")[-1] == flk])) for flk in first_level_keys])
        return g_key_dict
    def _graph_rrd(self, *args, **kwargs):
        src_id, srv_com = (args[0], server_command.srv_command(source=args[1]))
        dev_pks = [entry for entry in map(lambda x: int(x), srv_com.xpath(".//device_list/device/@pk", smart_strings=False)) if entry in self.vector_dict]
        dev_dict = dict([(cur_dev.pk, unicode(cur_dev.full_name)) for cur_dev in device.objects.filter(Q(pk__in=dev_pks))])
        graph_keys = sorted(srv_com.xpath(".//graph_key_list/graph_key/text()", smart_strings=False))
        graph_key_dict = self._create_graph_keys(graph_keys)
        self.log("found device pks: {}".format(", ".join(["{:d}".format(pk) for pk in dev_pks])))
        self.log("graph keys: {}".format(", ".join(graph_keys)))
        self.log("top level keys (== distinct graphs): {:d}; {}".format(
            len(graph_key_dict),
            ", ".join(sorted(graph_key_dict)),
            ))
        para_dict = {
            "size" : "400x200",
        }
        for para in srv_com.xpath(".//parameters", smart_strings=False)[0]:
            para_dict[para.tag] = para.text
        # cast to integer
        para_dict = dict([(key, int(value) if key in [] else value) for key, value in para_dict.iteritems()])
        for key in ["start_time", "end_time"]:
            # cast to datetime
            para_dict[key] = datetime.datetime.strptime(para_dict[key], "%Y-%m-%d %H:%M")
        para_dict["timeframe"] = abs((para_dict["end_time"] - para_dict["start_time"]).total_seconds())
        graph_size = para_dict["size"]
        graph_width, graph_height = [int(value) for value in graph_size.split("x")]
        self.log("width / height : {:d} x {:d}".format(graph_width, graph_height))
        graph_list = E.graph_list()
        multi_dev_mode = len(dev_pks) > 1
        for tlk in sorted(graph_key_dict):
            graph_keys = graph_key_dict[tlk]
            graph_name = "gfx_{}_{:d}.png".format(tlk, int(time.time()))
            abs_file_loc, rel_file_loc = (
                os.path.join(self.graph_root, graph_name),
                os.path.join("/{}/static/graphs/{}".format(settings.REL_SITE_ROOT, graph_name)),
            )
            dt_1970 = datetime.datetime(1970, 1, 1)
            rrd_args = [
                    abs_file_loc,
                    "-E",
                    "-Rlight",
                    "-G",
                    "normal",
                    "-P",
                    # "-nDEFAULT:8:",
                    "-w {:d}".format(graph_width),
                    "-h {:d}".format(graph_height),
                    "-a"
                    "PNG",
                    "--daemon",
                    "unix:/var/run/rrdcached.sock",
                    "-W init.at clustersoftware",
                    "--slope-mode",
                    "-cBACK#ffffff",
                    "--end",
                    # offset to fix UTC, FIXME
                    "{:d}".format((para_dict["end_time"] - dt_1970).total_seconds() - 1 * 3600),
                    "--start",
                    "{:d}".format((para_dict["start_time"] - dt_1970).total_seconds() - 1 * 3600),
                    graph_var(None, "", graph_width=graph_width).header_line,
            ]
            graph_var.init(self.colorizer)
            for graph_key in sorted(graph_keys):
                for cur_pk in dev_pks:
                    dev_vector = self.vector_dict[cur_pk]
                    if graph_key.startswith("pde:"):
                        # performance data from icinga
                        graph_pde = dev_vector.find(".//value[@name='{}']".format(graph_key))
                        if graph_pde is not None:
                            rrd_args.extend(graph_var(graph_pde, dev_dict[cur_pk], graph_width=graph_width).config)
                    else:
                        # machine vector entry
                        graph_mve = dev_vector.find(".//mve[@name='{}']".format(graph_key))
                        if graph_mve is not None:
                            rrd_args.extend(graph_var(graph_mve, dev_dict[cur_pk], graph_width=graph_width).config)
            if graph_var.var_idx:
                rrd_args.extend([
                    "--title",
                    "{} ({}, {})".format(
                        tlk,
                        logging_tools.get_plural("DEF", graph_var.var_idx),
                        logging_tools.get_diff_time_str(para_dict["timeframe"])),
                ])
                try:
                    draw_result = rrdtool.graphv(*rrd_args)
                except:
                    self.log("error creating graph: {}".format(process_tools.get_except_info()), logging_tools.LOG_LEVEL_ERROR)
                    if global_config["DEBUG"]:
                        pprint.pprint(rrd_args)
                else:
                    graph_list.append(
                        E.graph(
                            href=rel_file_loc,
                            **dict([(key, "{:d}".format(value) if type(value) in [int, long] else "{:.6f}".format(value)) for key, value in draw_result.iteritems()])
                        )
                    )
            else:
                self.log("no DEFs for graph_key_dict {}".format(tlk), logging_tools.LOG_LEVEL_ERROR)
        srv_com["graphs"] = graph_list
        # print srv_com.pretty_print()
        srv_com.set_result(
            "generated {}".format(logging_tools.get_plural("graph", len(graph_list))),
            server_command.SRV_REPLY_STATE_OK
        )
        self.send_pool_message("send_command", src_id, unicode(srv_com))

