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

# Script to list all VMs in a given cluster
# Remi Bergsma - rbergsma@schubergphilis.com

import sys
import getopt
from cloudstackops import cloudstackops
import os.path
from prettytable import PrettyTable


# Function to handle our arguments
def handleArguments(argv):
    global DEBUG
    DEBUG = 0
    global DRYRUN
    DRYRUN = 0
    global domainname
    domainname = ''
    global fromCluster
    fromCluster = ''
    global toCluster
    toCluster = ''
    global configProfileName
    configProfileName = ''
    global isProjectVm
    isProjectVm = 0
    global projectname
    projectname = ''
    global filterKeyword
    filterKeyword = ''
    global zonename
    zonename = ''
    global podname
    podname = ''
    global display
    display = 'detailed'
    global displayRouters
    displayRouters = 1
    global onlyDisplayRouters
    onlyDisplayRouters = 0
    global onlyDisplayRoutersThatRequireUpdate
    onlyDisplayRoutersThatRequireUpdate = 0
    global routerNicCount
    routerNicCount = ''
    global routerNicCountIsMinimum
    routerNicCountIsMinimum = ''
    global routerNicCountIsMaximum
    routerNicCountIsMaximum = ''
    global nonAdminCredentials
    nonAdminCredentials = 0
    global ignoreDomainList
    ignoreDomainList = ''
    global ignoreDomains
    ignoreDomains = ''

    # Usage message
    help = "Usage: ./" + os.path.basename(__file__) + ' [options]' + \
        '\n  --config-profile -c <name>\t\tSpecify CloudMonkey profile ' + \
        'name to get the credentials from (or specify in ./config file)' + \
        '\n  --domainname -d <name>\t\tLimit search to VMs in ' + \
        'domain' + \
        '\n  --oncluster -o <name>\t\t\tLimit search to VMs on ' + \
        'this cluster' + \
        '\n  --pod <podname>\t\t\tLimit search to VMs in this POD' + \
        '\n  --zone -z <zonename>\t\t\tLimit search to VMs in this zone ' + \
        '\n  --filter -f <keyword>\t\t\tLimit search to VMs which names' + \
        'match keyword' + \
        '\n  --only-routers\t\t\tLimit search to VMs that are router ' + \
        '\n  --only-routers-to-be-upgraded\t\tLimit search to VMs that are' + \
        'router and need upgrading' + \
        '\n  --no-routers\t\t\t\tLimit search to VMs that are not router ' + \
        '\n  --router-nic-count -n <number>\tLimit search to router VMs' + \
        'having this number of nics' + \
        '\n  --nic-count-is-minimum\t\tLimit search to router VMs that ' + \
        'have at least --router-nic-count nics' + \
        '\n  --nic-count-is-maximum\t\tLimit search to router VMs that ' + \
        'have no more than --router-nic-count nics' + \
        '\n  --projectname -p \t\t\tLimit search to VMs in this project' + \
        '\n  --is-projectvm\t\t\tLimit search to VMs that belong to a ' + \
        'project' + \
        '\n  --ignore-domains <list>\t\tDo not list VMs from these ' + \
        'domains (list should be comma separated, without spaces)' + \
        '\n  --non-admin-credentials\t\tLimit search to VMs of calling ' + \
        'credentials' + \
        '\n  --summary\t\t\t\tDisplay only a summary, no details' + \
        '\n  --no-summary\t\t\t\tDo not display summary' + \
        '\n  --debug\t\t\t\tEnable debug mode' + \
        '\n  --exec\t\t\t\tExecute for real (not needed for list* scripts)'

    try:
        opts, args = getopt.getopt(
            argv, "hc:d:p:o:f:z:n:",
            [
                "config-profile=", "domainname=",
                "projectname=", "oncluster=", "filter=",
                "zone=", "pod=", "router-nic-count=",
                "debug", "exec", "non-admin-credentials",
                "is-projectvm", "summary", "no-summary",
                "no-routers", "only-routers",
                "only-routers-to-be-upgraded",
                "nic-count-is-minimum",
                "nic-count-is-maximum", "ignore-domains="
            ]
        )
    except getopt.GetoptError as e:
        print "Error: " + str(e)
        print help
        sys.exit(2)
    if len(opts) == 0:
        print help
        sys.exit(2)

    for opt, arg in opts:
        if opt == '-h':
            print help
            sys.exit()
        elif opt in ("-c", "--config-profile"):
            configProfileName = arg
        elif opt in ("-d", "--domainname"):
            domainname = arg
        elif opt in ("--ignore-domains"):
            ignoreDomainList = arg
        elif opt in ("-o", "--oncluster"):
            fromCluster = arg
        elif opt in ("-p", "--projectname"):
            projectname = arg
            isProjectVm = 1
        elif opt in ("-f", "--filter"):
            filterKeyword = arg
        elif opt in ("-z", "--zone"):
            zonename = arg
        elif opt in ("--pod"):
            podname = arg
        elif opt in ("--router-nic-count"):
            routerNicCount = arg
        elif opt in ("--debug"):
            DEBUG = 1
        elif opt in ("--exec"):
            DRYRUN = 0
        elif opt in ("--non-admin-credentials"):
            nonAdminCredentials = 1
        elif opt in ("--is-projectvm"):
            isProjectVm = 1
        elif opt in ("--summary"):
            display = "onlySummary"
        elif opt in ("--no-summary"):
            display = "plain"
        elif opt in ("--no-routers"):
            displayRouters = 0
        elif opt in ("--only-routers"):
            onlyDisplayRouters = 1
        elif opt in ("--only-routers-to-be-upgraded"):
            onlyDisplayRoutersThatRequireUpdate = 1
            onlyDisplayRouters = 1
        elif opt in ("--nic-count-is-minimum"):
            routerNicCountIsMinimum = 1
        elif opt in ("--nic-count-is-maximum"):
            routerNicCountIsMaximum = 1

    # Default to cloudmonkey default config file
    if len(configProfileName) == 0:
        configProfileName = "config"

    # Ignore domain list
    if len(ignoreDomainList) > 0:
        ignoreDomains = ignoreDomainList.split(", ")
    else:
        ignoreDomains = []

    # Domain and project not together
    if len(projectname) > 0 and len(domainname) > 0:
        print "Error: Please specify either domainname \
            or projectname, not both."
        print help
        sys.exit()


