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

# Script to migrate a router VM to a new cluster
# Remi Bergsma - rbergsma@schubergphilis.com

import time
import sys
import getopt
from cloudstackops import cloudstackops
from cloudstackops import cloudstacksql
import os.path
from random import choice

# Function to handle our arguments


def handleArguments(argv):
    global DEBUG
    DEBUG = 0
    global DRYRUN
    DRYRUN = 1
    global FORCE
    FORCE = 0
    global vmname
    vmname = ''
    global toCluster
    toCluster = ''
    global configProfileName
    configProfileName = ''
    global isProjectVm
    isProjectVm = 0
    global mysqlHost
    mysqlHost = ''
    global mysqlPasswd
    mysqlPasswd = ''

    # Usage message
    help = "Usage: " + os.path.basename(__file__) + ' [options] ' + \
        '\n  --config-profile -c <profilename>\t\tSpecify the CloudMonkey profile name to get the credentials from (or specify in ./config file)' + \
        '\n  --routerinstance-name -r <instancename>\tMigrate this router (r-12345-VM)' + \
        '\n  --tocluster -t <clustername>\t\t\tMigrate router to this cluster' + \
        '\n  --mysqlserver -s <mysql hostname>\t\tSpecify MySQL server to read HA worker table from' + \
        '\n  --mysqlpassword <passwd>\t\t\tSpecify password to cloud MySQL user' + \
        '\n  --is-projectrouter\t\t\t\tThe specified router belongs to a project' + \
        '\n  --debug\t\t\t\t\tEnable debug mode' + \
        '\n  --exec\t\t\t\t\tExecute for real'

    try:
        opts, args = getopt.getopt(
            argv, "hc:r:s:t:p", [
                "config-profile=", "routerinstance-name=", "mysqlserver=", "tocluster=", "debug", "exec", "is-projectrouter", "force"])
    except getopt.GetoptError as e:
        print("Error: " + str(e))
        sys.exit(2)
    for opt, arg in opts:
        if opt == '-h':
            print(help)
            sys.exit()
        elif opt in ("-c", "--config-profile"):
            configProfileName = arg
        elif opt in ("-r", "--routerinstance-name"):
            vmname = arg
        elif opt in ("--debug"):
            DEBUG = 1
        elif opt in ("--exec"):
            DRYRUN = 0
        elif opt in ("--force"):
            FORCE = 1
        elif opt in ("-t", "--tocluster"):
            toCluster = arg
        elif opt in ("--is-projectrouter"):
            isProjectVm = 1
        elif opt in ("-s", "--mysqlserver"):
            mysqlHost = arg
        elif opt in ("-p", "--mysqlpassword"):
            mysqlPasswd = arg

    # Default to cloudmonkey default config file
    if len(configProfileName) == 0:
        configProfileName = "config"

    # We need at least these vars
    if len(vmname) == 0 or len(mysqlHost) == 0:
        print(help)
        sys.exit()

# Parse arguments
if __name__ == "__main__":
    handleArguments(sys.argv[1:])

# Init our class
c = cloudstackops.CloudStackOps(DEBUG, DRYRUN, FORCE)
s = cloudstacksql.CloudStackSQL(DEBUG, DRYRUN)

# Connect MySQL
result = s.connectMySQL(mysqlHost, mysqlPasswd)
if result > 0:
    print("Error: MySQL connection failed")
    sys.exit(1)
elif DEBUG == 1:
    print("DEBUG: MySQL connection successful")
    print(s.conn)

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

if isProjectVm == 1:
    projectParam = "true"
else:
    projectParam = "false"

# check CloudStack IDs
routerID = c.checkCloudStackName({'csname': vmname,
                                  'csApiCall': 'listRouters',
                                  'listAll': 'true',
                                  'isProjectVm': projectParam})
if len(toCluster) != 0:
    toClusterID = c.checkCloudStackName(
        {'csname': toCluster, 'csApiCall': 'listClusters'})

# get router data
routerData = c.getRouterData({'name': vmname, 'isProjectVm': projectParam})
router = routerData[0]

if DEBUG == 1:
    print(routerData)

print("Note: Found router " + router.name + " that belongs to account " + router.account + " with router ID " + router.id)
print("Note: This router has " + str(len(router.nic)) + " nics.")

