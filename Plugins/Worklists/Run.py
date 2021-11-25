#!/usr/bin/python
# -*- coding: utf-8 -*-


# Orthanc - A Lightweight, RESTful DICOM Store
# Copyright (C) 2012-2016 Sebastien Jodogne, Medical Physics
# Department, University Hospital of Liege, Belgium
# Copyright (C) 2017-2021 Osimis S.A., Belgium
# Copyright (C) 2021-2021 Sebastien Jodogne, ICTEAM UCLouvain, Belgium
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

parser = argparse.ArgumentParser(description = 'Run the integration tests for the DICOM worklist plugin.')

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
parser.add_argument('--dicom',
                    type = int,
                    default = 4242,
                    help = 'DICOM port of the Orthanc instance to test')
parser.add_argument('options', metavar = 'N', nargs = '*',
                    help='Arguments to Python unittest')

args = parser.parse_args()



ORTHANC = DefineOrthanc(server = args.server,
                        username = args.username,
                        password = args.password,
                        restPort = args.rest)



##
## Toolbox
## 

DATABASE = os.path.abspath(os.path.normpath(os.path.join(os.path.dirname(__file__), '..', '..', 'Database', 'Worklists')))
WORKING = os.path.join(DATABASE, 'Working')

print('Database directory: %s' % DATABASE)
print('Working directory: %s' % WORKING)

try:
    os.mkdir(WORKING)
except Exception as e:
    # The working folder has already been created
    pass

def ClearDatabase():
    for f in os.listdir(WORKING):
        if f != 'lockfile':
            os.remove(os.path.join(WORKING, f))

def AddToDatabase(worklist):
    extension = os.path.splitext(worklist)[1].lower()
    source = os.path.join(DATABASE, worklist)
    target = os.path.join(WORKING, os.path.basename(worklist) + '.wl')

    if extension == '.dump':
        subprocess.check_call([ 'dump2dcm', '--write-xfer-little', source, target ])
    else:
        copyfile(source, target)
        

def RunQuery(source, ignoreTags):
    with tempfile.NamedTemporaryFile() as f:
        subprocess.check_call([ 'dump2dcm', '--write-xfer-little',
                                os.path.join(DATABASE, source), f.name ])

        a = subprocess.check_output([ 'findscu', '-v', '--call', 'ORTHANC', '-aet', 'ORTHANCTEST',
                                      args.server, str(args.dicom), f.name ],
                                    stderr = subprocess.STDOUT).splitlines()

        if len(filter(lambda x: x.startswith('E:'), a)) > 0:
            raise Exception('Error while running findscu')

        b = map(lambda x: x[3:], filter(lambda x: (x.startswith('I: ---') or
                                                   x.startswith('W: ---') or
                                                   x.startswith('I: (') or
                                                   x.startswith('W: (')), a))
        b = map(lambda x: re.sub(r'\s*#.*', '', x), b)

        answers = []
        current = []
        isQuery = True

        for l in b:
            l = l.replace('\0', '')
            
            if l[0] == '-':
                if isQuery:
                    isQuery = False
                else:
                    # This is a separator between DICOM datasets
                    if len(current) > 0:
                        answers.append(current)
                        current = []

            else:
                if not isQuery:
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


