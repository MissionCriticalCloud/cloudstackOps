#!/usr/bin/python

#      Copyright 2016, Schuberg Philis BV
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
    global instancename
    instancename = ''
    global toCluster
    toCluster = ''
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
    global newBaseTemplate
    newBaseTemplate = ''
    global doVirtvtov
    doVirtvtov = True
    global helperScriptsPath
    helperScriptsPath = None

    # Usage message
    help = "Usage: ./" + os.path.basename(__file__) + ' [options] ' + \
        '\n  --config-profile -c <profilename>\tSpecify the CloudMonkey profile name to get the credentials from ' \
        '(or specify in ./config file)' + \
        '\n  --instance-name -i <instancename>\tMigrate VM with this instance name (i-123-12345-VM). VM name is also' \
        'supported as long as it is unique.' + \
        '\n  --tocluster -t <clustername>\t\tMigrate router to this cluster' + \
        '\n  --new-base-template -b <template>\tKVM template to link the VM to. Won\'t do much, mostly needed for ' \
        'properties like tags. We need to record it in the DB as it cannot be NULL and the XenServer one obviously ' \
        'doesn\'t work either.' + \
        '\n  --is-projectvm\t\t\tThis VMs belongs to a project' + \
        '\n  --mysqlserver -s <mysql hostname>\tSpecify MySQL server config section name' + \
        '\n  --mysqlpassword <passwd>\t\tSpecify password to cloud ' + \
        'MySQL user' + \
        '\n  --skip-virt-v2v\t\t\tSkipping the virt-v2v step' + \
        '\n  --helper-scripts-path\t\t\tFolder with scripts to be copied to hypervisor in migrate working folder' + \
        '\n  --debug\t\t\t\tEnable debug mode' + \
        '\n  --exec\t\t\t\tExecute for real'

    try:
        opts, args = getopt.getopt(
            argv, "hc:i:t:p:s:b:", [
                "config-profile=", "instance-name=", "tocluster=", "mysqlserver=", "mysqlpassword=",
                "new-base-template=", "skip-virt-v2v", "helper-scripts-path=", "debug", "exec", "is-projectvm",
                "force"])
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
            instancename = arg
        elif opt in ("-t", "--tocluster"):
            toCluster = arg
        elif opt in ("-b", "--new-base-template"):
            newBaseTemplate = arg
        elif opt in ("-s", "--mysqlserver"):
            mysqlHost = arg
        elif opt in ("-p", "--mysqlpassword"):
            mysqlPasswd = arg
        elif opt in ("--debug"):
            DEBUG = 1
        elif opt in ("--exec"):
            DRYRUN = 0
        elif opt in ("--is-projectvm"):
            isProjectVm = 1
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
    if len(instancename) == 0 or len(toCluster) == 0 or len(mysqlHost) == 0:
        print help
        sys.exit()

    if not os.path.isdir(helperScriptsPath):
        print "Error: Directory %s as specified with --helper-scripts-path does not exist!" % helperScriptsPath
        sys.exit(1)

def exit_script(message):
    print "Fatal Error: %s" % message
    sys.exit(1)


def start_vm(hypervisor_name):
    global message, result, autoStartVM
    if DRYRUN == 1:
        message = "Would have started vm %s with id %s" % (vm.name, vm.id)
        c.print_message(message=message, message_type="Note", to_slack=False)
    elif autoStartVM:
        message = "Starting virtualmachine %s with id %s" % (vm.name, vm.id)
        c.print_message(message=message, message_type="Note", to_slack=True)
        result = c.startVirtualMachine(vm.id)
        if result == 1:
            message = "Start vm failed -- exiting."
            c.print_message(message=message, message_type="Error", to_slack=True)
            message = "investegate manually!"
            c.print_message(message=message, message_type="Note", to_slack=False)
            sys.exit(1)

        if result.virtualmachine.state == "Running":
            message = "%s is started successfully on %s" % (result.virtualmachine.name, hypervisor_name)
            c.print_message(message=message, message_type="Note", to_slack=True)
        else:
            warningMsg = "Warning: " + result.virtualmachine.name + " is in state " + \
                         result.virtualmachine.state + \
                         " instead of Running. Please investigate (could just take some time)."
            print warningMsg

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
c.task = "XenServer -> KVM migration"
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

