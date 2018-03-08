#!/usr/bin/python

import getopt
import getpass
import os.path
import sys
import time
from datetime import datetime

from cloudstackops import cloudstackops
from cloudstackops import cloudstacksql
from cloudstackops import kvm
from cloudstackops import vmware


# Function to handle our arguments
def handleArguments(argv):
    global DEBUG
    DEBUG = 0
    global DRYRUN
    DRYRUN = 1
    global instancename
    instancename = ''
    global toCluster
    toCluster = ''
    global configProfileName
    configProfileName = ''
    global force
    force = 0
    global threads
    threads = 5
    global mysqlHost
    mysqlHost = ''
    global mysqlPasswd
    mysqlPasswd = ''
    global newBaseTemplate
    newBaseTemplate = ''
    global helperScriptsPath
    helperScriptsPath = None
    global startVM
    startVM = True
    global esxiHost
    esxiHost = ''
    global vmxPath
    vmxPath = ''

    # Usage message
    help = "Usage: ./" + os.path.basename(__file__) + ' [options] ' + \
           '\n  --config-profile -c <profilename>\tSpecify the CloudMonkey profile name to get the credentials from ' \
           '(or specify in ./config file)' + \
           '\n  --instance-name -i <instancename>\tMigrate VM with this instance name' + \
           '\n  --esxi-host -e <ipv4 address>\t\tMigrate VM from this esxi host' + \
           '\n  --vmx-path -v <vmxpath>\t\tThe vmx path including /vmfs/volumes/' + \
           '\n  --to-cluster -t <clustername>\t\tMigrate VM to this cluster' + \
           '\n  --new-base-template -b <template>\tKVM template to link the VM to. Won\'t do much, mostly needed for ' \
           'properties like tags. We need to record it in the DB as it cannot be NULL and the XenServer one obviously ' \
           'doesn\'t work either.' + \
           '\n  --mysqlserver -s <mysql hostname>\tSpecify MySQL server config section name' + \
           '\n  --mysqlpassword <passwd>\t\tSpecify password to cloud ' + \
           'MySQL user' + \
           '\n  --start-vm\t\t\t\tStart VM when migration is complete; default=true' + \
           '\n  --helper-scripts-path\t\t\tFolder with scripts to be copied to hypervisor in migrate working folder' + \
           '\n  --debug\t\t\t\tEnable debug mode' + \
           '\n  --exec\t\t\t\tExecute for real' + \
           '\n\n\n\n' + \
           '\nMake sure the esxi host is in the known hosts file of every kvm host in the cluster ' \
           'for h in 01 02 03 04 05 06 07 08 09 10 11 12 13 14; do ssh mccppod051-hv${h} -A "sudo -E ssh -o StrictHostKeyChecking=no root@172.16.98.219 ls"; done"; done'

    try:
        opts, args = getopt.getopt(
            argv,
            "hc:i:t:p:s:b:v:e:",
            [
                "config-profile=", "instance-name=", "to-cluster=", "esxi-host=", "vmx-path", "mysqlserver=", "mysqlpassword=",
                "new-base-template=", "start-vm", "helper-scripts-path=", "debug", "exec", "force"]
        )
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
        elif opt in ("-i", "--instance-name"):
            instancename = arg
        elif opt in ("-t", "--to-cluster"):
            toCluster = arg
        elif opt in ("-e", "--esxi-host"):
            esxiHost = arg
        elif opt in ("-v", "--vmx-path"):
            vmxPath = arg
        elif opt in ("-b", "--new-base-template"):
            newBaseTemplate = arg
        elif opt in ("-s", "--mysqlserver"):
            mysqlHost = arg
        elif opt in ("-p", "--mysqlpassword"):
            mysqlPasswd = arg
        elif opt in ("--debug"):
            DEBUG = 1
        elif opt in ("--exec"):
            DRYRUN = 0
        elif opt in ("--force"):
            force = 1
        elif opt in ("--start-vm"):
            startVM = True
        elif opt in ("--helper-scripts-path"):
            helperScriptsPath = arg

    # Default to cloudmonkey default config file
    if len(configProfileName) == 0:
        configProfileName = "config"

    # We need at least these vars
    if len(instancename) == 0 or len(toCluster) == 0 or len(mysqlHost) == 0 or len(vmxPath) == 0 or len(esxiHost) == 0:
        print help
        sys.exit()

    if not os.path.isdir(helperScriptsPath):
        print "Error: Directory %s as specified with --helper-scripts-path does not exist!" % helperScriptsPath
        sys.exit(1)


# Parse arguments
if __name__ == "__main__":
    handleArguments(sys.argv[1:])

# Start time
print "Note: Starting @ %s" % time.strftime("%Y-%m-%d %H:%M")
start_time = datetime.now()

if DEBUG == 1:
    print "Warning: Debug mode is enabled!"

