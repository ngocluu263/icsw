#!/usr/bin/python -Ot
#
# Copyright (C) 2007,2008,2012,2013 Andreas Lang-Nevyjel
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

import sys
import cs_base_class
import logging_tools
import server_command
import net_tools
import pprint
import partition_tools
import process_tools
import config_tools
from lxml import etree
from django.db.models import Q
from initat.cluster_server.config import global_config
from initat.cluster.backbone.models import device, partition, partition_disc, partition_table, \
     partition_fs, lvm_lv, lvm_vg, sys_partition, get_related_models, netdevice, net_ip

class fetch_partition_info(cs_base_class.server_com):
    class Meta:
        needed_option_keys = ["device_pk"]
    def _call(self, cur_inst):
        target_pks = cur_inst.option_dict["device_pk"].split(",")
        cur_inst.log("got %s: %s" % (logging_tools.get_plural("pk", len(target_pks)),
                                     ", ".join(target_pks)))
        src_dev = device.objects.get(Q(pk=global_config["SERVER_IDX"]))
        src_nds = src_dev.netdevice_set.all().values_list("pk", flat=True)
        target_devs = device.objects.filter(Q(pk__in=target_pks)).prefetch_related("netdevice_set")
        cur_inst.log("device list: %s" % (", ".join([unicode(cur_dev) for cur_dev in target_devs])))
        router_obj = config_tools.router_object(cur_inst.log)
        for cur_dev in target_devs:
            routes = router_obj.get_ndl_ndl_pathes(
                src_nds,
                cur_dev.netdevice_set.all().values_list("pk", flat=True),
                only_endpoints=True,
                add_penalty=True)
            cur_dev.target_ip = None
            if routes:
                for route in routes:
                    found_ips = net_ip.objects.filter(Q(netdevice=route[2]))
                    if found_ips:
                        cur_dev.target_ip = found_ips[0].ip
                        break
            if cur_dev.target_ip:
                cur_inst.log("contact device %s via %s" % (
                    unicode(cur_dev),
                    cur_dev.target_ip)
                             )
            else:
                cur_inst.log("no route to device %s found" % (unicode(cur_dev)),
                             logging_tools.LOG_LEVEL_ERROR)
        del router_obj
        zmq_con = net_tools.zmq_connection(
            "server:%s" % (process_tools.get_machine_name()),
            context=self.process_pool.zmq_context)
        result_devs = []
        for target_dev in target_devs:
            if target_dev.target_ip:
                result_devs.append(target_dev)
                conn_str = "tcp://%s:%d" % (cur_dev.target_ip,
                                            2001)
                cur_inst.log("connection_str for %s is %s" % (unicode(target_dev), conn_str))
                zmq_con.add_connection(
                    conn_str,
                    server_command.srv_command(command="partinfo"),
                    multi=True
                )
        res_list = zmq_con.loop()
        cur_inst.log("length of result list: %d" % (len(res_list)))
        num_errors, ret_f = (0, [])
        for idx, (result, target_dev) in enumerate(zip(res_list, result_devs)):
            res_state = -1 if result is None else int(result["result"].attrib["state"])
            if res_state:
                num_errors += 1
                if res_state == -1:
                    ret_f.append("%s: no result" % (unicode(target_dev)))
                else:
                    ret_f.append("%s: error %d: %s" % (
                        unicode(target_dev),
                        int(result["result"].attrib["state"]),
                        result["result"].attrib["reply"]))
            else:
                try:
                    dev_dict, sys_dict, lvm_dict = (
                        result["dev_dict"],
                        result["sys_dict"],
                        result["lvm_dict"],
                    )
                except KeyError:
                    num_errors += 1
                    ret_f.append("%s: error missing keys in dict" % (target_dev))
                else:
                    lvm_info = partition_tools.lvm_struct("xml", xml=lvm_dict)
                    partition_name, partition_info = (
                        "%s_part" % (target_dev),
                        "generated partition_setup from device '%s'" % (target_dev))
                    try:
                        cur_pt = partition_table.objects.get(Q(name=partition_name))
                    except partition_table.DoesNotExist:
                        pass
                    else:
                        for rel_obj in cur_pt._meta.get_all_related_objects():
                            if rel_obj.name in [
                                "backbone:partition_disc",
                                "backbone:lvm_lv",
                                "backbone:lvm_vg",
                                "backbone:sys_partition"]:
                                pass
                            elif rel_obj.name == "backbone:device":
                                for ref_obj in  rel_obj.model.objects.filter(Q(**{rel_obj.field.name : cur_pt})):
                                    self.log("cleaning %s of %s" % (rel_obj.field.name, unicode(ref_obj)))
                                    setattr(ref_obj, rel_obj.field.name, None)
                                    ref_obj.save()
                            else:
                                raise ValueError, "unknown related object %s for partition_info" % (rel_obj.name)
                        cur_pt.delete()
                    # fetch partition_fs
                    fs_dict = {}
                    for db_rec in partition_fs.objects.all():
                        fs_dict.setdefault(("%02x" % (int(db_rec.hexid, 16))).lower(), {})[db_rec.name] = db_rec
                    new_part_table = partition_table(name=partition_name,
                                                     description=partition_info)
                    new_part_table.save()
                    for dev, dev_stuff in dev_dict.iteritems():
                        self.log("handling device %s" % (dev))
                        new_disc = partition_disc(partition_table=new_part_table,
                                                  disc=dev)
                        new_disc.save()
                        for part in sorted(dev_stuff):
                            part_stuff = dev_stuff[part]
                            self.log("   handling partition %s" % (part))
                            hex_type = part_stuff["hextype"][2:].lower()
                            if part.startswith("p"):
                                part = part[1:]
                            if part_stuff.has_key("mountpoint"):
                                fs_stuff = fs_dict.get(hex_type, {}).get(part_stuff["fstype"].lower(), None)
                                if fs_stuff is not None:
                                    new_part = partition(
                                        partition_disc=new_disc,
                                        mountpoint=part_stuff["mountpoint"],
                                        size=part_stuff["size"],
                                        pnum=part,
                                        mount_options=part_stuff["options"] or "defaults",
                                        fs_freq=part_stuff["dump"],
                                        fs_passno=part_stuff["fsck"],
                                        partition_fs=fs_stuff,
                                        disk_by_info=",".join(part_stuff.get("lut", [])),
                                    )
                                else:
                                    self.log("skipping partition because fs_stuff is None", logging_tools.LOG_LEVEL_WARN)
                                    new_part = None
                            else:
                                if fs_dict.has_key(hex_type):
                                    new_part = partition(
                                        partition_disc=new_disc,
                                        partition_hex=hex_type,
                                        size=part_stuff["size"],
                                        pnum=part,
                                        #partition_fs=fs_dict[hex_type],
                                        mount_options="defaults",
                                    )
                                    self.log("skipping partition because no mountpoint and no matching fs_dict (hex_type %s)" % (hex_type), logging_tools.LOG_LEVEL_ERROR)
                                    new_part = None
                                else:
                                    new_part = partition(
                                        partition_disc=new_disc,
                                        partition_hex=hex_type,
                                        size=part_stuff["size"],
                                        pnum=part,
                                    )
                            if new_part is not None:
                                new_part.save()
                            part_name = "%s%s" % (dev, part)
                    for part, part_stuff in sys_dict.iteritems():
                        self.log("handling part %s (sys)" % (part))
                        if type(part_stuff) == type({}):
                            part_stuff = [part_stuff]
                        for p_stuff in part_stuff:
                            # ignore tmpfs mounts
                            if p_stuff["fstype"] in ["tmpfs"]:
                                pass
                            else:
                                new_sys = sys_partition(
                                    partition_table=new_part_table,
                                    name=p_stuff["fstype"] if part == "none" else part,
                                    mountpoint=p_stuff["mountpoint"],
                                    mount_options=p_stuff["options"],
                                )
                                new_sys.save()
                    if lvm_info.lvm_present:
                        self.log("LVM info is present")
                        # lvm save
                        for vg_name, v_group in lvm_info.lv_dict.get("vg", {}).iteritems():
                            self.log("handling VG %s" % (vg_name))
                            new_vg = lvm_vg(
                                partition_table=new_part_table,
                                name=v_group["name"])
                            new_vg.save()
                            v_group["db"] = new_vg
                        for lv_name, lv_stuff in lvm_info.lv_dict.get("lv", {}).iteritems():
                            self.log("handling LV %s" % (lv_name))
                            mount_options = lv_stuff.get(
                                "mount_options", {
                                    "dump"       : 0,
                                    "fsck"       : 0,
                                    "mountpoint" : "",
                                    "options"    : "",
                                    "fstype"     : "",
                                }
                            )
                            mount_options["fstype_idx"] = None
                            if mount_options["fstype"]:
                                mount_options["fstype_idx"] = fs_dict.get("83", {}).get(mount_options["fstype"].lower(), None)
                            new_lv = lvm_lv(
                                partition_table=new_part_table,
                                lvm_vg=lvm_info.lv_dict.get("vg", {})[lv_stuff["vg_name"]]["db"],
                                name=lv_stuff["name"],
                                size=lv_stuff["size"],
                                mountpoint=mount_options["mountpoint"],
                                mount_options=mount_options["options"],
                                fs_freq=mount_options["dump"],
                                fs_passno=mount_options["fsck"],
                                partition_fs=mount_options["fstype_idx"],
                            )
                            new_lv.save()
                            lv_stuff["db"] = new_lv
                    # set partition table
                    cur_inst.log("set partition_table for '%s'" % (unicode(target_dev)))
                    target_dev.act_partition_table = new_part_table
                    target_dev.partdev = ""
                    target_dev.save()
                ret_f.append("%s: %s, %s, %s and %s" % (
                    target_dev,
                    logging_tools.get_plural("disc", len(dev_dict.keys())),
                    logging_tools.get_plural("sys_partition", len(sys_dict.keys())),
                    logging_tools.get_plural("volumegroup", len(lvm_info.lv_dict.get("vg", {}).keys())),
                    logging_tools.get_plural("logical volume", len(lvm_info.lv_dict.get("lv", {}).keys()))))
        if num_errors:
            cur_inst.srv_com["result"].attrib.update({
                "reply" : "ok %s" % (";".join(ret_f)),
                "state" : "%d" % (server_command.SRV_REPLY_STATE_ERROR)})
        else:
            cur_inst.srv_com["result"].attrib.update({
                "reply" : "ok %s" % (";".join(ret_f)),
                "state" : "%d" % (server_command.SRV_REPLY_STATE_OK)})
        
if __name__ == "__main__":
    print "Loadable module, exiting ..."
    sys.exit(0)
