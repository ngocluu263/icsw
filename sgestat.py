#!/usr/bin/python-init -Ot
#
# Copyright (C) 2001,2002,2003,2004,2005,2006,2007,2008,2012,2013 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of rms-tools
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
""" frontend for SGE qstat """

import argparse
import logging_tools
import os
import sge_tools
import sys
import time
import urwid

def check_environment():
    # set environment variables SGE_ROOT / SGE_CELL if not already set
    for v_name, v_src in [("SGE_ROOT", "/etc/sge_root"),
                          ("SGE_CELL", "/etc/sge_cell")]:
        if not os.environ.has_key(v_name):
            if os.path.isfile(v_src):
                os.environ[v_name] = open(v_src, "r").read().strip()
            else:
                print "error Cannot assign environment-variable '%s', exiting..." % (v_name)
                sys.exit(1)

def sjs(s_info, opt_dict):
    # print etree.tostring(sge_tools.build_running_list(s_info, opt_dict), pretty_print=True)
    ret_list = [time.ctime()]
    s_info.build_luts()
    # running jobs
    r_out_list = logging_tools.new_form_list()
    left_justified = set(["id", "task", "nodelist"])
    run_list = sge_tools.build_running_list(s_info, opt_dict)
    for run_job in run_list:
        r_out_list.append([logging_tools.form_entry(cur_el.text, header=cur_el.tag, left=cur_el.tag in left_justified) for cur_el in run_job])
    if len(run_list) == int(run_list.get("total")):
        ret_list.append("%s" % (logging_tools.get_plural("running job", len(run_list))))
    else:
        ret_list.append("%s, showing only %d (due to filter)" % (logging_tools.get_plural("running job", int(run_list.get("total"))),
                                                                 len(run_list)))
    if r_out_list:
        ret_list.append(str(r_out_list))
    # waiting jobs
    w_out_list = logging_tools.new_form_list()
    left_justified = set(["id", "task", "depends"])
    wait_list = sge_tools.build_waiting_list(s_info, opt_dict)
    for wait_job in wait_list:
        w_out_list.append([logging_tools.form_entry(cur_el.text, header=cur_el.tag, left=cur_el.tag in left_justified) for cur_el in wait_job])
    if len(wait_list) == int(wait_list.get("total")):
        ret_list.append("%s" % (logging_tools.get_plural("waiting job", len(wait_list))))
    else:
        ret_list.append("%s, showing only %d (due to filter)" % (logging_tools.get_plural("waiting job", int(wait_list.get("total"))),
                                                                 len(wait_list)))
    if w_out_list:
        ret_list.append(str(w_out_list))
    if opt_dict.interactive:
        return "\n".join(ret_list)
    else:
        print "\n".join(ret_list)

def sns(s_info, opt_dict):
    ret_list = [time.ctime()]
    s_info.build_luts()
    node_list = sge_tools.build_node_list(s_info, opt_dict)
    left_justified = set(["host", "queue", "queues", "node", "seqno", "state", "type", "complex", "pe_list", "userlists", "projects", "jobs"])
    short_dict = {"slots_used"     : "su",
                  "slots_reserved" : "sr",
                  "slots_total"    : "st"}
    out_list = logging_tools.new_form_list()
    for cur_node in node_list:
        out_list.append([logging_tools.form_entry(cur_el.text, header=short_dict.get(cur_el.tag, cur_el.tag), left=cur_el.tag in left_justified) for cur_el in cur_node])
    if out_list:
        ret_list.append(str(out_list))
    if opt_dict.interactive:
        return "\n".join(ret_list)
    else:
        print "\n".join(ret_list)

# following code from NH for interactive mode

