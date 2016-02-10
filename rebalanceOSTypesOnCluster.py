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

# Script to rebalance OS types on a cluster
# Remi Bergsma - rbergsma@schubergphilis.com

import time
import sys, getopt
from cloudstackops import cloudstackops
import os.path
from random import choice
from prettytable import PrettyTable
from datetime import date
import re
import operator

# Function to handle our arguments
def handleArguments(argv):
   global DEBUG
   DEBUG = 0
   global DRYRUN
   DRYRUN = 1
   global configProfileName
   configProfileName = ''
   global isProjectVm
   isProjectVm = 0
   global clusterName
   clusterName = ''

   # Usage message
   help = "Usage: " + os.path.basename(__file__) + ' --config-profile|-c -n <cluster name> [--debug --exec --is-projectvm]'

   try:
      opts, args = getopt.getopt(argv,"hc:n:p:",["config-profile=","cluster","debug","exec","is-projectvm"])
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
      elif opt in ("-n", "--cluster"):
         clusterName = arg
      elif opt in ("--debug"):
         DEBUG = 1
      elif opt in ("--exec"):
         DRYRUN = 0
      elif opt in ("--is-projectvm"):
         isProjectVm = 1

   # Default to cloudmonkey default config file
   if len(configProfileName) == 0:
     configProfileName = "config"

   if len(clusterName) == 0:
     print "ERROR: Please provide cluster name"
     print help
     sys.exit(1)

# Check available memory
def hostHasEnhoughMemory(h):
  # Available memory
  memoryavailable = h.memorytotal - h.memoryallocated
  print "Host " + h.name + " has available memory: " + str(memoryavailable)

  # Don't try if host has less than 10GB memory left or if vm does not fit at all
  # vm.memory is in Mega Bytes
  if memoryavailable < (10 * 1024 * 1024 * 1024):
    print "Warning: Skipping " + h.name + " as it has not enough free memory (" + str(memoryavailable) + ")."
    return False
  return True

# Get host with min/max instances
def sortHostByVmCounter(vmcounter,reverse=False):
    return sorted(vmcounter.items(), key=lambda x:x[1], reverse=reverse)

# Get host with min/max memory
def sortHostByMemory(hosts,reverse=False):
    return dict(sorted(hosts.items(), key=lambda x:x[1].memoryallocated, reverse=reverse))

# Parse arguments
if __name__ == "__main__":
   handleArguments(sys.argv[1:])

# Handle project parameter
if isProjectVm == 1:
  projectParam = "true"
else:
  projectParam = "false"

# Init our class
c = cloudstackops.CloudStackOps(DEBUG,DRYRUN)

if DEBUG == 1:
  print "Warning: Debug mode is enabled!"

if DRYRUN == 1:
  print "Warning: dry-run mode is enabled, not running any commands!"

# make credentials file known to our class
c.configProfileName = configProfileName

# Init the CloudStack API
c.initCloudStackAPI()

if len(clusterName) > 1:
  clusterID = c.checkCloudStackName({'csname': clusterName, 'csApiCall': 'listClusters'})

if DEBUG == 1:
  print "API address: " + c.apiurl
  print "ApiKey: " + c.apikey
  print "SecretKey: " + c.secretkey

fromClusterHostsData = c.getHostsFromCluster(clusterID)
if fromClusterHostsData == 1 or fromClusterHostsData == None:
  print
  sys.stdout.write("\033[F")
  print "No (enabled) hosts found on cluster " + clustername

# Settings
minInstances = 10
maxInstances = 25
osFamilies = []
osFamilies.append('Windows')
osFamilies.append('RedHat')
osData = {}

