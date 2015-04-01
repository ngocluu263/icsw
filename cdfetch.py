#!/usr/bin/python-init -Ot
#
# Copyright (c) 2013-2014 Andreas Lang-Nevyjel, lang-nevyjel@init.at
#
# this file is part of collectd-init
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
""" connect to a given collectd-server and fetch some data """

from initat.host_monitoring.hm_classes import mvect_entry
from lxml import etree # @UnresolvedImports
import argparse
import json
import logging_tools
import memcache
import process_tools
import server_command
import re
import sys
import time
import zmq

class base_com(object):
    def __init__(self, options, *args):
        self.options = options
        self.args = args
        if self.options.mode == "tcp":
            srv_com = server_command.srv_command(command=self.Meta.command)
            srv_com["identity"] = process_tools.zmq_identity_str(self.options.identity_string)
            for arg_index, arg in enumerate(args):
                if self.options.verbose:
                    print " arg {:d}: {}".format(arg_index, arg)
                    srv_com["arguments:arg{:d}".format(arg_index)] = arg
            srv_com["arg_list"] = " ".join(args)
            srv_com["host_filter"] = self.options.host_filter
            srv_com["key_filter"] = self.options.key_filter
            self.srv_com = srv_com #
        self.ret_state = 1
    def __getitem__(self, key):
        return self.srv_com[key]
    def __unicode__(self):
        return unicode(self.srv_com)
    def get_mc(self):
        return memcache.Client([self.options.mc_addr])
    def compile_re(self, re_str):
        try:
            cur_re = re.compile(re_str)
        except:
            print("error transforming '{}' to re".format(re_str))
            cur_re = re.compile(".*")
        return cur_re
    def send_and_receive(self, client):
        # tcp (0MQ) mode
        conn_str = "tcp://{}:{:d}".format(self.options.host, self.options.port)
        if self.options.verbose:
            print "Identity_string is '{}', connection_string is '{}'".format(
                self.srv_com["identity"].text,
                conn_str)
        client.connect(conn_str)
        s_time = time.time()

        client.send_unicode(unicode(self.srv_com))
        if self.options.verbose:
            print self.srv_com.pretty_print()
        r_client = client
        if r_client.poll(self.options.timeout * 1000):
            recv_str = r_client.recv()
            if r_client.getsockopt(zmq.RCVMORE):
                recv_id = recv_str
                recv_str = r_client.recv()
            else:
                recv_id = ""
            self.receive_tuple = (recv_id, recv_str)
            timeout = False
        else:
            print "error timeout ({:.2f} > {:d})".format(time.time() - s_time, self.options.timeout)
            timeout = True
        e_time = time.time()
        if self.options.verbose:
            if timeout:
                print "communication took {}".format(
                    logging_tools.get_diff_time_str(e_time - s_time),
                )
            else:
                print "communication took {}, received {:d} bytes".format(
                    logging_tools.get_diff_time_str(e_time - s_time),
                    len(recv_str),
                )
        return True if not timeout else False
    def interpret_tcp(self):
        recv_id, recv_str = self.receive_tuple
        try:
            srv_reply = server_command.srv_command(source=recv_str)
        except:
            print "cannot interpret reply: {}".format(process_tools.get_except_info())
            print "reply was: {}".format(recv_str)
            self.ret_state = 1
        else:
            if self.options.verbose:
                print
                print "XML response (id: '{}'):".format(recv_id)
                print
                print srv_reply.pretty_print()
                print
            if "result" in srv_reply:
                if hasattr(self, "_interpret"):
                    # default value: everything OK
                    self.ret_state = 0
                    self._interpret(srv_reply)
                else:
                    print srv_reply["result"].attrib["reply"]
                    self.ret_state = int(srv_reply["result"].attrib["state"])
            else:
                print "no result tag found in reply"
                self.ret_state = 2

class host_list_com(base_com):
    class Meta:
        command = "host_list"
    def fetch(self):
        _mc = self.get_mc()
        hlist = json.loads(_mc.get("cc_hc_list"))
        h_re = self.compile_re(self.options.host_filter)
        v_dict = {key : value for key, value in hlist.iteritems() if h_re.match(value[1])}
        print("{} found : {}").format(logging_tools.get_plural("host", len(v_dict)), ", ".join(sorted([value[1] for value in v_dict.itervalues()])))
        for key, value in v_dict.iteritems():
            print "{:30s} ({}) : last updated {}".format(value[1], key, time.ctime(value[0]))
        # print v_list
    def _interpret(self, srv_com):
        h_list = srv_com.xpath(".//host_list", smart_strings=False)
        if len(h_list):
            h_list = h_list[0]
            print "got result for {}:".format(logging_tools.get_plural("host", int(h_list.attrib["entries"])))
            for host in h_list:
                print "{:<30s} ({:<40s}) : {:4d} keys, last update {}, store_to_disk is {}".format(
                    host.attrib["name"],
                    host.attrib["uuid"],
                    int(host.attrib["keys"]),
                    time.ctime(int(host.attrib["last_update"])),
                    "enabled" if int(host.get("store_to_disk", "1")) else "disabled",
                    )
            pass
        else:
            print "No host_list found in result"
            self.ret_state = 1

