#!/usr/bin/python3
# -*- coding: utf-8 -*-


# Orthanc - A Lightweight, RESTful DICOM Store
# Copyright (C) 2012-2016 Sebastien Jodogne, Medical Physics
# Department, University Hospital of Liege, Belgium
# Copyright (C) 2017-2023 Osimis S.A., Belgium
# Copyright (C) 2024-2026 Orthanc Team SRL, Belgium
# Copyright (C) 2021-2026 Sebastien Jodogne, ICTEAM UCLouvain, Belgium
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
import pprint
import re
import subprocess
import sys
import tempfile
import unittest
from shutil import copyfile

sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'Tests'))
from Toolbox import *


##
## Parse the command-line arguments
##

parser = argparse.ArgumentParser(description = 'Run the integration tests for the WSI Dicomizer.')

parser.add_argument('--server',
                    default = 'localhost',
                    help = 'Address of the Orthanc server to test')
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
parser.add_argument('options', metavar = 'N', nargs = '*',
                    help='Arguments to Python unittest')

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
## The tests
##

ORTHANC = DefineOrthanc(server = args.server,
                        username = args.username,
                        password = args.password,
                        restPort = args.rest)

class Orthanc(unittest.TestCase):
    def setUp(self):
        if (sys.version_info >= (3, 0)):
            # Remove annoying warnings about unclosed socket in Python 3
            import warnings
            warnings.simplefilter("ignore", ResourceWarning)

        DropOrthanc(ORTHANC)


    def test_single(self):
        print('hello')


try:
    print('\nStarting the tests...')
    unittest.main(argv = [ sys.argv[0] ] + args.options)

finally:
    print('\nDone')
