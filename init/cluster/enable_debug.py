#!/usr/bin/python-init -Otu

import sys
import os

cur_cwd = os.getcwd()
if "/clustersoftware/build-extern/" in cur_cwd:
    while True:
        cwd_path, cwd_rest = os.path.split(cur_cwd)
        cur_cwd = cwd_path
        if cur_cwd.endswith("cluster-backbone-sql"):
            break
    if cur_cwd not in sys.path:
        sys.path.insert(0, cur_cwd)

import init.cluster
# reload magic
reload(init)
reload(init.cluster)
