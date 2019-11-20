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

# Script to live migrate a VM to another cluster
# Remi Bergsma - rbergsma@schubergphilis.com

import sys
import getopt
from cloudstackops import cloudstackops
from cloudstackops import cloudstacksql
from cloudstackops import kvm
import os.path
from datetime import datetime
import time
import getpass

# Function to handle our arguments


def handleArguments(argv):
    global DEBUG
    DEBUG = 0
    global DRYRUN
    DRYRUN = 1
    global vmname
    vmname = ''
    global toStoragePool
    toStoragePool = ''
    global fromStoragePool
    fromStoragePool = ''
    global configProfileName
    configProfileName = ''
    global isProjectVm
    isProjectVm = 0
    global force
    force = 0
    global mysqlHost
    mysqlHost = ''
    global mysqlPasswd
    mysqlPasswd = ''
    global zwps2cwps
    zwps2cwps = False
    global max_iops
    max_iops = 1000


    # Usage message
    help = "Usage: ./" + os.path.basename(__file__) + ' [options] ' + \
        '\n  --config-profile -c <profilename>\tSpecify the CloudMonkey profile name to get the credentials from (or specify in ./config file)' + \
        '\n  --vmname -n <name>\t\t\tMigrate VM with this name (only allowed when unique, otherwise use -i)' + \
        '\n  --instance-name -i <instancename>\tStop/Start VM with this instance name (i-123-12345-VM)' + \
        '\n  --tostoragepool -t <storagepoolname>\t\tMigrate to this storage pool' + \
        '\n  --fromstoragepool -f <storagepoolname>\t\tMigrate from this storage pool only' + \
        '\n  --maxiops -m <iops>\t\tMax nr of IOPS to use during migration' + \
        '\n  --mysqlserver -s <mysql hostname>\tSpecify MySQL server config section name' + \
        '\n  --mysqlpassword <passwd>\t\tSpecify password to cloud MySQL user' + \
        '\n  --zwps2cwps\t\t\t\tMigrate ZWPS to CWPS' + \
        '\n  --is-projectvm\t\t\tThis VMs belongs to a project' + \
        '\n  --debug\t\t\t\tEnable debug mode' + \
        '\n  --exec\t\t\t\tExecute for real'

    try:
        opts, args = getopt.getopt(
            argv, "hm:c:n:i:t:s:f:p", [
                "config-profile=", "vmname=", "instance-name=", "tostoragepool=", "fromstoragepool=", "zwps2cwps", "mysqlserver=", "debug",
                "exec", "is-projectvm", "force", "maxiops="])
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
        elif opt in ("-i", "--instance-name"):
            vmname = arg
        elif opt in ("-n", "--vmname"):
            vmname = arg
        elif opt in ("-t", "--tostoragepool"):
            toStoragePool = arg
        elif opt in ("-f", "--fromstoragepool"):
            fromStoragePool = arg
        elif opt in ("-s", "--mysqlserver"):
            mysqlHost = arg
        elif opt in ("-p", "--mysqlpassword"):
            mysqlPasswd = arg
        elif opt in ("-m", "--maxiops"):
            max_iops = arg
        elif opt in ("--debug"):
            DEBUG = 1
        elif opt in ("--exec"):
            DRYRUN = 0
        elif opt in ("--is-projectvm"):
            isProjectVm = 1
        elif opt in ("--force"):
            force = 1
        elif opt in ("--zwps2cwps"):
            zwps2cwps = True


    # Default to cloudmonkey default config file
    if len(configProfileName) == 0:
        configProfileName = "config"

    # We need at least these vars
    if len(vmname) == 0 or len(toStoragePool) == 0:
        print help
        sys.exit()

    # If ZWPS conversion we need the SQL stuff
    if zwps2cwps and len(mysqlHost) == 0:
        print("When --zwps2cwps flag is used, you need to specify --mysqlserver to make the change")
        sys.exit()


# Parse arguments
if __name__ == "__main__":
    handleArguments(sys.argv[1:])

