#
# Copyright (C) 2016 Gregor Kaufmann, Andreas Lang-Nevyjel init.at
#
# this file is part of icsw-server
#
# Send feedback to: <g.kaufmann@init.at>
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

import base64
import bz2
import datetime
import json

from django.db.models import signals, CASCADE
from django.dispatch import receiver
from django.db import models
from django.db.models import Q
from django.utils import timezone, dateparse
from enum import IntEnum
from lxml import etree

from initat.tools import server_command, pci_database, dmi_tools


########################################################################################################################
# Functions
########################################################################################################################


def get_base_assets_from_raw_result(asset_run,):
    blob = asset_run.raw_result_str
    runtype = asset_run.run_type
    scantype = asset_run.scan_type
    if blob:
        if runtype == AssetType.PACKAGE:
            assets = []
            if scantype == ScanType.NRPE:
                if blob.startswith("b'"):
                    _data = bz2.decompress(base64.b64decode(blob[2:-2]))
                else:
                    _data = bz2.decompress(base64.b64decode(blob))
                l = json.loads(_data)
                for (name, version, size, date) in l:
                    if size == "Unknown":
                        size = 0
                    assets.append(
                        BaseAssetPackage(
                            name,
                            version=version,
                            size=size,
                            install_date=date,
                            package_type=PackageTypeEnum.WINDOWS
                        )
                    )
            elif scantype == ScanType.HM:
                try:
                    package_dict = server_command.decompress(blob, pickle=True)
                except:
                    raise
                else:
                    for package_name in package_dict:
                        for versions_dict in package_dict[package_name]:
                            assets.append(
                                BaseAssetPackage(
                                    package_name,
                                    version=versions_dict['version'],
                                    size=versions_dict['size'],
                                    release=versions_dict['release'],
                                    package_type=PackageTypeEnum.LINUX
                                )
                            )
            # lookup cache
            lu_cache = {}
            for idx, ba in enumerate(assets):
                if idx % 100 == 0:
                    lu_cache = {
                        _p.name: _p for _p in AssetPackage.objects.filter(
                            Q(name__in=[_x.name for _x in assets[idx:idx + 100]]) &
                            Q(package_type=ba.package_type)
                        ).prefetch_related(
                            "assetpackageversion_set"
                        )
                    }
                name = ba.name
                version = ba.version if ba.version else ""
                release = ba.release if ba.release else ""
                size = ba.size if ba.size else 0
                package_type = ba.package_type

                # kwfilterdict['name'] = ba.name
                # kwfilterdict['version'] = ba.version
                # kwfilterdict['release'] = ba.release
                if name in lu_cache:
                    ap = lu_cache[ba.name]

                    versions = ap.assetpackageversion_set.filter(version=version, release=release, size=size)
                    assert (len(versions) < 2)

                    if versions:
                        apv = versions[0]
                    else:
                        apv = AssetPackageVersion(asset_package=ap, version=version, release=release, size=size)
                        apv.save()
                else:
                    ap = AssetPackage(name=name, package_type=package_type)
                    ap.save()
                    apv = AssetPackageVersion(asset_package=ap, version=version, release=release, size=size)
                    apv.save()
                asset_run.packages.add(apv)

        elif runtype == AssetType.HARDWARE:
            if scantype == ScanType.NRPE:
                if blob.startswith("b'"):
                    s = bz2.decompress(base64.b64decode(blob[2:-2]))
                else:
                    s = bz2.decompress(base64.b64decode(blob))
            elif scantype == ScanType.HM:
                s = bz2.decompress(base64.b64decode(blob))
            else:
                s = blob

            root = etree.fromstring(s)
            assert (root.tag == "topology")

            # lookup for structural entries
            _struct_lut = {}
            _root_tree = root.getroottree()
            struct_el = None
            for element in root.iter():
                if element.tag in ["topology", "object"]:
                    # structural entry
                    struct_el = AssetHardwareEntry(
                        type=element.tag,
                        attributes=json.dumps({key: value for key, value in element.attrib.iteritems()}),
                        asset_run=asset_run,
                    )
                    # get local path
                    _path = _root_tree.getpath(element)
                    _struct_lut[_path] = struct_el
                    struct_el._info_dict = {}
                    if element.getparent() is not None:
                        # parent_path
                        _parent = _struct_lut[_root_tree.getpath(element.getparent())]
                        struct_el.parent = _parent
                        struct_el.depth = _parent.depth + 1

                    struct_el.save()
                else:
                    _struct_el = _struct_lut[_root_tree.getpath(element.getparent())]
                    _struct_el._info_dict.setdefault(element.tag, []).append(
                        json.dumps(
                            {key: value for key, value in element.attrib.iteritems()}
                        )
                    )
            for _path, _el in _struct_lut.iteritems():
                _el.info_list = json.dumps(_el._info_dict)
                _el.save()

        elif runtype == AssetType.LICENSE:
            if scantype == ScanType.NRPE:
                if blob.startswith("b'"):
                    _data = bz2.decompress(base64.b64decode(blob[2:-2]))
                else:
                    _data = bz2.decompress(base64.b64decode(blob))
                l = json.loads(_data)
                for (name, licensekey) in l:
                    new_lic = AssetLicenseEntry(
                        name=name,
                        license_key=licensekey,
                        asset_run=asset_run,
                    )
                    new_lic.save()
            elif scantype == ScanType.HM:
                # todo implement me (--> what do we want to gather/display here?)
                pass

        elif runtype == AssetType.PENDING_UPDATE:
            if scantype == ScanType.NRPE:
                if blob.startswith("b'"):
                    _data = bz2.decompress(base64.b64decode(blob[2:-2]))
                else:
                    _data = bz2.decompress(base64.b64decode(blob))
                l = json.loads(_data)
                for (name, optional) in l:
                    new_pup = AssetUpdateEntry(
                        name=name,
                        installed=False,
                        asset_run=asset_run,
                        optional=optional,
                    )
                    new_pup.save()

            elif scantype == ScanType.HM:
                l = server_command.decompress(blob, pickle=True)
                for (name, version) in l:
                    new_pup = AssetUpdateEntry(
                        name=name,
                        installed=False,
                        asset_run=asset_run,
                        # by definition linux updates are optional
                        optional=True,
                        new_version=version,
                    )
                    new_pup.save()

        elif runtype == AssetType.UPDATE:
            if scantype == ScanType.NRPE:
                if blob.startswith("b'"):
                    _data = bz2.decompress(base64.b64decode(blob[2:-2]))
                else:
                    _data = bz2.decompress(base64.b64decode(blob))
                l = json.loads(_data)
                for (name, up_date, status) in l:
                    new_up = AssetUpdateEntry(
                        name=name,
                        install_date=dateparse.parse_datetime(up_date),
                        status=status,
                        installed=True,
                        asset_run=asset_run,
                        optional=False,
                    )
                    new_up.save()
            elif scantype == ScanType.HM:
                # todo implement me (--> what do we want to gather/display here?)
                pass

        elif runtype == AssetType.SOFTWARE_VERSION:
            # todo implement me
            pass

        elif runtype == AssetType.PROCESS:
            if scantype == ScanType.NRPE:
                if blob.startswith("b'"):
                    _data = bz2.decompress(base64.b64decode(blob[2:-2]))
                else:
                    _data = bz2.decompress(base64.b64decode(blob))
                l = json.loads(_data)
                process_dict = {int(pid): {"name": name} for name, pid in l}
            elif scantype == ScanType.HM:
                process_dict = eval(bz2.decompress(base64.b64decode(blob)))
            for pid, stuff in process_dict.iteritems():
                new_proc = AssetProcessEntry(
                    pid=pid,
                    name=stuff["name"],
                    asset_run=asset_run,
                )
                new_proc.save()

        elif runtype == AssetType.PCI:
            if scantype == ScanType.NRPE:
                if blob.startswith("b'"):
                    _data = bz2.decompress(base64.b64decode(blob[2:-2]))
                else:
                    _data = bz2.decompress(base64.b64decode(blob))

                info_dicts = []

                info_dict = {}
                for line in _data.decode().split("\r\n"):
                    if len(line) == 0:
                        if len(info_dict) > 0:
                            info_dicts.append(info_dict)
                            info_dict = {}
                    if line.startswith("Slot:"):
                        info_dict['slot'] = line.split("\t", 1)[1]

                        comps = info_dict['slot'].split(":")
                        bus = comps[0]

                        comps = comps[1].split(".")
                        slot = comps[0]
                        func = comps[1]

                        info_dict['bus'] = bus
                        info_dict['slot'] = slot
                        info_dict['func'] = func
                    elif line.startswith("Class:"):
                        info_dict['class'] = line.split("\t", 1)[1]
                    elif line.startswith("Vendor:"):
                        info_dict['vendor'] = line.split("\t", 1)[1]
                    elif line.startswith("Device:"):
                        info_dict['device'] = line.split("\t", 1)[1]
                    elif line.startswith("SVendor:"):
                        info_dict['svendor'] = line.split("\t", 1)[1]
                    elif line.startswith("SDevice:"):
                        info_dict['sdevice'] = line.split("\t", 1)[1]
                    elif line.startswith("Rev:"):
                        info_dict['rev'] = line.split("\t", 1)[1]

                for info_dict in info_dicts:
                    new_pci = AssetPCIEntry(
                        asset_run=asset_run,
                        domain=0,
                        bus=int(info_dict['bus'], 16) if 'bus' in info_dict else 0,
                        slot=int(info_dict['slot'], 16) if 'slot' in info_dict else 0,
                        func=int(info_dict['func'], 16) if 'func' in info_dict else 0,
                        pci_class=0,
                        subclass=0,
                        device=0,
                        vendor=0,
                        revision=int(info_dict['rev'], 16) if 'rev' in info_dict else 0,
                        pci_classname=info_dict['class'],
                        subclassname=info_dict['class'],
                        devicename=info_dict['device'],
                        vendorname=info_dict['vendor'],
                    )
                    new_pci.save()

            elif scantype == ScanType.HM:
                s = pci_database.pci_struct_to_xml(
                    pci_database.decompress_pci_info(blob)
                )
                for func in s.findall(".//func"):
                    _slot = func.getparent()
                    _bus = _slot.getparent()
                    _domain = _bus.getparent()
                    new_pci = AssetPCIEntry(
                        asset_run=asset_run,
                        domain=int(_domain.get("id")),
                        bus=int(_domain.get("id")),
                        slot=int(_slot.get("id")),
                        func=int(func.get("id")),
                        pci_class=int(func.get("class"), 16),
                        subclass=int(func.get("subclass"), 16),
                        device=int(func.get("device"), 16),
                        vendor=int(func.get("vendor"), 16),
                        revision=int(func.get("revision"), 16),
                        pci_classname=func.get("classname"),
                        subclassname=func.get("subclassname"),
                        devicename=func.get("devicename"),
                        vendorname=func.get("vendorname"),
                    )
                    new_pci.save()

        elif runtype == AssetType.DMI:
            if scantype == ScanType.NRPE:
                if blob.startswith("b'"):
                    _data = bz2.decompress(base64.b64decode(blob[2:-2]))
                else:
                    _data = bz2.decompress(base64.b64decode(blob))

                _lines = []

                for line in _data.decode().split("\r\n"):
                    _lines.append(line)
                    if line == "End Of Table":
                        break

                _xml = dmi_tools.dmi_struct_to_xml(dmi_tools.parse_dmi_output(_lines))
            elif scantype == ScanType.HM:
                _xml = dmi_tools.decompress_dmi_info(blob)
            head = AssetDMIHead(
                asset_run=asset_run,
                version=_xml.get("version"),
                size=int(_xml.get("size")),
            )
            head.save()
            for _handle in _xml.findall(".//handle"):
                handle = AssetDMIHandle(
                    dmihead=head,
                    handle=int(_handle.get("handle")),
                    dmi_type=int(_handle.get("dmi_type")),
                    length=int(_handle.get("length")),
                    header=_handle.get("header"),
                )
                handle.save()
                for _value in _handle.findall(".//value"):
                    if len(_value):
                        value = AssetDMIValue(
                            dmihandle=handle,
                            key=_value.get("key"),
                            single_value=False,
                            value=json.dumps([_el.text for _el in _value]),
                            num_values=len(_value),
                        )
                    else:
                        value = AssetDMIValue(
                            dmihandle=handle,
                            key=_value.get("key"),
                            single_value=True,
                            value=_value.text or "",
                            num_values=1,
                        )
                    value.save()

        elif runtype == AssetType.PRETTYWINHW:
            if blob.startswith("b'"):
                _data = bz2.decompress(base64.b64decode(blob[2:-2]))
            else:
                _data = bz2.decompress(base64.b64decode(blob))

            _data = json.loads(_data)

            memory_data = _data['memory']
            cpu_data = _data['cpu']
            gpu_data = _data['gpu']
            hdd_data = _data['hdd']
            logical_data = _data['logical']
            display_data = _data['monitor']

            for memory_entry in memory_data:
                banklabel = memory_entry['banklabel']
                formfactor = memory_entry['formfactor']
                memorytype = memory_entry['memorytype']
                manufacturer = memory_entry['manufacturer']
                capacity = int(memory_entry['capacity'])

                memory_modules = AssetHWMemoryEntry.objects.filter(
                    banklabel=banklabel,
                    formfactor=formfactor,
                    memorytype=memorytype,
                    manufacturer=manufacturer,
                    capacity=capacity)

                assert(len(memory_modules) < 2)

                if memory_modules:
                    memory_module = memory_modules[0]
                else:
                    memory_module = AssetHWMemoryEntry(
                        banklabel=banklabel,
                        formfactor=formfactor,
                        memorytype=memorytype,
                        manufacturer=manufacturer,
                        capacity=capacity
                    )
                    memory_module.save()

                asset_run.memory_modules.add(memory_module)
                asset_run.memory_count += 1

            for cpu_entry in cpu_data:
                cpuname = cpu_entry['name']
                numberofcores = int(cpu_entry['numberofcores'])

                cpus = AssetHWCPUEntry.objects.filter(
                    cpuname=cpuname,
                    numberofcores=numberofcores
                )

                assert(len(cpus) < 2)

                if cpus:
                    cpu = cpus[0]
                else:
                    cpu = AssetHWCPUEntry(
                        cpuname=cpuname,
                        numberofcores=numberofcores
                    )
                    cpu.save()

                asset_run.cpus.add(cpu)
                asset_run.cpu_count += 1

            for gpu_entry in gpu_data:
                gpuname = gpu_entry['name']
                driverversion = gpu_entry['driverversion']

                gpus = AssetHWGPUEntry.objects.filter(
                    gpuname=gpuname,
                    driverversion=driverversion
                )

                assert (len(gpus) < 2)

                if gpus:
                    gpu = gpus[0]
                else:
                    gpu = AssetHWGPUEntry(
                        gpuname=gpuname,
                        driverversion=driverversion
                    )
                    gpu.save()

                asset_run.gpus.add(gpu)

            for hdd_entry in hdd_data:
                name = hdd_entry['name']
                serialnumber = hdd_entry["serialnumber"]
                size = hdd_entry['size']
                if size:
                    size = int(size)
                else:
                    size = None

                hdds = AssetHWHDDEntry.objects.filter(
                    name=name,
                    serialnumber=serialnumber,
                    size=size
                )

                assert (len(hdds) < 2)

                if hdds:
                    hdd = hdds[0]
                else:
                    hdd = AssetHWHDDEntry(
                        name=name,
                        serialnumber=serialnumber,
                        size=size
                    )
                    hdd.save()

                asset_run.hdds.add(hdd)

            for logical_entry in logical_data:
                name = logical_entry['name']
                size = logical_entry['size']
                free = logical_entry['free']

                if size:
                    size = int(size)
                else:
                    size = None

                if free:
                    free = int(free)
                else:
                    free = None

                partitions = AssetHWLogicalEntry.objects.filter(
                    name=name,
                    size=size,
                    free=free
                )

                assert (len(partitions) < 2)

                if partitions:
                    partition = partitions[0]
                else:
                    partition = AssetHWLogicalEntry(
                        name=name,
                        size=size,
                        free=free
                    )
                    partition.save()

                asset_run.partitions.add(partition)

            for display_entry in display_data:
                xpixels = display_entry['xpixels']
                ypixels = display_entry['ypixels']
                manufacturer = display_entry['manufacturer']
                type = display_entry['type']
                name = display_entry['name']

                if xpixels:
                    xpixels = int(xpixels)
                else:
                    xpixels = None

                if ypixels:
                    ypixels = int(ypixels)
                else:
                    ypixels = None

                displays = AssetHWDisplayEntry.objects.filter(
                    xpixels=xpixels,
                    ypixels=ypixels,
                    manufacturer=manufacturer,
                    type=type,
                    name=name
                )

                assert (len(displays) < 2)

                if displays:
                    display = displays[0]
                else:
                    display = AssetHWDisplayEntry(
                        xpixels=xpixels,
                        ypixels=ypixels,
                        manufacturer=manufacturer,
                        type=type,
                        name=name
                    )
                    display.save()

                asset_run.displays.add(display)

