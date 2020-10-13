#!/usr/bin/python

# Orthanc - A Lightweight, RESTful DICOM Store
# Copyright (C) 2012-2016 Sebastien Jodogne, Medical Physics
# Department, University Hospital of Liege, Belgium
# Copyright (C) 2017-2020 Osimis S.A., Belgium
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
import easywebdav
import io
import os
import pprint
import re
import sys
import unittest

sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'Tests'))
from Toolbox import *


##
## Parse the command-line arguments
##

parser = argparse.ArgumentParser(description = 'Run the integration tests for the patient recycling behavior.')

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

WEBDAV = easywebdav.connect(args.server,
                            port = args.rest,
                            username = args.username,
                            password = args.password)


##
## The tests
##


def ListFiles(path, recursive):
    result = [ ]
    for i in WEBDAV.ls(path):
        if i.name == path:
            pass
        elif i.contenttype == '':
            if recursive:
                result += ListFiles(i.name + '/', True)
        else:
            result.append(i.name)
    return result


def GetFileInfo(path):
    for i in WEBDAV.ls(path[0 : path.rfind('/')]):
        if i.name == path:
            return i
    raise Exception('Cannot find: %s' % path)


def DownloadFile(path):
    with tempfile.NamedTemporaryFile(delete = False) as f:
        f.close()
        WEBDAV.download(path, f.name)
        with open(f.name, 'rb') as g:
            result = g.read()
        os.unlink(f.name)
        return result
    

class Orthanc(unittest.TestCase):
    def setUp(self):
        if (sys.version_info >= (3, 0)):
            # Remove annoying warnings about unclosed socket in Python 3
            import warnings
            warnings.simplefilter("ignore", ResourceWarning)

        DropOrthanc(ORTHANC)

        
    def test_root(self):
        self.assertEqual(6, len(WEBDAV.ls('/webdav/')))
        for i in WEBDAV.ls('/webdav/'):
            self.assertTrue(i.name in [
                '/webdav/',
                '/webdav/by-dates',
                '/webdav/by-patients',
                '/webdav/by-studies',
                '/webdav/by-uids',
                '/webdav/uploads'
            ])
            self.assertEqual(0, i.size)
            self.assertEqual('', i.contenttype)

        patients = WEBDAV.ls('/webdav/by-patients/')
        self.assertEqual(1, len(patients))
        self.assertEqual(patients[0].name, '/webdav/by-patients/')
        self.assertEqual(0, patients[0].size)
        self.assertEqual('', patients[0].contenttype)


    def test_upload(self):
        self.assertEqual(0, len(ListFiles('/webdav/uploads/', True)))

        uploads = WEBDAV.ls('/webdav/uploads/')
        for i in uploads:
            self.assertEqual(i.contenttype, '')  # Only folders are allowed
        
        self.assertEqual(0, len(DoGet(ORTHANC, '/studies')))
        WEBDAV.upload(GetDatabasePath('DummyCT.dcm'), '/webdav/uploads/DummyCT.dcm')

        while len(ListFiles('/webdav/uploads/', True)) > 1:
            time.sleep(0.1)
        
        instances = DoGet(ORTHANC, '/instances?expand')
        self.assertEqual(1, len(instances))
        self.assertEqual('1.2.840.113619.2.176.2025.1499492.7040.1171286242.109',
                         instances[0]['MainDicomTags']['SOPInstanceUID'])

        
    def test_upload_folders(self):
        self.assertEqual(0, len(ListFiles('/webdav/uploads/', True)))
        self.assertEqual(0, len(DoGet(ORTHANC, '/studies')))

        try:
            WEBDAV.mkdir('/webdav/uploads/a')
        except:
            pass
        try:
            WEBDAV.mkdir('/webdav/uploads/b')
        except:
            pass

        WEBDAV.upload(GetDatabasePath('DummyCT.dcm'), '/webdav/uploads/a/DummyCT.dcm')
        WEBDAV.upload(GetDatabasePath('ColorTestMalaterre.dcm'), '/webdav/uploads/b/ColorTestMalaterre.dcm')
        
        while len(ListFiles('/webdav/uploads/', True)) > 1:
            time.sleep(0.1)
        
        self.assertEqual(2, len(DoGet(ORTHANC, '/instances')))


    def test_by_uids(self):
        self.assertEqual(1, len(WEBDAV.ls('/webdav/by-uids/')))
        self.assertEqual(0, len(ListFiles('/webdav/by-uids/', True)))
        self.assertEqual(0, len(DoGet(ORTHANC, '/instances')))

        i = UploadInstance(ORTHANC, 'DummyCT.dcm')['ID']
        instance = DoGet(ORTHANC, '/instances/%s/tags?simplify' % i)
        studyUid = instance['StudyInstanceUID']
        seriesUid = instance['SeriesInstanceUID']
        sopUid = instance['SOPInstanceUID']

        self.assertEqual(0, len(ListFiles('/webdav/by-uids/', False)))
        self.assertEqual(1, len(ListFiles('/webdav/by-uids/%s/' % studyUid, False)))
        self.assertEqual(2, len(ListFiles('/webdav/by-uids/%s/%s/' % (studyUid, seriesUid), False)))

        content = ListFiles('/webdav/by-uids/', True)
        self.assertEqual(3, len(content))
        self.assertTrue(('/webdav/by-uids/%s/study.json' % studyUid) in content)
        self.assertTrue(('/webdav/by-uids/%s/%s/series.json' % (studyUid, seriesUid)) in content)
        self.assertTrue(('/webdav/by-uids/%s/%s/%s.dcm' % (studyUid, seriesUid, sopUid)) in content)

        info = GetFileInfo('/webdav/by-uids/%s/study.json' % studyUid)
        self.assertEqual(info.contenttype, 'application/json')
        
        info = GetFileInfo('/webdav/by-uids/%s/%s/series.json' % (studyUid, seriesUid))
        self.assertEqual(info.contenttype, 'application/json')
        
        info = GetFileInfo('/webdav/by-uids/%s/%s/%s.dcm' % (studyUid, seriesUid, sopUid))
        self.assertEqual(info.contenttype, 'application/dicom')
        self.assertEqual(info.size, os.stat(GetDatabasePath('DummyCT.dcm')).st_size)

        a = DownloadFile('/webdav/by-uids/%s/%s/%s.dcm' % (studyUid, seriesUid, sopUid))
        self.assertEqual(len(a), info.size)

        with open(GetDatabasePath('DummyCT.dcm'), 'rb') as f:
            self.assertEqual(a, f.read())

        self.assertEqual(studyUid, json.loads(DownloadFile('/webdav/by-uids/%s/study.json' % studyUid))
                         ['MainDicomTags']['StudyInstanceUID'])

        self.assertEqual(seriesUid, json.loads(DownloadFile('/webdav/by-uids/%s/%s/series.json' % (studyUid, seriesUid)))
                         ['MainDicomTags']['SeriesInstanceUID'])

        self.assertEqual(1, len(DoGet(ORTHANC, '/instances')))
        WEBDAV.delete('/webdav/by-uids/%s/%s/%s.dcm' % (studyUid, seriesUid, sopUid))
        self.assertEqual(0, len(DoGet(ORTHANC, '/instances')))
            
try:
    print('\nStarting the tests...')
    unittest.main(argv = [ sys.argv[0] ] + args.options)

finally:
    print('\nDone')
