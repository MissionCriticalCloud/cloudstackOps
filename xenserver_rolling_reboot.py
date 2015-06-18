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

# Patch XenServers that are registered in CloudStack
# Remi Bergsma, rbergsma@schubergphilis.com

# We depend on these modules
import sys
import socket
import time
import os
import getopt
from cloudstackops import cloudstackops
from cloudstackops import xenserver
# Fabric
from fabric.api import *
from fabric import api as fab
from fabric import *
from fabric.network import disconnect_all


# Handle arguments passed
def handleArguments(argv):
    global DEBUG
    DEBUG = 0
    global DRYRUN
    DRYRUN = 1
    global PREPARE
    PREPARE = 0
    global clustername
    clustername = ''
    global configProfileName
    configProfileName = ''
    global ignoreHostList
    ignoreHostList = ""
    global ignoreHosts
    ignoreHosts = ''
    global threads
    threads = 5

    # Usage message
    help = "Usage: ./" + os.path.basename(__file__) + ' [options]' + \
        '\n  --config-profile -c <profilename>\t\tSpecify the CloudMonkey profile name to get the credentials from (or specify in ./config file)' + \
        '\n  --clustername -n <clustername> \t\tName of the cluster to work with' + \
        '\n  --ignore-hosts <list>\t\t\t\tSkip work on the specified hosts (for example if you need to resume): Example: --ignore-hosts="host1, host2" ' + \
        '\n  --threads <nr>\t\t\t\tUse this number or concurrent migration threads" ' + \
        '\n  --debug\t\t\t\t\tEnable debug mode' + \
        '\n  --exec\t\t\t\t\tExecute for real' + \
        '\n  --prepare\t\t\t\t\tExecute some prepare commands'

    try:
        opts, args = getopt.getopt(
            argv, "hc:n:t:p", [
                "credentials-file=", "clustername=", "ignore-hosts=", "threads=", "debug", "exec", "prepare"])
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
        elif opt in ("-n", "--clustername"):
            clustername = arg
        elif opt in ("-t", "--threads"):
            threads = arg
        elif opt in ("--ignore-hosts"):
            ignoreHostList = arg
        elif opt in ("--debug"):
            DEBUG = 1
        elif opt in ("--exec"):
            DRYRUN = 0
        elif opt in ("--prepare"):
            PREPARE = 1

    # Default to cloudmonkey default config file
    if len(configProfileName) == 0:
        configProfileName = "config"

    # Ignore host list
    if len(ignoreHostList) > 0:
        ignoreHosts = ignoreHostList.split(", ")
    else:
        ignoreHosts = []

    # We need at least a cluster name
    if len(clustername) == 0:
        print help
        sys.exit(1)


if __name__ == '__main__':
    handleArguments(sys.argv[1:])

# Init CloudStack class
c = cloudstackops.CloudStackOps(DEBUG, DRYRUN)

# Init XenServer class
x = xenserver.xenserver('root', threads)
c.xenserver = x

# make credentials file known to our class
c.configProfileName = configProfileName

# Init the CloudStack API
c.initCloudStackAPI()

if DEBUG == 1:
    print "API address: " + c.apiurl
    print "ApiKey: " + c.apikey
    print "SecretKey: " + c.secretkey

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

# Check cloudstack IDs
if DEBUG == 1:
    print "Note: Checking CloudStack IDs of provided input.."
clusterID = c.checkCloudStackName(
    {'csname': clustername, 'csApiCall': 'listClusters'})
if clusterID == 1:
    print "Error: Could not find cluster '" + clustername + "'."
    disconnect_all()
    sys.exit(1)

# Get cluster hosts
cluster_hosts = c.getAllHostsFromCluster(clusterID)
first_host = cluster_hosts[0]

# Print cluster info
print "Note: Some info about cluster '" + clustername + "':"
c.printCluster(clusterID)

# Hosts to ignore
if len(ignoreHosts) > 0:
    print "Note: Ignoring these hosts: " + str(ignoreHosts)

# Get poolmaster
poolmaster_name = x.get_poolmaster(first_host)
if not poolmaster_name:
    print "Error: unable to figure out the poolmaster while talking to " + first_hostname
    disconnect_all()
    sys.exit(1)
print "Note: The poolmaster of cluster " + clustername + " is " + poolmaster_name

# Put the scripts we need
for h in cluster_hosts:
    x.put_scripts(h)
    if DRYRUN == 0 or PREPARE == 1:
        x.fake_pv_tools(h)
    if h.name == poolmaster_name:
        poolmaster = h

# Eject CDs
if DRYRUN == 0 or PREPARE == 1:
    eject_result = x.eject_cds(poolmaster)
    if eject_result == False:
        print "Warning: Ejecting CDs failed. Continuing anyway."

# Print overview
checkBonds = True
c.printHypervisors(clusterID, poolmaster.name, checkBonds)

