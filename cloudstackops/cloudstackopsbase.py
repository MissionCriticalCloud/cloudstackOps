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

import os
import sys
import signal
import getopt
import ConfigParser
from os.path import expanduser
from random import choice
import logging
import urllib2
import time
import string
import random
import commands
from urlparse import urlparse
from prettytable import PrettyTable
import slackweb
import pprint
# Colored terminals
try:
    from clint.textui import colored
except:
    print "Error: Please install clint library to support color in the terminal:"
    print "       pip install clint"
    sys.exit(1)


class CloudStackOpsBase(object):

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
        self.pp = pprint.PrettyPrinter(depth=6)
        self.slack = None
        self.slack_custom_title = "Undefined"
        self.slack_custom_value = "Undefined"
        self.cluster = "Undefined"
        self.instance_name = "Undefined"
        self.task = "Undefined"

        self.printWelcome()
        self.configure_slack()

        signal.signal(signal.SIGINT, self.catch_ctrl_C)

    def printWelcome(self):
        pass

    def configure_slack(self):
        slack_url = ""
        try:
            self.configfile = os.getcwd() + '/config'
            config = ConfigParser.RawConfigParser()
            config.read(self.configfile)
            slack_url = config.get('slack', 'hookurl')

        except:
            print "Warning: No Slack integration found, so not using. See config file to setup."

        if len(slack_url) > 0:
            self.slack = slackweb.Slack(url=slack_url)

    def print_message(self, message, message_type="Note", to_slack=False):
        print "%s: %s" % (message_type.title(), message)

        if to_slack:
            color = "good"
            if message_type.lower() == "error":
                color = "danger"
            if message_type.lower() == "warning":
                color = "warning"
            self.send_slack_message(message, color)

    def send_slack_message(self, message, color="good"):

        attachments = []
        attachment = {"text": message, "color": color, "fields": [
            {
                "title": str(self.slack_custom_title),
                "value": str(self.slack_custom_value),
                "short": "true"
            },
            {
                "title": "Task",
                "value": self.task,
                "short": "true"
            },
            {
                "title": "Cluster",
                "value": self.cluster,
                "short": "true"
            },
            {
                "title": "Instance ID",
                "value": self.instance_name,
                "short": "true"
            }
        ]}

        attachments.append(attachment)
        self.slack.notify(attachments=attachments, icon_emoji=":robot_face:", username="cloudstackOps")

    # Handle unwanted CTRL+C presses
    def catch_ctrl_C(self, sig, frame):
        print "Warning: do not interrupt! If you really want to quit, use kill -9."

    # Read config files
    def readConfigFile(self):
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
