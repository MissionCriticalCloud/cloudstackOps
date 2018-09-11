#!/usr/bin/env python

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

# Patch KVM hypervisors that are registered in Cosmic
# Remi Bergsma, rbergsma@schubergphilis.com

# We depend on these modules
import sys
import time
from datetime import datetime
import os
import getopt
import getpass
from cloudstackops import cloudstackops, kvm, cloudstackopsssh
# Fabric
from fabric.api import *
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
    global onlyHosts
    onlyHosts = ''
    global onlyHostList
    onlyHostList = ""
    global threads
    threads = 5
    global halt_hypervisor
    halt_hypervisor = False
    global force_reset_hypervisor
    force_reset_hypervisor = False
    global skip_reboot_hypervisor
    skip_reboot_hypervisor = False
    global firmware_reboot_hypervisor
    firmware_reboot_hypervisor = False
    global pre_empty_script
    pre_empty_script = 'kvm_pre_empty_script.sh'
    global post_empty_script
    post_empty_script = 'kvm_post_empty_script.sh'
    global post_reboot_script
    post_reboot_script = 'kvm_post_reboot_script.sh'
    global checkBonds
    checkBonds = True
    global force_out_of_band_live_migration
    force_out_of_band_live_migration = False

    # Usage message
    help = "Usage: ./" + os.path.basename(__file__) + ' [options]' + \
        '\n  --config-profile -c <profilename>\t\tSpecify the CloudMonkey profile name to ' \
        'get the credentials from (or specify in ./config file)' + \
        '\n  --clustername -n <clustername> \t\tName of the cluster to work with' + \
        '\n  --ignore-hosts <list>\t\t\t\tSkip work on the specified hosts (for example if you need to resume): ' \
        'Example: --ignore-hosts="host1, host2" ' + \
        '\n  --only-hosts <list>\t\t\t\tOnly execute work on the specified hosts (for example if you need to resume): ' \
        'Example: --only-hosts="host1, host2" ' + \
        '\n  --threads <nr>\t\t\t\tUse this number or concurrent migration threads ' + \
        '\n  --halt\t\t\t\t\tInstead of the default reboot, halt the hypervisor (useful in case of hardware ' \
        'upgrades) ' + \
        '\n  --force-reset-hypervisor\t\t\tInstead of the default reboot, force-reset the hypervisor (useful in ' \
        'situations where a normal reboot would hang. It will sync filesystems first.) ' + \
        '\n  --skip-reboot-hypervisor\t\t\tInstead of the default reboot, skip the hypervisor reboot (useful in ' \
        'situations where you would only want to live migrate virtual machines in the cluster.) ' + \
        '\n  --upgrade-firmware-reboot\t\t\tInstead of the default reboot, upgrade the HP firmware and reboot the hypervisor' \
        '\n  --pre-empty-script\t\t\t\tBash script to run on hypervisor before starting the live migrations to empty ' \
        'hypervisor (expected in same folder as this script)' + \
        '\n  --post-empty-script\t\t\t\tBash script to run on hypervisor after a hypervisor has no more VMs running' \
        '\n  --post-reboot-script\t\t\t\tBash script to run on hypervisor after a hypervisor has been rebooted' \
        '\n  --no-bond-check\t\t\t\tSkip the bond check' + \
        '\n  --force-out-of-band-live-migration\t\tUse LibVirt to live migrate directly instead of Cosmic' + \
        '\n  --debug\t\t\t\t\tEnable debug mode' + \
        '\n  --exec\t\t\t\t\tExecute for real' + \
        '\n  --prepare\t\t\t\t\tExecute some prepare commands'

    try:
        opts, args = getopt.getopt(
            argv, "hc:n:t:p", [
                "credentials-file=", "clustername=", "ignore-hosts=", "only-hosts=", "threads=", "pre-empty-script=",
                "post-empty-script=", "force-reset-hypervisor", "skip-reboot-hypervisor", "upgrade-firmware-reboot", "no-bond-check", "force-out-of-band-live-migration",
                "halt", "debug", "exec", "post-reboot-script=", "prepare"])
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
        elif opt in ("--only-hosts"):
            onlyHostList = arg
        elif opt in ("--halt"):
            halt_hypervisor = True
        elif opt in ("--force-reset-hypervisor"):
            force_reset_hypervisor = True
        elif opt in ("--skip-reboot-hypervisor"):
            skip_reboot_hypervisor = True
        elif opt in ("--upgrade-firmware-reboot"):
            firmware_reboot_hypervisor = True
        elif opt in ("--force-out-of-band-live-migration"):
            force_out_of_band_live_migration = True
        elif opt in ("--pre-empty-script"):
            pre_empty_script = arg
        elif opt in ("--post-empty-script"):
            post_empty_script = arg
        elif opt in ("--post-reboot-script"):
            post_reboot_script = arg
        elif opt in ("--debug"):
            DEBUG = 1
        elif opt in ("--exec"):
            DRYRUN = 0
        elif opt in ("--prepare"):
            PREPARE = 1
        elif opt in ("--no-bond-check"):
            checkBonds = False

    # Default to cloudmonkey default config file
    if len(configProfileName) == 0:
        configProfileName = "config"

    # Ignore host list
    if len(ignoreHostList) > 0:
        ignoreHosts = ignoreHostList.replace(' ', '').split(",")
    else:
        ignoreHosts = []

    # Only host list
    if len(onlyHostList) > 0:
        onlyHosts = onlyHostList.replace(' ', '').split(",")
    else:
        onlyHosts = []

    # We need at least a cluster name
    if len(clustername) == 0:
        print help
        sys.exit(1)