vmID = c.checkCloudStackName({'csname': instancename,
                              'csApiCall': 'listVirtualMachines',
                              'listAll': 'true',
                              'isProjectVm': projectParam})
toClusterID = c.checkCloudStackName(
    {'csname': toCluster, 'csApiCall': 'listClusters'})

message = "Cluster ID found for %s is %s" % (toCluster, toClusterID)
c.print_message(message=message, message_type="Note", to_slack=False)
c.cluster = toCluster


if toClusterID == 1 or toClusterID is None:
    message = "Cluster with name '%s' can not be found! Halting!" % toCluster
    c.print_message(message=message, message_type="Error", to_slack=False)
    sys.exit(1)

# Get data from vm
vmdata = c.getVirtualmachineData(vmID)
if vmdata is None:
    message = "Error: Could not find vm %s !" % instancename
    c.print_message(message=message, message_type="Error", to_slack=False)
    sys.exit(1)

vm = vmdata[0]
c.instance_name = vm.instancename
c.vm_name = vm.name
c.zone_name = vm.zonename
c.slack_custom_title = "Migration details for %s" % vm.domain

# Convert template
template_dict = {
    'Win2012R2': 'Win2012R2-DC-SBP_CIS-KVM-2017-05',
    'Windows2012R2': 'Win2012R2-DC-SBP_CIS-KVM-2017-05',
    'Windows 2012 R2': 'Win2012R2-DC-SBP_CIS-KVM-2017-05',
    'Windows 2012 DC R2': 'Win2012R2-DC-SBP_CIS-KVM-2017-05',
    'win2008r2ee': 'win2008r2ee-m2015-02-V3B19-KVM',
    'Windows 2008R2': 'win2008r2ee-m2015-02-V3B19-KVM',
    'Win81': 'Win81x64_for_kvmvdi_v1.5',
    'Centos7': 'Centos7-x86_64-Sbp_cis-KVM-latest',
    'Centos 7': 'Centos7-x86_64-Sbp_cis-KVM-latest',
    'Rhel7': 'Rhel7-x86_64-Sbp_cis-KVM-latest',
    'Rhel6': 'Rhel6-x86_64-Sbp_cis-KVM-latest',
    'Rhel 7': 'Rhel7-x86_64-Sbp_cis-KVM-latest',
    'Rhel 6': 'Rhel6-x86_64-Sbp_cis-KVM-latest',
    'Centos6': 'Centos6-x86_64-Sbp_cis-KVM-latest',
    'Centos 6': 'Centos6-x86_64-Sbp_cis-KVM-latest',
    'NSVPX-XEN': 'Netscaler 11.1.47.14f',
    'Netscaler': 'Netscaler 11.1.47.14f',
    'Ubuntu12': 'Ubuntu1204-x86_64-Sbp_cis-KVM-latest',
    'Ubuntu14': 'Ubuntu1404-x86_64-Sbp_cis-KVM-latest',
    'Ubuntu16': 'ubuntu-16.04',
    'Ubuntu-12': 'Ubuntu1204-x86_64-Sbp_cis-KVM-latest',
    'Ubuntu-14': 'Ubuntu1404-x86_64-Sbp_cis-KVM-latest',
    'Ubuntu-16': 'ubuntu-16.04',
    'Ubuntu 12': 'Ubuntu1204-x86_64-Sbp_cis-KVM-latest',
    'Ubuntu Server 12': 'Ubuntu1204-x86_64-Sbp_cis-KVM-latest',
    'Ubuntu 14': 'Ubuntu1404-x86_64-Sbp_cis-KVM-latest',
    'Ubuntu 16': 'ubuntu-16.04',
    'Ubuntu Desktop 12': 'Ubuntu1204-x86_64-Sbp_cis-KVM-latest',
    'ubuntu-13': 'Ubuntu1404-x86_64-Sbp_cis-KVM-latest',
    'ubuntu 13': 'Ubuntu1404-x86_64-Sbp_cis-KVM-latest',
    'Ubuntu 10': 'Ubuntu1404-x86_64-Sbp_cis-KVM-latest',
    'Ubuntu-10': 'Ubuntu1404-x86_64-Sbp_cis-KVM-latest'
}

