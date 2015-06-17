#!/usr/bin/python

# Orthanc - A Lightweight, RESTful DICOM Store
# Copyright (C) 2012-2015 Sebastien Jodogne, Medical Physics
# Department, University Hospital of Liege, Belgium
#
# This program is free software: you can redistribute it and/or
# modify it under the terms of the GNU General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.


# sudo docker run --rm -t -i -v `pwd`:/tmp/tests:ro -p 5000:8042 -p 5001:4242 --entrypoint python jodogne/orthanc-tests /tmp/tests/Run.py --force



import re
import sys
import argparse
import subprocess
import unittest

from ExternalCommandThread import *
from Toolbox import *
from Tests import *


##
## Parse the command-line arguments
##

parser = argparse.ArgumentParser(description = 'Run the integration tests on some instance of Orthanc.')
parser.add_argument('--server', 
                    default = GetDockerHostAddress(),
                    help = 'Address of the Orthanc server to test')
parser.add_argument('--aet',
                    default = 'ORTHANC',
                    help = 'AET of the Orthanc instance to test')
parser.add_argument('--dicom',
                    type = int,
                    default = 4242,
                    help = 'DICOM port of the Orthanc instance to test')
parser.add_argument('--rest',
                    type = int,
                    default = 8042,
                    help = 'Port to the REST API')
parser.add_argument('--username',
                    default = 'alice',
                    help = 'Username to the REST API')
parser.add_argument('--password',
                    default = 'orthanctest',
                    help = 'Password to the REST API')
parser.add_argument('--force', help = 'Do not warn the user',
                    action = 'store_true')

args = parser.parse_args()

if not args.force:
    print("""
WARNING: This test will remove all the content of your
Orthanc instance running on %s!

Are you sure ["yes" to go on]?""" % args.server)

    if sys.stdin.readline().strip() != 'yes':
        print('Aborting...')
        exit(0)



## 
## Generate the configuration file for the anciliary instance of
## Orthanc
##

CONFIG = '/tmp/Configuration.json'
subprocess.check_call([ 'Orthanc', '--config=%s' % CONFIG ])

with open(CONFIG, 'r') as f:
    config = f.read()

config = re.sub(r'("StorageDirectory"\s*:)\s*".*?"', r'\1 "/tmp/OrthancStorage"', config)
config = re.sub(r'("IndexDirectory"\s*:)\s*".*?"', r'\1 "/tmp/OrthancStorage"', config)
config = re.sub(r'("DicomAet"\s*:)\s*".*?"', r'\1 "ORTHANCTEST"', config)
config = re.sub(r'("RemoteAccessAllowed"\s*:)\s*false', r'\1 true', config)
config = re.sub(r'("AuthenticationEnabled"\s*:)\s*false', r'\1 true', config)
config = re.sub(r'("RegisteredUsers"\s*:)\s*{', r'\1 { "alice" : [ "orthanctest" ]', config)
config = re.sub(r'("DicomModalities"\s*:)\s*{', r'\1 { "orthanc" : [ "%s", "%s", "%s" ]' % 
                (args.aet, args.server, args.dicom), config)

localOrthanc = ExternalCommandThread([ 
        'Orthanc', CONFIG, #'--verbose'
        ])


LOCAL = DefineOrthanc(aet = 'ORTHANCTEST')
REMOTE = DefineOrthanc(url = 'http://%s:%d/' % (args.server, args.rest),
                       username = args.username,
                       password = args.password,
                       aet = args.aet,
                       dicomPort = args.dicom)



print('Parameters of the instance of Orthanc to test:')
print(REMOTE)
print('')


print('Waiting for the internal Orthanc to start...')
while True:
    try:
        DoGet(LOCAL, '/instances')
        break
    except:
        time.sleep(0.1)


try:
    print('Starting the tests...')
    SetOrthancParameters(LOCAL, REMOTE)
    unittest.main(argv = [ sys.argv[0] ]) #argv = args)

finally:
    # The tests have stopped or "Ctrl-C" has been hit
    try:
        localOrthanc.stop()
    except:
        pass
