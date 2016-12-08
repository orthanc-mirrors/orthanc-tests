#!/usr/bin/python

# Orthanc - A Lightweight, RESTful DICOM Store
# Copyright (C) 2012-2016 Sebastien Jodogne, Medical Physics
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
import pprint
import re
import subprocess
import sys
import tempfile
import unittest

sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'Tests'))
from Toolbox import *


##
## Parse the command-line arguments
##

parser = argparse.ArgumentParser(description = 'Run the integration tests for the DICOM worklist plugin.')

parser.add_argument('--server', 
                    default = 'localhost',
                    help = 'Address of the Orthanc server to test')
parser.add_argument('--dicom',
                    type = int,
                    default = 4242,
                    help = 'DICOM port of the Orthanc instance to test')
parser.add_argument('options', metavar = 'N', nargs = '*',
                    help='Arguments to Python unittest')

args = parser.parse_args()



##
## Toolbox
## 

DATABASE = os.path.abspath(os.path.normpath(os.path.join(os.path.dirname(__file__), '..', '..', 'Database', 'Worklists')))
WORKING = os.path.join(DATABASE, 'Working')

try:
    os.mkdir(WORKING)
except Exception as e:
    # The working folder has already been created
    pass

def ClearDatabase():
    for f in os.listdir(WORKING):
        if f != 'lockfile':
            os.remove(os.path.join(WORKING, f))

def AddToDatabase(source):
    subprocess.check_call([ 'dump2dcm', '--write-xfer-little',
                            os.path.join(DATABASE, source),
                            os.path.join(WORKING, os.path.basename(source) + '.wl') ])

def RunQuery(source, ignoreTags):
    with tempfile.NamedTemporaryFile() as f:
        subprocess.check_call([ 'dump2dcm', '--write-xfer-little',
                                os.path.join(DATABASE, source), f.name ])

        a = subprocess.check_output([ 'findscu', '-v', '--call', 'ORTHANC', '-aet', 'ORTHANCTEST',
                                      args.server, str(args.dicom), f.name ],
                                    stderr = subprocess.STDOUT).splitlines()

        if len(filter(lambda x: x.startswith('E:'), a)) > 0:
            raise Exception('Error while running findscu')

        b = map(lambda x: x[3:], filter(lambda x: x.startswith('W: ---') or x.startswith('W: ('), a))
        b = map(lambda x: re.sub(r'\s*#.*', '', x), b)

        answers = []
        current = []

        for l in b:
            if l[0] == '-':
                # This is a separator between DICOM datasets
                if len(current) > 0:
                    answers.append(current)
                    current = []

            else:
                tag = l[1:10].lower()
                if not tag in ignoreTags:
                    current.append(l)

        if len(current) > 0:
            answers.append(current)

        return answers

def CompareAnswers(expected, actual):
    if len(expected) != len(actual):
        return False

    if len(expected) == 0:
        return True

    for i in range(len(expected)):
        for j in range(len(actual)):
            if expected[i] == actual[j]:
                return True

    return False


##
## The tests
##

class Orthanc(unittest.TestCase):
    def setUp(self):
        if (sys.version_info >= (3, 0)):
            # Remove annoying warnings about unclosed socket in Python 3
            import warnings
            warnings.simplefilter("ignore", ResourceWarning)

        ClearDatabase()


    def test_single(self):
        for db in range(1, 11):
            ClearDatabase()
            AddToDatabase('Dcmtk/Database/wklist%d.dump' % db)

            for query in range(0, 13):
                answers = RunQuery('Dcmtk/Queries/wlistqry%d.dump' % query, [
                    '0008,0005', 
                    '0040,0004',
                    '0040,0005',
                    '0040,0020',
                ])

                with open(os.path.join('%s/Dcmtk/Expected/single-%d-%d.json' % (DATABASE, db, query)), 'r') as f:
                    expected = json.loads(f.read())
                    self.assertTrue(CompareAnswers(expected, answers))


    def test_all(self):
        ClearDatabase()

        for db in range(1, 11):
            AddToDatabase('Dcmtk/Database/wklist%d.dump' % db)

        for query in range(0, 13):
            answers = RunQuery('Dcmtk/Queries/wlistqry%d.dump' % query, [
                '0008,0005', 
                '0040,0004',
                '0040,0005',
                '0040,0020',
            ])

            with open(os.path.join('%s/Dcmtk/Expected/all-%d.json' % (DATABASE, query)), 'r') as f:
                expected = json.loads(f.read())
                self.assertTrue(CompareAnswers(expected, answers))


    def test_vet(self):
        AddToDatabase('Sequences/STATION_AET/orig.7705.dump')
        AddToDatabase('Sequences/STATION_AET/orig.7814.dump')
        AddToDatabase('Sequences/STATION_AET/orig.7814.without.seq.dump')
        
        self.assertEqual(2, len(RunQuery('Sequences/Queries/7814.without.length.dump', [])))
        self.assertEqual(2, len(RunQuery('Sequences/Queries/7814.without.seq.dump', [])))
        self.assertEqual(2, len(RunQuery('Sequences/Queries/orig.7814.dump', [])))



try:
    print('\nStarting the tests...')
    unittest.main(argv = [ sys.argv[0] ] + args.options)

finally:
    print('\nDone')
