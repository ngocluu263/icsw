from distutils.core import setup

SERVER_LIST = [
    "host-monitoring-zmq.py",
]

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
                "opt/cluster/bin/migrate_repos.py",
                # icsw helper
                "opt/cluster/bin/ics_tools.sh",
                # license
                "opt/cluster/bin/license_server_tool.py",
            ]
        ),
        (
            "/opt/cluster/sbin",
            SERVER_LIST,
        ),
        (
            "/opt/cluster/sbin/pis",
            [
                "pis/cluster_post_install.sh",
                "pis/sge_post_install.sh",
                "pis/webfrontend_pre_start.sh",
                "pis/webfrontend_post_install.sh",
                "pis/hpc_library_post_install.py",
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