for key, value in template_dict.iteritems():
    if key.lower() in vm.templatedisplaytext.lower():
        if len(newBaseTemplate) > 0 and newBaseTemplate != value:
            print "Warning: Would have guessed to use template '%s' but now using overridden value '%s'" \
                  % (value, newBaseTemplate)
            continue
        newBaseTemplate = value

if len(newBaseTemplate) == 0:
    print "Warning: Was unable to detect a KVM template for vm %s. Please specify one using the --new-base-template " \
          "flag and try again. Using 'Linux - Unknown template converted from XenServer'" % (vm.name)
    newBaseTemplate = 'Linux - Unknown template converted from XenServer'

if 'Netscaler' in newBaseTemplate or 'NSVPX' in newBaseTemplate:
    print "Warning: Setting doVirtvtov = False due to Netscaler detected"
    doVirtvtov = False

templateID = c.checkCloudStackName(
    {'csname': newBaseTemplate, 'csApiCall': 'listTemplates'})

message = "Template ID found for %s is %s" % (newBaseTemplate, templateID)
c.print_message(message=message, message_type="Note", to_slack=False)

if templateID == 1 or templateID is None:
    message = "Template with name '%s' can not be found! Halting!" % newBaseTemplate
    c.print_message(message=message, message_type="Error", to_slack=False)
    sys.exit(1)

# Detach any isos
if vm.isoid is not None:
    print "Note: Detaching any connected ISO from vm %s" % vm.name
    c.detach_iso(vm.id)
else:
    print "Note: No ISOs connected to detach"

# Get cluster hosts
kvm_host = c.getRandomHostFromCluster(toClusterID)

# Select storage pool
targetStorage = c.getStoragePoolWithMostFreeSpace(toClusterID)
targetStorageID = targetStorage.id
targetStoragePoolData = c.getStoragePoolData(targetStorageID)[0]
storagepooltags = targetStoragePoolData.tags
storagepoolname = targetStoragePoolData.name

# Get hosts that belong to toCluster
toClusterHostsData = c.getHostsFromCluster(toClusterID)
if DEBUG == 1:
    print "Note: You selected a storage pool with tags '" + str(storagepooltags) + "'"

if vm.hypervisor == "KVM":
    message = "VM %s aka '%s' is already happily running on KVM!" % (vm.instancename, vm.name)
    c.print_message(message=message, message_type="Error", to_slack=False)
    sys.exit(1)

if vm.state == "Running":
    needToStop = True
    autoStartVM = True
    message = "Found vm %s running on %s" % (vm.name, vm.hostname)
    to_slack = True
    if DRYRUN == 1:
        to_slack = False
    c.print_message(message=message, message_type="Note", to_slack=to_slack)

elif vm.state == "Stopped":
    message = "Found vm %s with state %s" % (vm.name, vm.state)
    to_slack = True
    if DRYRUN == 1:
        to_slack = False
    c.print_message(message=message, message_type="Note", to_slack=to_slack)
    needToStop = False
    autoStartVM = False
else:
    message = "Found vm %s with state %s. Needs to be Running or Stopped." % (vm.name, vm.state)
    c.print_message(message=message, message_type="Error", to_slack=False)
    sys.exit(1)

# Volumes
voldata = c.getVirtualmachineVolumes(vmID, projectParam)
saved_storage_id = None
currentStorageID = None

# Migrate its volumes
for vol in voldata:
    # Check if volume is already on correct storage
    currentStorageID = c.checkCloudStackName(
        {'csname': vol.storage, 'csApiCall': 'listStoragePools'})

    if saved_storage_id is None:
        saved_storage_id = currentStorageID

    if currentStorageID == targetStorageID:
        message = "No need to migrate volume %s -- already on the desired storage pool. Skipping." % vol.name
        c.print_message(message=message, message_type="Note", to_slack=False)
        continue

if currentStorageID is None:
    print "Error: Unable to determine the current storage pool of the volumes."
    sys.exit(1)

