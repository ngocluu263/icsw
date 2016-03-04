# Django settings for ICSW
#
# -*- coding: utf-8 -*-
#
# Copyright (C) 2010-2016 Andreas Lang-Nevyjel
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


import glob
import os
import sys

from django.core.exceptions import ImproperlyConfigured
from django.utils.crypto import get_random_string
from django.utils.translation import ugettext_lazy as _
from lxml import etree

from initat.constants import GEN_CS_NAME, DB_ACCESS_CS_NAME, VERSION_CS_NAME, CLUSTER_DIR, SITE_PACKAGES_BASE
from initat.icsw.service.instance import InstanceXML
from initat.tools import logging_tools, config_store

# set unified name
logging_tools.UNIFIED_NAME = "cluster.http"

ugettext = lambda s: s  # @IgnorePep8

# monkey-patch threading for python 2.7.x
if (sys.version_info.major, sys.version_info.minor) in [(2, 7)]:
    import threading
    threading._DummyThread._Thread__stop = lambda x: 42  # @IgnorePep8

DEBUG = "DEBUG_WEBFRONTEND" in os.environ
LOCAL_STATIC = "LOCAL_STATIC" in os.environ

ADMINS = (
    ("Andreas Lang-Nevyjel", "lang-nevyjel@init.at"),
)

ALLOWED_HOSTS = ["*"]

INTERNAL_IPS = (
    "127.0.0.1",
    "192.168.1.173",
)

MANAGERS = ADMINS

MAIL_SERVER = "localhost"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": "",
        "USER": "",
        "PASSWORD": "",
        "HOST": "",
        "PORT": "",
        # "CONN_MAX_AGE" : 30,
    }
}

DATABASE_ROUTERS = ["initat.cluster.backbone.routers.db_router"]

# config stores
# database config
_cs = config_store.ConfigStore(GEN_CS_NAME, quiet=True)
if config_store.ConfigStore.exists(DB_ACCESS_CS_NAME):
    _ps = config_store.ConfigStore(DB_ACCESS_CS_NAME, quiet=True)
else:
    raise ImproperlyConfigured("DB-Access not configured (store not found)")

# version config
# TODO: check for local config when running in debug (development) mode
_vers = config_store.ConfigStore(VERSION_CS_NAME, quiet=True)
_DEF_NAMES = ["database", "software", "models"]
ICSW_VERSION_DICT = {
    _name: _vers[_name] for _name in _DEF_NAMES
}
ICSW_DATABASE_VERSION = _vers["database"]
ICSW_SOFTWARE_VERSION = _vers["software"]
ICSW_MODELS_VERSION = _vers["models"]

# validate settings
if _cs["password.hash.function"] not in ["SHA1", "CRYPT"]:
    raise ImproperlyConfigured("password hash function '{}' not known".format(_cs["password.hash.function"]))

SECRET_KEY = _cs["django.secret.key"]

for src_key, dst_key in [
    ("db.database", "NAME"),
    ("db.user", "USER"),
    ("db.passwd", "PASSWORD"),
    ("db.host", "HOST"),
    ("db.engine", "ENGINE")
]:
    if src_key in _ps:
        DATABASES["default"][dst_key] = _ps[src_key]

FILE_ROOT = os.path.normpath(os.path.dirname(__file__))

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.memcached.MemcachedCache",
        "LOCATION": "127.0.0.1:{:d}".format(InstanceXML(quiet=True).get_port_dict("memcached", command=True)),
    }
}

TIME_ZONE = "Europe/Vienna"

# Language code for this installation. All choices can be found here:
# http://www.i18nguy.com/unicode/language-identifiers.html
LANGUAGE_CODE = "en-us"

LANGUAGES = (
    ("en", _("English")),
)

ANONYMOUS_USER_ID = -1

SITE_ID = 1

REL_SITE_ROOT = "icsw/api/v2"
SITE_ROOT = "/{}".format(REL_SITE_ROOT)
LOGIN_URL = "{}/session/login/".format(SITE_ROOT)

USE_I18N = True

USE_L10N = True

USE_TZ = True

# URL that handles the media served from MEDIA_ROOT. Make sure to use a
# trailing slash.
# Examples: "http://media.lawrence.com/media/", "http://example.com/media/"
MEDIA_ROOT = os.path.join(FILE_ROOT, "frontend", "media")

MEDIA_URL = "{}/media/".format(SITE_ROOT)

