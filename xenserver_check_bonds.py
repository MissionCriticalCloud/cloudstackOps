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


import sys
import socket
import time
import re
import os
import XenAPI

# check xen bond status

DEBUG = False


def log(s):
    if DEBUG:
        print(s)


def get_bonds(session, host):
    bonds = {}
    slaves = {}

    for (b, brec) in list(session.xenapi.PIF.get_all_records().items()):
        # only local interfaces
        if brec['host'] != host:
            continue
        # save masters and slaves
        if brec['bond_master_of']:
            bonds[b] = brec
        if brec['bond_slave_of']:
            slaves[b] = brec

    for (m, mrec) in list(session.xenapi.PIF_metrics.get_all_records().items()):
        for srec in list(slaves.values()):
            if srec['metrics'] != m:
                continue
            srec['carrier'] = mrec['carrier']

    for (n, nrec) in list(session.xenapi.network.get_all_records().items()):
        for brec in list(bonds.values()):
            if brec['network'] != n:
                continue
            brec['name_label'] = nrec['name_label']

    return bonds, slaves


def get_bond_status(session, host):
    status = {}
    for (b, brec) in list(session.xenapi.Bond.get_all_records().items()):
        status[b] = brec

    return status


def main():

    # First acquire a valid session by logging in:
    session = XenAPI.xapi_local()
    session.xenapi.login_with_password("root", "")

    hostname = socket.gethostname()
    host = (session.xenapi.host.get_by_name_label(hostname))[0]

    # warning when host not found...
    if not host:
        print("failed to detect XAPI host for '%s'" % hostname)
        sys.exit(1)

    bonds, slaves = get_bonds(session, host)
    bond_status = get_bond_status(session, host)

    clist = []
    olist = []

    # iterate over the bonds
    for b in bonds:
        net = bonds[b]['name_label']
        ref = bonds[b]['bond_master_of'][0]
        status = bond_status[ref]

        # On XenServer 6.0 we manually build links_up by checking carrier
        if 'links_up' not in status:

            status['links_up'] = 0

            for slave in status['slaves']:
                if slaves[slave]['carrier']:
                    status['links_up'] += 1

        if len(status['slaves']) != int(status['links_up']):
            clist.append("%s has only %s links up (%s slaves)"
                         % (net, status['links_up'], len(status['slaves'])))
        else:
            olist.append("%s %s links up" % (net, status['links_up']))

    if len(clist):
        print("CRITICAL:", ", ".join(clist))
        return 2
    elif len(olist):
        print("OK:", ", ".join(olist))
        return 0
    else:
        print("OK: no bonds found")
        return 0

if __name__ == "__main__":
    sys.exit(main())
