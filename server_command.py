#!/opt/python-init/bin/python -Ot
#
# Copyright (C) 2001,2002,2003,2004,2005,2006,2007,2008,2011,2012,2013 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
# 
# This file is part of python-modules-base
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; version 2 of the License
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
""" server command structure definitions """

import sys
import marshal
import socket
import time
import re
import os
from lxml import etree
from lxml.builder import E, ElementMaker
import base64
import bz2
import datetime
try:
    import cPickle as pickle
except ImportError:
    import pickle
import logging_tools

XML_NS = "http://www.initat.org/lxml/ns"

def net_to_sys(in_val):
    try:
        result = pickle.loads(in_val)
    except:
        try:
            result = marshal.loads(in_val)
        except:
            raise ValueError
    return result

def sys_to_net(in_val):
    return pickle.dumps(in_val)

SRV_REPLY_STATE_OK       = 0
SRV_REPLY_STATE_WARN     = 1
SRV_REPLY_STATE_ERROR    = 2
SRV_REPLY_STATE_CRITICAL = 3
SRV_REPLY_STATE_UNSET    = 4

def srv_reply_to_log_level(srv_reply_state):
    return {
        SRV_REPLY_STATE_OK    : logging_tools.LOG_LEVEL_OK,
        SRV_REPLY_STATE_WARN  : logging_tools.LOG_LEVEL_WARN,
        SRV_REPLY_STATE_ERROR : logging_tools.LOG_LEVEL_ERROR,
    }.get(srv_reply_state, logging_tools.LOG_LEVEL_ERROR)

def compress(in_str, **kwargs):
    if kwargs.get("marshal", False):
        in_str = marshal.dumps(in_str)
    elif kwargs.get("pickle", False):
        in_str = pickle.dumps(in_str)
    return base64.b64encode(bz2.compress(in_str))

def decompress(in_str, **kwargs):
    ret_struct = bz2.decompress(base64.b64decode(in_str))
    if kwargs.get("marshal", False):
        ret_struct = marshal.loads(ret_struct)
    elif kwargs.get("pickle", False):
        ret_struct = pickle.loads(ret_struct)
    return ret_struct

