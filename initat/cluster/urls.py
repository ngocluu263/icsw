from django.conf.urls import patterns, include, url
from django.conf import settings
import sys

from django.contrib import admin
admin.autodiscover()

import initat.cluster.sub_urls

urlpatterns = initat.cluster.sub_urls.sub_patterns

urlpatterns += patterns("",
    (r"^%s/admin/" % (settings.REL_SITE_ROOT)               , include(admin.site.urls)),
    #(r"^%s/media/(?P<path>.*)$" % (settings.REL_SITE_ROOT)  , "django.views.static.serve", {
    #    "document_root" : settings.MEDIA_ROOT,
    #    "show_indexes"  : True}),
)

