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
import time
import logging

from django.db.models import signals
from django.dispatch import receiver
from django.db import models
from django.db.models import Q
from django.utils import timezone, dateparse
from enum import IntEnum
from lxml import etree

from initat.tools import (server_command, pci_database, dmi_tools,
    partition_tools, logging_tools)
from initat.cluster.backbone.tools.hw import Hardware
from initat.cluster.backbone.models.partition import (partition_disc,
    partition_table, partition, partition_fs, LogicalDisc, lvm_vg,
    sys_partition, lvm_lv)
from initat.tools.server_command import srv_command
from initat.cluster.backbone.models.functions import get_related_models
from initat.snmp.snmp_struct import ResultNode

logger = logging.getLogger(__name__)


########################################################################################################################
# Functions
########################################################################################################################

def sizeof_fmt(num, suffix='B'):
    for unit in ['','Ki','Mi','Gi','Ti','Pi','Ei','Zi']:
        if abs(num) < 1024.0:
            return "%3.1f%s%s" % (num, unit, suffix)
        num /= 1024.0
    return "%.1f%s%s" % (num, 'Yi', suffix)


def get_packages_for_ar(asset_run):
    blob = asset_run.raw_result_str
    runtype = asset_run.run_type
    scantype = asset_run.scan_type

    assets = []

    if blob:
        if runtype == AssetType.PACKAGE:
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
                            installtimestamp = None
                            if 'installtimestamp' in versions_dict:
                                installtimestamp = versions_dict['installtimestamp']

                            assets.append(
                                BaseAssetPackage(
                                    package_name,
                                    version=versions_dict['version'],
                                    size=versions_dict['size'],
                                    release=versions_dict['release'],
                                    install_date=installtimestamp,
                                    package_type=PackageTypeEnum.LINUX
                                )
                            )

    return assets





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

    def get_install_time_as_datetime(self):
        if self.package_type == PackageTypeEnum.LINUX:
            try:
                return datetime.datetime.fromtimestamp(int(self.install_date))
            except:
                pass

            return None
        else:
            try:
                year = self.install_date[0:4]
                month = self.install_date[4:6]
                day = self.install_date[6:8]

                return datetime.datetime(year=int(year), month=int(month), day=int(day), hour=12)
            except:
                pass

            return None

    def get_as_row(self):
        _name = self.name
        _version = self.version if self.version else "N/A"
        _release = self.release if self.release else "N/A"

        if self.package_type == PackageTypeEnum.LINUX:
            if self.size:
                try:
                    _size = sizeof_fmt(self.size)
                except:
                    _size = "N/A"
            else:
                _size = "N/A"

            if self.install_date:
                try:
                    _install_date = datetime.datetime.fromtimestamp(int(self.install_date)).\
                        strftime(ASSET_DATETIMEFORMAT)
                except:
                    _install_date = "N/A"
            else:
                _install_date = "N/A"
        else:
            if self.size:
                try:
                    _size = sizeof_fmt(int(self.size) * 1024)
                except:
                    _size = "N/A"
            else:
                _size = "N/A"

            _install_date = self.install_date if self.install_date else "N/A"
            if _install_date == "Unknown":
                _install_date = "N/A"

            if _install_date != "N/A":
                try:
                    year = _install_date[0:4]
                    month = _install_date[4:6]
                    day = _install_date[6:8]

                    _install_date = datetime.datetime(year=int(year), month=int(month), day=int(day)).\
                        strftime(ASSET_DATETIMEFORMAT)
                except:
                    _install_date = "N/A"

        o = {}
        o['package_name'] = _name
        o['package_version'] = _version
        o['package_release'] = _release
        o['package_size'] = _size
        o['package_install_date'] = _install_date
        return o

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
# Enums / Globals
########################################################################################################################

ASSET_DATETIMEFORMAT = "%a %d. %b %Y %H:%M:%S"