########################################################################################################################
# Base Asset Classes
########################################################################################################################


class BaseAssetPackage(object):
    def __init__(self, name, version=None, release=None, size=None, install_date=None, package_type=None):
        self.name = name
        self.version = version
        self.release = release
        self.size = size
        self.install_date = install_date
        self.package_type = package_type

    def __repr__(self):
        s = "Name: %s" % self.name
        if self.version:
            s += " Version: %s" % self.version
        if self.release:
            s += " Release: %s" % self.release
        if self.size:
            s += " Size: %s" % self.size
        if self.install_date:
            s += " InstallDate: %s" % self.install_date
        if self.package_type:
            s += " PackageType: %s" % self.package_type

        return s

    def __lt__(self, other):
        return self.name < other.name

    def __eq__(self, other):
        return isinstance(other, self.__class__) \
            and self.name == other.name \
            and self.version == other.version \
            and self.release == other.release \
            and self.size == other.size \
            and self.install_date == other.install_date \
            and self.package_type == other.package_type

    def __hash__(self):
        return hash((self.name, self.version, self.release, self.size, self.install_date, self.package_type))

########################################################################################################################
# Enums
########################################################################################################################


class AssetType(IntEnum):
    PACKAGE = 1
    HARDWARE = 2  # lstopo
    LICENSE = 3
    UPDATE = 4
    SOFTWARE_VERSION = 5
    PROCESS = 6
    PENDING_UPDATE = 7
    DMI = 8
    PCI = 9
    PRETTYWINHW = 10


