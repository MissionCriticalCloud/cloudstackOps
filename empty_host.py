#!/usr/bin/env python

from __future__ import print_function

import operator
import os
import signal
import sys
import time
import warnings
from argparse import ArgumentParser

from cloudstackops import cloudstackops

try:
    import configparser as ConfigParser
except ImportError:
    import ConfigParser

try:
    import cs
except ImportError:
    print("Missing CS module: pip install cs")
    sys.exit(1)


class Args:
    """ Argument class """

    def __init__(self):
        argparser = ArgumentParser()
        arggroup = argparser.add_mutually_exclusive_group()
        argparser.add_argument("-c", "--config-profile", dest="zone", help="Cosmic/CloudStack zone", required=True,
                               action="store")
        argparser.add_argument("-d", "--disablehost", dest="disablehost", help="Disable 'from' host", default=False,
                               action="store_true")
        argparser.add_argument("-f", "--from", dest="src", help="From hypervisor", required=True, action="store")
        argparser.add_argument("-t", "--to", dest="dst", help="To hypervisor", required=True, action="store")
        argparser.add_argument("--config", dest="conf", help="Alternate config file", action="store",
                               default="~/.cloudmonkey/config")
        argparser.add_argument("--exec", dest="DRYRUN", help="Execute migration", default=True, action="store_false")
        arggroup.add_argument("--domain", dest="domain", help="Only migrate VM's from domain", action="store")
        arggroup.add_argument("--exceptdomain", dest="excdomain", help="Migrate all VM's except domain", action="store")
        self.__args = argparser.parse_args()

    def __getitem__(self, item):
        """ Get argument as dictionary """
        return self.__args.__dict__[item]


