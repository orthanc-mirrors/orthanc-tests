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


import os
import pprint
import sys
import argparse
import unittest
import re
from DicomWeb import *

sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'Tests'))
from Toolbox import *


##
## Parse the command-line arguments
##

parser = argparse.ArgumentParser(description = 'Run the integration tests for the DICOMweb plugin.')

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
parser.add_argument('--wado',
                    default = '/wado',
                    help = 'Path to the WADO API')
parser.add_argument('--dicomweb',
                    default = '/dicom-web/',
                    help = 'Path to the DICOMweb API')
parser.add_argument('--force', help = 'Do not warn the user',
                    action = 'store_true')
parser.add_argument('options', metavar = 'N', nargs = '*',
                    help='Arguments to Python unittest')

args = parser.parse_args()


##
## Configure the testing context
##

if not args.force:
    print("""
WARNING: This test will remove all the content of your
Orthanc instance running on %s!

Are you sure ["yes" to go on]?""" % args.server)

    if sys.stdin.readline().strip() != 'yes':
        print('Aborting...')
        exit(0)


ORTHANC = DefineOrthanc(server = args.server,
                        username = args.username,
                        password = args.password,
                        restPort = args.rest)


##
## The tests
##

class Orthanc(unittest.TestCase):
    def setUp(self):
        if (sys.version_info >= (3, 0)):
            # Remove annoying warnings about unclosed socket in Python 3
            import warnings
            warnings.simplefilter("ignore", ResourceWarning)

        DropOrthanc(ORTHANC)

    def test_wado_dicom(self):
        UploadInstance(ORTHANC, 'Brainix/Flair/IM-0001-0001.dcm')

        SIZE = 169478
        INSTANCE = '1.3.46.670589.11.0.0.11.4.2.0.8743.5.5396.2006120114314079549'
        SERIES = '1.3.46.670589.11.0.0.11.4.2.0.8743.5.5396.2006120114285654497'
        STUDY = '2.16.840.1.113669.632.20.1211.10000357775'

        self.assertRaises(Exception, lambda: DoGet(ORTHANC, args.wado))
        self.assertRaises(Exception, lambda: DoGet(ORTHANC, args.wado + '?requestType=WADO'))
        self.assertRaises(Exception, lambda: DoGet(ORTHANC, args.wado + '?objectUID=%s' % INSTANCE))

        dicom = DoGet(ORTHANC, args.wado + '?contentType=application/dicom&requestType=WADO&objectUID=%s' % INSTANCE)
        self.assertEqual(SIZE, len(dicom))

        dicom = DoGet(ORTHANC, args.wado + '?contentType=application/dicom&requestType=WADO&objectUID=%s&seriesUID=%s' % (INSTANCE, SERIES))
        self.assertEqual(SIZE, len(dicom))

        dicom = DoGet(ORTHANC, args.wado + '?contentType=application/dicom&requestType=WADO&objectUID=%s&seriesUID=%s&studyUID=%s' % (INSTANCE, SERIES, STUDY))
        self.assertEqual(SIZE, len(dicom))

        dicom = DoGet(ORTHANC, args.wado + '?contentType=application/dicom&requestType=WADO&objectUID=%s&seriesUID=%s' % (INSTANCE, SERIES))
        self.assertEqual(SIZE, len(dicom))

        dicom = DoGet(ORTHANC, args.wado + '?contentType=application/dicom&requestType=WADO&objectUID=%s&studyUID=%s' % (INSTANCE, STUDY))
        self.assertEqual(SIZE, len(dicom))

        self.assertRaises(Exception, lambda: DoGet(ORTHANC, args.wado + '?requestType=WADO&objectUID=%s&seriesUID=nope' % INSTANCE))
        self.assertRaises(Exception, lambda: DoGet(ORTHANC, args.wado + '?requestType=WADO&objectUID=%s&studyUID=nope' % INSTANCE))
        self.assertRaises(Exception, lambda: DoGet(ORTHANC, args.wado + '?requestType=WADO&objectUID=%s&seriesUID=nope&studyUID=nope' % INSTANCE))

    def test_wado_image(self):
        UploadInstance(ORTHANC, 'Phenix/IM-0001-0001.dcm')
        INSTANCE = '1.2.840.113704.7.1.1.6632.1127829031.2'

        im = GetImage(ORTHANC, args.wado + '?requestType=WADO&objectUID=%s' % INSTANCE)
        self.assertEqual('JPEG', im.format)
        self.assertEqual('L', im.mode)
        self.assertEqual(512, im.size[0])
        self.assertEqual(358, im.size[1])

        im = GetImage(ORTHANC, args.wado + '?contentType=image/jpg&requestType=WADO&objectUID=%s' % INSTANCE)
        self.assertEqual('JPEG', im.format)

        im = GetImage(ORTHANC, args.wado + '?contentType=image/png&requestType=WADO&objectUID=%s' % INSTANCE)
        self.assertEqual('PNG', im.format)
        self.assertEqual('L', im.mode)
        self.assertEqual(512, im.size[0])
        self.assertEqual(358, im.size[1])

    def test_stow(self):
        self.assertEqual(0, len(DoGet(ORTHANC, '/instances')))
        SendStow(ORTHANC, args.dicomweb + '/studies', GetDatabasePath('Phenix/IM-0001-0001.dcm'))
        self.assertEqual(1, len(DoGet(ORTHANC, '/instances')))
        a = SendStow(ORTHANC, args.dicomweb + '/studies', GetDatabasePath('Phenix/IM-0001-0001.dcm'))
        self.assertEqual(1, len(DoGet(ORTHANC, '/instances')))

        self.assertEqual(0, len(a['00081198']['Value']))  # No error
        self.assertEqual(1, len(a['00081199']['Value']))  # 1 success

        self.assertTrue(a['00081190']['Value'][0].endswith('studies/2.16.840.1.113669.632.20.1211.10000098591'))
        self.assertTrue(a['00081199']['Value'][0]['00081190']['Value'][0].
                        endswith('series/1.2.840.113704.1.111.5692.1127828999.2/instances/1.2.840.113704.7.1.1.6632.1127829031.2'))

        # Remove the "http://localhost:8042" prefix
        url = a['00081190']['Value'][0]
        url = re.sub(r'(http|https)://[^/]+(/.*)', r'\2', url)

        # Get the content-length of all the multiparts of this WADO-RS request
        b = DoGet(ORTHANC, url).decode('utf-8', 'ignore')
        parts = re.findall(r'^Content-Length:\s*(\d+)\s*', b, re.IGNORECASE | re.MULTILINE)
        self.assertEqual(1, len(parts))
        self.assertEqual(os.path.getsize(GetDatabasePath('Phenix/IM-0001-0001.dcm')), int(parts[0]))



try:
    print('\nStarting the tests...')
    unittest.main(argv = [ sys.argv[0] ] + args.options)

finally:
    print('\nDone')
