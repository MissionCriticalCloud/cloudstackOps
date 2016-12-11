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

# Script to upgrade a router VM to the new template
# Remi Bergsma - rbergsma@schubergphilis.com

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
    global onlyRequired
    onlyRequired = 0

    # Usage message
    help = "Usage: ./" + os.path.basename(__file__) + ' [options] ' + \
        '\n  --config-profile -c <profilename>\tSpecify the CloudMonkey profile name to get the credentials from (or specify in ./config file)' + \
        '\n  --routerinstance-name -r <name>\tWork with this router (r-12345-VM)' + \
        '\n  --is-projectrouter\t\t\tThe specified router belongs to a project' + \
        '\n  --only-when-required\t\t\tOnly reboot when the RequiresUpgrade flag is set' + \
        '\n  --debug\t\t\t\tEnable debug mode' + \
        '\n  --exec\t\t\t\tExecute for real'

    try:
        opts, args = getopt.getopt(
            argv, "hc:r:p", [
                "config-profile=", "routerinstance-name=", "debug", "exec", "is-projectrouter", "only-when-required"])
    except getopt.GetoptError:
        print help
        sys.exit(2)
    for opt, arg in opts:
        if opt == '-h':
            print help
            sys.exit()
        elif opt in ("-c", "--config-profile"):
            configProfileName = arg
        elif opt in ("-r", "--routerinstance-name"):
            vmname = arg
        elif opt in ("--debug"):
            DEBUG = 1
        elif opt in ("--exec"):
            DRYRUN = 0
        elif opt in ("--is-projectrouter"):
            isProjectVm = 1
        elif opt in ("--only-when-required"):
            onlyRequired = 1

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

if DEBUG == 1:
    print "Warning: Debug mode is enabled!"

if DRYRUN == 1:
    print "Warning: dry-run mode is enabled, not running any commands!"

# make credentials file known to our class
c.configProfileName = configProfileName

# Init the CloudStack API
c.initCloudStackAPI()

if DEBUG == 1:
    print "DEBUG: API address: " + c.apiurl
    print "DEBUG: ApiKey: " + c.apikey
    print "DEBUG: SecretKey: " + c.secretkey

# Check cloudstack IDs
if DEBUG == 1:
    print "DEBUG: Checking CloudStack IDs of provided input.."

if isProjectVm == 1:
    projectParam = "true"
else:
    projectParam = "false"

# check routerID
routerID = c.checkCloudStackName({'csname': vmname,
                                  'csApiCall': 'listRouters',
                                  'listAll': 'true',
                                  'isProjectVm': projectParam})

# get router data
routerData = c.getRouterData({'name': vmname, 'isProjectVm': projectParam})
router = routerData[0]

if DEBUG == 1:
    print routerData

print "Note: Found router " + router.name + " that belongs to account " + str(router.account) + " with router ID " + router.id
print "Note: This router has " + str(len(router.nic)) + " nics."

# Does this router need an upgrade?
if onlyRequired == 1 and router.requiresupgrade == 0:
    print "Note: This router does not need to be upgraded. Won't reboot because of --only-when-required flag. When you remove the flag and run the script again it will reboot anyway."
    sys.exit(0)

print "Note: Let's reboot the router VM.."

# Get user data to e-mail
adminData = c.getDomainAdminUserData(router.domainid)
if DRYRUN == 1:
    print "Note: Not sending notification e-mails due to DRYRUN setting. Would have e-mailed " + adminData.email
else:

    if not adminData.email:
        print "Warning: Skipping mailing due to missing e-mail address."

    templatefile = open("email_template/rebootRouterVM.txt", "r")
    emailbody = templatefile.read()
    emailbody = emailbody.replace("FIRSTNAME", adminData.firstname)
    emailbody = emailbody.replace("LASTNAME", adminData.lastname)
    emailbody = emailbody.replace("ROUTERDOMAIN", router.domain)
    emailbody = emailbody.replace("ROUTERNAME", router.name)
    emailbody = emailbody.replace("ORGANIZATION", c.organization)
    templatefile.close()

    # Notify user
    msgSubject = 'Starting maintenance for domain ' + router.domain
    c.sendMail(c.mail_from, adminData.email, msgSubject, emailbody)

    # Notify admin
    c.sendMail(c.mail_from, c.errors_to, msgSubject, emailbody)

    if DEBUG == 1:
        print emailbody

# Reboot router
if DRYRUN == 1:
    print "Note: Would have rebooted router " + router.name + " (" + router.id + ")"
else:
    print "Executing: reboot router " + router.name + " (" + router.id + ")"
    result = c.rebootRouter(router.id)
    if result == 1:
        print "Rebooting failed, will try again!"
        result = c.rebootRouter(router.id)
        if result == 1:
            print "Rebooting failed again -- exiting."
            print "Error: investegate manually!"

            # Notify admin
            msgSubject = 'Warning: problem with maintenance for domain ' + \
                router.domain
            emailbody = "Could not reboot router " + router.name
            c.sendMail(c.mail_from, c.errors_to, msgSubject, emailbody)
            sys.exit(1)

# Get user data to e-mail
if DRYRUN == 1:
    print "Note: Not sending notification e-mails due to DRYRUN setting. Would have e-mailed " + adminData.email
else:

    if not adminData.email:
        print "Warning: Skipping mailing due to missing e-mail address."

    templatefile = open("email_template/rebootRouterVM_done.txt", "r")
    emailbody = templatefile.read()
    emailbody = emailbody.replace("FIRSTNAME", adminData.firstname)
    emailbody = emailbody.replace("LASTNAME", adminData.lastname)
    emailbody = emailbody.replace("ROUTERDOMAIN", router.domain)
    emailbody = emailbody.replace("ROUTERNAME", router.name)
    emailbody = emailbody.replace("ORGANIZATION", c.organization)
    templatefile.close()

    # Notify user
    msgSubject = 'Completed maintenance for domain ' + router.domain
    c.sendMail(c.mail_from, adminData.email, msgSubject, emailbody)

    # Notify admin
    c.sendMail(c.mail_from, c.errors_to, msgSubject, emailbody)

    if DEBUG == 1:
        print "DEBUG: email body:"
        print emailbody

print "Note: We're done!"