class ScanType(IntEnum):
    HM = 1
    NRPE = 2


class RunStatus(IntEnum):
    PLANNED = 1
    RUNNING = 2
    ENDED = 3


class RunResult(IntEnum):
    UNKNOWN = 1
    SUCCESS = 2
    WARNING = 3
    FAILED = 4
    # canceled (no IP)
    CANCELED = 5


class PackageTypeEnum(IntEnum):
    WINDOWS = 1
    LINUX = 2


memory_entry_form_factors = {
    0: "Unknown",
    1: "Other",
    2: "SIP",
    3: "DIP",
    4: "ZIP",
    5: "SOJ",
    6: "Proprietary",
    7: "SIMM",
    8: "DIMM",
    9: "TSOP",
    10: "PGA",
    11: "RIMM",
    12: "SODIMM",
    13: "SRIMM",
    14: "SMD",
    15: "SSMP",
    16: "QFP",
    17: "TQFP",
    18: "SOIC",
    19: "LCC",
    20: "PLCC",
    21: "BGA",
    22: "FPBGA",
    23: "LGA"
}

memory_entry_memory_types = {
    0: "Unknown",
    1: "Other",
    2: "DRAM",
    3: "Synchronous DRAM",
    4: "Cache DRAM",
    5: "EDO",
    6: "EDRAM",
    7: "VRAM",
    8: "SRAM",
    9: "RAM",
    10: "ROM",
    11: "FLASH",
    12: "EEPROM",
    13: "FEPROM",
    14: "EPROM",
    15: "CDRAM",
    16: "3DRAM",
    17: "SDRAM",
    18: "SGRAM",
    19: "RDRAM",
    20: "DDR",
    21: "DDR2",
    22: "DDR2 FB-DIMM",
    24: "DDR3",
    25: "FBD2"
}

