# -*- coding: utf-8 -*-
#
# Copyright (C) 2001-2014 Andreas Lang-Nevyjel, init.at
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
""" machine information """

from initat.host_monitoring import hm_classes, limits
from lxml import etree # @UnresolvedImport
from lxml.builder import E # @UnresolvedImport
import commands
import cpu_database
import logging_tools
import os
import partition_tools
import pci_database
import platform
import pprint
import process_tools
import re
import server_command
import statvfs
import sys
import tempfile
import time
import uuid_tools
import psutil
try:
    from initat.host_monitoring_version import VERSION_STRING
except ImportError:
    VERSION_STRING = "?.?"

nw_classes = ["ethernet", "network", "infiniband"]

EXTRA_BLOCK_DEVS = "/etc/sysconfig/host-monitoring.d/extra_block_devs"

class _general(hm_classes.hm_module):
    def base_init(self):
        self.dmi_bin = process_tools.find_file("dmidecode")
    def init_module(self):
        self.local_lvm_info = partition_tools.lvm_struct("bin")
        self.local_mp_info = partition_tools.multipath_struct("bin")
        self.disk_dict, self.vmstat_dict, self.disk_stat, self.nfsstat_dict = ({}, {}, {}, {})
        # locate binaries
        self.parted_path = process_tools.find_file("parted")
        self.btrfs_path = process_tools.find_file("btrfs")
        self.disk_dict_last_update = 0
        self.last_vmstat_time = None
        self.last_nfsstat_time = None
        self.nfsstat_used = False
    def _proc_stat_info(self, first_line=None):
        self.stat_list = psutil.cpu_times(percpu=False)._fields
        return self.stat_list
    def _rescan_valid_disk_stuff(self):
        self.log("checking valid block_device names and major numbers")
        valid_block_devs, valid_major_nums = ({}, {})
        try:
            block_devs_dict, block_part = ({}, False)
            block_ignore_list = ["loop", "ram", "ramdisk", "fd", "sr", "nbd"]
            for line in open("/proc/devices", "r").readlines():
                line = line.strip().lower()
                if line.startswith("block device"):
                    block_part = True
                elif block_part:
                    lp = line.split(None, 1)
                    if lp[0].isdigit() and lp[1] not in block_ignore_list:
                        block_devs_dict[int(lp[0])] = lp[1]
            block_dir = "/sys/block"
            if os.path.isdir(block_dir):
                for entry in os.listdir(block_dir):
                    dev_file = "%s/%s/dev" % (block_dir, entry)
                    if os.path.isfile(dev_file):
                        major, minor = [int(x) for x in open(dev_file, "r").read().strip().split(":")]
                        if block_devs_dict.has_key(major):
                            dev_name = entry.replace("!", "/")
                            valid_block_devs[dev_name] = major
                            valid_major_nums.setdefault(major, []).append(dev_name)
                            self.log("   adding %-14s (major %3d, minor %3d) to block_device_list" % (dev_name, major, minor))
                            # print dev_name, block_devs_dict[major], minor
        except:
            self.log("error in rescan_valid_disk_stuff: %s" % (process_tools.get_except_info()), logging_tools.LOG_LEVEL_CRITICAL)
        else:
            self.log("Found %s and %s: %s; %s" % (
                logging_tools.get_plural("device_name", len(valid_block_devs.keys())),
                logging_tools.get_plural("major number", len(valid_major_nums.keys())),
                ", ".join(valid_block_devs.keys()),
                ", ".join(["%d" % (x) for x in valid_major_nums.keys()])))
        self.valid_block_devs, self.valid_major_nums = (valid_block_devs,
                                                        valid_major_nums)
        # pprint.pprint(psutil.disk_io_counters(perdisk=True))
        # print "*", self.valid_block_devs, self.valid_major_nums
    def set_machine_vector_flags(self, mv):
        mv.vector_flags["detailed_cpu_statistics"] = False
    def init_machine_vector(self, mv):
        mv.register_entry("load.1"           , 0., "load average of the last $2 minute")
        mv.register_entry("load.5"           , 0., "load average of the last $2 minutes")
        mv.register_entry("load.15"          , 0., "load average of the last $2 minutes")
        mv.register_entry("mem.avail.phys"   , 0, "available physical memory"       , "Byte", 1024, 1024)
        mv.register_entry("mem.avail.swap"   , 0, "available swap memory"           , "Byte", 1024, 1024)
        mv.register_entry("mem.avail.total"  , 0, "available total memory"          , "Byte", 1024, 1024)
        mv.register_entry("mem.free.phys"    , 0, "free physical memory"            , "Byte", 1024, 1024)
        mv.register_entry("mem.free.phys.bc" , 0, "free physical memory without b+c", "Byte", 1024, 1024)
        mv.register_entry("mem.free.swap"    , 0, "free swap memory"                , "Byte", 1024, 1024)
        mv.register_entry("mem.free.total"   , 0, "free total memory"               , "Byte", 1024, 1024)
        mv.register_entry("mem.free.total.bc", 0, "free total memory without b+c"   , "Byte", 1024, 1024)
        mv.register_entry("mem.used.phys"    , 0, "used physical memory"            , "Byte", 1024, 1024)
        mv.register_entry("mem.used.phys.bc" , 0, "used physical memory with b+c"   , "Byte", 1024, 1024)
        mv.register_entry("mem.used.swap"    , 0, "used swap memory"                , "Byte", 1024, 1024)
        mv.register_entry("mem.used.total"   , 0, "used total memory"               , "Byte", 1024, 1024)
        mv.register_entry("mem.used.total.bc", 0, "used total memory with b+c"      , "Byte", 1024, 1024)
        mv.register_entry("mem.used.buffers" , 0, "memory used for buffers"         , "Byte", 1024, 1024)
        mv.register_entry("mem.used.cached"  , 0, "memory used for caches"          , "Byte", 1024, 1024)
        # mv.register_entry("mem.used.shared"  , 0, "shared memory"                   , "Byte", 1024, 1024)
        # check for /proc/stat
        stat_list = self._proc_stat_info()
        for what in stat_list:
            mv.register_entry("vms.{}".format(what), 0., "percentage of time spent for $2 (total)", "%")
        self.cpu_list = ["{:d}".format(_cpu_idx) for _cpu_idx in xrange(psutil.cpu_count(logical=True))]
        if mv.vector_flags["detailed_cpu_statistics"]:
            if not self.cpu_list:
                self.cpu_list = ["0"]
            if len(self.cpu_list) > 1:
                for cpu_idx in self.cpu_list:
                    for what in stat_list:
                        mv.register_entry("vms.{}.p{}".format(what, cpu_idx), 0., "percentage of time spent for $2 on cpu {}".format(cpu_idx), "%")
        mv.register_entry("num.interrupts", 0, "number of interrupts per second"      , "1/s")
        mv.register_entry("num.context"   , 0, "number of context switches per second", "1/s")
        # mv.register_entry("blks.in"       , 0, "number of blocks read per second"     , "1/s")
        # mv.register_entry("blks.out"      , 0, "number of blocks written per second"  , "1/s")
        mv.register_entry("swap.in"       , 0, "number of swap pages brought in"      , "1/s")
        mv.register_entry("swap.out"      , 0, "number of swap pages brought out"     , "1/s")
        mv.register_entry("pages.in"      , 0, "number of pages brought in"      , "1/s")
        mv.register_entry("pages.out"     , 0, "number of pages brought out"     , "1/s")
        self._rescan_valid_disk_stuff()
    def _cpuinfo_int(self, srv_com):
        return cpu_database.global_cpu_info().get_send_dict(srv_com)
    def _load_int(self):
        return [float(value) for value in open("/proc/loadavg", "r").read().strip().split()[0:3]]
    def _mem_int(self):
        return psutil.virtual_memory(), psutil.swap_memory()
    def _df_int(self, mvect=None):
        act_time, update_dict = (time.time(), False)
        if mvect or abs(self.disk_dict_last_update - act_time) > 90:
            update_dict = True
        if update_dict:
            self.disk_dict_last_update = act_time
            ram_match = re.compile("^.*/ram\d+$")
            smount_lines = [line.strip().split() for line in open("/etc/mtab", "r").readlines()]
            link_set, mount_list = (set(), [])
            for line in smount_lines:
                if line[2] not in ["none"] and line[0].startswith("/") and not ram_match.match(line[0]) and line[0].startswith("/dev/"):
                    mount_list.append(line)
                    if os.path.islink(line[0]):
                        link_set.add((
                            os.path.normpath(
                                os.path.join(
                                    os.path.dirname(line[0]),
                                    os.readlink(line[0]))
                                ),
                                line[0]
                            ))
            # print self.disk_dict
            n_dict = {}
            for mnt in mount_list:
                try:
                    osres = os.statvfs(mnt[1])
                except:
                    pass
                else:
                    fact = float(osres[statvfs.F_FRSIZE]) / (1024.)
                    try:
                        blocks, bfree, bavail = int(osres[statvfs.F_BLOCKS]), int(osres[statvfs.F_BFREE]), int(osres[statvfs.F_BAVAIL])
                        inodes, ifree, iavail = int(osres[statvfs.F_FILES]), int(osres[statvfs.F_FFREE]), int(osres[statvfs.F_FAVAIL])
                    except:
                        pass
                    else:
                        if blocks:
                            sizetot = blocks * fact
                            sizeused = (blocks - bfree) * fact
                            sizeavail = bavail * fact
                            sizefree = sizetot - sizeused
                            proc = int((100. * float(blocks - bfree)) / float(blocks - bfree + bavail))
                            # print mnt, proc
                            n_dict[mnt[0]] = {
                                "mountpoint"  : mnt[1],
                                "fs"          : mnt[2],
                                "b_free_perc" : proc,
                                "b_size"      : int(sizetot),
                                "b_used"      : int(sizeused),
                                "b_free"      : int(sizefree),
                                "i_size"      : int(inodes),
                                # "i_used"      : int(inodes) - int(ifree),
                                "i_avail"     : int(iavail),
                                "i_free"      : int(ifree),
                            }
                            # [mnt[1], proc, int(sizetot), int(sizeused), int(sizefree), mnt[2]]
            for link_dst, link_src in link_set:
                n_dict[link_dst] = n_dict[link_src]
        else:
            n_dict = self.disk_dict
        if mvect:
            # delete old keys
            for key in self.disk_dict:
                if key not in n_dict:
                    mvect.unregister_entry("df.%s.f" % (key))
                    mvect.unregister_entry("df.%s.u" % (key))
                    mvect.unregister_entry("df.%s.t" % (key))
            for key in n_dict:
                if key not in self.disk_dict:
                    mvect.register_entry(
                        "df.%s.f" % (key),
                        0.,
                        "free space on $2 (%s, %s)" % (n_dict[key]["mountpoint"], n_dict[key]["fs"]),
                        "Byte", 1000, 1000)
                    mvect.register_entry(
                        "df.%s.u" % (key),
                        0.,
                        "used space on $2 (%s, %s)" % (n_dict[key]["mountpoint"], n_dict[key]["fs"]),
                        "Byte", 1000, 1000)
                    mvect.register_entry(
                        "df.%s.t" % (key),
                        0.,
                        "size of $2 (%s, %s)" % (n_dict[key]["mountpoint"], n_dict[key]["fs"]),
                        "Byte", 1000, 1000)
            self.disk_dict = n_dict
            for key in self.disk_dict:
                mvect["df.%s.f" % (key)] = self.disk_dict[key]["b_free"]
                mvect["df.%s.u" % (key)] = self.disk_dict[key]["b_used"]
                mvect["df.%s.t" % (key)] = self.disk_dict[key]["b_size"]
        else:
            return n_dict
    def _vmstat_int(self, mvect):
        act_time = time.time()
        # disk_stat format: device -> (sectors read/written, milliseconds spent read/written)
        stat_dict, disk_stat = ({}, {})
        for line in [cur_line.strip().split() for cur_line in open("/proc/stat", "r") if cur_line.strip()]:
            # if line[0].startswith("cpu"):
            #    if not mvect.vector_flags["detailed_cpu_statistics"] and line[0] != "cpu":
            #        continue
            #    stat_dict[line[0]] = [long(_line) for _line in line[1:]]
            if line[0] == "ctxt":
                stat_dict["ctxt"] = long(line[1])
            elif line[0] == "intr":
                stat_dict["intr"] = long(line[1])
        # use psutil
        stat_dict["cpu"] = psutil.cpu_times()
        if mvect.vector_flags["detailed_cpu_statistics"]:
            for cpu_num, cpu_stat in enumerate(psutil.cpu_times(percpu=True)):
                stat_dict["cpu{}".format(self.cpu_list[cpu_num])] = cpu_stat
        if os.path.isfile("/proc/vmstat"):
            _vm_dict = {}
            for line in [cur_line.strip().split() for cur_line in open("/proc/vmstat", "r").readlines() if cur_line.strip()]:
                if len(line) == 2:
                    key, value = line
                    if value.isdigit():
                        _vm_dict[key] = int(value)
            # print _vm_dict
            # print psutil.disk_io_counters(perdisk=True)
            stat_dict["swap"] = [_vm_dict.get("pswpin", 0), _vm_dict.get("pswpout", 0)]
            stat_dict["pages"] = [_vm_dict.get("pgpgin", 0), _vm_dict.get("pgpgout", 0)]
        if os.path.isfile("/proc/diskstats"):
            try:
                ds_dict = dict([(parts[2].strip(), [int(parts[0]), int(parts[1])] + [long(cur_val) for cur_val in parts[3:]]) for parts in [line.strip().split() for line in open("/proc/diskstats", "r").readlines()] if len(parts) == 14]) # and y[2].strip() in self.valid_block_devs.keys()])
            except:
                pass
            else:
                # get list of mounts
                try:
                    mount_list = [line.strip().split()[0].split("/", 2)[2] for line in open("/proc/mounts", "r").readlines() if line.startswith("/dev")]
                except:
                    # cannot read, take all devs
                    mount_list = ds_dict.keys()
                else:
                    # check for by-* devices
                    mount_list = [os.path.normpath(os.path.join(os.path.dirname(os.path.join("/dev", _value)), os.readlink(os.path.join("/dev", _value)))).split("/", 2)[2] if _value.count("/by-") else _value for _value in mount_list]
                # get unique devices
                ds_keys_ok_by_name = sorted([key for key in ds_dict.iterkeys() if key in self.valid_block_devs])
                # sort out partition stuff
                last_name = ""
                ds_keys_ok_by_major = []
                for d_name in sorted([key for key, value in ds_dict.iteritems() if value[0] in self.valid_major_nums.keys()]):
                    if last_name and not (d_name.startswith("dm-") or d_name.startswith("md")) and d_name.startswith(last_name):
                        pass
                    else:
                        ds_keys_ok_by_major.append(d_name)
                        last_name = d_name
                if ds_keys_ok_by_name != ds_keys_ok_by_major:
                    self._rescan_valid_disk_stuff()
                    ds_keys_ok_by_major = ds_keys_ok_by_name
                    self.local_lvm_info.update()
                mounted_lvms = {}
                if self.local_lvm_info.lvm_present:
                    for _loc_lvm_name, loc_lvm_info in self.local_lvm_info.lv_dict.get("lv", {}).iteritems():
                        lv_k_major, lv_k_minor = (int(loc_lvm_info["kernel_major"]),
                                                  int(loc_lvm_info["kernel_minor"]))
                        if lv_k_major in self.valid_major_nums.keys():
                            mount_dev = "%s/%s" % (loc_lvm_info["vg_name"],
                                                   loc_lvm_info["name"])
                            mounted_lvms[mount_dev] = "%s-%d" % (self.valid_major_nums[lv_k_major][0].split("-")[0], lv_k_minor)
                if os.path.isfile(EXTRA_BLOCK_DEVS):
                    extra_block_devs = [entry.strip() for entry in file(EXTRA_BLOCK_DEVS, "r").read().split("\n") if entry.strip()]
                else:
                    extra_block_devs = []
                # problem: LVM devices are not handled properly
                dev_list = [ds_key for ds_key in ds_keys_ok_by_name if [True for m_entry in mount_list if m_entry.startswith(ds_key)]] + \
                           [value for key, value in mounted_lvms.iteritems() if key in mount_list] + \
                           extra_block_devs
                for dl in set(dev_list):
                    try:
                        bname = os.path.basename(dl)
                        if dl.startswith("cciss"):
                            bname = "cciss!%s" % (bname)
                        cur_bs = int(file("/sys/block/%s/queue/hw_sector_size" % (bname), "r").read().strip())
                    except:
                        cur_bs = 512
                        self.log(
                            "cannot get bs of {} (using {:d}): {}".format(
                                dl,
                                cur_bs,
                                process_tools.get_except_info()
                            ),
                            logging_tools.LOG_LEVEL_ERROR
                        )
                    disk_stat[dl] = (
                        ds_dict[dl][4],
                        ds_dict[dl][8],
                        ds_dict[dl][5],
                        ds_dict[dl][9],
                        ds_dict[dl][11],
                        ds_dict[dl][4] * cur_bs,
                        ds_dict[dl][8] * cur_bs,
                        )
                # pprint.pprint(disk_stat)
                # pprint.pprint(psutil.disk_io_counters(perdisk=False))
                # pprint.pprint(psutil.disk_io_counters(perdisk=True))
                disk_stat["total"] = []
                for idx in xrange(7):
                    disk_stat["total"].append(sum([disk_stat[d_name][idx] for d_name in dev_list]))
                dev_list.append("total")
                unique_dev_list = dev_list
                # pprint.pprint(disk_stat)
        # print dev_list, disk_stat
        # stat_dict["disk_io"] = [blks_read, blks_written]
        if self.last_vmstat_time is not None:
            tdiff = act_time - self.last_vmstat_time
            vms_tdiff = tdiff
            if "ctxt" in stat_dict and "ctxt" in self.vmstat_dict:
                mvect["num.context"] = int((stat_dict["ctxt"] - self.vmstat_dict["ctxt"]) / tdiff)
            _cpu_update_list = [("cpu", "")]
            if mvect.vector_flags["detailed_cpu_statistics"]:
                _cpu_update_list.extend([("cpu{}".format(cpu_idx), ".p{}".format(cpu_idx)) for cpu_idx in self.cpu_list] if len(self.cpu_list) > 1 else [])
            for cpu_str, name_p in _cpu_update_list:
                if cpu_str in stat_dict and cpu_str in self.vmstat_dict:
                    for idx, name in enumerate(self.stat_list):
                        mvect["vms.{}{}".format(name, name_p)] = float(sub_wrap(stat_dict[cpu_str][idx], self.vmstat_dict[cpu_str][idx]) / (vms_tdiff / 100.))
                else:
                    break
            if "intr" in stat_dict and "intr" in self.vmstat_dict:
                mvect["num.interrupts"] = int(sub_wrap(stat_dict["intr"], self.vmstat_dict["intr"]) / tdiff)
            if "swap" in stat_dict and "swap" in self.vmstat_dict:
                for name, idx in [("in", 0), ("out", 1)]:
                    mvect["swap.%s" % (name)] = int(sub_wrap(stat_dict["swap"][idx], self.vmstat_dict["swap"][idx]) / tdiff)
            if "pages" in stat_dict and "pages" in self.vmstat_dict:
                for name, idx in [("in", 0), ("out", 1)]:
                    mvect["pages.%s" % (name)] = int(sub_wrap(stat_dict["pages"][idx], self.vmstat_dict["pages"][idx]) / tdiff)
            # print unique_dev_list
            if unique_dev_list != ["total"]:
                for act_disk in unique_dev_list:
                    if not self.disk_stat.has_key(act_disk):
                        info_str = act_disk == "total" and "total" or "on /dev/$2"
                        mvect.register_entry("io.%s.blks.read" % (act_disk)    , 0 , "number of blocks read per second %s" % (info_str)   , "1/s")
                        mvect.register_entry("io.%s.blks.written" % (act_disk) , 0 , "number of blocks written per second %s" % (info_str), "1/s")
                        mvect.register_entry("io.%s.bytes.read" % (act_disk)   , 0 , "bytes read per second %s" % (info_str)   , "B/s", 1024)
                        mvect.register_entry("io.%s.bytes.written" % (act_disk), 0 , "bytes written per second %s" % (info_str), "B/s", 1024)
                        mvect.register_entry("io.%s.time.read" % (act_disk)    , 0., "milliseconds spent reading %s" % (info_str)         , "s")
                        mvect.register_entry("io.%s.time.written" % (act_disk) , 0., "milliseconds spent writing %s" % (info_str)         , "s")
                        mvect.register_entry("io.%s.time.io" % (act_disk)      , 0., "milliseconds spent doing I/O %s" % (info_str)       , "s")
            for old_disk in self.disk_stat.keys():
                if not disk_stat.has_key(old_disk):
                    mvect.unregister_entry("io.%s.blks.read" % (old_disk))
                    mvect.unregister_entry("io.%s.blks.written" % (old_disk))
                    mvect.unregister_entry("io.%s.bytes.read" % (old_disk))
                    mvect.unregister_entry("io.%s.bytes.written" % (old_disk))
                    mvect.unregister_entry("io.%s.time.read" % (old_disk))
                    mvect.unregister_entry("io.%s.time.written" % (old_disk))
                    mvect.unregister_entry("io.%s.time.io" % (old_disk))
            for act_disk in [dev for dev in unique_dev_list if dev in self.disk_stat]:
                # print act_disk, disk_stat[act_disk]
                for idx, what in [(0, "read"), (1, "written")]:
                    mvect["io.%s.blks.%s" % (act_disk, what)] = int(sub_wrap(disk_stat[act_disk][idx], self.disk_stat[act_disk][idx]) / tdiff)
                for idx, what in [(5, "read"), (6, "written")]:
                    mvect["io.%s.bytes.%s" % (act_disk, what)] = int(sub_wrap(disk_stat[act_disk][idx], self.disk_stat[act_disk][idx]) / tdiff)
                for idx, what in [(2, "read"), (3, "written"), (4, "io")]:
                    mvect["io.%s.time.%s" % (act_disk, what)] = float(sub_wrap(disk_stat[act_disk][idx], self.disk_stat[act_disk][idx]) / (1000 * tdiff))
            self.vmstat_dict = stat_dict
            self.disk_stat = disk_stat
        else:
            tdiff = None
        self.last_vmstat_time = act_time
    def _interpret_nfsstat_line(self, header, *parts):
        if header in ["th"]:
            return [int(parts[0]), int(parts[1])] + [float(val) for val in parts[2:]]
        else:
            return [int(val) for val in parts]
    def _nfsstat_int(self, mvect):
        act_time = time.time()
        nfs_file = "/proc/net/rpc/nfsd"
        if os.path.isfile(nfs_file):
            if not self.nfsstat_used:
                self.nfsstat_used = True
                # register
                mvect.register_entry("nfs.rc.hits"   , 0., "NFS read cache hits"   , "1/s")
                mvect.register_entry("nfs.rc.misses" , 0., "NFS read cache misses" , "1/s")
                mvect.register_entry("nfs.rc.nocache", 0., "NFS cache not required", "1/s")
                mvect.register_entry("nfs.io.read"   , 0., "bytes read from disk", "B/s" , 1024)
                mvect.register_entry("nfs.io.write"  , 0., "bytes written to disk", "B/s", 1024)
                mvect.register_entry("nfs.net.count"   , 0., "total reads"    , "1/s")
                mvect.register_entry("nfs.net.udpcount", 0., "UDP packets"    , "1/s")
                mvect.register_entry("nfs.net.tcpcount", 0., "TCP packets"    , "1/s")
                mvect.register_entry("nfs.net.tcpcons" , 0., "TCP connections", "1/s")
                mvect.register_entry("nfs.rpc.count"   , 0., "total RPC operations", "1/s")
                mvect.register_entry("nfs.rpc.badtotal", 0., "bad RPC errors"      , "1/s")
                mvect.register_entry("nfs.rpc.badfmt"  , 0., "RPC bad format"      , "1/s")
                mvect.register_entry("nfs.rpc.badauth" , 0., "RPC bad auth"        , "1/s")
                mvect.register_entry("nfs.rpc.badclnt" , 0., "RPC bad clnt"        , "1/s")
            nfs_dict = dict([(parts[0], self._interpret_nfsstat_line(*parts)) for parts in [line.split() for line in file(nfs_file, "r").read().split("\n")] if len(parts)])
            if self.last_nfsstat_time:
                tdiff = act_time - self.last_nfsstat_time
                # read cache
                for index, name in enumerate(["hits", "misses", "nocache"]):
                    mvect["nfs.rc.%s" % (name)] = float(sub_wrap(nfs_dict["rc"][index], self.nfsstat_dict["rc"][index]) / tdiff)
                # io
                for index, name in enumerate(["read", "write"]):
                    mvect["nfs.io.%s" % (name)] = float(sub_wrap(nfs_dict["io"][index], self.nfsstat_dict["io"][index]) / tdiff)
                # net
                for index, name in enumerate(["count", "udpcount", "tcpcount", "tcpcons"]):
                    mvect["nfs.net.%s" % (name)] = float(sub_wrap(nfs_dict["net"][index], self.nfsstat_dict["net"][index]) / tdiff)
                # rpc
                for index, name in enumerate(["count", "badtotal", "badfmt", "badauth", "badclnt"]):
                    mvect["nfs.rpc.%s" % (name)] = float(sub_wrap(nfs_dict["rpc"][index], self.nfsstat_dict["rpc"][index]) / tdiff)
            self.nfsstat_dict = nfs_dict
            self.last_nfsstat_time = act_time
            # pprint.pprint(nfs_dict)
        else:
            if self.nfsstat_used:
                self.nfsstat_used = False
                # unregister and clear stats
                self.last_nfsstat_time = None
                self.nfsstat_dict = {}
                mvect.unregister_tree("nfs.")
    def update_machine_vector(self, mv):
        try:
            load_list = self._load_int()
        except:
            load_list = [0., 0., 0.]
        mv["load.1"] = load_list[0]
        mv["load.5"] = load_list[1]
        mv["load.15"] = load_list[2]
        try:
            virt_info, swap_info = self._mem_int()
        except:
            mv["mem.avail.phys"] = 0
            mv["mem.avail.swap"] = 0
            mv["mem.avail.total"] = 0
            mv["mem.free.phys"] = 0
            mv["mem.free.phys.bc"] = 0
            mv["mem.free.swap"] = 0
            mv["mem.free.total"] = 0
            mv["mem.free.total.bc"] = 0
            mv["mem.used.phys"] = 0
            mv["mem.used.phys.bc"] = 0
            mv["mem.used.swap"] = 0
            mv["mem.used.total"] = 0
            mv["mem.used.total.bc"] = 0
            mv["mem.used.buffers"] = 0
            mv["mem.used.cached"] = 0
            # mv["mem.used.shared"] = 0
        else:
            # buffers + cached
            bc_mem = virt_info.buffers + virt_info.cached
            mv["mem.avail.phys"] = virt_info.total / 1024
            mv["mem.avail.swap"] = swap_info.total / 1024
            mv["mem.avail.total"] = (virt_info.total + swap_info.total) / 1024
            mv["mem.free.phys"] = virt_info.free / 1024
            mv["mem.free.phys.bc"] = (virt_info.free + bc_mem) / 1024
            mv["mem.free.swap"] = swap_info.free / 1024
            mv["mem.free.total"] = (virt_info.free + swap_info.free) / 1024
            mv["mem.free.total.bc"] = (virt_info.free + bc_mem + swap_info.free) / 1024
            mv["mem.used.phys"] = (virt_info.total - (virt_info.free + bc_mem)) / 1024
            mv["mem.used.phys.bc"] = (virt_info.total - virt_info.free) / 1024
            mv["mem.used.swap"] = (swap_info.total - swap_info.free) / 1024
            mv["mem.used.total"] = (virt_info.total + swap_info.total - (virt_info.free + swap_info.free + bc_mem)) / 1024
            mv["mem.used.total.bc"] = (virt_info.total + swap_info.total - (virt_info.free + swap_info.free)) / 1024
            mv["mem.used.buffers"] = virt_info.buffers / 1024
            mv["mem.used.cached"] = virt_info.cached / 1024
            # mv["mem.used.shared"] = mem_list["MemShared"]
        for call_name in ["_df_int", "_vmstat_int", "_nfsstat_int"]:
            try:
                getattr(self, call_name)(mv)
            except:
                self.log(
                    "error calling self.%s(): %s" % (
                        call_name,
                        process_tools.get_except_info()),
                    logging_tools.LOG_LEVEL_CRITICAL)
    def _partinfo_int(self):
        # lookup tables for /dev/disk-by
        my_disk_lut = partition_tools.disk_lut()
        # print self.local_lvm_info
        # IGNORE_LVM_PARTITIONS = False
        file_dict = {}
        # read files
        file_list = ["/proc/mounts", "/proc/devices", "/etc/fstab", "/proc/partitions"]
        for file_name in file_list:
            b_name = os.path.basename(file_name)
            try:
                cur_list = [line.strip().split() for line in open(file_name, "r").read().split("\n") if line.strip() and not line.strip().startswith("#")]
            except:
                pass
            else:
                file_dict[b_name] = cur_list
        read_err_list = [os.path.basename(file_name) for file_name in file_list if os.path.basename(file_name) not in file_dict]
        file_dict["partitions"] = [line[0:4] for line in file_dict["partitions"] if len(line) > 3]
        dev_dict, sys_dict = ({}, {})
        try:
            real_root_dev = int(open("/proc/sys/kernel/real-root-dev", "r").read().strip())
        except:
            read_err_list.append("/proc/sys/kernel/real-root-dev")
        if read_err_list:
            ret_str = "error reading %s" % (", ".join(read_err_list))
        else:
            ret_str = ""
            # build devices-dict
            while True:
                stuff = file_dict.get("devices", []).pop(0)
                if stuff[0].lower().startswith("block"):
                    break
            devices_dict = dict([(int(key), value) for key, value in file_dict.get("devices", [])])
            # print devices_dict
            # build partition-dict
            part_dict, real_root_dev_name = ({}, None)
            for major, minor, blocks, part_name in file_dict.get("partitions", []):
                if major.isdigit() and minor.isdigit() and blocks.isdigit():
                    major = int(major)
                    minor = int(minor)
                    if major * 256 + minor == real_root_dev:
                        real_root_dev_name = part_name
                    blocks = int(blocks)
                    if not minor or not part_name[-1].isdigit():
                        dev_dict["/dev/%s" % (part_name)] = {}
                    part_dict.setdefault(major, {}).setdefault(minor, (part_name, blocks))
            if not real_root_dev_name and real_root_dev:
                real_root_list = [entry[0] for entry in file_dict.get("mounts", []) if entry[1] == "/" and entry[0] != "rootfs"]
                if real_root_list:
                    real_root_dev = real_root_list[0]
                    if not real_root_dev.startswith("/"):
                        ret_str = "error determining real_root_device"
            if not real_root_dev_name:
                # try to get root-dev-name from /dev/root
                if os.path.islink("/dev/root"):
                    real_root_dev_name = os.path.normpath(os.path.join("/dev", os.readlink("/dev/root")))
                    # if real_root_dev_name.startswith("/dev/"):
                    #    real_root_dev_name = real_root_dev_name[5:]
            # still no real_root_dev_name: try /etc/mtab
            if not real_root_dev_name:
                if os.path.isfile("/etc/mtab"):
                    root_list = [parts[0] for parts in [line.split() for line in open("/etc/mtab", "r").read().split("\n") if line.strip()] if len(parts) > 2 and parts[1] == "/"]
                    if root_list:
                        real_root_dev_name = root_list[0]
                        if real_root_dev_name.startswith("/dev/"):
                            real_root_dev_name = real_root_dev_name[5:]
            # resolve real_root_dev_name if /dev/disk/by-uuid
            # print real_root_dev_name
            # hm, not needed ?
            if False:
                if real_root_dev_name.startswith("/dev/disk/by-uuid"):
                    _real_root_dev_name = os.path.join(real_root_dev_name, os.readlink(real_root_dev_name))
                    self.log("real_root_dev_name is {}, following link to {}".format(
                        real_root_dev_name,
                        _real_root_dev_name,))
                    real_root_dev_name = _real_root_dev_name
            if not ret_str:
                # build blkid dict
                uls_obj = partition_tools.uuid_label_struct()
                # partition lookup dict
                part_lut = {}
                part_bin = self.parted_path
                if part_bin:
                    self.log("getting partition info via parted")
                    cur_stat, out = commands.getstatusoutput("%s -l" % (part_bin))
                    skip_until_next_blank_line = False
                    parted_dict = {}
                    dev_dict = {}
                    for line in out.split("\n"):
                        line = line.rstrip()
                        if line and skip_until_next_blank_line:
                            continue
                        elif skip_until_next_blank_line:
                            skip_until_next_blank_line = False
                            continue
                        if line.strip().lower().startswith("error") or line.strip().lower().startswith("warn"):
                            # skip error or blank lines
                            skip_until_next_blank_line = True
                            continue
                        lline = line.lower()
                        if lline.startswith("model"):
                            parts = line.strip().split()
                            cur_disc = {"model" : " ".join(parts[1:-1]),
                                        "type"  : parts[-1][1:-1]}
                        elif lline.startswith("disk"):
                            d_name = lline.split()[1][:-1]
                            parted_dict[d_name] = cur_disc
                            if cur_disc["type"] in ["dm"]:
                                # ignore mapper devices in dev_dict
                                pass
                            else:
                                dev_dict[d_name] = {}
                            cur_disc["size"] = line.split()[-1]
                        elif lline.startswith("sector"):
                            pass
                        elif lline.startswith("partition table"):
                            cur_disc["table_type"] = line.split()[-1]
                        elif lline.startswith("number"):
                            if cur_disc["type"] in ["dm"]:
                                # not interested in parsing device-mapper devices
                                skip_until_next_blank_line = True
                        elif line:
                            parts = line.strip().split()
                            part_num = parts.pop(0)
                            start = parts.pop(0)
                            end = parts.pop(0)
                            size = parts.pop(0)
                            if size.endswith("TB"):
                                size = int(float(size[:-2]) * 1000 * 1000)
                            elif size.endswith("GB"):
                                size = int(float(size[:-2]) * 1000)
                            elif size.endswith("MB"):
                                size = int(float(size[:-2]))
                            else:
                                size = 0
                            parts = (" ".join(parts)).replace(",", "").strip().split()
                            if any([part.count("type") for part in parts]):
                                # assume hextype is last in list
                                hextype = "0x%02x" % (int(parts.pop(-1).split("=", 1)[1], 16))
                            else:
                                # no hextype
                                if any ([fs_name in (" ".join(parts)).lower() for fs_name in ["ext3", "ext4", "btrfs"]]):
                                    hextype = "0x83"
                                elif any ([fs_name in (" ".join(parts)).lower() for fs_name in ["swap"]]):
                                    hextype = "0x82"
                                elif any ([fs_name in (" ".join(parts)).lower() for fs_name in ["lvmpv"]]):
                                    hextype = "0x8e"
                                else:
                                    hextype = None
                            dev_dict[d_name][part_num] = {
                                "size"    : size,
                                "hextype" : hextype,
                                "info"    : " ".join(parts),
                            }
                            part_lut["%s%s" % (d_name, part_num)] = (d_name, part_num)
                else:
                    self.log("getting partition info via sfdisk (deprecated)")
                    # fetch fdisk information
                    for dev in dev_dict.keys():
                        cur_stat, out = commands.getstatusoutput("/sbin/fdisk -l %s" % (dev))
                        if cur_stat:
                            ret_str = "error reading partition table of %s (%d): %s" % (dev, cur_stat, out)
                            break
                        lines = [[part.strip() for part in line.strip().split() if part.strip() != "*"] for line in out.split("\n") if line.startswith(dev)]
                        for line in lines:
                            part = line.pop(0)
                            start = line.pop(0)
                            end = line.pop(0)
                            size = line.pop(0)
                            hextype = line.pop(0)
                            info = " ".join(line)
                            if size.endswith("+"):
                                size = size[:-1]
                            start, end, size = (int(start), int(end), int(size) / 1000)
                            hextype = "0x%02x" % (int(hextype, 16))
                            part_num = part[len(dev):]
                            dev_dict[dev][part_num] = {
                                "size"      : size,
                                "hextype"   : hextype,
                                "info"      : info,
                            }
                            part_lut[part] = (dev, part_num)
                # kick empty devices
                dev_dict = dict([(key, value) for key, value in dev_dict.iteritems() if value])
                if not ret_str:
                    if not dev_dict:
                        # no device_dict up to now, maybe xen-machine, check part_dict
                        for major, m_stuff in part_dict.iteritems():
                            for minor, part_stuff in m_stuff.iteritems():
                                part_name, part_size = part_stuff
                                dev_name = part_name
                                while dev_name[-1].isdigit():
                                    dev_name = dev_name[:-1]
                                part_num = int(part_name[len(dev_name):])
                                dev_name = "/dev/%s" % (dev_name)
                                if not dev_dict.has_key(dev_name):
                                    dev_dict[dev_name] = {}
                                dev_dict[dev_name]["%d" % (part_num)] = {
                                    "size"    : part_size / 1024,
                                    "hextype" : "0x00",
                                    "info"    : ""}
                                part_lut["/dev/%s" % (part_name)] = (dev_name, "%d" % (part_num))
                    # automount mointpoints
                    auto_mps = []
                    # drop unneeded entries
                    real_mounts, sys_mounts = ([], [])
                    parts_found = []
                    # build fs_tab_dict
                    fs_tab_dict = {}
                    for value in file_dict.get("fstab", []):
                        key = value[0]
                        # rewrite key to 'real' devices /dev/sdXY
                        # at first try to make a lookup in the lvm lut
                        if key in self.local_lvm_info.dm_dict["lvtodm"]:
                            key = self.local_lvm_info.dm_dict["lvtodm"][key]
                        else:
                            if key.count("by-"):
                                key = my_disk_lut[key]
                        fs_tab_dict[key] = value
                    for mount_idx, (part, mp, fstype, opts, _ignore_1, _ignore_2) in enumerate(file_dict.get("mounts", [])):
                        # rewrite from /dev/disk to real device
                        # ???
                        # if part.startswith("/dev/disk"):
                        #    part = dd_lut["fw_lut"][part]
                        if part in parts_found:
                            # already touched
                            continue
                        parts_found.append(part)
                        if fstype in ["subfs", "autofs"]:
                            continue
                        if part == "rootfs" or part.startswith("automount(") or part.count(":"):
                            if part.startswith("automount("):
                                auto_mps.append(mp)
                            continue
                        if part == "/dev/root":
                            part = "/dev/%s" % (real_root_dev_name)
                        if part.startswith("/") and part != mp:
                            if any([mp.startswith(entry) for entry in auto_mps]):
                                # ignore automounted stuff
                                continue
                            elif part.startswith("/dev/loop"):
                                # ignore loop mounted stuff
                                continue
                            # now we are at the real devices
                            fs_tab_entry = fs_tab_dict.get(part, None)
                            if fs_tab_entry:
                                dump, fsck = (int(fs_tab_entry[-2]),
                                              int(fs_tab_entry[-1]))
                            else:
                                dump, fsck = (0, 0)
                            real_mounts.append((part, mp, fstype, opts, dump, fsck))
                            if not part_lut.has_key(part):
                                # check for LVM-partition
                                part = self.local_lvm_info.dm_dict["dmtolv"].get(part, part)
                                try:
                                    if part.startswith("/dev/mapper"):
                                        vg_lv_base = os.path.basename(part)
                                        if vg_lv_base.count("-"):
                                            vg_name, lv_name = part.split("/")[3].split("-")
                                        else:
                                            vg_name, lv_name = (vg_lv_base, None)
                                    else:
                                        vg_name, lv_name = part.split("/")[2:4]
                                except:
                                    self.log(
                                        "error splitting path %s (line %d): %s" % (
                                            part,
                                            mount_idx,
                                            process_tools.get_except_info()),
                                        logging_tools.LOG_LEVEL_ERROR
                                    )
                                else:
                                    if vg_name in self.local_mp_info.dev_dict and lv_name not in self.local_lvm_info.lv_dict.get("lv", {}):
                                        # handled by multipath and not present in lvm-struct
                                        dm_struct = self.local_mp_info.dev_dict[vg_name]
                                        dm_name = os.path.normpath(
                                            os.path.join(
                                                "/dev/mapper",
                                                os.readlink("/dev/mapper/%s%s" % (vg_name, "-%s" % (lv_name) if lv_name is not None else ""))))
                                        dev_dict.setdefault("/dev/mapper/%s" % (vg_name), {})[lv_name] = {
                                            "    mountpoint" : mp,
                                            "fstype"     : fstype,
                                            "options"    : opts,
                                            "dump"       : dump,
                                            "fsck"       : fsck,
                                            "multipath"  : dm_struct,
                                            "dm_name"    : dm_name,
                                            "lut"        : my_disk_lut[dm_name],
                                        }
                                    else:
                                        if "lv" in self.local_lvm_info.lv_dict:
                                            act_lv = self.local_lvm_info.lv_dict["lv"][lv_name]
                                            act_lv["mount_options"] = {
                                                "mountpoint" : mp,
                                                "fstype"     : fstype,
                                                "options"    : opts,
                                                "dump"       : dump,
                                                "fsck"       : fsck}
                            else:
                                dev, part_num = part_lut[part]
                                dev_dict[dev][part_num]["mountpoint"] = mp
                                dev_dict[dev][part_num]["fstype"] = fstype
                                dev_dict[dev][part_num]["options"] = opts
                                dev_dict[dev][part_num]["dump"] = dump
                                dev_dict[dev][part_num]["fsck"] = fsck
                                if not dev_dict[dev][part_num]["info"]:
                                    if fstype not in ["swap"]:
                                        dev_dict[dev][part_num]["hextype"] = "0x83"
                                        dev_dict[dev][part_num]["info"] = "Linux"
                                    else:
                                        dev_dict[dev][part_num]["hextype"] = "0x82"
                                        dev_dict[dev][part_num]["info"] = "Linux swap / Solaris"
                                # add lookup
                                dev_dict[dev][part_num]["lut"] = my_disk_lut[part]
                        else:
                            if part == mp:
                                part = "none"
                            if not sys_dict.has_key(part) or not any([entry["mountpoint"] == mp for entry in sys_dict[part]]):
                                sys_dict.setdefault(part, []).append({
                                    "mountpoint" : mp,
                                    "fstype"     : fstype,
                                    "options"    : opts})
                                sys_mounts.append((part, mp, fstype, opts))
                    ret_str = ""
        return ret_str, dev_dict, sys_dict

