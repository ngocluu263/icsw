
# Copyright (C) 2015-2016 Bernhard Mallinger, Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <mallinger@init.at>, <lang-nevyjel@init.at>
#
# This file is part of icsw-server
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License Version 3 as
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
# -*- coding: utf-8 -*-
#

""" database definitions for license / ova management """

from __future__ import print_function, unicode_literals

import collections
import datetime
import logging

import django.utils.timezone
import enum
from dateutil import relativedelta
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import signals, Q
from django.dispatch import receiver

from initat.cluster.backbone.available_licenses import get_available_licenses, LicenseEnum, LicenseParameterTypeEnum
from initat.cluster.backbone.models.functions import memoize_with_expiry, cluster_timezone
from initat.tools import logging_tools
from .license_xml import ICSW_XML_NS, ICSW_XML_NS_NAME, ICSW_XML_NS_MAP, LIC_FILE_RELAX_NG_DEFINITION

__all__ = [
    b"LicenseState",
    b"License",
    b"LicenseEnum",
    b"LicenseParameterTypeEnum",
    b"ICSW_XML_NS",
    b"ICSW_XML_NS_MAP",
    b"ICSW_XML_NS_NAME",
    b"LIC_FILE_RELAX_NG_DEFINITION",
    b"icswEggCradle",
    b"icswEggEvaluationDef",
    b"icswEggBasket",
    b"icswEggConsumer",
    b"icswEggRequest",
    b"LICENSE_USAGE_GRACE_PERIOD",
]

logger = logging.getLogger("cluster.icsw_license")

LICENSE_USAGE_GRACE_PERIOD = relativedelta.relativedelta(weeks=2)


class InitProduct(enum.Enum):
    CORVUS = 1
    NOCTUA = 2
    NESTOR = 3

    def get_version_family(self, version):
        if version == "0.0":
            version = _PRODUCT_FAMILY_MATRIX.keys()[-1]

        return _PRODUCT_FAMILY_MATRIX.get(version, {}).get(self, "")

_PRODUCT_FAMILY_MATRIX = collections.OrderedDict(  # ordered dict so we know which is last
    [
        (
            "2.5",
            {
                InitProduct.CORVUS: u"Corvus hawaiiensis",  # Hawaiikraehe
                InitProduct.NOCTUA: u"Strigidae occidentalis",  # Fleckenkauz
                InitProduct.NESTOR: u"Nestor notabilis",  # Kea
            }
        ),
        (
            "3.0",
            {
                InitProduct.CORVUS: u"CORVUS Corax",  # Kolkrabe
                InitProduct.NOCTUA: u"NOCTUA Athene",  # Steinkauz
                InitProduct.NESTOR: u"NESTOR Notabilis",  # Kea
            }
        ),
        (
            "3.1",
            {
                InitProduct.CORVUS: u"Corvus splendens",  # Glanzkraehe
                InitProduct.NOCTUA: u"Strigidae rufipes",  # Rostfusskauz
                InitProduct.NESTOR: u"Nestor meridionalis",  # Kaka (Waldpapagei)
            }
        )
    ]
)


class LicenseState(enum.IntEnum):
    # NOTE: this is ordered in the sense that if multiple licenses are
    # present, the higher one is actually used
    violated = 120        # license parameters have been violated
    valid = 100           # license is valid now
    grace = 80            # license has expired but we still let the software run
    new_install = 60      # to be defined
    expired = 40          # license used to be valid but is not valid anymore
    valid_in_future = 20  # license will be valid in the future
    none = 0              # license not present
    not_needed = -1       # license not needed
    ip_mismatch = 200     # IP mismatch, should not run
    fp_mismatch = 300     # fingerprint mismatch, should not run

    def is_valid(self):
        # states where we consider the license to be valid, i.e. the user may access the feature
        return self in (LicenseState.valid, LicenseState.grace, LicenseState.new_install)


