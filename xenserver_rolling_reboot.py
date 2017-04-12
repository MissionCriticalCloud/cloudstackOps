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
import glob
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
    global halt_hypervisor
    halt_hypervisor = False
    global pre_empty_script
    pre_empty_script = 'xenserver_pre_empty_script.sh'
    global post_empty_script
    post_empty_script = 'xenserver_post_empty_script.sh'
    global patch_list_file
    patch_list_file = 'xenserver_patches_to_install.txt'
    global preserve_downloads
    preserve_downloads = False

    # Usage message
    help = "Usage: ./" + os.path.basename(__file__) + ' [options]' + \
        '\n  --config-profile -c <profilename>\t\tSpecify the CloudMonkey profile name to ' \
        'get the credentials from (or specify in ./config file)' + \
        '\n  --clustername -n <clustername> \t\tName of the cluster to work with' + \
        '\n  --ignore-hosts <list>\t\t\t\tSkip work on the specified hosts (for example if you need to resume): ' \
        'Example: --ignore-hosts="host1, host2" ' + \
        '\n  --threads <nr>\t\t\t\tUse this number or concurrent migration threads ' + \
        '\n  --halt\t\t\t\t\tInstead of the default reboot, halt the hypervisor (useful in case of hardware ' \
        'upgrades) ' + \
        '\n  --pre-empty-script\t\t\t\tBash script to run on hypervisor before starting the live migrations to empty ' \
        'hypervisor (expected in same folder as this script)' + \
        '\n  --post-empty-script\t\t\t\tBash script to run on hypervisor after a hypervisor has no more VMs running' \
        '\n  --patch-list-file\t\t\t\tText file with URLs of patches to download and install. One per line. ' \
        '(expected in same folder as this script)' + \
        '\n  --preserve-downloads\t\t\t\tPreserve downloads instead of wiping them and downloading again.' + \
        '\n  --debug\t\t\t\t\tEnable debug mode' + \
        '\n  --exec\t\t\t\t\tExecute for real' + \
        '\n  --prepare\t\t\t\t\tExecute some prepare commands'

    try:
        opts, args = getopt.getopt(
            argv, "hc:n:t:p", [
                "credentials-file=", "clustername=", "ignore-hosts=", "threads=", "pre-empty-script=",
                "post-empty-script=", "patch-list-file=", "preserve-downloads", "halt", "debug", "exec", "prepare"])
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
        elif opt in ("--halt"):
            halt_hypervisor = True
        elif opt in ("--pre-empty-script"):
            pre_empty_script = arg
        elif opt in ("--post-empty-script"):
            post_empty_script = arg
        elif opt in ("--patch-list-file"):
            patch_list_file = arg
        elif opt in ("--preserve-downloads"):
            preserve_downloads = True
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
        ignoreHosts = ignoreHostList.replace(' ', '').split(",")
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
c.task = "XenServer Rolling Reboot"
c.slack_custom_title = "Hypervisor"
c.slack_custom_value = ""
c.instance_name = "N/A"
c.cluster = clustername

# Init XenServer class
x = xenserver.xenserver('root', threads, pre_empty_script, post_empty_script)
c.xenserver = x

# make credentials file known to our class
c.configProfileName = configProfileName

# Init the CloudStack API
c.initCloudStackAPI()

if DEBUG == 1:
    print "API address: " + c.apiurl
    print "ApiKey: " + c.apikey
    print "SecretKey: " + c.secretkey

to_slack = True
if DRYRUN == 1:
    to_slack = False

# Check cloudstack IDs
if DEBUG == 1:
    print "Note: Checking IDs of provided input.."
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
message = "Some info about cluster '" + clustername + "':"
c.print_message(message=message, message_type="Note", to_slack=False)
c.printCluster(clusterID)

# Hosts to ignore
if len(ignoreHosts) > 0:
    message = "Ignoring these hosts: " + str(ignoreHosts)
    c.print_message(message=message, message_type="Note", to_slack=to_slack)

# Get poolmaster
poolmaster_name = x.get_poolmaster(first_host)
if not poolmaster_name:
    message = "unable to figure out the poolmaster while talking to " + first_host
    c.print_message(message=message, message_type="Error", to_slack=to_slack)
    disconnect_all()
    sys.exit(1)
message = "The poolmaster of cluster " + clustername + " is " + poolmaster_name
c.print_message(message=message, message_type="Note", to_slack=to_slack)
c.slack_custom_value = poolmaster_name

# Put the scripts we need
for h in cluster_hosts:
    x.put_scripts(h)
    if DRYRUN == 0 or PREPARE == 1:
        x.fake_pv_tools(h)
        x.create_vlans(h)
    if h.name == poolmaster_name:
        poolmaster = h

