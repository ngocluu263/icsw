from distutils.core import setup

setup(
    name="icsw",
    version="3.0.0",
    description="The init.at Clustersoftware (CORUVS, NOCTUA, NESTOR)",
    url="http://www.init.at",
    author="Andreas Lang-Nevyjel",
    author_email="lang-nevyjel@init.at",
    packages=[
        "initat",
        "initat.rms",
        "initat.cluster",
        "initat.cluster.backbone",
        "initat.cluster.backbone.0800_models",
        "initat.cluster.backbone.models",
        "initat.cluster.backbone.migrations",
        "initat.cluster.backbone.management",
        "initat.cluster.backbone.management.commands",
        "initat.cluster.rms",
        "initat.cluster.rms.rms_addons",
        "initat.cluster.frontend",
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
        "initat.snmp_relay",
        "initat.meta_server",
        "initat.host_monitoring",
        "initat.host_monitoring.modules",
        "initat.host_monitoring.exe",
        "initat.host_monitoring.modules.raidcontrollers"
    ],
    scripts=[
        "compile_libgoto.py",
        "compile_openmpi.py",
        "compile_hpl.py",
        "compile_fftw.py",
        "read_bonnie.py",
        "bonnie.py",
        "n_from_mem.py",
        "read_hpl_result.py",
        "check_vasp.py",
    ],
    py_modules=[
        "configfile",
        "ip",
        "inet",
        "icmp",
        "icmp_class",
        "cpu_database",
        "pci_database",
        "send_mail",
        "process_tools",
        "logging_tools",
        "server_command",
        "mail_tools",
        "uuid_tools",
        "rrd_tools",
        "net_tools",
        "threading_tools",
        "threading_tools_ancient",
        "ipvx_tools",
        "rpm_build_tools",
        "openssl_tools",
        "config_tools",
        "check_scripts",
        "drbd_tools",
        "partition_tools",
        "rsync_tools",
        "io_stream_helper",
        "libvirt_tools",
        "affinity_tools",
        "server_mixins",
        "inotify_tools",
        "compile_tools",
    ],
    package_data={
        "initat.cluster.frontend": [
            "*/*",
        ]
    }
)
