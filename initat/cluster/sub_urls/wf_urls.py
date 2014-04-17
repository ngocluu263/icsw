#!/usr/bin/python-init -Otu

from django.conf.urls import patterns, include, url
from django.conf import settings
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
import os
from initat.cluster.frontend import rest_views, device_views, main_views, network_views, \
    monitoring_views, user_views, package_views, config_views, boot_views, session_views, rrd_views, \
    base_views, setup_views
from initat.cluster.rms import rms_views
# from rest_framework.urlpatterns import format_suffix_patterns

handler404 = main_views.index.as_view()

# Uncomment the next two lines to enable the admin:
# from django.contrib import admin
# admin.autodiscover()

session_patterns = patterns(
    "initat.cluster.frontend",
    url(r"logout", session_views.sess_logout.as_view(), name="logout"),
    url(r"login" , session_views.sess_login.as_view() , name="login"),
)

rms_patterns = patterns(
    "initat.cluster.rms",
    url(r"overview"        , rms_views.overview.as_view()         , name="overview"),
    url(r"get_header_xml"  , rms_views.get_header_xml.as_view()   , name="get_header_xml"),
    url(r"get_rms_json"    , rms_views.get_rms_json.as_view()     , name="get_rms_json"),
    url(r"control_job"     , rms_views.control_job.as_view()      , name="control_job"),
    url(r"get_file_content", rms_views.get_file_content.as_view() , name="get_file_content"),
    url(r"set_user_setting", rms_views.set_user_setting.as_view() , name="set_user_setting"),
    url(r"get_user_setting", rms_views.get_user_setting.as_view() , name="get_user_setting"),
)


base_patterns = patterns(
    "initat.cluster.setup",
    url("^get_gauge_info$"                    , base_views.get_gauge_info.as_view()     , name="get_gauge_info"),
    url("^get_cat_tree$"                      , base_views.get_category_tree.as_view()  , name="category_tree"),
    url("^change_category"                    , base_views.change_category.as_view()    , name="change_category"),
    url("^prune_cat_tree"                     , base_views.prune_category_tree.as_view(), name="prune_categories"),
)

setup_patterns = patterns(
    "initat.cluster.setup",
    url(r"p_overview"         , setup_views.partition_overview.as_view()        , name="partition_overview"),
    url(r"xml/validate"       , setup_views.validate_partition.as_view()        , name="validate_partition"),
    url(r"i_overview"         , setup_views.image_overview.as_view()            , name="image_overview"),
    url(r"k_overview"         , setup_views.kernel_overview.as_view()           , name="kernel_overview"),
    url(r"xml/rescan_images"  , setup_views.scan_for_images.as_view()           , name="rescan_images"),
    url(r"xml/use_image"      , setup_views.use_image.as_view()                 , name="use_image"),
    url(r"xml/rescan_kernels" , setup_views.rescan_kernels.as_view()            , name="rescan_kernels"),
)

config_patterns = patterns(
    "initat.cluster.frontend",
    url("^show_config$"         , config_views.show_configs.as_view()            , name="show_configs"),
    url("^set_config_cb$"       , config_views.alter_config_cb.as_view()         , name="alter_config_cb"),
    url("^generate_config$"     , config_views.generate_config.as_view()         , name="generate_config"),
    url("^download_config/(?P<hash>.*)$", config_views.download_configs.as_view(), name="download_configs"),
    url("^upload_config$"       , config_views.upload_config.as_view()           , name="upload_config"),
    url("^xml/show_dev_vars"    , config_views.get_device_cvars.as_view()        , name="get_device_cvars"),
)

boot_patterns = patterns(
    "initat.cluster.frontend",
    url("^show_boot$"          , boot_views.show_boot.as_view()         , name="show_boot"),
    url("^xml/get_boot_infojs$", boot_views.get_boot_info_json.as_view(), name="get_boot_info_json"),
    url("^xml/get_devlog_info$", boot_views.get_devlog_info.as_view()   , name="get_devlog_info"),
    url("^soft_control$"       , boot_views.soft_control.as_view()      , name="soft_control"),
    url("^hard_control$"       , boot_views.hard_control.as_view()      , name="hard_control"),
    url("^update_device/(\d+)$", boot_views.update_device.as_view()     , name="update_device"),
)

