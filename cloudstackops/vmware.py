#!/usr/bin/python

from fabric import api as fab
from fabric.api import *

from . import hypervisor

# Set user/passwd for fabric ssh
env.user = 'root'
env.password = 'password'
env.forward_agent = True
env.disable_known_hosts = True
env.parallel = False
env.pool_size = 1
env.keepalive = 1

# Supress Fabric output by default, we will enable when needed
output['debug'] = False
output['running'] = False
output['stdout'] = False
output['stdin'] = False
output['output'] = False
output['warnings'] = False


class vmware(hypervisor.hypervisor):

    def __init__(self, ssh_user='root', threads=5):
        hypervisor.__init__(ssh_user, threads)
        self.ssh_user = ssh_user
        self.threads = threads
        self.mountpoint = None
        self.migration_path = None

    # Execute script on hypervisor
    def exec_script_on_hypervisor(self, host, script):
        script = script.split('/')[-1]
        print("Note: Executing script '%s' on host %s.." % (script, host.name))
        try:
            with settings(show('output'), host_string=self.ssh_user + "@" + host.ipaddress):
                return fab.run("bash /tmp/" + script)
        except:
            return False

    def find_nfs_mountpoint(self, host):
        print("Note: Looking for Datastores on VMware host %s" % host.name)
        if self.mountpoint is not None:
            print("Note: Found " + str(self.mountpoint))
            return self.mountpoint
        try:
            with settings(host_string=self.ssh_user + "@" + host.ipaddress):
                command = "mount | grep sr-mount | grep \"type nfs\" | awk {'print $3'}"
                self.mountpoint = fab.run(command)
                print("Note: Found " + str(self.mountpoint))
                return self.mountpoint
        except:
            return False
