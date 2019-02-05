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

# Script to update the host tags
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
    global hostname
    hostname = ''
    global configProfileName
    configProfileName = ''
    global replace
    replace = 0
    global newTags
    newTags = ''

    # Usage message
    help = "Usage: ./" + os.path.basename(__file__) + ' [options] ' + \
        '\n  --config-profile -c <profilename>\tSpecify the CloudMonkey profile name to get the credentials from (or specify in ./config file)' + \
        '\n  --hostname -n <hostname>\t\tWork with this hypervisor' + \
        '\n  --tags -t <tags>\t\t\tAdd these tags (can be comma separated list, without spaces). Use \' \' to set empty.' + \
        '\n  --replace\t\t\t\tReplace all tags with the one(s) specified' + \
        '\n  --debug\t\t\t\tEnable debug mode' + \
        '\n  --exec\t\t\t\tExecute for real'

    try:
        opts, args = getopt.getopt(
            argv, "hc:n:t:r", [
                "config-profile=", "hostname=", "tags=", "debug", "exec", "replace"])
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
        elif opt in ("-n", "--hostname"):
            hostname = arg
        elif opt in ("-t", "--tags"):
            newTags = arg
        elif opt in ("--debug"):
            DEBUG = 1
        elif opt in ("--exec"):
            DRYRUN = 0
        elif opt in ("--replace"):
            replace = 1

    # Default to cloudmonkey default config file
    if len(configProfileName) == 0:
        configProfileName = "config"

    # We need at least these vars
    if len(hostname) == 0 or len(newTags) == 0:
        print(help)
        sys.exit()

# Parse arguments
if __name__ == "__main__":
    handleArguments(sys.argv[1:])

# Init our class
c = cloudstackops.CloudStackOps(DEBUG, DRYRUN)

if DEBUG == 1:
    print("Warning: Debug mode is enabled!")

if DRYRUN == 1:
    print("Warning: dry-run mode is enabled, not running any commands!")

# make credentials file known to our class
c.configProfileName = configProfileName

# Init the CloudStack API
c.initCloudStackAPI()

if DEBUG == 1:
    print("DEBUG: API address: " + c.apiurl)
    print("DEBUG: ApiKey: " + c.apikey)
    print("DEBUG: SecretKey: " + c.secretkey)

# Check cloudstack IDs
if DEBUG == 1:
    print("DEBUG: Checking CloudStack IDs of provided input..")

# check hostID
hostID = c.checkCloudStackName({'csname': hostname, 'csApiCall': 'listHosts'})

# get router data
if hostID == 1 or hostID is None:
    print("Error: could not locate ID.")
    sys.exit()
if DEBUG == 1:
    print("DEBUG: Found host with id " + str(hostID))

hostData = c.getHostData({'hostid': hostID})

if DEBUG == 1:
    print(hostData)

# current tags
if hostData[0].hosttags is None:
    currentTags = ''
    comma = ''
    print("Note: Hosttags are currently set to '" + currentTags + "'")
else:
    currentTags = hostData[0].hosttags
    comma = ', '
    print("Note: Hosttags are currently set to '" + currentTags + "'")

# Construct new tags
if replace == 1:
    updatedTags = newTags
else:
    updatedTags = currentTags + comma + newTags

print("Note: Hosttags will be set to '" + updatedTags + "'")

# Update host tags
if DRYRUN == 1:
    print("Note: Would have updated tags to '" + updatedTags + "'")
else:
    result = c.updateHostTags(hostID, updatedTags)
    if result == 1:
        print("Error: updating failed")
    else:
        print("Note: updating was succesful")
