#!/usr/bin/python
import sys
import getopt
from cloudstackops import cloudstackops
import os.path

# Function to handle our arguments


def handleArguments(argv):
    global DEBUG
    DEBUG = 0
    global DRYRUN
    DRYRUN = 1
    global vpcname
    vpcname = ''
    global vpcuuid
    vpcuuid = ''
    global networkuuid
    networkuuid = ''
    global toCluster
    toCluster = ''
    global configProfileName
    configProfileName = ''
    global isProjectVm
    isProjectVm = 0

    # Usage message
    help = "Usage: ./" + os.path.basename(__file__) + ' [options] ' + \
        '\n  --config-profile -c <profilename>\tSpecify the CloudMonkey profile name to get the credentials from (or specify in ./config file)' + \
        '\n  --vpc-name -v <name>\t\t\tWork with this VPC (r-12345-VM)' + \
        '\n  --uuid -u <name>\t\t\tWork with this VPC (UUID)' + \
        '\n  --network-uuid -t <name>\t\tWork with this VPC tier (UUID)' + \
        '\n  --is-projectrouter\t\t\tThe specified router belongs to a project' + \
        '\n  --debug\t\t\t\tEnable debug mode' + \
        '\n  --exec\t\t\t\tExecute for real'

    try:
        opts, args = getopt.getopt(
            argv, "hc:v:u:pt:", [
                "config-profile=", "vpc-name=", "uuid=", "network-uuid=", "debug", "exec", "is-projectrouter"])
    except getopt.GetoptError:
        print help
        sys.exit(2)
    for opt, arg in opts:
        if opt == '-h':
            print help
            sys.exit()
        elif opt in ("-c", "--config-profile"):
            configProfileName = arg
        elif opt in ("-v", "--vpc-name"):
            vpcname = arg
        elif opt in ("-u", "--uuid"):
            vpcuuid = arg
        elif opt in ("-t", "--network-uuid"):
            networkuuid = arg
        elif opt in ("--debug"):
            DEBUG = 1
        elif opt in ("--exec"):
            DRYRUN = 0
        elif opt in ("--is-projectrouter"):
            isProjectVm = 1

    # Default to cloudmonkey default config file
    if len(configProfileName) == 0:
        configProfileName = "config"

    # We need at least these vars
    if len(vpcname) == 0 and len(vpcuuid) == 0 and len(networkuuid) == 0:
        print vpcuuid
        print vpcname
        print networkuuid
        print help
        sys.exit()

# Parse arguments
if __name__ == "__main__":
    handleArguments(sys.argv[1:])

# Init CloudStack class
c = cloudstackops.CloudStackOps(DEBUG, DRYRUN)
c.instance_name = "N/A"

if DEBUG == 1:
    print "Warning: Debug mode is enabled!"

if DRYRUN == 1:
    print "Warning: dry-run mode is enabled, not running any commands!"

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

if isProjectVm == 1:
    projectParam = "true"
else:
    projectParam = "false"

# check routerID
VPCUUID = c.checkCloudStackName({'csname': vpcname,
                                  'csApiCall': 'listVPCs',
                                  'listAll': 'true',
                                  'isProjectVm': projectParam})

if len(networkuuid) > 0:
    print "Note: Getting VPC id from network uuid %s" % networkuuid
    network = c.listNetworks(networkuuid)[0]
    VPCUUID = network.vpcid

if not VPCUUID:
    VPCUUID = vpcuuid

if VPCUUID == 1 or VPCUUID == "":
    print "Error: VPC cannot be found!"
    exit(1)

vpc = c.listVPCs(VPCUUID)[0]

print "Note: Found VPC " + vpcname

# Pretty Slack messages
c.instance_name = vpcname
c.slack_custom_title = "Domain"
c.slack_custom_value = vpc.domain
c.zone_name = vpc.zonename

print "Note: Let's reboot the VPC.."

if DRYRUN == 1:
    print "Note: Would have rebooted vpc " + vpc.name + " (" + VPCUUID + ")"
else:
    # If the network is a VPC
    c.task = "Restart VPC with clean up"
    message = "Restarting VPC " + vpc.name + " with clean up (" + VPCUUID + ")"
    c.print_message(message=message, message_type="Note", to_slack=True)
    result = c.restartVPC(VPCUUID)
    if result == 1:
        print "Restarting failed, will try again!"
        result = c.restartVPC(VPCUUID)
        if result == 1:
            message = "Restarting VPC " + vpc.name + "(" + VPCUUID + ") with clean up failed.\nError: investigate manually!"
            c.print_message(message=message, message_type="Error", to_slack=True)
            sys.exit(1)
        else:
            message = "Successfully restarted VPC " + vpc.name + " (" + VPCUUID + ")"
            c.print_message(message=message, message_type="Note", to_slack=True)
    else:
        message = "Successfully restarted VPC " + vpc.name + " (" + VPCUUID + ")"
        c.print_message(message=message, message_type="Note", to_slack=True)


print "Note: We're done!"
