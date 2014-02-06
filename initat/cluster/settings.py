# Django settings for cluster project.

from django.core.exceptions import ImproperlyConfigured
import logging_tools
import os
import sys
try:
    from initat.cluster.license_tools import check_license, get_all_licenses, License
except ImportError:
    raise ImproperlyConfigured("cannot initialise license framework")
# set unified name
logging_tools.UNIFIED_NAME = "cluster.http"

ugettext = lambda s : s

# monkey-patch threading for python 2.7.x
if (sys.version_info.major, sys.version_info.minor) in [(2, 7)]:
    import threading
    threading._DummyThread._Thread__stop = lambda x: 42

DEBUG = "DEBUG_WEBFRONTEND" in os.environ
PIPELINE_ENABLED = True
TEMPLATE_DEBUG = DEBUG

ADMINS = (
    # ("Andreas Lang-Nevyjel", "cluster@init.at"),
    ("Andreas Lang-Nevyjel", "lang-nevyjel@init.at"),
)

# determine product name
if os.path.isfile("/etc/sysconfig/cluster/.is_corvus"):
    INIT_PRODUCT_NAME = "Corvus"
    INIT_PRODUCT_FAMILY = "Corvus albicollis" # Geierrabe
else:
    INIT_PRODUCT_NAME = "Noctua"
    INIT_PRODUCT_FAMILY = "Strigidae bubo bubo" # Uhu

ALLOWED_HOSTS = ["*"]

INTERNAL_IPS = ("127.0.0.1", "192.168.1.173",)

MANAGERS = ADMINS

MAIL_SERVER = "localhost"

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

DATABASE_ROUTERS = ["initat.cluster.backbone.routers.db_router"]

NEW_CONF_FILE = "/etc/sysconfig/cluster/db.cf"
OLD_CONF_FILE = "/etc/sysconfig/cluster/mysql.cf"

if os.path.isfile(NEW_CONF_FILE):
    try:
        conf_content = file(NEW_CONF_FILE, "r").read()
    except IOError:
        raise ImproperlyConfigured("cannot read '%s', wrong permissions ?" % (NEW_CONF_FILE))
else:
    if not os.path.isfile(OLD_CONF_FILE):
        raise ImproperlyConfigured("config '%s' and %s' not found" % (NEW_CONF_FILE, OLD_CONF_FILE))
    else:
        try:
            conf_content = file(OLD_CONF_FILE, "r").read()
        except IOError:
            raise ImproperlyConfigured("cannot read '%s', wrong permissions ?" % (OLD_CONF_FILE))

sql_dict = dict([(key.split("_")[1], value) for key, value in [
    line.strip().split("=", 1) for line in conf_content.split("\n") if line.count("=") and line.count("_") and not line.count("NAGIOS")]])

mon_dict = dict([(key.split("_")[1], value) for key, value in [
    line.strip().split("=", 1) for line in conf_content.split("\n") if line.count("=") and line.count("_") and line.count("NAGIOS_")]])

for src_key, dst_key in [
    ("DATABASE", "NAME"),
    ("USER"    , "USER"),
    ("PASSWD"  , "PASSWORD"),
    ("HOST"    , "HOST"),
    ("ENGINE"  , "ENGINE")]:
    if src_key in sql_dict:
        DATABASES["default"][dst_key] = sql_dict[src_key]

if mon_dict:
    DATABASES["monitor"] = dict([(key, value) for key, value in DATABASES["default"].iteritems()])
    for src_key , dst_key in [
        ("DATABASE", "NAME"),
        ("USER"    , "USER"),
        ("PASSWD"  , "PASSWORD"),
        ("HOST"    , "HOST"),
        ("ENGINE"  , "ENGINE")]:
        if src_key in mon_dict:
            DATABASES["monitor"][dst_key] = mon_dict[src_key]

FILE_ROOT = os.path.normpath(os.path.dirname(__file__))

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

# URL that handles the media served from MEDIA_ROOT. Make sure to use a
# trailing slash.
# Examples: "http://media.lawrence.com/media/", "http://example.com/media/"
MEDIA_ROOT = os.path.join(FILE_ROOT, "frontend", "media")

MEDIA_URL = "%s/media/" % (SITE_ROOT)

# Absolute path to the directory static files should be collected to.
# Don't put anything in this directory yourself; store your static files
# in apps' "static/" subdirectories and in STATICFILES_DIRS.
# Example: "/home/media/media.lawrence.com/static/"

# where to store static files
STATIC_ROOT_DEBUG = "/tmp/.icsw/static/"
if DEBUG:
    STATIC_ROOT = STATIC_ROOT_DEBUG