########################################################################################################################
# (Django Database) Classes
########################################################################################################################


class AssetHWMemoryEntry(models.Model):
    idx = models.AutoField(primary_key=True)

    # i.e slot 0 / slot A
    banklabel = models.TextField(null=True)
    # dimm type
    formfactor = models.TextField(null=True)
    # i.e ddr/ddr2 if known
    memorytype = models.TextField(null=True)

    manufacturer = models.TextField(null=True)

    capacity = models.BigIntegerField(null=True)

    created = models.DateTimeField(auto_now_add=True)

    def __unicode__(self):
        return "MemoryEntry[BankLabel:{}|FormFactor:{}|Memorytype:{}|Manufacturer:{}|Capacity:{}]".format(
            self.banklabel,
            self.formfactor,
            self.memorytype,
            self.manufacturer,
            self.capacity
        )

    def get_name_of_form_factor(self):
        if self.formfactor:
            try:
                return memory_entry_form_factors[int(self.formfactor)]
            except ValueError:
                return "Unknown"
            except KeyError:
                return self.formfactor

        return "Unknown"

    def get_name_of_memory_type(self):
        if self.memorytype:
            try:
                return memory_entry_memory_types[int(self.memorytype)]
            except ValueError:
                return "Unknown"
            except KeyError:
                return self.memorytype

        return "Unknown"


class AssetHWCPUEntry(models.Model):
    idx = models.AutoField(primary_key=True)

    cpuname = models.TextField(null=True)

    numberofcores = models.IntegerField(null=True)

    created = models.DateTimeField(auto_now_add=True)

    def __unicode__(self):
        return "CPUEntry[CPUname:{}|Numberofcores:{}]".format(self.cpuname, self.numberofcores)


class AssetHWGPUEntry(models.Model):
    idx = models.AutoField(primary_key=True)

    gpuname = models.TextField(null=True)

    driverversion = models.TextField(null=True)

    created = models.DateTimeField(auto_now_add=True)

    def __unicode__(self):
        return "GPUEntry[GPUname:{}|Driverversion:{}]".format(self.gpuname, self.driverversion)


class AssetHWHDDEntry(models.Model):
    idx = models.AutoField(primary_key=True)

    name = models.TextField(null=True)

    serialnumber = models.TextField(null=True)

    size = models.BigIntegerField(null=True)

    created = models.DateTimeField(auto_now_add=True)

    def __unicode__(self):
        return "HDDEntry[Name:{}|Serialnumber:{}|Size:{}]".format(self.name, self.serialnumber, self.size)


