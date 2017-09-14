#!/usr/bin/python

#      Copyright 2017, Schuberg Philis BV
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

# Script to migrate a specific VM from XenServer to KVM
# Remi Bergsma - rbergsma@schubergphilis.com

import time
import sys
import getopt
from cloudstackops import cloudstackops
from cloudstackops import cloudstacksql
from cloudstackops import xenserver
from cloudstackops import kvm
import os.path
from random import choice
import getpass
from datetime import datetime


# Function to handle our arguments


def handleArguments(argv):
    global DEBUG
    DEBUG = 0
    global DRYRUN
    DRYRUN = 1
    global volumename
    volumename = ''
    global toStoragePool
    toStoragePool = ''
    global configProfileName
    configProfileName = ''
    global isProjectVm
    isProjectVm = 0
    global force
    force = 0
    global threads
    threads = 5
    global mysqlHost
    mysqlHost = ''
    global mysqlPasswd
    mysqlPasswd = ''
    global doVirtvtov
    doVirtvtov = True
    global helperScriptsPath
    helperScriptsPath = None

    # Usage message
    help = "Usage: ./" + os.path.basename(__file__) + ' [options] ' + \
        '\n  --config-profile -c <profilename>\tSpecify the CloudMonkey profile name to get the credentials from ' \
        '(or specify in ./config file)' + \
        '\n  --volume-name -v <volumename>\tMigrate Volume with name DATA-12345' + \
        '\n  --toStoragePool -t <storagepool>\t\tMigrate Volume to this storage pool' + \
        '\n  --mysqlserver -s <mysql hostname>\tSpecify MySQL server config section name' + \
        '\n  --mysqlpassword <passwd>\t\tSpecify password to cloud ' + \
        'MySQL user' + \
        '\n  --skip-virt-v2v\t\t\tSkipping the virt-v2v step' + \
        '\n  --helper-scripts-path\t\t\tFolder with scripts to be copied to hypervisor in migrate working folder' + \
        '\n  --debug\t\t\t\tEnable debug mode' + \
        '\n  --exec\t\t\t\tExecute for real'

    try:
        opts, args = getopt.getopt(
            argv, "hc:v:t:p:s:", [
                "config-profile=", "volume-name=", "tostoragepool=", "mysqlserver=", "mysqlpassword=",
                "skip-virt-v2v", "helper-scripts-path=", "debug", "exec", "force"])
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
        elif opt in ("-v", "--volume-name"):
            volumename = arg
        elif opt in ("-t", "--tostoragepool"):
            toStoragePool = arg
        elif opt in ("-s", "--mysqlserver"):
            mysqlHost = arg
        elif opt in ("-p", "--mysqlpassword"):
            mysqlPasswd = arg
        elif opt in ("--debug"):
            DEBUG = 1
        elif opt in ("--exec"):
            DRYRUN = 0
        elif opt in ("--force"):
            force = 1
        elif opt in ("--skip-virt-v2v"):
            doVirtvtov = False
        elif opt in ("--helper-scripts-path"):
            helperScriptsPath = arg

    # Default to cloudmonkey default config file
    if len(configProfileName) == 0:
        configProfileName = "config"

    # We need at least these vars
    if len(volumename) == 0 or len(toStoragePool) == 0 or len(mysqlHost) == 0:
        print help
        sys.exit()

def exit_script(message):
    print "Fatal Error: %s" % message
    sys.exit(1)


# Parse arguments
if __name__ == "__main__":
    handleArguments(sys.argv[1:])

# Start time
print "Note: Starting @ %s" % time.strftime("%Y-%m-%d %H:%M")
start_time = datetime.now()

if DEBUG == 1:
    print "Warning: Debug mode is enabled!"

if DRYRUN == 1:
    print "Warning: dry-run mode is enabled, not running any commands!"

# Init CloudStackOps class
c = cloudstackops.CloudStackOps(DEBUG, DRYRUN)
c.task = "XenServer -> KVM migration (disk)"
c.slack_custom_title = "Migration details"

# Init XenServer class
x = xenserver.xenserver('root', threads)
x.DEBUG = DEBUG
x.DRYRUN = DRYRUN
c.xenserver = x

# Init KVM class
k = kvm.Kvm(ssh_user=getpass.getuser(), threads=threads, helper_scripts_path=helperScriptsPath)
k.DEBUG = DEBUG
k.DRYRUN = DRYRUN
c.kvm = k

# Init SQL class
s = cloudstacksql.CloudStackSQL(DEBUG, DRYRUN)