# Init our class
c = cloudstackops.CloudStackOps(DEBUG, DRYRUN)
c.task = "Live Migrate VM Volumes"
c.slack_custom_title = "Domain"
c.slack_custom_value = ""

# Start time
print "Note: Starting @ %s" % time.strftime("%Y-%m-%d %H:%M")
start_time = datetime.now()

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

if isProjectVm == 1:
    projectParam = "true"
else:
    projectParam = "false"

to_slack = True
if DRYRUN == 1:
    to_slack = False

vmID = c.checkCloudStackName({'csname': vmname,
                              'csApiCall': 'listVirtualMachines',
                              'listAll': 'true',
                              'isProjectVm': projectParam})

toStoragePoolID = c.checkCloudStackName(
    {'csname': toStoragePool, 'csApiCall': 'listStoragePools'})

if toStoragePoolID == 1 or toStoragePoolID is None:
    print "Error: Storage Pool with name '" + toStoragePool + "' can not be found! Halting!"
    sys.exit(1)

# Get data from vm
vmdata = c.getVirtualmachineData(vmID)
if vmdata is None:
    print "Error: Could not find vm " + vmname + "!"
    sys.exit(1)
vm = vmdata[0]
c.instance_name = vm.instancename
c.slack_custom_value = vm.domain
c.vm_name = vm.name
c.zone_name = vm.zonename

snapshotData = c.listVMSnapshot(vm.id)
snapshot_found = False
if snapshotData == 1:
    print "Error: Could not list VM snapshots"
elif snapshotData is None:
    print "Note: No VM snapshots found for this vm."
else:
    for snapshot in snapshotData:
        print "Note: Found VM snapshot %s, unable to live migrate. Please remove VM snapshots first. " % snapshot.displayname
        snapshot_found = True

if snapshot_found:
    message = "VM %s has VM snapshots, unable to live migrate. Please remove VM snapshots!" % vmname
    c.print_message(message=message, message_type="Error", to_slack=to_slack)
    sys.exit(1)

if vm.state != "Running":
    message = "VM %s is in state %s, can only live migrate when in state Running. Skipping this vm!" % (vmname, vm.state)
    c.print_message(message=message, message_type="Error", to_slack=to_slack)
    sys.exit(1)

hostData = c.getHostData({'hostid': vm.hostid})[0]
clusterData = c.listClusters({'clusterid': hostData.clusterid})
c.cluster = clusterData[0].name

# Init SQL class
s = cloudstacksql.CloudStackSQL(DEBUG, DRYRUN)

# Connect MySQL
result = s.connectMySQL(mysqlHost, mysqlPasswd)

# Do ZWPS to CWPS conversion before finding migration hosts or else it will return none
if zwps2cwps:
    message = "Switching any ZWPS volume of vm %s to CWPS so they will move along with the VM" % vm.name
    c.print_message(message=message, message_type="Note", to_slack=to_slack)
    if result > 0:
        message = "MySQL connection failed"
        c.print_message(message=message, message_type="Error", to_slack=to_slack)
        sys.exit(1)
    elif DEBUG == 1:
        print "DEBUG: MySQL connection successful"
        print s.conn

    if not s.update_zwps_to_cwps(instance_name=vm.instancename, disk_offering_name="MCC_v1.CWPS"):
        message = "Switching disk offerings to CWPS failed. Halting"
        c.print_message(message=message, message_type="Error", to_slack=to_slack)
        sys.exit(1)

# Init KVM class
k = kvm.Kvm(ssh_user=getpass.getuser())
k.DRYRUN = DRYRUN
k.PREPARE = False
c.kvm = k

# Libvirt disk info
libvirt_disk_info = c.kvm.libvirt_get_disks(vmname=vm.instancename, hypervisor_fqdn=vm.hostname)