device_patterns = patterns(
    "initat.cluster.frontend",
    url("^device_tree$"       , device_views.device_tree.as_view()        , name="tree"),
    url("^set_selection$"     , device_views.set_selection.as_view()      , name="set_selection"),
    url("^config$"            , device_views.show_configs.as_view()       , name="show_configs"),
    url("^connections"        , device_views.connections.as_view()        , name="connections"),
    url("manual_connection"   , device_views.manual_connection.as_view()  , name="manual_connection"),
    url("variables$"          , device_views.variables.as_view()          , name="variables"),
    url("change_devices$"     , device_views.change_devices.as_view()     , name="change_devices"),
    url("scan_device_network$", device_views.scan_device_network.as_view(), name="scan_device_network"),
)

network_patterns = patterns(
    "initat.cluster.frontend",
    url("^network$"           , network_views.show_cluster_networks.as_view() , name="show_networks"),
    url("^dev_network$"       , network_views.device_network.as_view()        , name="device_network"),
    url("^copy_network$"      , network_views.copy_network.as_view()          , name="copy_network"),
    url("^json_network$"      , network_views.json_network.as_view()          , name="json_network"),
    url("^cdnt$"              , network_views.get_domain_name_tree.as_view()  , name="domain_name_tree"),
)

monitoring_patterns = patterns(
    "initat.cluster.frontend",
    url("^setup$"              , monitoring_views.setup.as_view()            , name="setup"),
    url("^extsetupc$"          , monitoring_views.setup_cluster.as_view()    , name="setup_cluster"),
    url("^extsetupe$"          , monitoring_views.setup_escalation.as_view() , name="setup_escalation"),
    url("^xml/dev_config$"     , monitoring_views.device_config.as_view()    , name="device_config"),
    url("^create_config$"      , monitoring_views.create_config.as_view()    , name="create_config"),
    url("^to_icinga$"          , monitoring_views.call_icinga.as_view()      , name="call_icinga"),
    url("^xml/read_part$"      , monitoring_views.fetch_partition.as_view()  , name="fetch_partition"),
    url("^get_node_status"     , monitoring_views.get_node_status.as_view()  , name="get_node_status"),
    url("^get_node_config"     , monitoring_views.get_node_config.as_view()  , name="get_node_config"),
    url("^build_info$"         , monitoring_views.build_info.as_view()       , name="build_info"),
)

user_patterns = patterns(
    "initat.cluster.frontend",
    url("overview/$"                , user_views.overview.as_view()              , name="overview"),
    url("sync$"                     , user_views.sync_users.as_view()            , name="sync_users"),
    url("^save_layout_state$"       , user_views.save_layout_state.as_view()     , name="save_layout_state"),
    url("^set_user_var$"            , user_views.set_user_var.as_view()          , name="set_user_var"),
    url("^get_user_var$"            , user_views.get_user_var.as_view()          , name="get_user_var"),
    url("^change_obj_perm$"         , user_views.change_object_permission.as_view(), name="change_object_permission"),
    url("^account_info$"            , user_views.account_info.as_view()          , name="account_info"),
    url("^global_settings$"         , user_views.global_settings.as_view()       , name="global_settings"),
    url("^background_info$"         , user_views.background_job_info.as_view()   , name="background_job_info"),
    url("^chdc$"                    , user_views.clear_home_dir_created.as_view(), name="clear_home_dir_created"),
)

pack_patterns = patterns(
    "initat.cluster.frontend",
    url("overview/repo$"       , package_views.repo_overview.as_view()      , name="repo_overview"),
    url("search/retry"         , package_views.retry_search.as_view()       , name="retry_search"),
    url("search/use_package"   , package_views.use_package.as_view()        , name="use_package"),
    url("search/unuse_package" , package_views.unuse_package.as_view()      , name="unuse_package"),
    # url("install"              , package_views.install.as_view()            , name="install"),
    # url("refresh"              , package_views.refresh.as_view()            , name="refresh"),
    url("pack/add"             , package_views.add_package.as_view()        , name="add_package"),
    url("pack/remove"          , package_views.remove_package.as_view()     , name="remove_package"),
    url("pack/change"          , package_views.change_package.as_view()     , name="change_pdc"),
    url("pack/change_tstate"   , package_views.change_target_state.as_view(), name="change_target_state"),
    url("pack/change_pflag"    , package_views.change_package_flag.as_view(), name="change_package_flag"),
    url("pack/sync"            , package_views.synchronize.as_view()        , name="synchronize"),
    url("pack/get_status"      , package_views.get_pdc_status.as_view()     , name="get_pdc_status"),
)

