#!/usr/bin/python

#      Copyright 2015, Schuberg Philis BV
#
#      Licensed to the Apache Software Foundation (ASF) under one
#      or more contributor license agreements.  See the NOTICE file
#      distributed with this work for additional information
#      regarding copyright ownership.  The ASF licenses this file
#      to you under the Apache License, Version 2.0 (the
#      "License"); you may not use this file except in compliance
#      with the License.  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#      Unless required by applicable law or agreed to in writing,
#      software distributed under the License is distributed on an
#      "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
#      KIND, either express or implied.  See the License for the
#      specific language governing permissions and limitations
#      under the License.

# We depend on these
import socket
import sys
import time
import os

# Fabric
from fabric.api import *
from fabric import api as fab
from fabric import *

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
        print "Note: Waiting for " + host.name + " to go offline"
        while os.system("ping -c 1 " + host.ipaddress + " 2>&1 >/dev/null") == 0:
            # Progress indication
            sys.stdout.write(".")
            sys.stdout.flush()
            time.sleep(5)
        # Remove progress indication
        sys.stdout.write("\033[F")
        print "Note: Host " + host.name + " is now offline!                           "

    # Execute script on hypervisor
    def exec_script_on_hypervisor(self, host, script):
        script = script.split('/')[-1]
        print "Note: Executing script '%s' on host %s.." % (script, host.name)
        try:
            with settings(show('output'), host_string=self.ssh_user + "@" + host.ipaddress):
                return fab.run("bash /tmp/" + script)
        except:
            return False
