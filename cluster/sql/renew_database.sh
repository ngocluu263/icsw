#!/bin/bash
#
# Copyright (C) 2001,2002,2003,2004,2005,2006,2007 Andreas Lang, init.at
#
# Send feedback to: <lang@init.at>
#
# This file is part of cluster-backbone
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

cdir=/usr/local/cluster

file_list=$(cat /etc/sysconfig/cluster/db_access  | grep "=" | cut -d "=" -f 2 | grep "^/" | tr ";" "\n")

for conf in $file_list ; do
    [ -r $conf ] && break
done

[ -r $conf ] || { echo "No readable mysql-configfiles found, exiting..." ; exit -1 ; }

source $conf

echo "Deleting old tables and creating cluster database ..."
mysql -u ${MYSQL_USER} -h ${MYSQL_HOST} -p${MYSQL_PASSWD} < ${cdir}/sql/recreate.sql

echo "Creating device and system tables ..."
mysql -u ${MYSQL_USER} -h ${MYSQL_HOST} -p${MYSQL_PASSWD} ${MYSQL_DATABASE} < ${cdir}/sql/create_all_tables.sql

echo "Creating nagios tables and structures ..."
mysql -u ${MYSQL_USER} -h ${MYSQL_HOST} -p${MYSQL_PASSWD} ${MYSQL_DATABASE} < ${cdir}/sql/create_nagios_tables.sql

echo "Creating user and group tables ..."
mysql -u ${MYSQL_USER} -h ${MYSQL_HOST} -p${MYSQL_PASSWD} ${MYSQL_DATABASE} < ${cdir}/sql/create_user_tables.sql

echo "Creating rrd tables ..."
mysql -u ${MYSQL_USER} -h ${MYSQL_HOST} -p${MYSQL_PASSWD} ${MYSQL_DATABASE} < ${cdir}/sql/create_rrd_tables.sql

echo "Creating package tables ..."
mysql -u ${MYSQL_USER} -h ${MYSQL_HOST} -p${MYSQL_PASSWD} ${MYSQL_DATABASE} < ${cdir}/sql/create_package_tables.sql
echo "Creating RMS tables ..."
mysql -u ${MYSQL_USER} -h ${MYSQL_HOST} -p${MYSQL_PASSWD} ${MYSQL_DATABASE} < ${cdir}/sql/create_rms_tables.sql

echo "Creating external nagios tables ..."
echo "DROP DATABASE IF EXISTS $NAGIOS_DATABASE ; CREATE DATABASE $NAGIOS_DATABASE ; " | mysql -u ${MYSQL_USER} -h ${MYSQL_HOST} -p${MYSQL_PASSWD} 

mysql -u ${MYSQL_USER} -h ${MYSQL_HOST} -p${MYSQL_PASSWD} ${NAGIOS_DATABASE} < ${cdir}/sql/create_ext_nagios_tables.sql