class _LicenseManager(models.Manager):
    """
    Interface to licenses in db.
    """

    def _get_license_state(self, license, parameters=None, ignore_violations=False):
        """Returns the license state for this license
        :type license: LicenseEnum
        :param parameters: {LicenseParameterTypeEnum: int} of required parameters
        """
        # TODO: new_install?
        if not self._license_readers:
            return LicenseState.none
        _states = [r.get_license_state(license, parameters) for r in self._license_readers]
        _valid_states = [_state for _state in _states if _state not in [LicenseState.fp_mismatch]]
        if len(_valid_states):
            return max(_valid_states)
        else:
            return LicenseState.fp_mismatch

    ########################################
    # Accessors for actual program logic

    def has_valid_license(self, license, parameters=None, ignore_violations=False):
        """Returns whether we currently have this license in some valid state.
        :type license: LicenseEnum
        :param parameters: {LicenseParameterTypeEnum: int} of required parameters
        :rtype: bool
        """
        return self._get_license_state(license, parameters, ignore_violations=ignore_violations).is_valid()

    def fingerprint_ok(self, license):
        # return false even when no licenses are present, ToDo, FIXME
        return any([r.fingerprint_ok for r in self._license_readers if r.has_license(license)])

    def license_exists(self, lic_content):
        from initat.cluster.backbone.license_file_reader import LicenseFileReader
        _pure_content = LicenseFileReader.get_pure_data(lic_content)
        _present = False
        # only compare with the latest version ? ToDo, Fixme
        for value in self.values_list("license_file", flat=True):
            _loc_pc = LicenseFileReader.get_pure_data(value)
            if _loc_pc == _pure_content:
                _present = True
                break
        return _present

    ########################################
    # Accessors for views for client

    def get_init_product(self):
        valid_lics = set(self.get_valid_licenses())
        # print(valid_lics)
        product_licenses = set()
        # all available licenses
        for available_lic in get_available_licenses():
            if available_lic.enum_value in valid_lics:
                if available_lic.product is not None:
                    # print("   ", available_lic.product)
                    product_licenses.add(available_lic.product)

        # print("+", product_licenses)
        # this does currently not happen:
        if InitProduct.CORVUS in product_licenses:
            return InitProduct.CORVUS

        # unlicensed version
        if not product_licenses:
            # decision by AL, BM, SR (20150519): if the product is not decided, it can become anything, so it's a CORVUS
            return InitProduct.CORVUS

        if InitProduct.NESTOR in product_licenses and InitProduct.NOCTUA in product_licenses:
            return InitProduct.CORVUS
        else:
            # can only contain one
            return next(iter(product_licenses))

    def get_license_info(self):
        return sum([_reader.license_info(raw=True) for _reader in self._license_readers], [])

    def get_valid_licenses(self):
        """
        Returns all licenses which are active (and should be displayed to the user)
        Problem: if you upload multiple license files (== license-packs) with the
        same name / UUID the system will return the any valid licenses and not the one
        from the latest files
        Quick fix: delete previous license files
        """
        return [
            lic for lic in set().union(
                *[
                    r.get_valid_licenses() for r in self._license_readers
                ]
            )
        ]

    def get_license_packages(self):
        """Returns license packages in custom format for the client."""
        from initat.cluster.backbone.license_file_reader import LicenseFileReader
        return LicenseFileReader.get_license_packages(self._license_readers)

    _license_readers_cache = {}

    @property
    @memoize_with_expiry(10, _cache=_license_readers_cache)
    def _license_readers(self):
        from initat.cluster.backbone.license_file_reader import LicenseFileReader
        from initat.cluster.backbone.models import device_variable
        from initat.tools import hfp_tools
        cluster_id = device_variable.objects.get_cluster_id()
        cur_fp = hfp_tools.get_server_fp(serialize=True)
        readers = []
        for file_content, file_name in self.values_list('license_file', 'file_name'):
            try:
                readers.append(
                    LicenseFileReader(
                        file_content,
                        file_name,
                        cluster_id=cluster_id,
                        current_fingerprint=cur_fp
                    )
                )
            except LicenseFileReader.InvalidLicenseFile as e:
                logger.error(
                    "Invalid license file in database {}: {}".format(
                        file_name,
                        e
                    )
                )

        return readers


########################################
# actual license documents:


class License(models.Model):
    objects = _LicenseManager()

    idx = models.AutoField(primary_key=True)

    date = models.DateTimeField(auto_now_add=True)

    file_name = models.CharField(max_length=512)
    license_file = models.TextField()  # contains the exact file content of the respective license files

    def __unicode__(self):
        from initat.cluster.backbone.license_file_reader import LicenseFileReader
        _reader = LicenseFileReader(self.license_file, self.file_name)
        return _reader.license_info()

    class Meta:
        app_label = "backbone"
        verbose_name = "License"
        ordering = ("idx",)