# where to store static files
STATIC_ROOT_DEBUG = "/tmp/.icsw/static/"
if DEBUG:
    STATIC_ROOT = STATIC_ROOT_DEBUG
else:
    if LOCAL_STATIC:
        STATIC_ROOT = STATIC_ROOT_DEBUG
    else:
        STATIC_ROOT = "/srv/www/htdocs/icsw/static"

if not os.path.isdir(STATIC_ROOT_DEBUG):
    try:
        os.makedirs(STATIC_ROOT_DEBUG)
    except IOError:
        pass

# use X-Forwarded-Host header
USE_X_FORWARDED_HOST = True

# URL prefix for static files.
# Example: "http://media.lawrence.com/static/"
STATIC_URL = "{}/static/".format(SITE_ROOT)

# Session settings
SESSION_ENGINE = "django.contrib.sessions.backends.cache"
SESSION_COOKIE_HTTPONLY = True

# Make this unique, and don't share it with anybody.
# SECRET_KEY = "av^t8g^st(phckz=9u#68k6p&amp;%3@h*z!mt=mo@3t!!ls^+4%ic"

MIDDLEWARE_CLASSES = (
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",

    "django.middleware.csrf.CsrfViewMiddleware",

    # "django.middleware.transaction.TransactionMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",

    "initat.cluster.backbone.middleware.thread_local_middleware",
    # Uncomment the next line for simple clickjacking protection:
    # 'django.middleware.clickjacking.XFrameOptionsMiddleware',

    "backbone.middleware.database_debug",
    # "django.middleware.gzip.GZipMiddleware",

    "reversion.middleware.RevisionMiddleware",
)

if not DEBUG:
    MIDDLEWARE_CLASSES = tuple(
        ["django.middleware.gzip.GZipMiddleware"] +
        list(
            MIDDLEWARE_CLASSES
        )
    )
ROOT_URLCONF = "initat.cluster.urls"

# Python dotted path to the WSGI application used by Django's runserver.
WSGI_APPLICATION = "initat.cluster.wsgi.application"


INSTALLED_APPS = (
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.sites",
    "django.contrib.staticfiles",
    # Uncomment the next line to enable the admin:
    "django.contrib.admin",
    # Uncomment the next line to enable admin documentation:
    # "django.contrib.admindocs",
    "django_extensions",
    "reversion",
)

ICSW_WEBCACHE = os.path.join(CLUSTER_DIR, "share", "webcache")

# List of finder classes that know how to find static files in
# various locations.
STATICFILES_FINDERS = (
    "django.contrib.staticfiles.finders.FileSystemFinder",
    "django.contrib.staticfiles.finders.AppDirectoriesFinder",
)

# print STATICFILES_FINDERS, STATICFILES_STORAGE

STATICFILES_DIRS = []
if os.path.isdir("/opt/icinga/share/images/logos"):
    STATICFILES_DIRS.append(
        ("icinga", "/opt/icinga/share/images/logos")
    )

STATICFILES_DIRS.append(
    ("admin", os.path.join(SITE_PACKAGES_BASE, "django", "contrib", "admin", "static", "admin")),
)

STATICFILES_DIRS = list(STATICFILES_DIRS)

# print STATICFILES_DIRS

# add all applications, including backbone

AUTOCOMMIT = True

INSTALLED_APPS = list(INSTALLED_APPS)
ADDITIONAL_ANGULAR_APPS = []
# ADDITIONAL_URLS = []
ICSW_ADDITIONAL_JS = []
ICSW_ADDITIONAL_HTML = []

# my authentication backend
AUTHENTICATION_BACKENDS = (
    "initat.cluster.backbone.cluster_auth.db_backend",
)

ICSW_ADDON_APPS = []
# add everything below cluster
dir_name = os.path.dirname(__file__)
for sub_dir in os.listdir(dir_name):
    full_path = os.path.join(dir_name, sub_dir)
    if os.path.isdir(full_path):
        if any([entry.endswith("views.py") for entry in os.listdir(full_path)]):
            add_app = "initat.cluster.{}".format(sub_dir)
            if add_app not in INSTALLED_APPS:
                # search for icsw meta
                icsw_meta = os.path.join(full_path, "ICSW.meta.xml")
                if os.path.exists(icsw_meta):
                    try:
                        _tree = etree.fromstring(file(icsw_meta, "r").read())
                    except:
                        pass
                    else:
                        ICSW_ADDON_APPS.append(sub_dir)
                        ADDITIONAL_ANGULAR_APPS.extend(
                            [_el.attrib["name"] for _el in _tree.findall(".//app")]
                        )
                        js_full_paths = glob.glob(os.path.join(dir_name, "addons", sub_dir, "initat", "cluster", "work", "icsw", "*.js"))
                        ICSW_ADDITIONAL_JS.extend(
                            [
                                js_file for js_file in js_full_paths
                            ]
                        )
                        html_full_paths = glob.glob(os.path.join(dir_name, "addons", sub_dir, "initat", "cluster", "work", "icsw", "*.html"))
                        ICSW_ADDITIONAL_HTML.extend(
                            [
                                html_file for html_file in html_full_paths
                            ]
                        )
                INSTALLED_APPS.append(add_app)