# Function to handle stdout vm data
def printVirtualmachine(args):
    args = c.remove_empty_values(args)

    vmdata = (args['vmdata']) if 'vmdata' in args else None
    counter = (args['counter']) if 'counter' in args else 0
    hostCounter = (args['hostCounter']) if 'hostCounter' in args else 0
    memoryTotal = (args['memoryTotal']) if 'memoryTotal' in args else 0
    coresTotal = (args['coresTotal']) if 'coresTotal' in args else 0
    storageSizeTotal = (args['storageSizeTotal']) \
        if 'storageSizeTotal' in args else 0
    hostMemoryTotal = (args['hostMemoryTotal']) \
        if 'hostMemoryTotal' in args else 0
    ignoreDomains = (args['ignoreDomains']) if 'ignoreDomains' in args else []
    clustername = (args['clustername']) if 'clustername' in args else None

    if vmdata is not None:
        for vm in vmdata:
            if vm.domain in ignoreDomains:
                continue
            # Calculate storage usage
            storageSize = c.calculateVirtualMachineStorageUsage(
                vm.id,
                projectParam
            )
            storageSizeTotal = storageSizeTotal + storageSize

            # Memory
            memory = vm.memory / 1024
            memoryTotal = memoryTotal + memory

            # Cores
            coresTotal = coresTotal + vm.cpunumber

            # Counter
            counter = counter + 1

            # Display names
            vmname = (vm.name[:20] + '..') if len(vm.name) >= 22 else vm.name
            vmmemory = str(memory) + " GB"
            vmstoragesize = str(storageSize) + " GB"

            # Display project and non-project different
            if display != "onlySummary":
                if projectParam == "true":
                    t.add_row([
                        vmname,
                        vmstoragesize,
                        '-',
                        vmmemory,
                        vm.cpunumber,
                        vm.instancename,
                        vm.hostname,
                        vm.domain,
                        "Proj: " + " " + str(vm.project)
                    ])
                else:
                    t.add_row([
                        vmname,
                        vmstoragesize,
                        '-',
                        vmmemory,
                        vm.cpunumber,
                        vm.instancename,
                        vm.hostname,
                        vm.domain,
                        vm.account
                    ])
                sys.stdout.write(".")
                sys.stdout.flush()
    return storageSizeTotal, memoryTotal, coresTotal, counter

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
    print "API address: " + c.apiurl
    print "ApiKey: " + c.apikey
    print "SecretKey: " + c.secretkey

