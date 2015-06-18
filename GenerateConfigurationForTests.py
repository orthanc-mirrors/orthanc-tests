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


import argparse
import os
import re
import socket
import subprocess
import sys

##
## Parse the command-line arguments
##

parser = argparse.ArgumentParser(description = 'Generate the configuration file for the ' +
                                 'instance of Orthanc to be checked against the integration tests.')

parser.add_argument('--target', 
                    default = 'IntegrationTestsConfiguration.json',
                    help = 'Configuration file to generate')

parser.add_argument('--force', 
                    help = 'Overwrite the file even if it already exists',
                    action = 'store_true')

args = parser.parse_args()


##
## Check whether the file can be overwritten
##

if os.path.exists(args.target) and not args.force:
    print("""
WARNING: The file %s will be overwritten!

Are you sure ["yes" to go on]?""" % args.target)

    if sys.stdin.readline().strip() != 'yes':
        print('Aborting...')
        exit(0)


## 
## Generate the configuration file
##


# Retrieve the IP address of the localhost
ip = socket.gethostbyname(socket.gethostname())

subprocess.check_call([ 'Orthanc', '--config=%s' % args.target ])

with open(args.target, 'r') as f:
    config = f.read()

config = re.sub(r'("DicomAet"\s*:)\s*".*?"', r'\1 "ORTHANC"', config)
config = re.sub(r'("RemoteAccessAllowed"\s*:)\s*false', r'\1 true', config)
config = re.sub(r'("AuthenticationEnabled"\s*:)\s*false', r'\1 true', config)
config = re.sub(r'("RegisteredUsers"\s*:)\s*{', r'\1 { "alice" : "orthanctest"', config)
config = re.sub(r'("DicomModalities"\s*:)\s*{', r'\1 { "orthanctest" : [ "%s", "%s", %d ]' % 
                ('ORTHANCTEST', ip, 5001), config)
config = re.sub(r'("OrthancPeers"\s*:)\s*{', r'\1 { "peer" : [ "http://%s:%d/", "%s", "%s" ]' % 
                (ip, 5000, 'alice', 'orthanctest'), config)

# Enable case-insensitive PN (the default on versions <= 0.8.6)
config = re.sub(r'("CaseSensitivePN"\s*:)\s*true', r'\1 false', config) 

with open(args.target, 'wt') as f:
    f.write(config)

