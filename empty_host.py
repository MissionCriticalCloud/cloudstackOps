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

# Script to empty/live migrate a HV to other HV in the same cluster
# Daan de Goede

import sys
import getopt
from cloudstackops import cloudstackops
from cloudstackops import cloudstacksql
from cloudstackops import kvm
import os.path
from datetime import datetime
import time
import liveMigrateVirtualMachine as lmvm

# Function to handle our arguments


def handleArguments(argv):
    global DEBUG
    DEBUG = 0
    global DRYRUN
    DRYRUN = 1
    global fromHV
    fromHV = ''
    global configProfileName
    configProfileName = ''
    global force
    force = 0

    # Usage message
    help = "Usage: ./" + os.path.basename(__file__) + ' [options] ' + \
        '\n  --config-profile -c <profilename>\tSpecify the CloudMonkey profile name to get the credentials from (or specify in ./config file)' + \
        '\n  --hypervisor -h <name>\t\tHypervisor to migrate' + \
        '\n  --debug\t\t\t\tEnable debug mode' + \
        '\n  --exec\t\t\t\tExecute for real'

    try:
        opts, args = getopt.getopt(
            argv, "c:h:", [
                "config-profile=", "hypervisor=", "debug", "exec", "force"])
    except getopt.GetoptError as e:
        print "Error: " + str(e)
        print help
        sys.exit(2)
    for opt, arg in opts:
        if opt == '--help':
            print help
            sys.exit()
        elif opt in ("-c", "--config-profile"):
            configProfileName = arg
        elif opt in ("-h", "--hypervisor"):
            fromHV = arg
        elif opt in ("--debug"):
            DEBUG = 1
        elif opt in ("--exec"):
            DRYRUN = 0
        elif opt in ("--force"):
            force = 1

    # Default to cloudmonkey default config file
    if len(configProfileName) == 0:
        configProfileName = "config"

    # We need at least these vars
    if len(fromHV) == 0:
        print help
        sys.exit()

def emptyHV(DEBUG=0, DRYRUN=1, fromHV='', configProfileName='', force=0):
    # Init our class
    c = cloudstackops.CloudStackOps(DEBUG, DRYRUN)
    c.task = "empty HV"
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

    # Check hypervisor parameter
    if DEBUG == 1:
        print "Note: Checking host ID of provided hypervisor.."

    host = c.getHostByName(name=fromHV)
    if not host or len(host) == 0 or host['count'] != 1:
        print "hypervisor parameter ('" + fromHV + "') resulted in zero or more than one hypervisors!"
        sys.exit(1)

    if DEBUG == 1:
        print host

    hostid = host['host'][0]['id']
    listVMs = c.listVirtualMachines({'hostid': hostid, 'listall': 'true'})
    listProjectVMs = c.listVirtualMachines({'hostid': hostid, 'listall': 'true', 'projectid': -1})
    listRouterVMs = c.listRouters({'hostid': hostid, 'listall': 'true'})

    userVMs = {}
    userVMs['count'] = listVMs.get('count',0) + listProjectVMs.get('count',0)
    userVMs['virtualmachine'] = listVMs.get('virtualmachine',[]) + listProjectVMs.get('virtualmachine',[])
    if DEBUG == 1:
        print userVMs
        print listRouterVMs
    vmCount = 1
    vmTotal = userVMs.get('count',0)
    print "found " + str(vmTotal) + " virtualmachines and " + str(listRouterVMs.get('count',0)) + " routerVMs on hypervisor: " + fromHV
    c.emptyHypervisor(hostid)

    result = True
    listVMs = c.listVirtualMachines({'hostid': hostid, 'listall': 'true'})
    listProjectVMs = c.listVirtualMachines({'hostid': hostid, 'listall': 'true', 'projectid': -1})
    listRouterVMs = c.listRouters({'hostid': hostid, 'listall': 'true'})
    
    vmCount = listVMs.get('count',0) + listProjectVMs.get('count',0) + listRouterVMs.get('count',0)
    if vmCount > 0:
        result = False

    # End time
    message = "Finished @ " + time.strftime("%Y-%m-%d %H:%M")
    c.print_message(message=message, message_type="Note", to_slack=False)
    elapsed_time = datetime.now() - start_time

    if result:
        print "HV %s is successfully migrated in %s seconds" % (fromHV, elapsed_time.total_seconds())
    else:
        print "HV %s has failed to migrate in %s seconds, %s of %s remaining." % (fromHV, elapsed_time.total_seconds(), vmCount, vmTotal)

# Parse arguments
if __name__ == "__main__":
    handleArguments(sys.argv[1:])
    emptyHV(DEBUG, DRYRUN, fromHV, configProfileName, force)