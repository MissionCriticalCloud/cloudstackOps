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

# Class to talk to hypervisors using SSH
# Remi Bergsma - rbergsma@schubergphilis.com

# Import the class we depend on
from cloudstackopsbase import *
# Import our dependencies
import subprocess
from subprocess import Popen, PIPE


class CloudStackOpsSSH(CloudStackOpsBase):

    # Run SSH remoteCmd
    def runSSHCommand(self, hostname, remoteCmd):
        if self.DEBUG == 1:
            print "Debug: Running SSH command on " + hostname + " :" + remoteCmd
        p = subprocess.Popen(['ssh',
                              '-oStrictHostKeyChecking=no',
                              '-oUserKnownHostsFile=/dev/null',
                              '-q',
                              'root@' + hostname,
                              remoteCmd],
                             stdout=subprocess.PIPE)
        output = ""
        try:
            output = p.stdout.read().strip()
            while p.poll() is None:
                time.sleep(0.5)
        except:
            pass
        retcode = self.__parseReturnCode(p.returncode, hostname)
        return retcode, output

    def __parseReturnCode(self, retcode, hostname):
        if retcode != 0:
            print "Error: SSH connection to '" + hostname + "' returned code " + str(retcode)
            print "Note: Please make sure 'ssh root@" + hostname + "' works key-based and try again."
        elif self.DEBUG == 1:
            print "Note: SSH remoteCmd executed OK."
        return retcode

    # Test SSH connection
    def testSSHConnection(self, hostname):
        remoteCmd = 'echo Note: Testing SSH to $HOSTNAME'
        return self.runSSHCommand(hostname, remoteCmd)

    # Fake PV tools
    def fakePVTools(self, hostname):
        print "Note: We're faking the presence of PV tools of all vm's reporting no tools on hypervisor '" + hostname + "'. Migration will not work otherwise."
        remoteCmd = "xe vm-list PV-drivers-up-to-date='<not in database>' is-control-domain=false resident-on=$(xe host-list name-label=$HOSTNAME --minimal) params=uuid --minimal |tr ', ' '\n'| grep \"-\" | awk {'print \"/opt/tools/sysadmin/bin/fakepv.sh \" $1'} | sh"
        return self.runSSHCommand(hostname, remoteCmd)

    # Look for poolmaster
    def getPoolmaster(self, hostname):
        remoteCmd = "for i in $(xe pool-list --minimal | sed 's/\, /\\n/g'); do poolMaster=$(xe pool-list uuid=$i --minimal params=master | xargs -i xe host-list uuid={} params=name-label --minimal); echo $poolMaster; done"
        return self.runSSHCommand(hostname, remoteCmd)

    # Get bond status
    def getBondStatus(self, hostname):
        remoteCmd = "/opt/tools/nrpe/bin/check_xenbond.py | awk {'print $1'} | tr -d \":\""
        return self.runSSHCommand(hostname, remoteCmd)

    # Get heartbeat status
    def getHeartbeatStatus(self, hostname):
        remoteCmd = "/opt/tools/nrpe/bin/check_heartbeat.sh | awk {'print $2'}"
        return self.runSSHCommand(hostname, remoteCmd)

    # Get xapi vm count
    def getXapiVmCount(self, hostname):
        remoteCmd = "xe vm-list resident-on=$(xe host-list params=uuid \
                     name-label=$HOSTNAME --minimal) \
                     params=name-label,memory-static-max is-control-domain=false | \
                     tr '\\n' ' ' | sed 's/name-label/\\n/g' | \
                     awk {'print $4 \",\" $8'} | sed '/^,$/d'| wc -l"
        return self.runSSHCommand(hostname, remoteCmd)

    # Migrate vm via xapi
    def migrateVirtualMachineViaXapi(self, args):

        # Handle arguments
        hostname = (args['hostname']) if 'hostname' in args else ''
        desthostname = (args['desthostname']) if 'desthostname' in args else ''
        vmname = (args['vmname']) if 'vmname' in args else ''

        if len(vmname) > 0 and len(desthostname) > 0 and len(hostname):
            remoteCmd = "xe vm-migrate vm=" + vmname + " host=" + desthostname
            if self.DEBUG == 1:
                print "Debug: Running SSH command on " + hostname + " :" + remoteCmd
            p = subprocess.Popen(['ssh',
                                  '-oStrictHostKeyChecking=no',
                                  '-oUserKnownHostsFile=/dev/null',
                                  '-q',
                                  'root@' + hostname,
                                  remoteCmd],
                                 stdout=subprocess.PIPE)
            output = ""
            try:
                output = p.stdout.read().strip()
                while p.poll() is None:
                    time.sleep(0.5)
            except:
                pass
            retcode = p.returncode
            if retcode != 0:
                print "Error: something went wrong on host " + hostname + ". Got return code " + str(retcode)
            elif self.DEBUG == 1:
                print "Note: Output: " + output
            return retcode, output
        return false