class srv_command(object):
    srvc_open = 0
    def __init__(self, **kwargs):
        srv_command.srvc_open += 1
        self.__builder = ElementMaker(namespace=XML_NS)
        if "source" in kwargs:
            #print len(kwargs["source"])
            if type(kwargs["source"]) in [str, unicode]:
                self.__tree = etree.fromstring(kwargs["source"])
            else:
                self.__tree = kwargs["source"]
        else:
            self.__tree = self.__builder.ics_batch(
                self.__builder.source(host=os.uname()[1],
                                      pid="%d" % (os.getpid())),
                self.__builder.command(kwargs.pop("command", "not set")),
                self.__builder.identity(kwargs.pop("identity", "not set")),
                # set srv_command version
                srvc_version="%d" % (kwargs.pop("srvc_version", 1)))
            for key, value in kwargs.iteritems():
                self[key] = value
    def xpath(self, start_el=None, *args, **kwargs):
        if "namespace" not in kwargs:
            kwargs["namespaces"] = {"ns" : XML_NS}
        if start_el is None:
            start_el = self.__tree
        return start_el.xpath(*args, **kwargs)
    def set_result(self, ret_str, level=SRV_REPLY_STATE_OK):
        if "result" not in self:
            self["result"] = None
        self["result"].attrib.update({
            "reply" : ret_str,
            "state" : "%d" % (level)})
    def builder(self, tag_name, *args, **kwargs):
        if type(tag_name) == type(0):
            tag_name = "__int__%d" % (tag_name)
        if tag_name.count("/"):
            tag_name = tag_name.replace("/", "__slash__")
            kwargs["escape_slash"] = "1"
        if tag_name.count("@"):
            tag_name = tag_name.replace("@", "__atsign__")
            kwargs["escape_atsign"] = "1"
        if tag_name[0].isdigit():
            tag_name = "__fdigit__%s" % (tag_name)
            kwargs["first_digit"] = "1"
        if tag_name.count(":"):
            tag_name = tag_name.replace(":", "__colon__")
            kwargs["escape_colon"] = "1"
        # escape special chars
        for s_char in "[] ":
            tag_name = tag_name.replace(s_char, "_0x0%x_" % (ord(s_char)))
        return getattr(self.__builder, tag_name)(*args, **kwargs)
    def _interpret_tag(self, el, tag_name):
        iso_re = re.compile("^(?P<pre>.*)_0x0(?P<code>[^_]\S+)_(?P<post>.*)")
        if tag_name.startswith("{http"):
            tag_name = tag_name.split("}", 1)[1]
        if "escape_slash" in el.attrib:
            tag_name = tag_name.replace("__slash__", "/")
        if "escape_atsign" in el.attrib:
            tag_name = tag_name.replace("__atsign__", "@")
        if "first_digit" in el.attrib:
            tag_name = tag_name.replace("__fdigit__", "")
        if "escape_colon" in el.attrib:
            tag_name = tag_name.replace("__colon__", ":")
        if tag_name.startswith("__int__"):
            tag_name = int(tag_name[7:])
        else:
            while True:
                cur_match = iso_re.match(tag_name)
                if cur_match:
                    tag_name = "%s%s%s" % (cur_match.group("pre"),
                                           chr(int(cur_match.group("code"), 16)),
                                           cur_match.group("post"))
                else:
                    break
        return tag_name
    @property
    def tree(self):
        return self.__tree
    def get_int(self, key):
        return int(self[key].text)
    def __contains__(self, key):
        xpath_str = "/ns:ics_batch/%s" % ("/".join(["ns:%s" % (sub_arg) for sub_arg in key.split(":")]))
        xpath_res = self.__tree.xpath(xpath_str, namespaces={"ns" : XML_NS})
        return True if len(xpath_res) else False
    def get_element(self, key):
        xpath_str = "/ns:ics_batch/%s" % ("/".join(["ns:%s" % (sub_arg) for sub_arg in key.split(":")]))
        return self.__tree.xpath(xpath_str, namespaces={"ns" : XML_NS})
    def __getitem__(self, key):
        if key.startswith("*"):
            interpret = True
            key = key[1:]
        else:
            interpret = False
        xpath_res = self.get_element(key)
        if len(xpath_res) == 1:
            xpath_res = xpath_res[0]
            if xpath_res.attrib.get("type") == "dict":
                return self._interpret_el(xpath_res)
            else:
                if interpret:
                    return self._interpret_el(xpath_res)
                else:
                    return xpath_res
        elif len(xpath_res) > 1:
            if interpret:
                return [self._interpret_el(cur_res) for cur_res in xpath_res]
            else:
                return [cur_res for cur_res in xpath_res]
        else:
            raise KeyError, "key %s not found in srv_command" % (key)
    def _to_unicode(self, value):
        if type(value) == bool:
            return ("True" if value else "False", "bool")
        elif type(value) in [type(0), type(0L)]:
            return ("%d" % (value), "int")
        else:
            return (value, "str")
    def __setitem__(self, key, value):
        cur_element = self._create_element(key)
        if etree.iselement(value):
            cur_element.append(value)
        else:
            self._element(value, cur_element)
    def delete_subtree(self, key):
        xpath_str = "/ns:ics_batch/%s" % ("/".join(["ns:%s" % (sub_arg) for sub_arg in key.split(":")]))
        for result in self.__tree.xpath(xpath_str, namespaces={"ns" : XML_NS}):
            result.getparent().remove(result)
    def _element(self, value, cur_element=None):
        if cur_element is None:
            cur_element = self.builder("value")
        if type(value) in [type(""), type(u"")]:
            cur_element.text = value
            cur_element.attrib["type"] = "str"
        elif type(value) in [type(0), type(0L)]:
            cur_element.text = "%d" % (value)
            cur_element.attrib["type"] = "int"
        elif type(value) in [type(0.0)]:
            cur_element.text = "%f" % (value)
            cur_element.attrib["type"] = "float"
        elif type(value) == type(None):
            cur_element.text = None
            cur_element.attrib["type"] = "none"
        elif type(value) == datetime.date:
            cur_element.text = value.isoformat()
            cur_element.attrib["type"] = "date"
        elif type(value) == datetime.datetime:
            cur_element.text = value.isoformat()
            cur_element.attrib["type"] = "datetime"
        elif type(value) == bool:
            cur_element.text = str(value)
            cur_element.attrib["type"] = "bool"
        elif type(value) == dict:
            cur_element.attrib["type"] = "dict"
            for sub_key, sub_value in value.iteritems():
                sub_el = self._element(sub_value, self.builder(sub_key))
                sub_el.attrib["dict_key"] = "__int__%d" % (sub_key) if type(sub_key) in [type(0), type(0L)] else sub_key
                cur_element.append(sub_el)
        elif type(value) == list:
            cur_element.attrib["type"] = "list"
            for sub_value in value:
                sub_el = self._element(sub_value)
                cur_element.append(sub_el)
        elif type(value) == tuple:
            cur_element.attrib["type"] = "tuple"
            for sub_value in value:
                sub_el = self._element(sub_value)
                cur_element.append(sub_el)
        else:
            raise ValueError, "_element: unknown value type '%s'" % (type(value))
        return cur_element