_show_apps = False
for rem_app_key in [key for key in os.environ.keys() if key.startswith("INIT_REMOVE_APP_NAME")]:
    rem_app = os.environ[rem_app_key]
    _show_apps = True
    if rem_app.endswith("."):
        INSTALLED_APPS = [_entry for _entry in INSTALLED_APPS if not _entry.startswith(rem_app)]
    else:
        if rem_app in INSTALLED_APPS:
            INSTALLED_APPS.remove(rem_app)

if any([_app.startswith("initat.cluster.") for _app in INSTALLED_APPS]):
    ICSW_INCLUDE_URLS = True
    AUTH_USER_MODEL = "backbone.user"
else:
    ICSW_INCLUDE_URLS = False

INSTALLED_APPS = tuple(INSTALLED_APPS)

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [
            os.path.join(MEDIA_ROOT, "angular"),
            os.path.join(CLUSTER_DIR, "share", "doc", "handbook", "chunks"),
        ],
        "OPTIONS": {
            "context_processors": [
                "django.contrib.auth.context_processors.auth",
                "django.template.context_processors.i18n",
                "django.template.context_processors.request",
                "django.template.context_processors.media",
                "django.template.context_processors.debug",
            ],
            "debug": DEBUG,
            "loaders": [
                "django.template.loaders.filesystem.Loader",
                "django.template.loaders.app_directories.Loader",
            ],
        },

    }
]

INSTALLED_APPS = tuple(list(INSTALLED_APPS) + ["rest_framework"])

if _show_apps:
    print(
        "{:d} INSTALLED_APPS: {}".format(
            len(INSTALLED_APPS),
            " ".join(INSTALLED_APPS),
        )
    )

TEST_RUNNER = "django.test.runner.DiscoverRunner"

rest_renderers = (
    [
        "rest_framework.renderers.BrowsableAPIRenderer"
    ] if DEBUG else []
) + [
    "rest_framework.renderers.JSONRenderer",
    # "rest_framework_csv.renderers.CSVRenderer",
    "rest_framework_xml.renderers.XMLRenderer",
]

REST_FRAMEWORK = {
    'DEFAULT_RENDERER_CLASSES': tuple(rest_renderers),
    "DEFAULT_PARSER_CLASSES": (
        "rest_framework_xml.parsers.XMLParser",
        "rest_framework.parsers.JSONParser",
    ),
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework.authentication.BasicAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ),
    "EXCEPTION_HANDLER": "initat.cluster.frontend.rest_views.csw_exception_handler",
    "ID_FIELD_NAME": "idx",
}

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        "initat": {
            "()": "initat.tools.logging_net.initat_formatter",
        },
        'verbose': {
            'format': '%(levelname)s %(asctime)s %(module)s %(process)d %(message)s %(thread)d %(message)s'
        },
        'simple': {
            'format': '%(levelname)s %(message)s'
        },
    },
    'handlers': {
        "init_unified": {
            "level": "INFO" if DEBUG else "WARN",
            "class": "initat.tools.logging_net.init_handler_unified",
            "formatter": "initat",
        },
        "init": {
            "level": 'INFO' if DEBUG else "WARN",
            "class": "initat.tools.logging_net.init_handler",
            "formatter": "initat",
        },
        "init_mail": {
            "level": "ERROR",
            "class": "initat.tools.logging_net.init_email_handler",
            "formatter": "initat",
        },
    },
    'loggers': {
        'django': {
            'handlers': ['init_unified', "init_mail"],
            'propagate': True,
            'level': 'WARN',
        },
        'initat': {
            'handlers': ['init_unified', "init_mail"],
            'propagate': True,
            'level': 'WARN',
        },
        'cluster': {
            'handlers': ["init_unified", "init", "init_mail"],
            'propagate': True,
            'level': 'INFO' if DEBUG else "WARN",
        },
    }
}
