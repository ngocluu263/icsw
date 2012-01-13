#!/bin/bash

. /etc/sysconfig/cluster/mysql.cf

echo "CREATE DATABASE IF NOT EXISTS $MYSQL_DATABASE ; CREATE DATABASE IF NOT EXISTS $NAGIOS_DATABASE ; CREATE USER '$MYSQL_USER'@'$MYSQL_HOST' IDENTIFIED BY '$MYSQL_PASSWD' ; GRANT ALL ON $MYSQL_DATABASE.* TO '$MYSQL_USER'@'$MYSQL_HOST' ; GRANT ALL ON cdtemp.* TO '$MYSQL_USER'@'$MYSQL_HOST' ; GRANT ALL ON ngtemp.* TO '$MYSQL_USER'@'$MYSQL_HOST' ; GRANT ALL ON $NAGIOS_DATABASE.* TO '$MYSQL_USER'@'$MYSQL_HOST' ; FLUSH PRIVILEGES" | mysql $*


