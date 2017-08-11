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

# Script to migrate a specific VM to another cluster
# Remi Bergsma - rbergsma@schubergphilis.com

# @TODO: More checking, like: handle disabled cluster (XEN-12: allocationstate)

import time
import sys
import getopt
from cloudstackops import cloudstackops
import os.path
from random import choice

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

    # Usage message
    help = "Usage: ./" + os.path.basename(__file__) + ' [options] ' + \
        '\n  --config-profile -c <profilename>\tSpecify the CloudMonkey profile name to get the credentials from (or specify in ./config file)' + \
        '\n  --vmname -n <name>\t\t\tMigrate VM with this name (only allowed when unique, otherwise use -i)' + \
        '\n  --instance-name -i <instancename>\tMigrate VM with this instance name (i-123-12345-VM)' + \
        '\n  --tocluster -t <clustername>\t\tMigrate router to this cluster' + \
        '\n  --is-projectvm\t\t\tThis VMs belongs to a project' + \
        '\n  --debug\t\t\t\tEnable debug mode' + \
        '\n  --exec\t\t\t\tExecute for real'

    try:
        opts, args = getopt.getopt(
            argv, "hc:n:i:t:p", [
                "config-profile=", "vmname=", "instance-name=", "tocluster=", "debug", "exec", "is-projectvm", "force"])
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

    # Default to cloudmonkey default config file
    if len(configProfileName) == 0:
        configProfileName = "config"

    # We need at least these vars
    if len(vmname) == 0 or len(toCluster) == 0:
        print help
        sys.exit()

# Parse arguments
if __name__ == "__main__":
    handleArguments(sys.argv[1:])

# Init our class
c = cloudstackops.CloudStackOps(DEBUG, DRYRUN)

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

vmID = c.checkCloudStackName({'csname': vmname,
                              'csApiCall': 'listVirtualMachines',
                              'listAll': 'true',
                              'isProjectVm': projectParam})
toClusterID = c.checkCloudStackName(
    {'csname': toCluster, 'csApiCall': 'listClusters'})

if toClusterID == 1 or toClusterID is None:
    print "Error: Cluster with name '" + toCluster + "' can not be found! Halting!"
    sys.exit(1)

# Select storage pool
targetStorageID = c.getRandomStoragePool(toClusterID)
targetStoragePoolData = c.getStoragePoolData(targetStorageID)
storagepooltags = targetStoragePoolData[0].tags

# Get hosts that belong to toCluster
toClusterHostsData = c.getHostsFromCluster(toClusterID)
if DEBUG == 1:
    print "Note: You selected a storage pool with tags '" + storagepooltags + "'"

# Get data from vm
vmdata = c.getVirtualmachineData(vmID)
if vmdata is None:
    print "Error: Could not find vm " + vmname + "!"
    sys.exit(1)

vm = vmdata[0]
if vm.state == "Running":
    needToStop = "true"
    autoStartVM = "true"
    print "Note: Found vm " + vm.name + " running on " + vm.hostname
else:
    print "Note: Found vm " + vm.name + " with state " + vm.state
    needToStop = "false"
    autoStartVM = "false"

# Figure out the tags
sodata = c.listServiceOfferings({'serviceofferingid': vm.serviceofferingid})
if sodata is not None:
    hosttags = (sodata[0].hosttags) if sodata[0].hosttags is not None else ''
    storagetags = (sodata[0].tags) if sodata[0].tags is not None else ''

    if storagetags == '':
        print "Warning: router service offering has empty storage tags."

    if storagetags != '' and storagepooltags != storagetags and c.FORCE == 0:
        if DEBUG == 1:
            print "Error: cannot do this: storage tags from provided storage pool '" + storagepooltags + "' do not match your vm's service offering '" + storagetags + "'"
            sys.exit(1)
    elif storagetags != '' and storagepooltags != storagetags and c.FORCE == 1:
        if DEBUG == 1:
            print "Warning: storage tags from provided storage pool '" + storagepooltags + "' do not match your vm's service offering '" + storagetags + "'. Since you used --FORCE you probably know what you manually need to edit in the database."
    elif DEBUG == 1:
        print "Note: Storage tags look OK."