# Build the data for each OS Family
for family in osFamilies:
  osData[family] = {}
  osData[family]['grandCounter'] = 0
  osData[family]['vms'] = {}
  osData[family]['vmcounter'] = {}

  # Figure out OStype
  osCat = c.listOsCategories({'name': family})
  keyword = 'Red' if family == 'RedHat' else 'Server'
  osTypes = c.listOsTypes({'oscategoryid': osCat[0].id, 'keyword': keyword })
  osData[family]['types'] = []
  osData[family]['hosts'] = {}

  if osTypes is None:
    print "Warning: No OS Types found for " + family + " skipping.."
    continue

  for type in osTypes:
    osData[family]['types'].append(type.id)

  # Look at all hosts in the cluster
  for fromHostData in fromClusterHostsData:
    osData[family]['vmcounter'][fromHostData.name] = 0
    osData[family]['vms'][fromHostData.name] = {}
    osData[family]['hosts'][fromHostData.name] = fromHostData

    if DEBUG ==1:
      print "# Looking for VMS on node " + fromHostData.name
      print "# Memory of this host: " + str(fromHostData.memorytotal)

    # Get all vm's: project and non project
    vmdata_non_project = c.listVirtualmachines({'hostid': fromHostData.id, 'isProjectVm': 'false' })
    vmdata_project = c.listVirtualmachines({'hostid': fromHostData.id, 'isProjectVm': 'true' })

    if vmdata_project is None and vmdata_non_project is None:
      print "Note: No vm's of type " + family  + " found on " + fromHostData.name
      continue
    if vmdata_project is None and vmdata_non_project is not None:
      vmdata = vmdata_non_project
    if vmdata_project is not None and vmdata_non_project is None:
      vmdata = vmdata_project
    if vmdata_project is not None and vmdata_non_project is not None:
      vmdata = vmdata_non_project + vmdata_project

    oscounter = 0
    for vm in vmdata:
      if DEBUG == 1:
        print vm.name + " -> " + str(vm.guestosid)
      if vm.guestosid in osData[family]['types']:
        osData[family]['vms'][fromHostData.name][vm.id] = vm
        osData[family]['vmcounter'][fromHostData.name] += 1

    # Cluster wide counters
    osData[family]['grandCounter'] += osData[family]['vmcounter'][fromHostData.name]

  # Sort by most memory free
  osData[family]['hosts'] = sortHostByMemory(osData[family]['hosts'], False)

print "Note: Cluster " + clusterName + " has " + str(osData['RedHat']['grandCounter']) + " Red Hat vm's and " + str(osData['Windows']['grandCounter']) + " Windows Server vm's"

# Process the generated OS Family data
for family, familyData in osData.iteritems():
  print
  print "Note: Processing " + family + " Family"
  print "Note: ======================================="
  migrateTo = []
  migrateFrom = []

  if 'vmcounter' not in familyData.keys():
    print "Warning: key vmcounter not found"
    if DEBUG == 1:
      c.pp.pprint(familyData)
    continue

  if DEBUG == 1:
    print "DEBUG: Overview: "
    c.pp.pprint(familyData['vmcounter'])
    print

  for h in familyData['vmcounter']:
    if familyData['vmcounter'][h] == 0:
      if DEBUG == 1:
        print "DEBUG: No VMs on " + h + " running family " + family
        continue

    if DEBUG == 1:
      print h + " " + str(familyData['vmcounter'][h])

    if familyData['vmcounter'][h] >= minInstances and familyData['vmcounter'][h] < maxInstances:
      if DEBUG == 1:
        print h + " is migration-to candidate!"

      # Available memory
      if not hostHasEnhoughMemory(familyData['hosts'][h]):
        continue

      migrateTo.append(h)

    elif familyData['vmcounter'][h] < minInstances:
      if DEBUG == 1:
        print h + " is migration-from candidate!"
      migrateFrom.append(h)

  if DEBUG == 1:
    print "DEBUG: MigrateTo:"
    print migrateTo

  # If no host with minCounter vm's, then select the one with the most
  if len(migrateTo) == 0:
    maxHosts = sortHostByVmCounter(familyData['vmcounter'], True)
    print "Note: Hosts in sorted order:"
    print maxHosts
    maxHost = ""

    # Select the best host to migrate to
    for d in maxHosts:
      # Get hostname
      m = d[0]
      # Available memory
      if not hostHasEnhoughMemory(familyData['hosts'][m]):
        continue
      # Too many instances already
      if familyData['vmcounter'][m] >= maxInstances:
        print "Note: Skipping " + m + " because it has more than maxInstances vm's already " + str(maxInstances)
        continue
      # Take the next best one
      maxHost = m
      print "Note: Selecting " + m + " because it already has some instances running."
      break

    # If it did not work, halt
    if len(maxHost) == 0:
      print "Error: Could not select a suitable host. Halting."
      sys.exit(1)

    if DEBUG == 1:
      print "DEBUG: Selecting the host with max vm's already."
    migrateTo.append(maxHost)

  osData[family]['vmcounterafter'] = osData[family]['vmcounter']

  # Display what we'd do
  for h in migrateFrom:
    for key,vm in familyData['vms'][h].iteritems():
      to = choice(migrateTo)
      if to != h:
        print "Note: Would have migrated " + vm.name + " (from " + h + " to " + str(to) + ") " + str(vm.memory) + " mem"
        osData[family]['vmcounterafter'][to] +=1
        osData[family]['vmcounterafter'][h] -=1
      else:
        print "Note: Skipping " + vm.name + " (already on " + h + " / " + to + ")"

  print "DEBUG Result after migration:"
  c.pp.pprint(osData[family]['vmcounterafter'])

if DEBUG == 1:
  print "Note: We're done!"