##    def _escape_key(self, key_str):
##        return key_str.replace("/", "r")
    def _escape_key(self, key_str):
        return key_str.replace("/", "__slash__").replace("@", "__atsign__")
    def _create_element(self, key):
        """ creates all element(s) down to key.split(":") """
        xpath_str = "/ns:ics_batch"
        cur_element = self.__tree.xpath(xpath_str, namespaces={"ns" : XML_NS})[0]
        for cur_key in key.split(":"):
            xpath_str = "%s/ns:%s" % (xpath_str, self._escape_key(cur_key))
            full_key = "{%s}%s" % (XML_NS, self._escape_key(cur_key))
            sub_el = cur_element.find("./%s" % (full_key))
            if sub_el is not None:
                cur_element = sub_el
            else:
                sub_el = self.builder(cur_key)#getattr(self.__builder, cur_key)()
                cur_element.append(sub_el)
            cur_element = sub_el
        return cur_element
    def _interpret_el(self, top_el):
        value, el_type = (top_el.text, top_el.attrib.get("type", None))
        if  el_type == "dict":
            result = {}
            for el in top_el:
                if "dict_key" in el.attrib:
                    key = self._interpret_tag(el, el.attrib["dict_key"])
                else:
                    key = self._interpret_tag(el, el.tag.split("}", 1)[1])
                result[key] = self._interpret_el(el)
        elif el_type == "list":
            result = []
            for el in top_el:
                result.append(self._interpret_el(el))
        elif el_type == "tuple":
            result = []
            for el in top_el:
                result.append(self._interpret_el(el))
            result = tuple(result)
        else:
            if el_type == "int":
                value = int(value)
            elif el_type == "bool":
                value = bool(value)
            elif el_type == "date":
                value_dt = datetime.datetime.strptime(value, "%Y-%m-%d")
                value = datetime.date(value_dt.year, value_dt.month, value_dt.day)
            elif el_type == "datetime":
                value = datetime.datetime.strptime(value, "%Y-%m-%dT%H:%M:%S")
            elif el_type == "float":
                value = float(value)
            elif el_type == "str":
                value = value or u""
            return value
        return result
    def get(self, key, def_value):
        xpath_str = ".//%s" % ("/".join(["ns:%s" % (sub_arg) for sub_arg in key.split(":")]))
        xpath_res = self.__tree.xpath(xpath_str, namespaces={"ns" : XML_NS})
        if len(xpath_res) == 1:
            return xpath_res[0].text
        elif len(xpath_res) > 1:
            return [cur_res.text for cur_res in xpath_res]
        else:
            return def_value
    def update_source(self):
        self.__tree.xpath(".//ns:source", namespaces={"ns" : XML_NS})[0].attrib.update({
            "host" : os.uname()[1],
            "pid" : "%d" % (os.getpid())})
    def pretty_print(self):
        return etree.tostring(self.__tree, encoding=unicode, pretty_print=True)
    def __unicode__(self):
        return etree.tostring(self.__tree, encoding=unicode)
    def tostring(self, **kwargs):
        return etree.tostring(self.__tree, **kwargs)
    def get_log_tuple(self):
        # returns the reply / state attribute, mapped to logging_tool levels
        res_node = self.xpath(None, ".//ns:result")
        if len(res_node):
            res_node = res_node[0]
            ret_str, ret_state = res_node.attrib["reply"], int(res_node.attrib["state"])
            ret_state = {
                SRV_REPLY_STATE_OK       : logging_tools.LOG_LEVEL_OK,
                SRV_REPLY_STATE_WARN     : logging_tools.LOG_LEVEL_WARN,
                SRV_REPLY_STATE_ERROR    : logging_tools.LOG_LEVEL_ERROR,
                SRV_REPLY_STATE_CRITICAL : logging_tools.LOG_LEVEL_CRITICAL}.get(ret_state, logging_tools.LOG_LEVEL_CRITICAL)
        else:
            ret_str, ret_state = ("no result element found", logging_tools.LOG_LEVEL_CRITICAL)
        return ret_str, ret_state
    def __del__(self):
        srv_command.srvc_open -= 1
        
class command_template(object):
    def __init__(self, *rest_vals, **rest_dict):
        self.invalidate_buffer()
        self.init_time = time.time()
        self.__get_calls = dict([(k, getattr(self, "get_%s" % (k))) for k in self.key_list])
        self.__set_calls = dict([(k, getattr(self, "set_%s" % (k))) for k in self.key_list])
        if rest_dict:
            pass
        elif rest_vals:
            rest_dict = net_to_sys(rest_vals[0])
        else:
            rest_dict = {}
        for what in self.key_list:
            if what in rest_dict:
                self.__set_calls[what](rest_dict[what])
            else:
                self.__set_calls[what]()
        wrong_keys = [x for x in rest_dict.keys() if x not in self.key_list]
        if wrong_keys:
            raise IndexError, "undefined keys for command_template: %s" % (",".join(wrong_keys))
    def get_init_time(self):
        return self.init_time
    def create_string(self):
        if not self.buffer:
            self.buffer = sys_to_net(dict([(k, self.__get_calls[k]()) for k in self.key_list]))
        return self.buffer
    def invalidate_buffer(self):
        self.buffer = None
    def __nonzero__(self):
        return True
    def __len__(self):
        return len(self.create_string())
    def __repr__(self):
        return self.create_string()
    