# Get hosts that belong to toCluster vm is currently running on
currentStorageData = c.getStoragePoolData(currentStorageID)[0]
xenserver_host = c.getRandomHostFromCluster(currentStorageData.clusterid)
currentClusterData = c.listClusters({'clusterid': currentStorageData.clusterid})[0]

c.slack_custom_value = "From %s to %s" % (xenserver_host.name, kvm_host.name.split(".")[0])

# Figure out the tags
sodata = c.listServiceOfferings({'serviceofferingid': vm.serviceofferingid})
if sodata is not None:
    hosttags = (sodata[0].hosttags) if sodata[0].hosttags is not None else ''
    storagetags = (sodata[0].tags) if sodata[0].tags is not None else ''

    message = "Service offering: " + str(sodata[0].name)
    c.print_message(message=message, message_type="Note", to_slack=False)

    if hosttags == '':
        message = "Service offering has empty hosttags."
        c.print_message(message=message, message_type="Note", to_slack=False)

    if hosttags != '' and kvm_host.hosttags != hosttags and c.FORCE == 0:
        if DEBUG == 1:
            print "Error: hosttags of new KVM hypervisor '" + kvm_host + \
                  "' do not match your vm's service offering '" + hosttags
            sys.exit(1)
    elif hosttags != '' and kvm_host.hosttags != hosttags and c.FORCE == 1:
        if DEBUG == 1:
            print "Warning: hosttags of new KVM hypervisor '" + kvm_host + \
                  "' do not match your vm's service offering '" + hosttags + "'. Since you used --FORCE you " \
                  "probably know what you manually need to edit in the database."
    elif DEBUG == 1:
        print "Note: hosttags look OK."

# Stop this vm if it was running
if needToStop:
    if DRYRUN == 1:
        message = "Would have stopped vm %s with id %s" % (vm.name, vm.id)
        c.print_message(message=message, message_type="Note", to_slack=False)
    else:
        message = "Stopping virtualmachine %s with id %s" % (vm.name, vm.id)
        c.print_message(message=message, message_type="Note", to_slack=True)
        result = c.stopVirtualMachine(vm.id)
        if result == 1:
            message = "Stop vm %s failed -- exiting." % vm.name
            c.print_message(message=message, message_type="Error", to_slack=True)
            message = "investigate manually!"
            c.print_message(message=message, message_type="Note", to_slack=False)
            sys.exit(1)

        if result.virtualmachine.state == "Stopped":
            message = "%s is stopped successfully, starting migration" % result.virtualmachine.name
            c.print_message(message=message, message_type="Note", to_slack=True)

        else:
            message = "%s is in state %s instead of Stopped. VM need to be stopped to continue. " \
                      "Re-run script to try again -- exit." % (result.virtualmachine.name, result.virtualmachine.state)
            c.print_message(message=message, message_type="Error", to_slack=True)


# Here we have a stopped VM to work with

# Prepare the folders
if x.prepare_xenserver(xenserver_host) is False:
    sys.exit(1)
if k.prepare_kvm(kvm_host, targetStoragePoolData.id) is False:
    sys.exit(1)
if k.put_scripts(kvm_host) is False:
    sys.exit(1)

