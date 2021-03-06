# -*- coding: utf-8 -*-
#
# Copyright (C) 2015 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License Version 3 as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FTNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#
""" creates all defined fixtures """


from . import device_class_fixtures, srv_fixtures, graph_fixtures, dispatch_fixtures, \
    static_asset_fixtures, device_variable_fixtures


def add_fixtures(**kwargs):
    device_class_fixtures.add_fixtures(**kwargs)
    srv_fixtures.add_fixtures(**kwargs)
    graph_fixtures.add_fixtures(**kwargs)
    dispatch_fixtures.add_fixtures(**kwargs)
    static_asset_fixtures.add_fixtures(**kwargs)
    device_variable_fixtures.add_fixtures(**kwargs)
