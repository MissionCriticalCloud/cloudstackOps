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

# Script to search primary storage pools for 'orphaned disks' and remove
# them to free up space

import sys
import getopt
import math
import os.path

from cloudstackops import cloudstackops
from cloudstackops import cloudstackopsssh
from cloudstackops.cloudstackstorage import StorageHelper

from prettytable import PrettyTable


def get_volume_filesize(file_uuid_in_cloudstack, *filelist):
    filelist, = filelist
    size = None
    for filepath in filelist.keys():
        file_uuid_on_storagepool = filepath.split('/')[-1].split('.')[:1][0]

        if file_uuid_in_cloudstack == file_uuid_on_storagepool:
            size = int(filelist[filepath])
    return size

# Function to handle our arguments


def handle_arguments(argv):
    global DEBUG
    DEBUG = 0
    global DRYRUN
    DRYRUN = 1
    global FORCE
    FORCE = 0
    global zone
    zone = ''
    global clusterarg
    clusterarg = ''
    global configProfileName
    configProfileName = ''

    # Usage message
    help = "Usage: " + os.path.basename(__file__) + ' [options] ' + \
        '\n  --config-profile -c <profilename>\t\tSpecify the CloudMonkey profile name to get the credentials from (or specify in ./config file) [required]' + \
        '\n  --zone -z <zonename>\t\t\t\tZone Name [required]\t' + \
        '\n  --cluster -t <clustername>\t\t\tCluster Name [optional]\t' + \
        '\n  --debug\t\t\t\t\tEnable debug mode [optional]'
    try:
        opts, args = getopt.getopt(
            argv, "hc:z:t:", ["config-profile=", "zone=", "clusterarg=", "debug"])

    except getopt.GetoptError as e:
        print "Error: " + str(e)
        sys.exit(2)

    for opt, arg in opts:
        if opt == '-h':
            print help
            sys.exit()
        elif opt in ("-c", "--config-profile"):
            configProfileName = arg
        elif opt in ("--debug"):
            DEBUG = 1
        elif opt in ("-z", "--zone"):
            zone = arg
        elif opt in ("-t", "--cluster"):
            clusterarg = arg

    # Print help if required options not provided
    if len(configProfileName) == 0 or len(zone) == 0:
        print help
        exit(1)

## MAIN ##

# Parse arguments
if __name__ == "__main__":
    handle_arguments(sys.argv[1:])

# Init our classes
c = cloudstackops.CloudStackOps(DEBUG, DRYRUN, FORCE)
cs = cloudstackopsssh.CloudStackOpsSSH()

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

zoneid = c.getZoneId(zone)


if zoneid is None:
    print "Cannot find zone " + zone
    exit(1)

# get all clusters in zone if no cluster is given as input
if clusterarg is None or clusterarg == '':

    clusters = c.listClusters({'zoneid': zoneid, 'listall': 'true'})

else:

    clusters = c.listClusters(
        {'zoneid': zoneid, 'name': clusterarg, 'listall': 'true'})

# die if there are no clusters found (unlikely)
if clusters is None:
    print "DEBUG: No clusters found in zone"
    exit(1)


# get a list of storage pools for each cluster
t_storagepool = PrettyTable(
    ["Cluster", "Storage Pool", "Number of Orphaned disks", "Real Space used (GB)"])

for cluster in clusters:
    storagepools = []
    storagepools.append(c.getStoragePool(cluster.id))
    random_hypervisor = c.getHostsFromCluster(cluster.id).pop()
    # flatten storagepool list
    storagepools = [y for x in storagepools for y in x]

    # # if there are storage pools (should be)
    if len(storagepools) > 0:

        storagehelper = StorageHelper(debug=DEBUG)

        for storagepool in storagepools:
            used_space = 0

            # Get list of orphaned cloudstack disks for storagepool
            print "[INFO]: Retrieving list of orphans for storage pool", storagepool.name
            orphans = c.getDetachedVolumes(storagepool.id)

            storagepool_devicepath = storagepool.ipaddress + \
                ":" + str(storagepool.path)

            # get filelist for storagepool via a 'random' hypervisor from
            # cluster
            primary_mountpoint = storagehelper.get_mountpoint(
                random_hypervisor.ipaddress, storagepool_devicepath)

            if primary_mountpoint is None:
                print "[DEBUG]: no physical volume list retrieved for " + storagepool.name + " skipping"
                storagepool_filelist = None

            else:
                storagepool_filelist = storagehelper.list_files(
                    random_hypervisor.ipaddress, primary_mountpoint)

            t = PrettyTable(["Domain", "Account", "Name", "Cluster", "Storagepool", "Path",
                             "Allocated Size (GB)", "Real Size (GB)", "Orphaned"])

            for orphan in orphans:
                isorphaned = ''

                orphan_allocated_sizeGB = (orphan.size / math.pow(1024, 3))

                if storagepool_filelist is None:
                    orphan_real_sizeGB = 'n/a'
                    isorphaned = '?'

                else:
                    orphan_real_sizeGB = get_volume_filesize(
                        orphan.path, storagepool_filelist)

                    if orphan_real_sizeGB is not None:
                        used_space += (orphan_real_sizeGB / 1024)
                        orphan_real_sizeGB = format(
                            (orphan_real_sizeGB / 1024), '.2f')
                        isorphaned = 'Y'

                    else:
                        orphan_real_sizeGB = 0
                        isorphaned = 'N'

                # add a row with orphan details
                t.add_row([orphan.domain, orphan.account, orphan.name, cluster.name, storagepool.name, orphan.path,
                           orphan_allocated_sizeGB, orphan_real_sizeGB, isorphaned])

            # Print orphan table
            print t.get_string()
            t_storagepool.add_row(
                [cluster.name, storagepool.name, len(orphans), format(used_space, '.2f')])

print "Storagepool Totals"
print t_storagepool.get_string()
