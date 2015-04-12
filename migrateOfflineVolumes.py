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

# Script to migrate offline volumes to a new storage
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
    DRYRUN = 1
    global fromCluster
    fromCluster = ''
    global toCluster
    toCluster = ''
    global configProfileName
    configProfileName = ''
    global isProjectVm
    isProjectVm = 0

    # Usage message
    help = "Usage: ./" + os.path.basename(__file__) + ' [options] ' + \
        '\n  --config-profile -c <profilename>\t\tSpecify the CloudMonkey profile name to get the credentials from (or specify in ./config file)' + \
        '\n  --oncluster -o <clustername>\t\t\tMigrate volumes on this cluster' + \
        '\n  --tocluster -t <clustername>\t\t\tMigrate volumes to this cluster' + \
        '\n  --is-projectvm\t\t\t\tLimit search to volumes that belong to a project' + \
        '\n  --debug\t\t\t\t\tEnable debug mode' + \
        '\n  --exec\t\t\t\t\tExecute for real'

    try:
        opts, args = getopt.getopt(
            argv, "hc:o:t:p", [
                "config-profile=", "oncluster=", "tocluster=", "debug", "exec", "is-projectvm"])
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
        elif opt in ("-o", "--oncluster"):
            fromCluster = arg
        elif opt in ("-t", "--tocluster"):
            toCluster = arg
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
    if len(fromCluster) == 0 or len(toCluster) == 0:
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
    print "Note: dry-run mode is enabled, not running any commands!"

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

fromClusterID = c.checkCloudStackName(
    {'csname': fromCluster, 'csApiCall': 'listClusters'})
toClusterID = c.checkCloudStackName(
    {'csname': toCluster, 'csApiCall': 'listClusters'})

# Select storage pool
fromStorageID = c.getStoragePool(fromClusterID)
toStorageID = c.getStoragePool(toClusterID)

# Get storage pool data
result = c.getStoragePoolData(fromStorageID)
fromStorage = result[0].name
result = c.getStoragePoolData(toStorageID)
toStorage = result[0].name

# Figure out how many volumes we have
volumes = c.listVolumes(fromStorageID, isProjectVm)

# Init vars
size = 0
tsize = 0
volumesToMigrate = {}
count = 0

# Read volumes we should ignore
if os.path.isfile('ignore_volumes.txt'):
    ignoreVolumes = []
    ignoreVolumes = [line.strip() for line in open('ignore_volumes.txt')]
    if DEBUG == 1:
        print "Debug: Ignoring these volumes: %s" % (ignoreVolumes)
else:
    print "Note: Ignore file 'ignore_volumes.txt' not found, so no volumes will be ignored."
    ignoreVolumes = []

# loop volumes
for volume in volumes:
    tsize = tsize + (volume.size / 1024 / 1024 / 1024)
    # We need a storage attribute to be able to migrate -- otherwise it's
    # probably just allocated and not ready yet
    if volume.id in ignoreVolumes:
        print "Debug: Ignorning volume id %s because it is on the ignore_volumes.txt list!" % (volume.id)
    elif hasattr(volume, 'storage'):
        # No need to migrate if we're already on target
        if volume.storage == toStorage:
            if DEBUG == 1:
                print "Debug: volume %s with name %s is already on storage %s -- ignoring!" % (volume.id, volume.name, volume.storage)
        # Only manage this hypervisor
        else:
            if volume.state == 'Ready':
                if hasattr(volume, 'vmstate') and volume.vmstate == 'Stopped':
                    # Mark this volume for migration
                    volumesToMigrate[count] = volume
                    count = count + 1
                    if DEBUG == 1:
                        print "Note: Will migrate because volume %s is attached to non-running VM: %s %s %s" % (volume.id, volume.name, volume.state, volume.storage)
                        print volume
                    size = size + (volume.size / 1024 / 1024 / 1024)
                # Check if volume is attached to a vm
                elif volume.vmstate is not None:
                    if DEBUG == 1:
                        print "Debug: volume %s is in attached to %s VM -- ignoring!" % (volume.id, volume.vmstate)
                else:
                    # Mark this volume for migration
                    volumesToMigrate[count] = volume
                    count = count + 1
                    if DEBUG == 1:
                        print "Note: will migrate because volume %s is not attached to running VM: %s %s %s" % (volume.id, volume.name, volume.state, volume.storage)
                        print volume
                    size = size + (volume.size / 1024 / 1024 / 1024)
            elif DEBUG == 1:
                print "Debug: volume %s is in state %s -- ignoring!" % (volume.id, volume.state)
    elif DEBUG == 1:
        print "Debug: no storage attribute found for volume id %s with name %s and state %s -- ignoring!" % (volume.id, volume.name, volume.state)

# Display sizes
if DEBUG == 1:
    print size
    print tsize
    print "Debug: Overview of volumes to migrate:"
    print volumesToMigrate

# Define table
t = PrettyTable(["Volume name",
                 "Attached to VM",
                 "Type",
                 "Volume state",
                 "Size",
                 "Account",
                 "Domain"])
t.align["Volume name"] = "l"

# Volumes to migrate
if len(volumesToMigrate) > 0:
    print "Note: Overview of volumes to migrate to storage pool " + toStorage + ":"
    counter = 0
    for x, vol in volumesToMigrate.items():
        counter = counter + 1
        if vol.account is not None:
            volaccount = vol.account
        else:
            volaccount = "Unknown"

        if vol.vmname is not None:
            volvmname = (
                vol.vmname[:22] +
                '..') if len(
                vol.vmname) > 24 else vol.vmname
        else:
            volvmname = "None"

        if vol.name is not None:
            volname = (
                vol.name[:22] +
                '..') if len(
                vol.name) > 24 else vol.name
        else:
            volname = "None"

        # Print overview table
        t.add_row([volname,
                   volvmname,
                   vol.type,
                   vol.state,
                   str(vol.size / 1024 / 1024 / 1024),
                   volaccount,
                   vol.domain])

        if DRYRUN != 1:
            # Execute the commands
            print "Executing: migrate volume " + vol.id + " to storage " + toStorageID
            result = c.migrateVolume(vol.id, toStorageID)
            if result == 1:
                print "Migrate failed -- exiting."
                print "Error: investegate manually!"
                # Notify user
                msgSubject = 'Warning: problem with maintenance for volume ' + \
                    vol.name + ' / ' + vol.id
                emailbody = "Could not migrate volume " + vol.id
                c.sendMail(c.mail_from, c.errors_to, msgSubject, emailbody)
                continue

            if result.volume.state == "Ready":
                print "Note: " + result.volume.name + " is migrated successfully "
            else:
                warningMsg = "Warning: " + result.volume.name + " is in state " + \
                    result.volume.state + " instead of Ready. Please investigate!"
                print warningMsg
                msgSubject = 'Warning: problem with maintenance for volume ' + \
                    vol.name + ' / ' + vol.id
                emailbody = warningMsg
                c.sendMail(c.mail_from, c.errors_to, msgSubject, emailbody)

    # Display table
    print t

    if DRYRUN == 1:
        print "Total size of volumes to migrate: " + str(size) + " GB"

else:
    print "Note: Nothing to migrate at this time."