@receiver(signals.post_save, sender=License)
@receiver(signals.post_delete, sender=License)
def license_save(sender, **kwargs):
    _LicenseManager._license_readers_cache.clear()


@receiver(signals.post_save, sender=License)
def license_post_save(sender, **kwargs):
    if "instance" in kwargs:
        cur_inst = kwargs["instance"]
        print(cur_inst)


########################################
# license usage management:

class icswEggCradleManager(models.Manager):
    def create_system_cradle(self):
        _sc = self.create(
            system_cradle=True
        )
        return _sc

    def get_system_cradle(self):
        try:
            _sc = self.get(Q(system_cradle=True))
        except icswEggCradle.DoesNotExist:
            return None
        else:
            return _sc


class icswEggCradle(models.Model):
    """
    container for all baskets, more than one cradle may be defined
    but only one is a system cradle

    grace handling: when the system requires more eggs then available, the grace_period
    starts to run. During this time up to limit_grace eggs can be consumed, if this
    limit is reached the system will no longer accept new egg requests
    """
    objects = icswEggCradleManager()
    idx = models.AutoField(primary_key=True)
    # is a sytem basket, only one allowed (and no user baskets defined)
    system_cradle = models.BooleanField(default=True)
    # how many eggs are currently installed (and covered by licenses)
    installed = models.IntegerField(default=0)
    # how many eggs are currently available (must be smaller or equal to the installed eggs)
    available = models.IntegerField(default=0)
    # grace days, defaults to 14 days
    grace_days = models.IntegerField(default=14)
    # start of grace period
    grace_start = models.DateTimeField(null=True)
    # limit of eggs when in grace, defaults to 110% of installed
    limit_grace = models.IntegerField(default=0)
    # creation date
    date = models.DateTimeField(auto_now_add=True)

    def calc(self):
        _avail = 0
        _installed = 0
        for _basket in icswEggBasket.objects.get_valid_baskets():
            if _basket:
                _avail += _basket.eggs
                _installed += _basket.eggs
        for _cons in self.icsweggconsumer_set.all():
            _avail -= _cons.get_all_consumed()
        self.available = _avail
        self.installed = _installed
        self.save(update_fields=["available", "installed"])

    def __unicode__(self):
        return "EggCradle, {:d} installed, {:d} available".format(
            self.installed,
            self.available,
        )


class icswEggBasketManager(models.Manager):
    def get_valid_baskets(self):
        _now = django.utils.timezone.now()
        return self.filter(
            Q(egg_cradle__system_cradle=True) &
            Q(is_valid=True) &
            Q(valid_from__lte=_now) &
            Q(valid_to__gte=_now)
        )

    def num_valid_baskets(self):
        return self.get_valid_baskets().count()

    def create_dummy_basket(self, eggs=10, validity=20):
        _now = django.utils.timezone.now()
        _sys_c = icswEggCradle.objects.get(Q(system_cradle=True))
        _new_b = self.create(
            egg_cradle=_sys_c,
            dummy=True,
            is_valid=True,
            valid_from=_now - datetime.timedelta(days=1),
            valid_to=_now.replace(year=_now.year + validity),
            eggs=eggs,
        )
        return _new_b


class icswEggBasket(models.Model):
    objects = icswEggBasketManager()
    # basket definition, from ovum global parameters
    idx = models.AutoField(primary_key=True)
    # basket
    egg_cradle = models.ForeignKey(icswEggCradle)
    # dummy entry
    dummy = models.BooleanField(default=False)
    # valid from / to
    valid_from = models.DateField()
    valid_to = models.DateField()
    # valid flag
    is_valid = models.BooleanField(default=True)
    # link to license, null for default basket
    license = models.ForeignKey(License, null=True)
    # eggs defined
    eggs = models.IntegerField(default=0)
    # creation date
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = False

    def __unicode__(self):
        return "EggBasket (valid={})".format(self.is_valid)


@receiver(signals.post_save, sender=icswEggBasket)
def icsw_egg_basket_post_save(sender, **kwargs):
    if "instance" in kwargs:
        _inst = kwargs["instance"]
        _inst.egg_cradle.calc()


class icswEggEvaluationDefManager(models.Manager):
    def get_active_def(self):
        try:
            _cd = self.get(Q(active=True))
        except icswEggEvaluationDef.DoesNotExist:
            _cd = None
        return _cd

    def create_dummy_def(self):
        _sys_c = icswEggCradle.objects.get(Q(system_cradle=True))
        _new_b = self.create(
            egg_cradle=_sys_c,
            content="",
            dummy=True,
            active=True,
        )
        return _new_b