class AssetHWLogicalEntry(models.Model):
    idx = models.AutoField(primary_key=True)

    name = models.TextField(null=True)

    size = models.BigIntegerField(null=True)

    free = models.BigIntegerField(null=True)

    created = models.DateTimeField(auto_now_add=True)

    def __unicode__(self):
        return "PartitionEntry[Name:{}|Size:{}|Free:{}]".format(self.name, self.size, self.free)


class AssetHWDisplayEntry(models.Model):
    idx = models.AutoField(primary_key=True)

    name = models.TextField(null=True)

    type = models.TextField(null=True)

    xpixels = models.IntegerField(null=True)

    ypixels = models.IntegerField(null=True)

    manufacturer = models.TextField(null=True)

    def __unicode__(self):
        return "DisplayEntry[Name:{}|Type:{}|xpixels:{}|ypixels:{}|manufacturer:{}]".format(
            self.name,
            self.type,
            self.xpixels,
            self.ypixels,
            self.manufacturer
        )


class AssetPackage(models.Model):
    idx = models.AutoField(primary_key=True)
    name = models.TextField()
    created = models.DateTimeField(auto_now_add=True)
    package_type = models.IntegerField(choices=[(pt.value, pt.name) for pt in PackageTypeEnum])

    def __lt__(self, other):
        return self.name < other.name

    def __eq__(self, other):
        return isinstance(other, self.__class__) \
            and self.name == other.name \
            and self.package_type == other.package_type

    def __hash__(self):
        return hash((self.name, self.package_type))


class AssetPackageVersion(models.Model):
    idx = models.AutoField(primary_key=True)
    asset_package = models.ForeignKey("backbone.AssetPackage")
    size = models.IntegerField(default=0)
    # for comment and / or info
    info = models.TextField(default="")
    version = models.TextField(default="", blank=True)
    release = models.TextField(default="", blank=True)
    created = models.DateTimeField(auto_now_add=True)

    def __lt__(self, other):
        return self.name < other.name

    def __eq__(self, other):
        return isinstance(other, self.__class__) and self.version == other.version \
            and self.release == other.release

    def __hash__(self):
        return hash((self.version, self.release, self.size))


class AssetHardwareEntry(models.Model):
    idx = models.AutoField(primary_key=True)
    # type (from XML)
    type = models.TextField(default="")
    # json-serializes attribute dict
    attributes = models.TextField(default="")
    # assetrun
    asset_run = models.ForeignKey("backbone.AssetRun")
    # depth
    depth = models.IntegerField(default=0)
    # json-serialized dict of all non-structural subentries
    """
    <page_type size="4096" count="4092876"/>
    <page_type size="2097152" count="0"/>
    <info name="DMIProductName" value="System Product Name"/>
    <info name="DMIProductVersion" value="System Version"/>
    <info name="DMIProductSerial" value="System Serial Number"/>
    <info name="DMIProductUUID" value="00A5001E-8C00-005E-A775-3085A99A7CAF"/>
    <info name="DMIBoardVendor" value="ASUSTeK COMPUTER INC."/>
    <info name="DMIBoardName" value="P9X79"/>
    <info name="DMIBoardVersion" value="Rev 1.xx"/>

    becomes
    {
        page_type: [{size: ..., count: ...}, {size: ..., count:....}]
        info: [{name: ..., value: ....}, {name: ..., value: ....}]
    }
    """
    info_list = models.TextField(default="")
    # link to parent
    parent = models.ForeignKey("backbone.AssetHardwareEntry", null=True)
    created = models.DateTimeField(auto_now_add=True)

    def __unicode__(self):
        return "AssetHardwareEntry {}".format(self.type)

    class Meta:
        ordering = ("idx",)


class AssetLicenseEntry(models.Model):
    idx = models.AutoField(primary_key=True)
    # name
    name = models.CharField(default="", max_length=255)
    # license key
    license_key = models.CharField(default="", max_length=255)
    # assetrun
    asset_run = models.ForeignKey("backbone.AssetRun")
    created = models.DateTimeField(auto_now_add=True)

    def __unicode__(self):
        return "AssetLicense name={}".format(self.name)

    class Meta:
        ordering = ("name",)


class AssetUpdateEntry(models.Model):
    # also for pendingUpdates
    idx = models.AutoField(primary_key=True)
    # name
    name = models.CharField(default="", max_length=255)
    # version / release
    version = models.CharField(default="", max_length=255)
    release = models.CharField(default="", max_length=255)
    # vendor ?
    # KnowledgeBase idx
    kb_idx = models.IntegerField(default=0)
    # install date
    install_date = models.DateTimeField(null=True)
    # status, now as string
    status = models.CharField(default="", max_length=128)
    # assetrun
    asset_run = models.ForeignKey("backbone.AssetRun")
    # optional
    optional = models.BooleanField(default=True)
    # installed
    installed = models.BooleanField(default=False)
    # new version (for RPMs)
    new_version = models.CharField(default="", max_length=64)
    created = models.DateTimeField(auto_now_add=True)

    def __unicode__(self):
        return "AssetUpdate name={}".format(self.name)

    class Meta:
        ordering = ("name",)


class AssetProcessEntry(models.Model):
    idx = models.AutoField(primary_key=True)
    # assetrun
    asset_run = models.ForeignKey("backbone.AssetRun")
    # Process ID
    pid = models.IntegerField(default=0)
    # Name
    name = models.CharField(default="", max_length=255)
    created = models.DateTimeField(auto_now_add=True)

    def __unicode__(self):
        return "AssetProcess pid={:d}".format(self.pid)

    class Meta:
        ordering = ("pid",)


