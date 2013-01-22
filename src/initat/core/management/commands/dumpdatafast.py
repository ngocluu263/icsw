# -*- coding: utf-8 -*-
"""
Dump data from Django models to PostgreSQL dump format.

Some measurements:
  Stupidly writing out the data:

    with codecs.open("/tmp/outfile", "w", "utf-8") as f:
        for obj in email_log.objects.select_related("certificate", "user", "email_to_user").iterator():
            f.write(smart_unicode(obj.__dict__) + "\n")

  takes ~20s on email_log.objects.count() == 152982.

  The same operation with dumpdatafast takes about ~30s, because of the rather expensive
  datetime operations and some conversion overhead.
"""

import cProfile
import pstats
import os
import sys
# For profiling
#os.environ["DJANGO_SETTINGS_MODULE"] = "settings"
#sys.path.append(".")
import subprocess
import datetime
import pytz
import codecs
import time
from logging_tools import LOG_LEVEL_OK, LOG_LEVEL_ERROR
from functools import partial

from django.core.exceptions import ImproperlyConfigured
from django.core.management.base import BaseCommand, CommandError
from django.db import DEFAULT_DB_ALIAS, connection
from django.utils.datastructures import SortedDict
from django.conf import settings
from django.utils import datetime_safe
from django.db.models import ForeignKey, OneToOneField, Model
from django.utils.encoding import smart_unicode

from optparse import make_option

from initat.core.utils import init_base_object, sql_iterator, MemoryProfile

BASE_OBJECT = init_base_object("dumpdatafast")
TIMEZONE = pytz.timezone(settings.TIME_ZONE)


def log(x):
    BASE_OBJECT.log(LOG_LEVEL_OK, x)


def error(x):
    sys.stderr.write(x + "\n")
    BASE_OBJECT.log(LOG_LEVEL_ERROR, x)


