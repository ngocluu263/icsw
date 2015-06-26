# Copyright (C) 2014-2015 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# this file is part of init-snmp-libs
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
""" SNMP handler instances """

from ...functions import simplify_dict
from ...snmp_struct import ResultNode, snmp_ip
from ..base import SNMPHandler

try:
    from django.db.models import Q
    from initat.cluster.backbone.models import network, netdevice, domain_tree_node, \
        network_type, net_ip
except:
    pass


class handler(SNMPHandler):
    class Meta:
        # oids = ["generic.netip"]
        description = "network settings (IP addresses)"
        vendor_name = "generic"
        name = "netip"
        tl_oids = ["1.3.6.1.2.1.4.20"]
        initial = True

    def update(self, dev, scheme, result_dict, oid_list, flags):
        # ip dict
        _ip_dict = {key: snmp_ip(value) for key, value in simplify_dict(result_dict["1.3.6.1.2.1.4.20"], (1,)).iteritems()}
        if dev.domain_tree_node_id:
            _tln = dev.domain_tree_node
        else:
            _tln = domain_tree_node.objects.get(Q(depth=0))
        if_lut = {_dev_nd.snmp_idx: _dev_nd for _dev_nd in netdevice.objects.filter(Q(snmp_idx__gt=0) & Q(device=dev))}
        # handle IPs
        _found_ip_ids = set()
        _added = 0
        for ip_struct in _ip_dict.itervalues():
            if ip_struct.if_idx in if_lut:
                _dev_nd = if_lut[ip_struct.if_idx]
                # check for network
                _network_addr = ip_struct.address_ipv4 & ip_struct.netmask_ipv4

                cur_nw = network.objects.get_or_create_network(network_addr=_network_addr,
                                                               netmask=ip_struct.netmask_ipv4,
                                                               context="SNMP")
                # check for existing IP
                try:
                    _ip = net_ip.objects.get(Q(netdevice__device=dev) & Q(ip=ip_struct.address))
                except net_ip.DoesNotExist:
                    _added += 1
                    _ip = net_ip(
                        ip=ip_struct.address,
                    )
                _ip.domain_tree_node = _tln
                _ip.network = cur_nw
                _ip.netdevice = _dev_nd
                _ip.save()
                _found_ip_ids.add(_ip.idx)
        if flags["strict"]:
            stale_ips = net_ip.objects.exclude(Q(pk__in=_found_ip_ids)).filter(Q(netdevice__device=dev))
            if stale_ips.count():
                stale_ips.delete()
        if _added:
            return ResultNode(ok="updated IPs (added: {:d})".format(_added))
        else:
            return ResultNode()
