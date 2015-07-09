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

# Script to put a cluster in enable/disable and manage/unmanage state
# Remi Bergsma - rbergsma@schubergphilis.com

import time
import sys
import getopt
from cloudstackops import cloudstackops
from cloudstackops import cloudstackopsssh
from cloudstackops import xenserver
import os.path
from random import choice
from prettytable import PrettyTable

# Function to handle our arguments


def handleArguments(argv):
    global DEBUG
    DEBUG = 0
    global DRYRUN
    DRYRUN = 1
    global clustername
    clustername = ''
    global configProfileName
    configProfileName = ''
    global managedstate
    managedstate = ""
    global allocationstate
    allocationstate = ""
    global force
    force = 0
    global checkBonds
    checkBonds = True

    # Usage message
    help = "Usage: ./" + os.path.basename(__file__) + ' [options]' + \
        '\n  --config-profile -c <profilename>\t\tSpecify the CloudMonkey profile name to get the credentials from (or specify in ./config file)' + \
        '\n  --clustername -n <clustername> \t\tName of the cluster to work with' + \
        '\n  --managedstate -m <Managed|Unmanaged> \tSet managed state to Managed or Unmanaged' + \
        '\n  --allocationstate -a <Enabled|Disabled>\tSet allocated state to Enabled or Disabled' + \
        '\n  --no-bond-check\t\t\t\tSkip the bond check' + \
        '\n  --debug\t\t\t\t\tEnable debug mode' + \
        '\n  --exec\t\t\t\t\tExecute for real'

    try:
        opts, args = getopt.getopt(
            argv, "hc:n:a:m:", [
                "credentials-file=", "clustername=", "managedstate=", "allocationstate=", "no-bond-check", "debug", "exec", "force"])
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
        elif opt in ("-m", "--managedstate"):
            checkBonds = False
            managedstate = arg
        elif opt in ("-a", "--allocationstate"):
            checkBonds = False
            allocationstate = arg
        elif opt in ("--debug"):
            DEBUG = 1
        elif opt in ("--exec"):
            DRYRUN = 0
        elif opt in ("--force"):
            force = 1
        elif opt in ("--no-bond-check"):
            checkBonds = False

    # Default to cloudmonkey default config file
    if len(configProfileName) == 0:
        configProfileName = "config"

    # We need at least these vars
    if len(clustername) == 0:
        print help
        sys.exit()
    if len(managedstate) > 0 and len(allocationstate) > 0:
        print "Error: please specify either 'allocationstate' or 'managedstate' and not both."
        print help
        sys.exit()

    # Check argument sanity
    allocationstate_set = ('Enabled', 'Disabled')
    if len(allocationstate) > 0 and allocationstate not in allocationstate_set:
        print "Error: 'allocationstate' can only contain " + str(allocationstate_set)
        print help
        sys.exit(1)

    managedstate_set = ('Managed', 'Unmanaged')
    if len(managedstate) > 0 and managedstate not in managedstate_set:
        print "Error: 'managedstate' can only contain " + str(managedstate_set)
        print help
        sys.exit(1)

# Parse arguments
if __name__ == "__main__":
    handleArguments(sys.argv[1:])

# Init our class
c = cloudstackops.CloudStackOps(DEBUG, DRYRUN)
ssh = cloudstackopsssh.CloudStackOpsSSH(DEBUG, DRYRUN)
c.ssh = ssh
x = xenserver.xenserver()
c.xenserver = x

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
clusterID = c.checkCloudStackName(
    {'csname': clustername, 'csApiCall': 'listClusters'})
if clusterID == 1:
    print "Error: Could not find cluster '" + clustername + "'."
    sys.exit(1)

print "Note: Looking for other hosts in this cluster and checking their health.."

# Print cluster info
print "Note: Some info about cluster '" + clustername + "':"
c.printCluster(clusterID)

# Update Cluster
if DRYRUN == 1 and len(managedstate) > 0:
    print "Note: Would have set the 'Managed State' of cluster '" + clustername + "' to '" + managedstate + "'"
elif DRYRUN == 1 and len(allocationstate) > 0:
    print "Note: Would have set the 'Allocation State' of cluster '" + clustername + "' to '" + allocationstate + "'"
elif DRYRUN == 1:
    print "Warning: no command specified, just listing info"
else:
    clusterUpdateReturn = c.updateCluster(
        {'clusterid': clusterID, 'managedstate': managedstate, 'allocationstate': allocationstate})

    if clusterUpdateReturn == 1 or clusterUpdateReturn is None:
        print "Error: update failed."
    else:
        cluster = clusterUpdateReturn.cluster
        print "Note: Updated OK!"
        t = PrettyTable(["Cluster name",
                         "Allocation state",
                         "Managed state",
                         "Hypervisortype",
                         "Pod name",
                         "Zone name"])
        t.align["Cluster name"] = "l"
        t.add_row([cluster.name,
                   cluster.allocationstate,
                   cluster.managedstate,
                   cluster.hypervisortype,
                   cluster.podname,
                   cluster.zonename])
        print t
        print "Note: Displaying the hosts of this cluster:"
        c.printHypervisors(clusterID, False, checkBonds)