if __name__ == '__main__':
    handleArguments(sys.argv[1:])

# Init CloudStack class
c = cloudstackops.CloudStackOps(DEBUG, DRYRUN)
ssh = cloudstackopsssh.CloudStackOpsSSH(DEBUG, DRYRUN)
c.ssh = ssh

c.task = "KVM Rolling Reboot"
c.slack_custom_title = "Hypervisor"
c.slack_custom_value = ""
c.instance_name = "N/A"
c.cluster = clustername

# Init XenServer class
k = kvm.Kvm(ssh_user=getpass.getuser(), threads=threads, pre_empty_script=pre_empty_script,
            post_empty_script=post_empty_script, post_reboot_script=post_reboot_script)
k.DRYRUN = DRYRUN
k.PREPARE = PREPARE
c.kvm = k

# make credentials file known to our class
c.configProfileName = configProfileName

# Init the CloudStack API
c.initCloudStackAPI()

# Poolmaster
poolmaster = "n/a"

if DEBUG == 1:
    print "API address: " + c.apiurl
    print "ApiKey: " + c.apikey
    print "SecretKey: " + c.secretkey

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
cluster_hosts = sorted(c.getAllHostsFromCluster(clusterID), key=lambda h: h.name)

# Print cluster info
print "Note: Gathering some info about cluster '" + clustername + "':"
c.printCluster(clusterID, "KVM")

# Put the scripts we need
for host in cluster_hosts:
    k.put_scripts(host)

# Print cluster info
print "Note: Gathering some info about hypervisors in cluster '" + clustername + "':"
c.printHypervisors(clusterID, False, checkBonds, "KVM")

to_slack = True
if DRYRUN == 1:
    to_slack = False

if halt_hypervisor:
    message = "Instead of reboot, we will halt the hypervisors. You need to start it yourself for the script to" \
          " continue moving to the next hypervisor."
    c.print_message(message=message, message_type="Warning", to_slack=to_slack)

if force_reset_hypervisor:
    message = "Instead of reboot, we will force-reset the hypervisors!"
    c.print_message(message=message, message_type="Warning", to_slack=to_slack)

