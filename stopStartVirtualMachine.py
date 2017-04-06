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

# Script to stop/start a VM
# Remi Bergsma - rbergsma@schubergphilis.com

import sys
import getopt
from cloudstackops import cloudstackops
import os.path

# Function to handle our arguments


def handleArguments(argv):
    global DEBUG
    DEBUG = 0
    global DRYRUN
    DRYRUN = 1
    global vmname
    vmname = ''
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
        '\n  --instance-name -i <instancename>\tStop/Start VM with this instance name (i-123-12345-VM)' + \
        '\n  --is-projectvm\t\t\tThis VMs belongs to a project' + \
        '\n  --debug\t\t\t\tEnable debug mode' + \
        '\n  --exec\t\t\t\tExecute for real'

    try:
        opts, args = getopt.getopt(
            argv, "hc:n:i:p", [
                "config-profile=", "vmname=", "instance-name=", "debug", "exec", "is-projectvm", "force"])
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
    if len(vmname) == 0:
        print help
        sys.exit()

# Parse arguments
if __name__ == "__main__":
    handleArguments(sys.argv[1:])

# Init our class
c = cloudstackops.CloudStackOps(DEBUG, DRYRUN)
c.task = "Stop/Start VM"
c.slack_custom_title = "Domain"
c.slack_custom_value = ""

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
# Get data from vm
vmdata = c.getVirtualmachineData(vmID)
if vmdata is None:
    print "Error: Could not find vm " + vmname + "!"
    sys.exit(1)
vm = vmdata[0]
c.instance_name = vm.name
c.slack_custom_value = vm.domain


if vm.state != "Running":
    message = "Error: VM %s is in state %s, can only stop/start when in state Running. Skipping this vm!" % (vmname, vm.state)
    c.print_message(message=message, message_type="Error", to_slack=to_slack)
    sys.exit(1)

clusterData = c.listClusters({'id': vm.clusterid})
c.cluster = clusterData[0].name

# Get user data to e-mail
adminData = c.getDomainAdminUserData(vm.domainid)
if DRYRUN == 1:
    print "Note: Not sending notification e-mails due to DRYRUN setting. Would have e-mailed " + adminData.email
else:

    if not adminData.email:
        print "Warning: Skipping mailing due to missing e-mail address."

    templatefile = open(
        "email_template/stopStartVirtualMachine_start.txt",
        "r")
    emailbody = templatefile.read()
    emailbody = emailbody.replace("FIRSTNAME", adminData.firstname)
    emailbody = emailbody.replace("LASTNAME", adminData.lastname)
    emailbody = emailbody.replace("DOMAIN", vm.domain)
    emailbody = emailbody.replace("VMNAME", vm.name)
    emailbody = emailbody.replace("STATE", vm.state)
    emailbody = emailbody.replace("INSTANCENAME", vm.instancename)
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
if DRYRUN == 1:
    print "Would have stopped vm " + vm.name + " with id " + vm.id
else:
    message = "Executing: stop virtualmachine " + vm.name + " with id " + vm.id
    c.print_message(message=message, message_type="Note", to_slack=to_slack)
    result = c.stopVirtualMachine(vm.id)
    if result == 1:
        message = "Stop vm failed -- exiting. Investigate manually!"
        c.print_message(message=message, message_type="Error", to_slack=to_slack)

        # Notify admin
        msgSubject = 'Warning: problem with maintenance for vm ' + \
            vm.name + ' / ' + vm.instancename
        emailbody = "Could not stop vm " + vm.name
        c.sendMail(c.mail_from, c.errors_to, msgSubject, emailbody)
        sys.exit(1)

    if result.virtualmachine.state == "Stopped":
        message = result.virtualmachine.name + " is stopped successfully "
        c.print_message(message=message, message_type="Note", to_slack=to_slack)
    else:
        message = result.virtualmachine.name + " is in state " + result.virtualmachine.state + " instead of Stopped. " \
                                                                                               "VM need to be stopped to continue. Re-run script to try again -- exit."
        c.print_message(message=message, message_type="Error", to_slack=to_slack)

        # Notify admin
        msgSubject = 'Warning: problem with maintenance for VM ' + \
            vm.name + ' / ' + vm.instancename
        emailbody = 'Could not stop VM ' + vm.name
        c.sendMail(c.mail_from, c.errors_to, msgSubject, emailbody)
        sys.exit(1)

# Start the VM again
if DRYRUN == 1:
    print "Would have started vm " + vm.name + " with id " + vm.id
else:
    message = "Executing: start virtualmachine " + vm.name + " with id " + vm.id
    c.print_message(message=message, message_type="Note", to_slack=to_slack)
    result = c.startVirtualMachine(vm.id)
    if result == 1:
        message = "Start vm failed -- exiting. Investigate manually!"
        c.print_message(message=message, message_type="Error", to_slack=to_slack)

        # Notify admin
        msgSubject = 'Warning: problem with maintenance for vm ' + \
            vm.name + ' / ' + vm.instancename
        emailbody = "Could not start vm " + vm.name
        c.sendMail(c.mail_from, c.errors_to, msgSubject, emailbody)
        sys.exit(1)

    if result.virtualmachine.state == "Running":
        message = result.virtualmachine.name + " is started successfully "
        c.print_message(message=message, message_type="Note", to_slack=to_slack)
        # Get user data to e-mail
        adminData = c.getDomainAdminUserData(vm.domainid)
        if DRYRUN == 1:
            print "Note: Not sending notification e-mails due to DRYRUN setting. Would have e-mailed " + adminData.email
        else:

            if not adminData.email:
                print "Warning: Skipping mailing due to missing e-mail address."

            templatefile = open(
                "email_template/stopStartVirtualMachine_done.txt",
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
        message = "Warning: " + result.virtualmachine.name + " is in state " + \
            result.virtualmachine.state + " instead of Started. Please investigate (could just take some time)."
        c.print_message(message=message, message_type="Error", to_slack=to_slack)

        # Notify admin
        msgSubject = 'Warning: problem with maintenance for VM ' + \
            vm.name + ' / ' + vm.instancename
        emailbody = message
        c.sendMail(c.mail_from, c.errors_to, msgSubject, emailbody)

print "Note: We're done!"