class df_command(hm_classes.hm_command):
    def __init__(self, name):
        hm_classes.hm_command.__init__(self, name, positional_arguments=True)
        self.parser.add_argument("-w", dest="warn", type=float)
        self.parser.add_argument("-c", dest="crit", type=float)
        self.__disk_lut = partition_tools.disk_lut()
    def __call__(self, srv_com, cur_ns):
        if not "arguments:arg0" in srv_com:
            srv_com["result"].attrib.update({
                "reply" : "missing argument",
                "state" : "%d" % (server_command.SRV_REPLY_STATE_ERROR)})
        else:
            disk = srv_com["arguments:arg0"].text.strip()
            orig_disk = disk
            if disk.startswith("/dev/mapper"):
                # follow mapper links
                if os.path.islink(disk):
                    disk = os.path.normpath(os.path.join(os.path.dirname(disk),
                                                         os.readlink(disk)))
            if disk.startswith("/dev/disk/by-"):
                try:
                    mapped_disk = self.__disk_lut[disk]
                except:
                    mapped_disk = "not found"
            else:
                mapped_disk = disk
            try:
                n_dict = self.module._df_int()
            except:
                srv_com["result"].attrib.update({
                    "reply" : "error reading mtab: %s" % (process_tools.get_except_info()),
                    "state" : "%d" % (server_command.SRV_REPLY_STATE_ERROR)})
            else:
                if disk == "ALL":
                    srv_com["df_result"] = dict([(disk, {
                        "mountpoint" : n_dict[disk]["mountpoint"],
                        "perc"       : n_dict[disk]["b_free_perc"],
                        "used"       : n_dict[disk]["b_used"],
                        "total"      : n_dict[disk]["b_size"]}) for disk in n_dict.keys()])
                else:
                    store_info = True
                    if not mapped_disk in n_dict:
                        # id is just a guess, FIXME
                        try:
                            all_maps = self.__disk_lut["id"][mapped_disk]
                        except KeyError:
                            store_info = False
                            srv_com["result"].attrib.update({
                                "reply" : "invalid partition %s (key is %s)" % (
                                    disk,
                                    mapped_disk),
                                "state" : "%d" % (server_command.SRV_REPLY_STATE_ERROR)})
                        else:
                            disk_found = False
                            for mapped_disk in ["/dev/disk/by-id/%s" % (cur_map) for cur_map in all_maps]:
                                if mapped_disk in n_dict:
                                    disk_found = True
                                    break
                            if not disk_found:
                                store_info = False
                                srv_com["result"].attrib.update({
                                    "reply" : "invalid partition %s" % (disk),
                                    "state" : "%d" % (server_command.SRV_REPLY_STATE_ERROR)})
                    if store_info:
                        mapped_info = n_dict[mapped_disk]
                        cur_fs = mapped_info["fs"]
                        res_dict = {
                            "part"        : disk,
                            "mapped_disk" : mapped_disk,
                            "orig_disk"   : orig_disk,
                            "mountpoint"  : mapped_info["mountpoint"],
                            "perc"        : mapped_info["b_free_perc"],
                            "used"        : mapped_info["b_used"],
                            "total"       : mapped_info["b_size"],
                            "i_size"      : mapped_info["i_size"],
                            "i_free"      : mapped_info["i_free"],
                            "i_avail"     : mapped_info["i_avail"],
                            "fs"          : cur_fs,
                        }
                        if cur_fs == "btrfs" and self.module.btrfs_path:
                            cur_stat, cur_out = commands.getstatusoutput("%s fi df %s" % (self.module.btrfs_path, mapped_info["mountpoint"]))
                            if not cur_stat:
                                btrfs_info = {}
                                for line in cur_out.lower().strip().split("\n"):
                                    l_type, l_data = line.split(":")
                                    l_type, l_data = (l_type.split(","), l_data.split(","))
                                    l_type = [entry.strip() for entry in l_type if entry.strip()]
                                    l_data = [entry.strip().split("=") for entry in l_data if entry.strip()]
                                    l_data = dict([(key, logging_tools.interpret_size_str(value)) for key, value in l_data])
                                    btrfs_info[":".join(l_type)] = l_data
                                res_dict["btrfs_info"] = btrfs_info
                        srv_com["df_result"] = res_dict
    def interpret(self, srv_com, cur_ns):
        result = srv_com["df_result"]
        # print result
        if result.has_key("perc"):
            # single-partition result
            ret_state = limits.check_ceiling(result["perc"], cur_ns.warn, cur_ns.crit)
            if result.get("i_size", 0):
                # inode info present ?
                inode_perc = float(100. * (float(result["i_size"] - result["i_avail"]) / float(result["i_size"])))
                ret_state = max(ret_state, limits.check_ceiling(inode_perc, cur_ns.warn, cur_ns.crit))
            other_keys = []
            for key in ["mapped_disk", "orig_disk"]:
                if key in result and result[key] != result["part"]:
                    other_keys.append(result[key])
            part_str = "%s%s" % (
                result["part"],
                " (%s)" % (", ".join(other_keys)) if other_keys else "",
                )
            if "btrfs_info" in result:
                # check for btrfs info
                btrfs_dict = result["btrfs_info"]
                # only check metadata (and dup) for now
                btrfs_result = {}
                for key, value in btrfs_dict.iteritems():
                    key = key.split(":")
                    r_key = key[0]
                    mult = 2 if (len(key) == 2 and key[1] == "dup") else 1
                    loc_dict = btrfs_result.setdefault(r_key, {})
                    for s_key, s_value in value.iteritems():
                        if s_key not in loc_dict:
                            loc_dict[s_key] = 0
                        loc_dict[s_key] += mult * s_value
                for res_key in ["used", "total"]:
                    btrfs_result[res_key] = sum([value[res_key] for value in btrfs_result.itervalues() if type(value) == dict])
                # report used data as total system + total metadata + used data
                result["used"] = (
                    btrfs_result["system"]["total"] +
                    btrfs_result["metadata"]["total"] +
                    btrfs_result["data"]["used"]
                    ) / 1024
                # recalc perc
                result["perc"] = result["used"] * 100 / result["total"]
                # add an asterisk to show the df-info as recalced
                result["fs"] = "%s*" % (result["fs"])
            if "i_size" in result:
                if result["i_size"]:
                    inode_str = "%.2f%% (%d of %d)" % (
                        inode_perc,
                        result["i_size"] - result["i_avail"],
                        result["i_size"],
                        )
                else:
                    inode_str = "no info"
            else:
                inode_str = ""
            return ret_state, u"%.0f %% used (%s of %s%s%s)%s on %s | total=%d used=%d free=%d" % (
                result["perc"],
                logging_tools.get_size_str(result["used"] * 1024, strip_spaces=True),
                logging_tools.get_size_str(result["total"] * 1024, strip_spaces=True),
                ", mp %s" % (result["mountpoint"]) if "mountpoint" in result else "",
                ", %s" % (result["fs"]) if "fs" in result else "",
                ", inode: %s" % (inode_str) if inode_str else "",
                part_str,
                (result["total"]) * 1024,
                (result["used"]) * 1024,
                (result["total"] - result["used"]) * 1024,
            )
        else:
            if result:
                # all-partition result
                max_stuff = {"perc" :-1}
                all_parts = sorted(result.keys())
                for part_name in all_parts:
                    d_stuff = result[part_name]
                    if d_stuff["perc"] > max_stuff["perc"]:
                        max_stuff = d_stuff
                        max_part = part_name
                ret_state = limits.check_ceiling(max_stuff["perc"], cur_ns.warn, cur_ns.crit)
                return ret_state, "%.0f %% used on %s (%s, %s)" % (
                    max_stuff["perc"],
                    max_part,
                    max_stuff["mountpoint"],
                    logging_tools.get_plural("partition", len(all_parts)))
            else:
                return limits.nag_STATE_CRITICAL, "no partitions found"
    def interpret_old(self, result, parsed_coms):
        result = hm_classes.net_to_sys(result[3:])
        if result.has_key("perc"):
            # single-partition result
            ret_state = limits.check_ceiling(result["perc"], parsed_coms.warn, parsed_coms.crit)
            if result.has_key("mapped_disk"):
                part_str = "%s (is %s)" % (result["mapped_disk"], result["part"])
            else:
                part_str = result["part"]
            return ret_state, "%.0f %% (%s of %s%s) used on %s" % (
                result["perc"],
                logging_tools.get_size_str(result["used"] * 1024, strip_spaces=True),
                logging_tools.get_size_str(result["total"] * 1024, strip_spaces=True),
                ", mp %s" % (result["mountpoint"]) if result.has_key("mountpoint") else "",
                part_str)
        else:
            # all-partition result
            max_stuff = {"perc" :-1}
            all_parts = sorted(result.keys())
            for part_name in all_parts:
                d_stuff = result[part_name]
                if d_stuff["perc"] > max_stuff["perc"]:
                    max_stuff = d_stuff
                    max_part = part_name
            ret_state = limits.check_ceiling(max_stuff["perc"], parsed_coms.warn, parsed_coms.crit)
            return ret_state, "%.0f %% used on %s (%s, %s)" % (
                max_stuff["perc"],
                max_part,
                max_stuff["mountpoint"],
                logging_tools.get_plural("partition", len(all_parts)))