# Get all volumes
volumes_result = s.get_volumes_for_instance(vm.instancename)
for (name, path, uuid, size, vmstate, voltype) in volumes_result:
    size_gb = size / 1024 / 1024 / 1024
    message = "Processing volume '%s', filename '%s', uuid '%s', size '%sGB'" % (name, path, uuid, size_gb)
    to_slack = True
    if DRYRUN == 1:
        to_slack = False
    c.print_message(message=message, message_type="Note", to_slack=to_slack)

    if DRYRUN == 1:
        print "Note: Would have extracted, downloaded, converted volume %s " % name
    else:
        if vmstate != "Stopped":
            message = "Volume %s is attached to a VM state %s (should be Stopped). Halting." % (name, vmstate)
            c.print_message(message=message, message_type="Error", to_slack=True)
            message = "Nothing has changed, you can either retry or start the VM on XenServer"
            c.print_message(message=message, message_type="Note", to_slack=False)
            start_vm("XenServer")
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
            message = "Nothing has changed, you can either retry or start the VM on XenServer"
            c.print_message(message=message, message_type="Note", to_slack=False)
            start_vm("XenServer")
            sys.exit(1)
        if k.download_volume(kvm_host, file_to_download, path) is False:
            message = "Downloading volume %s failed" % path
            c.print_message(message=message, message_type="Error", to_slack=True)
            message = "Nothing has changed, you can either retry or start the VM on XenServer"
            c.print_message(message=message, message_type="Note", to_slack=False)
            start_vm("XenServer")
            sys.exit(1)
        message = "Downloading volume %s (name on disk %s) to KVM was successful" % (name, path)
        c.print_message(message=message, message_type="Note", to_slack=False)
        kvmresult = False
        os_family = None
        if voltype == "DATADISK":
            message = "%s is a disk of type %s so skipping virt-v2v and friends" % (name, voltype)
            c.print_message(message=message, message_type="Note", to_slack=False)
            kvmresult = k.make_kvm_compatible(kvm_host, path, False, True)
        elif voltype == "ROOT":
            message = "%s is a disk of type %s" % (name, voltype)
            c.print_message(message=message, message_type="Note", to_slack=False)
            kvmresult = k.make_kvm_compatible(kvm_host, path, doVirtvtov, True)
            message = "For troubleshooting purposes, use this command to edit /etc/fstab (on any hypervisor) " \
                      "of cluster %s: ```virt-edit -a %s /etc/fstab```" % (toCluster, path)
            c.print_message(message=message, message_type="Note", to_slack=to_slack)

        else:
            message = "Found volume %s with unknown type %s. Halting." % (name, voltype)
            c.print_message(message=message, message_type="Error", to_slack=True)
            start_vm("XenServer")
            sys.exit(1)

        if kvmresult is False:
            message = "Making volume %s KVM compatible failed" % path
            c.print_message(message=message, message_type="Error", to_slack=True)
            message = "If using Linux, you could try using --skip-virt-v2v to skip the virt-v2v steps"
            c.print_message(message=message, message_type="Note", to_slack=False)
            message = "Nothing has changed, you can either retry or start the VM on XenServer"
            c.print_message(message=message, message_type="Note", to_slack=False)
            start_vm("XenServer")
            sys.exit(1)
        message = "Converting volume %s to KVM was successful" % path
        c.print_message(message=message, message_type="Note", to_slack=True)


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

# Revery Query
revert_sql = s.generate_revert_query(vm.instancename)

message = "Updating the database to activate the VM on KVM"
c.print_message(message=message, message_type="Note", to_slack=False)

if not s.update_instance_to_kvm(vm.instancename, newBaseTemplate, storagepoolname):
    message = "Updating the database failed"
    c.print_message(message=message, message_type="Error", to_slack=True)
    message = "Nothing has changed, you can either retry or start the VM on XenServer"
    c.print_message(message=message, message_type="Note", to_slack=False)
    start_vm("XenServer")
    sys.exit(1)
else:
    message =  "Note: Should you want to revert, you simply stop the VM on KVM and then run this SQL:"
    c.print_message(message=message, message_type="Note", to_slack=False)
    c.print_message(message="Revert SQL: ```" + revert_sql + "```", message_type="Plain", to_slack=to_slack)

# Start the VM again
if autoStartVM:
    start_vm("KVM")
else:
    message = "Not starting %s automatically because when migration started it was also in Stopped state!" % vm.name
    to_slack = True
    if DRYRUN == 1:
        to_slack = False
    c.print_message(message=message, message_type="Warning", to_slack=to_slack)

# Disconnect MySQL
s.disconnectMySQL()

# End time
message = "Finished @ " + time.strftime("%Y-%m-%d %H:%M")
c.print_message(message=message, message_type="Note", to_slack=False)
elapsed_time = datetime.now() - start_time

m, s = divmod(elapsed_time.total_seconds(), 60)
h, m = divmod(m, 60)

message = "VM %s is successfully migrated to KVM on cluster %s in %02d:%02d:%02d" % (vm.name, toCluster, h, m, s)
c.print_message(message=message, message_type="Note", to_slack=to_slack)