if DRYRUN == 1:
    print "Warning: dry-run mode is enabled, not running any commands!"

def exit_script(message):
    print "Fatal Error: %s" % message
    sys.exit(1)


def start_vm(hypervisor_name, start=startVM):
    global message, result
    if DRYRUN == 1:
        message = "Would have started vm %s with id %s" % (vm.name, vm.id)
        c.print_message(message=message, message_type="Note", to_slack=False)
    elif start:
        message = "Starting virtualmachine %s with id %s" % (vm.name, vm.id)
        c.print_message(message=message, message_type="Note", to_slack=True)
        result = c.startVirtualMachine(vm.id)
        if result == 1:
            message = "Start vm failed -- exiting."
            c.print_message(message=message, message_type="Error", to_slack=True)
            message = "investegate manually!"
            c.print_message(message=message, message_type="Note", to_slack=False)
            sys.exit(1)

        if result.virtualmachine.state == "Running":
            message = "%s is started successfully on %s" % (result.virtualmachine.name, hypervisor_name)
            c.print_message(message=message, message_type="Note", to_slack=True)
        else:
            warningMsg = "Warning: " + result.virtualmachine.name + " is in state " + \
                         result.virtualmachine.state + \
                         " instead of Running. Please investigate (could just take some time)."
            print warningMsg


# Init CloudStackOps class
c = cloudstackops.CloudStackOps(DEBUG, DRYRUN)
c.task = "VMware -> KVM migration"
c.slack_custom_title = "Migration details"

# Init VMware class
v = vmware.vmware('root', threads)
v.DEBUG = DEBUG
v.DRYRUN = DRYRUN
c.vmware = v

# Init KVM class
k = kvm.Kvm(ssh_user=getpass.getuser(), threads=threads, helper_scripts_path=helperScriptsPath)
k.DEBUG = DEBUG
k.DRYRUN = DRYRUN
c.kvm = k

# Init SQL class
s = cloudstacksql.CloudStackSQL(DEBUG, DRYRUN)

# Connect MySQL
result = s.connectMySQL(mysqlHost, mysqlPasswd)
if result > 0:
    message = "MySQL connection failed"
    c.print_message(message=message, message_type="Error", to_slack=True)
    sys.exit(1)
elif DEBUG == 1:
    print "DEBUG: MySQL connection successful"
    print s.conn

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
    print "Debug: Checking CloudStack IDs of provided input.."

toClusterID = c.checkCloudStackName({'csname': toCluster, 'csApiCall': 'listClusters'})

message = "Cluster ID found for %s is %s" % (toCluster, toClusterID)
c.print_message(message=message, message_type="Note", to_slack=False)
c.cluster = toCluster

if toClusterID == 1 or toClusterID is None:
    message = "Cluster with name '%s' can not be found! Halting!" % toCluster
    c.print_message(message=message, message_type="Error", to_slack=False)
    sys.exit(1)

c.slack_custom_title = "Migration details for vmx %s" % vmxPath

if len(newBaseTemplate) == 0:
    print "Please specify a template one using the --new-base-template " \
          "flag and try again. Using 'Linux - Unknown template converted from XenServer'"
    newBaseTemplate = 'Linux - Unknown template converted from XenServer'

templateID = c.checkCloudStackName(
    {'csname': newBaseTemplate, 'csApiCall': 'listTemplates'})

message = "Template ID found for %s is %s" % (newBaseTemplate, templateID)
c.print_message(message=message, message_type="Note", to_slack=False)

if templateID == 1 or templateID is None:
    message = "Template with name '%s' can not be found! Halting!" % newBaseTemplate
    c.print_message(message=message, message_type="Error", to_slack=False)
    sys.exit(1)

# Get cluster hosts
kvm_host = c.getRandomHostFromCluster(toClusterID)

# Select storage pool
targetStorage = c.getStoragePoolWithMostFreeSpace(toClusterID)
targetStorageID = targetStorage.id
targetStoragePoolData = c.getStoragePoolData(targetStorageID)[0]
storagepooltags = targetStoragePoolData.tags
storagepoolname = targetStoragePoolData.name

# Get hosts that belong to toCluster
toClusterHostsData = c.getHostsFromCluster(toClusterID)
if DEBUG == 1:
    print "Note: You selected a storage pool with tags '" + str(storagepooltags) + "'"

# SSH to random host on tocluster -> create migration folder
if k.prepare_kvm(kvm_host, targetStoragePoolData.id) is False:
    sys.exit(1)
if k.put_scripts(kvm_host) is False:
    sys.exit(1)

# SSH to random host on tocluster -> do virt-v2v
k.vmware_virt_v2v(kvm_host, esxiHost, vmxPath)

# Gather disk info from kvm host

# Create virtualmachine
# Add data disks
# Start virtual machine
# Stop virtual machine
# Get disks locations from database
# Move disks on kvm host to correct location
# Start vm

exit(0)