class AssetPCIEntry(models.Model):
    idx = models.AutoField(primary_key=True)
    # assetrun
    asset_run = models.ForeignKey("backbone.AssetRun")
    # Domain / Bus / Slot / Func
    domain = models.IntegerField(default=0)
    bus = models.IntegerField(default=0)
    slot = models.IntegerField(default=0)
    func = models.IntegerField(default=0)
    # ids
    pci_class = models.IntegerField(default=0)
    subclass = models.IntegerField(default=0)
    device = models.IntegerField(default=0)
    vendor = models.IntegerField(default=0)
    revision = models.IntegerField(default=0)
    # Name(s)
    pci_classname = models.CharField(default="", max_length=255)
    subclassname = models.CharField(default="", max_length=255)
    devicename = models.CharField(default="", max_length=255)
    vendorname = models.CharField(default="", max_length=255)
    created = models.DateTimeField(auto_now_add=True)

    def __unicode__(self):
        return "AssetPCIEntry {:04x}:{:02x}:{:02x}.{:x} {}".format(
            self.domain,
            self.bus,
            self.slot,
            self.func,
            self.devicename,
        )

    class Meta:
        ordering = ("domain", "bus", "slot", "func",)


class AssetDMIHead(models.Model):
    idx = models.AutoField(primary_key=True)
    # assetrun
    asset_run = models.ForeignKey("backbone.AssetRun")
    version = models.CharField(default="", max_length=63)
    size = models.IntegerField(default=0)
    created = models.DateTimeField(auto_now_add=True)

    def __unicode__(self):
        return "AssetDMIHead"


class AssetDMIHandle(models.Model):
    idx = models.AutoField(primary_key=True)
    # dmi_head
    dmihead = models.ForeignKey("backbone.AssetDMIHead")
    # handle id
    handle = models.IntegerField(default=0)
    # type
    dmi_type = models.IntegerField(default=0)
    # header string
    header = models.CharField(default="", max_length=128)
    # length
    length = models.IntegerField(default=0)
    created = models.DateTimeField(auto_now_add=True)

    def __unicode__(self):
        return "AssetDMIHandle {:d}: {}".format(
            self.handle,
            self.header,
        )


class AssetDMIValue(models.Model):
    idx = models.AutoField(primary_key=True)
    # dmi_handle
    dmihandle = models.ForeignKey("backbone.AssetDMIHandle")
    # key
    key = models.CharField(default="", max_length=128)
    # is single valued
    single_value = models.BooleanField(default=True)
    # number of values, 1 or more
    num_values = models.IntegerField(default=1)
    # value for single_valued else json encoded
    value = models.TextField(default="")
    created = models.DateTimeField(auto_now_add=True)

    def __unicode__(self):
        return "AssetDMIValue {}".format(
            self.key,
        )


class AssetRun(models.Model):
    idx = models.AutoField(primary_key=True)

    run_index = models.IntegerField(default=1)
    run_status = models.IntegerField(
        choices=[(status.value, status.name) for status in RunStatus],
        default=RunStatus.PLANNED.value,
    )
    run_result = models.IntegerField(
        choices=[(status.value, status.name) for status in RunResult],
        default=RunResult.UNKNOWN.value,
    )
    run_type = models.IntegerField(
        choices=[(_type.value, _type.name) for _type in AssetType],
        default=AssetType.PACKAGE.value,
    )
    run_start_time = models.DateTimeField(null=True, blank=True)
    run_end_time = models.DateTimeField(null=True, blank=True)
    # runtime in seconds (for communication)
    run_duration = models.IntegerField(default=0)
    # time needed to generate assets in db
    generate_duration = models.FloatField(default=0.0)
    # error string
    error_string = models.TextField(default="")
    # interpret error
    interpret_error_string = models.TextField(default="")
    asset_batch = models.ForeignKey("AssetBatch", null=True)
    device = models.ForeignKey("backbone.device", null=True)
    # run index in current batch
    batch_index = models.IntegerField(default=0)

    raw_result_str = models.TextField(null=True)

    raw_result_interpreted = models.BooleanField(default=False)

    scan_type = models.IntegerField(choices=[(_type.value, _type.name) for _type in ScanType], null=True)

    # link to packageversions
    packages = models.ManyToManyField(AssetPackageVersion)
    created = models.DateTimeField(auto_now_add=True)

    memory_modules = models.ManyToManyField(AssetHWMemoryEntry)
    memory_count = models.IntegerField(default=0)
    cpus = models.ManyToManyField(AssetHWCPUEntry)
    cpu_count = models.IntegerField(default=0)
    gpus = models.ManyToManyField(AssetHWGPUEntry)
    hdds = models.ManyToManyField(AssetHWHDDEntry)
    partitions = models.ManyToManyField(AssetHWLogicalEntry)
    displays = models.ManyToManyField(AssetHWDisplayEntry)

    def start(self):
        self.run_status = RunStatus.RUNNING
        self.run_start_time = timezone.now()
        self.save()

    def stop(self, result, error_string=""):
        self.run_result = result
        self.run_status = RunStatus.ENDED
        self.error_string = error_string
        if self.run_start_time:
            self.run_end_time = timezone.now()
            self.run_duration = int((self.run_end_time - self.run_start_time).seconds)
        else:
            # no start time hence no end time
            self.run_duration = 0
        self.save()
        self.asset_batch.run_done(self)

    def generate_assets(self):
        if not self.raw_result_interpreted:
            get_base_assets_from_raw_result(self)
            self.raw_result_interpreted = True
            self.save()

    def get_asset_changeset(self, other_asset_run):
        # self.generate_assets()
        # other_asset_run.generate_assets()
        # this_assets = [_asset.getAssetInstance() for _asset in self.asset_set.all()]
        # other_assets = [_asset.getAssetInstance() for _asset in other_asset_run.asset_set.all()]
        this_assets = self.generate_assets_no_save()
        other_assets = other_asset_run.generate_assets_no_save()

        return set(this_assets).difference(other_assets)

    def diff_to_prev_run(self):
        if self.run_index == 0:
            return []

        return self.get_asset_changeset(
            self.device.assetrun_set.get(run_index=self.run_index-1)
        )