# Check cloudstack IDs
if DEBUG == 1:
    print "Checking CloudStack IDs of provided input.."
if len(fromCluster) > 1:
    fromClusterID = c.checkCloudStackName({
        'csname': fromCluster,
        'csApiCall': 'listClusters'
    })
if len(zonename) > 1:
    zoneID = c.checkCloudStackName({
        'csname': zonename,
        'csApiCall': 'listZones'
    })
else:
    zoneID = ''
if len(podname) > 1:
    podID = c.checkCloudStackName({
        'csname': podname,
        'csApiCall': 'listPods'
    })
else:
    podID = ''

# Handle domain parameter
if len(domainname) > 0:
    domainnameID = c.checkCloudStackName({
        'csname': domainname,
        'csApiCall': 'listDomains'
    })
    if domainnameID == 1:
        print "Error: domain " + domainname + " does not exist."
        sys.exit(1)
else:
    domainnameID = ''

# Handle projectname parameter
if len(projectname) > 0:
    projectnameID = c.checkCloudStackName({
        'csname': projectname,
        'csApiCall': 'listProjects',
        'listAll': 'true'
    })
else:
    projectnameID = ''

# Handle project parameter
if isProjectVm == 1:
    projectParam = "true"
else:
    projectParam = "false"

# Domains to ignore
if len(ignoreDomains) > 0:
    print "Note: Ignoring these domains: " + str(ignoreDomains)

if nonAdminCredentials == 1:
    # Result table
    t = PrettyTable([
        "VM",
        "Storage",
        "Router nic count",
        "Memory",
        "Cores",
        "Instance",
        "Host",
        "Domain",
        "Account"
    ])
    t.align["VM"] = "l"

    vmdata = c.listVirtualmachines({'listAll': 'false'})
    printVirtualmachine({'vmdata': vmdata, 'ignoreDomains': ignoreDomains})
    print
    print t
    sys.exit()

clusters = {}
# ClusterID available
if 'fromClusterID' in locals():
    clusters[fromClusterID] = fromCluster
else:
    if len(podname) > 0:
        result = c.listClusters({'podid': podID})
        for cluster in result:
            clusters[cluster.id] = cluster.name
    else:
        result = c.listClusters({'zoneid': zoneID})
        for cluster in result:
            clusters[cluster.id] = cluster.name

if DEBUG == 1:
    print clusters
    print "Debug: display mode = " + display

# Empty line
print

# Look at each cluster
grandCounter = 0
grandHostCounter = 0
grandStorageSizeTotal = 0
grandMemoryTotal = 0
grandCoresTotal = 0
grandHostMemoryTotal = 0