class window(object):
    def __init__(self, **kwargs):
        self.start_time = time.time()
        self.callback = kwargs.get("callback", None)
        self.tree = kwargs.get("tree", None)
        self.cb_args = kwargs.get("args", [])
        self.top_text = urwid.Text(("banner", "Init cluster"), align="left")
        self.main_text = urwid.Text("Wait please...", align="left")
        self.bottom_text = urwid.Text("", align="left")
        if self.tree:
            self.set_question_text(self.tree.get_cur_text())
        else:
            self.set_question_text("q/Q - exit")
        palette = [
            ('banner', 'black', 'light gray', 'standout,underline'),
            ('streak', 'black', 'dark red', 'standout'),
            ('bg', 'white', 'dark blue'),
        ]
        urwid_map = urwid.AttrMap(
            urwid.Filler(
                urwid.Pile([
                    urwid.AttrMap(
                        self.top_text,
                        "streak"),
                    urwid.AttrMap(
                        self.main_text,
                        "banner"),
                    urwid.AttrMap(
                        self.bottom_text,
                        "streak")]),
                "top"),
            "banner")
        self.mainloop = urwid.MainLoop(urwid_map, palette, unhandled_input=self._handler_data)
        self._update_screen()
        self.mainloop.set_alarm_in(10, self._alarm_callback)
    def loop(self):
        self.mainloop.run()
    def _alarm_callback(self, main_loop, user_data):
        self._update_screen()
        self.mainloop.set_alarm_in(10, self._alarm_callback)
    # can be called from dt_tree
    def close(self):
        raise urwid.ExitMainLoop()
    def back_to_top(self):
        self.tree.back_to_top()
        self.set_question_text(self.tree.get_cur_text())
    def _handler_data(self, in_char):
        if type(in_char) in [str, unicode]:
            if self.tree:
                handled = self.tree.handle_input(in_char, self)
            else:
                if in_char.lower() == "q":
                    self.close()
                else:
                    handled = False
        else:
            handled = False
        if not handled:
            self._update_screen()
    def _update_screen(self):
        self.top_text.set_text(("streak", "time: %s" % (time.ctime())))
        self.main_text.set_text(("banner", str(self.get_data())))
    def set_question_text(self, in_text):
        self.bottom_text.set_text(("bg", in_text))
    def get_data(self):
        if self.callback:
            return unicode(self.callback(*self.cb_args))
        else:
            return "no data"

class dt_tree(object):
    def __init__(self, head_node):
        self.head_node = head_node
        self.head_node.set_tree(self)
        self.cur_node = self.head_node
    def back_to_top(self):
        self.cur_node = self.head_node
    def get_cur_text(self):
        return "%s (%s)" % (
            self.cur_node.question,
            "/".join(sorted(self.cur_node.get_triggers())))
    def handle_input(self, in_char, w_obj):
        cur_node = self.cur_node
        cur_triggers = cur_node.get_triggers()
        if in_char.lower() in cur_triggers:
            handled = True
            next_node = cur_node.follow_edge(in_char.lower())
            if next_node.action:
                getattr(w_obj, next_node.action)()
            else:
                self.cur_node = next_node
                w_obj.set_question_text(self.get_cur_text())
        else:
            handled = False
        return handled

class dt_node(object):
    def __init__(self, question, action=None, edges=None):
        self.question = question
        self.edges = []
        self.__edge_dict = {}
        self.action = action
        for edge in (edges or []):
            self.add_edge(edge)
    def add_edge(self, edge):
        edge.target.prev_node = self
        self.edges.append(edge)
        self.__edge_dict[edge.trigger.lower()] = edge
    def set_tree(self, tree):
        self.tree = tree
        for edge in self.edges:
            edge.target.set_tree(tree)
    def get_triggers(self):
        return [edge.trigger.lower() for edge in self.edges]
    def follow_edge(self, trigger):
        sub_edge = self.__edge_dict[trigger.lower()]
        return sub_edge.target

class dt_edge(object):
    def __init__(self, trigger, target=None):
        self.trigger = trigger
        self.target = target