class AssetBatch(models.Model):
    idx = models.AutoField(primary_key=True)
    run_start_time = models.DateTimeField(null=True, blank=True)
    run_end_time = models.DateTimeField(null=True, blank=True)
    # total number of runs
    num_runs = models.IntegerField(default=0)
    # number of runs completed
    num_completed = models.IntegerField(default=0)
    # number of runs ok / error
    num_runs_ok = models.IntegerField(default=0)
    num_runs_error = models.IntegerField(default=0)
    # status
    run_status = models.IntegerField(
        choices=[(status.value, status.name) for status in RunStatus],
        default=RunStatus.PLANNED.value,
    )
    # result
    run_result = models.IntegerField(
        choices=[(status.value, status.name) for status in RunResult],
        default=RunResult.UNKNOWN.value,
    )
    # error string
    error_string = models.TextField(default="")
    # total run time in seconds
    run_time = models.IntegerField(default=0)
    device = models.ForeignKey("backbone.device")
    date = models.DateTimeField(auto_now_add=True)
    created = models.DateTimeField(auto_now_add=True)

    def completed(self):
        for assetrun in self.assetrun_set.all():
            if not assetrun.run_status == RunStatus.ENDED:
                return False
        return True

    def run_done(self, asset_run):
        self.num_completed += 1
        if asset_run.run_result == RunResult.SUCCESS:
            self.num_runs_ok += 1
        else:
            self.num_runs_error += 1
        if self.num_completed == self.num_runs:
            # finished
            self.run_end_time = timezone.now()
            self.run_time = int((self.run_end_time - self.run_start_time).seconds)
            self.run_status = RunStatus.ENDED
            self.run_result = max([_res.run_result for _res in self.assetrun_set.all()])
        self.save()

    def __repr__(self):
        return unicode(self)

    def __unicode__(self):
        return "AssetBatch for device '{}'".format(
            unicode(self.device)
        )


class DeviceInventory(models.Model):
    # to be removed
    idx = models.AutoField(primary_key=True)
    device = models.ForeignKey("backbone.device")
    inventory_type = models.CharField(
        max_length=255,
        choices=(
            ("lstopo", "LSTopo"),
            ("dmi", "DMI"),
            ("pci", "PCI"),
        )
    )
    # results from the same fetch run have the same run_idx
    run_idx = models.IntegerField(default=0)
    # serialized XML
    value = models.TextField()
    date = models.DateTimeField(auto_now_add=True)


class StaticAssetType(IntEnum):
    # related to a software
    LICENSE = 1
    # general contract
    CONTRACT = 2
    # special hardware
    HARDWARE = 3


class StaticAssetTemplateFieldType(IntEnum):
    INTEGER = 1
    # oneline
    STRING = 2
    DATE = 3
    # textarea
    TEXT = 4


# static assets
class StaticAssetTemplate(models.Model):
    # to be defined by administrator
    idx = models.AutoField(primary_key=True)
    # asset type
    type = models.IntegerField(choices=[(_type.value, _type.name) for _type in StaticAssetType])
    # name of Template
    name = models.CharField(max_length=128, unique=True)
    # description
    description = models.TextField(default="", blank=True)
    # system template (not deleteable)
    system_template = models.BooleanField(default=False)
    # parent template (for copy operations)
    parent_template = models.ForeignKey("backbone.StaticAssetTemplate", null=True)
    # link to creation user
    user = models.ForeignKey("backbone.user", null=True)
    # enabled
    enabled = models.BooleanField(default=True)
    # created
    date = models.DateTimeField(auto_now_add=True)

    def check_ordering(self):
        # check ordering of elements
        _dict = {}
        for entry in self.staticassettemplatefield_set.all():
            _dict.setdefault(entry.ordering, []).append(entry)
        if any([len(_value) > 1 for _value in _dict.itervalues()]):
            # reorder
            for _idx, _entry in enumerate(self.staticassettemplatefield_set.all().order_by("ordering")):
                _entry.ordering = _idx
                _entry.save(update_fields=["ordering"])

    def copy(self, new_obj, create_user):
        nt = StaticAssetTemplate(
            type=self.type,
            name=new_obj["name"],
            description=new_obj["description"],
            system_template=False,
            parent_template=self,
            user=create_user,
            enabled=self.enabled,
        )
        nt.save()
        for _field in self.staticassettemplatefield_set.all():
            nt.staticassettemplatefield_set.add(_field.copy(nt, create_user))
            print _field
        return nt

    class CSW_Meta:
        permissions = (
            ("setup", "Change StaticAsset templates", False),
        )