class version_command(hm_classes.hm_command):
    def __call__(self, srv_com, cur_ns):
        srv_com["version"] = VERSION_STRING
    def interpret(self, srv_com, cur_ns):
        try:
            return limits.nag_STATE_OK, "version is %s" % (srv_com["version"].text)
        except:
            return limits.nag_STATE_CRITICAL, "version not found"
    def interpret_old(self, result, parsed_coms):
        act_state = limits.nag_STATE_OK
        return act_state, "version is %s" % (result)

class get_0mq_id_command(hm_classes.hm_command):
    def __call__(self, srv_com, cur_ns):
        zmq_id_name = "/etc/sysconfig/host-monitoring.d/0mq_id"
        if os.path.isfile(zmq_id_name):
            zmq_id_xml = etree.fromstring(file(zmq_id_name, "r").read())
            id_node = None
            if "target_ip" in srv_com:
                target_ip = srv_com["target_ip"].text
            else:
                target_ip = "*"
            self.log("target_ip for get_0mq_id is %s" % (target_ip))
            if target_ip != "*":
                id_node = zmq_id_xml.xpath(".//zmq_id[@bind_address='%s']" % (target_ip), smart_strings=False)
                id_node = id_node[0] if len(id_node) else None
            if id_node is None:
                id_node = zmq_id_xml.xpath(".//zmq_id[@bind_address='*']", smart_strings=False)
                id_node = id_node[0] if len(id_node) else None
            if id_node is not None:
                srv_com["zmq_id"] = id_node.text
            else:
                srv_com["result"].attrib.update({"reply" : "no matching 0MQ id found for ip %s" % (target_ip),
                                                 "state" : "%d" % (server_command.SRV_REPLY_STATE_ERROR)})
        else:
            srv_com["result"].attrib.update({"reply" : "no 0MQ_id file found",
                                             "state" : "%d" % (server_command.SRV_REPLY_STATE_ERROR)})
    def interpret(self, srv_com, cur_ns):
        try:
            return limits.nag_STATE_OK, "0MQ id is %s" % (srv_com["zmq_id"].text)
        except:
            return limits.nag_STATE_CRITICAL, "version not found"

