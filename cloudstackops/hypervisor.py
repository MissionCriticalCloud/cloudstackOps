#!/usr/bin/python

import os
import sys
import time

from fabric import api as fab
from fabric.api import *

# Set user/passwd for fabric ssh
env.user = 'root'
env.password = 'password'
env.forward_agent = True
env.disable_known_hosts = True
env.parallel = False
env.pool_size = 1

# Supress Fabric output by default, we will enable when needed
output['debug'] = False
output['running'] = False
output['stdout'] = False
output['stdin'] = False
output['output'] = False
output['warnings'] = False


# Class to talk to hypervisors
class hypervisor(object):

    def __init__(self, ssh_user='root', threads=5):
        self.ssh_user = ssh_user
        self.threads = threads
        self.DEBUG = 0

    # Check if we are really offline
    def check_offline(self, host):
        print("Note: Waiting for " + host.name + " to go offline")
        while os.system("ping -c 1 " + host.ipaddress + " 2>&1 >/dev/null") == 0:
            # Progress indication
            sys.stdout.write(".")
            sys.stdout.flush()
            time.sleep(5)
        # Remove progress indication
        sys.stdout.write("\033[F")
        print("Note: Host " + host.name + " is now offline!                           ")
        time.sleep(120)

    # Execute script on hypervisor
    def exec_script_on_hypervisor(self, host, script):
        script = script.split('/')[-1]
        print("Note: Executing script '%s' on host %s.." % (script, host.name))
        try:
            with settings(show('output'), host_string=self.ssh_user + "@" + host.ipaddress):
                return fab.run("bash /tmp/" + script)
        except:
            return False