class icswEggEvaluationDef(models.Model):
    """
    Egg evaluation definition
    """
    objects = icswEggEvaluationDefManager()
    # defining files for eggbasketconsumers
    idx = models.AutoField(primary_key=True)
    # cradle
    egg_cradle = models.ForeignKey(icswEggCradle)
    # content
    content = models.TextField(default="")
    # dummy entry
    dummy = models.BooleanField(default=False)
    # active flag, at least one Def must be active
    active = models.BooleanField(default=False)
    # creation date
    date = models.DateTimeField(auto_now_add=True)

    def create_consumers(self):
        from initat.cluster.backbone.server_enums import icswServiceEnum
        from initat.cluster.backbone.models import ConfigServiceEnum
        if not self.active:
            raise StandardError("Cannot create consumers from inactive EggEvaluationDef")
        icswEggConsumer.objects.filter(Q(content_type=None)).delete()
        # create or update all consumers
        # build list of required consumers
        _c_list = []
        for _name, _server in icswServiceEnum.get_server_enums().iteritems():
            _cs_enum = ConfigServiceEnum.objects.get(Q(enum_name=_name))
            if _server.egg_actions:
                for _action in _server.egg_actions:
                    _c_list.append(
                        {
                            "action": _action,
                            "service": _server,
                            "db_enum": _cs_enum,
                        }
                    )
        for _entry in _c_list:
            try:
                _cur_consum = icswEggConsumer.objects.get(
                    Q(action=_entry["action"].action) &
                    Q(content_type=_entry["action"].content_type) &
                    Q(config_service_enum=_entry["db_enum"]) &
                    Q(egg_cradle=self.egg_cradle)
                )
            except icswEggConsumer.DoesNotExist:
                # create new
                _cur_consum = icswEggConsumer.objects.create(
                    egg_evaluation_def=self,
                    xml_node_reference="",
                    egg_cradle=self.egg_cradle,
                    # multiplier=_entry["action"].weight,
                    content_type=_entry["action"].content_type,
                    action=_entry["action"].action,
                    config_service_enum=_entry["db_enum"],
                    valid=False,
                )
            else:
                if _cur_consum.egg_evaluation_def.idx != self.idx:
                    _cur_consum.valid = False
            _cur_consum.valid = False
            if _entry["action"].weight != _cur_consum.multiplier:
                _cur_consum.multiplier = _entry["action"].weight
                _cur_consum.valid = False
            if _entry["action"].timeframe_secs != _cur_consum.timeframe_secs:
                _cur_consum.timeframe_secs = _entry["action"].timeframe_secs
                _cur_consum.valid = False
            _cur_consum.save()

    class Meta:
        abstract = False

    def __unicode__(self):
        return "EggEvaluationDef (dummy={}, active={})".format(
            self.dummy,
            self.active,
        )