# Connect MySQL
result = s.connectMySQL(mysqlHost, mysqlPasswd)
if result > 0:
    message = "MySQL connection failed"
    c.print_message(message=message, message_type="Error", to_slack=True)
    sys.exit(1)
elif DEBUG == 1:
    print "DEBUG: MySQL connection successful"
    print s.conn

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
    print "Debug: Checking CloudStack IDs of provided input.."

if isProjectVm == 1:
    projectParam = "true"
else:
    projectParam = "false"

volumeID = c.checkCloudStackName({ 'csname': volumename,
                              'csApiCall': 'listVolumes',
                              'listAll': 'true',
                              'isProjectVm': projectParam })
toStoragePoolID = c.checkCloudStackName(
    {'csname': toStoragePool, 'csApiCall': 'listStoragePools' })

message = "Storage Pool ID found for %s is %s" % (toStoragePool, toStoragePoolID)
c.print_message(message=message, message_type="Note", to_slack=False)
c.cluster = toStoragePool


if toStoragePoolID == 1 or toStoragePoolID is None:
    message = "Storage Pool with name '%s' can not be found! Halting!" % toStoragePool
    c.print_message(message=message, message_type="Error", to_slack=False)
    sys.exit(1)

# Get data from volume
volumeData = c.getVolumeData(volumeID)
if volumeData is None:
    message = "Error: Could not find volume %s !" % volumename
    c.print_message(message=message, message_type="Error", to_slack=False)
    sys.exit(1)

volume = volumeData[0]
c.instance_name = volume.id
c.vm_name = volume.name
c.zone_name = volume.zonename
c.slack_custom_title = "Migration details for %s" % volume.domain

# Select storage pool
targetStoragePoolData = c.getStoragePoolData(toStoragePoolID)[0]
storagePoolTags = targetStoragePoolData.tags
storagePoolName = targetStoragePoolData.name
storagePoolClusterId = targetStoragePoolData.clusterid

# Get cluster hosts
kvm_host = c.getRandomHostFromCluster(storagePoolClusterId)

to_slack = True
if DRYRUN == 1:
    to_slack = False

if DEBUG == 1:
    print "Note: You selected a storage pool with tags '" + str(storagePoolTags) + "'"
    to_slack = False

if volume.hypervisor == "KVM":
    message = "VM %s is already happily running on KVM!" % (volume.name)
    c.print_message(message=message, message_type="Error", to_slack=False)
    sys.exit(1)

message = "Found volume %s in state %s on %s" % (volume.name, volume.state, volume.storage)
c.print_message(message=message, message_type="Note", to_slack=to_slack)

if volume.state != "Ready":
    message = "Volume %s needs to be in state Ready, not %s. Halting." % (volume.name, volume.state)
    sys.exit(1)

if volume.vmname is not None:
    message = "Volume %s in attached to VM %s. Use another script to migrate a VM with its volumes. Halting." % (volume.name, volume.vmname)
    c.print_message(message=message, message_type="Error", to_slack=to_slack)
    sys.exit(1)

if volume.state != "Ready":
    message = "Volume %s needs to be in state Ready, not %s. Halting." % (volume.name, volume.state)
    c.print_message(message=message, message_type="Error", to_slack=to_slack)
    sys.exit(1)

saved_storage_id = None

# Migrate volume
# Check if volume is already on correct storage
currentStorageID = c.checkCloudStackName(
    {'csname': volume.storage, 'csApiCall': 'listStoragePools'})

if saved_storage_id is None:
    saved_storage_id = currentStorageID

if currentStorageID == toStoragePoolID:
    message = "No need to migrate volume %s -- already on the desired storage pool. Skipping." % volume.name
    c.print_message(message=message, message_type="Note", to_slack=False)

if currentStorageID is None:
    print "Error: Unable to determine the current storage pool of the volumes."
    sys.exit(1)

# Get hosts that belong to toCluster vm is currently running on
currentStorageData = c.getStoragePoolData(currentStorageID)[0]
xenserver_host = c.getRandomHostFromCluster(currentStorageData.clusterid)
currentClusterData = c.listClusters({'clusterid': currentStorageData.clusterid})[0]

c.slack_custom_value = "From %s to %s" % (xenserver_host.name, kvm_host.name.split(".")[0])

# Prepare the folders
if x.prepare_xenserver(xenserver_host) is False:
    sys.exit(1)
if k.prepare_kvm(kvm_host, targetStoragePoolData.id) is False:
    sys.exit(1)
if k.put_scripts(kvm_host) is False:
    sys.exit(1)

