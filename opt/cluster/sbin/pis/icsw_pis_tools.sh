#!/bin/bash
# Copyright (C) 2013-2016 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
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

ICSW_BASE=/opt/cluster
ICSW_BIN=${ICSW_BASE}/bin
ICSW_SBIN=${ICSW_BASE}/sbin
ICSW_SGE=${ICSW_BASE}/sge
ICSW_PIS=${ICSW_SBIN}/pis
ICSW_ETC=${ICSW_BASE}/etc
ICSW_SHARE=${ICSW_BASE}/share
ICSW_SYSCONF=${SYSCONF}/cluster
ICSW_TFTP=${ICSW_BASE}/system/tftpboot
ICSW_MOTHER=${ICSW_SHARE}/mother
PREFIX_INIT=/opt/python-init/lib/python2.7/site-packages
DJANGO_PY=${PREFIX_INIT}/django/

MANAGE=${PREFIX_INIT}/initat/cluster/manage.py

USRSBIN=/usr/sbin
USRBIN=/usr/bin
INIT=/etc/init.d

BOLD="\033[1m"
RED="\033[31m"
GREEN="\033[32m"
YELLOW="\033[33m"
OFF="\033[m"

function icsw_cleanup() {
    rm -rf /usr/local/sbin/check_scripts.py*
    rm -rf ${ICSW_SBIN}/modules/*.pyo
    rm -rf /opt/python-init/lib/python2.7/site-packages/initat/tools/logging_tools
    rm -f /opt/python-init/lib/python2.7/site-packages/initat/icsw/setup/*.py{c,o}
    rm -f /opt/python-init/lib/python2.7/site-packages/initat/tools/logging_tools.py{c,o}
    # remove cached urls.py files
    rm -f ${PREFIX_INIT}/initat/cluster/urls.py{c,o}
    rm -rf ${PREFIX_INIT}/initat/core

    # delete modules install via npm
    rm -rf ${ICSW_BASE}/lib/node_modules/yuglify/node_modules
    # delete old modules
    rm -rf ${PREFIX_INIT}/initat/cluster/rms
    # old django py(o|c) files
    rm -f ${DJANGO_PY}/utils/*.py{c,o}
}

function is_chroot() {
    # returns 0 if running chrooted
    if [ -d /proc -a -d /proc/1 ] ; then
        p1_inode=$(ls --color=no -di /proc/1/root/ | tr -s " " | cut -d " " -f 1)
        root_inode=$(ls --color=no -di / | tr -s " " | cut -d " " -f 1)
        if [ "${p1_inode}" = "${root_inode}" ] ; then
            return 1
        else
            return 0
        fi
    else
        return 0
    fi
}

function restart_software() {
    mode=$1
    if is_chroot ; then
        echo "running chrooted, skipping restart"
    else
        [ -x /bin/systemctl ] && /bin/systemctl daemon-reload

        # logging-server
        echo -e "\n${GREEN}restarting logging-server${OFF}\n"
        ${ICSW_SBIN}/icsw --logger stdout --logall service restart logging-server

        if [ ! -f ${ICSW_PIS}/icsw_server_post_install.sh -o "${mode}" = "server" ] ; then
            # start / stop to force restart of all services
            if [ ! -d /var/lib/meta-server/.srvstate ] ; then
                NUM_RS=2
            else
                NUM_RS=1
            fi

            echo -e "\n${GREEN}restarting all ICSW related services (${RESTART_CAUSE}) (LC: ${NUM_RS})${OFF}\n"

            for idx in $(seq ${NUM_RS} ) ; do
                echo -e "${GREEN}(${idx}/${NUM_RS}) restarting all ICSW related services (mode=${mode})${OFF}\n"
                ${ICSW_SBIN}/icsw --logall service stop meta-server
                ${ICSW_SBIN}/icsw --logall service start meta-server
            done
        fi
    fi
}
