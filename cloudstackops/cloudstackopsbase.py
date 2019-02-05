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

import configparser
import os
import pprint
import signal
import sys

# Slackweb
try:
    import slackweb
except Exception as e:
    print("Error: Please install slackweb library to support Slack messaging: %s" % e)
    print("       pip install slackweb")
    sys.exit(1)

# Colored terminals
try:
    from clint.textui import colored
except Exception as e:
    print("Error: Please install clint library to support color in the terminal: %s" % e)
    print("       pip install clint")
    sys.exit(1)


class Timeout:
    """Timeout class using ALARM signal."""

    class Timeout(Exception):
        pass

    def __init__(self, sec):
        self.sec = sec

    def __enter__(self):
        signal.signal(signal.SIGALRM, self.raise_timeout)
        signal.alarm(self.sec)

    def __exit__(self, *args):
        signal.alarm(0)  # disable alarm

    def raise_timeout(self, *args):
        raise Timeout.Timeout()


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
        self.vm_name = "Undefined"
        self.zone_name = "Undefined"

        self.printWelcome()
        self.configure_slack()

        signal.signal(signal.SIGINT, self.catch_ctrl_C)

    def printWelcome(self):
        pass

    def configure_slack(self):
        slack_url = ""
        try:
            self.configfile = os.getcwd() + '/config'
            config = configparser.RawConfigParser()
            config.read(self.configfile)
            slack_url = config.get('slack', 'hookurl')

        except:
            print("Warning: No Slack integration found, so not using. See config file to setup.")

        self.slack = None
        if len(slack_url) > 0:
            self.slack = slackweb.Slack(url=slack_url)

    def print_message(self, message, message_type="Note", to_slack=False):
        if message_type != "Plain":
            print("%s: %s" % (message_type.title(), message))

        if to_slack and self.slack is not None:
            color = "good"
            if message_type.lower() == "error":
                color = "danger"
            if message_type.lower() == "warning":
                color = "warning"
            self.send_slack_message(message, color)

    def send_slack_message(self, message, color="good"):

        attachments = []
        attachment = {"text": message, "color": color, "mrkdwn_in": ["text", "pretext", "fields"], "mrkdwn": "true",
                      "fields": [
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
                          },
                          {
                              "title": "VM name",
                              "value": self.vm_name,
                              "short": "true"
                          },
                          {
                              "title": "Zone",
                              "value": self.zone_name,
                              "short": "true"
                          }
                      ]}

        try:
            attachments.append(attachment)
            self.slack.notify(attachments=attachments, icon_emoji=":robot_face:", username="cloudstackOps")
        except:
            print("Warning: Slack said NO.")

    # Handle unwanted CTRL+C presses
    def catch_ctrl_C(self, sig, frame):
        print("Warning: do not interrupt! If you really want to quit, use kill -9.")

    # Read config files
    def readConfigFile(self):
        # Read our own config file for some more settings
        config = configparser.RawConfigParser()
        config.read(self.configfile)
        try:
            self.organization = config.get('cloudstackOps', 'organization')
            self.smtpserver = config.get('mail', 'smtpserver')
            self.mail_from = config.get('mail', 'mail_from')
            self.errors_to = config.get('mail', 'errors_to')
        except:
            print("Error: Cannot read or parse CloudStackOps config file '" + self.configfile + "'")
            print("Hint: Setup the local config file 'config', using 'config.sample' as a starting point. See documentation.")
            sys.exit(1)