# Get all volumes
volumes_result = s.get_volume(volume.name)
for (name, path, uuid, voltype) in volumes_result:
    message = "Processing volume '%s', filename '%s', uuid '%s'" % (name, path, uuid)
    c.print_message(message=message, message_type="Note", to_slack=to_slack)

    if DRYRUN == 1:
        print "Note: Would have extracted, downloaded, converted volume %s " % name
    else:
        if voltype != "DATADISK":
            message = "Volume %s is of type %s (should be DATADISK). Nothing has changed. Halting." % (name, voltype)
            c.print_message(message=message, message_type="Error", to_slack=True)
            sys.exit(1)

        # Transfer volume from XenServer to KVM
        message = "Note: Extracting volume %s" % name
        c.print_message(message=message, message_type="Note", to_slack=False)

        file_to_download = "/mnt/NL1-NETAPPS/" + currentClusterData.name + "/" + str(x.extract_volume_wrapper(path, xenserver_host))
        if file_to_download is None:
            message = "Transferring volume failed: did not get download url from API"
            c.print_message(message=message, message_type="Error", to_slack=True)
            message = "Check volume_store_ref table, field url. It should contain a valid URL or NULL"
            c.print_message(message=message, message_type="Note", to_slack=False)
            message = "Nothing has changed, feel free to retry"
            c.print_message(message=message, message_type="Note", to_slack=False)
            sys.exit(1)
        if k.download_volume(kvm_host, file_to_download, path) is False:
            message = "Downloading volume %s failed" % path
            c.print_message(message=message, message_type="Error", to_slack=True)
            message = "Nothing has changed, feel free to retry"
            c.print_message(message=message, message_type="Note", to_slack=False)
            sys.exit(1)
        message = "Downloading volume %s (name on disk %s) to KVM was successful" % (name, path)
        c.print_message(message=message, message_type="Note", to_slack=False)
        kvmresult = False
        os_family = None
        if voltype == "DATADISK":
            message = "%s is a disk of type %s so skipping virt-v2v and friends" % (name, voltype)
            c.print_message(message=message, message_type="Note", to_slack=False)
            kvmresult = k.make_kvm_compatible(kvm_host, path, False, True)

        if kvmresult is False:
            message = "Making volume %s KVM compatible failed" % path
            c.print_message(message=message, message_type="Error", to_slack=True)
            message = "If using Linux, you could try using --skip-virt-v2v to skip the virt-v2v steps"
            c.print_message(message=message, message_type="Note", to_slack=False)
            message = "Nothing has changed, feel free to retry"
            c.print_message(message=message, message_type="Note", to_slack=False)
            sys.exit(1)
        message = "Converting volume %s to KVM was successful" % path
        c.print_message(message=message, message_type="Note", to_slack=True)

# Revery Query
revert_sql = s.generate_revert_query_volume(volume.id)

# It might be a long time since the initial MySQL connection so we need to reconnect
# Connect MySQL
result = s.connectMySQL(mysqlHost, mysqlPasswd)
if result > 0:
    message = "MySQL connection failed"
    c.print_message(message=message, message_type="Error", to_slack=to_slack)
    sys.exit(1)
elif DEBUG == 1:
    print "DEBUG: MySQL connection successful"
    print s.conn

message = "Updating the database to activate the Volume on KVM"
c.print_message(message=message, message_type="Note", to_slack=False)

if not s.update_volume_from_xenserver_cluster_to_kvm_cluster(volume.id, storagePoolName):
    message = "Updating the database failed"
    c.print_message(message=message, message_type="Error", to_slack=True)
    message = "Nothing has changed, feel free to retry"
    c.print_message(message=message, message_type="Note", to_slack=False)
    sys.exit(1)
else:
    message =  "Note: Should you want to revert, you simply run this SQL:"
    c.print_message(message=message, message_type="Note", to_slack=False)
    c.print_message(message="Revert SQL: ```" + revert_sql + "```", message_type="Plain", to_slack=to_slack)

# Disconnect MySQL
s.disconnectMySQL()

# End time
message = "Finished @ " + time.strftime("%Y-%m-%d %H:%M")
c.print_message(message=message, message_type="Note", to_slack=False)
elapsed_time = datetime.now() - start_time

m, s = divmod(elapsed_time.total_seconds(), 60)
h, m = divmod(m, 60)

message = "VM %s is successfully migrated to KVM on cluster %s in %02d:%02d:%02d" % (volume.name, toStoragePool, h, m, s)
c.print_message(message=message, message_type="Note", to_slack=to_slack)
