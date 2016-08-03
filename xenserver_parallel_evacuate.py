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

# Evacuate a XenServer using multiple threads in parallel
# Remi Bergsma, rbergsma@schubergphilis.com

# We depend on these modules
import sys
import os
import getopt


# Argument handling Class
class handleArguments(object):
    def handleArguments(self,argv):
        self.DEBUG = 0
        self.DRYRUN = 1
        self.threads = 5
        self.skip_checks = False

        # Usage message
        help = "Usage: " + os.path.basename(__file__) + ' --threads [--debug --exec --skip-checks]'

        try:
            opts, args = getopt.getopt(argv,"ht:",["threads=","debug","exec","skip-checks"])
        except getopt.GetoptError:
            print help
            sys.exit(2)
        for opt, arg in opts:
            if opt == '-h':
                print help
                sys.exit()
            elif opt in ("-t","--threads"):
                self.threads = arg
            elif opt in ("--debug"):
                self.DEBUG = 1
            elif opt in ("--exec"):
                self.DRYRUN = 0
            elif opt in ("--skip-checks"):
                self.skip_checks = True

# Class to handle XenServer parallel evactation
class xenserver_parallel_evacuation(object):

    def __init__(self, arg):
        self.DEBUG = arg.DEBUG
        self.DRYRUN = arg.DRYRUN
        self.threads = arg.threads
        self.poolmember = False
        self.vmlist = False
        self.hvlist = False
        self.skip_checks = arg.skip_checks

    # Run local command
    def run_local_command(self, command):
        if self.DEBUG == 1:
            print "Debug: Running command:" + command

        # XenServer 6.2 runs an ancient python 2.4
        # and the subprocess module did not work
        # properly. That's why I used ancient os.*
        p = os.popen(command)
        lines = ""
        while 1:
            line = p.readline()
            if not line: break
            lines += line

        return lines

    # Get overview of free memory on enabled hosts
    def get_hypervisor_free_memory(self):
            return self.run_local_command("for h in $(xe host-list params=name-label \
                                           enabled=true --minimal | tr ',' ' '); \
                                           do echo -n \"$h,\"; \
                                           xe host-compute-free-memory host=$h;done")

    # Get overview of VMs and their memory
    def get_vms_with_memory_from_hypervisor(self, grep_for=None):
        try:
            grep_command = ""
            if grep_for is not None:
                grep_command = "| grep %s" % grep_for
            return self.run_local_command("xe vm-list resident-on=$(xe host-list params=uuid \
                                           name-label=$HOSTNAME --minimal) \
                                           params=name-label,memory-static-max is-control-domain=false |\
                                           tr '\\n' ' ' | sed 's/name-label/\\n/g' | \
                                           awk {'print $4 \",\" $8'} | sed '/^,$/d'" + grep_command)
        except:
            return False

    # Get overview of peer hypervisors and their available memory
    def construct_poolmembers(self):
        self.hvlist = self.get_hypervisor_free_memory()

        # Construct poolmembers
        poolmember = {}
        hvlist_iter = self.hvlist.split('\n')
        for hv in hvlist_iter:
            info = hv.split(',')
            try:
                hv = info[0]
                mem = info[1]
            except:
                continue
            poolmember[hv] = {}
            poolmember[hv]['memory_free'] = int(mem)
            poolmember[hv]['name'] = hv
        return poolmember

    # Get the hypervisor with the most free memory
    def get_hypervisor_with_most_free_memory(self):
        if self.poolmember == False:
            self.poolmember = self.construct_poolmembers()
        return sorted(self.poolmember.items(),key = lambda x :x[1]['memory_free'],reverse = True)[:1][0][1]

    # Generate migration plan
    def generate_migration_plan(self, grep_for=None):
        if self.skip_checks is False:
            # Make sure host is disabled
            if self.is_host_enabled() is not False:
                print "Error: Host should be disabled first."
                return False

            # Make sure pool HA is turned off
            if self.pool_ha_check() is not False:
                print "Error: Pool HA should be disabled first."
                return False

        # Generate migration plan
        migration_cmds = ""
        if self.vmlist == False:
            self.vmlist = self.get_vms_with_memory_from_hypervisor(grep_for)

        vmlist_iter = self.vmlist.split('\n')

        for vm in vmlist_iter:
            info = vm.split(',')
            try:
                vm = info[0]
                mem = int(info[1].strip())
            except:
                continue

            while True:
                to_hv = self.get_hypervisor_with_most_free_memory()

                # If the hv with the most memory cannot host this vm, we're in trouble
                if to_hv['memory_free'] > mem:
                    # update free_mem
                    self.poolmember[to_hv['name']]['memory_free'] -= int(mem)
                    # Prepare migration command
                    migration_cmds += "xe vm-migrate vm=" + vm + " host=" + to_hv['name'] + ";\n"
                    print "OK, found migration destination for " + vm
                    break
                else:
                    # Unable to empty this hv
                    print "Error: not enough memory (need: " + str(mem)  + ") on any hypervisor to migrate vm " + vm + ". This means N+1 rule is not met, please investigate!"
                    return False
        return migration_cmds

    # Execute migration plan
    def execute_migration_plan(self, grep_for=None):
         try:
            migration_cmds = self.generate_migration_plan(grep_for)
            if migration_cmds == False:
                return False
            return self.run_local_command("nohup echo \"" + migration_cmds + "\" | \
                                           xargs -n 1 -P " + str(self.threads) + " -I {} bash -c \{\} 2>&1 >/dev/null &")
         except:
             return False

    # Is host enabled?
    def is_host_enabled(self):
        print "Note: Checking if host is enabled or disabled.."
        try:
            if self.run_local_command("xe host-list params=enabled name-label=$HOSTNAME --minimal").strip() == "true":
                return True
            else:
                return False
        except:
            return "Error"

    # Check the current state of HA
    def pool_ha_check(self):
        try:
           if self.run_local_command("xe pool-list params=ha-enabled | \
                                      awk {'print $5'} | tr -d '\n'") == "true":
               return True
           else:
               return False
        except:
            return "Error"

# Main program
if __name__ == "__main__":
    arg = handleArguments()
    arg.handleArguments(sys.argv[1:])

    # Init our class
    x = xenserver_parallel_evacuation(arg)

    if arg.DRYRUN == 1:
        print "Note: Running in DRY-run mode, not executing. Use --exec to execute."
        print "Note: Calculating migration plan.."
        print "Note: This is the migration plan:"
        print "Instances (threads = %s)" % str(x.threads)
        print x.generate_migration_plan("i-")
        x.threads = 1
        x.vmlist = False
        print "Routers (threads = %s)" % str(x.threads)
        print x.generate_migration_plan("r-")
        sys.exit(0)

    print "Note: Executing migration plan using " + str(x.threads) + " threads.."
    print x.execute_migration_plan("i-")
    x.threads = 1
    x.vmlist = False
    print "Note: Executing migration plan using " + str(x.threads) + " threads.."
    print x.execute_migration_plan()

