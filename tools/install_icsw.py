#!/usr/bin/env python
#
# Copyright (C) 2015 Bernhard Mallinger
#
# Send feedback to: <mllinger@init.at>
#
# This file is part of icsw
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
import argparse
import logging

import platform
import os
import os.path
import subprocess
import sys


log = logging.getLogger("install_icsw")


try:
    input = raw_input  # python 2/3
except NameError:
    pass


class OSHandler(object):
    def __init__(self, opts):
        self.opts = opts

    @classmethod
    def get_local_os(cls, opts):
        """
        :rtype: OSHandler
        """
        # format as in platform module
        # for ubuntu, ubuntu is returned anyway, so supported dists does not appear to be strict
        supported_dists = ("SuSE", "centos", "debian")
        distro = platform.linux_distribution(supported_dists=supported_dists,
                                             full_distribution_name=False)[0]

        if distro.lower() == "suse":
            return SuseHandler(opts)
        elif distro.lower() == "centos":
            return CentosHandler(opts)
        elif distro.lower() in ("debian", "ubuntu"):
            return AptgetHandler(opts)
        else:
            raise RuntimeError(
                "This install script does not support your platform: {}\n".format(platform.linux_distribution()[0]) +
                "Supported platforms are: {}".format(supported_dists)
            )

    def add_repos(self):
        raise NotImplementedError()

    def install_icsw(self):
        raise NotImplementedError()

    def process_command(self, cmd):
        if self.opts.show_commands:
            print(" ".join(cmd))
        else:
            print("Running:", " ".join(cmd))
            return subprocess.call(cmd)


class SuseHandler(OSHandler):
    # version must be like "13.1"
    CLUSTER_DEVEL_URL = "http://{user}:{password}@www.initat.org/cluster/RPMs/suse_{version}/cluster-devel"
    EXTRA_URL = "http://{user}:{password}@www.initat.org/cluster/RPMs/suse_{version}/extra"

    def add_repos(self):
        suse_version = platform.linux_distribution()[1]
        expansions = {
            'user': self.opts.user,
            'password': self.opts.password,
            'version': suse_version,
        }
        repos = (
            ("initat_cluster_devel", self.__class__.CLUSTER_DEVEL_URL.format(**expansions)),
            ("initat_extra", self.__class__.EXTRA_URL.format(**expansions)),
        )

        for repo_name, repo_url in repos:
            repo_list = subprocess.check_output(("zypper", "repos", "--uri"))
            if repo_url not in str(repo_list):
                command = ("zypper", "addrepo", repo_url, repo_name)
                self.process_command(command)
            else:
                log.debug("Repo {} already installed".format(repo_name))

    def install_icsw(self):
        commands = [
            ("zypper", "refresh"),
            ("zypper", "install", "icsw-server"),
        ]

        for cmd in commands:
            self.process_command(cmd)


class CentosHandler(OSHandler):
    def add_repos(self):
        raise NotImplementedError()

    def install_icsw(self):
        raise NotImplementedError()


class AptgetHandler(OSHandler):
    def add_repos(self):
        distro = platform.linux_distribution()[0].lower()

        if distro == "ubuntu":
            # we only support 12.04 explicitly as of now
            repos = (
                (
                    "initat_cluster_devel.list",
                    "deb http://www.initat.org/cluster/DEBs/ubuntu_12.04/cluster-devel precise main\n",
                ),
                (
                    "initat_extra.list",
                    "deb http://www.initat.org/cluster/DEBs/ubuntu_12.04/extra precise main\n"
                )
            )
        elif distro == "debian":
            debian_version = platform.linux_distribution()[1]

            if debian_version.startswith("6"):
                debian_release = "squeeze"
            elif debian_version.startswith("7"):
                debian_release = "wheezy"
            else:
                raise RuntimeError("Unsupported debian version: {}.\n".format(platform.linux_distribution()) +
                                   "Currently squeeze and wheezy are supporeted.")

            repos = (
                (
                    "initat_cluster_devel.list",
                    "deb http://www.initat.org/cluster/DEBs/debian_{rel}/cluster-devel {rel} main\n".format(
                        rel=debian_release)
                ),
                (
                    "initat_extra.list",
                    "deb http://www.initat.org/cluster/DEBs/debian_{rel}/extra {rel} main\n".format(rel=debian_release)
                )
            )
        else:
            raise RuntimeError("Unsupported debian platform: {}.\n".format(platform.linux_distribution()))

        for repo_file_name, file_content in repos:
            full_repo_file_path = os.path.join("/etc/apt/sources.list.d", repo_file_name)
            if not os.path.exists(full_repo_file_path):
                with open(full_repo_file_path, 'w') as repo_file:
                    repo_file.write(file_content)
            else:
                log.debug("file {} already exists.".format(full_repo_file_path))

    def install_icsw(self):
        self.process_command(("apt-get", "update"))
        self.process_command(("apt-get", "install", "icsw-server"))


def parse_args():
    parser = argparse.ArgumentParser(prog="install_icsw.py")
    parser.add_argument("-s", "--show-commands", dest="show_commands", action="store_true",
                        help="only show commands without actually executing them")

    parser.add_argument("-u", "--user", dest='user', required=True, help="your icsw user name")
    parser.add_argument("-p", "--password", dest='password', required=True, help="your icsw password")
    parser.add_argument("-cn", "--cluster-name", dest='cluster_name', required=True,
                        help="cluster name as provided by init.at")
    parser.add_argument("-ci", "--cluster-id", dest='cluster_id', required=True,
                        help="your local autogenerated cluster id")
    return parser.parse_args()


def main():

    logging.basicConfig(level=logging.DEBUG)

    opts = parse_args()

    if not opts.show_commands:
        answer = input("This script will add repositories and install packages using your package management. " +
                       "Continue? (y/n) ")
        if answer.lower() != "y":
            print("Exiting.")
            sys.exit(0)

    if opts.show_commands:
        print("The following commands need to be executed:")

    local_os = OSHandler.get_local_os(opts)

    log.debug("Adding repos")
    local_os.add_repos()

    log.debug("Installing packages")
    local_os.install_icsw()

    log.debug("Installing license file")
    local_os.process_command(
        (
            "icsw",
            "license",
            "--user", opts.user,
            "--password", opts.password,
            "--cluster-name", opts.cluster_name,
            "--cluster-id", opts.cluster_id
        )
    )


if __name__ == "__main__":
    main()