if skip_reboot_hypervisor:
    message = "Skipping the reboot of the hypervisors!"
    c.print_message(message=message, message_type="Warning", to_slack=to_slack)

if firmware_reboot_hypervisor:
    message = "Upgrading HP firmware and rebooting the hypervisor!"
    c.print_message(message=message, message_type="Warning", to_slack=to_slack)

if DRYRUN == 1:
    print
    print "Warning: We are running in DRYRUN mode."
    print
    print "This script will: "
    print "  - For any hypervisor it will do this:"
    print "      - execute the --pre-empty-script script '" + pre_empty_script + "' on the hypervisor"
    print "      - disable the host in Cosmic"
    print "      - live migrate all VMs off of it"
    print "      - execute the --post-empty-script script '" + post_empty_script + "' on the hypervisor"
    print "      - when empty, it will reboot the hypervisor"
    print "        (halting is " + str(halt_hypervisor) + ") and (force_reset is " + str(force_reset_hypervisor) + ")  and (skip_reboot is " + str(skip_reboot_hypervisor) + ") and (firmware_reboot is " + str(firmware_reboot_hypervisor) + ")"
    print "      - will wait for it to come back online (checks SSH connection)"
    print "      - execute the --post-reboot-script script '" + post_reboot_script + "' on the hypervisor"
    print "      - enable the host in Cosmic"
    print "      - waits until host is Connected & Up in Cosmic"
    print "      - continues to the next hypervisor"
    print "Then the reboot cyclus for " + clustername + " is done!"
    print

    # Hosts to ignore
    if len(ignoreHosts) > 0:
        print "Note: Ignoring these hosts: " + str(ignoreHosts)

    if len(onlyHosts) > 0:
        print "Note: Only processing these hosts: " + str(onlyHosts)

    print "To kick it off, run with the --exec flag."
    print
    disconnect_all()
    sys.exit(1)

# Start time
print "Note: Starting @ %s" % time.strftime("%Y-%m-%d %H:%M")
start_time = datetime.now()

