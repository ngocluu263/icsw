# Django settings for cluster project.

import os
import sys
import pprint
from initat.cluster.license_tools import check_license, get_all_licenses

ugettext = lambda s : s

from django.core.exceptions import ImproperlyConfigured

if "START_VIA_RC" in os.environ:
    DEBUG = False
else:
    DEBUG = os.uname()[1] in ["slayer", "eddie"]
TEMPLATE_DEBUG = DEBUG

ADMINS = (
    #("Andreas Lang-Nevyjel", "cluster@init.at"),
    ("Andreas Lang-Nevyjel", "lang-nevyjel@init.at"),
)

MANAGERS = ADMINS

DATABASES = {
    "default": {
        "ENGINE"   : "django.db.backends.mysql", 
        "NAME"     : "",
        "USER"     : "",
        "PASSWORD" : "",
        "HOST"     : "",
        "PORT"     : ""
    }
}

OLD_CONF_FILE = "/etc/sysconfig/cluster/mysql.cf"

if not os.path.isfile(OLD_CONF_FILE):
    raise ImproperlyConfigured("config '%s' not found" % (OLD_CONF_FILE))
else:
    try:
        file(OLD_CONF_FILE, "r").read()
    except IOError:
        raise ImproperlyConfigured("cannot read '%s', wrong permissions ?" % (OLD_CONF_FILE))
    
sql_dict = dict([(key[6:], value) for key, value in [
    line.strip().split("=", 1) for line in file("/etc/sysconfig/cluster/mysql.cf", "r").read().split("\n") if line.count("=") and line.startswith("MYSQL_")]])

mon_dict = dict([(key[7:], value) for key, value in [
    line.strip().split("=", 1) for line in file("/etc/sysconfig/cluster/mysql.cf", "r").read().split("\n") if line.count("=") and line.startswith("NAGIOS_")]])

for src_key ,dst_key in [
    ("DATABASE", "NAME"),
    ("USER"    , "USER"),
    ("PASSWD"  , "PASSWORD"),
    ("HOST"    , "HOST"),
    ("ENGINE"  , "ENGINE")]:
    if src_key in sql_dict:
        DATABASES["default"][dst_key] = sql_dict[src_key]

if mon_dict:
    DATABASES["monitor"] = dict([(key, value) for key, value in DATABASES["default"].iteritems()])
    for src_key ,dst_key in [
        ("DATABASE", "NAME"),
        ("USER"    , "USER"),
        ("PASSWD"  , "PASSWORD"),
        ("HOST"    , "HOST"),
        ("ENGINE"  , "ENGINE")]:
        if src_key in mon_dict:
            DATABASES["monitor"][dst_key] = mon_dict[src_key]

FILE_ROOT = os.path.normpath(os.path.dirname(__file__))

# compress settings
COMPRESS = False#not DEBUG
COMPRESS_ENABLED = COMPRESS
COMPRESS_OFFLINE = COMPRESS
# rebuild once a day
COMPRESS_REBUILD_TIMEOUT = 60 * 60 * 24
STATIC_ROOT = "/opt/python-init/lib/python2.7/site-packages/initat/cluster/"

CACHES = {
    "default" : {
        "BACKEND"  : "django.core.cache.backends.memcached.MemcachedCache",
        "LOCATION" : "127.0.0.1:11211",
    }
}

# Local time zone for this installation. Choices can be found here:
# http://en.wikipedia.org/wiki/List_of_tz_zones_by_name
# although not all choices may be available on all operating systems.
# On Unix systems, a value of None will cause Django to use the same
# timezone as the operating system.
# If running in a Windows environment this must be set to the same as your
# system time zone.
TIME_ZONE = "Europe/Vienna"

# Language code for this installation. All choices can be found here:
# http://www.i18nguy.com/unicode/language-identifiers.html
LANGUAGE_CODE = "en-us"

SITE_ID = 1

REL_SITE_ROOT = "cluster"
SITE_ROOT = "/%s" % (REL_SITE_ROOT)
LOGIN_URL = "%s/session/login/" % (SITE_ROOT)
                                   
# If you set this to False, Django will make some optimizations so as not
# to load the internationalization machinery.
USE_I18N = True

# If you set this to False, Django will not format dates, numbers and
# calendars according to the current locale.
USE_L10N = True

# If you set this to False, Django will not use timezone-aware datetimes.
USE_TZ = True

# Absolute filesystem path to the directory that will hold user-uploaded files.
# Example: "/home/media/media.lawrence.com/media/"
#MEDIA_ROOT = "/usr/local/share/home/local/development/clustersoftware/build-extern/webfrontend/htdocs/static/"

# URL that handles the media served from MEDIA_ROOT. Make sure to use a
# trailing slash.
# Examples: "http://media.lawrence.com/media/", "http://example.com/media/"
MEDIA_ROOT = os.path.join(FILE_ROOT, "media")

MEDIA_URL = "%s/media/" % (SITE_ROOT)

#COMPRESS_URL = "%s/frontend/media/" % (SITE_ROOT)

COMPRESS_OFFLINE_CONTEXT = {
    "MEDIA_URL" : MEDIA_URL,
}