main_patterns = patterns(
    "initat.cluster.frontend",
    url(r"^index$"         , main_views.index.as_view()             , name="index"),
    url(r"^permission$"    , main_views.permissions_denied.as_view(), name="permission_denied"),
    url(r"^info$"          , main_views.info_page.as_view()         , name="info_page"),
    url(r"^server_info$"   , main_views.get_server_info.as_view()   , name="get_server_info"),
    url(r"^server_control$", main_views.server_control.as_view()    , name="server_control"),
)

rrd_patterns = patterns(
    "initat.cluster.frontend",
    url(r"^dev_rrds$" , rrd_views.device_rrds.as_view(), name="device_rrds"),
    url(r"^graph_rrd$", rrd_views.graph_rrds.as_view() , name="graph_rrds"),
)

rpl = []
for obj_name in rest_views.REST_LIST:
    rpl.extend([
        url("^%s$" % (obj_name), getattr(rest_views, "%s_list" % (obj_name)).as_view(), name="%s_list" % (obj_name)),
        url("^%s/(?P<pk>[0-9]+)$" % (obj_name), getattr(rest_views, "%s_detail" % (obj_name)).as_view(), name="%s_detail" % (obj_name)),
    ])
rpl.extend([
    url("^device_tree$", rest_views.device_tree_list.as_view(), name="device_tree_list"),
    url("^device_tree/(?P<pk>[0-9]+)$", rest_views.device_tree_detail.as_view(), name="device_tree_detail"),
    url("^device_selection$", rest_views.device_selection_list.as_view(), name="device_selection_list"),
    url("^home_export_list$", rest_views.rest_home_export_list.as_view(), name="home_export_list"),
    url("^csw_object_list$", rest_views.csw_object_list.as_view({"get" : "list"}), name="csw_object_list"),
    url("^netdevice_peer_list$", rest_views.netdevice_peer_list.as_view({"get" : "list"}), name="netdevice_peer_list"),
    url("^fetch_forms$", rest_views.fetch_forms.as_view({"get" : "list"}), name="fetch_forms"),
])

rest_patterns = patterns(
    "initat.cluster.frontend",
    *rpl
)
# rest_patterns = format_suffix_patterns(rest_patterns)

doc_patterns = patterns(
    "",
    url(r"^%s/(?P<path>.*)$" % (settings.REL_SITE_ROOT)    ,
        "django.views.static.serve", {
            "document_root" : os.path.join(settings.FILE_ROOT, "doc", "build", "html")
            }, name="show"),
)

my_url_patterns = patterns(
    "",
    url(r"^$"         , session_views.redirect_to_main.as_view()),
    # redirect old entry point
    url(r"^main.py$"  , session_views.redirect_to_main.as_view()),
    url(r"^base/"     , include(base_patterns      , namespace="base")),
    url(r"^session/"  , include(session_patterns   , namespace="session")),
    url(r"^config/"   , include(config_patterns    , namespace="config")),
    url(r"^rms/"      , include(rms_patterns       , namespace="rms")),
    url(r"^main/"     , include(main_patterns      , namespace="main")),
    url(r"^device/"   , include(device_patterns    , namespace="device")),
    url(r"^network/"  , include(network_patterns   , namespace="network")),
    url(r"^mon/"      , include(monitoring_patterns, namespace="mon")),
    url(r"^boot/"     , include(boot_patterns      , namespace="boot")),
    url(r"^setup/"    , include(setup_patterns     , namespace="setup")),
    url(r"^user/"     , include(user_patterns      , namespace="user")),
    url(r"^pack/"     , include(pack_patterns      , namespace="pack")),
    url(r"^rrd/"      , include(rrd_patterns       , namespace="rrd")),
    url(r"^doc/"      , include(doc_patterns       , namespace="doc")),
    url(r"^rest/"     , include(rest_patterns      , namespace="rest")),
)

url_patterns = patterns(
    "",
    url(r"^%s/" % (settings.REL_SITE_ROOT), include(my_url_patterns)),
    url(r"^$", session_views.redirect_to_main.as_view()),
)

url_patterns += staticfiles_urlpatterns()

