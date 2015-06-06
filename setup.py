from distutils.core import setup

setup(
    name="icsw",
    version="3.0.0",
    description="The init.at Clustersoftware (CORUVS, NOCTUA, NESTOR)",
    license="GPL",
    url="http://www.init.at",
    author="Andreas Lang-Nevyjel",
    author_email="lang-nevyjel@init.at",
    packages=[
        "initat",
        "initat.icsw",
        "initat.icsw.logwatch",
        "initat.icsw.setup",
        "initat.icsw.service",
        "initat.icsw.license",
        "initat.tools",
        "initat.rms",
        "initat.cluster",
        "initat.cluster.backbone",
        "initat.cluster.backbone.0800_models",
        "initat.cluster.backbone.models",
        "initat.cluster.backbone.migrations",
        "initat.cluster.backbone.serializers",
        "initat.cluster.backbone.management",
        "initat.cluster.backbone.management.commands",
        "initat.cluster.backbone.management.commands.fixtures",
        "initat.cluster.rms",
        "initat.cluster.rms.rms_addons",
        "initat.cluster.frontend",
        "initat.cluster.frontend.forms",
        "initat.cluster.frontend.ext",
        "initat.cluster.frontend.management",
        "initat.cluster.frontend.management.commands",
        "initat.cluster.urls",
        "initat.cluster_config_server",
        "initat.cluster_server",
        "initat.cluster_server.capabilities",
        "initat.cluster_server.modules",
        "initat.collectd",
        "initat.collectd.collectd_types",
        "initat.discovery_server",
        "initat.logcheck_server",
        "initat.logging_server",
        "initat.md_config_server",
        "initat.md_config_server.config",
        "initat.md_config_server.icinga_log_reader",
        "initat.md_config_server.special_commands",
        "initat.md_config_server.special_commands.instances",
        "initat.md_config_server.kpi",
        "initat.package_install",
        "initat.package_install.server",
        "initat.package_install.client",
        "initat.rrd_grapher",
        "initat.mother",
        "initat.snmp",
        "initat.snmp.handler",
        "initat.snmp.handler.instances",
        "initat.snmp.process",
        "initat.snmp.sink",
        "initat.snmp_relay",
        "initat.meta_server",
        "initat.host_monitoring",
        "initat.host_monitoring.modules",
        "initat.host_monitoring.exe",
        "initat.host_monitoring.modules.raidcontrollers"
    ],
    data_files=[
        (
            "/opt/cluster/bin",
            [
                # cbc
                "opt/cluster/bin/compile_libgoto.py",
                "opt/cluster/bin/compile_openmpi.py",
                "opt/cluster/bin/compile_hpl.py",
                "opt/cluster/bin/compile_fftw.py",
                "opt/cluster/bin/read_bonnie.py",
                "opt/cluster/bin/bonnie.py",
                "opt/cluster/bin/n_from_mem.py",
                "opt/cluster/bin/read_hpl_result.py",
                "opt/cluster/bin/check_vasp.py",
                # tools
                "opt/cluster/bin/get_cpuid.py",
                "opt/cluster/bin/dump_graph_structure.py",
                "opt/cluster/bin/user_info.py",
                "opt/cluster/bin/clog.py",
                "opt/cluster/bin/device_info.py",
                "opt/cluster/bin/load_firmware.sh",
                "opt/cluster/bin/populate_ramdisk.py",
                "opt/cluster/bin/make_image.py",
                "opt/cluster/bin/change_cluster_var.py",
                "opt/cluster/bin/show_config_script.py",
                "opt/cluster/bin/resync_config.sh",
                "opt/cluster/bin/send_command.py",
                "opt/cluster/bin/send_command_zmq.py",
                # repo tools
                # "opt/cluster/bin/migrate_repos.py",
                # icsw helper
                "opt/cluster/bin/ics_tools.sh",
                # license
                "opt/cluster/bin/license_server_tool.py",
                # set passive checkresult
                "opt/cluster/bin/set_passive_checkresult.py",
                # cdfetch for collectd
                "opt/cluster/bin/cdfetch.py",
                "opt/cluster/bin/sgestat.py",
                "opt/cluster/bin/cluster-server.py",
                "opt/cluster/bin/license_progs.py",
                "opt/cluster/bin/loadsensor.py",
                "opt/cluster/bin/modify_object.py",
            ]
        ),
        (
            "/opt/cluster/sbin/pis",
            [
                "opt/cluster/sbin/pis/cluster_post_install.sh",
                "opt/cluster/sbin/pis/sge_post_install.sh",
                "opt/cluster/sbin/pis/modify_service.sh",
                "opt/cluster/sbin/pis/webfrontend_pre_start.sh",
                "opt/cluster/sbin/pis/webfrontend_post_install.sh",
                "opt/cluster/sbin/pis/hpc_library_post_install.py",
                "opt/cluster/sbin/pis/icsw_client_post_install.sh",
                "opt/cluster/sbin/pis/icsw_server_post_install.sh",
            ]
        ),
        (
            "/opt/cluster/sbin",
            [
                "opt/cluster/sbin/tls_verify.py",
                "opt/cluster/sbin/openvpn_scan.py",
                "opt/cluster/sbin/collclient.py",
                "opt/cluster/sbin/log_error.py",
                "opt/cluster/sbin/logging-client.py",
                "opt/cluster/sbin/tls_verify.py",
                "opt/cluster/sbin/lse",
                "opt/cluster/sbin/check_rpm_lists.py",
                "opt/cluster/sbin/make_package.py",
                "opt/cluster/sbin/force_redhat_init_script.sh",
            ]
        ),
        (
            "/opt/cluster/sge",
            [
                "opt/cluster/sge/sge_editor_conf.py",
                "opt/cluster/sge/modify_sge_config.sh",
                "opt/cluster/sge/add_logtail.sh",
                "opt/cluster/sge/sge_request",
                "opt/cluster/sge/sge_qstat",
                "opt/cluster/sge/build_sge6x.sh",
                "opt/cluster/sge/create_sge_links.py",
                "opt/cluster/sge/proepilogue.py",
                "opt/cluster/sge/qlogin_wrapper.sh",
                "opt/cluster/sge/sge_starter.sh",
                "opt/cluster/sge/batchsys.sh_client",
                # info files
                "opt/cluster/sge/.sge_files",
                "opt/cluster/sge/.party_files",
            ]
        ),
        (
            "/opt/cluster/sge/init.d",
            [
                "opt/cluster/sge/init.d/sgemaster",
                "opt/cluster/sge/init.d/sgeexecd",
            ]
        ),
        (
            "/opt/cluster/share/collectd",
            [
                "opt/cluster/share/collectd/aggregates.xml",
            ]
        ),
        (
            "/opt/cluster/share/collectd/aggregates.d",
            [
            ]
        ),
        (
            "/opt/cluster/share/rrd_grapher",
            [   
                "opt/cluster/share/rrd_grapher/color_rules.xml",
                "opt/cluster/share/rrd_grapher/color_tables.xml",
                "opt/cluster/share/rrd_grapher/compound.xml",
            ]   
        ),  
        (
            "/opt/cluster/share/rrd_grapher/compound.d",
            [
            ]
        ),
        (
            "/opt/cluster/share/rrd_grapher/color_tables.d",
            [
            ]
        ),
        (
            "/opt/cluster/share/rrd_grapher/color_rules.d",
            [
            ]
        ),

    ],
    scripts=[
    ],
    package_data={
        "initat.cluster.frontend": [
            "static/css/*",
            "static/fonts/*",
            "static/icons/*",
            "static/icsw/*/*.coffee",
            "static/icsw/*/*.html",
            "static/icsw/*/*/*.coffee",
            "static/icsw/*/*/*.html",
            "static/images/*",
            "static/images/*/*",
            "static/images/*/*/*",
            "static/css/*",
            "static/css/*/*",
            "static/js/*",
            "static/js/*/*",
            "static/js/*/*/*",
            "static/js/*/*/*/*",
            "static/js/*/*/*/*/*",
            "templates/*.html",
            "templates/angular/*.coffee",
        ],
        "initat.cluster": [
            "runserver.sh",
        ],
        "initat.cluster.rms": [
            "templates/*.html",
        ],
        "initat.cluster.backbone": [
            "fixtures_deprecated/*.xml",
        ],
    }
)