class status_command(hm_classes.hm_command):
    def __call__(self, srv_com, cur_ns):
        srv_com["status_str"] = "ok running"
    def interpret(self, srv_com, cur_ns):
        try:
            return limits.nag_STATE_OK, "status is %s" % (srv_com["status_str"].text)
        except:
            return limits.nag_STATE_CRITICAL, "status unknown"
    def interpret_old(self, result, parsed_coms):
        act_state = limits.nag_STATE_OK
        return act_state, "status is %s" % (result)

class get_uuid_command(hm_classes.hm_command):
    def __call__(self, srv_com, cur_ns):
        srv_com["uuid"] = uuid_tools.get_uuid().get_urn()
    def interpret(self, srv_com, cur_ns):
        try:
            return limits.nag_STATE_OK, "uuid is %s" % (srv_com["uuid"].text)
        except:
            return limits.nag_STATE_CRITICAL, "uuid not found"
    def interpret_old(self, result, parsed_coms):
        act_state = limits.nag_STATE_OK
        return act_state, "uuid is %s" % (result.split()[1])

class swap_command(hm_classes.hm_command):
    def __init__(self, name):
        hm_classes.hm_command.__init__(self, name, positional_arguments=False)
        self.parser.add_argument("-w", dest="warn", type=float)
        self.parser.add_argument("-c", dest="crit", type=float)
    def __call__(self, srv_com, cur_ns):
        _virt_info, swap_info = self.module._mem_int()
        srv_com["swap"] = dict(swap_info._asdict())
    def interpret(self, srv_com, cur_ns):
        if "swap" in srv_com:
            # new style with psutil
            _fac = 1
            swap_dict = srv_com["swap"]
            swap_total, swap_free = (swap_dict["total"], swap_dict["free"])
        else:
            # old style
            _fac = 1024
            swap_dict = srv_com["mem"]
            swap_total, swap_free = (swap_dict["SwapTotal"], swap_dict["SwapFree"])
        if swap_total == 0:
            return limits.nag_STATE_CRITICAL, "no swap space found"
        else:
            swap = 100 * float(swap_total - swap_free) / swap_total
            ret_state = limits.check_ceiling(swap, cur_ns.warn , cur_ns.crit)
            return ret_state, "swapinfo: %d %% of %s swap" % (
                swap,
                logging_tools.get_size_str(swap_total * _fac, strip_spaces=True),
            )
    def interpret_old(self, result, parsed_coms):
        result = hm_classes.net_to_sys(result[3:])
        swaptot, swapfree = (int(result["swaptotal"]),
                             int(result["swapfree"]))
        if swaptot == 0:
            return limits.nag_STATE_CRITICAL, "%s: no swap space found" % (limits.get_state_str(limits.nag_STATE_CRITICAL))
        else:
            swap = 100 * (swaptot - swapfree) / swaptot
            ret_state = limits.check_ceiling(swap, parsed_coms.warn, parsed_coms.crit)
            return ret_state, "swapinfo: %d %% of %s swap" % (
                swap,
                logging_tools.get_size_str(swaptot * 1024, strip_spaces=True),
                )