else:
    STATIC_ROOT = "/srv/www/htdocs/icsw/static"
# STATIC_ROOT = "/opt/python-init/lib/python2.7/site-packages/initat/cluster/"

# URL prefix for static files.
# Example: "http://media.lawrence.com/static/"
STATIC_URL = "%s/static/" % (SITE_ROOT)

# Session settings
SESSION_ENGINE = "django.contrib.sessions.backends.cache"
SESSION_COOKIE_HTTPONLY = True

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
    "initat.cluster.backbone.context_processors.add_csw_permissions",
)

TEMPLATE_LOADERS = (
    "django.template.loaders.filesystem.Loader",
    "django.template.loaders.app_directories.Loader",
#     'django.template.loaders.eggs.Loader',
)

MIDDLEWARE_CLASSES = (
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",

    "django.middleware.csrf.CsrfViewMiddleware",

    # "django.middleware.transaction.TransactionMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",

    # Uncomment the next line for simple clickjacking protection:
    # 'django.middleware.clickjacking.XFrameOptionsMiddleware',

    "backbone.middleware.database_debug",
    # "django.middleware.gzip.GZipMiddleware",
    "pipeline.middleware.MinifyHTMLMiddleware",
)

ROOT_URLCONF = "initat.cluster.urls"

# Python dotted path to the WSGI application used by Django's runserver.
WSGI_APPLICATION = "initat.cluster.wsgi.application"

TEMPLATE_DIRS = (
    # Put strings here, like "/home/html/django_templates" or "C:/www/django/templates".
    # Always use forward slashes, even on Windows.
    # Don't forget to use absolute paths, not relative paths.
    os.path.join(MEDIA_ROOT, "angular"),
)
if "INITIAL_MIGRATION_RUN" in os.environ:
    INSTALLED_APPS = (
        # "django.contrib.auth",
        "django.contrib.contenttypes",
        "django.contrib.sessions",
        "django.contrib.sites",
        "django.contrib.messages",
        "django.contrib.staticfiles",
        # Uncomment the next line to enable the admin:
        # "django.contrib.admin",
        # Uncomment the next line to enable admin documentation:
        # "django.contrib.admindocs",
        "django_extensions",
        # "reversion",
        "south",
        # "pipeline",
        # "static_precompiler",
        # "crispy_forms",
        # cluster
        # "initat.core",
    )
else:
    INSTALLED_APPS = (
        "django.contrib.auth",
        "django.contrib.contenttypes",
        "django.contrib.sessions",
        "django.contrib.sites",
        "django.contrib.messages",
        "django.contrib.staticfiles",
        # Uncomment the next line to enable the admin:
        "django.contrib.admin",
        # Uncomment the next line to enable admin documentation:
        # "django.contrib.admindocs",
        "django_extensions",
        "reversion",
        "south",
        "pipeline",
        "static_precompiler",
        "crispy_forms",
        # cluster
        "initat.core",
    )

# needed by some modules
ZMQ_LOGGING = True

# crispy settings, bootstrap3 is angularized via a patch
CRISPY_ALLOWED_TEMPLATE_PACKS = ('bootstrap3')
CRISPY_TEMPLATE_PACK = "bootstrap3"
CRISPY_FAIL_SILENTLY = not DEBUG

# coffee settings
COFFEESCRIPT_EXECUTABLE = "/opt/cluster/bin/coffee"
STATIC_PRECOMPILER_CACHE = not DEBUG

try:
    import crispy_forms
except ImportError:
    pass
else:
    _required = "1.4.0"
    if crispy_forms.__version__ != _required:
        raise ImproperlyConfigured("Crispy forms has version '%s' (required: '%s')" % (
            crispy_forms.__version__,
            _required,
        ))

# pipeline settings
PIPELINE_YUGLIFY_BINARY = "/opt/cluster/bin/yuglify"
if not os.path.exists(PIPELINE_YUGLIFY_BINARY):
    raise ImproperlyConfigured("no %s found" % (PIPELINE_YUGLIFY_BINARY))
PIPELINE_YUGLIFY_CSS_ARGUMENTS = "--terminal"
PIPELINE_YUGLIFY_JS_ARGUMENTS = "--terminal"
STATICFILES_STORAGE = "pipeline.storage.PipelineCachedStorage"

# List of finder classes that know how to find static files in
# various locations.
STATICFILES_FINDERS = (
    "django.contrib.staticfiles.finders.FileSystemFinder",
    "django.contrib.staticfiles.finders.AppDirectoriesFinder",
    "static_precompiler.finders.StaticPrecompilerFinder",
)

