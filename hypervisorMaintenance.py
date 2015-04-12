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

# Script to put a host in maintenance, and if that fails migrate vm's one by one
# so that it will enter maintenance after all
# Remi Bergsma - rbergsma@schubergphilis.com

import time
import sys
import getopt
from cloudstackops import cloudstackops
from cloudstackops import cloudstackopsssh
import os.path
from random import choice
import subprocess
from subprocess import Popen, PIPE
from prettytable import PrettyTable
import re

# Function to handle our arguments


def handleArguments(argv):
    global DEBUG
    DEBUG = 0
    global DRYRUN
    DRYRUN = 1
    global hostname
    hostname = ''
    global configProfileName
    configProfileName = ''
    global cancelmaintenance
    cancelmaintenance = 0
    global force
    force = 0
    global checkBonds
    checkBonds = True

    # Usage message
    help = "Usage: ./" + os.path.basename(__file__) + ' [options] ' + \
        '\n  --config-profile -c <profilename>\tSpecify the CloudMonkey profile name to get the credentials from (or specify in ./config file)' + \
        '\n  --hostname|-n <hostname>\t\tWork with this hypervisor' + \
        '\n  --cancel-maintenance\t\t\tCancel maintenance for this hypervisor' + \
        '\n  --no-bond-check\t\t\tSkip the bond check' + \
        '\n  --force\t\t\t\tForce put in maintenance, even when there is already a hypervisor in maintenance' + \
        '\n  --debug\t\t\t\tEnable debug mode' + \
        '\n  --exec\t\t\t\tExecute for real'

    try:
        opts, args = getopt.getopt(
            argv, "hc:n:", [
                "credentials-file=", "hostname=", "debug", "exec", "cancel-maintenance", "force", "no-bond-check"])
    except getopt.GetoptError as e:
        print "Error: " + str(e)
        print help
        sys.exit(2)
    for opt, arg in opts:
        if opt == '-h':
            print help
            sys.exit()
        elif opt in ("-c", "--config-profile"):
            configProfileName = arg
        elif opt in ("-n", "--hostname"):
            hostname = arg
        elif opt in ("--cancel-maintenance"):
            cancelmaintenance = 1
        elif opt in ("--debug"):
            DEBUG = 1
        elif opt in ("--exec"):
            DRYRUN = 0
        elif opt in ("--force"):
            force = 1
        elif opt in ("--no-bond-check"):
            checkBonds = False

    # Default to cloudmonkey default config file
    if len(configProfileName) == 0:
        configProfileName = "config"

    # We need at least these vars
    if len(hostname) == 0:
        print help
        sys.exit()

# Parse arguments
if __name__ == "__main__":
    handleArguments(sys.argv[1:])

# Init our classes
c = cloudstackops.CloudStackOps(DEBUG, DRYRUN)
ssh = cloudstackopsssh.CloudStackOpsSSH(DEBUG, DRYRUN)
c.ssh = ssh

if DEBUG == 1:
    print "Warning: Debug mode is enabled!"

if DRYRUN == 1:
    print "Warning: dry-run mode is enabled, not running any commands!"

# make credentials file known to our class
c.configProfileName = configProfileName

# Init the CloudStack API
c.initCloudStackAPI()

if DEBUG == 1:
    print "API address: " + c.apiurl
    print "ApiKey: " + c.apikey
    print "SecretKey: " + c.secretkey

# Check cloudstack IDs
if DEBUG == 1:
    print "Note: Checking CloudStack IDs of provided input.."
hostID = c.checkCloudStackName({'csname': hostname, 'csApiCall': 'listHosts'})
if hostID == 1:
    print "Error: Host " + hostname + " could not be found."
    sys.exit(1)

# Get hosts data
hostData = c.getHostData({'hostname': hostname})
for host in hostData:
    if host.name == hostname:
        foundHostData = host

# Get hosts that belong to toCluster
clusterHostsData = c.getAllHostsFromCluster(foundHostData.clusterid)
print "Note: Host '" + hostname + "' belongs to cluster '" + foundHostData.clustername + "'"

