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
                    default = None,
                    help = 'Username to the REST API')
parser.add_argument('--password',
                    default = None,
                    help = 'Password to the REST API')
parser.add_argument("--force", help = "Do not warn the user",
                    action = "store_true")

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



class Orthanc(unittest.TestCase):
    def setUp(self):
        DropOrthanc(LOCAL)
        DropOrthanc(REMOTE)

    def test_system(self):
        self.assertTrue('Version' in DoGet(REMOTE, '/system'))
        self.assertEqual('0', DoGet(REMOTE, '/statistics')['TotalDiskSize'])
        self.assertEqual('0', DoGet(REMOTE, '/statistics')['TotalUncompressedSize'])

    def test_upload(self):
        u = UploadInstance(REMOTE, 'DummyCT.dcm')
        self.assertEqual('Success', u['Status'])
        u = UploadInstance(REMOTE, 'DummyCT.dcm')
        self.assertEqual('AlreadyStored', u['Status'])
        self.assertEqual(1, len(DoGet(REMOTE, '/patients')))
        self.assertEqual(1, len(DoGet(REMOTE, '/studies')))
        self.assertEqual(1, len(DoGet(REMOTE, '/series')))
        self.assertEqual(1, len(DoGet(REMOTE, '/instances')))

        i = DoGet(REMOTE, '/instances/%s/simplified-tags' % u['ID'])
        self.assertEqual('20070101', i['StudyDate'])


    def test_rest_grid(self):
        i = UploadInstance(REMOTE, 'DummyCT.dcm')['ID']
        instance = DoGet(REMOTE, '/instances/%s' % i)
        self.assertEqual(i, instance['ID'])
        self.assertEqual('1.2.840.113619.2.176.2025.1499492.7040.1171286242.109',
                         instance['MainDicomTags']['SOPInstanceUID'])

        series = DoGet(REMOTE, '/series/%s' % instance['ParentSeries'])
        self.assertEqual('1.2.840.113619.2.176.2025.1499492.7391.1171285944.394', 
                         series['MainDicomTags']['SeriesInstanceUID'])

        study = DoGet(REMOTE, '/studies/%s' % series['ParentStudy'])
        self.assertEqual('1.2.840.113619.2.176.2025.1499492.7391.1171285944.390',
                         study['MainDicomTags']['StudyInstanceUID'])

        patient = DoGet(REMOTE, '/patients/%s' % study['ParentPatient'])
        self.assertEqual('ozp00SjY2xG',
                         patient['MainDicomTags']['PatientID'])

        dicom = DoGet(REMOTE, '/instances/%s/file' % instance['ID'])
        self.assertEqual(2472, len(dicom))
        self.assertEqual('3e29b869978b6db4886355a2b1132124', ComputeMD5(dicom))
        self.assertEqual(1, len(DoGet(REMOTE, '/instances/%s/frames' % i)))
        self.assertEqual('TWINOW', DoGet(REMOTE, '/instances/%s/simplified-tags' % i)['StationName'])
        self.assertEqual('TWINOW', DoGet(REMOTE, '/instances/%s/tags' % i)['0008,1010']['Value'])


try:
    print('Waiting for the internal Orthanc to start...')
    while True:
        try:
            DoGet(LOCAL, '/instances')
            break
        except:
            time.sleep(0.1)

    print('Starting the tests...')
    unittest.main(argv = [ sys.argv[0] ]) #argv = args)

finally:
    # The tests have stopped or "Ctrl-C" has been hit
    try:
        localOrthanc.stop()
    except:
        pass
