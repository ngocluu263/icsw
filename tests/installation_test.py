#!/usr/bin/python-init -Ot

import subprocess
import time
import paramiko
import socket
import sys
import argparse
try:
    import ConfigParser
except ImportError:
    import configparser as ConfigParser

RESET_PW_SCRIPT = "from initat.cluster.backbone.models import user;" \
                  "u = user.objects.get(login='admin');u.password = 'abc123';u.save()"


def install_icsw_base_system(host, username, password, package_manager, machine_name):
    # try to connect via ssh
    sys.stdout.write("Trying to connect via ssh ... ")
    sys.stdout.flush()
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    while True:
        try:
            ssh.connect(host, username=username, password=password)
            sys.stdout.write("done\n")
            sys.stdout.flush()
            break
        except socket.error as e:
            if e.errno != 111:
                raise e
            else:
                time.sleep(1)

    if package_manager == "zypper":
        setup_command = "zypper ref && zypper --non-interactive in icsw-server icsw-client nginx-init"
    elif package_manager == "apt-get":
        setup_command = "apt-get update && apt-get -y --force-yes install icsw-server icsw-client nginx-init"
    elif package_manager == "yum":
        setup_command = "yum check-update && yum -y --nogpgcheck install icsw-server icsw-client nginx-init"
    else:
        setup_command = ""

    commands = [
        ("Installing latest icsw-server and icsw-client ... ", setup_command),
        ("Perfoming icsw setup ... ", "/opt/cluster/sbin/icsw setup --ignore-existing --engine psql --port 5432"),
        ("Resetting admin password ... ", '/opt/cluster/sbin/clustermanage.py shell -c "{}"'.format(RESET_PW_SCRIPT)),
        ("Enabling uwsgi-init ... ", "/opt/cluster/sbin/icsw state enable uwsgi-init"),
        ("Enabling nginx ... ", "/opt/cluster/sbin/icsw state enable nginx"),
        ("Restarting icsw services ... ",  "/opt/cluster/sbin/icsw service restart")
    ]

    with open("{}.log".format(machine_name), "a", 0) as log_file:
        for status_msg, command in commands:
            sys.stdout.write(status_msg)
            sys.stdout.flush()

            ssh_stdin, ssh_stdout, ssh_stderr = ssh.exec_command(command)
            log_file.write("*** Command executed: {}\n".format(command))

            while True:
                try:
                    output = ssh_stdout.next()
                    log_file.write(output)
                except StopIteration:
                    break

            sys.stdout.write("done\n")
            sys.stdout.flush()


def reset_test_server(user, password, server_id, snapshot_id, machine_name):
    base_uri = "https://ovirt-engine.init.at/ovirt-engine/api/vms"
    base_params = [
        "curl",
        "-s",
        "-k",
        "-u", "{}:{}".format(user, password),
        "-H", "Content-type: application/xml",
    ]

    # command structure is ([Print/Status Message], [api uri to perform action on], [GET/POST action_type],
    # [output to check for])
    commands = [
        ("Powering off test system ... ", "{}/{}/stop".format(base_uri, server_id), "POST", None),
        ("Waiting for system to power off ... ", "{}/{}".format(base_uri, server_id), "GET",
         "<status>down</status>"),
        ("Restoring snapshot ... ", "{}/{}/snapshots/{}/restore".format(base_uri, server_id, snapshot_id), "POST",
         None),
        ("Waiting for snapshot restore ... ", "{}/{}".format(base_uri, server_id), "GET", "<status>down</status>"),
        ("Powering up test system ... ", "{}/{}/start".format(base_uri, server_id), "POST", None),
        ("Waiting for system to be up ... ", "{}/{}".format(base_uri, server_id), "GET", "<status>up</status>")
    ]

    with open("{}.log".format(machine_name), "a", 0) as log_file:
        for status_msg, action_uri, method, check_output in commands:
            sys.stdout.write(status_msg)
            sys.stdout.flush()

            args = [param for param in base_params]
            if method == "POST":
                args.append("-d")
                args.append("<action/>")
            args.append("-X")
            args.append(method)
            args.append(action_uri)

            while True:
                output = subprocess.check_output(args)
                log_file.write("*** Command executed: {}\n".format("".join(args)))
                log_file.write(output)

                if check_output:
                    if check_output in output:
                        break
                    else:
                        time.sleep(5)
                else:
                    break

            sys.stdout.write("done\n")
            sys.stdout.flush()


def basic_availability_test(host, machine_name):
    sys.stdout.write("Checking availability of icsw interface ... ")
    sys.stdout.flush()

    time.sleep(60)

    args = ["curl", "-s", "http://{}/icsw/api/v2/user/GetInitProduct".format(host)]

    try:
        output = subprocess.check_output(args)
    except subprocess.CalledProcessError as e:
        output = "*** Error connecting to {}".format(host)

    with open("{}.log".format(machine_name), "a", 0) as log_file:
        log_file.write("*** Command executed: {}\n".format("".join(args)))
        log_file.write(output)

    if "CORVUS Corax" in output and "CORVUS" in output:
        sys.stdout.write("done\n")
        sys.stdout.flush()
    else:
        sys.stdout.write("error\n")
        sys.stdout.flush()


def main():
    config = ConfigParser.ConfigParser()
    config.read("installation_test.cfg")

    parser = argparse.ArgumentParser(description='icsw installation tests')

    parser.add_argument('--ovirt-user', nargs=1, action='store', dest='ovirt_user',
                        help='OVIrt username', required=True)

    parser.add_argument('--ovirt-pass', nargs=1, action='store', dest='ovirt_pass',
                        help='OVIrt password', required=True)

    machine_names_str = ", ".join([system_name for system_name in config.sections()])
    parser.add_argument('--test-machine', nargs=1, action='store', dest='test_machine',
                        help='One of the following: {}'.format(machine_names_str), required=True)

    args = parser.parse_args()

    config = ConfigParser.ConfigParser()
    config.read("installation_test.cfg")

    test_system_name = args.test_machine[0]
    test_system_id = config.get(test_system_name, "id")
    snapshot_id = config.get(test_system_name, "snapshot_id")
    ip = config.get(test_system_name, "ip")
    password = config.get(test_system_name, "password")
    package_manager = config.get(test_system_name, "package_manager")

    reset_test_server(args.ovirt_user[0], args.ovirt_pass[0], test_system_id, snapshot_id, test_system_name)
    install_icsw_base_system(ip, "root", password, package_manager, test_system_name)
    basic_availability_test(ip, test_system_name)


if __name__ == "__main__":
    main()
