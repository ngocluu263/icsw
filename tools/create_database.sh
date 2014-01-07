#!/bin/bash

C_DIR="/opt/python-init/lib/python/site-packages/initat/cluster/"

if [ "${UID:-X}" = "0" ] ; then 
    if [ "${1:-X}" = "--no-initial-data" ] ; then
        ID_FLAGS="--no-initial-data"
    else
        ID_FLAGS=""
    fi
    MIG_DIR="${C_DIR}/backbone/migrations/"
    echo "migration_dir is ${MIG_DIR}, ID_FLAGS is '${ID_FLAGS}'"
    if [ ! -d ${MIG_DIR} ] ; then
        export NO_AUTO_ADD_APPLICATIONS=1
        export INITIAL_MIGRATION_RUN=1
        ${C_DIR}/manage.py syncdb --noinput ${ID_FLAGS}
        unset NO_AUTO_ADD_APPLICATIONS
        unset INITIAL_MIGRATION_RUN
        ${C_DIR}/manage.py schemamigration django.contrib.auth --initial
        ${C_DIR}/manage.py schemamigration backbone --initial
        ${C_DIR}/manage.py schemamigration reversion --initial
        # not working with south, strange ..., reenabled 
	${C_DIR}/manage.py schemamigration static_precompiler --initial
        ${C_DIR}/manage.py migrate auth
        ${C_DIR}/manage.py migrate backbone --no-initial-data
        ${C_DIR}/manage.py migrate reversion
	# see above
        ${C_DIR}/manage.py migrate static_precompiler
        ${C_DIR}/manage.py syncdb --noinput ${ID_FLAGS}
        ${C_DIR}/manage.py migrate ${ID_FLAGS}
        if [ -z "$1" ]; then
            echo ""
            echo "creating superuser"
            echo ""
            ${C_DIR}/manage.py createsuperuser
        fi
    else
        echo "migration directory ${MIG_DIR} present, refuse to operate"
    fi
else
    echo "need to be root to create database"
fi  
