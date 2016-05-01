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

# CloudStackOps Base Class
# Remi Bergsma - rbergsma@schubergphilis.com

from cloudstackopsbase import CloudStackOpsBase
import os.path
import signal
import re

class LswCloudStackOpsBase(CloudStackOpsBase):
    DEBUG = 0

    # CONSTs
    SAFETY_BEST = 0
    SAFETY_DOWNTIME = 1
    SAFETY_GOOD = 2
    SAFETY_UNKNOWN = -1
    SAFETY_NA = -99

    ACTION_R_LOG_CLEANUP = 'log-cleanup'
    ACTION_R_RST_PASSWD_SRV = 'rst-passwd-srv'
    ACTION_N_RESTART = 'restart'
    ACTION_I_THROTTLE = 'throttle'
    ACTION_UNKNOWN = 'unknown'
    ACTION_MANUAL = 'manual'
    ACTION_ESCALATE = 'escalate'

    STATE_ALLOCATED = 'Allocated'

    # Init function
    def __init__(self, debug=0, dryrun=0, force=0):
        self.DEBUG = debug
        self.DRYRUN = dryrun
        self.FORCE = force
        self.configProfileNameFullPath = ''
        self.organization = ''
        self.smtpserver = 'localhost'
        self.mail_from = ''
        self.errors_to = ''
        self.configfile = os.getcwd() + '/config'

        self.printWelcome()

        signal.signal(signal.SIGINT, self.catch_ctrl_C)

    def debug(self, level, args):
        if self.DEBUG>=level:
            print args

    def normalizePackageVersion(self, versionstr):
        # At LSW, RPM version differs in the bugfix version number between - (Ubuntu) and . (CentOS)
        # Example: 4.2.1-leaseweb34-1 (Ubuntu) vs. 4.2.1-leaseweb34.1 (CentOS)
        # So, let's normallize version numbers:
        #import re
        #regex = re.compile(r'(\d+)[-\.](\d+)$', re.IGNORECASE)
        #return regex.sub('\1-\2', versionstr)
        return versionstr.replace('.', '-')

    @staticmethod
    def translateSafetyLevel(level):
        if level==LswCloudStackOpsBase.SAFETY_BEST:
            return 'Best'
        if level==LswCloudStackOpsBase.SAFETY_DOWNTIME:
            return 'Downtime'
        if level==LswCloudStackOpsBase.SAFETY_GOOD:
            return 'Good'
        if level==LswCloudStackOpsBase.SAFETY_NA:
            return 'N/A'
        return 'Unknown'

    @staticmethod
    def translateSafetyLevelString(level):
        if level=='Best':
            return LswCloudStackOpsBase.SAFETY_BEST
        if level=='Downtime':
            return LswCloudStackOpsBase.SAFETY_DOWNTIME
        if level=='Good':
            return LswCloudStackOpsBase.SAFETY_GOOD
        if level=='N/A':
            return LswCloudStackOpsBase.SAFETY_NA
        if level=='Unknown':
            return LswCloudStackOpsBase.SAFETY_UNKNOWN
        return None

    @staticmethod
    def csVersionCompare(aver,bver):
       vstr = r'(\d+)[\.-](\d+)[\.-](\d+)-leaseweb(\d+)[\.-]*(\d+)*'
       a = re.match(vstr, aver)
       b = re.match(vstr, bver)

       if int(a.group(1)) > int(b.group(1)):
          return 1
       elif int(a.group(1)) < int(b.group(1)):
          return -1
       elif int(a.group(2)) > int(b.group(2)):
          return 2
       elif int(a.group(2)) < int(b.group(2)):
          return -2
       elif int(a.group(3)) > int(b.group(3)):
          return 3
       elif int(a.group(3)) < int(b.group(3)):
          return -3
       elif int(a.group(4)) > int(b.group(4)):
          return 4
       elif int(a.group(4)) < int(b.group(4)):
          return -4
       elif ((a.group(5)==None) and (b.group(5)!=None)) or ((a.group(5)!=None) and (b.group(5)!=None) and (int(a.group(5)) < int(b.group(5)))):
          return -5
       elif ((a.group(5)!=None) and (b.group(5)==None)) or ((a.group(5)!=None) and (b.group(5)!=None) and (int(a.group(5)) > int(b.group(5)))):
          return 5
       return 0
