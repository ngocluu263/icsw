#!/usr/bin/python-init -Ot
#
# Copyright (C) 2001-2009,2011-2015 Andreas Lang-Nevyjel, init.at
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

""" parser for the icsw service subcommand """

import argparse


class Parser(object):
    def link(self, sub_parser):
        self._add_status_parser(sub_parser)
        self._add_start_parser(sub_parser)
        self._add_stop_parser(sub_parser)
        self._add_restart_parser(sub_parser)
        self._add_debug_parser(sub_parser)

    def _add_status_parser(self, sub_parser):
        _srvc = sub_parser.add_parser("status", help="service status")
        _srvc.set_defaults(subcom="status", execute=self._execute)
        _srvc.add_argument("-i", dest="interactive", action="store_true", default=False, help="enable interactive mode [%(default)s]")
        _srvc.add_argument("-t", dest="thread", action="store_true", default=False, help="thread overview [%(default)s]")
        _srvc.add_argument("-s", dest="started", action="store_true", default=False, help="start info [%(default)s]")
        _srvc.add_argument("-p", dest="pid", action="store_true", default=False, help="show pid info [%(default)s]")
        _srvc.add_argument("-d", dest="database", action="store_true", default=False, help="show database info [%(default)s]")
        _srvc.add_argument("-m", dest="memory", action="store_true", default=False, help="memory consumption [%(default)s]")
        _srvc.add_argument("-a", dest="almost_all", action="store_true", default=False, help="almost all of the above, except start and DB info [%(default)s]")
        _srvc.add_argument("-A", dest="all", action="store_true", default=False, help="all of the above [%(default)s]")
        _srvc.add_argument("-v", dest="version", default=False, action="store_true", help="show version info [%(default)s]")
        self._add_iccs_sel(_srvc)
        # _srvc.add_argument("--mode", type=str, default="show", choices=["show", "stop", "start", "restart"], help="operation mode [%(default)s]")
        _srvc.add_argument("--failed", default=False, action="store_true", help="show only instances in failed state [%(default)s]")
        _srvc.add_argument("--every", default=0, type=int, help="check again every N seconds, only available for show [%(default)s]")
        return _srvc

    def _add_start_parser(self, sub_parser):
        _act = sub_parser.add_parser("start", help="start service")
        _act.set_defaults(subcom="start", execute=self._execute)
        _act.add_argument("-q", dest="quiet", default=False, action="store_true", help="be quiet [%(default)s]")
        self._add_iccs_sel(_act)

    def _add_debug_parser(self, sub_parser):
        _act = sub_parser.add_parser("debug", help="debug service")
        _act.set_defaults(subcom="debug", execute=self._execute)
        _act.add_argument("service", nargs=1, type=str, help="service to debug")

    def _add_stop_parser(self, sub_parser):
        _act = sub_parser.add_parser("stop", help="stop service")
        _act.set_defaults(subcom="stop", execute=self._execute)
        _act.add_argument("-q", dest="quiet", default=False, action="store_true", help="be quiet [%(default)s]")
        self._add_iccs_sel(_act)

    def _add_restart_parser(self, sub_parser):
        _act = sub_parser.add_parser("restart", help="restart service")
        _act.set_defaults(subcom="restart", execute=self._execute)
        _act.add_argument("-q", dest="quiet", default=False, action="store_true", help="be quiet [%(default)s]")
        self._add_iccs_sel(_act)

    def _add_iccs_sel(self, _parser):
        _parser.add_argument("service", nargs="*", type=str, help="list of services")

    def _execute(self, opt_ns):
        from .main import main
        # cleanup parser
        if hasattr(opt_ns, "instance"):
            if not opt_ns.instance and not opt_ns.client and not opt_ns.server and not opt_ns.system:
                opt_ns.instance = ["ALL"]
        if opt_ns.subcom == "status":
            if opt_ns.all or opt_ns.almost_all:
                opt_ns.thread = True
                opt_ns.memory = True
                opt_ns.version = True
            if opt_ns.all:
                opt_ns.pid = True
                opt_ns.started = True
        main(opt_ns)

    @staticmethod
    def get_default_ns():
        sub_parser = argparse.ArgumentParser().add_subparsers()
        def_ns = Parser()._add_status_parser(sub_parser).parse_args(["status"])
        def_ns.all = True
        def_ns.memory = True
        def_ns.database = True
        def_ns.pid = True
        def_ns.started = True
        def_ns.thread = True
        return def_ns
