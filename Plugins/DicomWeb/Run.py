#!/usr/bin/python
# -*- coding: utf-8 -*-


# Orthanc - A Lightweight, RESTful DICOM Store
# Copyright (C) 2012-2016 Sebastien Jodogne, Medical Physics
# Department, University Hospital of Liege, Belgium
# Copyright (C) 2017-2019 Osimis S.A., Belgium
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



# You must add the following to the configuration file:
#
#  "DicomWeb" : {
#    "Servers" : {
#      "sample" : [ "http://localhost:8042/dicom-web/", "alice", "orthanctest" ]
#    }
#  }




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


def UploadAndGetWadoPath(dicom):
    i = UploadInstance(ORTHANC, dicom) ['ID']
    study = DoGet(ORTHANC, '/instances/%s/tags?simplify' % i) ['StudyInstanceUID']
    series = DoGet(ORTHANC, '/instances/%s/tags?simplify' % i) ['SeriesInstanceUID']
    instance = DoGet(ORTHANC, '/instances/%s/tags?simplify' % i) ['SOPInstanceUID']
    return '/studies/%s/series/%s/instances/%s' % (study, series, instance)
    


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

        self.assertEqual(4, len(a))

        # Specific character set
        self.assertTrue('00080005' in a)
        self.assertEqual('CS', a['00080005']['vr'])

        self.assertTrue(a['00081190']['Value'][0].endswith('studies/2.16.840.1.113669.632.20.1211.10000098591'))
        self.assertEqual('UR', a['00081190']['vr'])
        
        self.assertFalse('Value' in a['00081198'])  # No error => empty sequence
        self.assertEqual('SQ', a['00081198']['vr'])

        self.assertEqual(1, len(a['00081199']['Value']))  # 1 success
        self.assertEqual('SQ', a['00081199']['vr'])

        b = a['00081199']['Value'][0]

        # Referenced SOP class UID
        self.assertEqual('UI', b['00081150']['vr'])
        self.assertEqual(1, len(b['00081150']['Value']))
        self.assertEqual('1.2.840.10008.5.1.4.1.1.2', b['00081150']['Value'][0])

        # Referenced SOP instance UID
        self.assertEqual('UI', b['00081155']['vr'])
        self.assertEqual(1, len(b['00081155']['Value']))
        self.assertEqual('1.2.840.113704.7.1.1.6632.1127829031.2', b['00081155']['Value'][0])

        # Retrieve URL
        self.assertEqual('UR', b['00081190']['vr'])
        self.assertEqual(1, len(b['00081190']['Value']))
        self.assertTrue(b['00081190']['Value'][0].
                        endswith('series/1.2.840.113704.1.111.5692.1127828999.2/instances/1.2.840.113704.7.1.1.6632.1127829031.2'))

        # Remove the "http://localhost:8042" prefix
        url = a['00081190']['Value'][0]
        url = re.sub(r'(http|https)://[^/]+(/.*)', r'\2', url)

        # Get the content-length of all the multiparts of this WADO-RS request
        b = DoGet(ORTHANC, url).decode('utf-8', 'ignore')
        parts = re.findall(r'^Content-Length:\s*(\d+)\s*', b, re.IGNORECASE | re.MULTILINE)
        self.assertEqual(1, len(parts))
        self.assertEqual(os.path.getsize(GetDatabasePath('Phenix/IM-0001-0001.dcm')), int(parts[0]))

        
    def test_server_get(self):
        UploadInstance(ORTHANC, 'Knee/T1/IM-0001-0001.dcm')

        self.assertEqual(1, len(DoGet(ORTHANC, '/dicom-web/servers')))
        self.assertTrue('sample' in DoGet(ORTHANC, '/dicom-web/servers'))

        serversReadback = DoGet(ORTHANC, '/dicom-web/servers?expand')
        self.assertEqual('http://localhost:8042/dicom-web/', serversReadback['sample']['Url'])
        self.assertEqual('alice', serversReadback['sample']['Username'])

        sample = DoGet(ORTHANC, '/dicom-web/servers/sample')
        self.assertEqual(5, len(sample))
        self.assertTrue('stow' in sample)
        self.assertTrue('retrieve' in sample)
        self.assertTrue('get' in sample)
        self.assertTrue('wado' in sample)  # New in 0.7
        self.assertTrue('qido' in sample)  # New in 0.7

        # application/dicom+xml
        self.assertEqual(2, len(re.findall('^--', DoGet(ORTHANC, '/dicom-web/studies',
                                                        headers = { 'Accept' : 'application/dicom+xml' }),
                                           re.MULTILINE)))
        self.assertEqual(2, len(re.findall('^--', DoPost
                                           (ORTHANC, '/dicom-web/servers/sample/get',
                                            { 'Uri' : '/studies',
                                              'HttpHeaders' : { 'Accept' : 'application/dicom+xml' }
                                            }), re.MULTILINE)))

        # application/dicom+json
        self.assertEqual(1, len(DoGet(ORTHANC, '/dicom-web/studies',
                                      headers = { 'Accept' : 'application/dicom+json' })))
        self.assertEqual(1, len(DoPost(ORTHANC, '/dicom-web/servers/sample/get',
                                       { 'Uri' : '/studies',
                                         'HttpHeaders' : { 'Accept' : 'application/dicom+json' }})))

        # application/json
        self.assertEqual(1, len(DoGet(ORTHANC, '/dicom-web/studies',
                                      headers = { 'Accept' : 'application/json' })))
        self.assertEqual(1, len(DoPost(ORTHANC, '/dicom-web/servers/sample/get',
                                       { 'Uri' : '/studies',
                                         'HttpHeaders' : { 'Accept' : 'application/json' }})))

        # application/dicom+json is the default as of OrthancDicomWeb-0.5
        self.assertEqual(1, len(DoGet(ORTHANC, '/dicom-web/studies')))
        self.assertEqual(1, len(DoPost(ORTHANC, '/dicom-web/servers/sample/get',
                                       { 'Uri' : '/studies' })))


    def test_server_stow(self):
        UploadInstance(ORTHANC, 'Knee/T1/IM-0001-0001.dcm')

        self.assertRaises(Exception, lambda: 
                          DoPost(ORTHANC, '/dicom-web/servers/sample/stow',
                                 { 'Resources' : [ 'nope' ],
                                   'Synchronous' : True }))  # inexisting resource

        l = 2   # For >= 0.7
        #l = 0   # For <= 0.6
        
        self.assertEqual(l, len(DoPost(ORTHANC, '/dicom-web/servers/sample/stow',
                                       { 'Resources' : [ '0a9b3153-2512774b-2d9580de-1fc3dcf6-3bd83918' ],
                                         'Synchronous' : True })))  # study

        self.assertEqual(l, len(DoPost(ORTHANC, '/dicom-web/servers/sample/stow',
                                       { 'Resources' : [ '6de73705-c4e65c1b-9d9ea1b5-cabcd8e7-f15e4285' ],
                                         'Synchronous' : True })))  # series

        self.assertEqual(l, len(DoPost(ORTHANC, '/dicom-web/servers/sample/stow',
                                       { 'Resources' : [ 'c8df6478-d7794217-0f11c293-a41237c9-31d98357' ],
                                         'Synchronous' : True })))  # instance

        self.assertEqual(l, len(DoPost(ORTHANC, '/dicom-web/servers/sample/stow',
                                       { 'Resources' : [ 
                                           'ca29faea-b6a0e17f-067743a1-8b778011-a48b2a17',
                                           '0a9b3153-2512774b-2d9580de-1fc3dcf6-3bd83918',
                                           '6de73705-c4e65c1b-9d9ea1b5-cabcd8e7-f15e4285',
                                           'c8df6478-d7794217-0f11c293-a41237c9-31d98357' ],
                                         'Synchronous' : True })))  # altogether


    def test_server_retrieve(self):
        COUNT = 'ReceivedInstancesCount'
        #COUNT = 'Instances'  # In version <= 0.6

        UploadInstance(ORTHANC, 'Knee/T1/IM-0001-0001.dcm')
        UploadInstance(ORTHANC, 'Knee/T1/IM-0001-0002.dcm')
        UploadInstance(ORTHANC, 'Knee/T2/IM-0001-0001.dcm')

        self.assertRaises(Exception, lambda: 
                          DoPost(ORTHANC, '/dicom-web/servers/sample/retrieve',
                                 { 'Resources' : [ { 'Study' : 'nope' } ]}))  # inexisting resource

        t = DoPost(ORTHANC, '/dicom-web/servers/sample/retrieve',
                   { 'Resources' : [ { 'Study' : '2.16.840.1.113669.632.20.121711.10000160881' } ] })
        self.assertEqual(3, int(t[COUNT]))

        # Missing "Study" field
        self.assertRaises(Exception, lambda: 
                          DoPost(ORTHANC, '/dicom-web/servers/sample/retrieve',
                                 { 'Resources' : [ { 'Series' : '1.3.46.670589.11.17521.5.0.3124.2008081908564160709' } ]}))

        t = DoPost(ORTHANC, '/dicom-web/servers/sample/retrieve',
                   { 'Resources' : [ { 'Study' : '2.16.840.1.113669.632.20.121711.10000160881',
                                       'Series' : '1.3.46.670589.11.17521.5.0.3124.2008081908564160709' } ] })
        self.assertEqual(2, int(t[COUNT]))

        t = DoPost(ORTHANC, '/dicom-web/servers/sample/retrieve',
                   { 'Resources' : [ { 'Study' : '2.16.840.1.113669.632.20.121711.10000160881',
                                       'Series' : '1.3.46.670589.11.17521.5.0.3124.2008081909090037350' } ] })
        self.assertEqual(1, int(t[COUNT]))

        t = DoPost(ORTHANC, '/dicom-web/servers/sample/retrieve',
                   { 'Resources' : [ { 'Study' : '2.16.840.1.113669.632.20.121711.10000160881',
                                       'Series' : '1.3.46.670589.11.17521.5.0.3124.2008081909090037350' },
                                     { 'Study' : '2.16.840.1.113669.632.20.121711.10000160881',
                                       'Series' : '1.3.46.670589.11.17521.5.0.3124.2008081908564160709' } ] })
        self.assertEqual(3, int(t[COUNT]))

        t = DoPost(ORTHANC, '/dicom-web/servers/sample/retrieve',
                   { 'Resources' : [ { 'Study' : '2.16.840.1.113669.632.20.121711.10000160881',
                                       'Series' : '1.3.46.670589.11.17521.5.0.3124.2008081909090037350',
                                       'Instance' : '1.3.46.670589.11.17521.5.0.3124.2008081909113806560' } ] })
        self.assertEqual(1, int(t[COUNT]))

        
    def test_bitbucket_issue_53(self):
        # DICOMWeb plugin support for "limit" and "offset" parameters in QIDO-RS
        # https://bitbucket.org/sjodogne/orthanc/issues/53
        
        UploadInstance(ORTHANC, 'Brainix/Flair/IM-0001-0001.dcm')
        UploadInstance(ORTHANC, 'Knee/T1/IM-0001-0001.dcm')

        brainix = '2.16.840.1.113669.632.20.1211.10000357775'
        knee = '2.16.840.1.113669.632.20.121711.10000160881'

        a = DoGet(ORTHANC, '/dicom-web/studies',
                  headers = { 'accept' : 'application/json' })
        self.assertEqual(2, len(a))

        b = []
        a = DoGet(ORTHANC, '/dicom-web/studies?limit=1',
                  headers = { 'accept' : 'application/json' })
        self.assertEqual(1, len(a))
        b.append(a[0]['0020000D']['Value'][0])

        a = DoGet(ORTHANC, '/dicom-web/studies?limit=1&offset=1',
                  headers = { 'accept' : 'application/json' })
        self.assertEqual(1, len(a))
        b.append(a[0]['0020000D']['Value'][0])

        self.assertTrue(brainix in b)
        self.assertTrue(knee in b)


    def test_bitbucket_issue_111(self):
        # Wrong serialization of empty values
        # https://bitbucket.org/sjodogne/orthanc/issues/111
        # https://bitbucket.org/sjodogne/orthanc-dicomweb/issues/3/

        # According to the standard, section F.2.5
        # (http://dicom.nema.org/medical/dicom/current/output/chtml/part18/sect_F.2.5.html),
        # null values behave as follows: If an attribute is present in
        # DICOM but empty (i.e., Value Length is 0), it shall be
        # preserved in the DICOM JSON attribute object containing no
        # "Value", "BulkDataURI" or "InlineBinary".
        # https://bitbucket.org/sjodogne/orthanc/issues/111/qido-rs-wrong-serialization-of-empty

        UploadInstance(ORTHANC, 'Issue111.dcm')

        # Test WADO-RS
        a = DoGet(ORTHANC, '/dicom-web/studies/1.2.276.0.7230010.3.1.2.8323329.30185.1551199973.371589/metadata')
        self.assertEqual(1, len(a))
        self.assertTrue('00080050' in a[0])  # AccessionNumber is null
        self.assertEqual(1, len(a[0]['00080050']))  # 'vr' is the only field to be present
        self.assertEqual('SH', a[0]['00080050']['vr'])

        # Test QIDO-RS
        a = DoGet(ORTHANC, '/dicom-web/studies')
        self.assertEqual(1, len(a))
        self.assertTrue('00080050' in a[0])  # AccessionNumber is null
        self.assertEqual(1, len(a[0]['00080050']))  # 'vr' is the only field to be present
        self.assertEqual('SH', a[0]['00080050']['vr'])


    def test_wado_hierarchy(self):
        def CheckJson(uri, headers = {}):
            with open(GetDatabasePath('DummyCT.json'), 'r') as f:
                expected = json.loads(f.read())
                actual = DoGet(ORTHANC, uri, headers)
                self.assertEqual(1, len(actual))
                AssertAlmostEqualRecursive(self, expected, actual[0])

        UploadInstance(ORTHANC, 'DummyCT.dcm')
        study = '1.2.840.113619.2.176.2025.1499492.7391.1171285944.390'
        series = '1.2.840.113619.2.176.2025.1499492.7391.1171285944.394'
        instance = '1.2.840.113619.2.176.2025.1499492.7040.1171286242.109'

        URI = '/dicom-web/studies/%s/series/%s/instances/%s/metadata'
        self.assertRaises(Exception, lambda: DoGet(ORTHANC, URI % (study, series, instance),
                                                   headers = { 'accept' : 'application/nope' }))

        CheckJson(URI % (study, series, instance), headers = { 'accept' : 'application/dicom+json' })
        CheckJson('/dicom-web/studies/%s/series/%s/metadata' % (study, series))
        CheckJson('/dicom-web/studies/%s/metadata' % study)

        self.assertRaises(Exception, lambda: DoGet(ORTHANC, URI % ('nope', series, instance)))
        self.assertRaises(Exception, lambda: DoGet(ORTHANC, URI % (study, 'nope', instance)))
        self.assertRaises(Exception, lambda: DoGet(ORTHANC, URI % (study, series, 'nope')))
        self.assertRaises(Exception, lambda: DoGet(ORTHANC, '/dicom-web/studies/%s/series/%s/metadata' % ('nope', series)))
        self.assertRaises(Exception, lambda: DoGet(ORTHANC, '/dicom-web/studies/%s/series/%s/metadata' % (study, 'nope')))
        self.assertRaises(Exception, lambda: DoGet(ORTHANC, '/dicom-web/studies/%s/metadata' % 'nope'))


    def test_wado_pixel_data(self):
        orthanc = UploadInstance(ORTHANC, 'Issue29.dcm') ['ID']
        a = DoGet(ORTHANC, '/dicom-web/instances')
        self.assertEqual(1, len(a))
        url = a[0]['00081190']['Value'][0]

        prefix = 'http://localhost:8042'
        self.assertTrue(url.startswith(prefix))

        b = DoGet(ORTHANC, url[len(prefix):] + '/metadata')
        self.assertEqual('OB', b[0]['7FE00010']['vr'])
        self.assertEqual(2, len(b[0]['7FE00010']))
        self.assertTrue('BulkDataURI' in b[0]['7FE00010'])

        url = b[0]['7FE00010']['BulkDataURI']
        self.assertTrue(url.startswith(prefix))

        p = DoGetMultipart(ORTHANC, url[len(prefix):])

        self.assertEqual(2, len(p))  # There are 2 fragments in this image
        self.assertEqual(4, len(p[0]))
        self.assertEqual(114486, len(p[1]))

        
    def test_wado_hierarchy_bulk(self):
        def CheckBulk(value, bulk):
            self.assertEqual(2, len(value))
            self.assertTrue('BulkDataURI' in value)
            self.assertTrue('vr' in value)
            self.assertEqual(value['BulkDataURI'], bulk)

        orthanc = UploadInstance(ORTHANC, 'PrivateTags.dcm') ['ID']
        study = '1.2.840.113619.2.115.147416.1094281639.0.29'
        series = '1.2.840.113619.2.115.147416.1094281639.0.30'
        sop = '1.2.840.113619.2.115.147416.1094281639.0.38'

        # WARNING: This test will fail on Orthanc <= 1.5.5, because
        # the following fix is not included yet:
        # https://bitbucket.org/sjodogne/orthanc/commits/b88937ef597b33c4387a546c751827019bcdc205
        
        a = DoGet(ORTHANC, '/dicom-web/studies/%s/metadata' % study)
        self.assertEqual(1, len(a))

        BASE_URI = '/dicom-web/studies/%s/series/%s/instances/%s/bulk' % (study, series, sop)
        BASE_URL = 'http://localhost:8042%s' % BASE_URI

        self.assertEqual(2, len(a[0]['60031010']['Value']))
        CheckBulk(a[0]['60031010']['Value'][0]['60031011'], '%s/60031010/1/60031011' % BASE_URL)
        CheckBulk(a[0]['60031010']['Value'][1]['60031011'], '%s/60031010/2/60031011' % BASE_URL)
        CheckBulk(a[0]['7FE00010'], '%s/7fe00010' % BASE_URL)

        b = DoGetRaw(ORTHANC, '/instances/%s/content/6003-1010/0/6003-1011' % orthanc) [1]
        c = DoGetMultipart(ORTHANC, '%s/60031010/1/60031011' % BASE_URI)

        self.assertEqual(12288, len(b))
        self.assertEqual(1, len(c))
        self.assertEqual(b, c[0])


    def test_bitbucket_issue_112(self):
        # Wrong serialization of number values
        # https://bitbucket.org/sjodogne/orthanc/issues/112
        # https://bitbucket.org/sjodogne/orthanc-dicomweb/issues/4/
        
        UploadInstance(ORTHANC, 'DummyCT.dcm')
        study = '1.2.840.113619.2.176.2025.1499492.7391.1171285944.390'

        # This is the WADO-RS testing
        a = DoGet(ORTHANC, '/dicom-web/studies/%s/metadata' % study)
        self.assertEqual(1, len(a))
        self.assertEqual('IS', a[0]['00180091']['vr'])  # EchoTrainLength

        if (sys.version_info >= (3, 0)):
            types = (int)
        else:
            types = (int, long)
        
        b = a[0]['00180091']['Value'][0]
        self.assertTrue(isinstance(b, types))
        self.assertEqual(10, b)

        # This is the QIDO-RS testing
        a = DoGet(ORTHANC, '/dicom-web/studies')
        self.assertEqual(1, len(a))
        self.assertEqual('IS', a[0]['00201208']['vr'])  # Number of Study Related Instances

        b = a[0]['00201208']['Value'][0]
        self.assertTrue(isinstance(b, types))
        self.assertEqual(1, b)


    def test_bitbucket_issue_113(self):
        # Wrong serialization of PN VR
        # https://bitbucket.org/sjodogne/orthanc/issues/113
        # https://bitbucket.org/sjodogne/orthanc-dicomweb/issues/2/
        
        UploadInstance(ORTHANC, 'Encodings/DavidClunie/SCSX1')
        study = '1.3.6.1.4.1.5962.1.2.0.1175775771.5711.0'

        # This is the WADO-RS testing
        a = DoGet(ORTHANC, '/dicom-web/studies/%s/metadata' % study)
        self.assertEqual(1, len(a))

        pn = a[0]['00100010']  # Patient name
        self.assertEqual('PN', pn['vr'])
        self.assertEqual(1, len(pn['Value']))
        self.assertEqual('Wang^XiaoDong', pn['Value'][0]['Alphabetic'])
        self.assertEqual(u'王^小東', pn['Value'][0]['Ideographic'])

        # This is the QIDO-RS testing
        a = DoGet(ORTHANC, '/dicom-web/studies')
        self.assertEqual(1, len(a))

        pn = a[0]['00100010']  # Patient name
        self.assertEqual('PN', pn['vr'])
        self.assertEqual(1, len(pn['Value']))
        self.assertEqual('Wang^XiaoDong', pn['Value'][0]['Alphabetic'])
        self.assertEqual(u'王^小東', pn['Value'][0]['Ideographic'])


    def test_bitbucket_issue_96(self):
        # WADO-RS RetrieveFrames rejects valid accept headers
        # https://bitbucket.org/sjodogne/orthanc/issues/96
        # https://bitbucket.org/sjodogne/orthanc-dicomweb/issues/5/
        
        UploadInstance(ORTHANC, 'Brainix/Epi/IM-0001-0001.dcm')

        a = DoGet(ORTHANC, '/dicom-web/instances')
        self.assertEqual(1, len(a))
        self.assertEqual(256, a[0]['00280010']['Value'][0]) # Rows
        self.assertEqual(256, a[0]['00280011']['Value'][0]) # Columns
        self.assertEqual(16, a[0]['00280100']['Value'][0])  # Bits allocated

        url = a[0]['00081190']['Value'][0]

        prefix = 'http://localhost:8042'
        self.assertTrue(url.startswith(prefix))
        uri = url[len(prefix):]

        self.assertRaises(Exception, lambda: DoGetMultipart(ORTHANC, '%s/frames/%d' % (uri, 0)))
        self.assertRaises(Exception, lambda: DoGetMultipart(ORTHANC, '%s/frames/%d' % (uri, 2)))

        b = DoGetMultipart(ORTHANC, '%s/frames/%d' % (uri, 1))
        self.assertEqual(1, len(b))
        self.assertEqual(256 * 256 * 2, len(b[0]))
        
        c = DoGetMultipart(ORTHANC, '%s/frames/%d' % (uri, 1),
                           headers = { 'Accept' : 'multipart/related; type=application/octet-stream' })
        self.assertEqual(1, len(c))
        self.assertEqual(b[0], c[0])

        c = DoGetMultipart(ORTHANC, '%s/frames/%d' % (uri, 1),
                           headers = { 'Accept' : 'multipart/related; type="application/octet-stream"' })
        self.assertEqual(1, len(c))
        self.assertEqual(b[0], c[0])

        self.assertRaises(Exception, lambda: DoGetMultipart(ORTHANC, '%s/frames/%d' % (uri, 1),
                                                            headers = { 'Accept' : 'multipart/related; type="nope"' }))

        self.assertRaises(Exception, lambda: DoGetMultipart(ORTHANC, '%s/frames/%d' % (uri, 1),
                                                            headers = { 'Accept' : 'multipart/related; type=nope' }))

        self.assertRaises(Exception, lambda: DoGetMultipart(ORTHANC, '%s/frames/%d' % (uri, 1),
                                                            headers = { 'Accept' : 'nope' }))


    def test_qido_fields(self):
        UploadInstance(ORTHANC, 'DummyCT.dcm')

        a = DoGet(ORTHANC, '/dicom-web/studies')
        self.assertEqual(1, len(a))
        self.assertFalse('00280010' in a[0])   # Rows

        a = DoGet(ORTHANC, '/dicom-web/studies?includefield=Rows')
        self.assertEqual(1, len(a))
        self.assertTrue('00280010' in a[0])
        self.assertEqual(512, a[0]['00280010']['Value'][0])

        a = DoGet(ORTHANC, '/dicom-web/studies?Rows=128')
        self.assertEqual(0, len(a))

        a = DoGet(ORTHANC, '/dicom-web/studies?Rows=512')
        self.assertEqual(1, len(a))
        self.assertTrue('00280010' in a[0])
        self.assertEqual(512, a[0]['00280010']['Value'][0])

        
    def test_stow_errors(self):
        # Pushing an instance to a study that is not its parent
        a = SendStow(ORTHANC, args.dicomweb + '/studies/nope', GetDatabasePath('Phenix/IM-0001-0001.dcm'))
        self.assertEqual(3, len(a))
        self.assertTrue('00080005' in a)
        self.assertEqual('CS', a['00080005']['vr'])
        self.assertTrue('00081198' in a)
        self.assertEqual('SQ', a['00081198']['vr'])
        self.assertEqual(1, len(['00081198']))
        self.assertTrue('00081199' in a)
        self.assertEqual('SQ', a['00081199']['vr'])
        self.assertEqual(1, len(['00081199']))

        # Pushing an instance with missing tags
        a = SendStow(ORTHANC, args.dicomweb + '/studies', GetDatabasePath('Issue111.dcm'))
        self.assertEqual(3, len(a))
        self.assertTrue('00080005' in a)
        self.assertEqual('CS', a['00080005']['vr'])
        self.assertTrue('00081198' in a)
        self.assertEqual('SQ', a['00081198']['vr'])
        self.assertEqual(1, len(['00081198']))
        self.assertTrue('00081199' in a)
        self.assertEqual('SQ', a['00081199']['vr'])
        self.assertEqual(1, len(['00081199']))

        # Pushing a file that is not in the DICOM format
        a = SendStow(ORTHANC, args.dicomweb + '/studies', GetDatabasePath('Issue111.dump'))
        self.assertEqual(3, len(a))
        self.assertTrue('00080005' in a)
        self.assertEqual('CS', a['00080005']['vr'])
        self.assertTrue('00081198' in a)
        self.assertEqual('SQ', a['00081198']['vr'])
        self.assertEqual(1, len(['00081198']))
        self.assertTrue('00081199' in a)
        self.assertEqual('SQ', a['00081199']['vr'])
        self.assertEqual(1, len(['00081199']))


    def test_allowed_methods(self):
        self.assertEqual(0, len(DoGet(ORTHANC, '/dicom-web/studies')))
        
        with self.assertRaises(Exception) as e:
            DoPut(ORTHANC, '/dicom-web/studies')

        self.assertEqual(405, e.exception[0])
        self.assertEqual("GET,POST", e.exception[1]['allow'])
        
        with self.assertRaises(Exception) as e:
            DoDelete(ORTHANC, '/dicom-web/studies')

        self.assertEqual(405, e.exception[0])
        self.assertEqual("GET,POST", e.exception[1]['allow'])


    def test_add_server(self):
        try:
            DoDelete(ORTHANC, '/dicom-web/servers/hello')
        except:
            pass
        
        l = DoGet(ORTHANC, '/dicom-web/servers')
        self.assertEqual(1, len(l))
        self.assertTrue('sample' in l)

        url = 'http://localhost:8042/dicom-web/'
        DoPut(ORTHANC, '/dicom-web/servers/hello', {
            'Url': url,
            'HttpHeaders' : {
                'Hello' : 'World'
            },
            'Username' : 'bob',
            'Password' : 'password',
            'UserProperty' : 'Test',
            'HasDelete' : True,
            })

        l = DoGet(ORTHANC, '/dicom-web/servers')
        self.assertEqual(2, len(l))
        self.assertTrue('sample' in l)        
        self.assertTrue('hello' in l)        

        o = DoGet(ORTHANC, '/dicom-web/servers/sample')
        self.assertEqual(5, len(o))
        self.assertTrue('stow' in o)
        self.assertTrue('retrieve' in o)
        self.assertTrue('get' in o)
        self.assertTrue('wado' in o)  # New in 0.7
        self.assertTrue('qido' in o)  # New in 0.7

        o = DoGet(ORTHANC, '/dicom-web/servers/hello')
        self.assertEqual(6, len(o))
        self.assertTrue('stow' in o)
        self.assertTrue('retrieve' in o)
        self.assertTrue('get' in o)
        self.assertTrue('wado' in o)  # New in 0.7
        self.assertTrue('qido' in o)  # New in 0.7
        self.assertTrue('delete' in o)  # New in 0.7

        s = DoGet(ORTHANC, '/dicom-web/servers?expand')
        self.assertEqual(7, len(s['hello']))
        self.assertEqual(url, s['hello']['Url'])
        self.assertEqual('bob', s['hello']['Username'])
        self.assertEqual(None, s['hello']['Password'])
        self.assertFalse(s['hello']['Pkcs11'])
        self.assertEqual(1, len(s['hello']['HttpHeaders']))
        self.assertTrue('Hello' in s['hello']['HttpHeaders'])
        self.assertEqual('Test', s['hello']['UserProperty'])
        self.assertEqual('1', s['hello']['HasDelete'])
        
        DoDelete(ORTHANC, '/dicom-web/servers/hello')

        
    def test_bitbucket_issue_143(self):
        # WADO-RS metadata request returns "500 Internal Server Error"
        # instead of "404 Not Found" for missing instance
        # https://bitbucket.org/sjodogne/orthanc/issues/143
        UploadInstance(ORTHANC, 'Issue143.dcm')

        try:
            DoGet(ORTHANC, '/dicom-web/studies/1.2.840.113619.2.55.3.671756986.106.1316467036.460/series/1.2.840.113619.2.55.3.671756986.106.1316467036.465/instances/0.0.0.0.0/metadata')
            self.assertFail()
        except Exception as e:
            self.assertEqual(404, e[0])
        
        DoGet(ORTHANC, '/dicom-web/studies/1.3.6.1.4.1.34261.90254037371867.41912.1553085024.2/series/1.3.6.1.4.1.34261.90254037371867.41912.1553085024.3/instances/1.2.276.0.7230010.3.1.4.253549293.36648.1555586123.754/metadata')

        try:
            DoGet(ORTHANC, '/dicom-web/studies/0.0.0.0.0/series/1.3.6.1.4.1.34261.90254037371867.41912.1553085024.3/instances/1.2.276.0.7230010.3.1.4.253549293.36648.1555586123.754/metadata')
            self.fail()
        except Exception as e:
            self.assertEqual(404, e[0])

        try:
            DoGet(ORTHANC, '/dicom-web/studies/1.3.6.1.4.1.34261.90254037371867.41912.1553085024.2/series/0.0.0.0.0/instances/1.2.276.0.7230010.3.1.4.253549293.36648.1555586123.754/metadata')
            self.assertFail()
        except Exception as e:
            self.assertEqual(404, e[0])

        try:
            DoGet(ORTHANC, '/dicom-web/studies/0.0.0.0.0/series/0.0.0.0.0/instances/0.0.0.0.0/metadata')
            self.assertFail()
        except Exception as e:
            self.assertEqual(404, e[0])


    def test_encodings_qido(self):
        # The "DefaultEncoding" condifuration option is set to "UTF8"
        # in the integration tests, so all the QIDO-RS requests must
        # lead to a "ISO_IR 192" specific character set
        def GetPatientName(dicom, onlyAlphabetic):
            i = UploadInstance(ORTHANC, dicom) ['ID']
            j = DoGet(ORTHANC, '/instances/%s/tags?simplify' % i) ['StudyInstanceUID']
            qido = DoGet(ORTHANC, '/dicom-web/studies?0020000D=%s' % j)
            self.assertEqual(1, len(qido))
            self.assertEqual('CS', qido[0]['00080005']['vr'])
            self.assertEqual('ISO_IR 192', qido[0]['00080005']['Value'][0])
            if onlyAlphabetic:
                self.assertEqual(1, len(qido[0]['00100010']['Value'][0]))
            else:
                self.assertEqual(3, len(qido[0]['00100010']['Value'][0]))
            return qido[0]['00100010']['Value'][0]

        # Check out "test_issue_95_encodings" in "../../Tests/Tests.py"

        self.assertEqual(u'Buc^Jérôme', GetPatientName('Encodings/DavidClunie/SCSFREN', True) ['Alphabetic'])
        self.assertEqual(u'Äneas^Rüdiger', GetPatientName('Encodings/DavidClunie/SCSGERM', True)['Alphabetic'])
        self.assertEqual(u'Διονυσιος', GetPatientName('Encodings/DavidClunie/SCSGREEK', True)['Alphabetic'])
        self.assertEqual(u'Люкceмбypг', GetPatientName('Encodings/DavidClunie/SCSRUSS', True)['Alphabetic'])
        self.assertEqual(u'שרון^דבורה', GetPatientName('Encodings/DavidClunie/SCSHBRW', True)['Alphabetic'])
        self.assertEqual(u'قباني^لنزار', GetPatientName('Encodings/DavidClunie/SCSARAB', True)['Alphabetic'])

        self.assertEqual(u'Hong^Gildong', GetPatientName('Encodings/DavidClunie/SCSI2', False)['Alphabetic'])
        self.assertEqual(u'洪^吉洞', GetPatientName('Encodings/DavidClunie/SCSI2', False)['Ideographic'])
        self.assertEqual(u'홍^길동', GetPatientName('Encodings/DavidClunie/SCSI2', False)['Phonetic'])
        self.assertEqual(u'Wang^XiaoDong', GetPatientName('Encodings/DavidClunie/SCSX2', False)['Alphabetic'])
        self.assertEqual(u'王^小东', GetPatientName('Encodings/DavidClunie/SCSX2', False)['Ideographic'])
        self.assertEqual(u'', GetPatientName('Encodings/DavidClunie/SCSX2', False)['Phonetic'])
        self.assertEqual(u'Wang^XiaoDong', GetPatientName('Encodings/DavidClunie/SCSX1', False)['Alphabetic'])
        self.assertEqual(u'王^小東', GetPatientName('Encodings/DavidClunie/SCSX1', False)['Ideographic'])
        self.assertEqual(u'', GetPatientName('Encodings/DavidClunie/SCSX1', False)['Phonetic'])
        self.assertEqual(u'Yamada^Tarou', GetPatientName('Encodings/DavidClunie/SCSH31', False)['Alphabetic'])
        self.assertEqual(u'山田^太郎', GetPatientName('Encodings/DavidClunie/SCSH31', False)['Ideographic'])
        self.assertEqual(u'やまだ^たろう', GetPatientName('Encodings/DavidClunie/SCSH31', False)['Phonetic'])
        self.assertEqual(u'ﾔﾏﾀﾞ^ﾀﾛｳ', GetPatientName('Encodings/DavidClunie/SCSH32', False)['Alphabetic'])

        # TODO - Not supported yet by the Orthanc core as of 1.5.7
        #self.assertEqual(u'山田^太郎', GetPatientName('Encodings/DavidClunie/SCSH32')['Ideographic'])
        #self.assertEqual(u'やまだ^たろう', GetPatientName('Encodings/DavidClunie/SCSH32')['Phonetic'])


    def test_encodings_wado_metadata(self):
        # If querying the instance metadata, the "DefaultEncoding"
        # configuration is not used, but the actual encoding
        def GetEncoding(dicom, length):
            qido = DoGet(ORTHANC, '/dicom-web/%s/metadata' % UploadAndGetWadoPath(dicom))
            self.assertEqual(1, len(qido))
            self.assertEqual(length, len(qido[0]['00080005']['Value']))
            self.assertEqual('CS', qido[0]['00080005']['vr'])
            return qido[0]['00080005']['Value']

        self.assertEqual('ISO_IR 100', GetEncoding('Encodings/DavidClunie/SCSFREN', 1)[0])
        self.assertEqual('ISO_IR 100', GetEncoding('Encodings/DavidClunie/SCSGERM', 1)[0])
        self.assertEqual('ISO_IR 126', GetEncoding('Encodings/DavidClunie/SCSGREEK', 1)[0])
        self.assertEqual('ISO_IR 144', GetEncoding('Encodings/DavidClunie/SCSRUSS', 1)[0])
        self.assertEqual('ISO_IR 138', GetEncoding('Encodings/DavidClunie/SCSHBRW', 1)[0])
        self.assertEqual('ISO_IR 127', GetEncoding('Encodings/DavidClunie/SCSARAB', 1)[0])
        self.assertEqual('ISO 2022 IR 149', GetEncoding('Encodings/DavidClunie/SCSI2', 1)[0])
        self.assertEqual('GB18030', GetEncoding('Encodings/DavidClunie/SCSX2', 1)[0])
        self.assertEqual('ISO_IR 192', GetEncoding('Encodings/DavidClunie/SCSX1', 1)[0])
        self.assertEqual('ISO 2022 IR 87', GetEncoding('Encodings/DavidClunie/SCSH31', 1)[0])
        self.assertEqual('ISO 2022 IR 13', GetEncoding('Encodings/DavidClunie/SCSH32', 2)[0])
        self.assertEqual('ISO 2022 IR 87', GetEncoding('Encodings/DavidClunie/SCSH32', 2)[1])


    def test_rendered(self):
        def RenderFrame(path, i):
            return DoPost(ORTHANC, '/dicom-web/servers/sample/get', {
                'Uri' : '%s/frames/%d/rendered' % (path, i)
            })

        # This image has 76 frames
        path = UploadAndGetWadoPath('Multiframe.dcm')

        self.assertRaises(Exception, lambda: RenderFrame(path, 0))

        frame1 = RenderFrame(path, 1)        
        im = UncompressImage(frame1)
        self.assertEqual("L", im.mode)
        self.assertEqual(512, im.size[0])
        self.assertEqual(512, im.size[1])

        im = UncompressImage(RenderFrame(path, 76))
        self.assertEqual("L", im.mode)
        self.assertEqual(512, im.size[0])
        self.assertEqual(512, im.size[1])

        self.assertRaises(Exception, lambda: RenderFrame(path, 77))

        defaultFrame = DoPost(ORTHANC, '/dicom-web/servers/sample/get', {
            'Uri' : '%s/rendered' % path
        })

        self.assertEqual(len(frame1), len(defaultFrame))
        self.assertEqual(frame1, defaultFrame)


        # This image has 1 frame
        path = UploadAndGetWadoPath('Phenix/IM-0001-0001.dcm')

        self.assertRaises(Exception, lambda: RenderFrame(path, 0))
        self.assertRaises(Exception, lambda: RenderFrame(path, 2))

        frame1 = RenderFrame(path, 1)
        im = UncompressImage(frame1)
        self.assertEqual("L", im.mode)
        self.assertEqual(512, im.size[0])
        self.assertEqual(358, im.size[1])

        defaultFrame = DoPost(ORTHANC, '/dicom-web/servers/sample/get', {
            'Uri' : '%s/rendered' % path
        })

        self.assertEqual(len(frame1), len(defaultFrame))
        self.assertEqual(frame1, defaultFrame)
        
        
try:
    print('\nStarting the tests...')
    unittest.main(argv = [ sys.argv[0] ] + args.options)

finally:
    print('\nDone')