class Command(BaseCommand):
    option_list = BaseCommand.option_list + (
        make_option('--database', action='store', dest='database',
                    default=DEFAULT_DB_ALIAS, help='Nominates a specific database to dump '
                    'fixtures from. Defaults to the "default" database.'),
        make_option('-e', '--exclude', dest='exclude', action='append', default=[],
                    help='An appname or appname.ModelName to exclude (use multiple'
                    ' --exclude to exclude multiple apps/models).'),
        make_option('-d', '--directory', action='store', default='/tmp', help=''
                    'The output directory (default: %(directory)s'),
        make_option('-s', '--stats', action='store_true', help='Show stats for '
                    'each dumped model'),
        make_option('-i', '--iterator', action="store_true", help="Use custom "
                    "QuerySet iterator. (Saves RAM, takes more time and DB queries)"),
        make_option('-c', '--count', action="store", default=None, type=int, help="Maximum count"
                    "of objects to dump per model"),
        make_option('-b', "--bz2", action="store_true", help="bzip2 the resulting"
                    " postgres dumps"),
        make_option("-p", "--progress", action="store_true", help="Print progress"
                    " bar"),
    )
    help = "Output the contents of the database in PostgreSQL dump format. "
    args = '[appname appname.ModelName ...]'

    def handle(self, *app_labels, **options):
        try:
            return self._handle(*app_labels, **options)
        except Exception as e:
            BASE_OBJECT.get_logger().exception("Exception occured")
            raise e

    def _handle(self, *app_labels, **options):
        from django.db.models import get_app, get_apps, get_model, get_models

        using = options.get('database')
        excludes = options.get('exclude')
        iterator = options.get("iterator")

        # pylint: disable-msg=W0201
        self.directory = options.get('directory')
        self.stats = options.get('stats')
        self.count = options.get("count")
        self.bz2 = options.get("bz2")
        self.progress = options.get("progress")

        if iterator:
            self.iterator = partial(sql_iterator, step=lambda x: max(x / 10, 5000))
            self.iterator.name = "Custom SQL iterator"
        else:
            self.iterator = lambda x: x.iterator()
            self.iterator.name = "Builtin django queryset iterator()"

        log("Started with options: %s" % options)
        log("app labels: %s" % ",".join(app_labels))

        excluded_apps = set()
        excluded_models = set()
        for exclude in excludes:
            if '.' in exclude:
                app_label, model_name = exclude.split('.', 1)
                model_obj = get_model(app_label, model_name)
                if not model_obj:
                    msg = 'Unknown model in excludes: %s' % exclude
                    error(msg)
                    raise CommandError(msg)
                excluded_models.add(model_obj)
            else:
                try:
                    app_obj = get_app(exclude)
                    excluded_apps.add(app_obj)
                except ImproperlyConfigured:
                    msg = 'Unknown app in excludes: %s' % exclude
                    error(msg)
                    raise CommandError(msg)

        if len(app_labels) == 0:
            app_list = SortedDict((app, None) for app in get_apps() if app not in excluded_apps)
        else:
            app_list = SortedDict()
            for label in app_labels:
                try:
                    app_label, model_label = label.split('.')
                    try:
                        app = get_app(app_label)
                    except ImproperlyConfigured:
                        msg = "Unknown application: %s" % app_label
                        error(msg)
                        raise CommandError(msg)
                    if app in excluded_apps:
                        continue
                    model = get_model(app_label, model_label)
                    if model is None:
                        msg = "Unknown model: %s.%s" % (app_label, model_label)
                        error(msg)
                        raise CommandError(msg)

                    if app in app_list.keys():
                        if app_list[app] and model not in app_list[app]:
                            app_list[app].append(model)
                    else:
                        app_list[app] = [model]
                except ValueError:
                    # This is just an app - no model qualifier
                    app_label = label
                    try:
                        app = get_app(app_label)
                    except ImproperlyConfigured:
                        msg = "Unknown application: %s" % app_label
                        error(msg)
                        raise CommandError(msg)
                    if app in excluded_apps:
                        continue
                    app_list[app] = None

        # Process the list of models
        deps = Dependencies()
        models = set()
        for app, model_list in app_list.items():
            if model_list is None:
                model_list = get_models(app)

            for model in model_list:
                models.add(model)
        models = list(models)

        for model in models:
            deps.add_to_tree(model)
            many_to_many = self.dump_model(model)
            for m2m in many_to_many:
                if m2m not in models:
                    models.append(m2m)

        with open(os.path.join(self.directory, "DEPENDENCIES"), "w") as f:
            f.writelines(["%s_%s" % (m._meta.app_label, m._meta.object_name) + "\n" for m in deps.tree])

    def dump_model(self, model):
        """
        Dump a model to file and return the related m2m models.
        """
        def convert(obj):
            """
            Convert to Postgres data representation.
            """
            converted_values = []
            for key in pg_copy.fields:
                value = getattr(obj, key)

                if isinstance(value, bool):
                    new_value = u"t" if value else u"f"
                # ForeignKey or OneToOne
                elif isinstance(value, Model):
                    new_value = smart_unicode(value.pk)
                elif isinstance(value, datetime.datetime):
                    # Adding TZ info is costly, but we can't just append a fixed
                    # distance from UTC to our datestrings because of daylight
                    # savings time.
                    if value.tzinfo is None:
                        value = TIMEZONE.localize(value)

                    # Not much difference between formating a datetime or
                    # creating a datetime_safe and then formatting it.
                    # Each opertion is quite costly
                    new_value = datetime_safe.new_datetime(value).strftime("%Y-%m-%d %H:%M:%S%z")
                    new_value = smart_unicode(new_value)
                elif isinstance(value, datetime.date):
                    new_value = datetime_safe.new_date(value).strftime("%Y-%m-%d")
                    new_value = smart_unicode(new_value)
                elif isinstance(value, (int, float)):
                    new_value = smart_unicode(value)
                elif value is None:
                    new_value = ur"\N"
                else:
                    # Escape all backslashes, tab, newline and CR
                    value = value.replace("\\", r"\\")
                    value = value.replace("\t", r"\t").replace("\n", r"\n").replace("\r", r"\r")
                    new_value = smart_unicode(value)
                converted_values.append(new_value)

            return u"%s\n" % u"\t".join(converted_values)

        pg_copy = PostgresCopy(model)
        model_file = os.path.join(self.directory, "%s_%s" % (model._meta.app_label, model._meta.object_name))

        # For --stats
        mem_profile = MemoryProfile()
        time_start = time.time()
        db_queries = len(connection.queries)

        # We have to explicitly pass all ForeignKey and OneToOne fields, because
        # select_related() without params does not follow FKs with null=True
        queryset = model.objects.select_related(*pg_copy.foreign_keys)
        if self.count > 0:
            queryset = queryset[:self.count]
        obj_count = queryset.count()

        # The min is necessary to avoid 1 / 0 on small --count
        # arguments
        progress_break = min(obj_count, 30)

        msg = "%s (%s)" % (model._meta.object_name, obj_count)
        log(msg)
        if self.progress:
            print msg

        with codecs.open(model_file, "w", "utf-8") as f:
            f.write(pg_copy.header())
            loop_count = 0
            progress_string = ""
            for obj in self.iterator(queryset):
                f.write(convert(obj))
                mem_profile.measure()
                loop_count += 1
                if self.progress:
                    if (loop_count % (obj_count / progress_break)) == 0:
                        progress_string += "."
                        sys.stdout.write("[%s" % (progress_string) .ljust(progress_break) + "]\r")
                        sys.stdout.flush()
            f.write(pg_copy.footer())

        time_bz_start = time.time()
        if self.bz2:
            subprocess.check_call(["bzip2", "-f", model_file])

        if self.stats:
            if self.progress:
                print
            print "    Iterator: %s" % self.iterator.name
            print "    Count: %s" % obj_count
            print "    DB Queries: %s" % (len(connection.queries) - db_queries)
            print "    Time : %6.2f s" % (time.time() - time_start)
            if self.bz2:
                print "    Time bz: %6.2f s" % (time.time() - time_bz_start)
            print "    RAM  : %6.2f MB" % (mem_profile.max_usage / 1024.0)

        return pg_copy.many_to_many