class StaticAssetTemplateField(models.Model):
    idx = models.AutoField(primary_key=True)
    # template
    static_asset_template = models.ForeignKey("backbone.StaticAssetTemplate")
    # name
    name = models.CharField(max_length=64, default="")
    # description
    field_description = models.TextField(default="", blank=True)
    field_type = models.IntegerField(choices=[(_type.value, _type.name) for _type in StaticAssetTemplateFieldType])
    # is optional
    optional = models.BooleanField(default=True)
    # is consumable (for integer fields)
    consumable = models.BooleanField(default=False)
    # consumable values, should be start > warn > critical
    consumable_start_value = models.IntegerField(default=0)
    consumable_warn_value = models.IntegerField(default=0)
    consumable_critical_value = models.IntegerField(default=0)
    # date check
    date_check = models.BooleanField(default=False)
    # date warning limits in days
    date_warn_value = models.IntegerField(default=60)
    date_critical_value = models.IntegerField(default=30)
    # field is fixed (cannot be altered)
    fixed = models.BooleanField(default=False)
    # default value
    default_value_str = models.CharField(default="", blank=True, max_length=255)
    default_value_int = models.IntegerField(default=0)
    default_value_date = models.DateField(default=timezone.now)
    default_value_text = models.TextField(default="", blank=True)
    # bounds, for input checking
    has_bounds = models.BooleanField(default=False)
    value_int_lower_bound = models.IntegerField(default=0)
    value_int_upper_bound = models.IntegerField(default=0)
    # monitor flag, only for datefields and / or consumable (...?)
    monitor = models.BooleanField(default=False)
    # hidden, used for linking (...?)
    hidden = models.BooleanField(default=False)
    # show_in_overview
    show_in_overview = models.BooleanField(default=False)
    # ordering, starting from 0 to #fields - 1
    ordering = models.IntegerField(default=0)
    # created
    date = models.DateTimeField(auto_now_add=True)

    def copy(self, new_template, create_user):
        nf = StaticAssetTemplateField(
            static_asset_template=new_template,
            name=self.name,
            field_description=self.field_description,
            field_type=self.field_type,
            optional=self.optional,
            consumable=self.consumable,
            default_value_str=self.default_value_str,
            default_value_int=self.default_value_int,
            default_value_date=self.default_value_date,
            default_value_text=self.default_value_text,
            has_bounds=self.has_bounds,
            value_int_lower_bound=self.value_int_lower_bound,
            value_int_upper_bound=self.value_int_upper_bound,
            monitor=self.monitor,
            fixed=self.fixed,
            hidden=self.hidden,
            show_in_overview=self.show_in_overview,
            consumable_start_value=self.consumable_start_value,
            consumable_warn_value=self.consumable_warn_value,
            consumable_critical_value=self.consumable_critical_value,
            date_warn_value=self.date_warn_value,
            date_critical_value=self.date_critical_value,
            date_check=self.date_check,
        )
        nf.save()
        return nf

    def get_attr_name(self):
        if self.field_type == StaticAssetTemplateFieldType.INTEGER.value:
            return ("value_int", "int")
        elif self.field_type == StaticAssetTemplateFieldType.STRING.value:
            return ("value_str", "str")
        elif self.field_type == StaticAssetTemplateFieldType.DATE.value:
            return ("value_date", "date")
        elif self.field_type == StaticAssetTemplateFieldType.TEXT.value:
            return ("value_text", "text")
        else:
            raise ValueError("wrong field type {}".format(self.field_type))

    def create_field_value(self, asset):
        new_f = StaticAssetFieldValue(
            static_asset=asset,
            static_asset_template_field=self,
            change_user=asset.create_user,
        )
        _local, _short = self.get_attr_name()
        setattr(new_f, _local, getattr(self, "default_{}".format(_local)))
        new_f.save()
        return new_f

    class Meta:
        unique_together = [
            ("static_asset_template", "name"),
        ]
        ordering = ["ordering"]


@receiver(signals.post_save, sender=StaticAssetTemplateField)
def StaticAssetTemplateField_post_save(sender, **kwargs):
    if "instance" in kwargs:
        cur_inst = kwargs["instance"]
        if not cur_inst.optional:
            # get all staticassets where this field is not set
            _missing_assets = StaticAsset.objects.filter(
                Q(static_asset_template=cur_inst.static_asset_template)
            ).exclude(
                Q(staticassetfieldvalue__static_asset_template_field=cur_inst)
            )
            if _missing_assets.count():
                # add fields
                for _asset in _missing_assets:
                    cur_inst.create_field_value(_asset)


class StaticAsset(models.Model):
    # used for linking
    idx = models.AutoField(primary_key=True)
    # template
    static_asset_template = models.ForeignKey("backbone.StaticAssetTemplate")
    # create user
    create_user = models.ForeignKey("backbone.user", null=True)
    # device
    device = models.ForeignKey("backbone.device")
    date = models.DateTimeField(auto_now_add=True)

    def add_fields(self):
        for _f in self.static_asset_template.staticassettemplatefield_set.all():
            _f.create_field_value(self)


class StaticAssetFieldValue(models.Model):
    idx = models.AutoField(primary_key=True)
    # template
    static_asset = models.ForeignKey("backbone.StaticAsset")
    # field
    static_asset_template_field = models.ForeignKey("backbone.StaticAssetTemplateField")
    # change user
    change_user = models.ForeignKey("backbone.user")
    # value
    value_str = models.CharField(null=True, blank=True, max_length=255, default=None)
    value_int = models.IntegerField(null=True, blank=True, default=None)
    value_date = models.DateField(null=True, blank=True, default=None)
    value_text = models.TextField(null=True, blank=True, default=None)
    date = models.DateTimeField(auto_now_add=True)

    def check_new_value(self, in_dict, xml_response):
        _field = self.static_asset_template_field
        _local, _short = _field.get_attr_name()
        _value = in_dict[_short]
        _errors = []
        if not _field.fixed:
            if _short == "int":
                # check for lower / upper bounds
                if _field.has_bounds:
                    if _value < _field.value_int_lower_bound:
                        _errors.append(
                            "value {:d} is below lower bound {:d}".format(
                                _value,
                                _field.value_int_lower_bound,
                            )
                        )
                    if _value > _field.value_int_upper_bound:
                        _errors.append(
                            "value {:d} is above upper bound {:d}".format(
                                _value,
                                _field.value_int_upper_bound,
                            )
                        )
        if _errors:
            xml_response.error(
                "Field {}: {}".format(
                    _field.name,
                    ", ".join(_errors)
                )
            )
            return False
        else:
            return True

    def set_new_value(self, in_dict, user):
        _field = self.static_asset_template_field
        _local, _short = _field.get_attr_name()
        if not _field.fixed:
            # ignore changes to fixed values
            if _short == "date":
                # cast date
                setattr(self, _local, datetime.datetime.strptime(in_dict[_short], "%d.%m.%Y").date())
            else:
                setattr(self, _local, in_dict[_short])
            self.change_user = user
            self.save()