class mem_command(hm_classes.hm_command):
    def __init__(self, name):
        hm_classes.hm_command.__init__(self, name, positional_arguments=False)
        self.parser.add_argument("-w", dest="warn", type=float)
        self.parser.add_argument("-c", dest="crit", type=float)
    def __call__(self, srv_com, cur_ns):
        virt_info, swap_info = self.module._mem_int()
        srv_com["mem"] = dict(virt_info._asdict())
        srv_com["swap"] = dict(swap_info._asdict())
    def interpret(self, srv_com, cur_ns):
        mem_dict = srv_com["mem"]
        if "swap" in srv_com:
            swap_dict = srv_com["swap"]
        else:
            swap_dict = None
        if swap_dict is None:
            # old format (without psutil)
            buffers = mem_dict["Buffers"]
            cached = mem_dict["Cached"]
            mem_total, mem_free = (
                mem_dict["MemTotal"],
                mem_dict["MemFree"],
            )
            swap_total, swap_free = (
                mem_dict["SwapTotal"],
                mem_dict["SwapFree"],
            )
            _fact = 1024
        else:
            print mem_dict, swap_dict
            buffers = mem_dict["buffers"]
            cached = mem_dict["cached"]
            mem_total, mem_free = (
                mem_dict["total"],
                mem_dict["free"],
            )
            swap_total, swap_free = (
                swap_dict["total"],
                swap_dict["free"],
            )
            _fact = 1
        all_total = mem_total + swap_total
        all_free = mem_free + swap_free
        mem_p = 100 * (1 if mem_total == 0 else float(mem_total - mem_free) / mem_total)
        # swap_p = 100 * (1 if swap_total == 0 else float(swap_total - swap_free) / swap_total)
        all_p = 100 * (1 if all_total == 0 else float(all_total - all_free) / all_total)
        ret_state = limits.check_ceiling(all_p, cur_ns.warn, cur_ns.crit)
        return ret_state, "meminfo: %d %% of %s phys, %d %% of %s tot (%s buffers, %s cached)" % (
            mem_p,
            logging_tools.get_size_str(mem_total * _fact, strip_spaces=True),
            all_p,
            logging_tools.get_size_str(all_total * _fact, strip_spaces=True),
            logging_tools.get_size_str(buffers * _fact, strip_spaces=True),
            logging_tools.get_size_str(cached * _fact, strip_spaces=True),
        )
    def interpret_old(self, result, parsed_coms):
        result = hm_classes.net_to_sys(result[3:])
        memtot = int(result["memtotal"])
        memfree = int(result["memfree"]) + int(result["buffers"]) + int(result["cached"])
        if memtot == 0:
            memp = 100
        else:
            memp = 100 * (memtot - memfree) / memtot
        swaptot = int(result["swaptotal"])
        swapfree = int(result["swapfree"])
        # if swaptot == 0:
        #    swapp = 100
        # else:
        #    swapp = 100 * (swaptot - swapfree) / swaptot
        alltot = memtot + swaptot
        allfree = memfree + swapfree
        if alltot == 0:
            allp = 100
        else:
            allp = 100 * (alltot - allfree) / alltot
        ret_state = limits.check_ceiling(max(allp, memp), parsed_coms.warn, parsed_coms.crit)
        return ret_state, "meminfo: %d %% of %s phys, %d %% of %s tot" % (
            memp,
            logging_tools.get_size_str(memtot * 1024),
            allp,
            logging_tools.get_size_str(alltot * 1024))

class sysinfo_command(hm_classes.hm_command):
    def __init__(self, name):
        hm_classes.hm_command.__init__(self, name, positional_arguments=True)
    def __call__(self, srv_com, cur_ns):
        root_dir = srv_com.get("arguments:arg0", "/")
        log_lines, sys_dict = process_tools.fetch_sysinfo(root_dir)
        for log_line, log_lev in log_lines:
            self.log(log_line, log_lev)
        imi_file = "/%s/.imageinfo" % (root_dir)
        if os.path.isfile(imi_file):
            srv_com["imageinfo"] = dict([(key.strip(), value.strip()) for key, value in [line.strip().lower().split("=", 1) for line in open(imi_file, "r").readlines() if line.count("=")]])
        srv_com["sysinfo"] = sys_dict
    def interpret(self, srv_com, cur_ns):
        need_keys = set(["vendor", "version", "arch"])
        miss_keys = [key for key in need_keys if not "sysinfo:%s" % (key) in srv_com]
        if miss_keys:
            return limits.nag_STATE_CRITICAL, "%s missing : %s" % (logging_tools.get_plural("key", len(miss_keys)), ", ".join(miss_keys))
        else:
            ret_str = "Distribution is %s version %s on an %s" % (
                srv_com["sysinfo:vendor"].text,
                srv_com["sysinfo:version"].text,
                srv_com["sysinfo:arch"].text)
            if "imageinfo" in srv_com:
                if "imageinfo:image_name" in srv_com and "imageinfo:image_version" in srv_com:
                    ret_str += ", image is %s (version %s)" % (srv_com["imageinfo:image_name"].text, srv_com["imageinfo:image_version"].text)
                else:
                    ret_str += ", no image info"
            return limits.nag_STATE_OK, ret_str
    def interpret_old(self, result, parsed_coms):
        result = hm_classes.net_to_sys(result[3:])
        need_keys = ["vendor", "version", "arch"]
        mis_keys = [k for k in need_keys if not result.has_key(k)]
        if mis_keys:
            return limits.nag_STATE_CRITICAL, "%s missing : %s" % (logging_tools.get_plural("key", len(mis_keys)), ", ".join(mis_keys))
        else:
            ret_str = "Distribution is %s version %s on an %s" % (result["vendor"], result["version"], result["arch"])
            if "imageinfo" in result.keys():
                ii_dict = result["imageinfo"]
                if ii_dict.has_key("image_name") and ii_dict.has_key("image_version"):
                    ret_str += ", image is %s (version %s)" % (ii_dict["image_name"], ii_dict["image_version"])
                else:
                    ret_str += ", no image info"
            return limits.nag_STATE_OK, ret_str

class load_command(hm_classes.hm_command):
    info_string = "load information"
    def __init__(self, name):
        hm_classes.hm_command.__init__(self, name, positional_arguments=False)
        self.parser.add_argument("-w", dest="warn", type=float)
        self.parser.add_argument("-c", dest="crit", type=float)
    def __call__(self, srv_com, cur_ns):
        cur_load = self.module._load_int()
        srv_com["load1"] = "%.2f" % (cur_load[0])
        srv_com["load5"] = "%.2f" % (cur_load[1])
        srv_com["load15"] = "%.2f" % (cur_load[2])
    def interpret(self, srv_com, cur_ns):
        load_1, load_5, load_15 = (
            float(srv_com["load1"].text),
            float(srv_com["load5"].text),
            float(srv_com["load15"].text))
        max_load = max([load_1, load_5, load_15])
        ret_state = limits.nag_STATE_OK
        if cur_ns.warn is not None:
            ret_state = max(ret_state, limits.nag_STATE_WARNING if max_load >= cur_ns.warn else limits.nag_STATE_OK)
        if cur_ns.crit is not None:
            ret_state = max(ret_state, limits.nag_STATE_CRITICAL if max_load >= cur_ns.crit else limits.nag_STATE_OK)
        return ret_state, "load (1/5/15): %.2f %.2f %.2f | load1=%.2f load5=%.2f load15=%.2f" % (
            load_1, load_5, load_15,
            load_1, load_5, load_15
        )
    def interpret_old(self, result, parsed_coms):
        result = hm_classes.net_to_sys(result[3:])
        load1 = float(result["load1"])
        load5 = float(result["load5"])
        load15 = float(result["load15"])
        maxload = max(load1, load5, load15)
        ret_state = limits.check_ceiling(maxload, parsed_coms.warn, parsed_coms.crit)
        ret_str = "load (1/5/15): %.2f %.2f %.2f" % (load1, load5, load15)
        return ret_state, ret_str