class PostgresCommand(object):
    def __init__(self, model):
        self.model = model
        self.table = model._meta.db_table
        self.columns = [f.column for f in model._meta.fields]
        self.fields = [f.name for f in model._meta.fields]
        self.foreign_keys = [f.name for f in model._meta.fields if isinstance(f, ForeignKey)]
        self.foreign_keys.extend([f.name for f in model._meta.fields if isinstance(f, OneToOneField)])
        self.many_to_many = []
        for m2m in self.model._meta.many_to_many:
            self.many_to_many.append(m2m.rel.through)

    @staticmethod
    def quote(value):
        return "\"%s\"" % value


class PostgresCopy(PostgresCommand):
    def header(self):
        return u"COPY %s (%s) FROM stdin;\n" % (self.quote(self.table),
                                                ",".join((self.quote(x) for x in self.columns)))

    @staticmethod
    def footer():
        return u"\\.\n\n"

    def __str__(self):
        return "<PSQL Copy '%s'>" % self.table


class Dependencies(object):
    def __init__(self):
        self.done = set()
        self.tree = []

    def add_to_tree(self, model_obj):
        self.tree.extend(self._dependency_tree(model_obj))
        if model_obj not in self.tree:
            self.tree.append(model_obj)

    @staticmethod
    def _get_fks(model_obj):
        res = []
        for field in model_obj._meta.fields:
            if isinstance(field, (ForeignKey, OneToOneField)):
                res.append(field.related.parent_model)
        return res

    def _dependency_tree(self, model_obj):
        deps = []
        self.done.add(model_obj)
        fks = self._get_fks(model_obj)
        for fk in fks:
            if fk not in self.done:
                deps.extend(self._dependency_tree(fk))
                deps.append(fk)
        return deps


if __name__ == "__main__":
    # Run profiling
    if False:
        CODE = """
c = Command()
opts = {'count': '10000', 'stats': True, 'bz2': True, 'iterator': False,
            'database': 'default', 'pythonpath': None, 'verbosity': '1',
            'traceback': None, 'exclude': [], 'directory': '/tmp/dumps',
            'progress': True, 'settings': None}
c.handle("backend.customer", **opts)
        """
        cProfile.run(CODE, "dumpfastprof")
        p = pstats.Stats("dumpfastprof")
        s = "-" * 10
        print s, "cumulative", s
        p.sort_stats("cumulative").print_stats(20)
        print s, "time", s
        p.sort_stats("time").print_stats(20)