class server_command(command_template):
    def __init__(self, *rest_vals, **rest_dict):
        # nodes ........... list of nodes
        # uid/gid ......... uid/gid of caller
        # host ............ calling host
        # key ............. key for server-internal commands
        # queue ........... queue for server-internal commands
        # option_dict ..... option_dict for command
        # node_commands ... node-specific command-dict
        self.key_list = ["command", "nodes", "uid", "gid", "host", "key", "option_dict", "compat", "queue", "node_commands"]
        command_template.__init__(self, *rest_vals, **rest_dict)
    def set_nodes(self, nodes=[]):
        self.nodes = nodes
    def get_nodes(self):
        return self.nodes
    def set_node_commands(self, node_commands={}):
        self.node_commands = node_commands
    def get_node_commands(self):
        return self.node_commands
    def set_node_command(self, node, command=""):
        self.node_commands[node] = command
    def get_node_command(self, node, default=""):
        return self.node_commands.get(node,"")
    def set_key(self, key = 0):
        self.key = key
    def get_key(self):
        return self.key
    def set_option_dict(self, option_dict={}):
        self.option_dict = option_dict
    def get_option_dict(self):
        return self.option_dict
    def get_option_dict_info(self):
        return ", ".join(["%s:%s" % (k, str(v)) for k, v in self.option_dict.iteritems()])
    def set_compat(self, compat=0):
        self.compat = compat
    def get_compat(self):
        return self.compat
    def set_uid(self, uid=0):
        self.uid = uid
    def get_uid(self):
        return self.uid
    def set_gid(self, gid=0):
        self.gid = gid
    def get_gid(self):
        return self.gid
    def set_host(self, host=socket.gethostname()):
        self.host = host
    def get_host(self):
        return self.host
    def set_queue(self, queue=None):
        self.queue = queue
    def get_queue(self):
        return self.queue
    def set_command(self, command="<not set>"):
        self.command = command
    def get_command(self):
        return self.command
    
class server_reply(command_template):
    def __init__(self, *rest_vals, **rest_dict):
        # node_results: on string per node
        # node_dicts: on dict per node
        self.key_list = ["node_results", "result", "state", "key", "node_dicts", "option_dict"]
        command_template.__init__(self, *rest_vals, **rest_dict)
    def set_node_results(self, node_results={}):
        self.node_results = node_results
    def get_node_results(self):
        return self.node_results
    def set_node_result(self, node, result):
        self.node_results[node] = result
    def get_node_result(self, node):
        return self.node_results[node]
    def set_node_dicts(self, node_dicts={}):
        self.node_dicts = node_dicts
    def get_node_dicts(self):
        return self.node_dicts
    def set_node_dict(self, node, in_dict):
        self.node_dicts[node] = in_dict
    def get_node_dict(self, node):
        return self.node_dicts[node]
    def set_result(self, result="not set"):
        self.result = result
    def get_result(self):
        return self.result
    def set_state(self, state=SRV_REPLY_STATE_UNSET):
        if type(state) != type(0):
            raise ValueError, "state '%s' is not of type Integer" % (state)
        self.state = state
    def get_state(self):
        return self.state
    def set_state_and_result(self, state=SRV_REPLY_STATE_UNSET, result="not set"):
        self.set_state(state)
        self.set_result(result)
    def get_state_and_result(self):
        return self.get_state(), self.get_result()
    def set_option_dict(self, option_dict={}):
        self.option_dict = option_dict
    def get_option_dict(self):
        return self.option_dict
    def get_option_dict_info(self):
        return ", ".join(["%s:%s" % (k, str(v)) for k, v in self.option_dict.iteritems()])
    def set_ok_result(self, result):
        self.set_state_and_result(SRV_REPLY_STATE_OK, result)
    def set_warn_result(self, result):
        self.set_state_and_result(SRV_REPLY_STATE_WARN, result)
    def set_error_result(self, result):
        self.set_state_and_result(SRV_REPLY_STATE_ERROR, result)
    def set_critical_result(self, result):
        self.set_state_and_result(SRV_REPLY_STATE_CRITICAL, result)
    def set_key(self, key=0):
        self.key = key
    def get_key(self):
        return self.key
    
def main():
    print "Loadable module, exiting..."
    sys.exit(0)
