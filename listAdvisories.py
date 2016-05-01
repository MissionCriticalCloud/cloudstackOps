#!/usr/bin/python

#      Copyright 2016, Leaseweb Technologies BV
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

# Script to list potential fixes.
# Nuno Tavares - n.tavares@tech.leaseweb.com

import time
import sys
import getopt
from cloudstackops import lswcloudstackopsbase
from cloudstackops import lswcloudstackops
from cloudstackops import lswcloudstackopsssh
import os.path
from random import choice
from prettytable import PrettyTable

# Function to handle our arguments

def debug(level, args):
    if DEBUG>=level:
        print args

opFilters = { 'safetylevel': lswcloudstackops.LswCloudStackOps.SAFETY_BEST, 'deep': False, 'live': False }
    
def handleArguments(argv):
    global DEBUG
    DEBUG = 0
    global DRYRUN
    DRYRUN = 1
    global configProfileName
    configProfileName = ''
    global command
    command = 'list'
    global plainDisplay
    plainDisplay = 0
    global PLATFORM
    PLATFORM = None
    global SEND_EMAIL
    SEND_EMAIL = False

    # Usage message
    help = "Usage: ./" + os.path.basename(__file__) + ' [options] ' + \
        '\n  --config-profile -c <profile>\t\tSpecify the CloudMonkey profile name to get the credentials from (or specify in ./config file)' + \
        '\n  --plain-display\t\t\tEnable plain display, no pretty tables' + \
        '\n  --repair\t\t\t\tApply suggested actions - at Safe/Best level' + \
        '\n' + \
        '\n  Modifiers:' + \
        '\n  --exec\tDisable dry-run mode. You\'l need this to perform changes to the platform.' + \
        '\n  --debug\tEnable debug mode. Use it multiple times to increase verbosity' + \
        '\n  --live\tPerform live scan. By default, quick mode is used (using deferred/cached collection methods)' + \
        '\n  --deep\tEnable further tests that usually produces a lot of results. For a list of tests, use -h with this option' + \
        '\n  --email\tSend Repair Report by email' + \
        '\n' + \
        '\n  Filters:' + \
        '\n  -n \t\tScan networks (incl. VPCs)' + \
        '\n  -r \t\tScan routerVMs' + \
        '\n  -i \t\tScan instances' + \
        '\n  -H \t\tScan hypervisors' + \
        '\n  -t \t\tScan resource usage' + \
        '\n  --all \tReport all assets of the selected types, independently of the presence of advisory' + \
        '\n  --safety <safety> \tFilter out advisories that are not at the specified safety level (default: ' + lswcloudstackopsbase.LswCloudStackOpsBase.translateSafetyLevel(opFilters['safetylevel']) + ')'

    try:
        opts, args = getopt.getopt(
            argv, "hc:nriHt", [
                "config-profile=", "debug", "exec", "deep", "live", "plain-display", "all", "repair", "safety=", 'email' ])
    except getopt.GetoptError as e:
        print "Error: " + str(e)
        print help
        sys.exit(2)

    if len(opts) == 0:
        print help
        sys.exit(2)

    helpRequested = False
    for opt, arg in opts:
        if opt == '-h':
            helpRequested = True
        elif opt in ("-c", "--config-profile"):
            configProfileName = arg
            PLATFORM = configProfileName
        elif opt in ("--debug"):
            if DEBUG==2:
                DEBUG = 1
            else:
                DEBUG = 2
        elif opt in ["--exec"]:
            DRYRUN = 0
        elif opt in ["--email"]:
            SEND_EMAIL = True
        elif opt in ["--repair"]:
            command = 'repair'
        elif opt in ["--live"]:
            opFilters['live'] = True
        elif opt in ["--deep"]:
            opFilters['deep'] = True
        elif opt in ["--plain-display"]:
            plainDisplay = 1
        elif opt in ["-n"]:
            opFilters['networks'] = True
        elif opt in ["-r"]:
            opFilters['routers'] = True
        elif opt in ["-i"]:
            opFilters['instances'] = True
        elif opt in ["-H"]:
            opFilters['host'] = True
        elif opt in ["--t"]:
            opFilters['resources'] = True
        elif opt in ["--all"]:
            opFilters['all'] = True
        elif opt in ["--safety"]:
            safety = lswcloudstackopsbase.LswCloudStackOpsBase.translateSafetyLevelString(arg)
            if safety != None:
                opFilters['safetylevel'] = safety
                opFilters['safetylevel_set'] = True

    def printHelpTests():
        print
        print "List of tests available"
        t = PrettyTable(["Scope", "Level", "Symptom / Probe / Detection", "Detection", "Recovery"])
        t.align["Symptom / Probe / Detection"] = "l"
        
        if plainDisplay == 1:
            t.border = False
            t.header = False
            t.padding_width = 1

        t.add_row([ "network", "Normal", "Flag restart_required", True, True ])
        t.add_row([ "network", "Normal", "Redundancy state inconsistency (needs -r)", True, True ])
        t.add_row([ "router", "Normal", "Redundancy state", True, True ])
        t.add_row([ "router", "Normal", "Output of check_router.sh is non-zero (dmesg,swap,resolv,ping,fs,disk,password)", True, True ])
        t.add_row([ "router", "Normal", "Checks if router has requiresUpgrade flag on", True, True ])
        t.add_row([ "router", "Deep", "Checks if router is running on the current systemvm template version", True, True ])
        t.add_row([ "router", "Deep", "Checks if router is based on the same package version than management (router.cloudstackversion)", True, True ])
        t.add_row([ "instance", "Normal", "Try to assess instance read-only state", True, False ])
        t.add_row([ "instance", "Normal", "Queries libvirt usage records for abusers (CPU, I/O, etc)", True, False ])
        t.add_row([ "hypervisor", "Normal", "Agent state (version, conn state)", True, False ])
        t.add_row([ "hypervisor", "Normal", "Load average", True, False ])
        t.add_row([ "hypervisor", "Normal", "Conntrack abusers", True, False ])
        t.add_row([ "hypervisor", "Normal", "check_libvirt_storage.sh correct functioning", True, False ])

        print t
        
    if helpRequested:
        if opFilters['deep']:
            printHelpTests()
        else:
            print help
        sys.exit()

    if PLATFORM==None:
        print "No platform is specified. Please use the -c option."
        sys.exit(1)

    # Default to cloudmonkey default config file
    if len(configProfileName) == 0:
        configProfileName = "config"

