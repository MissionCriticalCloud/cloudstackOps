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
# Remi Bergsma

import sys
import getopt
from cloudstackops import cloudstackops
from cloudstackops import cloudstacksql
from cloudstackops import kvm
import os.path
from datetime import datetime
import time

# Function to handle our arguments


def handleArguments(argv):
    global DEBUG
    DEBUG = 0
    global DRYRUN
    DRYRUN = 1
    global vmname
    vmname = ''
    global toCluster
    toCluster = ''
    global configProfileName
    configProfileName = ''
    global isProjectVm
    isProjectVm = 0
    global force
    force = 0
    global zwps2cwps
    zwps2cwps = False
    global affinityGroupToAdd
    affinityGroupToAdd = ''
    global destination_dc_name
    destination_dc_name = ''

    # Usage message
    help = "Usage: ./" + os.path.basename(__file__) + ' [options] ' + \
        '\n  --config-profile -c <profilename>\tSpecify the CloudMonkey profile name to get the credentials from (or specify in ./config file)' + \
        '\n  --vmname -n <name>\t\t\tMigrate VM with this name (only allowed when unique, otherwise use -i)' + \
        '\n  --instance-name -i <instancename>\tStop/Start VM with this instance name (i-123-12345-VM)' + \
        '\n  --tocluster -t <clustername>\t\tMigrate router to this cluster' + \
        '\n  --zwps2cwps\t\t\t\tMigrate ZWPS to CWPS' + \
        '\n  --affinity-group-to-add\t\tAdd this affinity group to the VM after migration' + \
        '\n  --destinationdc -d <DC name>\t\tSpecify name of DC to migrate to' + \
        '\n  --is-projectvm\t\t\tThis VMs belongs to a project' + \
        '\n  --debug\t\t\t\tEnable debug mode' + \
        '\n  --exec\t\t\t\tExecute for real'

    try:
        opts, args = getopt.getopt(
            argv, "hc:n:i:t:d:", [
                "config-profile=", "vmname=", "instance-name=", "tocluster=", "zwps2cwps", "debug",
                "affinity-group-to-add=", "exec", "is-projectvm", "force", "destinationdc="])
    except getopt.GetoptError as e:
        print("Error: " + str(e))
        print(help)
        sys.exit(2)
    for opt, arg in opts:
        if opt == '-h':
            print(help)
            sys.exit()
        elif opt in ("-c", "--config-profile"):
            configProfileName = arg
        elif opt in ("-i", "--instance-name"):
            vmname = arg
        elif opt in ("-n", "--vmname"):
            vmname = arg
        elif opt in ("-t", "--tocluster"):
            toCluster = arg
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
        elif opt in ("--affinity-group-to-add"):
            affinityGroupToAdd = arg
        elif opt in ("-d", "--destinationdc"):
            destination_dc_name = arg

    # Default to cloudmonkey default config file
    if len(configProfileName) == 0:
        configProfileName = "config"

    # We need at least these vars
    if len(vmname) == 0 or len(toCluster) == 0:
        print(help)
        sys.exit()