if foundHostData.hypervisor != "XenServer":
    print "Error: This is only tested for XenServer at the moment!"
    sys.exit(1)

# Test SSH connection
retcode, output = ssh.testSSHConnection(foundHostData.ipaddress)
if retcode != 0:
    sys.exit(1)

# Poolmaster
retcode, poolmaster = ssh.getPoolmaster(foundHostData.ipaddress)
print "Note: Poolmaster is: '" + poolmaster + "'"
print "Note: Looking for other hosts in this cluster and checking their health.."

# Print overview
c.printHypervisors(foundHostData.clusterid, poolmaster, checkBonds)

# Look for hosts without XenTools
retcode, output = ssh.fakePVTools(foundHostData.ipaddress)
if retcode != 0:
    print "Error: something went wrong. Got return code " + str(retcode)
else:
    print "Note: Command executed OK."

# Cancel maintenance
if cancelmaintenance == 1 and DRYRUN == 0:
    print "Note: You want to cancel maintenance for host '" + hostname + "'"
    # Does it make sense?
    if foundHostData.resourcestate != "Maintenance" and foundHostData.resourcestate != "PrepareForMaintenance":
        print "Error: Host '" + hostname + "' is not in maintenance, so can not cancel. Halting."
        sys.exit(1)
    # Cancel maintenance
    cancelresult = c.cancelHostMaintenance(hostID)
    if cancelresult is None or cancelresult == 1:
        print "Error: Cancel maintenance failed. Please investigate manually. Halting."
    # Check result
    while True:
        hostData = c.getHostData({'hostname': hostname})
        for host in hostData:
            if host.name == hostname:
                foundHostData = host

        if foundHostData.resourcestate != "Enabled":
            print "Note: Resource state currently is '" + foundHostData.resourcestate + "', waiting some more.."
            time.sleep(5)
        else:
            print "Note: Resource state currently is '" + foundHostData.resourcestate + "', returning"
            break
    print "Note: Cancel maintenance succeeded for host '" + hostname + "'"
    # Print overview
    c.printHypervisors(foundHostData.clusterid, poolmaster, checkBonds)
    print "Note: We're done!"
    sys.exit(0)
elif cancelmaintenance == 1 and DRYRUN == 1:
    print "Note: Would have cancelled maintenance for host '" + hostname + "'."
    sys.exit(0)
elif DRYRUN == 1:
    print "Note: Would have enabled maintenance for host '" + hostname + "'."

# Check if we are safe to put a hypervisor in Maintenance
safe = c.safeToPutInMaintenance(foundHostData.clusterid)
if safe == False and force == 0:
    print "Error: All hosts should be in resouce state 'Enabled' before putting a host to maintenance. Use --force to to ignore WARNING states. Halting."
    sys.exit(1)
elif safe == False and force == 1:
    print "Warning: To be safe, all hosts should be in resouce state 'Enabled' before putting a host to maintenance"
    print "Warning: You used --force to to ignore WARNING states. Assuming you know what you are doing.."
else:
    print "Note: All resource states are 'Enabled', we can safely put one to maintenance"

if DEBUG == 1:
    print "Debug: Host to put in maintenance: " + hostID

# Migrate all vm's and empty hypervisor
c.emptyHypervisor(hostID)

# Put host in CloudStack Maintenance
maintenanceresult = c.startMaintenance(hostID, hostname)
if maintenanceresult:
    # Print overview
    c.printHypervisors(foundHostData.clusterid, poolmaster, checkBonds)
    print "Note: We're done!"
    sys.exit(0)
elif DRYRUN == 0:
    print "Error: Could not enable Maintenance for host '" + hostname + "'. Please investigate manually. Halting."
elif DRYRUN == 1:
    print "Note: We're done!"

if DRYRUN == 0:
    # Print overview
    c.printHypervisors(foundHostData.clusterid, poolmaster, checkBonds)