if DEBUG:
    STATICFILES_FINDERS = tuple(list(STATICFILES_FINDERS) + ["pipeline.finders.PipelineFinder"])

STATICFILES_DIRS = (
    ("icinga", "/opt/icinga/share/images/logos"),
    ("admin", "/opt/python-init/lib/python/site-packages/django/contrib/admin/static/admin"),
    # ("frontend", os.path.join(FILE_ROOT, "frontend", "media")),
)

PIPELINE_CSS = {
    "part1" : {
        "source_filenames" : {
            "css/smoothness/jquery-ui-1.10.2.custom.min.css",
            "css/main.css",
            "js/libs/dynatree/skin/ui.dynatree.css",
            "js/libs/chosen/chosen.min.css",
            "js/libs/angular-chosen-1.0.3/chosen-spinner.css",
            "css/jquery.dataTables.css",
            "css/msdropdown/dd.css",
            "css/jqModal.css",
            "css/codemirror.css",
            "css/bootstrap.css",
            "css/jquery.Jcrop.min.css",
            "css/angular-datetimepicker.css",
            "js/libs/select2/select2.css",
            "js/libs/select2/select2-bootstrap.css",
        },
        "output_filename" : "pipeline/css/part1.css"
    }
}

PIPELINE_JS = {
    "js_jquery_new" : {
        "source_filenames" : {
            "js/libs/modernizr-2.6.2.min.js",
            "js/plugins.js",
            "js/libs/jquery-2.1.0.min.js",
        },
        "output_filename" : "pipeline/js/jquery_new.js"
    },
    "js_jquery_new_old" : {
        "source_filenames" : {
            "js/libs/modernizr-2.6.2.min.js",
            "js/plugins.js",
            "js/libs/jquery-1.11.0.min.js",
        },
        "output_filename" : "pipeline/js/jquery.js"
    },
    "js_base" : {
        "source_filenames" : {
            "js/libs/jquery-ui-1.10.2.custom.js",
            "js/libs/jquery-migrate-1.2.1.min.js",
            "js/libs/jquery.layout-latest.min.js",
            "js/libs/select2/select2.min.js",
            "js/jquery.dataTables.min.js",
            "js/jquery.sprintf.js_8.txt",
            "js/jquery.timers-1.2.js",
            "js/jquery.noty.packaged.js",
            "js/libs/lodash.min.js",
            "js/jquery.dd.min.js",
            "js/jquery.simplemodal.js",
            "js/codemirror/codemirror.js",
            "js/bootstrap.js",
            "js/libs/jquery.color.js",
            "js/libs/chosen/chosen.jquery.min.js",
            "js/libs/jquery.blockUI.js",
            "js/libs/angular.min.js",
            "js/libs/moment-with-langs.min.js",
            "js/libs/jquery.Jcrop.min.js",
        },
        "output_filename" : "pipeline/js/base.js"
    },
    "js_extra1" : {
        "source_filenames" : {
            "js/jquery.dataTables.rowGrouping.js",
            "js/codemirror/addon/selection/active-line.js",
            "js/libs/select2/ui-select2.js",
            "js/codemirror/python.js",
            "js/codemirror/xml.js",
            "js/codemirror/shell.js",
            "js/libs/jquery-ui-timepicker-addon.js",
            "js/libs/angular-route.min.js",
            "js/libs/angular-resource.min.js",
            "js/libs/angular-cookies.min.js",
            "js/libs/angular-sanitize.min.js",
            "js/libs/angular-chosen-1.0.3/chosen.js",
            "js/libs/restangular.min.js",
            "js/libs/ui-bootstrap.min.js",
            "js/libs/ui-bootstrap-tpls.min.js",
            "js/libs/ui-codemirror.min.js",
            "js/libs/angular-datetimepicker.js",
            # "js/libs/angular-strap.min.js",
            # "js/libs/angular-strap.tpl.min.js",
        },
        "output_filename" : "pipeline/js/extra2.js"
    }
}

# add all applications, including backbone

AUTOCOMMIT = True

INSTALLED_APPS = list(INSTALLED_APPS)
ADDITIONAL_MENU_FILES = []

AUTHENTICATION_BACKENDS = (
    "initat.cluster.backbone.cluster_auth.db_backend",
)
AUTH_USER_MODEL = "backbone.user"