def liveMigrateVirtualMachine(c=None, DEBUG=0, DRYRUN=1, vmname='', toCluster='', configProfileName='', isProjectVm=0, force=0, zwps2cwps=False, destination_dc_name='', affinityGroupToAdd='', multirun = False):
    # Start time
    print("Note: Starting @ %s" % time.strftime("%Y-%m-%d %H:%M"))
    start_time = datetime.now()

    # Check cloudstack IDs
    if DEBUG == 1:
        print("Note: Checking CloudStack IDs of provided input..")

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

    toClusterID = c.checkCloudStackName(
        {'csname': toCluster, 'csApiCall': 'listClusters'})

    if toClusterID == 1 or toClusterID is None:
        print("Error: Cluster with name '" + toCluster + "' can not be found! Halting!")
        if multirun:
            return True
        sys.exit(1)

    # Get data from vm
    vmdata = c.getVirtualmachineData(vmID)
    if vmdata is None:
        print("Error: Could not find vm " + vmname + "!")
        if multirun:
            return True
        sys.exit(1)
    vm = vmdata[0]
    c.instance_name = vm.instancename
    c.slack_custom_value = vm.domain
    c.vm_name = vm.name
    c.zone_name = vm.zonename

    snapshotData = c.listVMSnapshot(vm.id)
    snapshot_found = False
    if snapshotData == 1:
        print("Error: Could not list VM snapshots")
    elif snapshotData is None:
        print("Note: No VM snapshots found for this vm.")
    else:
        for snapshot in snapshotData:
            print("Note: Found VM snapshot %s, unable to live migrate. Please remove VM snapshots first. " % snapshot.displayname)
            snapshot_found = True

    if snapshot_found:
        message = "VM %s has VM snapshots, unable to live migrate. Please remove VM snapshots!" % vmname
        c.print_message(message=message, message_type="Error", to_slack=to_slack)
        if multirun:
            return True
        sys.exit(1)

    if vm.state != "Running":
        message = "VM %s is in state %s, can only live migrate when in state Running. Skipping this vm!" % (vmname, vm.state)
        c.print_message(message=message, message_type="Error", to_slack=to_slack)
        if multirun:
            return True
        sys.exit(1)

    hostData = c.getHostData({'hostid': vm.hostid})[0]
    clusterData = c.listClusters({'clusterid': hostData.clusterid})
    c.cluster = clusterData[0].name

    if hostData.clusterid == toClusterID:
        message = "VM %s is already running on cluster %s. Skipping this vm!" % (vmname, toCluster)
        c.print_message(message=message, message_type="Error", to_slack=to_slack)
        if multirun:
            return True
        sys.exit(1)

    # Init SQL class
    s = cloudstacksql.CloudStackSQL(DEBUG, DRYRUN)

    # Connect MySQL
    result = s.connectMySQL(configProfileName)
    if result > 0:
        message = "MySQL connection failed"
        c.print_message(message=message, message_type="Error", to_slack=to_slack)
        if multirun:
            return True
        sys.exit(1)
    elif DEBUG == 1:
        print("DEBUG: MySQL connection successful")
        print(s.conn)

    # Do ZWPS to CWPS conversion before finding migration hosts or else it will return none
    if zwps2cwps:
        message = "Switching any ZWPS volume of vm %s to CWPS so they will move along with the VM" % vm.name
        c.print_message(message=message, message_type="Note", to_slack=to_slack)

        if not s.update_zwps_to_cwps(instance_name=vm.instancename, disk_offering_name="MCC_v1.CWPS"):
            message = "Switching disk offerings to CWPS failed. Halting"
            c.print_message(message=message, message_type="Error", to_slack=to_slack)
            if multirun:
                return True
            sys.exit(1)

    # Do DC offering migrate before finding migration hosts or else it will return none
    if len(destination_dc_name) > 0:
        datacenters = ["SBP1", "EQXAMS2", "EVO"]
        current_offering_name = vm.serviceofferingname

        if destination_dc_name not in datacenters:
            print("Unknown DC %s. Should be one of: %s" % (destination_dc_name, str(datacenters)))
            sys.exit(1)

        for dc_name in datacenters:
            if dc_name == destination_dc_name:
                continue
            if dc_name in current_offering_name:
                print("Note: replacing %s DC with %s" % (dc_name, destination_dc_name))
                print("Note: current offering: %s" % current_offering_name)
                new_offering_name = current_offering_name.replace(dc_name, destination_dc_name)
                print("Note: new offering: %s" % new_offering_name)
                s.update_service_offering_of_vm(instance_name=vm.instancename, service_offering_name=new_offering_name)
                break

    # Quick scan
    zwps_found = False
    zwps_name = None
    root_disk = None
    cwps_found = False
    voldata = c.getVirtualmachineVolumes(vm.id, projectParam)
    for vol in voldata:
        if vol.type == 'DATADISK':
            if 'CWPS' in vol.diskofferingname.upper():
                cwps_found = True
            if 'ZWPS' in vol.diskofferingname.upper():
                zwps_found = True
                zwps_name = vol.storage
        elif vol.type == 'ROOT':
            root_disk = vol

    if cwps_found and zwps_found:
        message = "This VM has both ZWPS and CWPS data disks attached. That is not currently handled by this script."
        c.print_message(message=message, message_type="Error", to_slack=to_slack)
        if multirun:
            return True
        sys.exit(1)

    # Make sure we have no ZWPS and CWPS combi or else migrating will fail

    # Root disk is also CWPS.
    if zwps_found:
        print("Note: ZWPS data disk attached!")
        print("Note: For migration to work we need to migrate root disk %s to ZWPS pool %s first," %
              (root_disk.name, zwps_name))
        print("Note: then migrate the VM and its disks and finally move ROOT disk to a CWPS pool at %s" % toCluster)

    # Check if volume is already on correct storage
    if root_disk.storage == zwps_name:
        print("Warning: No need to migrate volume %s -- already on the desired storage pool. Skipping." % root_disk.name)
    else:
        if DRYRUN == 1:
            message = "Would have migrated ROOT disk %s of VM %s to ZWPS pool %s" % \
                      (root_disk.name, vm.instancename, zwps_name)
            c.print_message(message=message, message_type="Note", to_slack=to_slack)
            if multirun:
                return True
            sys.exit(1)

        message = "Migrating ROOT disk of %s VM %s to ZWPS pool %s" % (root_disk.name, vm.instancename, zwps_name)
        c.print_message(message=message, message_type="Note", to_slack=to_slack)
        target_storage_pool_data = c.getStoragePool(poolName=zwps_name)
        result = c.migrateVolume(volid=root_disk.id, storageid=target_storage_pool_data[0].id, live=True)
        if result == 1:
            message = "Migrate volume %s (%s) failed -- exiting." % (root_disk.name, root_disk.id)
            c.print_message(message=message, message_type="Error", to_slack=to_slack)
            if multirun:
                return True
            sys.exit(1)

    # VM now runs with root disk at ZWPS

    # Detach any isos
    if vm.isoid is not None:
        print("Note: Detaching any connected ISO from vm %s" % vm.name)
        c.detach_iso(vm.id)
    else:
        print("Note: No ISOs connected to detach")

    # Get hosts that belong to toCluster
    toClusterHostsData = c.getHostsFromCluster(toClusterID)
    migrationHost = c.findBestMigrationHost(toClusterID, vm.hostname, vm.memory)
    currentHostname=vm.hostname

    if not migrationHost:
        message = "No hosts with enough capacity to migrate %s to. Please migrate manually to another cluster." % vm.name
        c.print_message(message=message, message_type="Error", to_slack=to_slack)
        if multirun:
            return True
        sys.exit(1)

    # Init KVM class
    k = kvm.Kvm()
    k.DRYRUN = DRYRUN
    k.PREPARE = False
    c.kvm = k

    # Libvirt disk info
    libvirt_disk_info = c.kvm.libvirt_get_disks(vmname=vm.instancename, hypervisor_fqdn=vm.hostname)

    for path, disk_info in libvirt_disk_info.iteritems():
        print("Note: Disk %s on pool %s has size %s" % (disk_info['path'], disk_info['pool'], disk_info['size']))

        name, path, uuid, voltype, size = s.get_volume_size(path=disk_info['path'])

        if int(size) < int(disk_info['size']):
            print("Warning: looks like size in DB (%s) is less than libvirt reports (%s)" % (size, disk_info['size']))
            print("Note: Setting size of disk %s to %s" % (path, int(disk_info['size'])))
            s.update_volume_size(instance_name=vm.instancename, path=path, size=disk_info['size'])
        else:
            print("OK: looks like size in DB (%s) is >= libvirt reports (%s)" % (size, disk_info['size']))

    if DRYRUN == 1:
        message = "Would have migrated %s to %s on cluster %s" % (vm.name, migrationHost.name, toCluster)
        c.print_message(message=message, message_type="Note", to_slack=False)
        if multirun:
            return True
        sys.exit(1)

    message = "Starting migration of %s to %s on cluster %s" % (vm.name, migrationHost.name, toCluster)
    c.print_message(message=message, message_type="Note", to_slack=to_slack)

    result = c.migrateVirtualMachineWithVolume(vm.id, migrationHost.id)
    if not result:
        message = "Migrate vm %s failed -- exiting." % vm.name
        c.print_message(message=message, message_type="Error", to_slack=to_slack)
        if multirun:
            return True
        sys.exit(1)

    # Hack -- Is this still needed?
    while True:
        vmdata = c.getVirtualmachineData(vmID)
        if vmdata is None:
            print("Error: Could not find vm " + vmname + "!")
            if multirun:
                return True
            sys.exit(1)
        vm = vmdata[0]

        if vm.state == "Running":
            break
        time.sleep(60)
        print("Vm %s is in %s state and not Running. Sleeping." % (vm.name, vm.state))

    if zwps_found:
        message = "Root disk %s went from CWPS to ZWPS -- move it back to CWPS now" % root_disk.name
        c.print_message(message=message, message_type="Note", to_slack=to_slack)
        # Select storage pool
        target_storage = c.getStoragePoolWithMostFreeSpace(toCluster)
        result = c.migrateVolume(volid=root_disk.id, storageid=target_storage.id, live=True)
        if result == 1:
            message = "Migrate volume %s (%s) failed -- exiting." % (root_disk.name, root_disk.id)
            c.print_message(message=message, message_type="Error", to_slack=to_slack)
            if multirun:
                return True
            sys.exit(1)

        message = "Root disk %s migrated from pool %s to %s" % (root_disk.name, zwps_name, target_storage.name)
        c.print_message(message=message, message_type="Note", to_slack=to_slack)

    result = True
    if currentHostname == vm.hostname:
        result = False

    # End time
    message = "Finished @ " + time.strftime("%Y-%m-%d %H:%M")
    c.print_message(message=message, message_type="Note", to_slack=False)
    elapsed_time = datetime.now() - start_time

    if result:
        if len(affinityGroupToAdd) > 0:
            message = "Adding affinity group %s to VM %s" % (affinityGroupToAdd, vm.name)
            s.add_vm_to_affinity_group(affinity_group_name=affinityGroupToAdd, instance_name=vm.instancename)

        message = "VM %s is successfully migrated to %s on cluster %s in %s seconds" % (vm.name, migrationHost.name, toCluster, elapsed_time.total_seconds())
        c.print_message(message=message, message_type="Note", to_slack=to_slack)
    else:
        message = "VM %s is failed to migrate to %s on cluster %s in %s seconds" % (vm.name, migrationHost.name, toCluster, elapsed_time.total_seconds())
        c.print_message(message=message, message_type="Warning", to_slack=to_slack)

# Parse arguments
if __name__ == "__main__":
    handleArguments(sys.argv[1:])
    # Init our class
    c = cloudstackops.CloudStackOps(DEBUG, DRYRUN)
    c.task = "Live Migrate VM"
    c.slack_custom_title = "Domain"
    c.slack_custom_value = ""

    if DEBUG == 1:
        print("Warning: Debug mode is enabled!")

    if DRYRUN == 1:
        print("Warning: dry-run mode is enabled, not running any commands!")

    # make credentials file known to our class
    c.configProfileName = configProfileName

    # Init the CloudStack API
    c.initCloudStackAPI()

    if DEBUG == 1:
        print("API address: " + c.apiurl)
        print("ApiKey: " + c.apikey)
        print("SecretKey: " + c.secretkey)

    liveMigrateVirtualMachine(c, DEBUG, DRYRUN, vmname, toCluster, configProfileName, isProjectVm, force, zwps2cwps, destination_dc_name, affinityGroupToAdd)
