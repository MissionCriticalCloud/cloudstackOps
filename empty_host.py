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
        argparser.add_argument("-t", "--to", dest="dst",
                               help="To hypervisor, specify '@auto' to migrate to host with most available memory or "
                                    "'@balance' to balance them across multiple hypervisors", required=True,
                               action="store")
        argparser.add_argument("--config", dest="conf", help="Alternate config file", action="store",
                               default="~/.cloudmonkey/config")
        argparser.add_argument("--exec", dest="DRYRUN", help="Execute migration", default=True, action="store_false")
        argparser.add_argument("--noslack", dest="slack", help="Don't send slack messages", default=True,
                               action="store_false")
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
    slack = True
    balanced = False

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
        if len(self.hosts) == 0:
            self.getHosts()

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

    @property
    def dsthost(self):
        return self.__dsthost

    @dsthost.setter
    def dsthost(self, value):
        self.__dsthost = value

    def getHosts(self):
        hosts = self.__cs.listHosts()
        for host in hosts['host']:
            if 'clustertype' not in host:
                continue
            self.hosts[host['name']] = host

    @property
    def getFreeHost(self):
        self.getHosts()
        hv = {'free': 0}
        for host in self.hosts:
            if host.startswith(self.srchost):
                continue
            if self.hosts[host]['state'].lower() == 'down' and self.hosts[host][
                'resourcestate'].lower() == 'disabled':
                continue

            free_mem = self.hosts[host]['memorytotal'] - self.hosts[host]['memoryallocated']
            hv_id = self.hosts[host]['id']
            if free_mem > hv['free']:
                hv = {'host': host, 'id': hv_id, 'free': free_mem}
        return hv

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
        projectrvms = self.__cs.listRouters(hostid=hostid, listall=True, projectid=-1)
        if len(projectrvms) > 0 and 'router' in self.routervms:
            self.routervms['router'] += projectrvms['router']
        else:
            self.routervms = projectrvms

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
        if not self.slack:
            return
        self.clops.cluster = self.cluster
        self.clops.zone_name = self.zone
        self.clops.instance_name = instance_name
        self.clops.vm_name = vm_name
        self.clops.slack_custom_value = kwargs['srchost'] if 'srchost' in kwargs and kwargs['srchost'] else "N/A"
        color = kwargs['color'] if 'color' in kwargs and kwargs['color'] else "good"
        self.clops.send_slack_message(message=message, color=color)

    def migrate(self, srchost=None, DRYRUN=True, **kwargs):
        """ Migrate VMS to another HV """

        signal.signal(signal.SIGINT, self.__sighandler)

        src_hostid = self.hosts[self.srchost]['id']
        # dst_hostid = self.hosts[dsthost]['id']
        self.zone = kwargs['zone'] if 'zone' in kwargs and kwargs['zone'] else "N/A"
        self.cluster = self.hosts[self.srchost]['clustername']
        self.clops.slack_custom_value = self.srchost

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

                print("    UUID: %s  Name: %-20s [%-24s] %8iMb  State: " % (host['id'], host['instancename'],
                                                                            host['name'][:24], host['memory']),
                      end='')
                sys.stdout.flush()

                if self.balanced:
                    freehost = self.getFreeHost
                    dst_hostid = freehost['id']
                    self.dsthost = freehost['host']
                else:
                    dst_hostid = self.hosts[self.dsthost]['id']

                if not DRYRUN:
                    message = "Live migrating vm %s to host %s" % (host['name'], self.dsthost)
                    print(message + ' - ', end='')
                    self.send_slack(message=message, instance_name=host['instancename'], vm_name=host['name'])
                    jobid = self.__cs.migrateVirtualMachine(hostid=dst_hostid, virtualmachineid=host['id'])
                    if self.__waitforjob(jobid['jobid']):
                        print("Migration successful")
                    else:
                        self.send_slack(message="Error migrating vm %s to host %s" % (host['name'], self.dsthost),
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

                    if self.balanced:
                        freehost = self.getFreeHost
                        dst_hostid = freehost['id']
                        self.dsthost = freehost['host']
                    else:
                        dst_hostid = self.hosts[self.dsthost]['id']

                    if not DRYRUN:
                        message = "Live migrating SVM %s to host %s" % (host['name'], self.dsthost)
                        print(message + " - ", end='')
                        self.send_slack(message=message, instance_name=host['id'], vm_name=host['name'])
                        jobid = self.__cs.migrateSystemVm(hostid=dst_hostid, virtualmachineid=host['id'])
                        if self.__waitforjob(jobid['jobid']):
                            print("Migration successful")
                        else:
                            self.send_slack(message="Error migrating SVM %s to host %s" % (host['name'], self.dsthost),
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

                    if self.balanced:
                        freehost = self.getFreeHost
                        dst_hostid = freehost['id']
                        self.dsthost = freehost['host']
                    else:
                        dst_hostid = self.hosts[self.dsthost]['id']

                    if not DRYRUN:
                        message = "Live migrating RVM %s to host %s" % (host['name'], self.dsthost)
                        print(message + " - ", end='')
                        self.send_slack(message=message, instance_name=host['id'], vm_name=host['name'])
                        jobid = self.__cs.migrateSystemVm(hostid=dst_hostid, virtualmachineid=host['id'])
                        if self.__waitforjob(jobid['jobid']):
                            print("Migration successful")
                        else:
                            self.send_slack(message="Error migrating RVM %s to host %s" % (host['name'], self.dsthost),
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
    slack = args['slack']

    config = ConfigParser.ConfigParser()
    config.read(os.path.expanduser(configfile))
    cosmic = Cosmic(endpoint=config.get(zone, 'url'), apikey=config.get(zone, 'apikey'),
                    secretkey=config.get(zone, 'secretkey'), verify=False)

    cosmic.disablehost = disablehost
    cosmic.slack = slack

    srchost = [x for x in cosmic.hosts if x.startswith(srchv)]
    if len(srchost) == 0:
        print("Hypervisor %s not found, exiting..." % srchv)
        return 1
    cosmic.srchost = srchost[0]

    if dsthv.lower() == '@auto':
        print("Auto selected host %s as destination" % cosmic.getFreeHost['host'])
        cosmic.dsthost = cosmic.getFreeHost['host']
    elif dsthv.lower() == '@balance':
        print("Balancing VM's over multiple hosts")
        cosmic.balanced = True
    else:
        dsthost = [x for x in cosmic.hosts if x.startswith(dsthv)][0]
        if not dsthost:
            print("Hypervisor %s not found, exiting..." % dsthv)
            return 1

        if cosmic.hosts[dsthost]['state'].lower() == 'down':
            print("%s is down, unable to migrate machines to this host" % dsthost)
            return 1

        if cosmic.hosts[dsthost]['resourcestate'].lower() == 'disabled':
            print("%s is disabled, unable to to migrate VM's to this host" % dsthost)
            return 1
        cosmic.dsthost = dsthost

    return (cosmic.migrate(srchost=srchost, domain=domain, excdomain=excdomain,
                           DRYRUN=args['DRYRUN'], zone=zone))


if __name__ == "__main__":
    warnings.filterwarnings("ignore")
    sys.exit(main())