class uptime_command(hm_classes.hm_command):
    info_string = "update information"
    def __call__(self, srv_com, cur_ns):
        upt_data = [int(float(value)) for value in open("/proc/uptime", "r").read().strip().split()]
        srv_com["uptime"] = "%d" % (upt_data[0])
        if len(upt_data) > 1:
            srv_com["idle"] = "%d" % (upt_data[1])
    def interpret(self, srv_com, cur_ns):
        uptime_int = int(srv_com["uptime"].text)
        up_m = int(uptime_int) / 60
        up_d = int(up_m / (60 * 24))
        up_h = int((up_m - up_d * (60 * 24)) / 60)
        up_m = up_m - 60 * (up_d * 24 + up_h)
        return limits.nag_STATE_OK, "up for %s, %d:%02d" % (
            logging_tools.get_plural("day", up_d),
            up_h,
            up_m)
    def interpret_old(self, result, parsed_coms):
        result = hm_classes.net_to_sys(result[3:])
        return limits.nag_STATE_OK, "up for %s days, %s hours and %s mins" % (result["up_days"], result["up_hours"], result["up_minutes"])

class date_command(hm_classes.hm_command):
    info_string = "return date"
    def __call__(self, srv_com, cur_ns):
        srv_com["local_time"] = int(time.time())
    def interpret(self, srv_com, cur_ns):
        warn_diff, err_diff = (10, 5 * 60)
        local_date = time.time()
        remote_date = int(srv_com["local_time"].text)
        diff_time = int(abs(remote_date - local_date))
        if diff_time > err_diff:
            return limits.nag_STATE_CRITICAL, "%s (diff %d > %d seconds)" % (
                time.ctime(remote_date),
                diff_time,
                err_diff)
        elif diff_time > warn_diff:
            return limits.nag_STATE_WARNING, "%s (diff %d > %d seconds)" % (
                time.ctime(remote_date),
                diff_time,
                warn_diff)
        else:
            return limits.nag_STATE_OK, "%s" % (time.ctime(remote_date))
    def interpret_old(self, result, parsed_coms):
        warn_diff, err_diff = (10, 5 * 60)
        local_date = time.time()
        remote_date = hm_classes.net_to_sys(result[3:])["date"]
        if type(remote_date) == type(""):
            remote_date = time.mktime(time.strptime(remote_date))
        diff_time = int(abs(remote_date - local_date))
        if diff_time > err_diff:
            return limits.nag_STATE_CRITICAL, "%s (diff %d > %d seconds)" % (
                time.ctime(remote_date),
                diff_time,
                err_diff)
        elif diff_time > warn_diff:
            return limits.nag_STATE_WARNING, "%s (diff %d > %d seconds)" % (
                time.ctime(remote_date),
                diff_time,
                warn_diff)
        else:
            return limits.nag_STATE_OK, "%s" % (time.ctime(remote_date))

class macinfo_command(hm_classes.hm_command):
    def __call__(self, srv_com, cur_ns):
        valid_devs = ["eth", "myri", "ib", "vmnet"]
        net_dict = {}
        try:
            net_dir = "/sys/class/net"
            if os.path.isdir(net_dir):
                for net in [entry for entry in os.listdir(net_dir) if [True for postfix in valid_devs if entry.startswith(postfix)]]:
                    addr_file = "%s/%s/address" % (net_dir, net)
                    if os.path.isfile(addr_file):
                        net_dict[net.lower()] = open(addr_file, "r").read().strip().lower()
            else:
                c_stat, out = commands.getstatusoutput("ip link show")
                if not c_stat:
                    # ip link show successfull
                    head_match = re.compile("^(?P<idx>\d+):\s+(?P<devname>\S+):.*$")
                    tail_match = re.compile("^\s*(?P<bla>\S+)/(?P<blub>\S+)\s+(?P<macadr>\S+).*$")
                    act_name, act_mac = (None, None)
                    for hm, tm in [(head_match.match(entry), tail_match.match(entry)) for entry in [line.rstrip() for line in out.split("\n")]]:
                        if hm:
                            act_name, act_mac = (hm.group("devname").lower(), None)
                        elif tm:
                            act_mac = tm.group("macadr").lower()
                        if act_name and act_mac:
                            if [True for x in valid_devs if act_name.startswith(x)] and len(act_name.split(":")) == 1:
                                net_dict[act_name] = act_mac
                            act_name, act_mac = (None, None)
                else:
                    # try via ifconfig
                    net_match = re.compile("(?P<devname>\S+)\s+.*addr\s+(?P<macadr>\S+)\s*$")
                    c_stat, out = commands.getstatusoutput("/sbin/ifconfig -a")
                    if not c_stat:
                        for act_name, act_mac in [(entry.group("devname").lower(), entry.group("macadr").lower()) for entry in [net_match.match(line.strip()) for line in out.split("\n")] if entry]:
                            if [True for postfix in valid_devs if act_name.startswith(postfix)] and len(act_name.split(":")) == 1:
                                net_dict[act_name] = act_mac
        except:
            pass
        srv_com["macinfo"] = net_dict
    def interpret(self, srv_com, cur_ns):
        if "macinfo" in srv_com:
            mac_list = []
            for sub_el in sorted(srv_com["macinfo"].iterkeys()):
                mac_list.append("%s (%s)" % (sub_el, srv_com["macinfo"][sub_el]))
            return limits.nag_STATE_OK, "%s: %s" % (logging_tools.get_plural("device", len(mac_list)),
                                                    ", ".join(sorted(mac_list)))
        else:
            return limits.nag_STATE_CRITICAL, "no macaddresses found"
    def interpret_old(self, result, parsed_coms):
        if result.startswith("ok"):
            net_dict = hm_classes.net_to_sys(result[3:])
            return limits.nag_STATE_OK, "%d ether-devices found: %s" % (len(net_dict.keys()), ", ".join(["%s (%s)" % (k, net_dict[k]) for k in net_dict.keys()]))
        else:
            return limits.nag_STATE_CRITICAL, "error parsing return"

class umount_command(hm_classes.hm_command):
    def __init__(self, name):
        hm_classes.hm_command.__init__(self, name, positional_arguments=True)
    def __call__(self, srv_com, cur_ns):
        ignore_list = (srv_com["arguments:rest"].text or "").strip().split()
        mount_dict = get_nfs_mounts()
        auto_list = [m_point for src, m_point in mount_dict.get("autofs", [])]
        srv_com["umount_list"] = []
        if mount_dict and auto_list:
            for src, m_point in mount_dict.get("nfs", []) + mount_dict.get("nfs4", []) + mount_dict.get("nfs3", []):
                # mount points must not be in ignore list and have to be below an automount-directory
                if not (any([m_point.startswith(ignore_part) for ignore_part in ignore_list]) or any([m_point.startswith(a_mpoint) for a_mpoint in auto_list])):
                    self.log("trying to umount %s (source is %s)" % (m_point, src))
                    um_stat, um_out = commands.getstatusoutput("umount %s" % (m_point))
                    cur_umount_node = srv_com.builder("umount_result", m_point, src=src, error="0")
                    if um_stat:
                        cur_umount_node.attrib.update({"error"  : "1",
                                                       "status" : "%d" % (um_stat),
                                                       "log"    : " ".join([cur_line.strip() for cur_line in um_out.split("\n")])})
                        self.log("umounting %s: %s (%d)" % (m_point, cur_umount_node.attrib["log"], um_stat),
                                 logging_tools.LOG_LEVEL_ERROR)
                    else:
                        self.log("ok umounting %s" % (m_point))
                    srv_com["umount_list"].append(cur_umount_node)
    def interpret(self, srv_com, cur_ns):
        ok_list, error_list = (srv_com.xpath(".//ns:umount_result[@error='0']", smart_strings=False),
                               srv_com.xpath(".//ns:umount_result[@error='1']", smart_strings=False))
        return limits.nag_STATE_CRITICAL if error_list else limits.nag_STATE_OK, \
               "".join([
                   "tried to unmount %s" % (logging_tools.get_plural("entry", len(ok_list) + len(error_list))),
                   ", ok: %s" % (",".join([ok_node.text for ok_node in ok_list])) if ok_list else "",
                   ", error: %s" % (",".join([error_node.text for error_node in error_list])) if error_list else "",
               ])

class ksminfo_command(hm_classes.hm_command):
    def __call__(self, srv_com, cur_ns):
        ksm_dir = "/sys/kernel/mm/ksm"
        if os.path.isdir(ksm_dir):
            srv_com["ksm"] = dict([(entry, file(os.path.join(ksm_dir, entry), "r").read().strip()) for entry in os.listdir(ksm_dir)])
        else:
            srv_com["ksm"] = "not found"
    def interpret(self, srv_com, cur_ns):
        ksm_info = srv_com["ksm"]
        if type(ksm_info) == dict:
            page_size = 4096
            ksm_info = dict([(key, int(value) * page_size if value.isdigit() else value) for key, value in ksm_info.iteritems()])
            if ksm_info["run"]:
                info_field = [
                    "%s shared" % (logging_tools.get_size_str(ksm_info["pages_shared"], strip_spaces=True)),
                    "%s saved" % (logging_tools.get_size_str(ksm_info["pages_sharing"], strip_spaces=True)),
                    "%s volatile" % (logging_tools.get_size_str(ksm_info["pages_volatile"], strip_spaces=True)),
                    "%s unshared" % (logging_tools.get_size_str(ksm_info["pages_unshared"], strip_spaces=True))
                ]
                return limits.nag_STATE_OK, "KSM info: %s" % (", ".join(info_field))
            else:
                return limits.nag_STATE_WARNING, "KSM available but not enabled"
        else:
            return limits.nag_STATE_CRITICAL, "ksm problem: %s" % (ksm_info.text)

class hugepageinfo_command(hm_classes.hm_command):
    def __call__(self, srv_com, cur_ns):
        hpage_dir = "/sys/kernel/mm/hugepages"
        if os.path.isdir(hpage_dir):
            srv_com["hpages"] = dict([(entry, dict([(sub_entry, file(os.path.join(hpage_dir, entry, sub_entry), "r").read().strip()) for sub_entry in os.listdir(os.path.join(hpage_dir, entry))])) for entry in os.listdir(hpage_dir)])
        else:
            srv_com["hpages"] = "not found"
    def interpret(self, srv_com, cur_ns):
        hpage_info = srv_com["hpages"]
        if type(hpage_info) == dict:
            ret_state = limits.nag_STATE_OK
            info_field = []
            for page_dir, page_dict in hpage_info.iteritems():
                local_size = page_dir.split("-")[-1].lower()
                if local_size.endswith("kb"):
                    local_size = int(local_size[:-2]) * 1024
                elif local_size.endswith("mb"):
                    local_size = int(local_size[:-2]) * 1024 * 1024
                elif local_size.endswith("gb"):
                    local_size = int(local_size[:-2]) * 1024 * 1024 * 1024
                else:
                    local_size = None
                    info_field.append("cannot interpret %s" % (local_size))
                    ret_state = max(ret_state, limits.nag_STATE_CRITICAL)
                if local_size is not None:
                    hpage_info = dict([(key, int(value) * local_size if value.isdigit() else value) for key, value in page_dict.iteritems()])
                    info_field.append("%s: %s reserved, %s used" % (
                        logging_tools.get_size_str(local_size, strip_spaces=True),
                        logging_tools.get_size_str(hpage_info["nr_hugepages"], strip_spaces=True),
                        logging_tools.get_size_str(hpage_info["nr_hugepages"] - hpage_info["free_hugepages"], strip_spaces=True)))
            return ret_state, "hugepage info: %s" % (", ".join(info_field))
        else:
            return limits.nag_STATE_CRITICAL, "hugepage problem: %s" % (hpage_info.text)

class thugepageinfo_command(hm_classes.hm_command):
    def __call__(self, srv_com, cur_ns):
        hpage_dir = "/sys/kernel/mm/transparent_hugepage"
        if os.path.isdir(hpage_dir):
            sub_dirs = ["khugepaged"]
            srv_com["thpagef"] = dict([(entry, file(os.path.join(hpage_dir, entry), "r").read().strip()) for entry in os.listdir(hpage_dir) if entry not in sub_dirs])
            srv_com["thpaged"] = dict([(entry, file(os.path.join(hpage_dir, sub_dirs[0], entry), "r").read().strip()) for entry in os.listdir(os.path.join(hpage_dir, sub_dirs[0]))])
        else:
            srv_com["thpagef"] = "not found"
            srv_com["thpaged"] = "not found"
    def interpret(self, srv_com, cur_ns):
        thpage_f_info = srv_com["thpagef"]
        thpage_d_info = srv_com["thpaged"]
        if type(thpage_f_info) == dict:
            enable_state = [entry[1:-1] for entry in thpage_f_info["enabled"].strip().split() if entry.startswith("[")][0]
            defrag_state = [entry[1:-1] for entry in thpage_f_info["defrag"].strip().split() if entry.startswith("[")][0]
            if enable_state in ["always", "madvise"]:
                ret_state = limits.nag_STATE_OK
                ret_str = "info: enable=%s, defrag=%s, full_scans=%d, pages_to_scan=%d, collapsed: %d (%s), alloc/scan time: %.2f/%.2f secs" % (
                    enable_state,
                    defrag_state,
                    int(thpage_d_info["full_scans"]),
                    int(thpage_d_info["pages_to_scan"]),
                    int(thpage_d_info["pages_collapsed"]),
                    logging_tools.get_size_str(int(thpage_d_info["pages_collapsed"]) * 2 * 1024 * 1024, strip_spaces=True),
                    float(thpage_d_info["alloc_sleep_millisecs"]) / 1000.,
                    float(thpage_d_info["scan_sleep_millisecs"]) / 1000.,
                )
            else:
                ret_state, ret_str = (limits.nag_STATE_WARNING, "warning: enable=%s, defrag=%s" % (enable_state, defrag_state))
        else:
            ret_state, ret_str = (limits.nag_STATE_CRITICAL, "problem: %s, %s" % (thpage_d_info.text, thpage_f_info.text))
        return ret_state, "transparent hugepage %s" % (ret_str)