# Then the other hypervisors, one-by-one
for host in cluster_hosts:
    c.slack_custom_value = host.name
    if host.name in ignoreHosts:
        message = "Skipping %s due to --ignore-hosts setting" % host.name
        c.print_message(message=message, message_type="Warning", to_slack=False)
        continue

    if len(onlyHosts) > 0 and host.name not in onlyHosts:
        message = "Skipping %s due to --only-hosts setting" % host.name
        c.print_message(message=message, message_type="Warning", to_slack=False)
        continue

    # Execute pre-empty-script
    message = "Processing host %s" % host.name
    c.print_message(message=message, message_type="Note", to_slack=True)

    if k.exec_script_on_hypervisor(host, pre_empty_script) is False:
        message = "Executing script '%s' on host %s failed." % (pre_empty_script, host.name)
        c.print_message(message=message, message_type="Error", to_slack=True)
        sys.exit(1)

    # Start with disabling the host
    if host.resourcestate != "Disabled":
        # Disable host to prevent new VMs landing on it
        if not c.updateHost({'hostid': host.id, 'allocationstate': "Disable"}):
            message = "Disabling host %s failed! Please investigate.." \
                      % (host.name)
            c.print_message(message=message, message_type="Warning", to_slack=True)

        message = "Waiting for host %s to reach Disabled state" % host.name
        c.print_message(message=message, message_type="Note", to_slack=True)

        while True:
            hostData = c.getHostData({'hostid': host.id})
            if hostData[0].resourcestate == "Disabled":
                break
            sys.stdout.write(".")
            sys.stdout.flush()
            time.sleep(5)

    message = "Host %s reached Disabled state" % host.name
    c.print_message(message=message, message_type="Note", to_slack=True)

    running_vms = k.host_get_vms(host)

    message = "Found %s VMs running on host %s. Will now start migrating them to other hosts in the same cluster" % (running_vms, host.name)
    c.print_message(message=message, message_type="Note", to_slack=True)

    # Migrate all vm's and empty hypervisor
    retries = 0
    while not c.emptyHypervisor(host.id, force_out_of_band_live_migration):
        to_slack = False
        if retries == 0:
            to_slack = True
        retries += 1
        message = "Emptying hypervisor %s failed, retrying.." % host.name
        c.print_message(message=message, message_type="Warning", to_slack=to_slack)
        time.sleep(10)
    message = "Emptying hypervisor %s succeeded." % host.name
    c.print_message(message=message, message_type="Note", to_slack=True)

    # Reboot host
    message = "Will execute post_empty scripts, then reboot hypervisor %s" % host.name
    if halt_hypervisor:
        message = "About to halt hypervisor %s. Be sure to start it manually for the procedure to continue!" % host.name
    if force_reset_hypervisor:
        message = "About to force-reset hypervisor %s" % host.name
    if skip_reboot_hypervisor:
        message = "About to skip reboot of hypervisor %s" % host.name
    if firmware_reboot_hypervisor:
        message = "About to upgrade HP firmware and  reboot hypervisor %s" % host.name
    c.print_message(message=message, message_type="Note", to_slack=True)

    if not k.host_reboot(host, halt_hypervisor=halt_hypervisor, force_reset_hypervisor=force_reset_hypervisor, skip_reboot_hypervisor=skip_reboot_hypervisor, firmware_reboot_hypervisor=firmware_reboot_hypervisor):
        message = "Reboot/Halt/Force-reset failed for %s. Please investigate.." % host.name
        c.print_message(message=message, message_type="Error", to_slack=True)
        sys.exit(1)

    message = "Reboot/Halt/Force-reset/Skip-reboot was successful for %s." % host.name
    c.print_message(message=message, message_type="Note", to_slack=True)

    # Enable host
    if not c.updateHost({'hostid': host.id, 'allocationstate': "Enable"}):
        message = "Enabling host %s failed! Please investigate.." \
                  % (host.name)
        c.print_message(message=message, message_type="Warning", to_slack=True)

    # Wait until agent is connected
    message = "Waiting for %s to connect to Cosmic.." % host.name
    c.print_message(message=message, message_type="Note", to_slack=True)

    while True:
        hostData = c.getHostData({'hostid': host.id})
        if hostData[0].resourcestate == "Enabled" and hostData[0].state == "Up":
            break
        sys.stdout.write(".")
        sys.stdout.flush()
        time.sleep(5)

    # Print cluster info
    sys.stdout.write("\033[F")
    message = "Host %s is connected to Cosmic, Enabled and in Up state" % host.name
    c.print_message(message=message, message_type="Note", to_slack=True)

    # Start all VM's with migration policy ShutdownAndStart
    message = "Starting all VM's on Host %s with ShutdownAndStart policy" % host.name
    c.print_message(message=message, message_type="Note", to_slack=True)
    c.startVmsWithShutPolicy()

    message = "Gathering some info about hypervisors in cluster '%s'" % clustername
    c.print_message(message=message, message_type="Note", to_slack=False)
    c.printHypervisors(clusterID, False, checkBonds, "KVM")

# Print cluster info
message = "Some info about cluster '" + clustername + "':"
c.print_message(message=message, message_type="Note", to_slack=False)
c.printCluster(clusterID, "KVM")

# Disconnect
disconnect_all()

# Done
# End time
message = "Finished @ " + time.strftime("%Y-%m-%d %H:%M")
c.print_message(message=message, message_type="Note", to_slack=False)
elapsed_time = datetime.now() - start_time

message = "We're done with cluster %s. Rebooting cluster took %s seconds." % (clustername,
                                                                              str(elapsed_time.total_seconds()))
c.print_message(message=message, message_type="Note", to_slack=True)
