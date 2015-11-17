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

# Import the class we depend on
from cloudstackopsbase import *
# Import our dependencies
import smtplib
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from prettytable import PrettyTable
import subprocess
from subprocess import Popen, PIPE
import pprint
import re

# Marvin
try:
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


class CloudStackOps(CloudStackOpsBase):

    # Init function
    def __init__(self, debug=0, dryrun=0, force=0):
        self.apikey = ''
        self.secretkey = ''
        self.api = ''
        self.cloudstack = ''
        self.DEBUG = debug
        self.DRYRUN = dryrun
        self.FORCE = force
        self.configProfileNameFullPath = ''
        self.apiurl = ''
        self.apiserver = ''
        self.apiprotocol = ''
        self.apiport = ''
        self.csApiClass = ''
        self.conn = ''
        self.organization = ''
        self.smtpserver = 'localhost'
        self.mail_from = ''
        self.errors_to = ''
        self.configfile = os.getcwd() + '/config'
        self.pp = pprint.PrettyPrinter(depth=6)
        self.ssh = None
        self.xenserver = None

        self.printWelcome()
        self.checkScreenAlike()

        signal.signal(signal.SIGINT, self.catch_ctrl_C)

    def printWelcome(self):
        print colored.green("Welcome to CloudStackOps")

    # Check if we run in a screen session
    def checkScreen(self):
        try:
            if len(os.environ['STY']) > 0:
                if self.DEBUG == 1:
                    print "DEBUG: We're running in screen."
                return True
        except:
            return False

    # Check if we run in a tmux session
    def checkTmux(self):
        try:
            if len(os.environ['TMUX']) > 0:
                if self.DEBUG == 1:
                    print "DEBUG: We're running in tmux."
                return True
        except:
            return False

    def checkScreenAlike(self):
        if self.checkScreen():
            return True
        if self.checkTmux():
            return True
        print colored.red("Warning: You are NOT running inside screen/tmux. Please start a screen/tmux session to keep commands running in case you get disconnected!")

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
            print colored.yellow("Warning: Cannot read or parse CloudMonkey profile '" + self.configProfileName + "'. Trying local config file..")
            tryLocal = True

        if self.configProfileName == "config":
           tryLocal = True

        if tryLocal:
            # Read config for CloudStack API credentials
            try:
                print "Note: Trying to use API credentials from local config profile '" + self.configProfileName + "'"
                self.parseConfig(self.configfile)
            except:
                print colored.yellow("Warning: Cannot read or parse profile '" + self.configProfileName + "' from local config file either")

        # Do we have all required settings?
        if self.apiurl == '' or self.apikey == '' or self.secretkey == '':
            print colored.red("Error: Could not load CloudStack API settings from local config file, nor from CloudMonkey config file. Halting.")
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
                self.apiurl = config.get(profile, 'url')
            elif self.configProfileName != 'config':
                # cloudmonkey > 5.2.x config with the commandline profile
                # option
                if self.DEBUG == 1:
                    print "Cloudmonkey > 5.2.x configfile found, profile option given"
                self.apikey = config.get(self.configProfileName, 'apikey')
                self.secretkey = config.get(
                    self.configProfileName,
                    'secretkey')
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
            print "Debug: apiserver=" + self.apiserver + " apiKey=" + self.apikey + " securityKey=" + self.secretkey + " port=" + str(self.apiport) + " scheme=" + self.apiprotocol
        try:
            self.cloudstack = cloudConnection(
                self.apiserver,
                apiKey=self.apikey,
                securityKey=self.secretkey,
                asyncTimeout=14400,
                logging=log,
                port=int(
                    self.apiport),
                scheme=self.apiprotocol)
            if self.DEBUG == 1:
                print self.cloudstack
        except:
            print "Error connecting to CloudStack. Are you using the right Marvin version? See README file. Halting."
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
        else:
            print "No API command to call"
            sys.exit(1)

        if isProjectVm == 'true':
            apicall.projectid = "-1"

        if csname.startswith('i-'):
            apicall.keyword = str(csname)

        else:
            apicall.name = str(csname)

        if listAll == 'true':
            apicall.listAll = "true"

        try:
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
                        if self.DEBUG == 1:
                            print "Found in loop " + str(d.name)

                        csnameID = d.id
                        break
                    elif self.DEBUG == 1:
                        print "Not found in loop " + str(d.name)

                if len(csnameID) < 1:
                    print "Warning: '%s' could not be located in CloudStack database using '%s' or is not unique -- Exit." % (csname, csApiCall)
                    sys.exit(1)
            else:
                print "Error: '%s' could not be located in CloudStack database using '%s' -- exit!" % (csname, csApiCall)
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
        # Select a random storage pool that belongs to this cluster

        return data
    
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
        apicall.listAll = "true"

        # Call CloudStack API
        return self._callAPI(apicall)

    # Generic listVirtualMachines function
    def listVirtualmachines(self, args):
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
                            print "Note: The redundant peer of router " + routername + " is " + routerPeerData.name + " running on " + routerPeerData.hostname + " (" + peerHostData[0].clustername + " / " + peerHostData[0].podname + ")."
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

    # Reboot virtualrouter
    def rebootRouter(self, vmid):
        apicall = rebootRouter.rebootRouterCmd()
        apicall.id = str(vmid)

        # Call CloudStack API
        return self._callAPI(apicall)

    # Send an e-mail
    def sendMail(self, mailfrom, mailto, subject, htmlcontent):
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = mailfrom
        msg['To'] = mailto

        # HTML part
        htmlpart = MIMEText(htmlcontent, 'html')
        msg.attach(htmlpart)

        s = smtplib.SMTP(self.smtpserver)
        s.sendmail(msg['From'], msg['To'], msg.as_string())
        s.quit()

    # Stop virtualvirtualmachine
    def stopVirtualMachine(self, vmid):
        apicall = stopVirtualMachine.stopVirtualMachineCmd()
        apicall.id = str(vmid)
        apicall.forced = "false"

        # Call CloudStack API
        return self._callAPI(apicall)

    # Start virtualvirtualmachine
    def startVirtualMachine(self, vmid, hostid=""):
        apicall = startVirtualMachine.startVirtualMachineCmd()
        apicall.id = str(vmid)
        apicall.forced = "false"
        if len(hostid) > 0:
            apicall.hostid = hostid

        # Call CloudStack API
        return self._callAPI(apicall)

    # migrateVirtualMachine
    def migrateVirtualMachine(self, vmid, hostid):
        apicall = migrateVirtualMachine.migrateVirtualMachineCmd()
        apicall.virtualmachineid = str(vmid)
        apicall.hostid = str(hostid)

        # Call CloudStack API
        return self._callAPI(apicall)

    # migrateSystemVm
    def migrateSystemVm(self, vmid, hostid):
        apicall = migrateSystemVm.migrateSystemVmCmd()
        apicall.virtualmachineid = str(vmid)
        apicall.hostid = str(hostid)

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
        apicall.domainid = (
            str(args['domainid'])) if 'domainid' in args else None
        apicall.networkids = (
            str(args['networkids'])) if 'networkids' in args else None
        apicall.templateid = (
            str(args['templateid'])) if 'templateid' in args else None
        apicall.serviceofferingid = (
            str(args['serviceofferingid'])) if 'serviceofferingid' in args else None
        apicall.zoneid = (str(args['zoneid'])) if 'zoneid' in args else None
        apicall.account = (str(args['account'])) if 'account' in args else None
        apicall.name = (str(args['name'])) if 'name' in args else None

        # Call CloudStack API
        return self._callAPI(apicall)

    # Generate a random name
    def generateRandomName(self, prefix):
        name = prefix + (''.join(random.choice(string.digits)
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

    # list snapshotPolicies
    def listSnapshotPolicies(self, volid):
        apicall = listSnapshotPolicies.listSnapshotPoliciesCmd()
        apicall.volumeid = volid

        # Call CloudStack API
        return self._callAPI(apicall)

    # create snapshot policy
    def createSnapshotPolicy(self, args):
        args = self.remove_empty_values(args)

        apicall = createSnapshotPolicy.createSnapshotPolicyCmd()
        apicall.volumeid = (str(args['volid'])) if 'volid' in args else None
        apicall.intervaltype = (
            str(args['intervaltype'])) if 'intervaltype' in args else None
        apicall.maxsnaps = (
            str(args['maxsnaps'])) if 'maxsnaps' in args else None
        apicall.schedule = (
            str(args['schedule'])) if 'schedule' in args else None
        apicall.timezone = (
            str(args['timezone'])) if 'timezone' in args else 'Europe/Amsterdam'

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

    # Translate id to name, because of CLOUDSTACK-6542
    def translateIntervalType(self, intervaltype):
        return {
            0: 'HOURLY',
            1: 'DAILY',
            2: 'WEEKLY',
            3: 'MONTHLY'
        }.get(intervaltype, 0)

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
        targetStorageID = self.getStoragePool(toClusterID)
        targetStoragePoolData = self.getStoragePoolData(targetStorageID)
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
  
        volumes = self.listVolumes(storagepoolid,False)
              
        orphans = []   
        
        if volumes is not None:
            # sort results by domain
            volumes.sort(key=lambda vol: vol.domain, reverse=True)
        
            # select volumes with no vmname attached
            for volume in volumes:
                if volume.vmname is None:
                    orphans.append(volume)
            
        #return selected detached volumes
        return orphans      
        
    # Check zone
    def checkZone(self, routerClusterID, toClusterID):
        routerClusterData = self.listClusters({'clusterid': routerClusterID})
        if routerClusterData is None:
            print "Error: could not find cluster with id " + routerClusterID
            return 1

        targetStorageID = self.getStoragePool(toClusterID)
        storagepooltags = self.getStoragePoolTags(toClusterID)
        targetStoragePoolData = self.getStoragePoolData(targetStorageID)

        if self.DEBUG == 1:
            print "Debug: You selected a storage pool with tags '" + storagepooltags + "'"

        # Check zone of current and destination clusters
        if targetStoragePoolData[0].zonename != routerClusterData[0].zonename:
            print "Error: cannot do this: Router is currently in zone " + routerClusterData[0].zonename + " and you selected a cluster in zone " + targetStoragePoolData[0].zonename + "."
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
        for host in hostData:
            if host.name == hostname:
                foundHostData = host

        if self.DRYRUN == 1:
            print "\nNote: Would have prepared host '" + hostname + "' for maintenance"
            return False
        else:
            # Get vm count
            try:
                retcode, vmcount = self.ssh.getXapiVmCount(
                    foundHostData.ipaddress)
            except:
                vmcount = "?"
            print "\nNote: Preparing host '" + hostname + "' for maintenance, " + vmcount + " VMs to migrate.."

            # Maintenance
            maintenanceResult = self.prepareHostForMaintenance(hostID)

        # Did it work?
        if maintenanceResult is None or maintenanceResult == 1:
            print "Error: Got an empty result from prepareForMaintenance call"
            print "Error: Please investigate manually. Halting."
            sys.exit(1)

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
                    retcode, vmcount = self.ssh.getXapiVmCount(
                        foundHostData.ipaddress)
                except:
                    pass

            if foundHostData.resourcestate == "PrepareForMaintenance":
                print "Note: Resource state currently is '" + foundHostData.resourcestate + "'. Number of VMs still to be migrated: " + vmcount + "    "
                sys.stdout.write("\033[F")

                # Wait before checking again
                time.sleep(6)

            elif foundHostData.resourcestate == "Enabled":
                print "Note: Resource state currently is '" + foundHostData.resourcestate + "', maintenance must have been cancelled, returning"
                break
            else:
                # lots of spaces to clear previous line
                print "Note: Resource state currently is '" + foundHostData.resourcestate + "', that's looking good! Returning..                "
                break

            # Return if the same for 100x6 sec
            if vmcount == vmcount_previous:
                vmcount_same_counter = vmcount_same_counter + 1
            else:
                vmcount_same_counter = 0
            if vmcount_same_counter >= 100:
                print "Warning: The number of vm's still to migrate is still " + vmcount + " for 600s, returning and trying manual migration instead"
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
            print "Note: Host '" + hostname + "' maintenance was cancelled outside of script.. will try to migrate vm's manually"
            return False
        else:
            print "Note: Host '" + hostname + "' did not yet enter Maintenance. Cancel maintenance and trying to migrate vm's manually"
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
    def printHypervisors(self, clusterid, poolmaster=False, checkBonds=False):

        print "Note: Checking.."
        clusterHostsData = self.getAllHostsFromCluster(clusterid)

        # Start table
        t = PrettyTable(["Hostname",
                         "Poolmaster",
                         "Resource state",
                         "State",
                         "# VMs",
                         "Bond Status"])

        for clusterhost in clusterHostsData:

            # Some progress indication
            sys.stdout.write(clusterhost.name + ", ")
            sys.stdout.flush()

            if not poolmaster:
                if self.DEBUG == 1:
                    print "Debug: Looking for poolmaster"
                poolmaster = self.xenserver.get_poolmaster(clusterhost)

            # Poolmaster
            if clusterhost.name == poolmaster.strip():
                pm = "<------"
            else:
                pm = ""

            # Check bonds
            if checkBonds is True:
                try:
                    bondscripts = self.xenserver.put_scripts(
                        clusterhost)
                    bondstatus = self.xenserver.get_bond_status(
                        clusterhost)
                except:
                    bondstatus = "UNKNOWN"
            else:
                bondstatus = "UNTESTED"

            try:
                vmcount = self.xenserver.host_get_vms(
                    clusterhost)
            except:
                vmcount = "UNKNOWN"

            # Table
            t.add_row([clusterhost.name,
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
    def printCluster(self, clusterID):
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
            clusterHostsData = self.getAllHostsFromCluster(clusterID)
            xenserver_ha_state = self.xenserver.pool_ha_check(
                clusterHostsData[0])
        except:
            xenserver_ha_state = "N/A"

        try:
            if not clusterHostsData:
                clusterHostsData = self.getAllHostsFromCluster(clusterID)
            xenserver_patch_level = self.xenserver.get_patch_level(
                clusterHostsData[0])
        except:
            xenserver_patch_level = "N/A"


        for cluster in clusterData:
            t.add_row([cluster.name,
                       cluster.allocationstate,
                       cluster.managedstate,
                       xenserver_ha_state,
                       xenserver_patch_level,
                       cluster.podname,
                       cluster.zonename])
        # Print table
        print t

    # Check vm's still running on this host
    def getVirtualMachinesRunningOnHost(self, hostID):

        all_vmdata = []
        all_vmdata.append(
            self.listVirtualmachines({'hostid': hostID, 'listAll': 'true'}))
        all_vmdata.append(self.listVirtualmachines(
            {'hostid': hostID, 'listAll': 'true', 'isProjectVm': 'true'}))
        all_vmdata.append(
            self.getRouterData({'hostid': hostID, 'listAll': 'true'}))
        all_vmdata.append(self.getSystemVmData({'hostid': hostID}))

        if self.DEBUG == 1:
            if all_vmdata is not None:
                for vmdata in all_vmdata:
                    if vmdata is not None:
                        for v in vmdata:
                            if v is not None:
                                print v.name
            print "Debug: Combined vmdata"
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
            for h in clusterHosts:
                # Skip the current hostname
                if h.name == currentHostname:
                    continue
                # Only hosts have enough resources
                if h.suitableformigration == False:
                    continue
                # And are not in Maintenance, Error or Disabled
                if h.resourcestate == "Disabled" or h.resourcestate == "Maintenance" or h.resourcestate == "Error":
                    continue
                # Check memory availability
                # Available memory in Bytes
                memoryavailable = h.memorytotal - h.memoryallocated
                if self.DEBUG == 1:
                    print "Note: host " + h.name + " has free mem: " + str(memoryavailable)
                # Don't try if host has less than 10GB memory left or if vm does not fit at all
                # vm.memory is in Mega Bytes
                if requestedMemory is not None:
                    if memoryavailable < (
                            10 *
                            1024 *
                            1024 *
                            1024) or memoryavailable < (
                            requestedMemory *
                            1024 *
                            1024):
                        if self.DEBUG == 1:
                            print "Warning: Skipping " + h.name + " as it has not enough memory."
                        continue
                else:
                    if memoryavailable < (10 * 1024 * 1024 * 1024):
                        if self.DEBUG == 1:
                            print "Warning: Skipping " + h.name + " as it has not enough memory."
                        continue

                # Find host with most memory free
                if bestAvailableMemory == 0:
                    if self.DEBUG == 1:
                        print "Note: Found possible migration host '" + h.name + "' with free memory: " + str(memoryavailable)
                    migrationHost = h
                    bestAvailableMemory = memoryavailable
                elif memoryavailable > bestAvailableMemory:
                    if self.DEBUG == 1:
                        print "Note: Found better migration host '" + h.name + "' with free memory: " + str(memoryavailable)
                    migrationHost = h
                    bestAvailableMemory = memoryavailable
                elif self.DEBUG == 1:
                    print "Note: Found migration host '" + h.name + "' with free memory: " + str(memoryavailable) + " but there are already better (or equal) candidates so skipping this one"

        return migrationHost

    # Migrate all vm's and empty hypervisor
    def emptyHypervisor(self, hostID):
        # Host data
        hostData = self.getHostData({'hostid': hostID})
        foundHostData = hostData[0]
        hostname = foundHostData.name
        if self.DEBUG == 1:
            print "xxxxxxxxx"
            print hostData
            print "xxxxxxxxx"
            print foundHostData
            print "xxxxxxxxx"
            print hostname
            print "xxxxxxxxx"

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
                        migrationHost = self.findBestMigrationHost(
                            foundHostData.clusterid,
                            hostname,
                            vm.memory)
                        if not migrationHost:
                            print "\nError: No hosts with enough capacity to migrate vm's to. Please migrate manually to another cluster."
                            sys.exit(1)
                        try:
                            if self.DEBUG == 1:
                                print "Debug: Migrating vm to host '" + migrationHost.name + "'.."

                            # Systemvm or instance
                            if bool(re.search('[rvs]-([\d])*-VM', vm.name)):
                                vmresult = self.migrateSystemVm(
                                    vm.id,
                                    migrationHost.id)
                                instance = vm.name
                            else:
                                vmresult = self.migrateVirtualMachine(
                                    vm.id,
                                    migrationHost.id)
                                instance = vm.instancename
                        except:
                            vmresult = 1

                        try:
                            # Parse result
                            if vmresult is None or vmresult == 1:
                                sys.stdout.write(
                                    vm.name +
                                    " (failed using CloudStack, trying XAPI " +
                                    instance +
                                    "..), ")
                                sys.stdout.flush()
                                xapiresult, xapioutput = self.ssh.migrateVirtualMachineViaXapi(
                                    {'hostname': hostname, 'desthostname': migrationHost.name, 'vmname': instance})
                                if self.DEBUG == 1:
                                    print "Debug: Output: " + str(xapioutput) + " code " + str(xapiresult)
                            elif self.DEBUG == 1:
                                print "Debug: VM " + vm.name + " migrated OK"
                        except:
                            vmresult = 1
                        if vmresult == 1:
                            sys.stdout.write(
                                vm.name +
                                " (failed using CloudStack and XAPI!), ")
                            sys.stdout.flush()
                            return False
        return True