class pciinfo_command(hm_classes.hm_command):
    def __call__(self, srv_com, cur_ns):
        srv_com["pci"] = pci_database.get_actual_pci_struct(*pci_database.get_pci_dicts())
    def interpret(self, srv_com, cur_ns):
        def _short(in_tag):
            return in_tag.split("}")[1]
        def _short_tag(in_el):
            return int(_short(in_el.tag)[7:])
        cmr_b = []
        for domain in srv_com.get_element("pci")[0]:
            for bus in domain:
                for slot in bus:
                    for func in slot:
                        s_dict = dict([(_short(cur_el.tag), cur_el.text) for cur_el in func])
                        out_str = "%04x:%02x:%02x.%x %s: %s %s" % (_short_tag(domain), _short_tag(bus), _short_tag(slot), _short_tag(func),
                                                                   s_dict["subclassname"],
                                                                   s_dict["vendorname"],
                                                                   s_dict["devicename"])
                        if s_dict["revision"] != "00":
                            out_str = "%s (rev %s)" % (out_str, s_dict["revision"])
                        cmr_b.append(out_str)
        return limits.nag_STATE_OK, "\n".join(cmr_b)

class cpuflags_command(hm_classes.hm_command):
    def __call__(self, srv_com, cur_ns):
        srv_com["proclines"] = server_command.compress(file("/proc/cpuinfo", "r").read())
    def interpret(self, srv_com, cur_ns):
        # most likely source: http://www.softeng.rl.ac.uk/st/archive/SoftEng/SESP/html/SoftwareTools/vtune/users_guide/mergedProjects/analyzer_ec/mergedProjects/reference_olh/mergedProjects/instructions/instruct32_hh/vc46.htm
        flag_lut = {"FPU"    : "Floating Point Unit On-Chip. The processor contains an x87 FPU.",
                    "VME"    : "Virtual 8086 Mode Enhancements. Virtual 8086 mode enhancements, including CR4.VME for controlling the feature, CR4.PVI for protected mode virtual interrupts, software interrupt indirection, expansion of the TSS with the software indirection bitmap, and EFLAGS.VIF and EFLAGS.VIP flags.",
                    "DE"     : "Debugging Extensions. Support for I/O breakpoints, including CR4.DE for controlling the feature, and optional trapping of accesses to DR4 and DR5.",
                    "PSE"    : "Page Size Extension. Large pages of size 4Mbyte are supported, including CR4.PSE for controlling the feature, the defined dirty bit in PDE (Page Directory Entries), optional reserved bit trapping in CR3, PDEs, and PTEs.",
                    "TSC"    : "Time Stamp Counter. The RDTSC instruction is supported, including CR4.TSD for controlling privilege.",
                    "MSR"    : "Model Specific Registers RDMSR and WRMSR Instructions. The RDMSR and WRMSR instructions are supported. Some of the MSRs are implementation dependent.",
                    "PAE"    : "Physical Address Extension. Physical addresses greater than 32 bits are supported: extended page table entry formats, an extra level in the page translation tables is defined, 2 Mbyte pages are supported instead of 4 Mbyte pages if PAE bit is 1. The actual number of address bits beyond 32 is not defined, and is implementation specific.",
                    "MCE"    : "Machine Check Exception. Exception 18 is defined for Machine Checks, including CR4.MCE for controlling the feature. This feature does not define the model-specific implementations of machine-check error logging, reporting, and processor shutdowns. Machine Check exception handlers may have to depend on processor version to do model specific processing of the exception, or test for the presence of the Machine Check feature.",
                    "CX8"    : "CMPXCHG8B Instruction. The compare-and-exchange 8 bytes (64 bits) instruction is supported (implicitly locked and atomic).",
                    "APIC"   : "APIC On-Chip. The processor contains an Advanced Programmable Interrupt Controller (APIC), responding to memory mapped commands in the physical address range FFFE0000H to FFFE0FFFH (by default - some processors permit the APIC to be relocated).",
                    "SEP"    : "SYSENTER and SYSEXIT Instructions. The SYSENTER and SYSEXIT and associated MSRs are supported.",
                    "MTRR"   : "Memory Type Range Registers. MTRRs are supported. The MTRRcap MSR contains feature bits that describe what memory types are supported, how many variable MTRRs are supported, and whether fixed MTRRs are supported.",
                    "PGE"    : "PTE Global Bit. The global bit in page directory entries (PDEs) and page table entries (PTEs) is supported, indicating TLB entries that are common to different processes and need not be flushed. The CR4.PGE bit controls this feature.",
                    "MCA"    : "Machine Check Architecture. The Machine Check Architecture, which provides a compatible mechanism for error reporting in P6 family, Pentium 4, and Intel Xeon processors is supported. The MCG_CAP MSR contains feature bits describing how many banks of error reporting MSRs are supported.",
                    "CMOV"   : "Conditional Move Instructions. The conditional move instruction CMOV is supported. In addition, if x87 FPU is present as indicated by the CPUID.FPU feature bit, then the FCOMI and FCMOV instructions are supported.",
                    "PAT"    : "Page Attribute Table. Page Attribute Table is supported. This feature augments the Memory Type Range Registers (MTRRs), allowing an operating system to specify attributes of memory on a 4K granularity through a linear address.",
                    "PSE-36" : "32-Bit Page Size Extension. Extended 4-MByte pages that are capable of addressing physical memory beyond 4 GBytes are supported. This feature indicates that the upper four bits of the physical address of the 4-MByte page is encoded by bits 13-16 of the page directory entry.",
                    "PSN"    : "Processor Serial Number. The processor supports the 96-bit processor identification number feature and the feature is enabled.",
                    "CLFLSH" : "CLFLUSH Instruction. CLFLUSH Instruction is supported.",
                    "DS"     : "Debug Store. The processor supports the ability to write debug information into a memory resident buffer. This feature is used by the branch trace store (BTS) and precise event-based sampling (PEBS) facilities (see Chapter 15, Debugging and Performance Monitoring, in the IA-32 Intel Architecture Software Developer's Manual, Volume 3).",
                    "ACPI"   : "Thermal Monitor and Software Controlled Clock Facilities. The processor implements internal MSRs that allow processor temperature to be monitored and processor performance to be modulated in predefined duty cycles under software control.",
                    "MMX"    : "Intel MMX Technology. The processor supports the Intel MMX technology.",
                    "FXSR"   : "FXSAVE and FXRSTOR Instructions. The FXSAVE and FXRSTOR instructions are supported for fast save and restore of the floating point context. Presence of this bit also indicates that CR4.OSFXSR is available for an operating system to indicate that it supports the FXSAVE and FXRSTOR instructions.",
                    "SSE"    : "SSE. The processor supports the SSE extensions.",
                    "SSE2"   : "SSE2. The processor supports the SSE2 extensions.",
                    "SS"     : "Self Snoop. The processor supports the management of conflicting memory types by performing a snoop of its own cache structure for transactions issued to the bus.",
                    "HTT"    : "Hyper-Threading Technology. The processor implements Hyper-Threading technology.",
                    "TM"     : "Thermal Monitor. The processor implements the thermal monitor automatic thermal control circuitry (TCC).",
                    "PBE"    : "Pending Break Enable. The processor supports the use of the FERR#/PBE# pin when the processor is in the stop-clock state (STPCLK# is asserted) to signal the processor that an interrupt is pending and that the processor should return to normal operation to handle the interrupt. Bit 10 (PBE enable) in the IA32_MISC_ENABLE MSR enables this capability."}
        flag_dict = {}
        for line in server_command.decompress(srv_com["proclines"].text).split("\n"):
            if line.count(":"):
                key, value = [part.strip() for part in line.split(":", 1)]
                if key == "processor":
                    cpu_num = int(value)
                elif key == "flags":
                    flag_dict[cpu_num] = sorted(value.split())
        ret_lines = ["found %s:" % (logging_tools.get_plural("CPU", len(flag_dict.keys())))]
        for cpu_num in sorted(flag_dict.keys()):
            cpu_flags = flag_dict[cpu_num]
            ret_lines.append("CPU %2d: %s" % (cpu_num, logging_tools.get_plural("flag", len(cpu_flags))))
            for flag in cpu_flags:
                ret_lines.append("  %-15s : %s" % (flag, flag_lut.get(flag.upper(), flag)[:140]))
        ret_state = limits.nag_STATE_OK
        return ret_state, "\n".join(ret_lines)

class cpuinfo_command(hm_classes.hm_command):
    def __call__(self, srv_com, cur_ns):
        srv_com["cpuinfo"] = self.module._cpuinfo_int(srv_com)
    def interpret(self, srv_com, cur_ns):
        ret_state, pre_str = (limits.nag_STATE_OK, "OK")
        header_errors = []
        out_list = logging_tools.new_form_list()
        try:
            cpu_info = cpu_database.global_cpu_info(xml=srv_com.tree, parse=True)
        except:
            join_str, head_str = ("; ", "error decoding cpu_info: %s" % (process_tools.get_except_info()))
            exc_info = process_tools.exception_info()
            print "\n".join(exc_info.log_lines)
        else:
            for cpu in [cpu_info[cpu_idx] for cpu_idx in cpu_info.cpu_idxs()]:
                if cpu.get("online", True):
                    cpu_speed = cpu["speed"]
                    bnd_str = ""
                    # if cpu_range.has_boundaries_set():
                    #    if cpu_range.in_boundaries(cpu_speed):
                    #        bnd_str = "(in range [%d, %d])" % (cpu_range.get_lower_boundary(), cpu_range.get_upper_boundary())
                    #    else:
                    #        ret_state, pre_str = (limits.nag_STATE_CRITICAL, "Error")
                    #        bnd_str = "(not in range [%d, %d])" % (cpu_range.get_lower_boundary(), cpu_range.get_upper_boundary())
                    #        header_errors.append("core %d (%d) not in range [%d, %d]" % (cpu["core_num"], cpu_speed, cpu_range.get_lower_boundary(), cpu_range.get_upper_boundary()))
                    out_list.append([logging_tools.form_entry(cpu["core_num"], header="core"),
                                     logging_tools.form_entry(cpu_speed, header="speed"),
                                     logging_tools.form_entry(cpu["socket_num"], header="socket"),
                                     logging_tools.form_entry(cpu.get_cache_info_str(), header="cache"),
                                     logging_tools.form_entry(cpu["cpu_id"], header="cpu_id"),
                                     logging_tools.form_entry(trim_string(cpu.get("model name", "unknown brand")), header="brand"),
                                     logging_tools.form_entry(bnd_str, header="problems")])
                else:
                    out_list.append([logging_tools.form_entry(cpu["core_num"], header="core"),
                                     logging_tools.form_entry(0, header="speed"),
                                     logging_tools.form_entry(0, header="socket"),
                                     logging_tools.form_entry("---", header="cache"),
                                     logging_tools.form_entry("---", header="cpu_id"),
                                     logging_tools.form_entry("---", header="brand"),
                                     logging_tools.form_entry("offline")])
            join_str, head_str = ("\n", "%s: %s, %s%s" % (pre_str,
                                                          logging_tools.get_plural("socket", cpu_info.num_sockets()),
                                                          logging_tools.get_plural("core", cpu_info.num_cores()),
                                                          ", %s" % (", ".join(header_errors)) if header_errors else ""))
        return ret_state, join_str.join([head_str] + str(out_list).split("\n")) # ret_f)