for clusterid, clustername in clusters.items():

    # Get hosts that belong to fromCluster
    fromClusterHostsData = c.getHostsFromCluster(clusterid)

    if fromClusterHostsData == 1 or fromClusterHostsData is None:
        print
        sys.stdout.write("\033[F")
        print "No (enabled) hosts found on cluster " + clustername
        continue

    # Look for VMs on each of the cluster hosts
    counter = 0
    hostCounter = 0
    memoryTotal = 0
    coresTotal = 0
    storageSizeTotal = 0
    hostMemoryTotal = 0
    hostCoresTotal = 0

    # Result table
    t = PrettyTable([
        "VM",
        "Storage",
        "Router nic count",
        "Memory",
        "Cores",
        "Instance",
        "Host",
        "Domain",
        "Account"
    ])
    t.align["VM"] = "l"

    for fromHostData in fromClusterHostsData:
        hostCounter = hostCounter + 1
        grandHostCounter = grandHostCounter + 1

        if DEBUG == 1:
            print "# Looking for VMS on node " + fromHostData.name
            print "# Memory of this host: " + str(fromHostData.memorytotal)

        # Reset progress indication
        print
        sys.stdout.write("\033[F")
        sys.stdout.write("\033[2K")
        sys.stdout.write(fromHostData.name + ":")

        # Count memory on the nodes
        memory = fromHostData.memorytotal / 1024 / 1024 / 1024
        hostMemoryTotal = hostMemoryTotal + memory
        grandHostMemoryTotal = grandHostMemoryTotal + memory

        # Cores
        coresTotal = 0

        # Get all vms of the domainid running on this host
        if onlyDisplayRouters < 1:

            vmdata = c.listVirtualmachines({
                'hostid': fromHostData.id,
                'domainid': domainnameID,
                'isProjectVm': projectParam,
                'projectid': projectnameID,
                'filterKeyword': filterKeyword
            })

            storageSizeTotal, memoryTotal, coresTotal, \
                counter = printVirtualmachine({
                    'vmdata': vmdata,
                    'counter': counter,
                    'hostCounter': hostCounter,
                    'memoryTotal': memoryTotal,
                    'coresTotal': coresTotal,
                    'storageSizeTotal': storageSizeTotal,
                    'hostMemoryTotal': hostMemoryTotal,
                    'ignoreDomains': ignoreDomains,
                    'clustername': clustername
                })

        # Cores
        hostCoresTotal += coresTotal

        # Routers
        if displayRouters < 1:
            continue

        vmdata = c.getRouterData({
            'hostid': fromHostData.id,
            'domainid': domainnameID,
            'isProjectVm': projectParam
        })

        if vmdata is None:
            continue

        for vm in vmdata:
            if vm.domain in ignoreDomains:
                continue

            # Nic
            niccount = len(vm.nic)

            if routerNicCountIsMinimum == 1:
                # Minimum this number of nics
                if len(routerNicCount) > 0 and niccount < int(routerNicCount):
                    continue

            elif routerNicCountIsMaximum == 1:
                # Maximum this number of nics
                if len(routerNicCount) > 0 and niccount > int(routerNicCount):
                    continue

            else:
                # Exactly this number of nics
                if len(routerNicCount) > 0 and niccount != int(routerNicCount):
                    continue

            if onlyDisplayRoutersThatRequireUpdate == 1 and \
                    vm.requiresupgrade is False:
                continue

            # Service Offering (to find allocated RAM)
            serviceOfferingData = c.listServiceOfferings({
                'serviceofferingid': vm.serviceofferingid,
                'issystem': 'true'
            })

            if serviceOfferingData is not None:
                # Memory
                memory = round(float(serviceOfferingData[0].memory) / 1024, 3)
                memoryTotal = memoryTotal + memory
                if serviceOfferingData[0].memory >= 1024:
                    memoryDisplay = str(serviceOfferingData[0].memory / 1024) \
                        + " GB"
                else:
                    memoryDisplay = str(serviceOfferingData[0].memory) + " MB"

                # Cores
                hostCoresTotal += serviceOfferingData[0].cpunumber

            else:
                memoryDisplay = "Unknown"

            # Tabs
            counter = counter + 1

            if vm.isredundantrouter is True:
                redundantstate = vm.redundantstate
            elif vm.vpcid is not None:
                redundantstate = "VPC"
            else:
                redundantstate = "SINGLE"

            # Name of the network / VPC
            if vm.vpcid is not None:
                networkResult = c.listVPCs(vm.vpcid)
            else:
                networkResult = c.listNetworks(vm.guestnetworkid)

            if networkResult is not None:
                displayname = networkResult[0].name
                displayname = (networkResult[0].name[:18] + '..') \
                    if len(networkResult[0].name) >= 21 \
                    else networkResult[0].name
            else:
                displayname = (vm.name[:18] + '..') \
                    if len(vm.name) >= 21 else vm.name

            displayname = displayname + " (" + redundantstate.lower() + ")"

            if vm.requiresupgrade is True:
                displayname = displayname + " [ReqUpdate!]"

            vmniccount = str(niccount) + " nics "

            # Display project and non-project different
            if display != "onlySummary":
                if vm.project:
                    try:
                        t.add_row([
                            displayname,
                            '-',
                            vmniccount,
                            memoryDisplay,
                            serviceOfferingData[0].cpunumber,
                            vm.name,
                            vm.hostname,
                            vm.domain,
                            "Proj: " + " " + vm.project
                        ])
                    except:
                        t.add_row([
                            displayname,
                            '-',
                            vmniccount,
                            memoryDisplay,
                            'Unknown',
                            vm.name,
                            vm.hostname,
                            vm.domain,
                            "Proj: " + " " + vm.project
                        ])
                else:
                    try:
                        t.add_row([
                            displayname,
                            '-',
                            vmniccount,
                            memoryDisplay,
                            serviceOfferingData[0].cpunumber,
                            vm.name,
                            vm.hostname,
                            vm.domain,
                            vm.account
                        ])
                    except:
                        t.add_row([
                            displayname,
                            '-',
                            vmniccount,
                            memoryDisplay,
                            'Unknown',
                            vm.name,
                            vm.hostname,
                            vm.domain,
                            vm.account
                        ])

                sys.stdout.write(".")
                sys.stdout.flush()

    if counter > 0 and display != "onlySummary":
        # Remove progress indication
        sys.stdout.write("\033[F")

        # Print result table
        print
        print t

    if counter > 0 and display != "plain":
        memoryUtilisation = round((memoryTotal / float(
            hostMemoryTotal)) * 100, 2)
        print ""
        print "Summary '" + clustername + "':"
        print " Total number of VMs: " + str(counter)

        if not len(domainname) > 0 \
            and not len(filterKeyword) > 0 \
            and not len(projectname) > 0 \
            and projectParam == 'false' \
            and not (len(routerNicCount) > 0 or
                     displayRouters < 1 or
                     onlyDisplayRouters == 1
                     ):
            print " Total number hypervisors: " + str(hostCounter)
            print " Total allocated RAM: " + str(memoryTotal) + " / " + \
                str(hostMemoryTotal) + " GB (" + str(memoryUtilisation) + " %)"
            print " Total allocated cores: " + str(hostCoresTotal)
            print " Total allocated storage: " + str(storageSizeTotal) + " GB"
        else:
            print " Total allocated RAM: " + str(memoryTotal) + " GB"
            print " Total allocated cores: " + str(hostCoresTotal)

        print ""
        grandCounter = grandCounter + counter
        grandStorageSizeTotal = grandStorageSizeTotal + storageSizeTotal
        grandMemoryTotal = grandMemoryTotal + memoryTotal
        grandCoresTotal = grandCoresTotal + hostCoresTotal


if len(clusters) > 1 and display == "onlySummary":
    grandMemoryUtilisation = round((grandMemoryTotal / float(
        grandHostMemoryTotal)) * 100, 2)
    print ""
    print "==================  Grand Totals ==============="
    print " Total number of VMs: " + str(grandCounter)

    if not len(domainname) > 0 \
            and not len(filterKeyword) > 0 \
            and not len(projectname) > 0 \
            and projectParam == 'false':
        print " Total number hypervisors: " + str(grandHostCounter)
        print " Total allocated RAM: " + str(grandMemoryTotal) + " / " + \
            str(grandHostMemoryTotal) + " GB (" + \
            str(grandMemoryUtilisation) + " %)"
        print " Total allocated storage: " + str(grandStorageSizeTotal) + " GB"
    else:
        print " Total allocated RAM: " + str(grandMemoryTotal) + " GB"
        print " Total allocated cores: " + str(grandCoresTotal)

    print "================================================"
    print ""

if DEBUG == 1:
    print "Note: We're done!"

# Remove progress indication
sys.stdout.write("\033[F")
print