if not "NO_AUTO_ADD_APPLICATIONS" in os.environ:
    # my authentication backend

    # add everything below cluster
    dir_name = os.path.dirname(__file__)
    for sub_dir in os.listdir(dir_name):
        full_path = os.path.join(dir_name, sub_dir)
        if os.path.isdir(full_path):
            if any([entry.endswith("views.py") for entry in os.listdir(full_path)]):
                add_app = "initat.cluster.%s" % (sub_dir)
                if add_app not in INSTALLED_APPS:
                    # search for menu file
                    templ_dir = os.path.join(full_path, "templates")
                    if os.path.isdir(templ_dir):
                        for templ_name in os.listdir(templ_dir):
                            if templ_name.endswith("_menu.html"):
                                ADDITIONAL_MENU_FILES.append(templ_name)
                    INSTALLED_APPS.append(add_app)
    for add_app_key in [key for key in os.environ.keys() if key.startswith("INIT_APP_NAME")]:
        add_app = os.environ[add_app_key]
        if add_app not in INSTALLED_APPS:
            INSTALLED_APPS.append(add_app)
    # INSTALLED_APPS.append("initat.core")

INSTALLED_APPS = tuple(INSTALLED_APPS)

AUTO_CREATE_NEW_DOMAINS = True

LOCAL_CONFIG = "/etc/sysconfig/cluster/local_settings.py"

PASSWORD_HASH_FUNCTION = "SHA1"

if os.path.isfile(LOCAL_CONFIG):
    local_dir = os.path.dirname(LOCAL_CONFIG)
    sys.path.append(local_dir)
    from local_settings import *
    sys.path.remove(local_dir)

# validate settings
if PASSWORD_HASH_FUNCTION not in ["SHA1", "CRYPT"]:
    raise ImproperlyConfigured("password hash function '%s' not known" % (PASSWORD_HASH_FUNCTION))

c_license = License()
# check licenses
all_lics = get_all_licenses()
CLUSTER_LICENSE = {}
for cur_lic in all_lics:
    CLUSTER_LICENSE[cur_lic] = check_license(cur_lic)
CLUSTER_LICENSE["device_count"] = c_license.get_device_count()
del c_license

INSTALLED_APPS = tuple(list(INSTALLED_APPS) + ["rest_framework"])

rest_renderers = (["rest_framework.renderers.BrowsableAPIRenderer"] if DEBUG else []) + [
    "rest_framework.renderers.JSONRenderer",
    # "rest_framework_csv.renderers.CSVRenderer",
    "rest_framework.renderers.XMLRenderer",
]

REST_FRAMEWORK = {
    'DEFAULT_RENDERER_CLASSES' : tuple(rest_renderers),
    "DEFAULT_PARSER_CLASSES"   : (
        "rest_framework.parsers.XMLParser",
        "rest_framework.parsers.JSONParser",
    ),
    "DEFAULT_AUTHENTICATION_CLASSES" : (
        "rest_framework.authentication.BasicAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ),
    "EXCEPTION_HANDLER" : "initat.cluster.frontend.rest_views.csw_exception_handler",
    "ID_FIELD_NAME" : "idx",
}

# SOUTH config
SOUTH_LOGGING_ON = True
SOUTH_LOGGING_FILE = "/var/log/cluster/south.log"

LOGGING = {
    'version' : 1,
    'disable_existing_loggers' : True,
    'formatters' : {
        "initat" : {
            "()" : "logging_tools.initat_formatter",
        },
        'verbose' : {
            'format' : '%(levelname)s %(asctime)s %(module)s %(process)d %(message)s %(thread)d %(message)s'
        },
        'simple' : {
            'format' : '%(levelname)s %(message)s'
        },
    },
    'handlers' : {
        "init_unified" : {
            "level"     : "INFO" if DEBUG else "WARN",
            "class"     : "logging_tools.init_handler_unified",
            "formatter" : "initat",
        },
        "init" : {
            "level"     : 'INFO' if DEBUG else "WARN",
            "class"     : "logging_tools.init_handler",
            "formatter" : "initat",
        },
        "init_mail" : {
            "level"     : "ERROR",
            "class"     : "logging_tools.init_email_handler",
            "formatter" : "initat",
        },
    },
    'loggers' : {
        'django' : {
            'handlers'  : ['init_unified', "init_mail"],
            'propagate' : True,
            'level'     : 'WARN',
        },
        'initat' : {
            'handlers'  : ['init_unified', "init_mail"],
            'propagate' : True,
            'level'     : 'WARN',
        },
        'cluster' : {
            'handlers'  : ['init', "init_mail"],
            'propagate' : True,
            'level'     : 'INFO' if DEBUG else "WARN",
        },
    }
}