class lvminfo_command(hm_classes.hm_command):
    def __call__(self, srv_com, cur_ns):
        self.module.local_lvm_info.update()
        srv_com["lvm_dict"] = self.module.local_lvm_info.generate_xml_dict(srv_com.builder)
    def interpret(self, srv_com, cur_ns):
        lvm_struct = srv_com["lvm_dict"]
        if lvm_struct.get("type", "???") == "str":
            return limits.nag_STATE_CRITICAL, "cannot interpret old return value"
        else:
            lvm_struct = lvm_struct[0]
            if lvm_struct.attrib["lvm_present"] == "1":
                out_f = [", ".join([logging_tools.get_plural("%s element" % (sub_struct.attrib["lvm_type"]), int(sub_struct.attrib["entities"])) for sub_struct in lvm_struct]) or "no LVM-elements found"]
                for sub_struct in lvm_struct:
                    for sub_el in sub_struct:
                        out_f.append("%s %-20s: %s" % (sub_el.tag.split("}")[1],
                                                       sub_el.attrib["name"],
                                                       sub_el.attrib["uuid"]))
                return limits.nag_STATE_OK, "\n".join(out_f)
            else:
                return limits.nag_STATE_WARNING, "no LVM-binaries found"
# #            lv_stuff = partition_tools.lvm_struct("dict", source_dict=lvm_dict)
# #            if lv_stuff.lvm_present:
# #                lv_elements = ["pv", "vg", "lv"]
# #                if True:#list_mode:
# #                    out_f = ["%s:" % (", ".join([logging_tools.get_plural("%s element" % (lv_element), len(lv_stuff.lv_dict.get(lv_element, {}).keys())) for lv_element in lv_elements]))]
# #                    for lv_element in lv_elements:
# #                        act_el_dict = lv_stuff.lv_dict.get(lv_element, {})
# #                        for el_name, act_el in act_el_dict.iteritems():
# #                            out_f.append("%s %-20s: %s" % (lv_element, el_name, act_el["uuid"]))
# #                    return limits.nag_STATE_OK, "ok %s" % ("\n".join(out_f))
# #                else:
# #                    return limits.nag_STATE_OK, "ok %s" % (lv_stuff.get_info())
# #            else:
# #                return limits.nag_STATE_OK, "ok no LVM-binaries found"

class partinfo_command(hm_classes.hm_command):
    def __call__(self, srv_com, cur_ns):
        self.module.local_lvm_info.update()
        ret_str, dev_dict, sys_dict = self.module._partinfo_int()
        srv_com["ret_str"] = ret_str
        srv_com["dev_dict"] = dev_dict
        srv_com["sys_dict"] = sys_dict
        srv_com["lvm_dict"] = self.module.local_lvm_info.generate_xml_dict(srv_com.builder)
    def interpret(self, srv_com, cur_ns):
        dev_dict, sys_dict, lvm_dict = (
            srv_com["dev_dict"],
            srv_com["sys_dict"],
            srv_com["lvm_dict"])
        # (server_command.decompress(srv_com["dev_dict"].text, marshal=True),
        #                                server_command.decompress(srv_com["sys_dict"].text, marshal=True),
        #                                server_command.decompress(srv_com["lvm_dict"].text, pickle=True))
        lvm_stuff = partition_tools.lvm_struct("xml", xml=lvm_dict)
        all_disks = sorted(dev_dict.keys())
        all_sys = sorted(sys_dict.keys())
        ret_f = ["found %s (%s) and %s:" % (
            logging_tools.get_plural("disc"         , len(all_disks)),
            logging_tools.get_plural("partition"    , sum([len(value) for value in dev_dict.itervalues()])),
            logging_tools.get_plural("special mount", len(all_sys)))]
        to_list = logging_tools.new_form_list()
        # to_list.set_format_string(2, pre_string="(", post_string=")")
        # to_list.set_format_string(3, left="", post_string=" MB,")
        ret_f.append("Partition overview")
        for disk in all_disks:
            all_parts = sorted(dev_dict[disk].keys())
            for part in all_parts:
                part_stuff = dev_dict[disk][part]
                is_multipath = "multipath" in part_stuff
                if is_multipath:
                    # see fetch_partition_info_mod.py
                    part_name = "%s-%s" % (disk, part)
                    real_disk = [entry for entry in part_stuff["multipath"]["list"] if entry["status"] == "active"]
                    if real_disk:
                        mp_id = part_stuff["multipath"]["id"]
                        real_disk = real_disk[0]
                        if part is None:
                            real_disk, real_part = ("/dev/%s" % (real_disk["device"]), part)
                        else:
                            real_disk, real_part = ("/dev/%s" % (real_disk["device"]), part[4:])
                        # copy data from real disk
                        if real_disk in dev_dict:
                            # LVM between
                            real_part = dev_dict[real_disk][real_part]
                            for key in ["hextype", "info", "size"]:
                                part_stuff[key] = real_part[key]
                        else:
                            # no LVM between
                            real_part = dev_dict["/dev/mapper/%s" % (mp_id)]
                            part_stuff["hextype"] = "0x00"
                            part_stuff["info"] = "multipath w/o LVM"
                            part_stuff["size"] = int(logging_tools.interpret_size_str(part_stuff["multipath"]["size"]) / (1024 * 1024))
                else:
                    part_name = "%s%s" % (disk, part)
                if part_stuff.has_key("mountpoint"):
                    mount_info = "fstype %s, opts %s, (%d/%d)" % (
                        part_stuff["fstype"],
                        part_stuff["options"],
                        part_stuff["dump"],
                        part_stuff["fsck"])
                else:
                    mount_info = ""
                lut_info = part_stuff.get("lut", None)
                if lut_info:
                    if type(lut_info) == dict:
                        # old version
                        lut_keys = sorted(lut_info.keys())
                        lut_str = "; ".join(["%s: %s" % (lut_key, ",".join(sorted(lut_info[lut_key]))) for lut_key in lut_keys])
                    else:
                        lut_str = "; ".join(lut_info)
                else:
                    lut_str = "---"
                to_list.append([logging_tools.form_entry(part_name, header="partition"),
                                logging_tools.form_entry(part_stuff["hextype"], header="hex"),
                                logging_tools.form_entry(part_stuff["info"], header="info"),
                                logging_tools.form_entry_right(part_stuff["size"], header="size (MB)"),
                                logging_tools.form_entry(part_stuff.get("mountpoint", "none"), header="mountpoint"),
                                logging_tools.form_entry(mount_info, header="info"),
                                logging_tools.form_entry(lut_str, header="lut")])
        ret_f.extend(str(to_list).split("\n"))
        ret_f.append("System partition overview")
        to_list = logging_tools.new_form_list()
        for disk in all_sys:
            sys_stuff = sys_dict[disk]
            if type(sys_stuff) == type({}):
                sys_stuff = [sys_stuff]
            for s_stuff in sys_stuff:
                to_list.append([logging_tools.form_entry(disk, header="part"),
                                logging_tools.form_entry(s_stuff["fstype"], header="type"),
                                logging_tools.form_entry(s_stuff["options"], header="option"),
                                logging_tools.form_entry(s_stuff["mountpoint"], header="mountpoint")])
        ret_f.extend(str(to_list).split("\n"))
        if lvm_stuff.lvm_present:
            ret_f.append("LVM info")
            ret_f.append(lvm_stuff.get_info(short=False))
        return limits.nag_STATE_OK, "\n".join(ret_f)

class mdstat_command(hm_classes.hm_command):
    def __call__(self, srv_com, cur_ns):
        srv_com["mdstat"] = server_command.compress(file("/proc/mdstat", "r").read())
    def interpret(self, srv_com, cur_ns):
        lines = server_command.decompress(srv_com["mdstat"].text).split("\n")
        raid_list = []
        cur_raid = None
        for _line_num, line in enumerate(lines):
            parts = line.strip().split()
            if line.startswith("md"):
                cur_raid = {"name"  : parts[0],
                            "state" : parts[2]}
                parts = parts[3:]
                if cur_raid["state"] == "active":
                    cur_raid["type"] = parts.pop(0)
                else:
                    cur_raid["type"] = None
                cur_raid["discs"] = parts
                raid_list.append(cur_raid)
            elif cur_raid and len(parts) > 2:
                if parts[1] == "blocks":
                    cur_raid["blocks"] = int(parts[0])
                elif parts[1] == "resync":
                    cur_raid["resync"] = parts[3]
        ret_state = limits.nag_STATE_OK
        if any(["resync" in cur_raid for cur_raid in raid_list]):
            ret_state = limits.nag_STATE_WARNING
        if raid_list:
            ret_str = ", ".join(["%s (%s%s%s)" % (
                        cur_raid["name"],
                        "%s %s" % (cur_raid["state"], cur_raid["type"]) if cur_raid["state"] == "active" else cur_raid["state"],
                        ", %d blocks" % (cur_raid["blocks"]) if "blocks" in cur_raid else "",
                        ", resync %s" % (cur_raid["resync"]) if "resync" in cur_raid else ""
                        ) for cur_raid in raid_list])
        else:
            ret_str = "no md-devices found"
        return ret_state, ret_str

class uname_command(hm_classes.hm_command):
    def __call__(self, srv_com, cur_ns):
        for idx, sub_str in enumerate(platform.uname()):
            srv_com["uname:part_%d" % (idx)] = sub_str
    def interpret(self, srv_com, cur_ns):
        uname_list = []
        for _idx, sub_el in enumerate(srv_com["uname"]):
            uname_list.append(sub_el.text)
        return limits.nag_STATE_OK, "%s, kernel %s" % (uname_list[0], uname_list[2])

class dmiinfo_command(hm_classes.hm_command):
    def __call__(self, srv_com, cur_ns):
        _dmi_stat, _dmi_result = commands.getstatusoutput(self.module.dmi_bin)
        with tempfile.NamedTemporaryFile()  as tmp_file:
            _dmi_stat, _dmi_result = commands.getstatusoutput("{} --dump-bin {}".format(self.module.dmi_bin, tmp_file.name))
            srv_com["dmi_dump"] = server_command.compress(file(tmp_file.name, "r").read())
    def interpret(self, srv_com, cur_ns):
        with tempfile.NamedTemporaryFile() as tmp_file:
            file(tmp_file.name, "w").write(server_command.decompress(srv_com["dmi_dump"].text))
            _dmi_stat, dmi_result = commands.getstatusoutput("{} --from-dump {}".format(self.module.dmi_bin, tmp_file.name))
            # decode dmi-info
            dec_lines = []
            for line in dmi_result.split("\n"):
                n_level = 0
                while line.startswith("\t"):
                    n_level += 1
                    line = line[1:]
                line = line.strip()
                dec_lines.append((n_level, line))
            dmi_struct = {"info"    : [],
                          "handles" : []}
            # info
            print dec_lines
            while True:
                if dec_lines[0][1].lower().startswith("handle"):
                    break
                n_level, line = dec_lines.pop(0)
                if not line:
                    break
                else:
                    dmi_struct["info"].append(line)
            # handles
            while True:
                n_level, h_info = dec_lines.pop(0)
                if h_info.lower().startswith("invalid"):
                    break
                if len(h_info.split(",")) < 3:
                    h_info = "%s, %s" % (h_info, dec_lines.pop(0)[1])
                top_level, info_str = dec_lines.pop(0)
                h_info_spl = [part.strip().split() for part in h_info.split(",")]
                handle_dict = {"info"     : info_str,
                               "handle"   : int(h_info_spl[0][1], 16),
                               "dmi_type" : int(h_info_spl[1][2]),
                               "length"   : int(h_info_spl[2][0]),
                               "content"  : {}}
                while True:
                    n_level, line = dec_lines.pop(0)
                    if n_level == top_level + 1:
                        try:
                            key, value = line.split(":", 1)
                        except:
                            self.log("error decoding dmi-line %s: %s" % (line,
                                                                         process_tools.get_except_info()),
                                     logging_tools.LOG_LEVEL_ERROR)
                        else:
                            handle_dict["content"][key.strip()] = value.strip()
                    elif n_level == top_level + 2:
                        if key and type(handle_dict["content"][key]) != type([]):
                            handle_dict["content"][key] = []
                        handle_dict["content"][key].append(line)
                    else:
                        while line.strip():
                            n_level, line = dec_lines.pop(0)
                        break
                dmi_struct["handles"].append(handle_dict)
                if handle_dict["dmi_type"] == 127:
                    break
            # pprint.pprint(dmi_struct)
            out_f = dmi_struct["info"]
            for handle in dmi_struct["handles"]:
                out_f.extend(["",
                              handle["info"]])
                for c_key in sorted(handle["content"].keys()):
                    c_value = handle["content"][c_key]
                    if type(c_value) == type([]):
                        out_f.append("    %s:" % (c_key))
                        for sub_value in c_value:
                            out_f.append("        %s" % (sub_value))
                    else:
                        out_f.append("    %s: %s" % (c_key, c_value))
            return limits.nag_STATE_OK, "ok %s" % ("\n".join(out_f))

# helper routines
def get_nfs_mounts():
    m_dict = {}
    try:
        for line in open("/proc/mounts", "r").read().split("\n"):
            line_split = line.strip().split()
            if len(line_split) == 6:
                m_dict.setdefault(line_split[2], []).append((line_split[0], line_split[1]))
    except:
        pass
    return m_dict

def sub_wrap(val_1, val_0):
    sub = val_1 - val_0
    while sub < 0:
        sub += sys.maxint
    if sub > sys.maxint / 8:
        sub = 0
    return sub

def trim_string(in_str):
    while in_str.count("  "):
        in_str = in_str.replace("  ", " ")
    return in_str.strip()