# Parse arguments
if __name__ == "__main__":
    handleArguments(sys.argv[1:])
    debug(2, 'Command line args: ' + str(sys.argv))

# Init our class
c = lswcloudstackops.LswCloudStackOps(DEBUG, DRYRUN)
ssh = lswcloudstackopsssh.LswCloudStackOpsSSH(DEBUG, DRYRUN)
c.ssh = ssh
c.assignSshObject(ssh)
c.setManagementServer( "mgt01." + PLATFORM )
c.setFilters(opFilters)


if DEBUG > 0:
    print "# Warning: Debug mode is enabled!"

if DRYRUN == 1:
    print "# Warning: dry-run mode is enabled, not running any commands!"

# make credentials file known to our class
c.configProfileName = configProfileName

# Init the CloudStack API
c.initCloudStackAPI()

if DEBUG == 1:
    print "API address: " + c.apiurl
    print "ApiKey: " + c.apikey
    print "SecretKey: " + c.secretkey

#
# TODO : examine conntrack







def cmdListAdvisories():

    results = c.getAdvisories()

#    import pprint
#    pp = pprint.PrettyPrinter(indent=4)
#    pp.pprint(networkData)
    
    # Empty line
    print
    t = PrettyTable(["#", "Platf", "Type", "Name", "ID", "Domain", "Action", "SafetyLevel", "Comment"])
    t.align["Comment"] = "l"
    
    if plainDisplay == 1:
        t.border = False
        t.header = False
        t.padding_width = 1

    counter = 0
    for a in results:
        counter = counter + 1
        t.add_row([counter, configProfileName, a['asset_type'], a['name'], a['id'], a['domain'], a['adv_action'], lswcloudstackopsbase.LswCloudStackOpsBase.translateSafetyLevel(a['adv_safetylevel']), a['adv_comment']])

    # Display table
    print t

    if SEND_EMAIL and counter>0:
        if not c.errors_to:
            print "Warning: Skipping mailing due to missing e-mail address."

        templatefile = open(
            "email_template/advisoriesReport.txt",
            "r")
        emailbody = templatefile.read()
        emailbody = emailbody.replace("PLATFORM", PLATFORM)
        emailbody = emailbody.replace("ADVISORIES_REPORT", str(t))
        emailbody = emailbody.replace("COMMAND_LINE", str(sys.argv))
        templatefile.close()

        msgSubject = '[' + PLATFORM + '] listAdvisories Report'

        # Notify admin
        c.sendMail(c.mail_from, c.errors_to, msgSubject, emailbody)



def cmdRepair():
    debug(2, "cmdRepair : begin")
    results = c.runRepair()

    print
    t = PrettyTable(["#", "Type", "Name", "ID", "Domain", "Action", "Result", "Comment"])
    t.align["Comment"] = "l"
    
    if plainDisplay == 1:
        t.border = False
        t.header = False
        t.padding_width = 1

    counter = 0
    for a in results:
        counter = counter + 1
        t.add_row([counter, a['asset_type'], a['name'], a['id'], a['domain'], a['adv_action'], a['repair_code'], a['repair_msg']])
    print t

    if SEND_EMAIL and counter>0:
        if not c.errors_to:
            print "Warning: Skipping mailing due to missing e-mail address."

        templatefile = open(
            "email_template/advisoriesRepairReport.txt",
            "r")
        emailbody = templatefile.read()
        emailbody = emailbody.replace("PLATFORM", PLATFORM)
        emailbody = emailbody.replace("REPAIR_REPORT", str(t))
        emailbody = emailbody.replace("COMMAND_LINE", str(sys.argv))
        templatefile.close()

        msgSubject = '[' + PLATFORM + '] listAdvisories Repair Report'

        # Notify admin
        c.sendMail(c.mail_from, c.errors_to, msgSubject, emailbody)

    debug(2, "cmdRepair : end")

print "Applying filter: safetylevel == %s" % lswcloudstackopsbase.LswCloudStackOpsBase.translateSafetyLevel(opFilters['safetylevel'])

if command == 'list':
    cmdListAdvisories()
elif command == 'repair':
    cmdRepair()  