class key_list_com(base_com):
    class Meta:
        command = "key_list"
    def fetch(self):
        _mc = self.get_mc()
        hlist = json.loads(_mc.get("cc_hc_list"))
        h_re = self.compile_re(self.options.host_filter)
        v_re = self.compile_re(self.options.key_filter)
        v_dict = {key : value for key, value in hlist.iteritems() if h_re.match(value[1])}
        print("{} found : {}").format(logging_tools.get_plural("host", len(v_dict)), ", ".join(sorted([value[1] for value in v_dict.itervalues()])))
        k_dict = {key : json.loads(_mc.get("cc_hc_{}".format(key))) for key in v_dict.iterkeys()}
        for key, value in v_dict.iteritems():
            print "{:30s} ({}) : last updated {}".format(value[1], key, time.ctime(value[0]))
        out_f = logging_tools.new_form_list()
        for h_uuid, h_struct in k_dict.iteritems():
            num_key = 0
            for entry in sorted(h_struct):
                if v_re.match(entry[1]):
                    num_key += 1
                    if entry[0] == 0:
                        # simple format
                        cur_mv = mvect_entry(entry[1], info=entry[2], unit=entry[3], v_type=entry[4], value=entry[5], base=entry[6], factor=entry[7])
                    out_f.append([logging_tools.form_entry(v_dict[h_uuid][1], header="device")] + cur_mv.get_form_entry(num_key))
        print unicode(out_f)
        # print v_list
    def _interpret(self, srv_com):
        h_list = srv_com.xpath(".//host_list", smart_strings=False)
        if len(h_list):
            h_list = h_list[0]
            out_f = logging_tools.new_form_list()
            print "got result for {}:".format(logging_tools.get_plural("host", int(h_list.attrib["entries"])))
            for host in h_list:
                print "{:<30s} ({:<40s}) : {:4d} keys, last update {}".format(
                    host.attrib["name"],
                    host.attrib["uuid"],
                    int(host.attrib["keys"]),
                    time.ctime(int(host.attrib["last_update"]))
                    )
                for num_key, key_el in enumerate(host):
                    cur_mv = mvect_entry(key_el.attrib.pop("name"), info="", **key_el.attrib)
                    out_f.append([logging_tools.form_entry(host.attrib["name"], header="device")] + cur_mv.get_form_entry(num_key + 1))
            print unicode(out_f)
        else:
            print "No host_list found in result"
            self.ret_state = 1

def main():
    parser = argparse.ArgumentParser("query the datastore of collectd servers")
    com_list = [key[:-4] for key in globals().keys() if key.endswith("_com") if key not in ["base_com"]]
    parser.add_argument("arguments", nargs="+", help="additional arguments, first one is command (one of {})".format(
        ", ".join(sorted(com_list))))
    parser.add_argument("-t", help="set timeout [%(default)d]", default=10, type=int, dest="timeout")
    parser.add_argument("-p", help="port [%(default)d]", default=8008, dest="port", type=int)
    parser.add_argument("-H", help="host [%(default)s] or server", default="localhost", dest="host")
    parser.add_argument("-v", help="verbose mode [%(default)s]", default=False, dest="verbose", action="store_true")
    parser.add_argument("-i", help="set identity substring [%(default)s]", type=str, default="cdf", dest="identity_string")
    parser.add_argument("--host-filter", help="set filter for host name [%(default)s]", type=str, default=".*", dest="host_filter")
    parser.add_argument("--key-filter", help="set filter for key name [%(default)s]", type=str, default=".*", dest="key_filter")
    parser.add_argument("--mode", type=str, default="tcp", choices=["tcp", "memcached"], help="set access type [%(default)s]")
    parser.add_argument("--mc-addr", type=str, default="127.0.0.1:11211", help="address of memcached [%(default)s]")
    # parser.add_argument("arguments", nargs="+", help="additional arguments")
    ret_state = 1
    args, other_args = parser.parse_known_args()
    # print args.arguments, other_args
    command = args.arguments.pop(0)
    other_args = args.arguments + other_args
    if command in com_list:
        try:
            cur_com = globals()["{}_com".format(command)](args, *other_args)
        except:
            print "error init '{}': {}".format(command, process_tools.get_except_info())
            sys.exit(ret_state)
    else:
        print "Unknown command '{}'".format(command)
        sys.exit(ret_state)
    if args.mode == "tcp":
        zmq_context = zmq.Context(1)
        client = zmq_context.socket(zmq.DEALER) # if not args.split else zmq.PUB) # ROUTER)#DEALER)
        client.setsockopt(zmq.IDENTITY, cur_com["identity"].text)
        client.setsockopt(zmq.LINGER, args.timeout)
        was_ok = cur_com.send_and_receive(client)
        if was_ok:
            cur_com.interpret_tcp()
        client.close()
        zmq_context.term()
    else:
        cur_com.fetch()
    sys.exit(cur_com.ret_state)

if __name__ == "__main__":
    main()