class my_opt_parser(argparse.ArgumentParser):
    def __init__(self, run_mode):
        argparse.ArgumentParser.__init__(self)
        if run_mode in ["sjs", "sns"]:
            self.add_argument("--direct", dest="direct", default=False, action="store_true", help="do not connect sge-server [%(default)s]")
            self.add_argument("-m", dest="show_memory", help="show memory information [%(default)s]", action="store_true", default=False)
            self.add_argument("-s", dest="suppress_status", help="suppress status [%(default)s]", action="store_true", default=False)
            self.add_argument("-S", dest="long_status", help="show long status [%(default)s]", action="store_true", default=False)
            self.add_argument("-T", dest="show_long_type", help="show long queue type [%(default)s]", action="store_true", default=False)
            self.add_argument("-a", dest="show_acl", help="show access control info [%(default)s]", action="store_true", default=False)
            self.add_argument("-q", dest="show_seq", help="show sequence number [%(default)s]", action="store_true", default=False)
            self.add_argument("-u", dest="users", type=str, help="show only jobs of user [%(default)s]", action="append", default=[])
            self.add_argument("-c", dest="complexes", type=str, help="show only jobs with the given complexes [%(default)s]", action="append", default=[])
            self.add_argument("-e", dest="show_nonstd", help="show nonstandard queues, specifiy twice to suppress alarm queues [%(default)s]", action="count", default=0)
            self.add_argument("-i", dest="interactive", help="show info interactive", action="store_true", default=False)
            self.add_argument("--never-direct", dest="never_direct", default=False, action="store_true", help="always connect sge-server [%(default)s]")
        if run_mode == "sns":
            self.add_argument("-t", dest="show_type", help="show queue type [%(default)s]", action="store_true", default=False)
            self.add_argument("-C", dest="show_complexes", help="show complexes [%(default)s]", action="store_true", default=False)
            self.add_argument("-n", dest="suppress_empty", help="show only nonempty queues [%(default)s]", action="store_true", default=False)
            self.add_argument("-N", dest="node_sort", help="sort according to the nodename [%(default)s]", action="store_true", default=False)
            self.add_argument("--pe", dest="show_pe", help="show pe information [%(default)s]", action="store_true", default=False)
            self.add_argument("-J", dest="merge_node_queue", help="merge node with queues in output [%(default)s]", action="store_true", default=False)
        elif run_mode == "sjs":
            # self.add_argument("-s", dest="no_status", help="suppress status [%(default)s]", action="store_true", default=False)
            self.add_argument("--valid", dest="only_valid_waiting", help="show only valid waiting jobs [%(default)s]", action="store_true", default=False)
            self.add_argument("-n", dest="suppress_nodelist", help="suppress nodelist [%(default)s]", action="store_true", default=False)
            self.add_argument("-t", dest="suppress_times", help="suppress the display of start/run/left times [%(default)s]", action="store_true", default=False)
            self.add_argument("--stdoe", dest="show_stdoutstderr", help="supress display of stdout / stderr [%(default)s]", action="store_false", default=True)
        self.add_argument("-v", dest="verbose", help="set verbose mode [%(default)s]", action="store_true", default=False)

def log_com(what, level):
    print "%s [%s] %s" % (time.ctime(),
                          logging_tools.get_log_level_str(level),
                          what)

def get_server():
    srv_name = "localhost"
    if os.environ.has_key("SGE_SERVER"):
        srv_name = os.environ["SGE_SERVER"]
    else:
        for f_name in ["/etc/sge_relayer", "/etc/sge_server"]:
            if os.path.isfile(f_name):
                srv_name = file(f_name, "r").read().split()[0]
                break
    return srv_name

def main():
    c_time = time.time()
    check_environment()
    run_mode = {
        "sgejobstat"     : "sjs",
        "sgenodestat"    : "sns",
        "sjs"            : "sjs",
        "sns"            : "sns",
        }.get(os.path.basename(sys.argv[0]), "sjs")
    options = my_opt_parser(run_mode).parse_args()
    act_si = sge_tools.sge_info(update_pref={"qhost"     : [],
                                             "complexes" : ["server"],
                                             "hostgroup" : ["server"],
                                             "qstat"     : [],
                                             "queueconf" : ["server"]},
                                verbose=options.verbose,
                                log_command=log_com,
                                server=get_server(),
                                always_direct=options.direct,
                                never_direct=options.never_direct)
    s_time = time.time()
    if run_mode == "sjs":
        if options.interactive:
            window(callback=sjs,
                   args=(act_si, options),
                   tree=dt_tree(
                       dt_node(
                           "press p to print and q to exit",
                           edges=[
                               dt_edge(
                                   "p",
                                   dt_node(
                                       "Are you sure",
                                       edges=[
                                           dt_edge("y", dt_node(None, action="back_to_top")),
                                           dt_edge("n", dt_node(None, action="back_to_top"))])),
                               dt_edge(
                                   "q",
                                   dt_node(
                                       None,
                                       action="close"))])
                       )).loop()
        else:
            sjs(act_si, options)
    elif run_mode == "sns":
        if options.interactive:
            window(callback=sns, args=(act_si, options),
                   tree=dt_tree(
                       dt_node(
                           "press q to exit",
                           edges=[
                               dt_edge(
                                   "q",
                                   dt_node(
                                       None,
                                       action="close"))])
                       )).loop()
        else:
            sns(act_si, options)
    else:
        print "Unknown runmode %s" % (run_mode)
    e_time = time.time()
    if not options.interactive:
        print "took %s / %s" % (
            logging_tools.get_diff_time_str(s_time - c_time),
            logging_tools.get_diff_time_str(e_time - s_time))

if __name__ == "__main__":
    main()
