# -*- coding: utf-8 -*-

"""
initcore tags and filters for Django. Contains various
formatting helpers and the interface to get the menu.
"""

import datetime
import logging_tools
import codecs
from lxml.builder import E
from lxml import etree

import django.core.urlresolvers
import django.utils.http
import django.forms.forms
from django import template
from django.utils.safestring import mark_safe
from django.template.defaultfilters import stringfilter
from django.db.models import Q
from django.conf import settings
from django.utils.functional import memoize
from django.conf import settings

from initcore import menu_tools

register = template.Library()


@register.filter(name="nl_to_br")
@stringfilter
def nl_to_br(value):
    """ Convert a \n to <br> """
    return mark_safe(value.replace("\n", "<br>"))


@register.filter(name="to_nbsp")
@stringfilter
def to_nbsp(value):
    """ Convert a ' ' to &nbsp; """
    return mark_safe(value.replace(" ", "&nbsp;"))


@register.filter(name="relative_date")
def relative_date(value):
    if isinstance(value, datetime.datetime):
        value = logging_tools.get_relative_dt(value)
    return mark_safe(value)


@register.filter(name='class_name')
def class_name(ob):
    return ob.__class__.__name__


@register.tag("get_menu")
def get_menu(parser, token):
    return init_menu()


class init_menu(template.Node):
    def render(self, context):
        request = context["request"]
        is_mobile = request.session.get("is_mobile", False)
        return mark_safe(menu_tools.get_menu_html(request, is_mobile, False))


@register.filter(name="modulo")
def modulo(v, arg):
    return not bool(v % arg)


@register.filter(name="divide")
def divide(v, arg):
    return v / int(arg)