if DRYRUN == 1:
    print
    print "Warning: We are running in DRYRUN mode."
    print
    print "This script will: "
    print "  - Set cluster " + clustername + " to unmanage in CloudStack"
    print "  - Turn OFF XenServer poolHA for " + clustername
    print "  - For any hypervisor it will do this (poolmaster " + poolmaster.name + " first):"
    print "      - put it to Disabled aka Maintenance in XenServer"
    print "      - live migrate all VMs off of it using XenServer evacuate command"
    print "      - when empty, it will reboot the hypervisor"
    print "      - will wait for it to come back online (checks SSH connection)"
    print "      - set the hypervisor to Enabled in XenServer"
    print "      - continues to the next hypervisor"
    print "  - When the rebooting is done, it enables XenServer poolHA again for " + clustername
    print "  - Finally, it sets the " + clustername + " to Managed again in CloudStack"
    print "  - CloudStack will update its admin according to the new situation"
    print "Then the reboot cyclus for " + clustername + " is done!"
    print
    print "To kick it off, run with the --exec flag."
    print
    disconnect_all()
    sys.exit(1)

# Start time
print "Note: Starting @ " + time.strftime("%Y-%m-%d %H:%M")

# Set to unmanage in CloudStack
print "Note: Setting cluster " + clustername + " to Unmanaged in CloudStack"
clusterUpdateReturn = c.updateCluster(
    {'clusterid': clusterID, 'managedstate': 'Unmanaged'})

if clusterUpdateReturn == 1 or clusterUpdateReturn is None:
    print "Error: Unmanaging cluster " + clustername + " failed. Halting."
    disconnect_all()
    sys.exit(1)

# Check HA of Cluster
pool_ha = x.pool_ha_check(poolmaster)
if pool_ha == "Error":
    print "Error: Unable to get the current HA state of cluster " + clustername
    disconnect_all()
    sys.ext(1)
print "Note: The state of HA on cluster " + clustername + " is " + str(pool_ha)

# Disable HA
if pool_ha:
    pool_ha_result = x.pool_ha_disable(poolmaster)
    if pool_ha_result == "Error":
        print "Error: Unable to set the HA state to Disabled for cluster " + clustername
        disconnect_all()
        sys.exit(1)
    pool_ha = x.pool_ha_check(poolmaster)
    print "Note: The state of HA on cluster " + clustername + " is " + str(pool_ha)

# Do the poolmaster first
if poolmaster.name not in ignoreHosts:
    vm_count = x.host_get_vms(poolmaster)
    if vm_count:
        print "Note: " + poolmaster.name + " (poolmaster) has " + vm_count + " VMs running."
        reboot_result = x.host_reboot(poolmaster)
        if reboot_result is False:
            print "Error: Stopping sequence, as a reboot failed. Please investigate."
            x.roll_back(poolmaster)
            disconnect_all()
            sys.exit(1)
    else:
        print "Error: Unable to contact the poolmaster " + poolmaster.name
        disconnect_all()
        sys.exit(1)
else:
        print "Warning: Skipping " + poolmaster.name + " due to --ignore-hosts setting"

# Print overview
checkBonds = True
c.printHypervisors(clusterID, poolmaster.name, checkBonds)

# Then the other hypervisors, one-by-one
for h in cluster_hosts:
    if h.name in ignoreHosts:
        print "Warning: Skipping " + h.name + " due to --ignore-hosts setting"
        continue

    if h.name == poolmaster.name:
        print "Note: Skipping poolmaster"
        continue
    vm_count = x.host_get_vms(h)
    if vm_count:
        print "Note: " + h.name + " has " + vm_count + " VMs running."
        reboot_result = x.host_reboot(h)
        if reboot_result is False:
            print "Error: Stopping sequence, as a reboot failed. Please investigate."
            x.roll_back(h)
            disconnect_all()
            sys.exit(1)
    else:
        print "Error: Unable to get vm_count from host " + h.name
        x.roll_back(h)
        disconnect_all()
        sys.exit(1)
    print "Note: We completed host " + h.name + " successfully."

    # Print overview
    checkBonds = True
    c.printHypervisors(clusterID, poolmaster.name, checkBonds)

# Enable HA
pool_ha_result = x.pool_ha_enable(poolmaster)
if pool_ha_result is False:
    print "Warning: Unable to set the HA state to Enable for cluster " + clustername

# Check HA
pool_ha = x.pool_ha_check(poolmaster)
if pool_ha == "Error":
    print "Error: Unable to get the current HA state of cluster " + clustername
    disconnect_all()
    sys.ext(1)
print "Note: The state of HA on cluster " + clustername + " is " + str(pool_ha)

# Set to manage in CloudStack
clusterUpdateReturn = c.updateCluster(
    {'clusterid': clusterID, 'managedstate': 'Managed'})

if clusterUpdateReturn == 1 or clusterUpdateReturn is None:
    print "Error: Managing cluster " + clustername + " failed. Please check manually."
    disconnect_all()
    sys.exit(1)

# Print cluster info
print "Note: Some info about cluster '" + clustername + "':"
c.printCluster(clusterID)

# Disconnect
disconnect_all()

# Done
print "Note: We're done with cluster " + clustername

# End time
print "Note: Finished @ " + time.strftime("%Y-%m-%d %H:%M")
