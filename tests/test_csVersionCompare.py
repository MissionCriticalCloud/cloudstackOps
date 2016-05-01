#!/usr/bin/python


v421_34 = '4.2.1-leaseweb34'
v421_34_4 = '4.2.1-leaseweb34-4'
v421_35 = '4.2.1-leaseweb35'
v421_4 = '4.2.1-leaseweb4'
v471_1 = '4.7.1-leaseweb5'
v471_1_1 = '4.7.1-leaseweb1-1'
v471_1_5 = '4.7.1-leaseweb1-5'

import os, sys, inspect

cmd_folder = os.path.realpath(os.path.abspath(os.path.split(inspect.getfile( inspect.currentframe() ))[0]) + '/../cloudstackops')
if cmd_folder not in sys.path:
    sys.path.insert(0, cmd_folder)

from lswcloudstackopsbase import LswCloudStackOpsBase


def test_version(a,b,expected):
   r = LswCloudStackOpsBase.csVersionCompare(a,b)
   status = 'PASSED'
   if expected != r:
       status = 'FAILED'
   if r == 0:
      print "%s == %s (%d) - %s" % (a,b,r,status)
   if r > 0:
      print "%s > %s (%d) - %s" % (a,b,r,status)
   if r < 0:
      print "%s < %s (%d) - %s" % (a,b,r,status)
   return (expected!=r)


test_version(v421_34, 	v421_34_4,  -5)
test_version(v421_34_4,	v421_35,    -4)
test_version(v421_34_4,	v421_4,     4)
test_version(v421_4, 	v421_34_4,  -4)
test_version(v421_34,	v471_1,     -2)
test_version(v421_34_4,	v471_1,     -2)
test_version(v471_1,	v471_1_1,   4)
test_version(v471_1_1,	v471_1_5,   -5)
test_version(v471_1_1,	v421_34_4,  2)