# Absolute path to the directory static files should be collected to.
# Don't put anything in this directory yourself; store your static files
# in apps' "static/" subdirectories and in STATICFILES_DIRS.
# Example: "/home/media/media.lawrence.com/static/"

# URL prefix for static files.
# Example: "http://media.lawrence.com/static/"
STATIC_URL = "%s/static/" % (SITE_ROOT)

# Session settings
SESSION_ENGINE = "django.contrib.sessions.backends.cache"
SESSION_COOKIE_HTTPONLY = True

# Additional locations of static files
##STATICFILES_DIRS = (
##    # Put strings here, like "/home/html/static" or "C:/www/django/static".
##    # Always use forward slashes, even on Windows.
##    # Don't forget to use absolute paths, not relative paths.
##)

# List of finder classes that know how to find static files in
# various locations.
##STATICFILES_FINDERS = (
##    'django.contrib.staticfiles.finders.FileSystemFinder',
##    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
##    "compressor.finders.CompressorFinder",
##)

# Make this unique, and don't share it with anybody.
SECRET_KEY = "av^t8g^st(phckz=9u#68k6p&amp;%3@h*z!mt=mo@3t!!ls^+4%ic"

# List of callables that know how to import templates from various sources.
TEMPLATE_CONTEXT_PROCESSORS = (
    "django.contrib.messages.context_processors.messages",
    "django.contrib.auth.context_processors.auth",
    "django.core.context_processors.i18n",
    "django.core.context_processors.request",
    "django.core.context_processors.media",
    "django.core.context_processors.debug",
    "initat.core.context_processors.add_session",
    "initat.core.context_processors.add_settings",
)

TEMPLATE_LOADERS = (
    "django.template.loaders.filesystem.Loader",
    "django.template.loaders.app_directories.Loader",
#     'django.template.loaders.eggs.Loader',
)

MIDDLEWARE_CLASSES = (
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    #'django.middleware.csrf.CsrfViewMiddleware',
    "django.middleware.transaction.TransactionMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    # Uncomment the next line for simple clickjacking protection:
    # 'django.middleware.clickjacking.XFrameOptionsMiddleware',
    "backbone.middleware.database_debug",
)

ROOT_URLCONF = "initat.cluster.urls"

# Python dotted path to the WSGI application used by Django's runserver.
WSGI_APPLICATION = "initat.cluster.wsgi.application"

TEMPLATE_DIRS = (
    # Put strings here, like "/home/html/django_templates" or "C:/www/django/templates".
    # Always use forward slashes, even on Windows.
    # Don't forget to use absolute paths, not relative paths.
)

INSTALLED_APPS = (
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.sites",
    "django.contrib.messages",
    #"django.contrib.staticfiles",
    # Uncomment the next line to enable the admin:
    "django.contrib.admin",
    # Uncomment the next line to enable admin documentation:
    "django.contrib.admindocs",
    "reversion",
    "south",
    "compressor",
    # REST
    "rest_framework",
    # cluster
)

# add all applications, including backbone

INSTALLED_APPS = list(INSTALLED_APPS)

if not "NO_AUTO_ADD_APPLICATIONS" in os.environ:
    # add everything below cluster
    dir_name = os.path.dirname(__file__)
    for sub_dir in os.listdir(dir_name):
        full_path = os.path.join(dir_name, sub_dir)
        if os.path.isdir(full_path):
            if any([entry.endswith("views.py") for entry in os.listdir(full_path)]):
                add_app = "initat.cluster.%s" % (sub_dir)
                if add_app not in INSTALLED_APPS:
                    INSTALLED_APPS.append(add_app)
    for add_app_key in [key for key in os.environ.keys() if key.startswith("INIT_APP_NAME")]:
        add_app = os.environ[add_app_key]
        if add_app not in INSTALLED_APPS:
            INSTALLED_APPS.append(add_app)
    INSTALLED_APPS.append("initat.core")

INSTALLED_APPS = tuple(INSTALLED_APPS)

LOCAL_CONFIG = "/etc/sysconfig/cluster/local_settings.py"

if os.path.isfile(LOCAL_CONFIG):
    local_dir = os.path.dirname(LOCAL_CONFIG)
    sys.path.append(local_dir)
    from local_settings import *
    sys.path.remove(local_dir)

# check licenses
all_lics = get_all_licenses()
CLUSTER_LICENSE = {}
for cur_lic in all_lics:
    CLUSTER_LICENSE[cur_lic] = check_license(cur_lic)

rest_renderers = [
    "rest_framework.renderers.XMLRenderer",
    "rest_framework.renderers.JSONRenderer"] + ["rest_framework.renderers.BrowsableAPIRenderer"] if DEBUG else []
    
REST_FRAMEWORK = {
    'DEFAULT_RENDERER_CLASSES' : tuple(rest_renderers),
    "DEFAULT_PARSER_CLASSES"   : (
        "rest_framework.parsers.XMLParser",
        "rest_framework.parsers.JSONParser",
    ),
    "DEFAULT_AUTHENTICATION_CLASSES" : (
        "rest_framework.authentication.BasicAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    )
}