for path, disk_info in libvirt_disk_info.iteritems():
    print("Note: Disk %s on pool %s has size %s" % (disk_info['path'], disk_info['pool'], disk_info['size']))

    name, path, uuid, voltype, size = s.get_volume_size(path=disk_info['path'])

    if int(size) < int(disk_info['size']):
        print "Warning: looks like size in DB (%s) is less than libvirt reports (%s)" % (size, disk_info['size'])
        print "Note: Setting size of disk %s to %s" % (path, int(disk_info['size']))
        s.update_volume_size(instance_name=vm.instancename, path=path, size=disk_info['size'])
    else:
        print "OK: looks like size in DB (%s) is >= libvirt reports (%s)" % (size, disk_info['size'])


# Select storage pool
targetStoragePoolData = c.getStoragePool(poolName=toStoragePool)
storagepooltags = targetStoragePoolData[0].tags

if DRYRUN == 1:
    print("Note: Would have set IOPS limits")

else:
    print("Note: Setting IOPS limits")
    if max_iops is None:
        max_iops = 1000
    k.set_iops_limit_for_vm_disks(host=hostData, vm_name=vm.instancename, iops_limit=max_iops)

# Loop all volumes from vm_instance
voldata = c.getVirtualmachineVolumes(vm.id, projectParam)

# Migrate its volumes
volcount = 0
volIDs = []
for vol in voldata:
    # Check if volume is already on correct storage
    currentStorageID = c.checkCloudStackName(
        {'csname': vol.storage, 'csApiCall': 'listStoragePools'})

    if currentStorageID == targetStoragePoolData[0].id:
        print "Warning: No need to migrate volume %s -- already on the desired storage pool. Skipping." % vol.name
        continue

    currentStorageData = c.getStoragePoolData(currentStorageID)[0]
    if currentStorageData.scope in ("Host", "ZONE"):
        print "Note: No need to migrate volume %s -- scope of this volume is HOST / ZONE. Skipping." % vol.name
        continue

    # Check for snapshots
    snapshotData = c.listSnapshots(vol.id, projectParam)
    if snapshotData == 1:
        print "Error: Could not list snapshots"
    elif snapshotData is None:
        print "Note: No snapshots found for this volume."
    else:
        for snapshot in snapshotData:
            print "Note: Found snapshot '" + snapshot.name + "' with state " + snapshot.state + ". Looks OK."
            if snapshot.state != 'BackedUp':
                print "Error: migration of '" + snapshot.volumename + "' will fail because of non 'BackedUp' state of snapshot. Fix manually first."
                sys.exit(1)
        print "Warning: Snapshots will be lost after migration due to bug CLOUDSTACK-6538."

    if DRYRUN == 1:
        print "Note: Would have migrated volume %s to storage %s (%s)" % (vol.id, toStoragePool, targetStoragePoolData[0].id)
    else:
        print "Executing: migrate volume %s to storage %s" % (vol.id, targetStoragePoolData[0].id)
        result = c.migrateVolume(volid=vol.id, storageid=targetStoragePoolData[0].id, live=True)
        if result == 1:
            print "Migrate volume %s (%s) failed -- exiting." % (vol.name, vol.id)
            print "Error: investegate manually!"
            continue

        # Hack - Check when state of volume returns to Ready state
        while True:
            voldata = c.getVolumeData(volumeid=vol.id)
            if voldata is None:
                print "Error: Could not find volume " + vol.name + "!"
                sys.exit(1)
            vol_check = voldata[0]

            if vol_check.state == "Ready":
                break
            time.sleep(60)
            print("Volume %s is in %s state and not Ready. Sleeping." % (voldata.name, voldata.state))


if DRYRUN == 1:
    print("Note: Would have removed IOPS limits")

else:
    print("Note: Removing IOPS limits")
    k.set_iops_limit_for_vm_disks(host=hostData, vm_name=vm.instancename, iops_limit=0)

# End time
message = "Finished @ " + time.strftime("%Y-%m-%d %H:%M")
c.print_message(message=message, message_type="Note", to_slack=False)
elapsed_time = datetime.now() - start_time