class AssetType(IntEnum):
    PACKAGE = 1
    HARDWARE = 2  # lstopo
    LICENSE = 3
    UPDATE = 4
    LSHW = 5
    PROCESS = 6
    PENDING_UPDATE = 7
    DMI = 8
    PCI = 9
    PRETTYWINHW = 10
    PARTITION = 11


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
        return "BankLabel:{} FormFactor:{} Memorytype:{} Manufacturer:{} Capacity:{}".format(
            self.banklabel,
            self.get_name_of_form_factor(),
            self.get_name_of_memory_type(),
            self.manufacturer,
            sizeof_fmt(self.capacity)
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
        return "{} [Cores:{}]".format(self.cpuname, self.numberofcores)


class AssetHWGPUEntry(models.Model):
    idx = models.AutoField(primary_key=True)

    gpuname = models.TextField(null=True)

    driverversion = models.TextField(null=True)

    created = models.DateTimeField(auto_now_add=True)

    def __unicode__(self):
        return "{} [Version:{}]".format(self.gpuname, self.driverversion)


# TODO: Remove this model.
class AssetHWHDDEntry(models.Model):
    idx = models.AutoField(primary_key=True)

    name = models.TextField(null=True)

    serialnumber = models.TextField(null=True)

    size = models.BigIntegerField(null=True)

    created = models.DateTimeField(auto_now_add=True)

    def __unicode__(self):
        return "{} [Serialnumber:{} Size:{}]".format(self.name, self.serialnumber, sizeof_fmt(self.size))


class AssetHWLogicalEntry(models.Model):
    idx = models.AutoField(primary_key=True)

    name = models.TextField(null=True)

    size = models.BigIntegerField(null=True)

    free = models.BigIntegerField(null=True)

    created = models.DateTimeField(auto_now_add=True)

    def __unicode__(self):
        return "{} [Size:{} Free:{}]".format(self.name, sizeof_fmt(self.size), sizeof_fmt(self.free))


class AssetHWDisplayEntry(models.Model):
    idx = models.AutoField(primary_key=True)

    name = models.TextField(null=True)

    type = models.TextField(null=True)

    xpixels = models.IntegerField(null=True)

    ypixels = models.IntegerField(null=True)

    manufacturer = models.TextField(null=True)

    def __unicode__(self):
        return "{} [Type:{} xpixels:{} ypixels:{} manufacturer:{}]".format(
            self.name,
            self.type,
            self.xpixels,
            self.ypixels,
            self.manufacturer
        )

class AssetHWNetworkDevice(models.Model):
    idx = models.AutoField(primary_key=True)
    manufacturer = models.TextField(null=True)
    product_name = models.TextField(null=True)
    device_name = models.TextField(null=True)
    speed = models.IntegerField(null=True)
    mac_address = models.TextField(null=True)

    def __unicode__(self):
        return "AssetHWNetworkDevice[Manufacturer:{}|Product Name:{}|"\
            "Device Name:{}|Speed:{}]".format(
                self.manufacturer,
                self.product_name,
                self.device_name,
                self.speed,
            )

class AssetPackageVersionInstallTime(models.Model):
    idx = models.AutoField(primary_key=True)
    package_version = models.ForeignKey("backbone.AssetPackageVersion")
    timestamp = models.BigIntegerField()

    @property
    def install_time(self):
        return datetime.datetime.fromtimestamp(float(self.timestamp))

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
    # optional
    optional = models.BooleanField(default=True)
    # installed
    installed = models.BooleanField(default=False)
    # new version (for RPMs)
    new_version = models.CharField(default="", max_length=64)

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
    # run index in current batch
    batch_index = models.IntegerField(default=0)
    raw_result_str = models.TextField(null=True)
    raw_result_interpreted = models.BooleanField(default=False)
    scan_type = models.IntegerField(choices=[(_type.value, _type.name) for _type in ScanType], null=True)

    created = models.DateTimeField(auto_now_add=True)

    def is_finished_processing(self):
        if self.interpret_error_string or self.generate_duration:
            return True
        return False

    @property
    def hdds(self):
        if self.asset_batch and self.asset_batch.partition_table:
            return self.asset_batch.partition_table.partition_disc_set.all()
        return []

    @property
    def cpus(self):
        return self.asset_batch.cpus.all()

    @property
    def gpus(self):
        return self.asset_batch.gpus.all()

    @property
    def partitions(self):
        return self.asset_batch.partitions.all()

    @property
    def displays(self):
        return self.asset_batch.displays.all()

    @property
    def memory_modules(self):
        return self.asset_batch.memory_modules.all()

    @property
    def cpu_count(self):
        return len(self.asset_batch.cpus.all())

    @property
    def memory_count(self):
        return len(self.asset_batch.memory_modules.all())

    @property
    def packages(self):
        return [package.idx for package in self.asset_batch.packages.all()]

    @property
    def packages_install_times(self):
        return self.asset_batch.packages_install_times.all()

    @property
    def device(self):
        return self.asset_batch.device.idx

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

    def has_data(self):
        return RunResult(self.run_result) == RunResult.SUCCESS

    @property
    def raw_result(self):
        raw = self.raw_result_str
        if self.scan_type == ScanType.NRPE:
            if raw.startswith("b'"):
                raw = raw[2:-2]
            result = bz2.decompress(base64.b64decode(raw))
        elif self.scan_type == ScanType.HM:
            # parse XML
            result = etree.fromstring(raw)
        else:
            raise NotImplemented
        return result

    def generate_assets(self):
        function_name = '_generate_assets_{}_{}'.format(
            AssetType(self.run_type)._name_.lower(),
            ScanType(self.scan_type)._name_.lower()
        )
        func = getattr(self, function_name)
        if not self.raw_result_interpreted:
            # call the appropriate _generate_assets_... method
            func(self.raw_result)
            self.save()

    def _generate_assets_package_nrpe(self, data):
        assets = []
        if self.scan_type == ScanType.NRPE:
            l = json.loads(data)
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
        self._generate_assets_package(assets)

    def _generate_assets_package_hm(self, tree):
        blob = tree.xpath('ns0:pkg_list', namespaces=tree.nsmap)[0].text
        assets = []
        try:
            package_dict = server_command.decompress(blob, pickle=True)
        except:
            raise
        else:
            for package_name in package_dict:
                for versions_dict in package_dict[package_name]:
                    installtimestamp = None
                    if 'installtimestamp' in versions_dict:
                        installtimestamp = versions_dict['installtimestamp']
                    assets.append(
                        BaseAssetPackage(
                            package_name,
                            version=versions_dict['version'],
                            size=versions_dict['size'],
                            release=versions_dict['release'],
                            install_date=installtimestamp,
                            package_type=PackageTypeEnum.LINUX
                        )
                    )
        self._generate_assets_package(assets)

    def _generate_assets_package(self, assets):
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
            self.asset_batch.packages.add(apv)

            install_time = ba.get_install_time_as_datetime()

            if install_time:
                timestamp = time.mktime(install_time.timetuple())

                apv_install_times = AssetPackageVersionInstallTime.objects.filter(
                    package_version=apv,
                    timestamp=timestamp
                )

                if not apv_install_times:
                    apv_install_time = AssetPackageVersionInstallTime(
                        package_version=apv,
                        timestamp=timestamp
                    )

                    apv_install_time.save()
                else:
                    apv_install_time = apv_install_times[0]

                self.asset_batch.packages_install_times.add(apv_install_time)

    def _generate_assets_hardware_nrpe(self, data):
        self._generate_assets_hardware(etree.fromstring(data))

    def _generate_assets_hardware_hm(self, tree):
        blob = tree.xpath('ns0:lstopo_dump', namespaces=tree.nsmap)[0].text
        xml_str = bz2.decompress(base64.b64decode(blob))
        root = etree.fromstring(xml_str)
        self._generate_assets_hardware(root)

    def _generate_assets_hardware(self, root):
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
                    asset_run=self,
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

    def _generate_assets_license_nrpe(self, data):
        l = json.loads(data)
        for (name, licensekey) in l:
            new_lic = AssetLicenseEntry(
                name=name,
                license_key=licensekey,
                asset_run=self,
            )
            new_lic.save()

    def _generate_assets_pending_update_nrpe(self, data):
        l = json.loads(data)
        for (name, optional) in l:
            asset_update_entry = AssetUpdateEntry.objects.filter(
                name=name,
                version="",
                release="",
                kb_idx=0,
                install_date=None,
                status="",
                optional=optional,
                installed=False,
                new_version=""
                )
            if asset_update_entry:
                asset_update_entry = asset_update_entry[0]
            else:
                asset_update_entry = AssetUpdateEntry(
                    name=name,
                    installed=False,
                    optional=optional,
                )
                asset_update_entry.save()

            print asset_update_entry
            self.asset_batch.pending_updates.add(asset_update_entry)

    def _generate_assets_pending_update_hm(self, tree):
        blob = tree.xpath('ns0:update_list', namespaces=tree.nsmap)[0]\
            .text
        l = server_command.decompress(blob, pickle=True)
        for (name, version) in l:
            asset_update_entry = AssetUpdateEntry.objects.filter(
                name=name,
                version="",
                release="",
                kb_idx=0,
                install_date=None,
                status="",
                optional=True,
                installed=False,
                new_version=version
                )
            if asset_update_entry:
                asset_update_entry = asset_update_entry[0]
            else:
                asset_update_entry = AssetUpdateEntry(
                    name=name,
                    # by definition linux updates are optional
                    optional=True,
                    installed=False,
                    new_version=version,
                )
                asset_update_entry.save()

            print asset_update_entry
            self.asset_batch.pending_updates.add(asset_update_entry)

    def _generate_assets_update_nrpe(self, data):
        l = json.loads(data)
        for (name, up_date, status) in l:
            asset_update_entry = AssetUpdateEntry.objects.filter(
                name=name,
                version="",
                release="",
                kb_idx=0,
                install_date=dateparse.parse_datetime(up_date),
                status=status,
                optional=False,
                installed=True,
                new_version=""
                )
            if asset_update_entry:
                asset_update_entry = asset_update_entry[0]
            else:
                asset_update_entry = AssetUpdateEntry(
                    name=name,
                    install_date=dateparse.parse_datetime(up_date),
                    status=status,
                    optional=False,
                    installed=True
                )
                asset_update_entry.save()

            print asset_update_entry
            self.asset_batch.installed_updates.add(asset_update_entry)

    def _generate_assets_process_nrpe(self, data):
        l = json.loads(data)
        process_dict = {int(pid): {"name": name} for name, pid in l}
        self._generate_assets_process(process_dict)

    def _generate_assets_process_hm(self, tree):
        blob = tree.xpath('ns0:process_tree', namespaces=tree.nsmap)[0]\
            .text
        # TODO: Remove eval().
        process_dict = eval(bz2.decompress(base64.b64decode(blob)))
        self._generate_assets_process(process_dict)

    def _generate_assets_process(self, process_dict):
        for pid, stuff in process_dict.iteritems():
            new_proc = AssetProcessEntry(
                pid=pid,
                name=stuff["name"],
                asset_run=self,
            )
            new_proc.save()

    def _generate_assets_pci_nrpe(self, data):
        info_dicts = []
        info_dict = {}
        for line in data.decode().split("\r\n"):
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
                asset_run=self,
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

    def _generate_assets_pci_hm(self, tree):
        blob = tree.xpath('ns0:pci_dump', namespaces=tree.nsmap)[0].text
        s = pci_database.pci_struct_to_xml(
            pci_database.decompress_pci_info(blob)
        )
        for func in s.findall(".//func"):
            _slot = func.getparent()
            _bus = _slot.getparent()
            _domain = _bus.getparent()
            new_pci = AssetPCIEntry(
                asset_run=self,
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

    def _generate_assets_dmi_nrpe(self, blob):
        _lines = []
        for line in blob.decode().split("\r\n"):
            _lines.append(line)
            if line == "End Of Table":
                break
        xml = dmi_tools.dmi_struct_to_xml(dmi_tools.parse_dmi_output(_lines))
        self._generate_assets_dmi(xml)

    def _generate_assets_dmi_hm(self, tree):
        blob = tree.xpath('ns0:dmi_dump', namespaces=tree.nsmap)[0].text
        xml = dmi_tools.decompress_dmi_info(blob)
        self._generate_assets_dmi(xml)

    def _generate_assets_dmi(self, xml):
        head = AssetDMIHead(
            asset_run=self,
            version=xml.get("version"),
            size=int(xml.get("size")),
        )
        head.save()
        for _handle in xml.findall(".//handle"):
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

    def _generate_assets_prettywinhw_nrpe(self, blob):
        # The information is processed in
        # AssetBatch._generate_assets_from_raw_results() on completion of all
        # asset runs.
        pass

    def _generate_assets_lshw_hm(self, tree):
        # The information is processed in
        # AssetBatch._generate_assets_from_raw_results() on completion of all
        # asset runs.
        pass

    def _generate_assets_partition_hm(self, tree):
        result = srv_command(source=tree)
        target_dev = self.asset_batch.device
        res_node = ResultNode()
        try:
            dev_dict, lvm_dict = (
                result["dev_dict"],
                result["lvm_dict"],
            )
        except KeyError:
            res_node.error(u"%s: error missing keys in dict" % (target_dev))
        else:
            if "sys_dict" in result:
                sys_dict = result["sys_dict"]
                for _key, _value in sys_dict.iteritems():
                    if type(_value) == list and len(_value) == 1:
                        _value = _value[0]
                        sys_dict[_key] = _value
                    # rewrite dict
                    _value["opts"] = _value["options"]
            else:
                partitions = result["*partitions"]
                sys_dict = {
                    _part["fstype"]: _part for _part in partitions if not _part["is_disk"]
                }
            try:
                _old_stuff = server_command.decompress(lvm_dict.text)
            except:
                lvm_info = partition_tools.lvm_struct("xml", xml=lvm_dict)
            else:
                raise ValueError("it seems the client is using pickled transfers")
            partition_name, partition_info = (
                "{}_part".format(target_dev.full_name),
                "generated partition_setup from device '%s'" % (target_dev.full_name))
            prev_th_dict = {}
            try:
                cur_pt = partition_table.objects.get(Q(name=partition_name))
            except partition_table.DoesNotExist:
                pass
            else:
                # read previous settings
                for entry in cur_pt.partition_disc_set.all().values_list(
                    "partition__mountpoint",
                    "partition__warn_threshold",
                    "partition__crit_threshold",
                ):
                    prev_th_dict[entry[0]] = (entry[1], entry[2])
                for entry in cur_pt.lvm_vg_set.all().values_list(
                        "lvm_lv__mountpoint", "lvm_lv__warn_threshold", "lvm_lv__crit_threshold"
                ):
                    prev_th_dict[entry[0]] = (entry[1], entry[2])
                if cur_pt.user_created:
                    logger.warning(
                        "prevision partition_table '{}' was user created, not deleting".format(unicode(cur_pt)),
                    )
                else:
                    logger.info("deleting previous partition_table {}".format(unicode(cur_pt)))
                    for _dev in get_related_models(cur_pt, detail=True):
                        for _attr_name in ["act_partition_table", "partition_table"]:
                            if getattr(_dev, _attr_name) == cur_pt:
                                logger.info("clearing attribute {} of {}".format(_attr_name, unicode(_dev)))
                                setattr(_dev, _attr_name, None)
                                _dev.save(update_fields=[_attr_name])
                    if get_related_models(cur_pt):
                        raise SystemError("unable to delete partition {}".format(unicode(cur_pt)))
                    cur_pt.delete()
                target_dev.act_partition_table = None
            # fetch partition_fs
            fs_dict = {}
            for db_rec in partition_fs.objects.all():
                fs_dict.setdefault(("{:02x}".format(int(db_rec.hexid, 16))).lower(), {})[db_rec.name] = db_rec
                fs_dict[db_rec.name] = db_rec
            new_part_table = partition_table(
                name=partition_name,
                description=partition_info,
                user_created=False,
            )
            new_part_table.save()
            for dev, dev_stuff in dev_dict.iteritems():
                if dev.startswith("/dev/sr"):
                    logger.warning("skipping device {}".format(dev))
                    continue
                logger.info("handling device %s" % (dev))
                new_disc = partition_disc(partition_table=new_part_table,
                                          disc=dev)
                new_disc.save()
                for part in sorted(dev_stuff):
                    part_stuff = dev_stuff[part]
                    ("   handling partition %s" % (part))
                    if "multipath" in part_stuff:
                        # see machinfo_mod.py, lines 1570 (partinfo_command:interpret)
                        real_disk = [entry for entry in part_stuff["multipath"]["list"] if entry["status"] == "active"]
                        if real_disk:
                            mp_id = part_stuff["multipath"]["id"]
                            real_disk = real_disk[0]
                            if part is None:
                                real_disk, real_part = ("/dev/%s" % (real_disk["device"]), part)
                            else:
                                real_disk, real_part = ("/dev/%s" % (real_disk["device"]), part[4:])
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
                    hex_type = part_stuff["hextype"]
                    if hex_type is None:
                        logger.warning("ignoring partition because hex_type = None")
                    else:
                        hex_type = hex_type[2:].lower()
                        if part is None:
                            # special multipath without partition
                            part = "0"
                        elif part.startswith("part"):
                            # multipath
                            part = part[4:]
                        elif part.startswith("p"):
                            # compaq array
                            part = part[1:]
                        if "mountpoint" in part_stuff:
                            fs_stuff = fs_dict.get(hex_type, {}).get(part_stuff["fstype"].lower(), None)
                            if fs_stuff is None and "fstype" in part_stuff and part_stuff["fstype"] in fs_dict:
                                fs_stuff = fs_dict[part_stuff["fstype"]]
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
                                logger.warning("skipping partition {} because fs_stuff is None".format(part))
                                new_part = None
                        else:
                            if hex_type in fs_dict:
                                if hex_type == "82":
                                    new_part = partition(
                                        partition_disc=new_disc,
                                        partition_hex=hex_type,
                                        size=part_stuff["size"],
                                        pnum=part,
                                        partition_fs=fs_dict[hex_type].values()[0],
                                        mount_options="defaults",
                                    )
                                else:
                                    logger.error(
                                        "skipping partition {} because no mountpoint and no matching fs_dict (hex_type {})".format(
                                            part,
                                            hex_type
                                        ))
                                    new_part = None
                            else:
                                new_part = partition(
                                    partition_disc=new_disc,
                                    partition_hex=hex_type,
                                    size=part_stuff["size"],
                                    pnum=part,
                                )
                                new_part = None
                                logger.error("no mountpoint defined")
                        if new_part is not None:
                            if new_part.mountpoint in prev_th_dict:
                                new_part.warn_threshold, new_part.crit_threshold = prev_th_dict[new_part.mountpoint]
                            new_part.save()
                        _part_name = "%s%s" % (dev, part)
            for part, part_stuff in sys_dict.iteritems():
                logger.info("handling part %s (sys)" % (part))
                if type(part_stuff) == dict:
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
                            mount_options=p_stuff["opts"],
                        )
                        new_sys.save()
            if lvm_info.lvm_present:
                logger.info("LVM info is present")
                # lvm save
                for vg_name, v_group in lvm_info.lv_dict.get("vg", {}).iteritems():
                    logger.info("handling VG %s" % (vg_name))
                    new_vg = lvm_vg(
                        partition_table=new_part_table,
                        name=v_group["name"])
                    new_vg.save()
                    v_group["db"] = new_vg
                for lv_name, lv_stuff in lvm_info.lv_dict.get("lv", {}).iteritems():
                    logger.info("handling LV %s" % (lv_name))
                    mount_options = lv_stuff.get(
                        "mount_options", {
                            "dump": 0,
                            "fsck": 0,
                            "mountpoint": "",
                            "options": "",
                            "fstype": "",
                        }
                    )
                    mount_options["fstype_idx"] = None
                    if mount_options["fstype"]:
                        mount_options["fstype_idx"] = fs_dict.get("83", {}).get(mount_options["fstype"].lower(), None)
                        if mount_options["fstype_idx"]:
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
                            if new_lv.mountpoint in prev_th_dict:
                                new_lv.warn_threshold, new_lv.crit_threshold = prev_th_dict[new_lv.mountpoint]
                            new_lv.save()
                            lv_stuff["db"] = new_lv
                        else:
                            logger.error(
                                "no fstype found for LV %s (fstype %s)" % (
                                    lv_stuff["name"],
                                    mount_options["fstype"],
                                )
                            )
                    else:
                        logger.error(
                            "no fstype found for LV %s" % (lv_stuff["name"])
                        )
            # set partition table
            logger.info(u"set partition_table for '%s'" % (unicode(target_dev)))
            target_dev.act_partition_table = new_part_table
            target_dev.partdev = ""
            target_dev.save(update_fields=["act_partition_table", "partdev"])


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
    # fields generated from raw entries
    packages = models.ManyToManyField(AssetPackageVersion)
    packages_install_times = models.ManyToManyField(AssetPackageVersionInstallTime)
    cpus = models.ManyToManyField(AssetHWCPUEntry)
    memory_modules = models.ManyToManyField(AssetHWMemoryEntry)
    gpus = models.ManyToManyField(AssetHWGPUEntry)
    partition_table = models.ForeignKey(
        "backbone.partition_table",
        on_delete=models.SET_NULL,
        null=True,
    )
    network_devices = models.ManyToManyField(AssetHWNetworkDevice)

    pending_updates = models.ManyToManyField(AssetUpdateEntry, related_name="assetbatch_pending_updates")
    installed_updates = models.ManyToManyField(AssetUpdateEntry, related_name="assetbatch_installed_updates")

    # TODO: Remove this.
    partitions = models.ManyToManyField(AssetHWLogicalEntry)
    displays = models.ManyToManyField(AssetHWDisplayEntry)

    @property
    def is_finished_processing(self):
        for assetrun in self.assetrun_set.all():
            if not assetrun.is_finished_processing():
                return False
        return True

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
            self._generate_assets_from_raw_results()
        self.save()

    def __repr__(self):
        return unicode(self)

    def __unicode__(self):
        return "AssetBatch for device '{}'".format(
            unicode(self.device)
        )

    def _generate_assets_from_raw_results(self):
        """Set the batch level hardware information (.cpus, .memory_modules
        etc.) from the acquired asset runs."""
        runs = [
            ("win32_tree", AssetType.PRETTYWINHW, json.loads),
            ("lshw_tree", AssetType.LSHW, etree.fromstring),
            ]

        # search for relevant asset runs and Base64 decode and unzip the result
        run_results = {}
        for (arg_name, asset_type, parser) in runs:
            parsed = None
            try:
                run = self.assetrun_set.filter(run_type=asset_type).get()
            except AssetRun.DoesNotExist:
                pass
            else:
                if run.scan_type == ScanType.NRPE:
                    blob = run.raw_result
                elif run.scan_type == ScanType.HM:
                    tree = run.raw_result
                    blob = tree.xpath(
                        'ns0:lshw_dump',
                        namespaces=tree.nsmap
                    )[0].text
                    blob = bz2.decompress(base64.b64decode(blob))

                # parse raw_data
                parsed = parser(blob)
            run_results[arg_name] = parsed

        # check if we have the necessary asset runs
        if not ('win32_tree' in run_results or 'lshw_tree' in run_results):
            return
        hw = Hardware(**run_results)

        # set the CPUs
        self.cpus.all().delete()
        for cpu in hw.cpus:
            new_cpu = AssetHWCPUEntry(cpuname=cpu.product,
                numberofcores=cpu.number_of_cores)
            new_cpu.save()
            self.cpus.add(new_cpu)

        # set the memory modules
        self.memory_modules.all().delete()
        for memory_module in hw.memory_modules:
            new_memory_module = AssetHWMemoryEntry(
                banklabel=memory_module.bank_label,
                manufacturer=memory_module.manufacturer,
                capacity=memory_module.capacity,
            )
            new_memory_module.save()
            self.memory_modules.add(new_memory_module)

        # set the GPUs
        self.gpus.all().delete()
        for gpus in hw.gpus:
            new_gpu = AssetHWGPUEntry(gpuname=gpus.description)
            new_gpu.save()
            self.gpus.add(new_gpu)

        # set the discs and partitions
        fs_dict = {fs.name: fs for fs in partition_fs.objects.all()}

        name = "_".join([self.device.name, "part", str(self.idx)])
        partition_table_ = partition_table(
            name=name,
            description='partition information generated during asset run',
        )
        partition_table_.save()
        for hdd in hw.hdds:
            disc = partition_disc(
                partition_table=partition_table_,
                disc=hdd.device_name,
            )
            disc.save()

            for hdd_partition in hdd.partitions:
                partition_ = partition(
                    partition_disc=disc,
                    pnum=hdd_partition.index,
                    size=hdd_partition.size,
                )
                if hdd_partition.logical:
                    partition_fs_ = \
                        fs_dict[hdd_partition.logical.file_system.lower()]
                else:
                    partition_fs_ = fs_dict["empty"]
                partition_.partition_fs = partition_fs_
                partition_.save()
                if hdd_partition.logical:
                    logical = LogicalDisc(
                        device_name=hdd_partition.logical.device_name,
                        partition_fs=partition_fs_,
                        size=hdd_partition.logical.size,
                        free_space=hdd_partition.logical.free_space,
                    )
                    logical.save()
                    logical.partitions.add(partition_)
        self.partition_table = partition_table_
        # set the partition info on the device
        self.device.act_partition_table = partition_table_
        self.device.save()

        # set the network devices
        self.network_devices.all().delete()
        for network_device in hw.network_devices:
            new_network_device = AssetHWNetworkDevice(
                manufacturer=network_device.manufacturer,
                product_name=network_device.product,
                device_name=network_device.device_name,
                speed=network_device.speed,
                mac_address=network_device.mac_address
                )
            new_network_device.save()
            self.network_devices.add(new_network_device)

        # TODO: Set displays.


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

def sizeof_fmt(num, suffix='B'):
    if num is None:
        return "N/A"
    for unit in ['', 'Ki', 'Mi', 'Gi', 'Ti', 'Pi', 'Ei', 'Zi']:
        if abs(num) < 1024.0:
            return "%3.1f%s%s" % (num, unit, suffix)
        num /= 1024.0
    return "%.1f%s%s" % (num, 'Yi', suffix)
