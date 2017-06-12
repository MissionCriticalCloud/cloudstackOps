#!/usr/bin/env python

from __future__ import print_function
from argparse import ArgumentParser
import ConfigParser
import operator
import warnings
import time
import sys
import os

try:
    import cs
except ImportError:
    print("Missing CS module: pip install cs")
    sys.exit(1)


class Args:
    """ Argument class """
    def __init__(self):
        argparser = ArgumentParser()
        argparser.add_argument("-z", "--zone", dest="zone", help="Cosmic/CloudStack zone", required=True,
                               action="store")
        argparser.add_argument("-d", "--disablehost", dest="disablehost", help="Disable 'from' host", default=False,
                               action="store_true")
        argparser.add_argument("--exec", dest="DRYRUN", help="Execute migration", default=True, action="store_false")
        argparser.add_argument("-f", "--from", dest="src", help="From hypervisor", required=True, action="store")
        argparser.add_argument("-t", "--to", dest="dst", help="To hypervisor", required=True, action="store")
        argparser.add_argument("-c", "--config", dest="conf", help="Alternate config file", action="store",
                               default="~/.cloudmonkey/config")
        self.__args = argparser.parse_args()

    def __getitem__(self, item):
        """ Get argument as dictionary """
        return self.__args.__dict__[item]


class Cosmic(object):
    """ Cosmic class """
    __hvtypes = ('KVM', 'XenServer')
    disablehost = False

    def __init__(self, endpoint=None, apikey=None, secretkey=None, verify=True):
        self.__cs = cs.CloudStack(endpoint=endpoint, key=apikey, secret=secretkey, verify=verify)
        self.hosts = {}
        self.routervms = {}
        self.systemvms = {}
        self.virtualmachines = {}
        self.__srchost = None
        self.__dsthost = None

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
        if value in self.hosts:
            src_hostid = self.hosts[value]['id']
            self.__getVirtualMachines(hostid=src_hostid)
            if 'virtualmachine' in self.virtualmachines:
                self.virtualmachines['virtualmachine'] = sorted(self.virtualmachines['virtualmachine'],
                                                                key=operator.itemgetter('memory'), reverse=True)
            self.__getSystemVms(hostid=src_hostid)
            self.__getRouters(hostid=src_hostid)

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

    def __getVirtualMachines(self, hostid=None):
        self.virtualmachines = self.__cs.listVirtualMachines(hostid=hostid, listall=True)

    def __getSystemVms(self, hostid=None):
        self.systemvms = self.__cs.listSystemVms(hostid=hostid, listall=True)

    def __getRouters(self, hostid=None):
        self.routervms = self.__cs.listRouters(hostid=hostid, listall=True)

    def __waitforjob(self, jobid=None, retries=60):
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

    def migrate(self, srchost=None, dsthost=None, DRYRUN=True):
        """ Migrate VMS to another HV """

        src_hostid = self.hosts[srchost]['id']
        dst_hostid = self.hosts[dsthost]['id']
        if self.disablehost and ('virtualmachine' in self.virtualmachines or 'systemvm' in self.systemvms or
                                         'router' in self.routervms):
            # Only disable host if we have machines to migrate
            self.__cs.updateHost(id=src_hostid, allocationstate='Disable')

        if 'virtualmachine' in self.virtualmachines:
            print("Starting migration of user VM:")
            for host in self.virtualmachines['virtualmachine']:
                print("    UUID: %s  Name: %-16s [%-24s] %8iMb  State: " % (host['id'], host['instancename'],
                                                                            host['name'][:24], host['memory']),
                                                                            end='')
                sys.stdout.flush()
                if not DRYRUN:
                    jobid = self.__cs.migrateVirtualMachine(hostid=dst_hostid, virtualmachineid=host['id'])
                    if self.__waitforjob(jobid['jobid']):
                        print("Migration successful")
                    else:
                        print("Migration unsuccessful!")
                else:
                    print('DRYRUN')

        if 'systemvm' in self.systemvms:
            print("Starting migration of system VM:")
            for host in self.systemvms['systemvm']:
                print("    UUID: %s  Name: %-16s State: " % (host['id'], host['name']), end='')
                sys.stdout.flush()
                if not DRYRUN:
                    jobid = self.__cs.migrateSystemVm(hostid=dst_hostid, virtualmachineid=host['id'])
                    if self.__waitforjob(jobid['jobid']):
                        print("Migration successful")
                    else:
                        print("Migration unsuccessful!")
                else:
                    print('DRYRUN')

        if 'router' in self.routervms:
            print("Starting migration of router VM:")
            for host in self.routervms['router']:
                print("    UUID: %s  Name: %-16s State: " % (host['id'], host['name']), end='')
                sys.stdout.flush()
                if not DRYRUN:
                    jobid = self.__cs.migrateSystemVm(hostid=dst_hostid, virtualmachineid=host['id'])
                    if self.__waitforjob(jobid['jobid']):
                        print("Migration successful")
                    else:
                        print("Migration unsuccessful!")
                else:
                    print('DRYRUN')

def main():
    """ MAIN Loop starts here """
    args = Args()
    configfile = args['conf']
    disablehost = args['disablehost']
    zone = args['zone']
    srchv = args['src']
    dsthv = args['dst']

    config = ConfigParser.ConfigParser()
    config.read(os.path.expanduser(configfile))
    cosmic = Cosmic(endpoint=config.get(zone,'url'), apikey=config.get(zone, 'apikey'),
                    secretkey=config.get(zone,'secretkey'), verify=False)

    cosmic.srchost = srchv
    cosmic.dsthost = dsthv
    cosmic.disablehost = disablehost
    if srchv not in cosmic:
        print("Hypervisor %s not found, exiting..." % srchv)
        sys.exit(1)
    if dsthv not in cosmic:
        print("Hypervisor %s not found, exiting..." % dsthv)
        sys.exit(1)
    cosmic.migrate(srchost=srchv, dsthost=dsthv, DRYRUN=args['DRYRUN'])

if __name__ == "__main__":
    warnings.filterwarnings("ignore")
    main()