def ParseTopLevelTags(answer):
    tags = {}
    for line in answer:
        m = re.match(r'^\(([0-9a-f]{4},[0-9a-f]{4})\)\s*..\s*\[([^]]*)\]', line)
        tags[m.group(1)] = m.group(2).strip()
        
    return tags


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
        DoPost(ORTHANC, '/tools/execute-script', 'function IncomingWorklistRequestFilter(query, origin) return query end', 'application/lua')


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


    @unittest.skip("This test requires to enable option 'FilterIssuerAet' in the sample worklist plugin")
    def test_filter_issuer_aet(self):
        AddToDatabase('Sequences/STATION_AET/orig.7814.dump')
        AddToDatabase('Sequences/STATION_AET/orig.7814.other.station.dump')

        self.assertEqual(1, len(RunQuery('Sequences/Queries/7814.without.station.aet.dump', [])))

    def test_filter_issuer_aet_from_lua(self):
        AddToDatabase('Sequences/STATION_AET/orig.7814.dump')  # targeted at STATION_AET
        AddToDatabase('Sequences/STATION_AET/orig.7814.other.station.dump') # targeted at ORTHANC_TEST

        self.assertEqual(2, len(RunQuery('Sequences/Queries/7814.without.station.aet.dump', []))) # query is not targeting any station -> match all
        InstallLuaScript(ORTHANC, "\
            function IncomingWorklistRequestFilter(query, origin)\
                query['0040,0100'][1]['0040,0001'] = origin['RemoteAet']\
                return query\
            end");

        self.assertEqual(1, len(RunQuery('Sequences/Queries/7814.without.station.aet.dump', []))) # now, query is targeting ORTHANCTEST -> match one


    def test_remove_aet_from_query(self):
        AddToDatabase('Sequences/NO_STATION_AET/orig.7814.other.station.dump')  # targeted at ORTHANCTEST

        self.assertEqual(0, len(RunQuery('Sequences/Queries/orig.7814.dump', []))) # query is targeting STATION_AET -> will not match
        InstallLuaScript(ORTHANC, "\
            function IncomingWorklistRequestFilter(query, origin)\
                query['0040,0100'][1]['0040,0001'] = nil\
                return query\
            end");
        self.assertEqual(1, len(RunQuery('Sequences/Queries/orig.7814.dump', []))) # query is targeting STATION_AET but, since we have removed this field, we should get 2 queries

    def test_encodings(self):
        # Check out ../../Database/Worklists/Encodings/database.dump
        TEST = u'Test-éüäöòДΘĝדصķћ๛ﾈİ'
        ENCODINGS = {
            'Arabic' :   [ 'ISO_IR 127' ], 
            'Ascii' :    [ 'ISO_IR 6' ],   # More accurately, ISO 646
            'Cyrillic' : [ 'ISO_IR 144' ], 
            'Greek' :    [ 'ISO_IR 126' ], 
            'Hebrew' :   [ 'ISO_IR 138' ],
            'Japanese' : [ 'ISO_IR 13', 'shift-jis' ],
            'Latin1' :   [ 'ISO_IR 100' ],
            'Latin2' :   [ 'ISO_IR 101' ], 
            'Latin3' :   [ 'ISO_IR 109' ],
            'Latin4' :   [ 'ISO_IR 110' ], 
            'Latin5' :   [ 'ISO_IR 148' ], 
            'Thai' :     [ 'ISO_IR 166', 'tis-620' ],
            'Utf8' :     [ 'ISO_IR 192' ],
        }

        AddToDatabase('Encodings/database.dump')

        for name, encoding in ENCODINGS.iteritems():
            self.assertEqual(name, DoPut(ORTHANC, '/tools/default-encoding', name))
            result = RunQuery('Encodings/query.dump', [])

            self.assertEqual(1, len(result))
            self.assertEqual(2, len(result[0]))
            tags = ParseTopLevelTags(result[0])

            if len(encoding) == 1:
                encoded = TEST.encode(name, 'ignore')
            else:
                encoded = TEST.encode(encoding[1], 'ignore')

            self.assertEqual(encoding[0], tags['0008,0005'])
            self.assertEqual(encoded, tags['0010,0010'])


    def test_bitbucket_issue_49(self):
        def Check(encoding, expectedEncoding, expectedContent):
            DoPut(ORTHANC, '/tools/default-encoding', encoding)
            result = RunQuery('Encodings/issue49-latin1.query', [])
            self.assertEqual(1, len(result))
            self.assertEqual(2, len(result[0]))
            tags = ParseTopLevelTags(result[0])
            self.assertEqual(expectedEncoding, tags['0008,0005'])
            self.assertEqual(expectedContent, tags['0010,0010'])

        AddToDatabase('Encodings/issue49-latin1.wl')
        Check('Ascii', 'ISO_IR 6', r'VANILL^LAURA^^^Mme')
        Check('Utf8', 'ISO_IR 192', r'VANILLÉ^LAURA^^^Mme')
        Check('Latin1', 'ISO_IR 100', u'VANILLÉ^LAURA^^^Mme'.encode('latin-1', 'ignore'))


    def test_format(self):
        DoPut(ORTHANC, '/tools/default-encoding', 'Latin1')
        AddToDatabase('Dcmtk/Database/wklist1.dump')

        # Only behavior of Orthanc <= 1.9.4
        a = DoPost(ORTHANC, '/modalities/self/find-worklist', {
            'PatientID' : ''
            })
        self.assertEqual(1, len(a))
        self.assertEqual(2, len(a[0]))
        self.assertEqual('AV35674', a[0]['PatientID'])
        self.assertEqual('ISO_IR 100', a[0]['SpecificCharacterSet'])
        
        a = DoPost(ORTHANC, '/modalities/self/find-worklist', {
            'Query' : {
                'PatientID' : ''
                }
            })
        self.assertEqual(1, len(a))
        self.assertEqual(2, len(a[0]))
        self.assertEqual('AV35674', a[0]['PatientID'])
        self.assertEqual('ISO_IR 100', a[0]['SpecificCharacterSet'])
        
        a = DoPost(ORTHANC, '/modalities/self/find-worklist', {
            'Query' : {
                'PatientID' : ''
                },
            'Short' : True
            })
        self.assertEqual(1, len(a))
        self.assertEqual(2, len(a[0]))
        self.assertEqual('AV35674', a[0]['0010,0020'])
        self.assertEqual('ISO_IR 100', a[0]['0008,0005'])
        
        a = DoPost(ORTHANC, '/modalities/self/find-worklist', {
            'Query' : {
                'PatientID' : ''
                },
            'Full' : True
            })
        self.assertEqual(1, len(a))
        self.assertEqual(2, len(a[0]))
        self.assertEqual('AV35674', a[0]['0010,0020']['Value'])
        self.assertEqual('PatientID', a[0]['0010,0020']['Name'])
        self.assertEqual('ISO_IR 100', a[0]['0008,0005']['Value'])
        self.assertEqual('SpecificCharacterSet', a[0]['0008,0005']['Name'])
 
        
try:
    print('\nStarting the tests...')
    unittest.main(argv = [ sys.argv[0] ] + args.options)

finally:
    print('\nDone')