# Eject CDs
if DRYRUN == 0 or PREPARE == 1:
    eject_result = x.eject_cds(poolmaster)
    if eject_result == False:
        message = "Ejecting CDs failed. Continuing anyway."
        c.print_message(message=message, message_type="Warning", to_slack=to_slack)

# Print overview
checkBonds = True
c.printHypervisors(clusterID, poolmaster.name, checkBonds)

if halt_hypervisor:
    message = "Instead of reboot, we will halt the hypervisor. You need to start it yourself for the script to" \
          " continue moving to the next hypervisor."
    c.print_message(message=message, message_type="Warning", to_slack=False)

if DRYRUN == 1:
    print
    print "Warning: We are running in DRYRUN mode."
    print
    print "This script will: "
    print "  - Set cluster " + clustername + " to Unmanage"
    print "  - Turn OFF XenServer poolHA for " + clustername
    print "  - For any hypervisor it will do this (poolmaster " + poolmaster.name + " first):"
    print "      - put it to Disabled aka Maintenance in XenServer"
    print "      - download the patches in file --patch-list-file '" + patch_list_file + "'"
    print "         (preserve downloads is set to " + str(preserve_downloads) + ")"
    print "      - execute the --pre-empty-script script '" + pre_empty_script + "' on the hypervisor"
    print "      - live migrate all VMs off of it using XenServer evacuate command"
    print "      - execute the --post-empty-script script '" + post_empty_script + "' on the hypervisor"
    print "      - when empty, it will reboot the hypervisor (halting is " + str(halt_hypervisor) + ")"
    print "      - will wait for it to come back online (checks SSH connection)"
    print "      - set the hypervisor to Enabled in XenServer"
    print "      - continues to the next hypervisor"
    print "  - When the rebooting is done, it enables XenServer poolHA again for " + clustername
    print "  - Finally, it sets the " + clustername + " to Managed again"
    print "  - Database will be updated according to the new situation"
    print "Then the reboot cyclus for " + clustername + " is done!"
    print
    print "To kick it off, run with the --exec flag."
    print
    disconnect_all()
    sys.exit(1)

# Start time
message = "Starting @ " + time.strftime("%Y-%m-%d %H:%M")
c.print_message(message=message, message_type="Note", to_slack=False)

# Check HA of Cluster
pool_ha = x.pool_ha_check(poolmaster)
if pool_ha == "Error":
    message = "Error: Unable to get the current HA state of cluster " + clustername
    c.print_message(message=message, message_type="Error", to_slack=to_slack)
    disconnect_all()
    sys.ext(1)
message = "The state of HA on cluster " + clustername + " is " + str(pool_ha)
c.print_message(message=message, message_type="Note", to_slack=to_slack)

# Disable HA
if pool_ha:
    pool_ha_result = x.pool_ha_disable(poolmaster)
    if pool_ha_result == "Error":
        message = "Unable to set the HA state to Disabled for cluster " + clustername
        c.print_message(message=message, message_type="Error", to_slack=to_slack)
        disconnect_all()
        sys.exit(1)
    pool_ha = x.pool_ha_check(poolmaster)
    message = "The state of HA on cluster " + clustername + " is " + str(pool_ha)
    c.print_message(message=message, message_type="Note", to_slack=to_slack)

