import subprocess
import time
import os
import sys
import tempfile
from common import nrpe_encode

if __name__=="__main__":
    tf = tempfile.NamedTemporaryFile()
    tf_txt_name = tf.name + ".txt"

    with subprocess.Popen([".\scripts\python\cpuz_x64.exe", "--txt={}".format(tf.name)], stdout=subprocess.PIPE) as proc:
        output = proc.stdout.read()

    for i in range(30):
        try:
            f = open(tf_txt_name, "rb")
            data = f.read()
            f.close()
            os.remove(tf_txt_name)
            print(nrpe_encode(data))
            sys.exit()
        except IOError as e:
            time.sleep(1)
