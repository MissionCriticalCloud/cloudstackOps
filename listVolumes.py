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

# Script to list all volumes in a given storage pool
# Remi Bergsma - rbergsma@schubergphilis.com

import time
import sys
import getopt
from cloudstackops import cloudstackops
import os.path
from random import choice
from prettytable import PrettyTable

# Function to handle our arguments


def handleArguments(argv):
    global DEBUG
    DEBUG = 0
    global DRYRUN
    DRYRUN = 0
    global domainname
    domainname = ''
    global configProfileName
    configProfileName = ''
    global storagepoolname
    storagepoolname = ''
    global isProjectVm
    isProjectVm = 0

    # Usage message
    help = "Usage: ./" + os.path.basename(__file__) + ' [options] ' + \
        '\n  --config-profile -c <profilename>\t\tSpecify the CloudMonkey profile name to get the credentials from (or specify in ./config file)' + \
        '\n  --storagepoolname -p <storage pool name>\tList volumes from this storage pool' + \
        '\n  --is-projectvm\t\t\t\tLimit search to volumes that belong to a project' + \
        '\n  --debug\t\t\t\t\tEnable debug mode' + \
        '\n  --exec\t\t\t\t\tExecute for real (not needed for list* scripts)'

    try:
        opts, args = getopt.getopt(
            argv, "hc:p:", [
                "config-profile=", "storagepoolname=", "debug", "exec", "is-projectvm"])
    except getopt.GetoptError as e:
        print("Error: " + str(e))
        print(help)
        sys.exit(2)

    if len(opts) == 0:
        print(help)
        sys.exit(2)

    for opt, arg in opts:
        if opt == '-h':
            print(help)
            sys.exit()
        elif opt in ("-c", "--config-profile"):
            configProfileName = arg
        elif opt in ("-p", "--storagepoolname"):
            storagepoolname = arg
        elif opt in ("--debug"):
            DEBUG = 1
        elif opt in ("--exec"):
            DRYRUN = 0
        elif opt in ("--is-projectvm"):
            isProjectVm = 1

    # Default to cloudmonkey default config file
    if len(configProfileName) == 0:
        configProfileName = "config"

    # We need at least these vars
    if len(storagepoolname) == 0:
        print(help)
        sys.exit()

# Parse arguments
if __name__ == "__main__":
    handleArguments(sys.argv[1:])

# Handle project parameter
if isProjectVm == 1:
    projectParam = "true"
else:
    projectParam = "false"

# Init our class
c = cloudstackops.CloudStackOps(DEBUG, DRYRUN)

if DEBUG == 1:
    print("# Warning: Debug mode is enabled!")

if DRYRUN == 1:
    print("# Warning: dry-run mode is enabled, not running any commands!")

# make credentials file known to our class
c.configProfileName = configProfileName

# Init the CloudStack API
c.initCloudStackAPI()

if DEBUG == 1:
    print("API address: " + c.apiurl)
    print("ApiKey: " + c.apikey)
    print("SecretKey: " + c.secretkey)

# Check cloudstack IDs
if DEBUG == 1:
    print("Checking CloudStack IDs of provided input..")
if len(storagepoolname) > 1:
    storagepoolID = c.checkCloudStackName(
        {'csname': storagepoolname, 'csApiCall': 'listStoragePools'})

# Get volumes from storage pool
volumesData = c.listVolumes(storagepoolID, projectParam)

# Empty line
print()
t = PrettyTable(["VM name", "Volume name", "Instance name", "Volume path"])
t.align["VM"] = "l"

counter = 0

for volume in volumesData:
    counter = counter + 1

    # Attached?
    if volume.vmname is None:
        vmname = instancename = "NotAttached"
    else:
        vmname = (
            volume.vmname[:20] +
            '..') if len(
            volume.vmname) >= 22 else volume.vmname
        virtualmachineData = c.getVirtualmachineData(volume.virtualmachineid)
        vm = virtualmachineData[0]
        instancename = vm.instancename

    # Table
    t.add_row([vmname, volume.name, instancename, volume.path + ".vhd"])

# Display table
print(t)

if DEBUG == 1:
    print("Note: We're done!")