class icswEggConsumer(models.Model):
    """
    a consumers gets created by request from a steering XML control file
    it links a licensed service with an database element with a fixed or dynamic
    multiplier to calculate how many eggs are being consumd by a given funtion
    """
    # defines how eggs are consumed
    idx = models.AutoField(primary_key=True)
    # evaluation reference
    egg_evaluation_def = models.ForeignKey(icswEggEvaluationDef)
    # cradle
    egg_cradle = models.ForeignKey(icswEggCradle)
    # xml reference, points to an UUID
    xml_node_reference = models.TextField(default="")
    # content type
    content_type = models.ForeignKey(ContentType, null=True)
    # name for reference, used in icswServiceEnumBase
    action = models.CharField(max_length=63, default="")
    # total consumed by all fullfilled (valid=True) requests
    consumed = models.IntegerField(default=0)
    # config service enum
    config_service_enum = models.ForeignKey("backbone.ConfigServiceEnum")
    # multiplier
    multiplier = models.IntegerField(default=1)
    # dynamic multiplier ?
    dynamic_multiplier = models.BooleanField(default=False)
    # valid, parameters have not changed (after installing a new XML file)
    valid = models.BooleanField(default=False)
    # timeframe in seconds
    timeframe_secs = models.IntegerField(default=0)
    # creation date
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = False
        ordering = ("content_type__model", "config_service_enum__enum_name", "action")

    def get_all_consumed(self):
        _ws = self.icsweggrequest_set.filter(
            Q(is_lock=False) & (Q(valid=True))
        ).values_list("weight", flat=True)
        if _ws.count():
            _sum = sum(_ws)
            if _sum != self.consumed:
                self.consumed = _sum
                self.save(update_fields=["consumed"])
            return _sum
        else:
            return 0

    def get_num_consumers(self):
        return self.icsweggrequest_set.filter(
            Q(is_lock=False) & (Q(valid=True))
        ).count()

    def consume(self, request):
        if request.is_lock:
            # is a lock, we dont consume anything
            request.weight = 0
            request.valid = False
        else:
            # consum from egg_consumer
            # if request.valid is False, try to consume it
            # if request.valid is True, check the target weight
            _target_weight = self.multiplier
            if not request.valid:
                _to_consume = _target_weight
            else:
                _to_consume = _target_weight - request.weight
            if _to_consume:
                # something to consume, resolve egg_cradle
                _avail = self.egg_cradle.available
            else:
                _avail = 1
            if _avail > _to_consume:
                if _to_consume:
                    # nothing to consume (request was already fullfilled)
                    self.egg_cradle.available -= _to_consume
                    self.consumed += _to_consume
                    self.save(update_fields=["consumed"])
                    self.egg_cradle.save(update_fields=["available"])
                if self.timeframe_secs:
                    request.valid_until = cluster_timezone.localize(
                        datetime.datetime.now() + datetime.timedelta(seconds=self.timeframe_secs)
                    )
                else:
                    request.valid_until = None
                request.valid = True
            else:
                request.valid = False
            request.weight = _target_weight
        request.save(update_fields=["weight", "valid", "valid_until"])
        return request.valid

    def get_info_line(self):
        return [
            logging_tools.form_entry(self.action, header="action"),
            logging_tools.form_entry(unicode(self.config_service_enum), header="ConfigService"),
            logging_tools.form_entry_right(self.multiplier, header="Weight"),
            logging_tools.form_entry_center(unicode(self.content_type), header="ContentType"),
            logging_tools.form_entry_right(
                logging_tools.get_diff_time_str(self.timeframe_secs) if self.timeframe_secs else "---",
                header="timeframe",
            ),
            logging_tools.form_entry_right(self.get_num_consumers(), header="entries"),
            logging_tools.form_entry_right(self.get_all_consumed(), header="consumed"),
        ]

    def __unicode__(self):
        return u"EggConsumer {}@{} -> {} per {}".format(
            self.action,
            self.config_service_enum.name,
            logging_tools.get_plural("egg", self.multiplier),
            self.content_type.model,
        )


@receiver(signals.post_save, sender=icswEggConsumer)
def icsw_egg_consumer_post_save(sender, **kwargs):
    if "instance" in kwargs:
        _inst = kwargs["instance"]
        if not _inst.valid:
            pass
            # print(
            #    "Recalc {}, {}".format(
            #        unicode(_inst),
            #        logging_tools.get_plural("request", _inst.icsweggrequest_set.all().count()),
            #    )
            # )


class icswEggRequest(models.Model):
    """
    Egg request, are stored to be reevaluated at any time
    """
    idx = models.AutoField(primary_key=True)
    # egg consumer
    egg_consumer = models.ForeignKey(icswEggConsumer)
    # object id, may be None
    object_id = models.IntegerField(null=True)
    # effective number of eggs
    weight = models.IntegerField(default=0)
    # lock, is a lock (no eggs should be consumed, always returns false)
    is_lock = models.BooleanField(default=False)
    # valid, enough eggs present
    # generate an request even when not enough eggs are present, set valid=False
    valid = models.BooleanField(default=False)
    # valid until, used for locks with a limited validity
    valid_until = models.DateTimeField(default=None, null=True)
    # creation date
    date = models.DateTimeField(auto_now_add=True)

    def consume(self):
        return self.egg_consumer.consume(self)

    class Meta:
        abstract = False


@receiver(signals.pre_save, sender=icswEggCradle)
def icsw_egg_cradle_pre_save(sender, **kwargs):
    if "instance" in kwargs:
        _inst = kwargs["instance"]
        if _inst.system_cradle:
            _found = icswEggCradle.objects.filter(Q(system_cradle=True)).exclude(Q(pk=_inst.pk)).count()
            if _found:
                raise ValidationError("only one system cradle allowed")