class Cosmic(object):
    """ Cosmic class """
    __hvtypes = ('KVM', 'XenServer')
    __quit = False
    disablehost = False

    def __init__(self, endpoint=None, apikey=None, secretkey=None, verify=True):
        self.__cs = cs.CloudStack(endpoint=endpoint, key=apikey, secret=secretkey, verify=verify)
        self.hosts = {}
        self.routervms = {}
        self.systemvms = {}
        self.virtualmachines = {}
        self.domains = {}
        self.__srchost = None
        self.__dsthost = None
        self.clops = cloudstackops.CloudStackOps()
        self.clops.task = "Empty Hypervisor"
        self.clops.slack_custom_title = "Hypervisor"
        self.clops.slack_custom_value = ""
        self.clops.instance_name = "N/A"
        self.zone = "N/A"
        self.cluster = "N/A"

    def __contains__(self, item):
        return item in self.hosts

    def __getitem__(self, item):
        if item in self.hosts:
            return self.hosts[item]
        return None

    @property
    def srchost(self):
        return self.__srchost

    @srchost.setter
    def srchost(self, value):
        self.__srchost = value
        if len(self.hosts) == 0:
            self.getHosts()

    @property
    def dsthost(self):
        return self.__dsthost

    @dsthost.setter
    def dsthost(self, value):
        self.__dsthost = value
        if len(self.hosts) == 0:
            self.getHosts()

    def getHosts(self):
        hosts = self.__cs.listHosts()
        for host in hosts['host']:
            self.hosts[host['name']] = host

    def __getDomains(self):
        self.domains = self.__cs.listDomains(listall=True)

    def __getVirtualMachines(self, hostid=None):
        self.virtualmachines = self.__cs.listVirtualMachines(hostid=hostid, listall=True)
        projectvms = self.__cs.listVirtualMachines(hostid=hostid, listall=True, projectid=-1)
        if len(projectvms) > 0:
            self.virtualmachines['virtualmachine'] += projectvms['virtualmachine']
        if 'virtualmachine' in self.virtualmachines:
            self.virtualmachines['virtualmachine'] = sorted(self.virtualmachines['virtualmachine'],
                                                            key=operator.itemgetter('memory'), reverse=True)

    def __getSystemVms(self, hostid=None):
        self.systemvms = self.__cs.listSystemVms(hostid=hostid, listall=True)

    def __getRouters(self, hostid=None):
        self.routervms = self.__cs.listRouters(hostid=hostid, listall=True)

    def __sighandler(self, signal, frame):
        self.__quit = True

    def __waitforjob(self, jobid=None, retries=120):
        while True:
            if retries < 0:
                break
            # jobstatus 0 = Job still running
            jobstatus = self.__cs.queryAsyncJobResult(jobid=jobid)
            # jobstatus 1 = Job done successfully
            if int(jobstatus['jobstatus']) == 1:
                return True
            # jobstatus 2 = Job has an error
            if int(jobstatus['jobstatus']) == 2:
                break
            retries -= 1
            time.sleep(1)
        return False

    def send_slack(self, message=None, instance_name=None, vm_name=None, **kwargs):
        self.clops.cluster = self.cluster
        self.clops.zone_name = self.zone
        self.clops.instance_name = instance_name
        self.clops.vm_name = vm_name
        self.clops.slack_custom_value = kwargs['srchost'] if 'srchost' in kwargs and kwargs['srchost'] else "N/A"
        color = kwargs['color'] if 'color' in kwargs and kwargs['color'] else "good"
        self.clops.send_slack_message(message=message, color=color)

    def migrate(self, srchost=None, dsthost=None, DRYRUN=True, **kwargs):
        """ Migrate VMS to another HV """

        signal.signal(signal.SIGINT, self.__sighandler)

        src_hostid = self.hosts[srchost]['id']
        dst_hostid = self.hosts[dsthost]['id']
        self.zone = kwargs['zone'] if 'zone' in kwargs and kwargs['zone'] else "N/A"
        self.cluster = self.hosts[srchost]['clustername']
        self.clops.slack_custom_value = srchost

        self.__getDomains()
        self.__getSystemVms(hostid=src_hostid)
        self.__getRouters(hostid=src_hostid)
        self.__getVirtualMachines(hostid=src_hostid)

        if self.disablehost and ('virtualmachine' in self.virtualmachines or 'systemvm' in self.systemvms or
                                 'router' in self.routervms) and not DRYRUN:
            # Only disable host if we have machines to migrate
            self.__cs.updateHost(id=src_hostid, allocationstate='Disable')

        if 'virtualmachine' in self.virtualmachines:
            print("Starting migration of user VM:")
            for host in self.virtualmachines['virtualmachine']:
                if 'domain' in kwargs and kwargs['domain']:
                    if host['domain'] != kwargs['domain']:
                        continue
                if 'excdomain' in kwargs and kwargs['excdomain']:
                    if host['domain'] == kwargs['excdomain']:
                        continue

                print("    UUID: %s  Name: %-16s [%-24s] %8iMb  State: " % (host['id'], host['instancename'],
                                                                            host['name'][:24], host['memory']),
                      end='')
                sys.stdout.flush()

                if not DRYRUN:
                    self.send_slack(message="Live migrating vm %s to host %s" % (host['name'], dsthost),
                                    instance_name=host['instancename'], vm_name=host['name'])
                    jobid = self.__cs.migrateVirtualMachine(hostid=dst_hostid, virtualmachineid=host['id'])
                    if self.__waitforjob(jobid['jobid']):
                        print("Migration successful")
                    else:
                        self.send_slack(message="Error migrating vm %s to host %s" % (host['name'], dsthost),
                                        instance_name=host['instancename'], vm_name=host['name'], color="danger")
                        print("Migration unsuccessful!")
                else:
                    print('DRYRUN')
                if self.__quit:
                    return 0

        # System VM's are not bound to domain, so skip if domain is given
        if 'domain' in kwargs and kwargs['domain'] is None:
            if 'systemvm' in self.systemvms:
                print("Starting migration of system VM:")
                for host in self.systemvms['systemvm']:
                    print("    UUID: %s  Name: %-16s State: " % (host['id'], host['name']), end='')
                    sys.stdout.flush()
                    if not DRYRUN:
                        self.send_slack(message="Live migrating SVM %s to host %s" % (host['name'], dsthost),
                                        instance_name=host['id'], vm_name=host['name'])
                        jobid = self.__cs.migrateSystemVm(hostid=dst_hostid, virtualmachineid=host['id'])
                        if self.__waitforjob(jobid['jobid']):
                            print("Migration successful")
                        else:
                            self.send_slack(message="Error migrating SVM %s to host %s" % (host['name'], dsthost),
                                            instance_name=host['id'], vm_name=host['name'], color="danger")
                            print("Migration unsuccessful!")
                    else:
                        print('DRYRUN')
                    if self.__quit:
                        return 0

            if 'router' in self.routervms:
                print("Starting migration of router VM:")
                for host in self.routervms['router']:
                    print("    UUID: %s  Name: %-16s State: " % (host['id'], host['name']), end='')
                    sys.stdout.flush()
                    if not DRYRUN:
                        self.send_slack(message="Live migrating RVM %s to host %s" % (host['name'], dsthost),
                                        instance_name=host['id'], vm_name=host['name'])
                        jobid = self.__cs.migrateSystemVm(hostid=dst_hostid, virtualmachineid=host['id'])
                        if self.__waitforjob(jobid['jobid']):
                            print("Migration successful")
                        else:
                            self.send_slack(message="Error migrating RVM %s to host %s" % (host['name'], dsthost),
                                            instance_name=host['id'], vm_name=host['name'], color="danger")
                            print("Migration unsuccessful!")
                    else:
                        print('DRYRUN')
                    if self.__quit:
                        return 0


def main():
    """ MAIN Loop starts here """
    args = Args()
    configfile = args['conf']
    disablehost = args['disablehost']
    zone = args['zone']
    srchv = args['src']
    dsthv = args['dst']
    domain = args['domain']
    excdomain = args['excdomain']

    config = ConfigParser.ConfigParser()
    config.read(os.path.expanduser(configfile))
    cosmic = Cosmic(endpoint=config.get(zone, 'url'), apikey=config.get(zone, 'apikey'),
                    secretkey=config.get(zone, 'secretkey'), verify=False)

    cosmic.srchost = srchv
    cosmic.dsthost = dsthv
    cosmic.disablehost = disablehost

    srchost = [x for x in cosmic.hosts if x.startswith(srchv)][0]
    dsthost = [x for x in cosmic.hosts if x.startswith(dsthv)][0]
    if not srchost:
        print("Hypervisor %s not found, exiting..." % srchv)
        return 1
    if not dsthost:
        print("Hypervisor %s not found, exiting..." % dsthv)
        return 1
    cosmic.migrate(srchost=srchost, dsthost=dsthost, domain=domain, excdomain=excdomain, DRYRUN=args['DRYRUN'],
                   zone=zone)


if __name__ == "__main__":
    warnings.filterwarnings("ignore")
    sys.exit(main())