# Find the current host and cluster of this router
routerHostData = c.getHostData({'hostid': router.hostid})
if routerHostData is not None:
    routerClusterID = routerHostData[0].clusterid
else:
    print("Error: could not find host with id " + router.hostid)
    sys.exit(1)

# Get data from vm
if router.state == "Running":
    needToStop = "true"
    autoStartVM = "true"
    routerHostData = c.getHostData({'hostname': router.hostname})
    print("Note: Router " + router.name + " is running on " + router.hostname + " (" + routerHostData[0].clustername + " / " + routerHostData[0].podname + ")")
else:
    print("Note: Router " + router.name + " has state " + router.state)
    needToStop = "false"
    autoStartVM = "false"

# Search for hosttags on the current cluster
hosttags = c.getServiceOfferingTags(router.serviceofferingid, "host")
foundHostTag = c.checkClusterHostTags(routerClusterID, hosttags)
if foundHostTag:
    print("Error: your current cluster has hosts with tags '" + hosttags + "'. Migration will only work when current cluster is in Disabled state and has the host tag '" + hosttags + "' removed.")
    sys.exit(1)

# Check current cluster state
routerClusterData = c.listClusters({'clusterid': routerClusterID})
if routerClusterData[0].allocationstate != "Disabled":
    print("Error: migrating a Router only works when the current cluster is in Disabled state and has the host tag '" + hosttags + "' removed.")
    sys.exit(1)

# If no destination cluster is provided we should select one
# First, make sure redundant routers do not end up on the same cluster
if router.isredundantrouter:
    peerRouterData = c.getRouterPeerData(vmname)
    if peerRouterData is None or peerRouterData == 1:
        print("Error: cannot get router peer data.")
        sys.exit(1)
    if peerRouterData["routerPeer"].redundantstate == "FAULT":
        print("Error: The peer router is in " + peerRouterData["routerPeer"].redundantstate + " state. Failover will not work and cause downtime. Please fix this first!")
        sys.exit(1)
    else:
        print("Note: The peer router is in " + peerRouterData["routerPeer"].redundantstate + " state.")

    if peerRouterData["clustername"] == toCluster:
        print("Error: the redundant peer is also running on cluster " + toCluster + ". Please choose another cluster for this router.")
        sys.exit(1)
else:
    print("Note: This is not a redundant router pair. Skipping redundant checks.")

if len(toCluster) == 0:
    toClusterList = []
    print("Note: No destination cluster provided, selecting one to migrate to")
    clustersInZone = c.listClusters({'zoneid': router.zoneid})
    for cluster in clustersInZone:
        # Only select enabled clusters
        if cluster.allocationstate == "Enabled":
            if router.isredundantrouter:
                # If redundant router, make sure we ignore the peer's cluster
                if cluster.name == peerRouterData["clustername"]:
                    if DEBUG == 1:
                        print("Debug: ignorning cluster " + cluster.id + " because it is the same cluster as peer.")
                    continue
                # Also, select a cluster in a different pod
                elif cluster.podname == peerRouterData["podname"]:
                    if DEBUG == 1:
                        print("Debug: ignorning cluster " + cluster.id + " because it is on the same pod as peer is.")
                    continue
                else:
                    if DEBUG == 1:
                        print("Debug: adding cluster " + cluster.id + " to the list.")
                    toClusterList.append(cluster.id)
            # Check Storagetags
            if c.checkStorageTags({'toClusterID': cluster.id,
                                   'routername': router.name,
                                   'projectParam': projectParam}) > 0:

                print("Warning: Storage tags not OK, skipping " + cluster.name)
                continue

            # Check Hosttags
            if c.checkHostTags({'toClusterID': cluster.id,
                                'routername': router.name,
                                'projectParam': projectParam}) > 0:
                print("Warning: Host tags not OK, skipping " + cluster.name)
                continue
            # Add
            if DEBUG == 1:
                print("Debug: adding cluster " + cluster.id + " to the list.")
            toClusterList.append(cluster.id)

    # Finally, select a randon cluster from the list
    toClusterID = choice(toClusterList)

if len(toClusterID) == 0:
    print("Error: Could not automatically select a cluster to migrate to. Please specify using --tocluster.")
    sys.exit(1)

if DEBUG == 1:
    print("DEBUG: Selected cluster ID " + toClusterID)

toClusterData = c.listClusters({'clusterid': toClusterID})
print("Note: Migrating to " + toClusterData[0].name)