# Do the poolmaster first
if poolmaster.name not in ignoreHosts:

    # BEFORE: Set to Unmanage
    message = "Setting cluster " + clustername + " to Unmanaged"
    c.print_message(message=message, message_type="Note", to_slack=to_slack)
    clusterUpdateReturn = c.updateCluster(
        {'clusterid': clusterID, 'managedstate': 'Unmanaged'})

    if clusterUpdateReturn == 1 or clusterUpdateReturn is None:
        message = "Unmanaging cluster " + clustername + " failed. Halting."
        c.print_message(message=message, message_type="Error", to_slack=to_slack)
        disconnect_all()
        sys.exit(1)

    # Download all XenServer patches
    if not preserve_downloads:
        message = "Deleting previously downloaded patches"
        c.print_message(message=message, message_type="Note", to_slack=False)
        files = glob.glob('xenserver_patches/*.zip')
        for f in files:
            message = "Removing previously downloaded patch " + f
            c.print_message(message=message, message_type="Note", to_slack=False)
            os.remove(f)

    message = "Reading patches list '%s'" % patch_list_file
    c.print_message(message=message, message_type="Note", to_slack=False)
    with open(patch_list_file) as file_pointer:
        patches = file_pointer.read().splitlines()

    for patch_url in patches:
        message = "Processing patch '%s'" % patch_url
        c.print_message(message=message, message_type="Note", to_slack=False)
        x.download_patch(patch_url)

    # Upload the patches to poolmaster, then to XenServer
    x.put_patches_to_poolmaster(poolmaster)
    x.upload_patches_to_xenserver(poolmaster)

    # Migrate all VMs off of pool master
    vm_count = x.host_get_vms(poolmaster)
    if vm_count:
        message = poolmaster.name + " (poolmaster) has " + vm_count + " VMs running. Live migrating VMs to make it empty, then reboot it."
        c.print_message(message=message, message_type="Note", to_slack=to_slack)
        reboot_result = x.host_reboot(poolmaster, halt_hypervisor)
        if reboot_result is False:
            message = "Stopping sequence, as a reboot failed. Please investigate."
            c.print_message(message=message, message_type="Error", to_slack=to_slack)
            x.roll_back(poolmaster)
            disconnect_all()
            sys.exit(1)
    else:
        message = "Unable to contact the poolmaster " + poolmaster.name
        c.print_message(message=message, message_type="Error", to_slack=to_slack)
        disconnect_all()
        sys.exit(1)

    # AFTER: Set to Manage
    message = "Setting cluster " + clustername + " back to Managed"
    c.print_message(message=message, message_type="Note", to_slack=to_slack)
    clusterUpdateReturn = c.updateCluster(
        {'clusterid': clusterID, 'managedstate': 'Managed'})

    if clusterUpdateReturn == 1 or clusterUpdateReturn is None:
        message = "Managing cluster " + clustername + " failed. Please check manually."
        c.print_message(message=message, message_type="Error", to_slack=to_slack)
        disconnect_all()
        sys.exit(1)

    message = "Waiting 60s to allow all hosts connect.."
    c.print_message(message=message, message_type="Note", to_slack=False)
    time.sleep(60)

else:
        message = "Skipping " + poolmaster.name + " due to --ignore-hosts setting"
        c.print_message(message=message, message_type="Warning", to_slack=to_slack)

# Print overview
checkBonds = True
c.printHypervisors(clusterID, poolmaster.name, checkBonds)

# Print cluster info
message = "Some info about cluster '" + clustername + "':"
c.print_message(message=message, message_type="Note", to_slack=False)
c.printCluster(clusterID)

# Then the other hypervisors, one-by-one
for h in cluster_hosts:
    c.slack_custom_value = h.name

    if h.name in ignoreHosts:
        message = "Skipping " + h.name + " due to --ignore-hosts setting"
        c.print_message(message=message, message_type="Note", to_slack=to_slack)
        continue

    if h.name == poolmaster.name:
        message = "Skipping poolmaster"
        c.print_message(message=message, message_type="Note", to_slack=False)
        continue
    vm_count = x.host_get_vms(h)
    if vm_count:
        message = h.name + " has " + vm_count + " VMs running. Live migrating VMs to make it empty, then reboot it."
        c.print_message(message=message, message_type="Note", to_slack=to_slack)
        reboot_result = x.host_reboot(h, halt_hypervisor)
        if reboot_result is False:
            message = "Stopping sequence, as a reboot failed. Please investigate."
            c.print_message(message=message, message_type="Error", to_slack=to_slack)
            x.roll_back(h)
            disconnect_all()
            sys.exit(1)
    else:
        message = "Unable to get vm_count from host " + h.name
        c.print_message(message=message, message_type="Error", to_slack=to_slack)
        x.roll_back(h)
        disconnect_all()
        sys.exit(1)
    message = "We completed host " + h.name + " successfully."
    c.print_message(message=message, message_type="Note", to_slack=to_slack)

    # Print overview
    checkBonds = True
    c.printHypervisors(clusterID, poolmaster.name, checkBonds)

# Enable HA
pool_ha_result = x.pool_ha_enable(poolmaster)
if pool_ha_result is False:
    message = "Unable to set the HA state to Enable for cluster " + clustername
    c.print_message(message=message, message_type="Warning", to_slack=to_slack)

# Check HA
pool_ha = x.pool_ha_check(poolmaster)
if pool_ha == "Error":
    message = "Unable to get the current HA state of cluster " + clustername
    c.print_message(message=message, message_type="Error", to_slack=to_slack)
    disconnect_all()
    sys.ext(1)
message = "The state of HA on cluster " + clustername + " is " + str(pool_ha)
c.print_message(message=message, message_type="Note", to_slack=to_slack)

# Print cluster info
message = "Some info about cluster '" + clustername + "':"
c.print_message(message=message, message_type="Note", to_slack=False)
c.printCluster(clusterID)

# Disconnect
disconnect_all()

# Done
message = "We're done with cluster " + clustername
c.print_message(message=message, message_type="Note", to_slack=to_slack)

# End time
message = "Finished @ " + time.strftime("%Y-%m-%d %H:%M")
c.print_message(message=message, message_type="Note", to_slack=False)