# Volumes
voldata = c.getVirtualmachineVolumes(vm.id, projectParam)

# Migrate its volumes
volcount = 0
volIDs = []
for vol in voldata:
    # Check if volume is already on correct storage
    currentStorageID = c.checkCloudStackName(
        {'csname': vol.storage, 'csApiCall': 'listStoragePools'})

    if currentStorageID == targetStorageID:
        print "Warning: No need to migrate volume " + vol.name + " -- already on the desired storage pool. Skipping."
        continue

    currentStorageData = c.getStoragePoolData(currentStorageID)[0]
    if currentStorageData.scope == "ZONE":
        print "Note: No need to migrate volume " + vol.name + " -- scope of this volume is ZONE. Skipping."
        continue

    # Save ids for later -- we first need to find out if it's worth stopping
    # the vm
    volIDs.append(vol.id)
    volcount = volcount + 1

if volcount > 0:
    # Get user data to e-mail
    adminData = c.getDomainAdminUserData(vm.domainid)
    if DRYRUN == 1:
        print "Note: Not sending notification e-mails due to DRYRUN setting. Would have e-mailed " + adminData.email
    else:

        if not adminData.email:
            print "Warning: Skipping mailing due to missing e-mail address."

        templatefile = open(
            "email_template/migrateVirtualMachine_start.txt",
            "r")
        emailbody = templatefile.read()
        emailbody = emailbody.replace("FIRSTNAME", adminData.firstname)
        emailbody = emailbody.replace("LASTNAME", adminData.lastname)
        emailbody = emailbody.replace("DOMAIN", vm.domain)
        emailbody = emailbody.replace("VMNAME", vm.name)
        emailbody = emailbody.replace("STATE", vm.state)
        emailbody = emailbody.replace("INSTANCENAME", vm.instancename)
        emailbody = emailbody.replace("TOCLUSTER", toCluster)
        emailbody = emailbody.replace("ORGANIZATION", c.organization)
        templatefile.close()

        # Notify user
        msgSubject = 'Starting maintenance for VM ' + \
            vm.name + ' / ' + vm.instancename
        c.sendMail(c.mail_from, adminData.email, msgSubject, emailbody)

        # Notify admin
        c.sendMail(c.mail_from, c.errors_to, msgSubject, emailbody)

        if DEBUG == 1:
            print emailbody

    # Stop this vm if it was running
    if needToStop == "true":
        if DRYRUN == 1:
            print "Would have stopped vm " + vm.name + " with id " + vm.id
        else:
            print "Executing: stop virtualmachine " + vm.name + " with id " + vm.id
            result = c.stopVirtualMachine(vm.id)
            if result == 1:
                print "Stop vm failed -- exiting."
                print "Error: investegate manually!"

                # Notify admin
                msgSubject = 'Warning: problem with maintenance for vm ' + \
                    vm.name + ' / ' + vm.instancename
                emailbody = "Could not stop vm " + vm.name
                c.sendMail(c.mail_from, c.errors_to, msgSubject, emailbody)
                sys.exit(1)

            if result.virtualmachine.state == "Stopped":
                print "Note: " + result.virtualmachine.name + " is stopped successfully "
            else:
                print "Error: " + result.virtualmachine.name + " is in state " + result.virtualmachine.state + " instead of Stopped. VM need to be stopped to continue. Re-run script to try again -- exit."

                # Notify admin
                msgSubject = 'Warning: problem with maintenance for VM ' + \
                    vm.name + ' / ' + vm.instancename
                emailbody = 'Could not stop VM ' + vm.name
                c.sendMail(c.mail_from, c.errors_to, msgSubject, emailbody)
                sys.exit(1)

    # Migrate volume
    for volid in volIDs:
        # Check for snapshots
        snapshotData = c.listSnapshots(volid, projectParam)
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

        # Check for snapshot policies
        snapshotData = c.listSnapshotPolicies(volid)
        if snapshotData == 1:
            print "Error: Could not list snapshot policies"
        elif snapshotData is None:
            print "Note: No snapshot schedules found for this volume."
        else:
            for snapshot in snapshotData:
                intervaltype = c.translateIntervalType(snapshot.intervaltype)
                print "Note: Found snapshot policy: interval=" + str(intervaltype) + " schedule=" + snapshot.schedule + " maxsnaps=" + str(snapshot.maxsnaps) + " timezone=" + snapshot.timezone + " volumeid=" + snapshot.volumeid
            print "Warning: Snapshot schedules will be lost after migration due to bug CLOUDSTACK-6538. We'll try to recreate them, though."

        if DRYRUN == 1:
            print "Note: Would have migrated volume " + volid + " to storage " + targetStorageID
        else:
            print "Executing: migrate volume " + volid + " to storage " + targetStorageID
            result = c.migrateVolume(volid, targetStorageID)
            if result == 1:
                print "Migrate failed -- exiting."
                print "Error: investegate manually!"

                # Notify admin
                msgSubject = 'Warning: problem with maintenance for vm ' + \
                    vm.name + ' / ' + vm.instancename
                emailbody = "Could not migrate volume " + volid
                c.sendMail(c.mail_from, c.errors_to, msgSubject, emailbody)
                sys.exit(1)

            if result.volume.state == "Ready":
                print "Note: " + result.volume.name + " is migrated successfully "

                # Add the snapshot policy again
                if snapshotData is None:
                    print "Note: No snapshot policies to restore."
                elif snapshotData == 1:
                    print "Note: No snapshot policies to restore."
                else:
                    for snapshot in snapshotData:
                        # Translate intervaltype
                        intervaltype = c.translateIntervalType(
                            snapshot.intervaltype)
                        snapshotresult = c.createSnapshotPolicy(
                            {
                                'volid': result.volume.id,
                                'intervaltype': intervaltype,
                                'maxsnaps': snapshot.maxsnaps,
                                'schedule': snapshot.schedule,
                                'timezone': snapshot.timezone})
                        if snapshotresult == 1:
                            print "Error: failed to recreate snapshot schedule."
                        else:
                            print "Note: recreated snapshot schedule with id " + snapshotresult.snapshotpolicy.id

            else:
                warningMsg = "Warning: " + result.volume.name + " is in state " + \
                    result.volume.state + " instead of Ready. Please investigate before starting VM again!"
                print warningMsg
                autoStartVM = "false"

                # Notify admin
                msgSubject = 'Warning: problem with maintenance for VM ' + \
                    vm.name + ' / ' + vm.instancename
                emailbody = warningMsg
                c.sendMail(c.mail_from, c.errors_to, msgSubject, emailbody)

    # Select a random node from the toCluster
    toHostData = choice(toClusterHostsData)
    if DEBUG == 1:
        print "Note: Selected node " + toHostData.name + " with ID " + toHostData.id + " to start this VMs on"

    # Start the VM again
    if autoStartVM == "true":
        if DRYRUN == 1:
            print "Would have started vm " + vm.name + " with id " + vm.id + " on host " + toHostData.id
        else:
            print "Executing: start virtualmachine " + vm.name + " with id " + vm.id + " on host " + toHostData.id
            result = c.startVirtualMachine(vm.id, toHostData.id)
            if result == 1:
                print "Start vm failed -- exiting."
                print "Error: investegate manually!"

                # Notify admin
                msgSubject = 'Warning: problem with maintenance for vm ' + \
                    vm.name + ' / ' + vm.instancename
                emailbody = "Could not start vm " + vm.name
                c.sendMail(c.mail_from, c.errors_to, msgSubject, emailbody)
                sys.exit(1)

            if result.virtualmachine.state == "Running":
                print "Note: " + result.virtualmachine.name + " is started successfully "
                # Get user data to e-mail
                adminData = c.getDomainAdminUserData(vm.domainid)
                if DRYRUN == 1:
                    print "Note: Not sending notification e-mails due to DRYRUN setting. Would have e-mailed " + adminData.email
                else:

                    if not adminData.email:
                        print "Warning: Skipping mailing due to missing e-mail address."

                    templatefile = open(
                        "email_template/migrateVirtualMachine_done.txt",
                        "r")
                    emailbody = templatefile.read()
                    emailbody = emailbody.replace(
                        "FIRSTNAME",
                        adminData.firstname)
                    emailbody = emailbody.replace(
                        "LASTNAME",
                        adminData.lastname)
                    emailbody = emailbody.replace("DOMAIN", vm.domain)
                    emailbody = emailbody.replace("VMNAME", vm.name)
                    emailbody = emailbody.replace("STATE", vm.state)
                    emailbody = emailbody.replace(
                        "INSTANCENAME",
                        vm.instancename)
                    emailbody = emailbody.replace("TOCLUSTER", toCluster)
                    emailbody = emailbody.replace(
                        "ORGANIZATION",
                        c.organization)
                    templatefile.close()

                    # Notify user
                    msgSubject = 'Finished maintenance for VM ' + \
                        vm.name + ' / ' + vm.instancename
                    c.sendMail(
                        c.mail_from,
                        adminData.email,
                        msgSubject,
                        emailbody)

                    # Notify admin
                    c.sendMail(c.mail_from, c.errors_to, msgSubject, emailbody)

                    if DEBUG == 1:
                        print emailbody

            else:
                warningMsg = "Warning: " + result.virtualmachine.name + " is in state " + \
                    result.virtualmachine.state + " instead of Started. Please investigate (could just take some time)."
                print warningMsg
                autoStartVM = "false"

                # Notify admin
                msgSubject = 'Warning: problem with maintenance for VM ' + \
                    vm.name + ' / ' + vm.instancename
                emailbody = warningMsg
                c.sendMail(c.mail_from, c.errors_to, msgSubject, emailbody)

    else:
        print "Warning: Not starting " + vm.name + " automatically!"
        # Get user data to e-mail
        adminData = c.getDomainAdminUserData(vm.domainid)
        if DRYRUN == 1:
            print "Note: Not sending notification e-mails due to DRYRUN setting. Would have e-mailed " + adminData.email
        else:

            if not adminData.email:
                print "Warning: Skipping mailing due to missing e-mail address."

            # Tell the user how to start the VM manually
            cloudmonkeyCmd = "cloudmonkey start virtualmachine id=" + \
                vm.id + " hostid=" + toHostData.id

            templatefile = open(
                "email_template/migrateVirtualMachine_done_nostart.txt",
                "r")
            emailbody = templatefile.read()
            emailbody = emailbody.replace("FIRSTNAME", adminData.firstname)
            emailbody = emailbody.replace("LASTNAME", adminData.lastname)
            emailbody = emailbody.replace("DOMAIN", vm.domain)
            emailbody = emailbody.replace("VMNAME", vm.name)
            emailbody = emailbody.replace("STATE", vm.state)
            emailbody = emailbody.replace("INSTANCENAME", vm.instancename)
            emailbody = emailbody.replace("CLOUDMONKEYCMD", cloudmonkeyCmd)
            emailbody = emailbody.replace("TOCLUSTER", toCluster)
            emailbody = emailbody.replace("ORGANIZATION", c.organization)
            templatefile.close()

            # Notify user
            msgSubject = 'Finished maintenance for VM ' + \
                vm.name + ' / ' + vm.instancename
            c.sendMail(c.mail_from, adminData.email, msgSubject, emailbody)

            # Notify mon-cloud
            c.sendMail(c.mail_from, c.errors_to, msgSubject, emailbody)

            if DEBUG == 1:
                print emailbody

elif vm.state == "Running":
    print "Note: Nothing to do at all. Volumes are already on the desired storage pool."
else:
    print "Note: All volumes are already on the desired storage pool. Just start the VM!"

print "Note: We're done!"