# Check zone
if c.checkZone(routerClusterID, toClusterID) > 0:
    print("Error: Zone not OK.")
    sys.exit(1)

# Storagetags
if c.checkStorageTags({'toClusterID': toClusterID,
                       'routername': router.name,
                       'projectParam': projectParam}) > 0:
    print("Error: Storage tags not OK.")
    sys.exit(1)

# Hosttags
if c.checkHostTags({'toClusterID': toClusterID,
                    'routername': router.name,
                    'projectParam': projectParam}) > 0:
    print("Error: Host tags not OK.")
    sys.exit(1)

# Check router cluster
routerClusterData = c.listClusters({'clusterid': routerClusterID})
if routerClusterData is None:
    print("Error: could not find cluster with id " + routerClusterID)
    sys.exit(1)

# Get user data to e-mail
adminData = c.getDomainAdminUserData(router.domainid)
if DRYRUN == 1:
    print("Note: Not sending notification e-mails due to DRYRUN setting. Would have e-mailed " + adminData.email)
else:

    if not adminData.email:
        print("Warning: Skipping mailing due to missing e-mail address.")

    templatefile = open("email_template/migrateRouterVM.txt", "r")
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
        print(emailbody)

# Stop router
if DRYRUN == 1:
    print("Note: Would have stopped router " + router.name + " (" + router.id + ")")
else:
    print("Executing: stop router " + router.name + " (" + router.id + ")")
    result = c.stopRouter(router.id)
    if result == 1:
        print("Stopping failed, will try again!")
        result = c.stopRouter(router.id)
        if result == 1:
            print("Stop failed again -- exiting.")
            print("Error: investegate manually!")

            # Notify admin
            msgSubject = 'Warning: problem with maintenance for domain ' + \
                router.domain
            emailbody = "Could not stop router " + router.name
            c.sendMail(c.mail_from, c.errors_to, msgSubject, emailbody)
            sys.exit(1)

# Get this router's root volume uuid
mysqlResult = s.getRouterRootVolumeUUID(router.id)
if DEBUG == 1:
    print(mysqlResult)

targetStorageID = c.getRandomStoragePool(toClusterID)

for (volid, volumename, vm_instancename) in mysqlResult:
    print("Note: router " + router.name + " has ROOT volume with name " + volumename + " and uuid " + volid)

    if DRYRUN == 1:
        print("Note: Would have migrated volume " + volid + " (" + volumename + ") to storage " + targetStorageID)
    else:
        print("Executing: migrate volume " + volid + " to storage " + targetStorageID)
        result = c.migrateVolume(volid, targetStorageID)
        if result == 1:
            print("Migrate failed -- exiting.")
            print("Error: investegate manually!")

            # Notify admin
            msgSubject = 'Warning: problem with maintenance for router ' + \
                router.name
            emailbody = "Could not migrate volume " + volid
            c.sendMail(c.mail_from, c.errors_to, msgSubject, emailbody)
            sys.exit(1)

        if result.volume.state == "Ready":
            print("Note: " + result.volume.name + " is migrated successfully ")

# Start router
if DRYRUN == 1:
    print("Note: Would have started router " + router.name + " (" + router.id + ")")
else:
    print("Executing: start router " + router.name + " (" + router.id + ")")
    result = c.startRouter(router.id)
    if result == 1:
        print("Start failed, will try again!")
        result = c.stopRouter(router.id)
        if result == 1:
            print("Start failed again -- exiting.")
            print("Error: investegate manually!")

            # Notify admin
            msgSubject = 'Warning: problem with maintenance for domain ' + \
                router.domain

            if force == 1:
                emailbody = "Could not start router " + router.name + \
                    ". Note: the --force parameter was used."
            else:
                emailbody = "Could not start router " + router.name

            c.sendMail(c.mail_from, c.errors_to, msgSubject, emailbody)
            sys.exit(1)

# Get user data to e-mail
if DRYRUN == 1:
    print("Note: Not sending notification e-mails due to DRYRUN setting. Would have e-mailed " + adminData.email)
else:

    if not adminData.email:
        print("Warning: Skipping mailing due to missing e-mail address.")

    templatefile = open("email_template/migrateRouterVM_done.txt", "r")
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
        print("DEBUG: email body:")
        print(emailbody)

print("Note: We're done!")
