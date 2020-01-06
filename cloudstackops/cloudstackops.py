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

# Class to support tools used to operate CloudStack
# Remi Bergsma - rbergsma@schubergphilis.com
import json
import logging
import operator
import re
# Import our dependencies
import smtplib
import string
import urllib2
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
# Import the class we depend on
from os.path import expanduser
from random import choice
from urlparse import urlparse

import time
from prettytable import PrettyTable

from cloudstackopsbase import *

# Marvin
try:
    import requests
    from marvin.cloudstackConnection import cloudConnection
    from marvin.cloudstackException import cloudstackAPIException
    from marvin.cloudstackAPI import *
    from marvin import cloudstackAPI
except:
    print "Error: Please install Marvin to talk to the CloudStack API:"
    print "       pip install ./marvin/Marvin-0.1.0.tar.gz (file is in this repository)"
    sys.exit(1)
# Colored terminals
try:
    from clint.textui import colored
except:
    print "Error: Please install clint library to support color in the terminal:"
    print "       pip install clint"
    sys.exit(1)
# Exoscale CS library
try:
    from cs import CloudStack, CloudStackException
except:
    print "Error: Please install cs library to talk to Cosmic API:"
    print "       pip install cs"
    sys.exit(1)

class CloudStackOps(CloudStackOpsBase):
    # Init function
    def __init__(self, debug=0, dryrun=0, force=0):
        super(CloudStackOps, self).__init__(debug, dryrun, force)
        self.apikey = ''
        self.secretkey = ''
        self.username = ''
        self.password = ''
        self.api = ''
        self.cloudstack = ''
        self.apiurl = ''
        self.apiserver = ''
        self.apiprotocol = ''
        self.apiport = ''
        self.csApiClass = ''
        self.conn = ''
        self.exoCsApi = None
        self.ssh = None
        self.xenserver = None
        self.kvm = None
        self.vmware = None
        self.vmshutpolicy = {}
        self.check_screen_alike()


    def printWelcome(self):
        print colored.green("Welcome to CloudStackOps")

    # Check if we run in a screen session
    def check_screen_sty(self):
        try:
            if len(os.environ['STY']) > 0:
                if self.DEBUG == 1:
                    print "DEBUG: We're running in screen."
                return True
        except:
            return False

    # Check if we run in a tmux session
    def check_tmux(self):
        try:
            if len(os.environ['TMUX']) > 0:
                if self.DEBUG == 1:
                    print "DEBUG: We're running in tmux."
                return True
        except:
            return False

    # Check if we run in a tmux session
    def check_screen_term(self):
        try:
            if os.environ['TERM'] == "screen":
                if self.DEBUG == 1:
                    print "DEBUG: We're running in a screen-alike program."
                return True
        except:
            return False

    def check_screen_alike(self):
        if self.check_screen_sty():
            return True
        if self.check_tmux():
            return True
        if self.check_screen_term():
            return True
        print colored.red(
            "Warning: You are NOT running inside screen/tmux. Please start a screen/tmux session to keep commands running in case you get disconnected!")

    # Handle unwanted CTRL+C presses
    def catch_ctrl_C(self, sig, frame):
        print "Warning: do not interupt! If you really want to quit, use kill -9."

    # Read config files
    def readConfigFile(self):
        # Check config file
        home = expanduser("~")
        self.configProfileNameFullPath = home + "/.cloudmonkey/config"
        tryLocal = False

        # Read config for CloudStack API credentials
        try:
            print "Note: Trying to use API credentials from CloudMonkey profile '" + self.configProfileName + "'"
            self.parseConfig(self.configProfileNameFullPath)
        except:
            print colored.yellow(
                "Warning: Cannot read or parse CloudMonkey profile '" + self.configProfileName + "'. Trying local config file..")
            tryLocal = True

        if self.configProfileName == "config":
            tryLocal = True

        if tryLocal:
            # Read config for CloudStack API credentials
            try:
                print "Note: Trying to use API credentials from local config profile '" + self.configProfileName + "'"
                self.parseConfig(self.configfile)
            except:
                print colored.yellow(
                    "Warning: Cannot read or parse profile '" + self.configProfileName + "' from local config file either")

        # Do we have all required settings?
        if self.apiurl == '' or (self.apikey == '' or self.secretkey == '') and (
                self.username == '' or self.password == ''):
            print colored.red(
                "Error: Could not load CloudStack API settings from local config file, nor from CloudMonkey config file. Halting.")
            print "Hint: Specify a CloudMonkey profile or setup the local config file 'config'. See documentation."
            sys.exit(2)

        # Read our own config file for some more settings
        config = ConfigParser.RawConfigParser()
        config.read(self.configfile)
        try:
            self.organization = config.get('cloudstackOps', 'organization')
            self.smtpserver = config.get('mail', 'smtpserver')
            self.mail_from = config.get('mail', 'mail_from')
            self.errors_to = config.get('mail', 'errors_to')
        except:
            print "Error: Cannot read or parse CloudStackOps config file '" + self.configfile + "'"
            print "Hint: Setup the local config file 'config', using 'config.sample' as a starting point. See documentation."
            sys.exit(1)

    # Read and parse config file
    def parseConfig(self, configFile):
        if self.DEBUG == 1:
            print "Debug: Parsing config file " + configFile
        config = ConfigParser.RawConfigParser()
        config.read(configFile)
        if self.DEBUG == 1:
            print "Selected profile: " + self.configProfileName
        # lets figure out your config:
        if config.has_option('core', 'profile'):
            if self.configProfileName == 'config':
                # cloudmonkey > 5.2.x config without the commandline profile
                # option
                if self.DEBUG == 1:
                    print "Cloudmonkey > 5.2.x configfile found, no profile option, use profile directive from configfile"
                profile = config.get('core', 'profile')
                if self.DEBUG == 1:
                    print "Debug: profile " + profile
                self.apikey = config.get(profile, 'apikey')
                self.secretkey = config.get(profile, 'secretkey')
                self.username = config.get(profile, 'username')
                self.password = config.get(profile, 'password')
                self.apiurl = config.get(profile, 'url')
            elif self.configProfileName != 'config':
                # cloudmonkey > 5.2.x config with the commandline profile
                # option
                if self.DEBUG == 1:
                    print "Cloudmonkey > 5.2.x configfile found, profile option given"
                self.apikey = config.get(self.configProfileName, 'apikey')
                self.secretkey = config.get(self.configProfileName, 'secretkey')
                self.username = config.get(self.configProfileName, 'username')
                self.password = config.get(self.configProfileName, 'password')
                self.apiurl = config.get(self.configProfileName, 'url')
            # Split it, because we use an older Marvin and a newer CloudMonkey
            urlParts = urlparse(self.apiurl)
            self.apiport = '443'
            self.apiprotocol = 'https'
            if urlParts.scheme != '':
                self.apiprotocol = urlParts.scheme
            if urlParts.port is not None:
                self.apiport = urlParts.port
            elif urlParts.scheme != '' and urlParts.scheme == 'http':
                self.apiport = '80'
                self.apiprotocol = 'http'
            self.apiserver = urlParts.hostname
        else:
            # cloudmonkey < 5.2.x config
            if self.DEBUG == 1:
                print "Cloudmonkey < 5.2.x configfile found"
            self.apikey = config.get('user', 'apikey')
            self.secretkey = config.get('user', 'secretkey')
            self.username = config.get('user', 'username')
            self.password = config.get('user', 'password')
            self.apiport = config.get('server', 'port')
            self.apiprotocol = config.get('server', 'protocol')
            self.apiserver = config.get('server', 'host')
            self.apiurl = self.apiprotocol + '://' + self.apiserver + \
                          ':' + self.apiport + config.get('server', 'path')
        if self.DEBUG == 1:
            print "URL: " + self.apiurl

    # create connection to CloudStack API
    def initCloudStackAPI(self):
        self.readConfigFile()
        log = logging.getLogger()
        if self.DEBUG == 1:
            print "Debug: apiserver=" + self.apiserver + " apiKey=" + self.apikey + " securityKey=" + self.secretkey + " username=" + self.username + " password=" + self.password + " port=" + str(
                self.apiport) + " scheme=" + self.apiprotocol
        try:
            if self.apikey:
                self.cloudstack = cloudConnection(
                    self.apiserver,
                    apiKey=self.apikey,
                    securityKey=self.secretkey,
                    asyncTimeout=14400,
                    logging=log,
                    port=int(
                        self.apiport),
                    scheme=self.apiprotocol)
            elif self.password:
                print "Using username + password for connection!"
                self.cloudstack = cloudConnection(
                    self.apiserver,
                    user=self.username,
                    passwd=self.password,
                    asyncTimeout=14400,
                    logging=log,
                    scheme=self.apiprotocol)
            if self.DEBUG == 1:
                print self.cloudstack
        except:
            print "Error connecting to CloudStack. Are you using the right Marvin version? See README file. Halting."
            sys.exit(1)
        try:
            self.exoCsApi = CloudStack(
                endpoint=self.apiurl,
                key=self.apikey,
                secret=self.secretkey,
                timeout=60
            )
        except:
            print "Error connecting to Cosmic. Halting."
            sys.exit(1)

        # Print name of cloud we're connected to
        print "Note: Connected to '" + self.getCloudName() + "'"

    # Call the CloudStack API
    def _callAPI(self, apicall):

        #  Valid api object?
        if apicall is None:
            return 1

        try:
            data = self.cloudstack.marvin_request(apicall)
            if data is None and self.DEBUG == 1:
                print "Warning: Received None object from CloudStack API"

            if self.DEBUG == 1:
                print "DEBUG: received data:"
                print data

        except Exception as err:
            # org.apache.cloudstack.api.ApiErrorCode Enum Reference
            if "errorCode: 432" in str(err):
                print "Error: Please try again with --non-admin-credentials argument, or use admin API credentials."
                print "Error: Unsupported API call: %s" % str(apicall)[1:str(apicall).index(" object at ")]
                sys.exit()
            else:
                print "Error: " + str(err)
            return 1
        except urllib2.HTTPError as e:
            print "Error: Command failed: " + str(e.msg)
            return 1

        return data

    # Remove empty arguments
    def remove_empty_values(self, d):
        if isinstance(d, dict):
            return dict(
                (k,
                 self.remove_empty_values(v)) for k,
                                                  v in d.iteritems() if v and self.remove_empty_values(v))
        else:
            return d

    # Check if a given CloudStack name exists and return its ID if it does
    def checkCloudStackName(self, args):

        # Handle arguments
        csname = (args['csname']) if 'csname' in args else ''
        csApiCall = (args['csApiCall']) if 'csApiCall' in args else ''
        listAll = (args['listAll']) if 'listAll' in args else 'false'
        isProjectVm = (
            args['isProjectVm']) if 'isProjectVm' in args else 'false'

        domainId = (args['domainid']) if 'domainid' in args else ''

        # Find out which API call to make
        if csApiCall == "listVirtualMachines":
            apicall = listVirtualMachines.listVirtualMachinesCmd()
        elif csApiCall == "listClusters":
            apicall = listClusters.listClustersCmd()
        elif csApiCall == "listStoragePools":
            apicall = listStoragePools.listStoragePoolsCmd()
        elif csApiCall == "listRouters":
            apicall = listRouters.listRoutersCmd()
        elif csApiCall == "listDomains":
            apicall = listDomains.listDomainsCmd()
        elif csApiCall == "listAccounts":
            apicall = listAccounts.listAccountsCmd()
        elif csApiCall == "listProjects":
            apicall = listProjects.listProjectsCmd()
            isProjectVm = 'false'
        elif csApiCall == "listHosts":
            apicall = listHosts.listHostsCmd()
        elif csApiCall == "listZones":
            apicall = listZones.listZonesCmd()
        elif csApiCall == "listPods":
            apicall = listPods.listPodsCmd()
        elif csApiCall == "listZones":
            apicall = listZones.listZonesCmd()
        elif csApiCall == "listTemplates":
            apicall = listTemplates.listTemplatesCmd()
            apicall.templatefilter = "all"
        elif csApiCall == "listVolumes":
            apicall = listVolumes.listVolumesCmd()
        elif csApiCall == "listNetworks":
            apicall = listNetworks.listNetworksCmd()
        elif csApiCall == "listVPCs":
            apicall = listVPCs.listVPCsCmd()
        elif csApiCall == "listServiceOfferings":
            apicall = listServiceOfferings.listServiceOfferingsCmd()
        elif csApiCall == "listDiskOfferings":
            apicall = listDiskOfferings.listDiskOfferingsCmd()
        else:
            print "No API command to call"
            sys.exit(1)

        if isProjectVm == 'true':
            apicall.projectid = "-1"

        try:
            if csname.startswith('i-'):
                apicall.keyword = str(csname)
            else:
                apicall.name = str(csname)
        except:
            apicall.name = str(csname)

        if listAll == 'true':
            apicall.listAll = "true"

        if domainId is not '':
            apicall.domainid = domainId

        found_counter = 0
        try:
            if self.DEBUG == 1:
                print "DEBUG: making marvin request:"
            
            data = self.cloudstack.marvin_request(apicall)
            if (data is None or len(data) == 0) and self.DEBUG == 1:
                print "Warning: Received None object from CloudStack API"

            if self.DEBUG == 1:
                print "DEBUG: received data:"
                print data

            # Check for a result
            if data:
                for d in data:
                    # And make sure it's the correct one
                    if csname == d.name or csname == d.instancename:
                        found_counter += 1
                        if self.DEBUG == 1:
                            print "Found in loop " + str(d.name) + " counter = " + str(found_counter)

                        csnameID = d.id
                    elif self.DEBUG == 1:
                        print "Not found in loop " + str(d.name) + " counter = " + str(found_counter)

                if len(csnameID) < 1:
                    print "Warning: '%s' could not be located in CloudStack database using '%s' -- Exit." % (
                        csname, csApiCall)
                    sys.exit(1)

                if found_counter > 1:
                    print "Error: '%s' could not be located in CloudStack database using '%s' because it is not unique -- Exit." % (
                        csname, csApiCall)
                    sys.exit(1)

            else:
                print "Error: '%s' could not be located in CloudStack database using '%s' -- exit!" % (
                    csname, csApiCall)
                # Exit if not found
                sys.exit(1)

        except Exception as err:
            print "Error: " + str(err)
            return 1
        except urllib2.HTTPError as e:
            print "Error: Command failed: " + str(e.msg)
            return 1

        if self.DEBUG == 1:
            print "DEBUG: Found: '%s' with ID %s." % (csname, csnameID)

        return csnameID

    # Find Random storagePool for Cluster
    def getRandomStoragePool(self, clusterID):
        apicall = listStoragePools.listStoragePoolsCmd()
        apicall.clusterid = str(clusterID)
        apicall.listAll = "true"

        # Call CloudStack API
        data = self._callAPI(apicall)

        # Select a random storage pool that belongs to this cluster
        toStorageData = choice(data)
        targetStorageID = toStorageData.id
        if self.DEBUG == 1:
            print "DEBUG: Selected storage pool: " + targetStorageID + " (" + toStorageData.name + ")" + " for cluster " + clusterID

        return targetStorageID

    # Find storagePool for Cluster
    def getStoragePool(self, clusterID):
        apicall = listStoragePools.listStoragePoolsCmd()
        apicall.clusterid = str(clusterID)
        apicall.listAll = "true"

        # Call CloudStack API
        data = self._callAPI(apicall)

        return data

    # Find storagePool for Cluster with most free space
    def getStoragePoolWithMostFreeSpace(self, clusterID):
        apicall = listStoragePools.listStoragePoolsCmd()
        apicall.clusterid = str(clusterID)
        apicall.listAll = "true"

        # Call CloudStack API
        pools = self._callAPI(apicall)

        lowest_pool_utilisation = 100
        data = None

        for pool_data in pools:
            try:
                pool_utilisation = float(pool_data.disksizeused) / float(pool_data.disksizetotal)
            except:
                pool_utilisation = 1

            pool_utilisation_display = pool_utilisation * 100

            if pool_utilisation < lowest_pool_utilisation:
                lowest_pool_utilisation = pool_utilisation
                if self.DEBUG == 1:
                    print "Debug: Pool %s has utilisation of %s %%, currently lowest. Checking others" % (
                        pool_data.name, str(pool_utilisation_display))
                data = pool_data

        if data is not None:
            print "Note: Selected Pool %s" % data.name
            return data
        else:
            return False

    # Get storagePool data
    def getStoragePoolData(self, storagepoolID):
        apicall = listStoragePools.listStoragePoolsCmd()
        apicall.id = str(storagepoolID)
        apicall.listAll = "true"

        # Call CloudStack API
        return self._callAPI(apicall)

    # Find all hosts in a given cluster
    def getAllHostsFromCluster(self, clusterID):
        apicall = listHosts.listHostsCmd()
        apicall.clusterid = str(clusterID)
        apicall.listAll = "true"

        # Call CloudStack API
        return self._callAPI(apicall)

    # Find hosts in a given cluster
    def getHostsFromCluster(self, clusterID):
        apicall = listHosts.listHostsCmd()
        apicall.clusterid = str(clusterID)
        apicall.resourcestate = "Enabled"
        apicall.state = "Up"
        apicall.listAll = "true"

        # Call CloudStack API
        return self._callAPI(apicall)

    # Get host data
    def getRandomHostFromCluster(self, clusterID):

        hosts_list = self.getHostsFromCluster(clusterID)
        return choice(hosts_list)

    # Find enabled hosts in a given cluster excluding it's hosts which have been marked dedicated
    def getSharedHostsFromCluster(self, clusterID):
        apicall = listHosts.listHostsCmd()
        apicall.clusterid = str(clusterID)
        apicall.resourcestate = "Enabled"
        apicall.listAll = "true"

        # Call CloudStack API
        clusterhostdetails = self._callAPI(apicall)

        # Remove dedicated hosts from the results
        dedicatedhosts = self.getDedicatedHosts()
        clusterhostdetails_orig = list(clusterhostdetails)
        if dedicatedhosts:
            for h in clusterhostdetails_orig:
                for d in dedicatedhosts:
                    if h.name == d.name:
                        if self.DEBUG == 1:
                            print "Remove dedicated host from the list: " + str(d.name)
                        clusterhostdetails.remove(h)
        return clusterhostdetails

    # Find dedicated hosts
    def getDedicatedHosts(self):
        apicall = listDedicatedHosts.listDedicatedHostsCmd()
        apicall.listAll = "true"

        # Call CloudStack API
        return self._callAPI(apicall)

    # Generic listVirtualMachines function
    def listVirtualMachines(self, args):
        return self.exoCsApi.listVirtualMachines(**args)

    # Generic listRouters function
    def listRouters(self, args):
        return self.exoCsApi.listRouters(**args)

    # Generic listVirtualMachines function - DEPRECATED
    def deprecatedListVirtualMachines(self, args):
        args = self.remove_empty_values(args)

        apicall = listVirtualMachines.listVirtualMachinesCmd()
        apicall.listAll = (args['listAll']) if 'listAll' in args else 'true'
        apicall.networkid = (
            str(args['networkid'])) if 'networkid' in args else None
        apicall.projectid = (
            '-1') if 'isProjectVm' in args and args['isProjectVm'] == 'true' else None
        apicall.hostid = (str(args['hostid'])) if 'hostid' in args else None
        apicall.domainid = (
            str(args['domainid'])) if 'domainid' in args else None
        apicall.keyword = (
            args['filterKeyword']) if 'filterKeyword' in args else None

        # Call CloudStack API
        return self._callAPI(apicall)

    # Find volume
    def getVolumeData(self, volumeid):
        apicall = listVolumes.listVolumesCmd()
        apicall.id = str(volumeid)
        apicall.listAll = "true"

        # Call CloudStack API
        return self._callAPI(apicall)

    # Find volumes connected to a given vmid
    def getVirtualmachineVolumes(self, vmid, isProjectVm='false'):
        apicall = listVolumes.listVolumesCmd()
        apicall.virtualmachineid = str(vmid)
        apicall.listAll = "true"
        if isProjectVm == 'true':
            apicall.projectid = "-1"

        # Call CloudStack API
        return self._callAPI(apicall)

    # Get virtualserver data
    def getVirtualmachineData(self, vmid, isProjectVm='false'):
        apicall = listVirtualMachines.listVirtualMachinesCmd()
        apicall.id = str(vmid)
        apicall.listAll = "true"

        if isProjectVm == 'true':
            apicall.projectid = "-1"

        # Call CloudStack API
        return self._callAPI(apicall)

    # Get virtualrouter data
    def getRouterData(self, args):
        args = self.remove_empty_values(args)

        apicall = listRouters.listRoutersCmd()
        apicall.networkid = (
            str(args['networkid'])) if 'networkid' in args else None
        apicall.name = (str(args['name'])) if 'name' in args else None
        apicall.id = (str(args['id'])) if 'id' in args else None
        apicall.listAll = (args['listAll']) if 'listAll' in args else 'true'
        apicall.requiresupgrade = (
            str(args['requiresupgrade'])) if 'requiresupgrade' in args else None
        apicall.projectid = (
            '-1') if 'isProjectVm' in args and args['isProjectVm'] == 'true' else None
        apicall.hostid = (str(args['hostid'])) if 'hostid' in args else None
        apicall.domainid = (
            str(args['domainid'])) if 'domainid' in args else None
        apicall.state = (str(args['state'])) if 'state' in args else None

        # Call CloudStack API
        return self._callAPI(apicall)

    def getRedundantRouters(self, args):
        args = self.remove_empty_values(args)

        # Get all routers
        routerData = self.getRouterData(args)
        if routerData is None or routerData == 1:
            return routerData

        redRouters = {}

        # Loop routers and look for redundant ones
        for router in routerData:
            if router.isredundantrouter == False:
                continue
            redRouters[
                router.guestnetworkid] = self.getRouterPeerData(
                router.name,
                'false',
                'true')

        # Return the redundant routers
        return redRouters

    # Get systemvm data
    def getSystemVmData(self, args):
        args = self.remove_empty_values(args)

        apicall = listSystemVms.listSystemVmsCmd()
        apicall.name = (str(args['name'])) if 'name' in args else None
        apicall.hostid = (str(args['hostid'])) if 'hostid' in args else None
        apicall.state = (str(args['state'])) if 'state' in args else None
        apicall.systemvmtype = (
            str(args['systemvmtype'])) if 'systemvmtype' in args else None
        apicall.zoneid = (str(args['zoneid'])) if 'zoneid' in args else None

        # Call CloudStack API
        return self._callAPI(apicall)

    # Get the peer of the given router
    def getRouterPeerData(
            self,
            routername,
            projectParam='false',
            silent='false'):
        routerData = self.getRouterData(
            {'name': routername, 'isProjectVm': projectParam})
        router = routerData[0]
        for nic in router.nic:
            if nic.traffictype == "Guest":
                routersOfNetwork = self.getRouterData(
                    {'networkid': nic.networkid, 'state': 'Running'})
                if routersOfNetwork is None or len(routersOfNetwork) != 2:
                    if silent == 'True':
                        print "Error: Cannot find the redundant peer of this router. Please make sure it is running before continuing."
                    return 1
                for redundantRouter in routersOfNetwork:
                    if routername == redundantRouter.name:
                        if silent == 'True':
                            print "Note: Double check OK for router " + routername + ": Found myself."
                    else:
                        routerPeerData = redundantRouter
                        peerHostData = self.getHostData(
                            {'hostname': routerPeerData.hostname})
                        if silent == 'True':
                            print "Note: The redundant peer of router " + routername + " is " + routerPeerData.name + " running on " + routerPeerData.hostname + " (" + \
                                  peerHostData[0].clustername + " / " + peerHostData[0].podname + ")."
                        returnData = {
                            "guestnetworkid": router.guestnetworkid,
                            "router": router,
                            "routerPeer": routerPeerData,
                            "clustername": peerHostData[0].clustername,
                            "podname": peerHostData[0].podname}
                        return returnData

    # Stop virtualrouter
    def stopRouter(self, vmid):
        apicall = stopRouter.stopRouterCmd()
        apicall.id = str(vmid)

        # Call CloudStack API
        return self._callAPI(apicall)

    # Start virtualrouter
    def startRouter(self, vmid):
        apicall = startRouter.startRouterCmd()
        apicall.id = str(vmid)

        # Call CloudStack API
        return self._callAPI(apicall)

    # Destroy virtualrouter
    def destroyRouter(self, vmid):
        apicall = destroyRouter.destroyRouterCmd()
        apicall.id = str(vmid)

        # Call CloudStack API
        return self._callAPI(apicall)

    # Restart isolated network
    def restartNetwork(self, vmid, cleanup='true'):
        apicall = restartNetwork.restartNetworkCmd()
        apicall.id = str(vmid)
        apicall.cleanup = str(cleanup)

        # Call CloudStack API
        return self._callAPI(apicall)

    # Restart VPC network
    def restartVPC(self, vmid, cleanup='true'):
        apicall = restartVPC.restartVPCCmd()
        apicall.id = str(vmid)
        apicall.cleanup = str(cleanup)

        # Call CloudStack API
        return self._callAPI(apicall)

    # Reboot virtualrouter
    def rebootRouter(self, vmid):
        apicall = rebootRouter.rebootRouterCmd()
        apicall.id = str(vmid)

        # Call CloudStack API
        return self._callAPI(apicall)

    # Send an e-mail
    def sendMail(self, mailfrom, mailto, subject, htmlcontent):
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject.decode('ascii', 'ignore')
        msg['From'] = mailfrom.decode('ascii', 'ignore')
        msg['To'] = mailto.decode('ascii', 'ignore')

        # htmlcontent to proper ASCII
        htmlcontent = htmlcontent.decode('ascii', 'ignore')

        # HTML part
        htmlpart = MIMEText(htmlcontent, 'html')
        msg.attach(htmlpart)

        s = smtplib.SMTP(self.smtpserver)
        s.sendmail(msg['From'], msg['To'], msg.as_string())
        s.quit()

    # Stop virtualvirtualmachine
    def stopVirtualMachine(self, vmid, force="false", timeout=900):
        try:
            with Timeout(timeout):
                apicall = stopVirtualMachine.stopVirtualMachineCmd()
                apicall.id = str(vmid)
                apicall.forced = force

                # Call CloudStack API
                return self._callAPI(apicall)
        except Timeout.Timeout:
            print "Timeout!"
            return 1

    # Start virtualvirtualmachine
    def startVirtualMachine(self, vmid, hostid="", timeout=900):
        try:
            with Timeout(timeout):
                apicall = startVirtualMachine.startVirtualMachineCmd()
                apicall.id = str(vmid)
                apicall.forced = "false"
                if len(hostid) > 0:
                    apicall.hostid = hostid

                # Call CloudStack API
                return self._callAPI(apicall)
        except Timeout.Timeout:
            print "Timeout!"
            return 1

    # migrateVirtualMachine
    def migrateVirtualMachine(self, vmid, hostid):
        apicall = migrateVirtualMachine.migrateVirtualMachineCmd()
        apicall.virtualmachineid = str(vmid)
        apicall.hostid = str(hostid)

        # Call CloudStack API
        return self._callAPI(apicall)

    # migrateVirtualMachine with Volumes
    def migrateVirtualMachineWithVolume(self, vmid, hostid):
        vmresult = self.exoCsApi.migrateVirtualMachineWithVolume(hostid=hostid, virtualmachineid=vmid)
        return self.__waitforjob(vmresult['jobid'])

    # migrateSystemVm
    def migrateSystemVm(self, args):
        args = self.remove_empty_values(args)
        if not 'vmid' in args:
            return False
        if not 'projectParam' in args:
            args['projectParam'] = "false"

        if not 'hostid' in args:
            systemvm = self.getRouterData({'id': args['vmid'], 'isProjectVm': args['projectParam']})[0]
            if self.DEBUG:
                print "Received systemvm:"
                print systemvm

            requested_memory = self.get_needed_memory(systemvm)
            host_data = self.getHostData({'hostid': systemvm.hostid})[0]
            if self.DEBUG:
                print "Received host_data:"
                print host_data
            migration_host = self.findBestMigrationHost(
                host_data.clusterid,
                host_data.name,
                requested_memory)

        apicall = migrateSystemVm.migrateSystemVmCmd()
        apicall.virtualmachineid = (str(args['vmid'])) if 'vmid' in args else None
        apicall.hostid = (str(args['hostid'])) if 'hostid' in args else migration_host.id

        # Call CloudStack API
        return self._callAPI(apicall)

    # migrate volume
    def migrateVolume(self, volid, storageid):
        apicall = migrateVolume.migrateVolumeCmd()
        apicall.volumeid = str(volid)
        apicall.storageid = str(storageid)

        # Call CloudStack API
        return self._callAPI(apicall)

    def getDomainAdminUserData(self, domainid):
        apicall = listUsers.listUsersCmd()
        apicall.domainid = str(domainid)

        # Call CloudStack API
        data = self._callAPI(apicall)

        if data is None or data == 1:
            return 1

        for userdata in data:
            # Return an admin account
            if "admin" in userdata.username:
                return userdata
            else:
                continue

        # Otherwise return the first one found
        return data[0]

    # Get host data
    def getHostData(self, args):
        args = self.remove_empty_values(args)

        apicall = listHosts.listHostsCmd()
        apicall.id = (str(args['hostid'])) if 'hostid' in args else None
        apicall.name = (str(args['hostname'])) if 'hostname' in args else None

        # Call CloudStack API
        return self._callAPI(apicall)

    # Update host tags
    def updateHostTags(self, hostid, hosttags):
        apicall = updateHost.updateHostCmd()
        apicall.id = hostid
        apicall.hosttags = hosttags

        # Call CloudStack API
        return self._callAPI(apicall)

    # Deploy virtual machine
    def deployVirtualMachine(self, args):
        args = self.remove_empty_values(args)

        apicall = deployVirtualMachine.deployVirtualMachineCmd()
        apicall.domainid = (str(args['domainid'])) if 'domainid' in args else None
        apicall.networkids = (str(args['networkids'])) if 'networkids' in args else None
        apicall.templateid = (str(args['templateid'])) if 'templateid' in args else None
        apicall.serviceofferingid = (str(args['serviceofferingid'])) if 'serviceofferingid' in args else None
        apicall.zoneid = (str(args['zoneid'])) if 'zoneid' in args else None
        apicall.account = (str(args['account'])) if 'account' in args else None
        apicall.name = (str(args['name'])) if 'name' in args else None
        apicall.displayname = (str(args['displayname'])) if 'displayname' in args else None
        apicall.ipaddress = (str(args['ipaddress'])) if 'ipaddress' in args else None
        apicall.startvm = (str(args['startvm'])) if 'startvm' in args else None
        apicall.rootdisksize = (str(args['rootdisksize'])) if 'rootdisksize' in args else None
        apicall.iptonetworklist = args['iptonetworklist'] if 'iptonetworklist' in args else None

        # Call CloudStack API
        return self._callAPI(apicall)

    # Create volume
    def createVolume(self, args):
        args = self.remove_empty_values(args)

        apicall = createVolume.createVolumeCmd()
        apicall.name = (str(args['name'])) if 'name' in args else None
        apicall.domainid = (str(args['domainid'])) if 'domainid' in args else None
        apicall.account = (str(args['account'])) if 'account' in args else None
        apicall.diskofferingid = (str(args['diskofferingid'])) if 'diskofferingid' in args else None
        apicall.size = (str(args['size'])) if 'size' in args else None
        apicall.zoneid = (str(args['zoneid'])) if 'zoneid' in args else None

        # Call CloudStack API
        return self._callAPI(apicall)

    # Attach volume
    def attachVolume(self, args):
        args = self.remove_empty_values(args)

        apicall = attachVolume.attachVolumeCmd()
        apicall.id = (str(args['id'])) if 'id' in args else None
        apicall.virtualmachineid = (str(args['virtualmachineid'])) if 'virtualmachineid' in args else None
        apicall.deviceid = (str(args['deviceid'])) if 'deviceid' in args else None

        # Call CloudStack API
        return self._callAPI(apicall)

    # Generate a random name
    def generateRandomName(self, prefix):
        name = prefix + (''.join(choice(string.digits)
                                 for i in range(5)))
        return name

    # Destroy VM
    def destroyVirtualMachine(self, vmid):
        apicall = destroyVirtualMachine.destroyVirtualMachineCmd()
        apicall.id = vmid
        apicall.expunge = "true"

        # Call CloudStack API
        return self._callAPI(apicall)

    # Get setting
    def getConfiguration(self, setting):
        apicall = listConfigurations.listConfigurationsCmd()
        apicall.name = setting

        # Call CloudStack API
        return self._callAPI(apicall)

    # Get volumes
    def listVolumes(self, storageid, isProjectVm):
        apicall = listVolumes.listVolumesCmd()
        apicall.storageid = storageid

        if isProjectVm == 'true':
            apicall.projectid = "-1"

        # get default.page.size
        result = self.getConfiguration("default.page.size")
        apicall.listAll = "true"
        apicall.pagesize = result[0].value

        # Call API multiple times to get all volumes
        page = 0
        apicall.page = page

        # As long as we receive useful output, keep going
        volumes = []
        while result is not None:
            page = page + 1
            apicall.page = page
            result = self._listVolumesCall(apicall)
            if result is not None:
                if 'volumes' in locals():
                    volumes = volumes + result
                else:
                    volumes = result

        return volumes

    # Internal function used by listVolumes
    def _listVolumesCall(self, apicall):
        try:
            data = self.cloudstack.marvin_request(apicall)
            if (data is None) and self.DEBUG == 1:
                print "Warning: Received None object from CloudStack API"

            if self.DEBUG == 1:
                print "DEBUG: received data:"
                print data

        except Exception as err:
            print "Error: " + str(err)
            return 1
        except urllib2.HTTPError as e:
            print "Error: Command failed: " + str(e.msg)
            return 1

        return data

    # Calculate storage usage of vm
    def calculateVirtualMachineStorageUsage(self, vmid, isProjectVm):
        # Get vm volume data
        result = self.getVirtualmachineVolumes(vmid, isProjectVm)
        storageSize = 0
        if result is not None:
            for vol in result:
                storageSize = storageSize + (vol.size / 1024 / 1024 / 1024)
            return storageSize
        return 0

    # list clusters
    def listClusters(self, args):
        args = self.remove_empty_values(args)
        apicall = listClusters.listClustersCmd()
        apicall.id = (str(args['clusterid'])) if 'clusterid' in args else None
        apicall.zoneid = (str(args['zoneid'])) if 'zoneid' in args else None
        apicall.podid = (str(args['podid'])) if 'podid' in args else None
        apicall.allocationstate = (
            str(args['allocationstate'])) if 'allocationstate' in args else None
        apicall.clustertype = (
            str(args['clustertype'])) if 'clustertype' in args else None
        apicall.hypervisor = (
            str(args['hypervisor'])) if 'hypervisor' in args else None
        apicall.name = (str(args['name'])) if 'name' in args else None

        # Call CloudStack API
        return self._callAPI(apicall)

    # list snapshots
    def listSnapshots(self, volid, isProjectVm='false'):
        apicall = listSnapshots.listSnapshotsCmd()
        apicall.volumeid = volid
        apicall.listAll = "true"

        if isProjectVm == 'true':
            apicall.projectid = "-1"

        # Call CloudStack API
        return self._callAPI(apicall)

    # list networks
    def listNetworks(self, networkid):
        apicall = listNetworks.listNetworksCmd()
        apicall.id = networkid
        apicall.listAll = "true"

        # Call CloudStack API
        return self._callAPI(apicall)

    # list vpcs
    def listVPCs(self, vpcid):
        apicall = listVPCs.listVPCsCmd()
        apicall.id = vpcid
        apicall.listAll = "true"

        # Call CloudStack API
        return self._callAPI(apicall)

    # list listVMSnapshot
    def listVMSnapshot(self, vmid):
        apicall = listVMSnapshot.listVMSnapshotCmd()
        apicall.virtualmachineid = vmid
        apicall.listAll = "true"

        # Call CloudStack API
        return self._callAPI(apicall)

    # list service offerings
    def listServiceOfferings(self, args):
        args = self.remove_empty_values(args)

        apicall = listServiceOfferings.listServiceOfferingsCmd()
        apicall.id = (
            str(args['serviceofferingid'])) if 'serviceofferingid' in args else None
        apicall.issystem = (
            str(args['issystem'])) if 'issystem' in args else None

        # Call CloudStack API
        return self._callAPI(apicall)

    # Get hosttags
    def getServiceOfferingTags(self, serviceofferingid, tagtype):
        # Service Offering
        serviceOfferingData = self.listServiceOfferings(
            {'serviceofferingid': serviceofferingid, 'issystem': 'true'})

        # The required tags
        if tagtype == "host":
            tags = (serviceOfferingData[0].hosttags) if serviceOfferingData[
                                                            0].hosttags is not None else ''
        elif tagtype == "storage":
            tags = (serviceOfferingData[0].tags) if serviceOfferingData[
                                                        0].tags is not None else ''
        else:
            return 1
        return tags

    # Check storagetags
    def checkStorageTags(self, args):
        args = self.remove_empty_values(args)

        toClusterID = (
            str(args['toClusterID'])) if 'toClusterID' in args else None
        routername = (
            str(args['routername'])) if 'routername' in args else None
        projectParam = (
            str(args['projectParam'])) if 'projectParam' in args else 'false'

        if routername is None:
            print "Error: required field 'routername' not supplied."
            return 1
        if toClusterID is None:
            print "Error: required field 'toClusterID' not supplied."
            return 1

        # get router data
        routerData = self.getRouterData(
            {'name': routername, 'isProjectVm': projectParam})
        router = routerData[0]

        # The required tags
        storagetags = self.getServiceOfferingTags(
            router.serviceofferingid,
            "storage")

        # Check tags
        storagepooltags = self.getStoragePoolTags(toClusterID)

        if self.DEBUG == 1:
            print "Debug: storage tags of service offering: " + storagetags
            print "Debug: storage tags of storage pool: " + storagepooltags

        if storagetags == '':
            print "Warning: router service offering has empty storage tags."

        if storagetags != '' and storagepooltags != storagetags and self.FORCE == 0:
            if self.DEBUG == 1:
                print "Error: cannot do this: storage tags from provided storage pool '" + storagepooltags + "' do not match your vm's service offering '" + storagetags + "'"
            return 1
        elif storagetags != '' and storagepooltags != storagetags and self.FORCE == 1:
            if self.DEBUG == 1:
                print "Warning: storage tags from provided storage pool '" + storagepooltags + "' do not match your vm's service offering '" + storagetags + "'. Since you used --FORCE you probably know what you manually need to edit in the database."
        elif self.DEBUG == 1:
            print "Note: Storage tags look OK."

        return 0

    # Check hosttags
    def checkHostTags(self, args):
        args = self.remove_empty_values(args)

        toClusterID = (
            str(args['toClusterID'])) if 'toClusterID' in args else None
        routername = (
            str(args['routername'])) if 'routername' in args else None
        projectParam = (
            str(args['projectParam'])) if 'projectParam' in args else 'false'

        if routername is None:
            print "Error: required field 'routername' not supplied."
            return 1
        if toClusterID is None:
            print "Error: required field 'toClusterID' not supplied."
            return 1

        # get router data
        routerData = self.getRouterData(
            {'name': routername, 'isProjectVm': projectParam})
        router = routerData[0]

        # The required tags
        hosttags = self.getServiceOfferingTags(
            router.serviceofferingid,
            "host")

        if self.DEBUG == 1:
            print "Debug: host tags of router: " + hosttags

        # Search for hosttags on the selected cluster
        toClusterHostsData = self.getHostsFromCluster(toClusterID)
        foundHostTag = False
        if toClusterHostsData is not None:
            for host in toClusterHostsData:
                if self.DEBUG == 1:
                    print "Debug: Checking host tags of host " + host.name
                if host.hosttags is not None:
                    if hosttags in host.hosttags:
                        foundHostTag = True

        if hosttags != '' and foundHostTag == False and self.FORCE == 0:
            if self.DEBUG == 1:
                print "Error: cannot do this: the hosts in your selected cluster do not have the tags '" + hosttags + "' that are required by your router's service offering."
            return 1
        elif self.FORCE == 1 and self.DEBUG == 1:
            print "Warning: the hosts in your selected cluster do not have your vm's service offering '" + hosttags + "', so this will not work. Since you used --FORCE you probably know what you're doing."
        elif self.DEBUG == 1:
            print "Note: At least one of the hosts in the cluster has the required host tag '" + hosttags + "' set, so we can continue."

        return 0

    # Find storage pool of selected cluster
    def getStoragePoolTags(self, toClusterID):
        targetStorageID = self.getStoragePool(toClusterID)[0].id
        targetStoragePoolData = self.getStoragePoolData(targetStorageID)
        if targetStoragePoolData[0].tags is None:
            return ""
        return targetStoragePoolData[0].tags

    def getZoneId(self, zonename):

        apicall = listZones.listZonesCmd()
        apicall.name = zonename

        # Call CloudStack API
        result = self._callAPI(apicall)

        if result is not None:
            return result[0].id
        else:
            return None

    def getDetachedVolumes(self, storagepoolid):

        volumes = self.listVolumes(storagepoolid, False)

        orphans = []

        if volumes is not None:
            # sort results by domain
            volumes.sort(key=lambda vol: vol.domain, reverse=True)

            # select volumes with no vmname attached
            for volume in volumes:
                if volume.vmname is None:
                    orphans.append(volume)

        # return selected detached volumes
        return orphans

    # Check zone
    def checkZone(self, routerClusterID, toClusterID):
        routerClusterData = self.listClusters({'clusterid': routerClusterID})
        if routerClusterData is None:
            print "Error: could not find cluster with id " + routerClusterID
            return 1

        targetStorageID = self.getStoragePool(toClusterID)[0].id
        storagepooltags = self.getStoragePoolTags(toClusterID)
        targetStoragePoolData = self.getStoragePoolData(targetStorageID)

        if self.DEBUG == 1:
            print "Debug: You selected a storage pool with tags '" + storagepooltags + "'"

        # Check zone of current and destination clusters
        if targetStoragePoolData[0].zonename != routerClusterData[0].zonename:
            print "Error: cannot do this: Router is currently in zone " + routerClusterData[
                0].zonename + " and you selected a cluster in zone " + targetStoragePoolData[0].zonename + "."
            return 1

        # All OK
        return 0

    # Check to see if cluster has specified hosttags
    def checkClusterHostTags(self, clusterID, hosttags):
        clusterHostsData = self.getHostsFromCluster(clusterID)
        foundHostTag = False
        if clusterHostsData is not None:
            for host in clusterHostsData:
                if self.DEBUG == 1:
                    print "Debug: Checking host tags of host " + host.name
                if host.hosttags is not None:
                    if hosttags in host.hosttags:
                        foundHostTag = True

        return foundHostTag

    # prepareHostForMaintenance
    def prepareHostForMaintenance(self, hostid):
        apicall = prepareHostForMaintenance.prepareHostForMaintenanceCmd()
        apicall.id = hostid

        # Call CloudStack API
        return self._callAPI(apicall)

    # cancelHostMaintenance
    def cancelHostMaintenance(self, hostid):
        apicall = cancelHostMaintenance.cancelHostMaintenanceCmd()
        apicall.id = hostid

        # Call CloudStack API
        return self._callAPI(apicall)

    # findHostsForMigration
    def findHostsForMigration(self, virtualmachineid):
        apicall = findHostsForMigration.findHostsForMigrationCmd()
        apicall.virtualmachineid = virtualmachineid

        # Call CloudStack API
        return self._callAPI(apicall)

    # updateCluster
    def updateCluster(self, args):
        args = self.remove_empty_values(args)

        apicall = updateCluster.updateClusterCmd()
        apicall.id = str(args['clusterid'])
        apicall.allocationstate = (
            str(
                args['allocationstate'])) if 'allocationstate' in args and len(
            args['allocationstate']) > 0 else None
        apicall.managedstate = (str(args['managedstate'])) if 'managedstate' in args and len(
            args['managedstate']) > 0 else None

        # Call CloudStack API
        return self._callAPI(apicall)

    # updateHost
    def updateHost(self, args):
        args = self.remove_empty_values(args)

        apicall = updateHost.updateHostCmd()
        apicall.id = str(args['hostid'])
        apicall.allocationstate = (
            str(
                args['allocationstate'])) if 'allocationstate' in args and len(
            args['allocationstate']) > 0 else None

        # Call CloudStack API
        return self._callAPI(apicall)

    # list domains
    def listDomains(self, domainid=''):
        apicall = listDomains.listDomainsCmd()
        apicall.listAll = "true"
        apicall.state = "Enabled"
        if len(str(domainid)) > 0:
            apicall.id = domainid

        # Call CloudStack API
        return self._callAPI(apicall)

    # list templates
    def listTemplates(self, args):
        args = self.remove_empty_values(args)

        apicall = listTemplates.listTemplatesCmd()
        apicall.keyword = (str(args['keyword'])) if 'keyword' in args and len(
            args['keyword']) > 0 else ""
        apicall.zoneid = (str(args['zoneid'])) if 'zoneid' in args and len(
            args['zoneid']) > 0 else ""
        apicall.templatefilter = (str(args['templatefilter'])) if 'templatefilter' in args and len(
            args['templatefilter']) > 0 else "featured"
        apicall.page = 1
        apicall.pagesize = 1500

        # Call CloudStack API
        return self._callAPI(apicall)

    # update template permissions
    def updateTemplatePermissins(self, args):
        args = self.remove_empty_values(args)

        apicall = updateTemplatePermissions.updateTemplatePermissionsCmd()
        apicall.id = str(args['templateid'])
        apicall.isfeatured = (str(args['isfeatured'])) if 'isfeatured' in args and len(
            args['isfeatured']) > 0 else 'false'
        apicall.ispublic = (str(args['ispublic'])) if 'ispublic' in args and len(
            args['ispublic']) > 0 else None

        # Call CloudStack API
        return self._callAPI(apicall)

    # delete template
    def deleteTemplate(self, args):
        args = self.remove_empty_values(args)

        apicall = deleteTemplate.deleteTemplateCmd()
        apicall.id = str(args['id'])

        # Call CloudStack API
        return self._callAPI(apicall)

    # list users
    def listUsers(self, accountType, domainID='', listAll='true'):
        if len(str(accountType)) == 0:
            return 1

        apicall = listUsers.listUsersCmd()
        apicall.accounttype = accountType
        apicall.listAll = listAll
        apicall.state = "Enabled"
        if len(domainID) > 0:
            apicall.domainid = domainID

        # Call CloudStack API
        return self._callAPI(apicall)

    # report users
    def reportUsers(self):
        domainData = {}
        allDomains = self.listDomains()

        for domain in allDomains:
            accountType = 2
            listAll = "true"

            if domain.name == "ROOT":
                accountType = 1
                listAll = "false"
            elif domain.name == "Cust":
                continue
            elif domain.name == "Ext":
                continue
            elif domain.name == "Test":
                continue

            if self.DEBUG == 1:
                print str(accountType) + " " + domain.id + " " + listAll

            domainUsers = self.listUsers(accountType, domain.id, listAll)
            domainData[domain.id] = []
            domainData[domain.id].append(domainUsers)

        return domainData

    # Remove non-ascii chars
    def removeNonAscii(self, s):
        return "".join([x if ord(x) < 128 else '?' for x in s])

    # Get cloud name
    def getCloudName(self):
        return self.apiurl

    # Prepare host for maintenance
    def startMaintenance(self, hostID, hostname):
        hostData = self.getHostData({'hostname': hostname})
        if hostData == 1:
            return False
        for host in hostData:
            if host.name == hostname:
                foundHostData = host

        if self.DRYRUN == 1:
            print "\nNote: Would have prepared host '" + hostname + "' for maintenance"
            return False
        else:
            # Get vm count
            if foundHostData.hypervisor == "XenServer":
                retcode, vmcount = self.ssh.getXapiVmCount(
                    foundHostData.ipaddress)
            if foundHostData.hypervisor == "KVM":
                vmcount = self.kvm.host_get_vms(
                    foundHostData)
            print "Note: Preparing host '" + hostname + "' for maintenance, " + str(vmcount) + " VMs to migrate.."

            # Maintenance
            maintenanceResult = self.prepareHostForMaintenance(hostID)

        # Did it work?
        if maintenanceResult is None or maintenanceResult == 1:
            print "Error: Got an empty result from prepareForMaintenance call"
            print "Error: Please investigate manually. Halting."
            return False

        if self.DEBUG == 1:
            print maintenanceResult

        if maintenanceResult.resourcestate == "PrepareForMaintenance":
            print "Note: Host '" + hostname + "' is in state '" + maintenanceResult.resourcestate + "'"
            print "Note: Waiting for it to migrate all vm's..."

        # Defaults
        vmcount = 0
        vmcount_previous = 0
        vmcount_same_counter = 0

        # Check result
        while True:
            hostData = self.getHostData({'hostname': hostname})
            for host in hostData:
                if host.name == hostname:
                    foundHostData = host

                # Get vm count
                try:
                    if hostData.hypervisor == "XenServer":
                        retcode, vmcount = self.ssh.getXapiVmCount(
                            foundHostData.ipaddress)
                    if hostData.hypervisor == "KVM":
                        retcode, vmcount = self.kvm.host_get_vms(
                            foundHostData.ipaddress)
                except:
                    pass

            if foundHostData.resourcestate == "PrepareForMaintenance":
                print "Note: Resource state currently is '" + foundHostData.resourcestate + \
                      "'. Number of VMs still to be migrated: " + str(vmcount) + "    "
                sys.stdout.write("\033[F")

                # Wait before checking again
                time.sleep(6)

            elif foundHostData.resourcestate == "Enabled":
                print "Note: Resource state currently is '" + foundHostData.resourcestate + \
                      "', maintenance must have been cancelled, returning"
                break
            else:
                # lots of spaces to clear previous line
                print "Note: Resource state currently is '" + foundHostData.resourcestate + \
                      "', that's looking good! Returning..                "
                break

            # Return if the same for 100x6 sec
            if vmcount == vmcount_previous:
                vmcount_same_counter = vmcount_same_counter + 1
            else:
                vmcount_same_counter = 0
            if vmcount_same_counter >= 100:
                print "Warning: The number of vm's still to migrate is still " + vmcount + \
                      " for 600s, returning and trying manual migration instead"
                break

            if self.DEBUG == 1:
                print "vmcount: " + str(vmcount) + " vmcount_previous: " + str(vmcount_previous)

            # Remember vmcount
            vmcount_previous = vmcount

        # Final result
        if foundHostData.resourcestate == "Maintenance":
            print "Note: Host '" + hostname + "' is in state Maintenance!"
            return True
        elif foundHostData.resourcestate == "ErrorInMaintenance":
            print "Note: Host '" + hostname + "' did not yet enter Maintenance.. will try to migrate vm's manually"
            return False
        elif foundHostData.resourcestate == "Enabled":
            print "Note: Host '" + hostname + "' maintenance was cancelled outside of script.. " \
                                              "will try to migrate vm's manually"
            return False
        else:
            print "Note: Host '" + hostname + "' did not yet enter Maintenance. Cancel maintenance and trying " \
                                              "to migrate vm's manually"
            self.cancelHostMaintenance(hostID)
            return False

    def safeToPutInMaintenance(self, clusterid):
        # Get all hosts
        clusterHostsData = self.getAllHostsFromCluster(clusterid)

        # Safe to put hypervisor in maintenance?
        safe = True

        # Look at all hosts
        for clusterhost in clusterHostsData:
            if clusterhost.resourcestate == "PrepareForMaintenance":
                safe = False
            elif clusterhost.resourcestate == "Maintenance":
                safe = False
            elif clusterhost.resourcestate == "ErrorInMaintenance":
                safe = False
        return safe

    # print hypervisor table
    def printHypervisors(self, clusterid, poolmaster=False, checkBonds=False, hypervisor="XenServer"):

        print "Note: Checking.."
        clusterHostsData = self.getAllHostsFromCluster(clusterid)

        # Start table
        t = PrettyTable(["Hostname",
                         "Poolmaster",
                         "Resource state",
                         "State",
                         "# VMs",
                         "Bond Status"])

        for clusterhost in sorted(clusterHostsData, key=lambda h: h.name):

            # Some progress indication
            sys.stdout.write(clusterhost.name + ", ")
            sys.stdout.flush()

            pm = "n/a"
            if hypervisor == "XenServer" and not poolmaster:
                if self.DEBUG == 1:
                    print "Debug: Looking for poolmaster"
                poolmaster = self.xenserver.get_poolmaster(clusterhost)

            if hypervisor == "XenServer":
                # Poolmaster
                if clusterhost.name == poolmaster.strip():
                    pm = "<------"
                else:
                    pm = ""

            # Check bonds
            bondstatus = "UNTESTED"
            if checkBonds is True:
                try:
                    if hypervisor == "XenServer":
                        bondscripts = self.xenserver.put_scripts(
                            clusterhost)
                        bondstatus = self.xenserver.get_bond_status(
                            clusterhost)
                    if hypervisor == "KVM":
                        bondscripts = self.kvm.put_scripts(
                            clusterhost)
                        bondstatus = self.kvm.get_bond_status(
                            clusterhost)
                except:
                    bondstatus = "UNKNOWN"
            else:
                bondstatus = "UNTESTED"

            vmcount = "UNKNOWN"
            try:
                if hypervisor == "XenServer":
                    vmcount = self.xenserver.host_get_vms(
                        clusterhost)
                if hypervisor == "KVM":
                    vmcount = self.kvm.host_get_vms(
                        clusterhost)
            except:
                vmcount = "UNKNOWN"

            # Table
            t.add_row([clusterhost.name.split('.')[0],
                       pm,
                       clusterhost.resourcestate,
                       clusterhost.state,
                       vmcount,
                       bondstatus])

        # Remove progress indication
        sys.stdout.write("\033[F")
        # Print table
        print t.get_string(sortby="Hostname")

    # Print cluster table
    def printCluster(self, clusterID, hypervisor="XenServer"):
        clusterData = self.listClusters({'clusterid': clusterID})
        t = PrettyTable(["Cluster name",
                         "Allocation state",
                         "Managed state",
                         "XenServer HA",
                         "Patch level",
                         "Pod name",
                         "Zone name"])
        t.align["Cluster name"] = "l"
        t.max_width["Patch level"] = 32

        try:
            xenserver_ha_state = "N/A"
            clusterHostsData = self.getAllHostsFromCluster(clusterID)
            if hypervisor == "XenServer":
                xenserver_ha_state = self.xenserver.pool_ha_check(clusterHostsData[0])
        except:
            clusterHostsData = False
            xenserver_ha_state = "N/A"

        try:
            if not clusterHostsData:
                clusterHostsData = self.getAllHostsFromCluster(clusterID)
            if hypervisor == "XenServer":
                patch_level = self.xenserver.get_patch_level(clusterHostsData[0])
            elif hypervisor == "KVM":
                patch_level = self.kvm.get_patch_level(clusterHostsData)

        except:
            patch_level = "N/A"

        for cluster in clusterData:
            t.add_row([cluster.name,
                       cluster.allocationstate,
                       cluster.managedstate,
                       xenserver_ha_state,
                       patch_level,
                       cluster.podname,
                       cluster.zonename])
        # Print table
        print t

    # Check vm's still running on this host
    def getVirtualMachinesRunningOnHost(self, hostID):
        all_vmdata = ()
        vms = self.deprecatedListVirtualMachines({'hostid': hostID, 'listAll': 'true'}) or []
        pvms = tuple([self.deprecatedListVirtualMachines({'hostid': hostID, 'listAll': 'true', 'isProjectVm': 'true'})] or [])
        routers = tuple([self.getRouterData({'hostid': hostID, 'listAll': 'true'})] or [])
        prouters = tuple([self.getRouterData({'hostid': hostID, 'listAll': 'true', 'isProjectVm': 'true'})] or [])
        svms = tuple([[svm for svm in self.getSystemVmData({'hostid': hostID}) or []]])

        # Sort VM list on memory
        if len(vms) > 0:
            vms.sort(key=operator.attrgetter('memory'), reverse=True)

        all_vmdata += tuple([vms])
        all_vmdata += pvms
        all_vmdata += routers
        all_vmdata += prouters
        all_vmdata += svms

        if self.DEBUG:
            print all_vmdata

        return all_vmdata

    # Find suitable host
    def findBestMigrationHost(
            self,
            clusterID,
            currentHostname,
            requestedMemory):

        # All hosts from cluster
        clusterHosts = self.getHostsFromCluster(clusterID)
        bestAvailableMemory = 0
        migrationHost = False

        if clusterHosts != 1 and clusterHosts is not None:
            [currentHost] = [h for h in self.getAllHostsFromCluster(clusterID) if h.name == currentHostname] or [""]

            for h in clusterHosts:
                # Skip the current hostname
                if h.name == currentHostname:
                    continue
                # Only hosts have enough resources
                if h.suitableformigration == False:
                    continue
                # Handle dedicated hosts
                # if 'dedicated' in currentHost:
                #    if currentHost.dedicated != h.dedicated:
                #        continue
                #    if currentHost.dedicated == True and currentHost.domainid != h.domainid:
                #        continue
                # And are not in Maintenance, Error or Disabled
                if h.resourcestate == "Disabled" or h.resourcestate == "Maintenance" or h.resourcestate == "Error":
                    continue
                if h.state == "Alert" or h.state == "Disconnected":
                    continue
                # Check memory availability
                # Available memory in Bytes
                memoryavailable = h.memorytotal - h.memoryallocated
                if self.DEBUG == 1:
                    print "Note: host " + h.name + " has free mem: " + str(
                        memoryavailable / 1024 / 1024) + "MB and we need " + \
                          str(requestedMemory / 1024 / 1024) + " MB"

                # vm.memory is in Mega Bytes
                if requestedMemory is not None:
                    if memoryavailable < requestedMemory:
                        if self.DEBUG == 1:
                            print "Warning: Skipping " + h.name + " as it has not enough memory."
                        continue

                # Find host with most memory free
                if bestAvailableMemory == 0:
                    if self.DEBUG == 1:
                        print "Note: Found possible migration host '" + h.name + "' with free memory: " + str(
                            memoryavailable)
                    migrationHost = h
                    bestAvailableMemory = memoryavailable
                elif memoryavailable > bestAvailableMemory:
                    if self.DEBUG == 1:
                        print "Note: Found better migration host '" + h.name + "' with free memory: " + str(
                            memoryavailable)
                    migrationHost = h
                    bestAvailableMemory = memoryavailable
                elif self.DEBUG == 1:
                    print "Note: Found migration host '" + h.name + "' with free memory: " + str(
                        memoryavailable) + " but there are already better (or equal) candidates so skipping this one"

        return migrationHost

    # get Host by name
    def getHostByName(self, name=None):
        # Host data
        return self.exoCsApi.listHosts(name=name)

    # Migrate all vm's and empty hypervisor
    def emptyHypervisor(self, hostID):
        # Host data
        host_data = self.exoCsApi.listHosts(id=hostID)
        current_host = host_data['host'][0]
        hostname = current_host['name']
        to_slack = True
        if self.DEBUG == 1:
            print host_data
            print current_host
            print hostname
            to_slack = False

        # Check vm's still running on this host
        all_vmdata = self.getVirtualMachinesRunningOnHost(hostID)

        if all_vmdata is None:
            print "Warning: No vm's to be moved found on '" + hostname + "'.."
        else:
            if self.DRYRUN == 1:
                print "Note: Testing if we would be able to migrate the vm's on hypervisor '" + hostname + "':"
            else:
                print "Note: Migrating the vm's on hypervisor '" + hostname + "':"

            for vmdata in all_vmdata:
                if vmdata is None:
                    continue
                for vm in vmdata:

                    sys.stdout.write(vm.name + ", ")
                    sys.stdout.flush()
                    vmresult = 1
                    if self.DRYRUN == 0:
                        if vm.maintenancepolicy == "ShutdownAndStart":
                            message = "Note: Shutting down vm %s on host %s, has ShutdownAndStart policy" % (vm.name, vm.hostname)
                            self.print_message(message=message, message_type="Note", to_slack=to_slack)

                            vmresult = self.exoCsApi.stopVirtualMachine(id=vm.id)
                            if self.__waitforjob(vmresult['jobid']):
                                self.vmshutpolicy[vm.id] = {"name": vm.name, "hostid": vm.hostid, "hostname": vm.hostname}
                            else:
                                vmresult = 1
                            continue

                        # Affinity
                        try:
                            host_affinity = self.exoCsApi.listAffinityGroups(virtualmachineid=vm.id)
                            affinity_groups = host_affinity['affinitygroup']
                        except:
                            affinity_groups = []

                        vm_on_dedicated_hv = False
                        dedicated_affinity_id = None
                        for affinity_group in affinity_groups:
                            # Is VM on dedicated hypervisor
                            if affinity_group['type'] == 'ExplicitDedication':
                                vm_on_dedicated_hv = True
                                dedicated_affinity_id = affinity_group['id']

                        available_hosts = self.exoCsApi.findHostsForMigration(virtualmachineid=vm.id)
                        available_hosts = sorted(available_hosts['host'], key=lambda k: k['memoryallocated'], reverse=False)

                        for available_host in available_hosts:
                            # Skip hosts that require storage migration
                            if available_host['requiresStorageMotion']:
                                if self.DEBUG == 1:
                                    print "Note: Skipping %s because need storage_migration is %s" \
                                          % (available_host['name'], available_host['requiresStorageMotion'])
                                continue

                            # Only from the same cluster
                            if available_host['clusterid'] != current_host['clusterid']:
                                if self.DEBUG == 1:
                                    print "Note: Skipping %s because part of another cluster" % available_host['name']
                                continue

                            # Only suitable hosts
                            if not available_host['suitableformigration']:
                                if self.DEBUG == 1:
                                    print "Note: Skipping %s because is not suitable" % available_host['name']
                                continue

                            # Check dedication
                            if vm_on_dedicated_hv:
                                # VM is on dedicated HV, check to see if it is the right group
                                if 'affinitygroupid' in available_host and available_host['affinitygroupid'] != dedicated_affinity_id:
                                    print "Note: Skipping %s because host does not match dedication group of VM" % available_host['name']
                                    continue
                            else:
                                # VM is not dedicated: skip dedicated HVs
                                if 'affinitygroupid' in available_host:
                                    print "Note: Skipping %s because hv is dedicated and VM is not" % available_host['name']
                                    continue

                            print "Note: Selecting %s" % available_host['name']
                            break

                        if not available_host:
                            print "\nError: No hosts with enough capacity to migrate vm's to. Please migrate manually to another cluster."
                            sys.exit(1)

                        # Use findHostsForMigration to select host to migrate to
                        try:
                            message = "Live migrating vm %s to host %s" % (vm.name, available_host['name'])
                            self.print_message(message=message, message_type="Note", to_slack=to_slack)

                            # Systemvm or instance
                            if bool(re.search('[rvs]-([\d])*-', vm.name)):
                                vmresult = self.migrateSystemVm({
                                    'vmid': vm.id,
                                    'hostid': available_host['id']
                                })
                                instance = vm.name
                            else:
                                if vm.isoid is not None:
                                    self.detach_iso(vm.id)
                                vmresult = self.migrateVirtualMachine(
                                    vm.id,
                                    available_host['id'])
                                instance = vm.instancename
                        except:
                            vmresult = 1

                        try:
                            # Parse result
                            if vmresult is None or vmresult == 1:
                                sys.stdout.write(
                                    vm.name +
                                    " (failed) " +
                                    instance +
                                    "..), ")
                                sys.stdout.flush()
                                if current_host.hypervisor == "XenServer":
                                    xapiresult, xapioutput = self.ssh.migrateVirtualMachineViaXapi(
                                        {'hostname': hostname, 'desthostname': available_host['name'], 'vmname': instance})
                                    if self.DEBUG == 1:
                                        print "Debug: Output: " + str(xapioutput) + " code " + str(xapiresult)
                                if current_host.hypervisor == "KVM":
                                    pass

                            elif self.DEBUG == 1:
                                print "Debug: VM " + vm.name + " migrated OK"
                        except:
                            vmresult = 1
                        if vmresult == 1:
                            sys.stdout.write(
                                vm.name +
                                " (failed), ")
                            sys.stdout.flush()
                            return False
        return True

    # Start machines with ShutdownAndStart policy
    def startVmsWithShutPolicy(self):
        to_slack = True
        if self.DEBUG == 1:
            to_slack = False

        for i, vm in self.vmshutpolicy.iteritems():
            if 'status' in self.vmshutpolicy[i]:
                continue
            message = "Starting vm %s with ShutdownAndStart policy on host %s" % (vm['name'], vm['hostname'])
            self.print_message(message=message, message_type="Note", to_slack=to_slack)
            if self.DEBUG == 0:
                vmresult = self.exoCsApi.startVirtualMachine(id=i, hostid=vm['hostid'])
                if self.__waitforjob(vmresult['jobid']):
                    self.vmshutpolicy[i].update({'status': 'done'})
                else:
                    self.vmshutpolicy[i].update({'status': 'error'})
                    message = "Error starting vm %s with ShutdownAndStart policy on host %s" % (vm['name'], vm['hostname'])
                    self.print_message(message=message, message_type="Error", to_slack=to_slack)

    # list oscategories
    def listOsCategories(self, args):
        args = self.remove_empty_values(args)

        apicall = listOsCategories.listOsCategoriesCmd()
        apicall.id = (str(args['id'])) if 'id' in args and len(args['id']) > 0 else None
        apicall.name = (str(args['name'])) if 'name' in args and len(args['name']) > 0 else None
        apicall.keyword = (str(args['keyword'])) if 'keyword' in args and len(args['keyword']) > 0 else None

        # Call CloudStack API
        return self._callAPI(apicall)

    # list ostypes
    def listOsTypes(self, args):
        args = self.remove_empty_values(args)

        apicall = listOsTypes.listOsTypesCmd()
        apicall.id = (str(args['id'])) if 'id' in args and len(args['id']) > 0 else None
        apicall.oscategoryid = (str(args['oscategoryid'])) if 'oscategoryid' in args and len(
            args['oscategoryid']) > 0 else None
        apicall.keyword = (str(args['keyword'])) if 'keyword' in args and len(args['keyword']) > 0 else None

        # Call CloudStack API
        return self._callAPI(apicall)

    def extract_volume(self, uuid, zoneid):
        # Export volume
        apicall = extractVolume.extractVolumeCmd()
        apicall.id = uuid
        apicall.mode = "HTTP_DOWNLOAD"
        apicall.zoneid = zoneid

        result = self._callAPI(apicall)

        if not result:
            print "Error: Could not export vdi %s" % uuid
            return False
        if self.DEBUG == 1:
            print "DEBUG: received this result:" + str(result)
        return result.volume.url

    def detach_iso(self, virtualmachineid):

        apicall = detachIso.detachIsoCmd()
        apicall.virtualmachineid = virtualmachineid

        # Call CloudStack API
        result = self._callAPI(apicall)

        if result is not None:
            return False
        else:
            return True

    def get_needed_memory(self, system_vm):
        if system_vm.memory is None:
            # Try to get the memory of systemvms from their offering
            if bool(re.search('[rvs]-([\d])*-', system_vm.name)) and system_vm.serviceofferingid is not None:
                serviceOfferingData = self.listServiceOfferings(
                    {'serviceofferingid': system_vm.serviceofferingid, 'issystem': 'true'})
                system_vm.memory = serviceOfferingData[0].memory
                if self.DEBUG == 1:
                    print "DEBUG: Set memory to the value in the service offering: %s" % str(
                        serviceOfferingData[0].memory)
                    # Else, fail back to a 1GB default
            else:
                system_vm.memory = 1024
        return int(system_vm.memory) * 1024 * 1024

    def __waitforjob(self, jobid=None, retries=10):
        char = 0
        outputchar = '|/-\\'
        while True:
            if retries < 0:
                break
            # TODO: @FIXME Temporary fix for Cosmic serialization problem
            try:
                # jobstatus: 0 = Job still running
                #            1 = Job done successfully
                #            2 = Job has an error
                jobstatus = self.exoCsApi.queryAsyncJobResult(jobid=jobid) if not self.DRYRUN else {'jobstatus': 1}
            except CloudStackException as e:
                if 'multiple JSON fields named jobstatus' not in str(e):
                    raise e
                retries -= 1
            except requests.exceptions.ConnectionError as e:
                if 'Connection aborted' not in str(e):
                    raise e
                print e
                retries -= 1

            
            # jobstatus 1 = Job done successfully
            if int(jobstatus['jobstatus']) == 1:
                sys.stdout.write('\r')
                return True
            # jobstatus 2 = Job has an error
            if int(jobstatus['jobstatus']) == 2:
                sys.stdout.write('\r')
                break
            
            sys.stdout.write('\r' + outputchar[char % 4])
            sys.stdout.flush()
            char +=1
            time.sleep(1)
        return False
