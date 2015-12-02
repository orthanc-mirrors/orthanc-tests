#!/usr/bin/env python
# -*- coding: utf-8 -*-


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


import tempfile
import unittest
import base64

from PIL import ImageChops
from Toolbox import *
from xml.dom import minidom

_LOCAL = None
_REMOTE = None


def SetOrthancParameters(local, remote):
    global _LOCAL, _REMOTE
    _LOCAL = local
    _REMOTE = remote


def ExtractDicomTags(rawDicom, tags):
    with tempfile.NamedTemporaryFile(delete = True) as f:
        f.write(rawDicom)
        f.flush()
        data = subprocess.check_output([ FindExecutable('dcm2xml'), f.name ])

    result = []
    for tag in tags:
        match = re.search('<element[^>]+name="%s">([^>]*)</element>' % tag, data)
        if match == None:
            result.append('')
        else:
            result.append(match.group(1))

    return result


def InstallLuaScript(path):
    with open(GetDatabasePath(path), 'r') as f:
        DoPost(_REMOTE, '/tools/execute-script', f.read(), 'application/lua')
    

def UninstallLuaCallbacks():
    DoPost(_REMOTE, '/tools/execute-script', 'function OnStoredInstance() end', 'application/lua')
    InstallLuaScript('Lua/TransferSyntaxEnable.lua')


def CompareLists(a, b):
    if len(a) != len(b):
        return False

    for i in range(len(a)):
        d = a[i] - b[i]
        if abs(d) >= 0.51:  # Add some tolerance for rounding errors
            return False

    return True


def CallMoveScu(args):
    subprocess.check_call([ FindExecutable('movescu'), 
                            '--move', _LOCAL['DicomAet'],      # Target AET (i.e. storescp)
                            '--call', _REMOTE['DicomAet'],     # Called AET (i.e. Orthanc)
                            '--aetitle', _LOCAL['DicomAet'],   # Calling AET (i.e. storescp)
                            _REMOTE['Server'], str(_REMOTE['DicomPort'])  ] + args,
                          stderr=subprocess.PIPE)



def GenerateTestSequence():
    return [
        {
            'StudyDescription': 'Hello^',
            'ReferencedStudySequence' : [
                {
                    'StudyDescription': 'Toto',
                    },
                {
                    'StudyDescription': 'Tata',
                    },
                ]
            },
        {
            'StudyDescription': 'Sébastien^',
            'StudyDate' : '19700202',
            }
        ]




class Orthanc(unittest.TestCase):
    def setUp(self):
        DropOrthanc(_LOCAL)
        DropOrthanc(_REMOTE)
        UninstallLuaCallbacks()
        #print "In test", self._testMethodName
        
    def AssertSameImages(self, truth, url):
        im = GetImage(_REMOTE, url)
        self.assertTrue(CompareLists(truth, im.getdata()))


    def test_system(self):
        self.assertTrue('Version' in DoGet(_REMOTE, '/system'))
        self.assertEqual('0', DoGet(_REMOTE, '/statistics')['TotalDiskSize'])
        self.assertEqual('0', DoGet(_REMOTE, '/statistics')['TotalUncompressedSize'])

    def test_upload(self):
        u = UploadInstance(_REMOTE, 'DummyCT.dcm')
        self.assertEqual('Success', u['Status'])
        u = UploadInstance(_REMOTE, 'DummyCT.dcm')
        self.assertEqual('AlreadyStored', u['Status'])
        self.assertEqual(1, len(DoGet(_REMOTE, '/patients')))
        self.assertEqual(1, len(DoGet(_REMOTE, '/studies')))
        self.assertEqual(1, len(DoGet(_REMOTE, '/series')))
        self.assertEqual(1, len(DoGet(_REMOTE, '/instances')))

        i = DoGet(_REMOTE, '/instances/%s/simplified-tags' % u['ID'])
        self.assertEqual('20070101', i['StudyDate'])


    def test_upload_2(self):
        i = UploadInstance(_REMOTE, 'DummyCT.dcm')['ID']
        instance = DoGet(_REMOTE, '/instances/%s' % i)
        self.assertEqual(i, instance['ID'])
        self.assertEqual('1.2.840.113619.2.176.2025.1499492.7040.1171286242.109',
                         instance['MainDicomTags']['SOPInstanceUID'])

        series = DoGet(_REMOTE, '/series/%s' % instance['ParentSeries'])
        self.assertEqual('1.2.840.113619.2.176.2025.1499492.7391.1171285944.394', 
                         series['MainDicomTags']['SeriesInstanceUID'])

        study = DoGet(_REMOTE, '/studies/%s' % series['ParentStudy'])
        self.assertEqual('1.2.840.113619.2.176.2025.1499492.7391.1171285944.390',
                         study['MainDicomTags']['StudyInstanceUID'])

        patient = DoGet(_REMOTE, '/patients/%s' % study['ParentPatient'])
        self.assertEqual('ozp00SjY2xG',
                         patient['MainDicomTags']['PatientID'])

        dicom = DoGet(_REMOTE, '/instances/%s/file' % instance['ID'])
        self.assertEqual(2472, len(dicom))
        self.assertEqual('3e29b869978b6db4886355a2b1132124', ComputeMD5(dicom))
        self.assertEqual(1, len(DoGet(_REMOTE, '/instances/%s/frames' % i)))
        self.assertEqual('TWINOW', DoGet(_REMOTE, '/instances/%s/simplified-tags' % i)['StationName'])
        self.assertEqual('TWINOW', DoGet(_REMOTE, '/instances/%s/tags' % i)['0008,1010']['Value'])


    def test_images(self):
        i = UploadInstance(_REMOTE, 'Phenix/IM-0001-0001.dcm')['ID']
        self.assertEqual(1, len(DoGet(_REMOTE, '/instances/%s/frames' % i)))

        im = GetImage(_REMOTE, '/instances/%s/preview' % i)
        self.assertEqual("L", im.mode)
        self.assertEqual(512, im.size[0])
        self.assertEqual(358, im.size[1])

        im = GetImage(_REMOTE, '/instances/%s/image-uint8' % i)
        self.assertEqual("L", im.mode)
        self.assertEqual(512, im.size[0])
        self.assertEqual(358, im.size[1])

        im = GetImage(_REMOTE, '/instances/%s/image-uint16' % i)
        self.assertEqual(512, im.size[0])
        self.assertEqual(358, im.size[1])

        im = GetImage(_REMOTE, '/instances/%s/frames/0/preview' % i)
        self.assertEqual("L", im.mode)
        self.assertEqual(512, im.size[0])
        self.assertEqual(358, im.size[1])

        im = GetImage(_REMOTE, '/instances/%s/frames/0/image-uint8' % i)
        self.assertEqual("L", im.mode)
        self.assertEqual(512, im.size[0])
        self.assertEqual(358, im.size[1])

        im = GetImage(_REMOTE, '/instances/%s/frames/0/image-uint16' % i)
        self.assertEqual(512, im.size[0])
        self.assertEqual(358, im.size[1])

        # This is Little Endian Explicit
        self.assertEqual('1.2.840.10008.1.2.1', DoGet(_REMOTE, '/instances/%s/header?simplify' % i)['TransferSyntaxUID'])


    def test_hierarchy(self):
        UploadFolder(_REMOTE, 'Brainix/Epi')
        UploadFolder(_REMOTE, 'Brainix/Flair')
        UploadFolder(_REMOTE, 'Knee/T1')
        UploadFolder(_REMOTE, 'Knee/T2')

        p = DoGet(_REMOTE, '/patients')
        s = DoGet(_REMOTE, '/studies')
        t = DoGet(_REMOTE, '/series')
        self.assertEqual(2, len(p))
        self.assertEqual(2, len(s))
        self.assertEqual(4, len(t))
        self.assertEqual(94, len(DoGet(_REMOTE, '/instances')))

        brainixPatient = '16738bc3-e47ed42a-43ce044c-a3414a45-cb069bd0'
        brainixStudy = '27f7126f-4f66fb14-03f4081b-f9341db2-53925988'
        brainixEpi = '2ac1316d-3e432022-62eabff2-c59f5475-9b1ac3f8'
        brainixFlair = '1e2c125c-411b8e86-3f4fe68e-a7584dd3-c6da78f0'

        kneePatient = 'ca29faea-b6a0e17f-067743a1-8b778011-a48b2a17'
        kneeStudy = '0a9b3153-2512774b-2d9580de-1fc3dcf6-3bd83918'
        kneeT1 = '6de73705-c4e65c1b-9d9ea1b5-cabcd8e7-f15e4285'
        kneeT2 = 'bbf7a453-0d34251a-03663b55-46bb31b9-ffd74c59'

        self.assertTrue(brainixPatient in p)
        self.assertTrue(kneePatient in p)
        self.assertTrue(brainixStudy in s)
        self.assertTrue(kneeStudy in s)
        self.assertTrue(brainixEpi in t)
        self.assertTrue(brainixFlair in t)
        self.assertTrue(kneeT1 in t)
        self.assertTrue(kneeT2 in t)

        self.assertEqual(44, len(DoGet(_REMOTE, '/patients/%s/instances' % brainixPatient)))
        self.assertEqual(2, len(DoGet(_REMOTE, '/patients/%s/series' % brainixPatient)))
        self.assertEqual(1, len(DoGet(_REMOTE, '/patients/%s/studies' % brainixPatient)))

        self.assertEqual(50, len(DoGet(_REMOTE, '/patients/%s/instances' % kneePatient)))
        self.assertEqual(2, len(DoGet(_REMOTE, '/patients/%s/series' % kneePatient)))
        self.assertEqual(1, len(DoGet(_REMOTE, '/patients/%s/studies' % kneePatient)))

        self.assertEqual(2, len(DoGet(_REMOTE, '/studies/%s/series' % brainixStudy)))
        self.assertEqual(44, len(DoGet(_REMOTE, '/studies/%s/instances' % brainixStudy)))

        self.assertEqual(2, len(DoGet(_REMOTE, '/studies/%s/series' % kneeStudy)))
        self.assertEqual(50, len(DoGet(_REMOTE, '/studies/%s/instances' % kneeStudy)))

        self.assertEqual(22, len(DoGet(_REMOTE, '/series/%s/instances' % brainixEpi)))
        self.assertEqual(22, len(DoGet(_REMOTE, '/series/%s/instances' % brainixFlair)))
        self.assertEqual(24, len(DoGet(_REMOTE, '/series/%s/instances' % kneeT1)))
        self.assertEqual(26, len(DoGet(_REMOTE, '/series/%s/instances' % kneeT2)))

        for patient in p:
            for study in DoGet(_REMOTE, '/patients/%s/studies' % patient):
                self.assertEqual(patient, study['ParentPatient'])
                for series in DoGet(_REMOTE, '/studies/%s/series' % study['ID']):
                    self.assertEqual(study['ID'], series['ParentStudy'])
                    for instance in DoGet(_REMOTE, '/series/%s/instances' % series['ID']):
                        self.assertEqual(series['ID'], instance['ParentSeries'])

                        self.assertEqual(json.dumps(DoGet(_REMOTE, '/instances/%s/attachments/dicom-as-json/data' % instance['ID'])),
                                         json.dumps(DoGet(_REMOTE, '/instances/%s/tags' % instance['ID'])))


        r = DoDelete(_REMOTE, "/studies/%s" % brainixStudy)['RemainingAncestor']
        self.assertEqual(1, len(DoGet(_REMOTE, '/patients')))
        self.assertEqual(1, len(DoGet(_REMOTE, '/studies')))
        self.assertEqual(2, len(DoGet(_REMOTE, '/series')))
        self.assertEqual(50, len(DoGet(_REMOTE, '/instances')))
        self.assertEqual(None, r)

        r = DoDelete(_REMOTE, "/series/%s" % kneeT2)['RemainingAncestor']
        self.assertEqual(1, len(DoGet(_REMOTE, '/patients')))
        self.assertEqual(1, len(DoGet(_REMOTE, '/studies')))
        self.assertEqual(1, len(DoGet(_REMOTE, '/series')))
        self.assertEqual(24, len(DoGet(_REMOTE, '/instances')))
        self.assertEqual('Study', r['Type'])
        self.assertEqual(kneeStudy, r['ID'])

        r = DoDelete(_REMOTE, "/instances/%s" % DoGet(_REMOTE, '/instances')[0])['RemainingAncestor']
        self.assertEqual(1, len(DoGet(_REMOTE, '/patients')))
        self.assertEqual(1, len(DoGet(_REMOTE, '/studies')))
        self.assertEqual(1, len(DoGet(_REMOTE, '/series')))
        self.assertEqual(23, len(DoGet(_REMOTE, '/instances')))
        self.assertEqual('Series', r['Type'])
        self.assertEqual(kneeT1, r['ID'])

        r = DoDelete(_REMOTE, "/patients/%s" % kneePatient)['RemainingAncestor']
        self.assertEqual(0, len(DoGet(_REMOTE, '/patients')))
        self.assertEqual(0, len(DoGet(_REMOTE, '/studies')))
        self.assertEqual(0, len(DoGet(_REMOTE, '/series')))
        self.assertEqual(0, len(DoGet(_REMOTE, '/instances')))
        self.assertEqual(None, r)

        DropOrthanc(_REMOTE)
        self.assertEqual('0', DoGet(_REMOTE, '/statistics')['TotalDiskSize'])
        self.assertEqual('0', DoGet(_REMOTE, '/statistics')['TotalUncompressedSize'])


    def test_multiframe(self):
        i = UploadInstance(_REMOTE, 'Multiframe.dcm')['ID']
        self.assertEqual(76, len(DoGet(_REMOTE, '/instances/%s/frames' % i)))

        im = GetImage(_REMOTE, '/instances/%s/frames/0/preview' % i)
        self.assertEqual("L", im.mode)
        self.assertEqual(512, im.size[0])
        self.assertEqual(512, im.size[1])
  
        DoGet(_REMOTE, '/instances/%s/frames/0/image-uint8' % i)
        DoGet(_REMOTE, '/instances/%s/frames/0/image-uint16' % i)
        DoGet(_REMOTE, '/instances/%s/frames/75/preview' % i)
        self.assertRaises(Exception, lambda: DoGet(_REMOTE, '/instances/%s/frames/aaa/preview' % i))
        self.assertRaises(Exception, lambda: DoGet(_REMOTE, '/instances/%s/frames/76/preview' % i))


    def test_changes(self):
        # Check emptiness
        c = DoGet(_REMOTE, '/changes')
        self.assertEqual(0, len(c['Changes']))
        self.assertEqual(0, c['Last'])
        self.assertTrue(c['Done'])
        c = DoGet(_REMOTE, '/changes?last')
        self.assertEqual(0, len(c['Changes']))
        self.assertEqual(0, c['Last'])
        self.assertTrue(c['Done'])

        # Add 1 instance
        i = UploadInstance(_REMOTE, 'Brainix/Flair/IM-0001-0001.dcm')['ID']
        c = DoGet(_REMOTE, '/changes')
        begin = c['Last']
        self.assertEqual(4, len(c['Changes']))
        self.assertTrue(c['Done'])
        self.assertEqual(c['Changes'][-1]['Seq'], c['Last'])

        c = DoGet(_REMOTE, '/changes?last')
        self.assertEqual(1, len(c['Changes']))
        self.assertEqual(begin, c['Last'])
        self.assertTrue(c['Done'])
        c = DoGet(_REMOTE, '/changes?limit=1&since=' + str(begin - 1))
        self.assertEqual(1, len(c['Changes']))
        self.assertEqual(begin, c['Last'])
        self.assertTrue(c['Done'])
        c = DoGet(_REMOTE, '/changes?limit=1&since=' + str(begin - 2))
        self.assertEqual(1, len(c['Changes']))
        self.assertEqual(begin - 1, c['Last'])
        self.assertFalse(c['Done'])
        c = DoGet(_REMOTE, '/changes?limit=1&since=' + str(begin - 3))
        self.assertEqual(1, len(c['Changes']))
        self.assertEqual(begin - 2, c['Last'])
        self.assertFalse(c['Done'])

        UploadFolder(_REMOTE, 'Knee/T1')
        UploadFolder(_REMOTE, 'Knee/T2')
        since = begin
        countPatients = 0
        countStudies = 0
        countSeries = 0
        countInstances = 0
        completed = 0
        while True:
            c = DoGet(_REMOTE, '/changes', { 'since' : since, 'limit' : 3 })
            since = c['Last']
            for i in c['Changes']:
                if i['ResourceType'] == 'Instance':
                    countInstances += 1
                if i['ResourceType'] == 'Patient':
                    countPatients += 1
                if i['ResourceType'] == 'Study':
                    countStudies += 1
                if i['ResourceType'] == 'Series':
                    countSeries += 1
                if i['ChangeType'] == 'NewInstance':
                    countInstances += 1
                if i['ChangeType'] == 'NewPatient':
                    countPatients += 1
                if i['ChangeType'] == 'NewStudy':
                    countStudies += 1
                if i['ChangeType'] == 'NewSeries':
                    countSeries += 1
                if i['ChangeType'] == 'CompletedSeries':
                    completed += 1
                self.assertTrue('ID' in i)
                self.assertTrue('Path' in i)
                self.assertTrue('Seq' in i)
            if c['Done']:
                break

        self.assertEqual(2 * 50, countInstances)
        self.assertEqual(2 * 1, countPatients)
        self.assertEqual(2 * 1, countStudies)
        self.assertEqual(2 * 2, countSeries)
        self.assertEqual(0, completed)


    def test_archive(self):
        UploadInstance(_REMOTE, 'Knee/T1/IM-0001-0001.dcm')
        UploadInstance(_REMOTE, 'Knee/T2/IM-0001-0001.dcm')

        z = GetArchive(_REMOTE, '/patients/%s/archive' % DoGet(_REMOTE, '/patients')[0])
        self.assertEqual(2, len(z.namelist()))

        z = GetArchive(_REMOTE, '/studies/%s/archive' % DoGet(_REMOTE, '/studies')[0])
        self.assertEqual(2, len(z.namelist()))

        z = GetArchive(_REMOTE, '/series/%s/archive' % DoGet(_REMOTE, '/series')[0])
        self.assertEqual(1, len(z.namelist()))

        UploadInstance(_REMOTE, 'Brainix/Flair/IM-0001-0001.dcm')

        z = GetArchive(_REMOTE, '/patients/%s/archive' % DoGet(_REMOTE, '/patients')[0])
        self.assertEqual(2, len(z.namelist()))
        

    def test_media_archive(self):
        UploadInstance(_REMOTE, 'Knee/T1/IM-0001-0001.dcm')
        UploadInstance(_REMOTE, 'Knee/T2/IM-0001-0001.dcm')

        z = GetArchive(_REMOTE, '/patients/%s/media' % DoGet(_REMOTE, '/patients')[0])
        self.assertEqual(3, len(z.namelist()))
        self.assertTrue('IMAGES/IM0' in z.namelist())
        self.assertTrue('IMAGES/IM1' in z.namelist())
        self.assertTrue('DICOMDIR' in z.namelist())

        try:
            os.remove('/tmp/DICOMDIR')
        except:
            # The file does not exist
            pass

        z.extract('DICOMDIR', '/tmp')
        a = subprocess.check_output([ FindExecutable('dciodvfy'), '/tmp/DICOMDIR' ],
                                    stderr = subprocess.STDOUT).split('\n')
        self.assertEqual(3, len(a))
        self.assertTrue(a[0].startswith('Warning'))
        self.assertEqual('BasicDirectory', a[1])
        self.assertEqual('', a[2])

        a = subprocess.check_output([ FindExecutable('dcentvfy'), '/tmp/DICOMDIR' ],
                                    stderr = subprocess.STDOUT).split('\n')
        self.assertEqual(1, len(a))
        self.assertEqual('', a[0])

        a = subprocess.check_output([ FindExecutable('dcm2xml'), '/tmp/DICOMDIR' ])
        self.assertTrue(re.search('1.3.46.670589.11.17521.5.0.3124.2008081908590448738', a) != None)
        self.assertTrue(re.search('1.3.46.670589.11.17521.5.0.3124.2008081909113806560', a) != None)

        os.remove('/tmp/DICOMDIR')


    def test_protection(self):
        UploadInstance(_REMOTE, 'Knee/T1/IM-0001-0001.dcm')
        UploadInstance(_REMOTE, 'Brainix/Flair/IM-0001-0001.dcm')
        self.assertEqual(2, len(DoGet(_REMOTE, '/patients')))
        a = DoGet(_REMOTE, '/patients')[0]
        b = DoGet(_REMOTE, '/patients')[1]
        self.assertEqual(0, DoGet(_REMOTE, '/patients/%s/protected' % a))
        DoPut(_REMOTE, '/patients/%s/protected' % a, '0', 'text/plain')
        self.assertEqual(0, DoGet(_REMOTE, '/patients/%s/protected' % a))
        DoPut(_REMOTE, '/patients/%s/protected' % a, '1', 'text/plain')
        self.assertEqual(1, DoGet(_REMOTE, '/patients/%s/protected' % a))
        DoPut(_REMOTE, '/patients/%s/protected' % a, '0', 'text/plain')
        self.assertEqual(0, DoGet(_REMOTE, '/patients/%s/protected' % a))


    def test_raw_tags(self):
        i = UploadInstance(_REMOTE, 'PrivateTags.dcm')['ID']

        dicom = DoGet(_REMOTE, '/instances/%s/file' % i)
        self.assertEqual('1a7c56cb02d6e742cc9c856a8ac182e3', ComputeMD5(dicom))

        s = '/instances/%s/content/' % i

        self.assertEqual('LOGIQBOOK', DoGet(_REMOTE, s + '0008-1010').strip())
        self.assertRaises(Exception, lambda: DoGet(_REMOTE, s + '0008-1011'))

        self.assertEqual('Abdomen', DoGet(_REMOTE, s + '7fe1-1001/0/7fe1-1008/0/7fe1-1057').strip())
        self.assertEqual('cla_3c', DoGet(_REMOTE, s + '7fe1-1001/0/7fe1-1008/8/7fe1-1057').strip())

        UploadInstance(_REMOTE, 'Brainix/Epi/IM-0001-0001.dcm')
        UploadInstance(_REMOTE, 'Brainix/Flair/IM-0001-0001.dcm')
        UploadInstance(_REMOTE, 'Knee/T1/IM-0001-0001.dcm')
        UploadInstance(_REMOTE, 'Knee/T2/IM-0001-0001.dcm')

        for i in DoGet(_REMOTE, '/instances'):
            aid = DoGet(_REMOTE, '/instances/%s' % i)['MainDicomTags']['SOPInstanceUID']
            self.assertEqual(aid, DoGet(_REMOTE, '/instances/%s/content/0008-0018' % i).replace(chr(0), ''))


    def test_raw_tags_mdn(self):
        # Bug reported by Cyril Paulus
        i = UploadInstance(_REMOTE, 'PrivateMDNTags.dcm')['ID']
        self.assertAlmostEqual(0.000027, DoGet(_REMOTE, '/instances/%s/content/7053-1000' % i))


    def test_modify_instance(self):
        i = UploadInstance(_REMOTE, 'PrivateTags.dcm')['ID']
        modified = DoPost(_REMOTE, '/instances/%s/modify' % i,
                          json.dumps({
                    "Replace" : {
                        "PatientName" : "hello",
                        #"PatientID" : "world"
                        },
                    "Remove" : [ "StationName" ],
                    "RemovePrivateTags" : None
                    }),
                          'application/json')
        j = DoPost(_REMOTE, '/instances', modified, 'application/dicom')['ID']

        self.assertNotEqual('hello', DoGet(_REMOTE, '/instances/%s/content/0010-0010' % i).strip())
        #self.assertNotEqual('world', DoGet(_REMOTE, '/instances/%s/content/0010-0020' % i).strip())
        self.assertEqual('LOGIQBOOK', DoGet(_REMOTE, '/instances/%s/content/0008-1010' % i).strip())        
        DoGet(_REMOTE, '/instances/%s/content/6003-1010' % i)  # Some private tag

        self.assertEqual('hello', DoGet(_REMOTE, '/instances/%s/content/0010-0010' % j).strip())
        #self.assertEqual('world', DoGet(_REMOTE, '/instances/%s/content/0010-0020' % j).strip())
        self.assertRaises(Exception, lambda: DoGet(_REMOTE, '/instances/%s/content/0008-1010' % j))
        self.assertRaises(Exception, lambda: DoGet(_REMOTE, '/instances/%s/content/6003-1010' % j))


    def test_modify_series(self):
        # Upload 4 images from the same series
        for i in range(4):
            UploadInstance(_REMOTE, 'Brainix/Epi/IM-0001-000%d.dcm' % (i + 1))

        origSeries = DoGet(_REMOTE, '/series')[0]
        newSeries = DoPost(_REMOTE, '/series/%s/modify' % origSeries,
                           '{"Replace":{"PatientName":"Jodogne"}}',
                           'application/json')['ID']

        self.assertEqual(origSeries, DoGet(_REMOTE, '/series/%s' % newSeries)['ModifiedFrom'])
        instances = DoGet(_REMOTE, '/series/%s' % newSeries)['Instances']
        self.assertEqual(4, len(instances))
        for i in instances:
            j = DoGet(_REMOTE, '/instances/%s' % i)['ModifiedFrom']
            self.assertEqual(newSeries, DoGet(_REMOTE, '/instances/%s' % i)['ParentSeries'])
            self.assertEqual(origSeries, DoGet(_REMOTE, '/instances/%s' % j)['ParentSeries'])

            self.assertEqual('Jodogne', DoGet(_REMOTE, '/instances/%s/content/0010-0010' % i).strip())
            self.assertNotEqual('Jodogne', DoGet(_REMOTE, '/instances/%s/content/0010-0010' % j).strip())


    def test_modify_study(self):
        # Upload 4 images from the 2 series of the same study
        for i in range(4):
            UploadInstance(_REMOTE, 'Brainix/Flair/IM-0001-000%d.dcm' % (i + 1))
            UploadInstance(_REMOTE, 'Brainix/Epi/IM-0001-000%d.dcm' % (i + 1))

        origStudy = DoGet(_REMOTE, '/studies')[0]
        newStudy = DoPost(_REMOTE, '/studies/%s/modify' % origStudy,
                          '{"Replace":{"PatientName":"Jodogne"}}',
                          'application/json')['ID']

        self.assertEqual(origStudy, DoGet(_REMOTE, '/studies/%s' % newStudy)['ModifiedFrom'])
        series = DoGet(_REMOTE, '/studies/%s' % newStudy)['Series']
        self.assertEqual(2, len(series))
        for s in series:
            ss = DoGet(_REMOTE, '/series/%s' % s)['ModifiedFrom']
            self.assertEqual(newStudy, DoGet(_REMOTE, '/series/%s' % s)['ParentStudy'])
            self.assertEqual(origStudy, DoGet(_REMOTE, '/series/%s' % ss)['ParentStudy'])

            instances = DoGet(_REMOTE, '/series/%s' % s)['Instances']
            for i in instances:
                j = DoGet(_REMOTE, '/instances/%s' % i)['ModifiedFrom']
                self.assertEqual(s, DoGet(_REMOTE, '/instances/%s' % i)['ParentSeries'])
                self.assertEqual(ss, DoGet(_REMOTE, '/instances/%s' % j)['ParentSeries'])

                self.assertEqual('Jodogne', DoGet(_REMOTE, '/instances/%s/content/0010-0010' % i).strip())
                self.assertNotEqual('Jodogne', DoGet(_REMOTE, '/instances/%s/content/0010-0010' % j).strip())


    def test_anonymize_series(self):
        # Upload 4 images from the same series
        for i in range(4):
            UploadInstance(_REMOTE, 'Brainix/Epi/IM-0001-000%d.dcm' % (i + 1))

        origSeries = DoGet(_REMOTE, '/series')[0]
        newSeries = DoPost(_REMOTE, '/series/%s/anonymize' % origSeries,
                           '{}',
                           'application/json')['ID']

        self.assertEqual(origSeries, DoGet(_REMOTE, '/series/%s' % newSeries)['AnonymizedFrom'])
        instances = DoGet(_REMOTE, '/series/%s' % newSeries)['Instances']
        self.assertEqual(4, len(instances))
        for i in instances:
            j = DoGet(_REMOTE, '/instances/%s' % i)['AnonymizedFrom']
            self.assertEqual(newSeries, DoGet(_REMOTE, '/instances/%s' % i)['ParentSeries'])
            self.assertEqual(origSeries, DoGet(_REMOTE, '/instances/%s' % j)['ParentSeries'])

            DoGet(_REMOTE, '/instances/%s/content/0008-1010' % j)
            self.assertRaises(Exception, lambda: DoGet(_REMOTE, '/instances/%s/content/0008-1010' % i))


    def test_anonymize_study(self):
        # Upload 4 images from the 2 series of the same study
        for i in range(4):
            UploadInstance(_REMOTE, 'Brainix/Flair/IM-0001-000%d.dcm' % (i + 1))
            UploadInstance(_REMOTE, 'Brainix/Epi/IM-0001-000%d.dcm' % (i + 1))

        origStudy = DoGet(_REMOTE, '/studies')[0]
        newStudy = DoPost(_REMOTE,'/studies/%s/anonymize' % origStudy,
                          '{"Replace":{"PatientName":"Jodogne"}}',
                          'application/json')['ID']

        self.assertEqual(origStudy, DoGet(_REMOTE, '/studies/%s' % newStudy)['AnonymizedFrom'])
        series = DoGet(_REMOTE, '/studies/%s' % newStudy)['Series']
        self.assertEqual(2, len(series))
        for s in series:
            ss = DoGet(_REMOTE, '/series/%s' % s)['AnonymizedFrom']
            self.assertEqual(newStudy, DoGet(_REMOTE, '/series/%s' % s)['ParentStudy'])
            self.assertEqual(origStudy, DoGet(_REMOTE, '/series/%s' % ss)['ParentStudy'])

            instances = DoGet(_REMOTE, '/series/%s' % s)['Instances']
            for i in instances:
                j = DoGet(_REMOTE, '/instances/%s' % i)['AnonymizedFrom']
                self.assertEqual(s, DoGet(_REMOTE, '/instances/%s' % i)['ParentSeries'])
                self.assertEqual(ss, DoGet(_REMOTE, '/instances/%s' % j)['ParentSeries'])

                self.assertEqual('Jodogne', DoGet(_REMOTE, '/instances/%s/content/0010-0010' % i).strip())
                self.assertNotEqual('Jodogne', DoGet(_REMOTE, '/instances/%s/content/0010-0010' % j).strip())



    def test_storescu(self):
        # Check emptiness
        e = DoGet(_REMOTE, '/exports')
        self.assertEqual(0, len(e['Exports']))
        self.assertEqual(0, e['Last'])
        self.assertTrue(e['Done'])
        e = DoGet(_REMOTE, '/exports?last')
        self.assertEqual(0, len(e['Exports']))
        self.assertEqual(0, e['Last'])
        self.assertTrue(e['Done'])

        # Add 1 instance
        i = UploadInstance(_REMOTE, 'DummyCT.dcm')['ID']
        self.assertEqual(0, len(DoGet(_LOCAL, '/patients')))

        # Export the instance
        j = DoPost(_REMOTE, '/modalities/orthanctest/store', str(i), 'text/plain')  # instance
        self.assertEqual(1, len(DoGet(_LOCAL, '/patients')))
        self.assertEqual(1, len(DoGet(_LOCAL, '/studies')))
        self.assertEqual(1, len(DoGet(_LOCAL, '/series')))
        self.assertEqual(1, len(DoGet(_LOCAL, '/instances')))

        e = DoGet(_REMOTE, '/exports')
        self.assertEqual(1, len(e['Exports']))
        self.assertTrue(e['Done'])
        self.assertEqual(e['Exports'][-1]['Seq'], e['Last'])
        e = DoGet(_REMOTE, '/exports?limit=1')
        self.assertEqual(1, len(e['Exports']))
        self.assertTrue(e['Done'])
        self.assertEqual(e['Exports'][-1]['Seq'], e['Last'])
        e = DoGet(_REMOTE, '/exports?last')
        self.assertEqual(1, len(e['Exports']))
        self.assertTrue(e['Done'])
        self.assertEqual(e['Exports'][-1]['Seq'], e['Last'])
        seqInstance = e['Last']

        # Export the series
        j = DoPost(_REMOTE, '/modalities/orthanctest/store', 'f2635388-f01d497a-15f7c06b-ad7dba06-c4c599fe', 'text/plain')

        e = DoGet(_REMOTE, '/exports')
        self.assertEqual(2, len(e['Exports']))
        self.assertTrue(e['Done'])
        self.assertEqual(e['Exports'][-1]['Seq'], e['Last'])
        seqSeries = e['Last']
        self.assertNotEqual(seqInstance, seqSeries)
        e = DoGet(_REMOTE, '/exports?limit=1&since=0')
        self.assertEqual(1, len(e['Exports']))
        self.assertFalse(e['Done'])
        self.assertEqual(e['Exports'][-1]['Seq'], seqInstance)
        e = DoGet(_REMOTE, '/exports?limit=1&since=' + str(seqInstance))
        self.assertEqual(1, len(e['Exports']))
        self.assertTrue(e['Done'])
        self.assertEqual(e['Exports'][-1]['Seq'], seqSeries)
        e = DoGet(_REMOTE, '/exports?last')
        self.assertEqual(1, len(e['Exports']))
        self.assertTrue(e['Done'])
        self.assertEqual(e['Exports'][-1]['Seq'], seqSeries)

        # Export the study
        j = DoPost(_REMOTE, '/modalities/orthanctest/store', 'b9c08539-26f93bde-c81ab0d7-bffaf2cb-a4d0bdd0', 'text/plain')
        seqStudy = DoGet(_REMOTE, '/exports')['Last']

        # Export the patient
        j = DoPost(_REMOTE, '/modalities/orthanctest/store', '6816cb19-844d5aee-85245eba-28e841e6-2414fae2', 'text/plain')
        self.assertEqual(1, len(DoGet(_LOCAL, '/patients')))
        self.assertEqual(1, len(DoGet(_LOCAL, '/studies')))
        self.assertEqual(1, len(DoGet(_LOCAL, '/series')))
        self.assertEqual(1, len(DoGet(_LOCAL, '/instances')))

        e = DoGet(_REMOTE, '/exports')
        self.assertEqual(4, len(e['Exports']))
        self.assertTrue(e['Done'])
        self.assertEqual(e['Exports'][-1]['Seq'], e['Last'])
        seqPatient = e['Last']
        self.assertNotEqual(seqInstance, seqSeries)
        self.assertNotEqual(seqSeries, seqStudy)
        self.assertNotEqual(seqStudy, seqPatient)
        self.assertTrue(seqInstance < seqSeries)
        self.assertTrue(seqSeries < seqStudy)
        self.assertTrue(seqStudy < seqPatient)
        e = DoGet(_REMOTE, '/exports?limit=1&since=0')
        self.assertEqual(1, len(e['Exports']))
        self.assertFalse(e['Done'])
        self.assertEqual(e['Exports'][-1]['Seq'], seqInstance)
        e = DoGet(_REMOTE, '/exports?limit=1&since=' + str(seqInstance))
        self.assertEqual(1, len(e['Exports']))
        self.assertFalse(e['Done'])
        self.assertEqual(e['Exports'][-1]['Seq'], seqSeries)
        e = DoGet(_REMOTE, '/exports?limit=1&since=' + str(seqSeries))
        self.assertEqual(1, len(e['Exports']))
        self.assertFalse(e['Done'])
        self.assertEqual(e['Exports'][-1]['Seq'], seqStudy)
        e = DoGet(_REMOTE, '/exports?limit=1&since=' + str(seqStudy))
        self.assertEqual(1, len(e['Exports']))
        self.assertTrue(e['Done'])
        self.assertEqual(e['Exports'][-1]['Seq'], seqPatient)
        e = DoGet(_REMOTE, '/exports?last')
        self.assertEqual(1, len(e['Exports']))
        self.assertTrue(e['Done'])
        self.assertEqual(e['Exports'][-1]['Seq'], seqPatient)


        # Check the content of the logged information
        e = DoGet(_REMOTE, '/exports')['Exports']

        if 'PatientID' in e[0]:
            # Since Orthanc 0.8.6
            patient = 'PatientID'
            study = 'StudyInstanceUID'
            series = 'SeriesInstanceUID'
            instance = 'SOPInstanceUID'
        else:
            # Up to Orthanc 0.8.5
            patient = 'PatientId'
            study = 'StudyInstanceUid'
            series = 'SeriesInstanceUid'
            instance = 'SopInstanceUid'

        for k in range(4):
            self.assertTrue('Date' in e[k])
            self.assertTrue('Seq' in e[k])
            self.assertEqual('orthanctest', e[k]['RemoteModality'])

        self.assertEqual(10, len(e[0]))
        self.assertEqual('Instance', e[0]['ResourceType'])
        self.assertEqual('66a662ce-7430e543-bad44d47-0dc5a943-ec7a538d', e[0]['ID'])
        self.assertEqual('/instances/66a662ce-7430e543-bad44d47-0dc5a943-ec7a538d', e[0]['Path'])
        self.assertEqual('1.2.840.113619.2.176.2025.1499492.7040.1171286242.109', e[0][instance])
        self.assertEqual('1.2.840.113619.2.176.2025.1499492.7391.1171285944.394', e[0][series])
        self.assertEqual('1.2.840.113619.2.176.2025.1499492.7391.1171285944.390', e[0][study])
        self.assertEqual('ozp00SjY2xG', e[0][patient])

        self.assertEqual(9, len(e[1]))
        self.assertEqual('Series', e[1]['ResourceType'])
        self.assertEqual('f2635388-f01d497a-15f7c06b-ad7dba06-c4c599fe', e[1]['ID'])
        self.assertEqual('/series/f2635388-f01d497a-15f7c06b-ad7dba06-c4c599fe', e[1]['Path'])
        self.assertEqual('1.2.840.113619.2.176.2025.1499492.7391.1171285944.394', e[1][series])
        self.assertEqual('1.2.840.113619.2.176.2025.1499492.7391.1171285944.390', e[1][study])
        self.assertEqual('ozp00SjY2xG', e[1][patient])

        self.assertEqual(8, len(e[2]))
        self.assertEqual('Study', e[2]['ResourceType'])
        self.assertEqual('b9c08539-26f93bde-c81ab0d7-bffaf2cb-a4d0bdd0', e[2]['ID'])
        self.assertEqual('/studies/b9c08539-26f93bde-c81ab0d7-bffaf2cb-a4d0bdd0', e[2]['Path'])
        self.assertEqual('1.2.840.113619.2.176.2025.1499492.7391.1171285944.390', e[2][study])
        self.assertEqual('ozp00SjY2xG', e[2][patient])

        self.assertEqual(7, len(e[3]))
        self.assertEqual('Patient', e[3]['ResourceType'])
        self.assertEqual('6816cb19-844d5aee-85245eba-28e841e6-2414fae2', e[3]['ID'])
        self.assertEqual('/patients/6816cb19-844d5aee-85245eba-28e841e6-2414fae2', e[3]['Path'])
        self.assertEqual('ozp00SjY2xG', e[3][patient])

        DropOrthanc(_REMOTE)
        self.assertEqual(0, len(DoGet(_REMOTE, '/exports')['Exports']))


    def test_store_peer(self):
        self.assertEqual(0, len(DoGet(_LOCAL, '/exports')['Exports']))
        self.assertEqual(0, len(DoGet(_REMOTE, '/exports')['Exports']))

        i = UploadInstance(_REMOTE, 'DummyCT.dcm')['ID']
        self.assertEqual(0, len(DoGet(_LOCAL, '/patients')))
        self.assertEqual(1, len(DoGet(_REMOTE, '/patients')))

        j = DoPost(_REMOTE, '/peers/peer/store', str(i), 'text/plain')
        self.assertEqual(1, len(DoGet(_LOCAL, '/patients')))
        self.assertEqual(1, len(DoGet(_REMOTE, '/patients')))

        self.assertEqual(1, len(DoGet(_REMOTE, '/exports')['Exports']))

        DropOrthanc(_REMOTE)
        self.assertEqual(0, len(DoGet(_REMOTE, '/exports')['Exports']))


    def test_bulk_storescu(self):
        self.assertEqual(0, len(DoGet(_LOCAL, '/patients')))
        
        a = UploadInstance(_REMOTE, 'Knee/T1/IM-0001-0001.dcm')
        b = UploadInstance(_REMOTE, 'Knee/T2/IM-0001-0001.dcm')

        j = DoPost(_REMOTE, '/modalities/orthanctest/store', [ a['ID'], b['ID'] ], 'application/json')
        self.assertEqual(2, len(DoGet(_LOCAL, '/instances')))

        DropOrthanc(_LOCAL)

        # Send using patient's UUID
        self.assertEqual(0, len(DoGet(_LOCAL, '/instances')))
        j = DoPost(_REMOTE, '/modalities/orthanctest/store', 
                   [ 'ca29faea-b6a0e17f-067743a1-8b778011-a48b2a17' ], 'application/json')
        self.assertEqual(2, len(DoGet(_LOCAL, '/instances')))
        

    def test_color(self):
        i = UploadInstance(_REMOTE, 'ColorTestMalaterre.dcm')['ID']
        im = GetImage(_REMOTE, '/instances/%s/preview' % i)
        self.assertEqual("RGB", im.mode)
        self.assertEqual(41, im.size[0])
        self.assertEqual(41, im.size[1])

        # http://effbot.org/zone/pil-comparing-images.htm
        truth = Image.open(GetDatabasePath('ColorTestMalaterre.png'))
        self.assertTrue(ImageChops.difference(im, truth).getbbox() is None)


    def test_faking_ruby_put(self):
        UploadInstance(_REMOTE, 'Knee/T1/IM-0001-0001.dcm')
        UploadInstance(_REMOTE, 'Brainix/Flair/IM-0001-0001.dcm')
        self.assertEqual(2, len(DoGet(_REMOTE, '/patients')))
        a = DoGet(_REMOTE, '/patients')[0]
        b = DoGet(_REMOTE, '/patients')[1]
        self.assertEqual(0, DoGet(_REMOTE, '/patients/%s/protected' % a))
        DoGet(_REMOTE, '/patients/%s/protected' % a, data = { '_method' : 'PUT' }, body = '0')
        self.assertEqual(0, DoGet(_REMOTE, '/patients/%s/protected' % a))
        DoGet(_REMOTE, '/patients/%s/protected' % a, data = { '_method' : 'PUT' }, body = '1')
        self.assertEqual(1, DoGet(_REMOTE, '/patients/%s/protected' % a))
        DoGet(_REMOTE, '/patients/%s/protected' % a, data = { '_method' : 'PUT' }, body = '0')
        self.assertEqual(0, DoGet(_REMOTE, '/patients/%s/protected' % a))


    def test_faking_ruby_delete(self):
        UploadInstance(_REMOTE, 'Knee/T1/IM-0001-0001.dcm')
        UploadInstance(_REMOTE, 'Brainix/Flair/IM-0001-0001.dcm')
        self.assertEqual(2, len(DoGet(_REMOTE, '/patients')))
        a = DoGet(_REMOTE, '/patients')[0]
        b = DoGet(_REMOTE, '/patients')[1]
        DoGet(_REMOTE, '/patients/%s' % a, data = { '_method' : 'DELETE' })
        self.assertEqual(1, len(DoGet(_REMOTE, '/patients')))
        DoGet(_REMOTE, '/patients/%s' % b, data = { '_method' : 'DELETE' })
        self.assertEqual(0, len(DoGet(_REMOTE, '/patients')))


    def test_faking_google_put(self):
        UploadInstance(_REMOTE, 'Knee/T1/IM-0001-0001.dcm')
        UploadInstance(_REMOTE, 'Brainix/Flair/IM-0001-0001.dcm')
        self.assertEqual(2, len(DoGet(_REMOTE, '/patients')))
        a = DoGet(_REMOTE, '/patients')[0]
        b = DoGet(_REMOTE, '/patients')[1]
        self.assertEqual(0, DoGet(_REMOTE, '/patients/%s/protected' % a))
        DoPost(_REMOTE, '/patients/%s/protected' % a, headers = { 'X-HTTP-Method-Override' : 'PUT' }, data = '0')
        self.assertEqual(0, DoGet(_REMOTE, '/patients/%s/protected' % a))
        DoPost(_REMOTE, '/patients/%s/protected' % a, headers = { 'X-HTTP-Method-Override' : 'PUT' }, data = '1')
        self.assertEqual(1, DoGet(_REMOTE, '/patients/%s/protected' % a))
        DoPost(_REMOTE, '/patients/%s/protected' % a, headers = { 'X-HTTP-Method-Override' : 'PUT' }, data = '0')
        self.assertEqual(0, DoGet(_REMOTE, '/patients/%s/protected' % a))


    def test_faking_google_delete(self):
        UploadInstance(_REMOTE, 'Knee/T1/IM-0001-0001.dcm')
        UploadInstance(_REMOTE, 'Brainix/Flair/IM-0001-0001.dcm')
        self.assertEqual(2, len(DoGet(_REMOTE, '/patients')))
        a = DoGet(_REMOTE, '/patients')[0]
        b = DoGet(_REMOTE, '/patients')[1]
        DoPost(_REMOTE, '/patients/%s' % a, headers = { 'X-HTTP-Method-Override' : 'DELETE' })
        self.assertEqual(1, len(DoGet(_REMOTE, '/patients')))
        DoPost(_REMOTE, '/patients/%s' % b, headers = { 'X-HTTP-Method-Override' : 'DELETE' })
        self.assertEqual(0, len(DoGet(_REMOTE, '/patients')))


    def test_lua(self):
        self.assertEqual(42, DoPost(_REMOTE, '/tools/execute-script', 'print(42)'))
        self.assertTrue(IsDefinedInLua(_REMOTE, 'PrintRecursive'))
        self.assertFalse(IsDefinedInLua(_REMOTE, 'HelloWorld'))


    def test_metadata(self):
        UploadInstance(_REMOTE, 'Knee/T1/IM-0001-0001.dcm')
        p = DoGet(_REMOTE, '/patients')[0]
        i = DoGet(_REMOTE, '/instances')[0]

        m = DoGet(_REMOTE, '/patients/%s/metadata' % p)
        self.assertEqual(1, len(m))
        self.assertEqual('LastUpdate', m[0])

        m = DoGet(_REMOTE, '/instances/%s/metadata' % i)
        self.assertEqual(4, len(m))
        self.assertTrue('IndexInSeries' in m)
        self.assertTrue('ReceptionDate' in m)
        self.assertTrue('RemoteAET' in m)
        self.assertTrue('Origin' in m)
        self.assertEqual(DoGet(_REMOTE, '/instances/%s/metadata/IndexInSeries' % i), 1)
        self.assertEqual(DoGet(_REMOTE, '/instances/%s/metadata/Origin' % i), 'RestApi')
        self.assertEqual(DoGet(_REMOTE, '/instances/%s/metadata/RemoteAET' % i), '')  # None, received by REST API

        # Play with custom metadata
        DoPut(_REMOTE, '/patients/%s/metadata/5555' % p, 'coucou')
        m = DoGet(_REMOTE, '/patients/%s/metadata' % p)
        self.assertEqual(2, len(m))
        self.assertTrue('LastUpdate' in m)
        self.assertTrue('5555' in m)
        self.assertEqual('coucou', DoGet(_REMOTE, '/patients/%s/metadata/5555' % p))
        DoPut(_REMOTE, '/patients/%s/metadata/5555' % p, 'hello')
        self.assertEqual('hello', DoGet(_REMOTE, '/patients/%s/metadata/5555' % p))
        DoDelete(_REMOTE, '/patients/%s/metadata/5555' % p)
        m = DoGet(_REMOTE, '/patients/%s/metadata' % p)
        self.assertEqual(1, len(m))
        self.assertTrue('LastUpdate' in m)


    def test_statistics(self):
        # Upload 16 instances
        for i in range(4):
            UploadInstance(_REMOTE, 'Brainix/Flair/IM-0001-000%d.dcm' % (i + 1))
            UploadInstance(_REMOTE, 'Brainix/Epi/IM-0001-000%d.dcm' % (i + 1))
            UploadInstance(_REMOTE, 'Knee/T1/IM-0001-000%d.dcm' % (i + 1))
            UploadInstance(_REMOTE, 'Knee/T2/IM-0001-000%d.dcm' % (i + 1))

        s = DoGet(_REMOTE, '/statistics')
        self.assertEqual(16, s['CountInstances'])
        self.assertEqual(2, s['CountPatients'])
        self.assertEqual(2, s['CountStudies'])
        self.assertEqual(4, s['CountSeries'])
        d = int(s['TotalUncompressedSize'])

        e = 0
        for patient in DoGet(_REMOTE, '/patients'):
            s = DoGet(_REMOTE, '/patients/%s/statistics' % patient)
            self.assertEqual(8, s['CountInstances'])
            self.assertEqual(1, s['CountStudies'])
            self.assertEqual(2, s['CountSeries'])
            e += int(s['UncompressedSize'])

        for study in DoGet(_REMOTE, '/studies'):
            s = DoGet(_REMOTE, '/studies/%s/statistics' % study)
            self.assertEqual(8, s['CountInstances'])
            self.assertEqual(2, s['CountSeries'])
            e += int(s['UncompressedSize'])

        for series in DoGet(_REMOTE, '/series'):
            s = DoGet(_REMOTE, '/series/%s/statistics' % series)
            self.assertEqual(4, s['CountInstances'])
            e += int(s['UncompressedSize'])

        self.assertEqual(3 * d, e)


    def test_custom_attachment(self):
        UploadInstance(_REMOTE, 'Brainix/Flair/IM-0001-0001.dcm')
        patient = DoGet(_REMOTE, '/patients')[0]
        instance = DoGet(_REMOTE, '/instances')[0]
        size = int(DoGet(_REMOTE, '/patients/%s/statistics' % patient)['DiskSize'])
        self.assertEqual(size, int(DoGet(_REMOTE, '/statistics')['TotalDiskSize']))
        
        self.assertEqual(0, len(DoGet(_REMOTE, '/patients/%s/attachments' % patient)))
        self.assertEqual(2, len(DoGet(_REMOTE, '/instances/%s/attachments' % instance)))
        self.assertTrue('dicom' in DoGet(_REMOTE, '/instances/%s/attachments' % instance))
        self.assertTrue('dicom-as-json' in DoGet(_REMOTE, '/instances/%s/attachments' % instance))

        self.assertRaises(Exception, lambda: DoPut(_REMOTE, '/patients/%s/attachments/22' % patient, 'hello'))
        hello = 'hellohellohellohellohellohellohellohellohello'
        DoPut(_REMOTE, '/patients/%s/attachments/1025' % patient, hello)
        self.assertEqual(int(DoGet(_REMOTE, '/patients/%s/statistics' % patient)['DiskSize']),
                         int(DoGet(_REMOTE, '/statistics')['TotalDiskSize']))
        self.assertEqual(int(DoGet(_REMOTE, '/patients/%s/statistics' % patient)['DiskSize']),
                         size + int(DoGet(_REMOTE, '/patients/%s/attachments/1025/compressed-size' % patient)))

        DoPut(_REMOTE, '/patients/%s/attachments/1026' % patient, 'world')
        self.assertEqual(int(DoGet(_REMOTE, '/patients/%s/statistics' % patient)['DiskSize']),
                         int(DoGet(_REMOTE, '/statistics')['TotalDiskSize']))
        self.assertEqual(int(DoGet(_REMOTE, '/patients/%s/statistics' % patient)['DiskSize']),
                         size + 
                         int(DoGet(_REMOTE, '/patients/%s/attachments/1025/compressed-size' % patient)) +
                         int(DoGet(_REMOTE, '/patients/%s/attachments/1026/compressed-size' % patient)))

        self.assertEqual(2, len(DoGet(_REMOTE, '/patients/%s/attachments' % patient)))
        self.assertEqual(hello, DoGet(_REMOTE, '/patients/%s/attachments/1025/data' % patient))
        self.assertEqual('world', DoGet(_REMOTE, '/patients/%s/attachments/1026/data' % patient))
        DoPost(_REMOTE, '/patients/%s/attachments/1025/verify-md5' % patient)
        DoPost(_REMOTE, '/patients/%s/attachments/1026/verify-md5' % patient)
        DoPut(_REMOTE, '/patients/%s/attachments/1026' % patient, 'world2')
        self.assertEqual('world2', DoGet(_REMOTE, '/patients/%s/attachments/1026/data' % patient))

        self.assertRaises(Exception, lambda: DoDelete(_REMOTE, '/instances/%s/attachments/dicom' % instance))
        DoDelete(_REMOTE, '/patients/%s/attachments/1025' % patient)
        self.assertEqual(int(DoGet(_REMOTE, '/patients/%s/statistics' % patient)['DiskSize']),
                         int(DoGet(_REMOTE, '/statistics')['TotalDiskSize']))
        self.assertEqual(int(DoGet(_REMOTE, '/patients/%s/statistics' % patient)['DiskSize']),
                         size + int(DoGet(_REMOTE, '/patients/%s/attachments/1026/compressed-size' % patient)))

        self.assertEqual(1, len(DoGet(_REMOTE, '/patients/%s/attachments' % patient)))
        DoDelete(_REMOTE, '/patients/%s/attachments/1026' % patient)
        self.assertEqual(0, len(DoGet(_REMOTE, '/patients/%s/attachments' % patient)))

        self.assertEqual(int(DoGet(_REMOTE, '/patients/%s/statistics' % patient)['DiskSize']), size)
        self.assertEqual(size, int(DoGet(_REMOTE, '/statistics')['TotalDiskSize']))


    def test_incoming_storescu(self):
        self.assertEqual(0, len(DoGet(_REMOTE, '/patients')))
        subprocess.check_call([ FindExecutable('storescu'),
                                _REMOTE['Server'], str(_REMOTE['DicomPort']),
                                GetDatabasePath('ColorTestImageJ.dcm') ])
        self.assertEqual(1, len(DoGet(_REMOTE, '/patients')))

        i = DoGet(_REMOTE, '/instances')
        self.assertEqual(1, len(i))
        m = DoGet(_REMOTE, '/instances/%s/metadata' % i[0])
        self.assertEqual(4, len(m))
        self.assertTrue('IndexInSeries' in m)
        self.assertTrue('ReceptionDate' in m)
        self.assertTrue('RemoteAET' in m)
        self.assertTrue('Origin' in m)
        self.assertEqual(DoGet(_REMOTE, '/instances/%s/metadata/IndexInSeries' % i[0]), 1)
        self.assertEqual(DoGet(_REMOTE, '/instances/%s/metadata/Origin' % i[0]), 'DicomProtocol')
        self.assertEqual(DoGet(_REMOTE, '/instances/%s/metadata/RemoteAET' % i[0]), 'STORESCU')


    def test_incoming_findscu(self):
        def CallFindScu(args):
            p = subprocess.Popen([ FindExecutable('findscu'), 
                                   '-P', '-aec', _REMOTE['DicomAet'], '-aet', _LOCAL['DicomAet'],
                                   _REMOTE['Server'], str(_REMOTE['DicomPort']) ] + args,
                                 stderr=subprocess.PIPE)
            return p.communicate()[1]

        UploadInstance(_REMOTE, 'Multiframe.dcm')
        UploadInstance(_REMOTE, 'ColorTestImageJ.dcm')

        i = CallFindScu([ '-k', '0008,0052=PATIENT', '-k', '0010,0010' ])
        patientNames = re.findall('\(0010,0010\).*?\[(.*?)\]', i)
        self.assertEqual(2, len(patientNames))
        self.assertTrue('Test Patient BG ' in patientNames)
        self.assertTrue('Anonymized' in patientNames)

        i = CallFindScu([ '-k', '0008,0052=SERIES', '-k', '0008,0021' ])
        series = re.findall('\(0008,0021\).*?\[\s*(.*?)\s*\]', i)
        self.assertEqual(2, len(series))
        self.assertTrue('20070208' in series)
        self.assertTrue('19980312' in series)
        
        i = CallFindScu([ '-k', '0008,0052=SERIES', '-k', '0008,0021', '-k', 'ModalitiesInStudy=MR\\XA' ])
        series = re.findall('\(0008,0021\).*?\[\s*(.*?)\s*\]', i)
        self.assertEqual(1, len(series))
        self.assertTrue('19980312' in series)
        
        i = CallFindScu([ '-k', '0008,0052=SERIES', '-k', 'PatientName=Anonymized' ])
        series = re.findall('\(0010,0010\).*?\[\s*(.*?)\s*\]', i)
        self.assertEqual(1, len(series))

        # Test the "CaseSentitivePN" flag (false by default)
        i = CallFindScu([ '-k', '0008,0052=SERIES', '-k', 'PatientName=anonymized' ])
        series = re.findall('\(0010,0010\).*?\[\s*(.*?)\s*\]', i)
        self.assertEqual(1, len(series))

        # Test returning sequence values (only since Orthanc 0.9.5)
        i = CallFindScu([ '-k', '0008,0052=SERIES', '-k', '0008,2112' ])  # "ColorTestImageJ" has this sequence tag
        sequences = re.findall('\(0008,2112\)', i)
        self.assertEqual(1, len(sequences))
        

    def test_incoming_movescu(self):
        UploadInstance(_REMOTE, 'Multiframe.dcm')
        
        self.assertEqual(0, len(DoGet(_LOCAL, '/patients')))
        CallMoveScu([ '--patient', '-k', '0008,0052=PATIENT', '-k', 'PatientID=none' ])
        self.assertEqual(0, len(DoGet(_LOCAL, '/patients')))
        CallMoveScu([ '--patient', '-k', '0008,0052=PATIENT', '-k', 'PatientID=12345678' ])
        self.assertEqual(1, len(DoGet(_LOCAL, '/patients')))


    def test_findscu(self):
        i = UploadInstance(_REMOTE, 'DummyCT.dcm')['ID']
        j = UploadInstance(_REMOTE, 'Issue22.dcm')['ID']
        k = UploadInstance(_REMOTE, 'ColorTestImageJ.dcm')['ID']
        DoPost(_REMOTE, '/modalities/orthanctest/store', str(i), 'text/plain')
        
        # Test the "find-patient" level
        p = DoPost(_REMOTE, '/modalities/orthanctest/find-patient', { })
        self.assertEqual(1, len(p))
        self.assertEqual('ozp00SjY2xG', p[0]['PatientID'])
        
        # Test wildcards constraints. The "LO" value representation
        # for PatientID is always case-sensitive, but the "PN" for
        # PatientName might depend on the implementation:
        # "GenerateConfigurationForTests.py" will force it to be case
        # insensitive (which was the default until Orthanc 0.8.6).
        p = DoPost(_REMOTE, '/modalities/orthanctest/find-patient', { 'PatientName' : 'K*' })
        self.assertEqual(1, len(p))
        
        p = DoPost(_REMOTE, '/modalities/orthanctest/find-patient', { 'PatientName' : 'k*' })
        self.assertEqual(1, len(p))
        
        p = DoPost(_REMOTE, '/modalities/orthanctest/find-patient', { 'PatientID' : 'ozp*' })
        self.assertEqual(1, len(p))
        
        p = DoPost(_REMOTE, '/modalities/orthanctest/find-patient', { 'PatientID' : 'o?p*' })
        self.assertEqual(1, len(p))
        
        p = DoPost(_REMOTE, '/modalities/orthanctest/find-patient', { 'PatientID' : '0?q*' })
        self.assertEqual(0, len(p))
        
        p = DoPost(_REMOTE, '/modalities/orthanctest/find-patient', { 'PatientName' : 'B*' })
        self.assertEqual(0, len(p))
        
        p = DoPost(_REMOTE, '/modalities/orthanctest/find-patient', { 'PatientName' : 'b*' })
        self.assertEqual(0, len(p))
        
        DoPost(_REMOTE, '/modalities/orthanctest/store', str(j), 'text/plain')
        DoPost(_REMOTE, '/modalities/orthanctest/store', str(k), 'text/plain')
        DoPost(_REMOTE, '/modalities/orthanctest/find-patient', { })
        self.assertEqual(3, len(DoPost(_REMOTE, '/modalities/orthanctest/find-patient', { })))
        
        p = DoPost(_REMOTE, '/modalities/orthanctest/find-patient', { 'PatientName' : 'A*' })
        self.assertEqual(2, len(p))

        # Test the "find-study" level. This is the instance "ColorTestImageJ.dcm"
        s = DoPost(_REMOTE, '/modalities/orthanctest/find-study', { 'PatientID' : 'B9uTHKOZ' })
        self.assertEqual(1, len(s))
        self.assertEqual('20070208', s[0]['StudyDate'])
        
        # Test range searches
        t = DoPost(_REMOTE, '/modalities/orthanctest/find-study', { 'PatientID' : 'B9uTHKOZ',
                                                                    'StudyDate' : '-20070101' })
        self.assertEqual(0, len(t))
        
        t = DoPost(_REMOTE, '/modalities/orthanctest/find-study', { 'PatientID' : 'B9uTHKOZ',
                                                                    'StudyDate' : '20090101-' })
        self.assertEqual(0, len(t))
        
        t = DoPost(_REMOTE, '/modalities/orthanctest/find-study', { 'PatientID' : 'B9uTHKOZ',
                                                                    'StudyDate' : '20070101-' })
        self.assertEqual(1, len(t))
        
        t = DoPost(_REMOTE, '/modalities/orthanctest/find-study', { 'PatientID' : 'B9uTHKOZ',
                                                                    'StudyDate' : '-20090101' })
        self.assertEqual(1, len(t))
        
        t = DoPost(_REMOTE, '/modalities/orthanctest/find-study', { 'PatientID' : 'B9uTHKOZ',
                                                                    'StudyDate' : '20070207-20070207' })
        self.assertEqual(0, len(t))
        
        t = DoPost(_REMOTE, '/modalities/orthanctest/find-study', { 'PatientID' : 'B9uTHKOZ',
                                                                    'StudyDate' : '20070208-20070208' })
        self.assertEqual(1, len(t))
        
        t = DoPost(_REMOTE, '/modalities/orthanctest/find-study', { 'PatientID' : 'B9uTHKOZ',
                                                                    'StudyDate' : '20070209-20070209' })
        self.assertEqual(0, len(t))
        
        # Test the ModalitiesInStudy tag
        t = DoPost(_REMOTE, '/modalities/orthanctest/find-study', {
            'PatientID' : 'B9uTHKOZ', 
            'ModalitiesInStudy' : 'US' })
        self.assertEqual(0, len(t))

        t = DoPost(_REMOTE, '/modalities/orthanctest/find-study', {
            'PatientID' : 'B9uTHKOZ', 
            'ModalitiesInStudy' : 'CT' })
        self.assertEqual(1, len(t))

        t = DoPost(_REMOTE, '/modalities/orthanctest/find-study', {
            'PatientID' : 'B9uTHKOZ', 
            'ModalitiesInStudy' : 'US\\CT' })
        self.assertEqual(1, len(t))

        # Test the "find-series" level
        t = DoPost(_REMOTE, '/modalities/orthanctest/find-series', {
            'PatientID' : 'B9uTHKOZ', 
            'StudyInstanceUID' : s[0]['StudyInstanceUID'] })
        self.assertEqual(1, len(t))

        # Test "\" separator
        t = DoPost(_REMOTE, '/modalities/orthanctest/find-series', {
            'PatientID' : 'B9uTHKOZ', 
            'StudyInstanceUID' : s[0]['StudyInstanceUID'],
            'Modality' : 'MR\\CT\\US' })
        self.assertEqual(1, len(t))

        t = DoPost(_REMOTE, '/modalities/orthanctest/find-series', {
            'PatientID' : 'B9uTHKOZ', 
            'StudyInstanceUID' : s[0]['StudyInstanceUID'],
            'Modality' : 'MR\\US' })
        self.assertEqual(0, len(t))


    def test_update_modalities(self):
        try:
            DoDelete(_REMOTE, '/modalities/toto')
        except:
            pass
        try:
            DoDelete(_REMOTE, '/modalities/tata')
        except:
            pass
        self.assertRaises(Exception, lambda: DoGet(_REMOTE, '/modalities/toto'))
        DoPut(_REMOTE, '/modalities/toto', [ "STORESCP", "localhost", 2000 ])
        DoPut(_REMOTE, '/modalities/tata', [ "STORESCP", "localhost", 2000, 'MedInria' ])
        self.assertRaises(Exception, lambda: DoPut(_REMOTE, '/modalities/toto', [ "STORESCP", "localhost", 2000, 'MedInriaaa' ]))
        self.assertTrue('store' in DoGet(_REMOTE, '/modalities/toto'))
        self.assertTrue('store' in DoGet(_REMOTE, '/modalities/tata'))
        DoDelete(_REMOTE, '/modalities/toto')
        DoDelete(_REMOTE, '/modalities/tata')
        self.assertRaises(Exception, lambda: DoGet(_REMOTE, '/modalities/toto'))
        self.assertRaises(Exception, lambda: DoGet(_REMOTE, '/modalities/tata'))


    def test_update_peers(self):
        # curl -X PUT http://localhost:8042/peers/toto -d '["http://localhost:8042/"]' -v
        try:
            DoDelete(_REMOTE, '/peers/toto')
        except:
            pass
        try:
            DoDelete(_REMOTE, '/peers/tata')
        except:
            pass
        self.assertRaises(Exception, lambda: DoGet(_REMOTE, '/peers/toto'))
        DoPut(_REMOTE, '/peers/toto', [ 'http://localhost:8042/' ])
        DoPut(_REMOTE, '/peers/tata', [ 'http://localhost:8042/', 'user', 'pass' ])
        self.assertRaises(Exception, lambda: DoPut(_REMOTE, '/peers/toto', [ 'http://localhost:8042/', 'a' ]))
        self.assertRaises(Exception, lambda: DoPut(_REMOTE, '/peers/toto', [ 'http://localhost:8042/', 'a', 'b', 'c' ]))
        self.assertTrue('store' in DoGet(_REMOTE, '/peers/toto'))
        self.assertTrue('store' in DoGet(_REMOTE, '/peers/tata'))
        DoDelete(_REMOTE, '/peers/toto')
        DoDelete(_REMOTE, '/peers/tata')
        self.assertRaises(Exception, lambda: DoGet(_REMOTE, '/peers/toto'))
        self.assertRaises(Exception, lambda: DoGet(_REMOTE, '/peers/tata'))


    def test_mesterhazy_modification(self):
        # When I modify a series ( eg. curl
        # http://localhost:8042/series/uidhere/modify -X POST -d
        # '{"Replace":{"SeriesDate":"19990101"}}' ) the modified
        # series is added to a new Study, instead of the existing
        # Study. Fixed in Orthanc 0.7.5

        u = UploadInstance(_REMOTE, 'DummyCT.dcm')
        study = 'b9c08539-26f93bde-c81ab0d7-bffaf2cb-a4d0bdd0'
        series = 'f2635388-f01d497a-15f7c06b-ad7dba06-c4c599fe'

        modified = DoPost(_REMOTE, '/series/%s/modify' % series,
                          json.dumps({ "Replace" : { "SeriesDate" : "19990101" }}))

        self.assertEqual(study, DoGet(_REMOTE, '/series/%s' % modified['ID']) ['ParentStudy'])


    def test_create(self):
        i = DoPost(_REMOTE, '/tools/create-dicom',
                   json.dumps({
                    'PatientName' : 'Jodogne',
                    'Modality' : 'CT',
                    'SOPClassUID' : '1.2.840.10008.5.1.4.1.1.1',
                    'PixelData' : 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAUAAAAFCAYAAACNbyblAAAAHElEQVQI12P4//8/w38GIAXDIBKE0DHxgljNBAAO9TXL0Y4OHwAAAABJRU5ErkJggg==' # red dot in RGBA
                    }))

        self.assertEqual('Jodogne', DoGet(_REMOTE, '/instances/%s/content/PatientName' % i['ID']).strip())
        self.assertEqual('CT', DoGet(_REMOTE, '/instances/%s/content/Modality' % i['ID']).strip())

        png = GetImage(_REMOTE, '/instances/%s/preview' % i['ID'])
        self.assertEqual((5, 5), png.size)

        j = DoGet(_REMOTE, i['Path'])
        self.assertEqual('Instance', j['Type'])
        self.assertEqual(j['ID'], i['ID'])


    def test_pilates(self):
        # "SCU failed error when accessing orthanc with osirix" by
        # Pilates Agentur (Mar 10, 2014 at 9:33 PM)
        i = UploadInstance(_REMOTE, 'PilatesArgenturGEUltrasoundOsiriX.dcm')['ID']
        self.assertEqual(0, len(DoGet(_LOCAL, '/patients')))
        j = DoPost(_REMOTE, '/modalities/orthanctest/store', str(i), 'text/plain')
        self.assertEqual(1, len(DoGet(_LOCAL, '/patients')))


    def test_shared_tags(self):
        a = UploadInstance(_REMOTE, 'Knee/T1/IM-0001-0001.dcm')['ID']
        b = UploadInstance(_REMOTE, 'Knee/T1/IM-0001-0002.dcm')['ID']
        p = DoGet(_REMOTE, '/patients')[0]
        
        self.assertTrue('0010,0010' in DoGet(_REMOTE, '/patients/%s/shared-tags' % p))
        self.assertTrue('PatientName' in DoGet(_REMOTE, '/patients/%s/shared-tags?simplify' % p))
        self.assertTrue('0008,1030' in DoGet(_REMOTE, '/patients/%s/shared-tags' % p))
        self.assertTrue('StudyDescription' in DoGet(_REMOTE, '/patients/%s/shared-tags?simplify' % p))
        self.assertTrue('0008,103e' in DoGet(_REMOTE, '/patients/%s/shared-tags' % p))
        self.assertTrue('SeriesDescription' in DoGet(_REMOTE, '/patients/%s/shared-tags?simplify' % p))
        self.assertFalse('0008,0018' in DoGet(_REMOTE, '/patients/%s/shared-tags' % p))
        self.assertFalse('SOPInstanceUID' in DoGet(_REMOTE, '/patients/%s/shared-tags?simplify' % p))

        self.assertTrue('0008,0018' in DoGet(_REMOTE, '/instances/%s/tags' % a))
        self.assertTrue('SOPInstanceUID' in DoGet(_REMOTE, '/instances/%s/tags?simplify' % a))


    def test_modules(self):
        a = UploadInstance(_REMOTE, 'Knee/T1/IM-0001-0001.dcm')['ID']
        p = DoGet(_REMOTE, '/patients')[0]
        s = DoGet(_REMOTE, '/studies')[0]
        t = DoGet(_REMOTE, '/series')[0]
        
        self.assertTrue('0010,0010' in DoGet(_REMOTE, '/patients/%s/module' % p))
        self.assertTrue('PatientName' in DoGet(_REMOTE, '/patients/%s/module?simplify' % p))
        self.assertTrue('0010,0010' in DoGet(_REMOTE, '/studies/%s/module-patient' % p))
        self.assertTrue('PatientName' in DoGet(_REMOTE, '/studies/%s/module-patient?simplify' % p))
        self.assertTrue('0008,1030' in DoGet(_REMOTE, '/studies/%s/module' % s))
        self.assertTrue('StudyDescription' in DoGet(_REMOTE, '/studies/%s/module?simplify' % s))
        self.assertTrue('0008,103e' in DoGet(_REMOTE, '/series/%s/module' % p))
        self.assertTrue('SeriesDescription' in DoGet(_REMOTE, '/series/%s/module?simplify' % p))
        self.assertTrue('0008,0018' in DoGet(_REMOTE, '/instances/%s/module' % a))
        self.assertTrue('SOPInstanceUID' in DoGet(_REMOTE, '/instances/%s/module?simplify' % a))


    def test_auto_directory(self):
        a = UploadInstance(_REMOTE, 'Knee/T1/IM-0001-0001.dcm')['ID']
        self.assertTrue('now' in DoGet(_REMOTE, '/tools'))
        self.assertTrue('dicom-conformance' in DoGet(_REMOTE, '/tools'))
        self.assertTrue(len(DoGet(_REMOTE, '/tools/dicom-conformance')) > 1000)
        self.assertTrue('orthanctest' in DoGet(_REMOTE, '/modalities'))
        self.assertTrue('echo' in DoGet(_REMOTE, '/modalities/orthanctest'))
        self.assertTrue('find' in DoGet(_REMOTE, '/modalities/orthanctest'))
        self.assertTrue('find-instance' in DoGet(_REMOTE, '/modalities/orthanctest'))
        self.assertTrue('find-patient' in DoGet(_REMOTE, '/modalities/orthanctest'))
        self.assertTrue('find-series' in DoGet(_REMOTE, '/modalities/orthanctest'))
        self.assertTrue('find-study' in DoGet(_REMOTE, '/modalities/orthanctest'))
        self.assertTrue('store' in DoGet(_REMOTE, '/modalities/orthanctest'))
        self.assertTrue('store' in DoGet(_REMOTE, '/peers/peer'))
        self.assertTrue('matlab' in DoGet(_REMOTE, '/instances/%s/frames/0' % a))
        self.assertRaises(Exception, lambda: DoGet(_REMOTE, '/tools/nope'))
        self.assertRaises(Exception, lambda: DoGet(_REMOTE, '/nope'))
        self.assertRaises(Exception, lambda: DoGet(_REMOTE, '/nope/nope.html'))
        self.assertEqual(404, DoGetRaw(_REMOTE, '/nope')[0].status)
        self.assertEqual(404, DoGetRaw(_REMOTE, '/nope/nope.html')[0].status)


    def test_echo(self):
        DoPost(_REMOTE, '/modalities/orthanctest/echo')


    def test_xml(self):
        json = DoGet(_REMOTE, '/tools', headers = { 'accept' : 'application/json' })
        xml = minidom.parseString(DoGet(_REMOTE, '/tools', headers = { 'accept' : 'application/xml' }))
        items = xml.getElementsByTagName('root')[0].getElementsByTagName('item') 
        self.assertEqual(len(items), len(json))

        self.assertTrue('dicom-conformance' in json)

        ok = False
        for i in items:
            if i.childNodes[0].data == 'dicom-conformance':
                ok = True
        self.assertTrue(ok)


    def test_googlecode_issue_16(self):
        i = UploadInstance(_REMOTE, 'Issue16.dcm')['ID']
        t = DoGet(_REMOTE, '/instances/%s/tags?simplify' % i)['FrameIncrementPointer']
        self.assertEqual('0018,1063', t)


    def test_googlecode_issue_22(self):
        s = UploadInstance(_REMOTE, 'Issue22.dcm')['ID']
        a = [
            "f804691f62197040438f4627c6b994f1",  # Frame 0
            "c69eee9a51eea3e8611e82e578897254",
            "315666be83e2d0111c77bc0996d84901",
            "3e27aa959d911172c48a1436443c72b1",
            "958642c9e7e9d232d3869faff546058c",
            "5e7ea8e3e4230cae707d143481355c59",
            "eda37f83558d858a596175aed8b2ad47",
            "486713bd2895c4ecbe0e97715ac7f80a",
            "091ef729eb169e67da8a0faa9631f9a8",
            "5aa2b8c7ffe0a483efaa8e12417686ca",
            "e2f39e85896fe58876654b94cd0b5013",
            "6fd2129e4950abbe1be053bc814d5da8",
            "c3331a8ba7a757f3d423735ab7fa81f9",
            "746f808582156734dd6b6fdfd3a0b72c",
            "8075ea2b227a70c60ea6b7b75a6bb190",
            "806b8b3e300c615099c11a5ec23465aa",
            "7c836aa298ba6eef96434579af631a11",
            "a0357dc9f4f72d73a885c33d7c287446",
            "f25ba3be1cc7d7fad95706adc199ea7d",
            "8b114c526b8cbed6cad8a3248b7b480c",
            "44e6670f127e612a2b4aa60a0d207698",
            "b8945f90fe02facf2ace24ca1ecbe0a5",
            "95c796c2fa8f59018b15cf2987b1f79b",
            "ce0a51ab30224205b44920221dc27351",  # Frame 23
            ]

        self.assertEqual(24, len(DoGet(_REMOTE, '/instances/%s/frames' % s)))
        self.assertRaises(Exception, lambda: DoGet(_REMOTE, '/instances/%s/frames/24/preview' % s))

        for i in range(len(a)):
            self.assertEqual(a[i], ComputeMD5(DoGet(_REMOTE, '/instances/%s/frames/%d/preview' % (s, i))))


    def test_googlecode_issue_19(self):
        # This is an image with "YBR_FULL" photometric interpretation, it is not supported by Orthanc
        # gdcmconv -i /home/jodogne/DICOM/GdcmDatabase/US_DataSet/HDI5000_US/3EAF5E01 -w -o Issue19.dcm

        a = UploadInstance(_REMOTE, 'Issue19.dcm')['ID']
        self.assertRaises(Exception, lambda: DoGet(_REMOTE, '/instances/941ad3c8-05d05b88-560459f9-0eae0e20-6cddd533/preview'))


    def test_googlecode_issue_37(self):
        # Same test for issues 35 and 37. Fixed in Orthanc 0.9.1
        u = UploadInstance(_REMOTE, 'Beaufix/IM-0001-0001.dcm')['ID']

        a = DoPost(_REMOTE, '/tools/find', { 'Level' : 'Series',
                                             'CaseSensitive' : True,
                                             'Query' : { 'StationName' : 'SMR4-MP3' }})
        self.assertEqual(1, len(a))


    def test_rest_find(self):
        # Upload 8 instances
        for i in range(2):
            UploadInstance(_REMOTE, 'Brainix/Flair/IM-0001-000%d.dcm' % (i + 1))
            UploadInstance(_REMOTE, 'Brainix/Epi/IM-0001-000%d.dcm' % (i + 1))
            UploadInstance(_REMOTE, 'Knee/T1/IM-0001-000%d.dcm' % (i + 1))
            UploadInstance(_REMOTE, 'Knee/T2/IM-0001-000%d.dcm' % (i + 1))

        a = DoPost(_REMOTE, '/tools/find', { 'Level' : 'Patient',
                                             'CaseSensitive' : False,
                                             'Query' : { 'PatientName' : '*n*' }})
        self.assertEqual(2, len(a))

        a = DoPost(_REMOTE, '/tools/find', { 'Level' : 'Patient',
                                             'CaseSensitive' : True,
                                             'Query' : { 'PatientName' : '*n*' }})
        self.assertEqual(0, len(a))

        a = DoPost(_REMOTE, '/tools/find', { 'Expand' : True,
                                             'Level' : 'Patient',
                                             'CaseSensitive' : False,
                                             'Query' : { 'PatientName' : '*ne*' }})
        self.assertEqual(1, len(a))
        self.assertEqual('20080822', a[0]['MainDicomTags']['PatientBirthDate'])

        a = DoPost(_REMOTE, '/tools/find', { 'Level' : 'Patient',
                                             'CaseSensitive' : True,
                                             'Query' : { 'PatientName' : '*ne*' }})
        self.assertEqual(0, len(a))

        a = DoPost(_REMOTE, '/tools/find', { 'Level' : 'Study',
                                             'CaseSensitive' : True,
                                             'Query' : { 'PatientName' : '*NE*' }})
        self.assertEqual(1, len(a))

        a = DoPost(_REMOTE, '/tools/find', { 'Level' : 'Series',
                                             'CaseSensitive' : True,
                                             'Query' : { 'PatientName' : '*NE*' }})
        self.assertEqual(2, len(a))

        a = DoPost(_REMOTE, '/tools/find', { 'Level' : 'Instance',
                                             'CaseSensitive' : True,
                                             'Query' : { 'PatientName' : '*NE*' }})
        self.assertEqual(4, len(a))

        a = DoPost(_REMOTE, '/tools/find', { 'Level' : 'Patient', 'Query' : { }})
        self.assertEqual(2, len(a))

        a = DoPost(_REMOTE, '/tools/find', { 'Level' : 'Study', 'Query' : { }})
        self.assertEqual(2, len(a))

        a = DoPost(_REMOTE, '/tools/find', { 'Level' : 'Series', 'Query' : { }})
        self.assertEqual(4, len(a))

        a = DoPost(_REMOTE, '/tools/find', { 'Level' : 'Instance', 'Query' : { }})
        self.assertEqual(8, len(a))


    def test_rest_query_retrieve(self):
        self.assertEqual(0, len(DoGet(_REMOTE, '/patients')))

        # Upload 8 instances
        for i in range(2):
            UploadInstance(_REMOTE, 'Brainix/Flair/IM-0001-000%d.dcm' % (i + 1))
            UploadInstance(_REMOTE, 'Brainix/Epi/IM-0001-000%d.dcm' % (i + 1))
            UploadInstance(_REMOTE, 'Knee/T1/IM-0001-000%d.dcm' % (i + 1))
            UploadInstance(_REMOTE, 'Knee/T2/IM-0001-000%d.dcm' % (i + 1))

        self.assertEqual(2, len(DoGet(_REMOTE, '/patients')))
        for p in DoGet(_REMOTE, '/patients'):
            DoPost(_REMOTE, '/modalities/orthanctest/store', p)
            DoDelete(_REMOTE, '/patients/%s' % p)

        for q in DoGet(_REMOTE, '/queries'):
            DoDelete(_REMOTE, '/queries/%s' % q)

        self.assertEqual(0, len(DoGet(_REMOTE, '/patients')))
        self.assertEqual(0, len(DoGet(_REMOTE, '/queries')))
        a = DoPost(_REMOTE, '/modalities/orthanctest/query', { 'Level' : 'Series',
                                                               'Query' : { 
                                                                   'PatientName' : '*NE*',
                                                                   'StudyDate' : '*',
                                                               }})['ID']
        self.assertEqual(1, len(DoGet(_REMOTE, '/queries')))

        b = DoGet(_REMOTE, '/queries/%s' % a)
        self.assertTrue('answers' in b)
        self.assertTrue('level' in b)
        self.assertTrue('modality' in b)
        self.assertTrue('query' in b)
        self.assertTrue('retrieve' in b)
        self.assertEqual('Series', DoGet(_REMOTE, '/queries/%s/level' % a))
        self.assertEqual('orthanctest', DoGet(_REMOTE, '/queries/%s/modality' % a))
        
        q = DoGet(_REMOTE, '/queries/%s/query?simplify' % a)
        self.assertEqual(2, len(q))
        self.assertTrue('PatientName' in q)
        self.assertTrue('StudyDate' in q)
        self.assertEqual('*NE*', q['PatientName'])
        self.assertEqual('*', q['StudyDate'])

        self.assertEqual(2, len(DoGet(_REMOTE, '/queries/%s/answers' % a)))

        s = DoGet(_REMOTE, '/queries/%s/answers/0' % a)
        self.assertTrue('content' in s)
        self.assertTrue('retrieve' in s)

        s = DoGet(_REMOTE, '/queries/%s/answers/0/content?simplify' % a)
        self.assertEqual('887', s['PatientID'])
        self.assertEqual('2.16.840.1.113669.632.20.121711.10000160881', s['StudyInstanceUID'])

        self.assertEqual(0, len(DoGet(_REMOTE, '/patients')))
        DoPost(_REMOTE, '/queries/%s/answers/0/retrieve' % a, 'ORTHANC')
        self.assertEqual(1, len(DoGet(_REMOTE, '/patients')))
        self.assertEqual(1, len(DoGet(_REMOTE, '/studies')))
        self.assertEqual(1, len(DoGet(_REMOTE, '/series')))
        self.assertEqual(2, len(DoGet(_REMOTE, '/instances')))

        DoPost(_REMOTE, '/queries/%s/answers/1/retrieve' % a, 'ORTHANC')
        self.assertEqual(1, len(DoGet(_REMOTE, '/patients')))
        self.assertEqual(1, len(DoGet(_REMOTE, '/studies')))
        self.assertEqual(2, len(DoGet(_REMOTE, '/series')))
        self.assertEqual(4, len(DoGet(_REMOTE, '/instances')))

        DoDelete(_REMOTE, '/queries/%s' % a)
        self.assertEqual(0, len(DoGet(_REMOTE, '/queries')))


    def test_parent(self):
        u = UploadInstance(_REMOTE, 'DummyCT.dcm')['ID']
        patient = '6816cb19-844d5aee-85245eba-28e841e6-2414fae2'
        study = 'b9c08539-26f93bde-c81ab0d7-bffaf2cb-a4d0bdd0'
        series = 'f2635388-f01d497a-15f7c06b-ad7dba06-c4c599fe'
        instance = '66a662ce-7430e543-bad44d47-0dc5a943-ec7a538d'
        self.assertEqual(instance, u);

        a = DoGet(_REMOTE, '/studies/%s/patient' % study)
        self.assertEqual('Patient', a['Type'])
        self.assertEqual(patient, a['ID'])
        
        a = DoGet(_REMOTE, '/series/%s/patient' % series)
        self.assertEqual('Patient', a['Type'])
        self.assertEqual(patient, a['ID'])
        
        a = DoGet(_REMOTE, '/series/%s/study' % series)
        self.assertEqual('Study', a['Type'])
        self.assertEqual(study, a['ID'])
        
        a = DoGet(_REMOTE, '/instances/%s/patient' % instance)
        self.assertEqual('Patient', a['Type'])
        self.assertEqual(patient, a['ID'])
        
        a = DoGet(_REMOTE, '/instances/%s/study' % instance)
        self.assertEqual('Study', a['Type'])
        self.assertEqual(study, a['ID'])
        
        a = DoGet(_REMOTE, '/instances/%s/series' % instance)
        self.assertEqual('Series', a['Type'])
        self.assertEqual(series, a['ID'])
        

    def test_shanon(self):
        def Anonymize(instance, replacements = {}):
            return DoPost(_REMOTE, '/instances/%s/anonymize' % instance, { 'Replace' : replacements }, 'application/json')

        self.assertEqual(0, len(DoGet(_REMOTE, '/instances')))
        u = UploadInstance(_REMOTE, 'DummyCT.dcm')['ID']
        self.assertEqual(1, len(DoGet(_REMOTE, '/instances')))

        tags = [ 'PatientID', 'StudyInstanceUID', 'SeriesInstanceUID', 'SOPInstanceUID', 'DeidentificationMethod' ]
        ids = [ 'ozp00SjY2xG',
                '1.2.840.113619.2.176.2025.1499492.7391.1171285944.390',
                '1.2.840.113619.2.176.2025.1499492.7391.1171285944.394',
                '1.2.840.113619.2.176.2025.1499492.7040.1171286242.109' ]

        a = ExtractDicomTags(Anonymize(u), tags)
        for i in range(4):
            self.assertNotEqual(ids[i], a[i])
        self.assertTrue(a[4].startswith('Orthanc'))

        a = ExtractDicomTags(Anonymize(u, { 'PatientName' : 'toto' }), tags)
        for i in range(4):
            self.assertNotEqual(ids[i], a[i])
        self.assertFalse(a[4].startswith('Orthanc'))

        a = ExtractDicomTags(Anonymize(u, { 'SOPInstanceUID' : 'instance' }), tags)
        self.assertEqual('instance', a[3])
        self.assertFalse(a[4].startswith('Orthanc'))

        a = ExtractDicomTags(Anonymize(u, { 'SeriesInstanceUID' : 'series' }), tags)
        self.assertEqual('series', a[2])
        self.assertFalse(a[4].startswith('Orthanc'))

        a = ExtractDicomTags(Anonymize(u, { 'StudyInstanceUID' : 'study' }), tags)
        self.assertEqual('study', a[1])
        self.assertFalse(a[4].startswith('Orthanc'))

        a = ExtractDicomTags(Anonymize(u, { 'PatientID' : 'patient' }), tags)
        self.assertEqual('patient', a[0])
        self.assertFalse(a[4].startswith('Orthanc'))

        a = ExtractDicomTags(Anonymize(u, { 'PatientID' : 'patient',
                                            'StudyInstanceUID' : 'study',
                                            'SeriesInstanceUID' : 'series',
                                            'SOPInstanceUID' : 'instance' }), tags)
        self.assertEqual('patient', a[0])
        self.assertFalse(a[4].startswith('Orthanc'))

        self.assertEqual(1, len(DoGet(_REMOTE, '/instances')))


    def test_shanon_2(self):
        def Modify(instance, replacements = {}):
            return DoPost(_REMOTE, '/instances/%s/modify' % instance, { 'Replace' : replacements }, 'application/json')

        self.assertEqual(0, len(DoGet(_REMOTE, '/instances')))
        u = UploadInstance(_REMOTE, 'DummyCT.dcm')['ID']
        self.assertEqual(1, len(DoGet(_REMOTE, '/instances')))

        tags = [ 'PatientID', 'StudyInstanceUID', 'SeriesInstanceUID', 'SOPInstanceUID', 'DeidentificationMethod' ]
        ids = [ 'ozp00SjY2xG',
                '1.2.840.113619.2.176.2025.1499492.7391.1171285944.390',
                '1.2.840.113619.2.176.2025.1499492.7391.1171285944.394',
                '1.2.840.113619.2.176.2025.1499492.7040.1171286242.109' ]

        a = ExtractDicomTags(Modify(u), tags)
        self.assertEqual(ids[0], a[0])
        self.assertEqual(ids[1], a[1])
        self.assertEqual(ids[2], a[2])
        self.assertNotEqual(ids[3], a[3])
        self.assertEqual(0, len(a[4]))

        a = ExtractDicomTags(Modify(u, { 'SOPInstanceUID' : 'instance' }), tags)
        self.assertEqual(ids[0], a[0])
        self.assertEqual(ids[1], a[1])
        self.assertEqual(ids[2], a[2])
        self.assertEqual('instance', a[3])

        a = ExtractDicomTags(Modify(u, { 'SeriesInstanceUID' : 'series' }), tags)
        self.assertEqual(ids[0], a[0])
        self.assertEqual(ids[1], a[1])
        self.assertEqual('series', a[2])
        self.assertNotEqual(ids[3], a[3])

        a = ExtractDicomTags(Modify(u, { 'StudyInstanceUID' : 'study' }), tags)
        self.assertEqual(ids[0], a[0])
        self.assertEqual('study', a[1])
        self.assertNotEqual(ids[2], a[2])
        self.assertNotEqual(ids[3], a[3])

        a = ExtractDicomTags(Modify(u, { 'PatientID' : 'patient' }), tags)
        self.assertEqual('patient', a[0])
        self.assertNotEqual(ids[1], a[1])
        self.assertNotEqual(ids[2], a[2])
        self.assertNotEqual(ids[3], a[3])

        a = ExtractDicomTags(Modify(u, { 'PatientID' : 'patient',
                                         'StudyInstanceUID' : 'study',
                                         'SeriesInstanceUID' : 'series',
                                         'SOPInstanceUID' : 'instance' }), tags)
        self.assertEqual('patient', a[0])
        self.assertEqual('study', a[1])
        self.assertEqual('series', a[2])
        self.assertEqual('instance', a[3])

        self.assertEqual(1, len(DoGet(_REMOTE, '/instances')))
        

    def test_instances_tags(self):
        a = UploadInstance(_REMOTE, 'Knee/T1/IM-0001-0001.dcm')['ID']
        b = UploadInstance(_REMOTE, 'Knee/T2/IM-0001-0001.dcm')['ID']
        #a = UploadInstance(_REMOTE, 'Cardiac/MR.X.1.2.276.0.7230010.3.1.4.2831157719.2256.1336386937.676343')['ID']
        #b = UploadInstance(_REMOTE, 'Cardiac/MR.X.1.2.276.0.7230010.3.1.4.2831157719.2256.1336386925.676329')['ID']

        i = DoGet(_REMOTE, '/patients/%s/instances-tags?simplify' % DoGet(_REMOTE, '/patients')[0])
        self.assertEqual(2, len(i))
        self.assertEqual('887', i[i.keys()[0]]['PatientID'])
        self.assertEqual('887', i[i.keys()[1]]['PatientID'])

        i = DoGet(_REMOTE, '/patients/%s/instances-tags?simplify' % DoGet(_REMOTE, '/studies')[0])
        self.assertEqual(2, len(i))
        self.assertEqual('887', i[i.keys()[0]]['PatientID'])
        self.assertEqual('887', i[i.keys()[1]]['PatientID'])

        self.assertEqual(2, len(DoGet(_REMOTE, '/series')))
        i = DoGet(_REMOTE, '/patients/%s/instances-tags?simplify' % DoGet(_REMOTE, '/series')[0])
        self.assertEqual(1, len(i))
        self.assertEqual('887', i[i.keys()[0]]['PatientID'])
        
        i = DoGet(_REMOTE, '/patients/%s/instances-tags?simplify' % DoGet(_REMOTE, '/series')[1])
        self.assertEqual(1, len(i))
        self.assertEqual('887', i[i.keys()[0]]['PatientID'])


    def test_lookup(self):
        a = DoPost(_REMOTE, '/tools/lookup', 'ozp00SjY2xG')
        self.assertEqual(0, len(a))

        UploadInstance(_REMOTE, 'DummyCT.dcm')

        a = DoPost(_REMOTE, '/tools/lookup', 'ozp00SjY2xG')
        self.assertEqual(1, len(a))
        self.assertEqual('Patient', a[0]['Type'])
        self.assertEqual('6816cb19-844d5aee-85245eba-28e841e6-2414fae2', a[0]['ID'])
        self.assertEqual('/patients/%s' % a[0]['ID'], a[0]['Path'])
        
        a = DoPost(_REMOTE, '/tools/lookup', '1.2.840.113619.2.176.2025.1499492.7391.1171285944.390')
        self.assertEqual(1, len(a))
        self.assertEqual('Study', a[0]['Type'])
        self.assertEqual('b9c08539-26f93bde-c81ab0d7-bffaf2cb-a4d0bdd0', a[0]['ID'])
        self.assertEqual('/studies/%s' % a[0]['ID'], a[0]['Path'])
        
        a = DoPost(_REMOTE, '/tools/lookup', '1.2.840.113619.2.176.2025.1499492.7391.1171285944.394')
        self.assertEqual(1, len(a))
        self.assertEqual('Series', a[0]['Type'])
        self.assertEqual('f2635388-f01d497a-15f7c06b-ad7dba06-c4c599fe', a[0]['ID'])
        self.assertEqual('/series/%s' % a[0]['ID'], a[0]['Path'])
        
        a = DoPost(_REMOTE, '/tools/lookup', '1.2.840.113619.2.176.2025.1499492.7040.1171286242.109')
        self.assertEqual(1, len(a))
        self.assertEqual('Instance', a[0]['Type'])
        self.assertEqual('66a662ce-7430e543-bad44d47-0dc5a943-ec7a538d', a[0]['ID'])
        self.assertEqual('/instances/%s' % a[0]['ID'], a[0]['Path'])

        DropOrthanc(_REMOTE)
        a = DoPost(_REMOTE, '/tools/lookup', '3113719P')
        self.assertEqual(0, len(a))


    def test_autorouting(self):
        knee1 = 'Knee/T1/IM-0001-0001.dcm'
        knee2 = 'Knee/T2/IM-0001-0002.dcm'
        other = 'Brainix/Flair/IM-0001-0001.dcm'

        # Check that this version is >= 0.8.0
        self.assertTrue(IsDefinedInLua(_REMOTE, '_InitializeJob'))
        self.assertTrue('orthanctest' in DoGet(_REMOTE, '/modalities'))

        UploadInstance(_REMOTE, knee1)
        self.assertEqual(0, len(DoGet(_LOCAL, '/instances')))

        DropOrthanc(_REMOTE)
        DropOrthanc(_LOCAL)
        InstallLuaScript('Lua/Autorouting.lua')
        UploadInstance(_REMOTE, knee1)
        UploadInstance(_REMOTE, knee2)
        UploadInstance(_REMOTE, other)
        WaitEmpty(_REMOTE)
        UninstallLuaCallbacks()
        self.assertEqual(3, len(DoGet(_LOCAL, '/instances')))

        DropOrthanc(_REMOTE)
        DropOrthanc(_LOCAL)
        InstallLuaScript('Lua/AutoroutingConditional.lua')
        UploadInstance(_REMOTE, knee1)
        UploadInstance(_REMOTE, knee2)
        UploadInstance(_REMOTE, other)
        WaitEmpty(_REMOTE)
        UninstallLuaCallbacks()
        self.assertEqual(2, len(DoGet(_LOCAL, '/instances')))
        
        DropOrthanc(_REMOTE)
        DropOrthanc(_LOCAL)
        InstallLuaScript('Lua/AutoroutingModification.lua')
        UploadInstance(_REMOTE, knee1)
        WaitEmpty(_REMOTE)
        UninstallLuaCallbacks()
        i = DoGet(_LOCAL, '/instances')
        self.assertEqual(1, len(i))
        
        with tempfile.NamedTemporaryFile(delete = True) as f:
            f.write(DoGet(_LOCAL, '/instances/%s/file' % i[0]))
            f.flush()
            routed = subprocess.check_output([ FindExecutable('dcm2xml'), f.name ])
            self.assertEqual('My Medical Device', re.search('"StationName">(.*?)<', routed).group(1).strip())
            self.assertEqual(None, re.search('"MilitaryRank"', routed))
            self.assertEqual(None, re.search('"0051,0010"', routed))  # A private tag


    def test_storescu_rf(self):
        i = UploadInstance(_REMOTE, 'KarstenHilbertRF.dcm')['ID']
        self.assertEqual(0, len(DoGet(_LOCAL, '/instances')))
        j = DoPost(_REMOTE, '/modalities/orthanctest/store', str(i), 'text/plain')
        self.assertEqual(1, len(DoGet(_LOCAL, '/instances')))


    def test_anonymize_instance(self):
        def AnonymizeAndUpload(instanceId, parameters):
            return DoPost(_REMOTE, '/instances', DoPost(_REMOTE, '/instances/%s/anonymize' % instanceId, parameters,
                                               'application/json'), 'application/dicom')['ID']

        def ModifyAndUpload(instanceId, parameters):
            return DoPost(_REMOTE, '/instances', DoPost(_REMOTE, '/instances/%s/modify' % instanceId, parameters,
                                               'application/json'), 'application/dicom')['ID']

        a = UploadInstance(_REMOTE, 'PrivateMDNTags.dcm')['ID']
        s1 = DoGet(_REMOTE, '/instances/%s/content/PatientName' % a)
        s2 = DoGet(_REMOTE, '/instances/%s/content/00e1-10c2' % a)  # Some private tag
        s3 = DoGet(_REMOTE, '/instances/%s/content/StudyDescription' % a)
        s4 = DoGet(_REMOTE, '/instances/%s/content/SeriesDescription' % a)
        s5 = DoGet(_REMOTE, '/instances/%s/content/InstitutionName' % a)
        
        b = AnonymizeAndUpload(a, '{}')
        self.assertNotEqual(s1, DoGet(_REMOTE, '/instances/%s/content/PatientName' % b))
        self.assertRaises(Exception, lambda: DoGet(_REMOTE, '/instances/%s/content/00e1-10c2' % b))
        
        # Keep private tag (only OK since Orthanc 0.8.0)
        b = AnonymizeAndUpload(a, '{"Keep":["00e1-10c2"]}')  
        self.assertNotEqual(s1, DoGet(_REMOTE, '/instances/%s/content/PatientName' % b))
        self.assertEqual(s2, DoGet(_REMOTE, '/instances/%s/content/00e1-10c2' % b))
        
        b = AnonymizeAndUpload(a, '{"Keep":["00e1,10c2","PatientName"]}')
        self.assertEqual(s1, DoGet(_REMOTE, '/instances/%s/content/PatientName' % b))
        self.assertEqual(s2, DoGet(_REMOTE, '/instances/%s/content/00e1-10c2' % b))
        
        b = AnonymizeAndUpload(a, '{"Keep":["PatientName"],"Replace":{"00e1,10c2":"Hello"}}')
        self.assertEqual(s1, DoGet(_REMOTE, '/instances/%s/content/PatientName' % b))
        self.assertTrue(DoGet(_REMOTE, '/instances/%s/content/00e1-10c2' % b).startswith('Hello'))

        # Examples from the Wiki
        b = AnonymizeAndUpload(a, '{"Replace":{"PatientName":"hello","0010-0020":"world"},"Keep":["StudyDescription", "SeriesDescription"],"KeepPrivateTags": null}')
        self.assertEqual('hello', DoGet(_REMOTE, '/instances/%s/content/0010-0010' % b).strip())
        self.assertEqual('world', DoGet(_REMOTE, '/instances/%s/content/PatientID' % b).strip())
        self.assertEqual(s3, DoGet(_REMOTE, '/instances/%s/content/0008,1030' % b))
        self.assertEqual(s4, DoGet(_REMOTE, '/instances/%s/content/0008,103e' % b))
        self.assertEqual(s4, DoGet(_REMOTE, '/instances/%s/content/0008-103E' % b))
        self.assertEqual(s2, DoGet(_REMOTE, '/instances/%s/content/00e1-10c2' % b))
        DoGet(_REMOTE, '/instances/%s/content/InstitutionName' % a)
        self.assertRaises(Exception, lambda: DoGet(_REMOTE, '/instances/%s/content/InstitutionName' % b))

        b = ModifyAndUpload(a, '{"Replace":{"PatientName":"hello","PatientID":"world"},"Remove":["InstitutionName"],"RemovePrivateTags": null}')
        self.assertEqual('hello', DoGet(_REMOTE, '/instances/%s/content/0010-0010' % b).strip())
        self.assertEqual('world', DoGet(_REMOTE, '/instances/%s/content/PatientID' % b).strip())
        self.assertEqual(s3, DoGet(_REMOTE, '/instances/%s/content/0008,1030' % b))
        self.assertEqual(s4, DoGet(_REMOTE, '/instances/%s/content/0008,103e' % b))
        self.assertRaises(Exception, lambda: DoGet(_REMOTE, '/instances/%s/content/00e1-10c2' % b))
        self.assertRaises(Exception, lambda: DoGet(_REMOTE, '/instances/%s/content/InstitutionName' % b))

        b = ModifyAndUpload(a, '{"Replace":{"PatientName":"hello","PatientID":"world"}}')
        self.assertEqual('hello', DoGet(_REMOTE, '/instances/%s/content/0010-0010' % b).strip())
        self.assertEqual('world', DoGet(_REMOTE, '/instances/%s/content/PatientID' % b).strip())
        self.assertEqual(s2, DoGet(_REMOTE, '/instances/%s/content/00e1,10c2' % b))
        self.assertEqual(s3, DoGet(_REMOTE, '/instances/%s/content/0008,1030' % b))
        self.assertEqual(s4, DoGet(_REMOTE, '/instances/%s/content/0008-103E' % b))
        self.assertEqual(s5, DoGet(_REMOTE, '/instances/%s/content/InstitutionName' % b))


        # Test modify non-existing
        i = DoPost(_REMOTE, '/tools/create-dicom',
                   json.dumps({
                    'PatientName' : 'Jodogne',
                    'Modality' : 'CT',
                    }))['ID']

        self.assertEqual('Jodogne', DoGet(_REMOTE, '/instances/%s/content/PatientName' % i).strip())
        self.assertRaises(Exception, lambda: DoGet(_REMOTE, '/instances/%s/content/StudyDescription' % i))
        self.assertEqual('CT', DoGet(_REMOTE, '/instances/%s/content/Modality' % i).strip())

        b = ModifyAndUpload(i, '{"Replace":{"StudyDescription":"hello","Modality":"world"}}')
        self.assertEqual('Jodogne', DoGet(_REMOTE, '/instances/%s/content/PatientName' % b).strip())
        self.assertEqual('hello', DoGet(_REMOTE, '/instances/%s/content/StudyDescription' % b).strip())
        self.assertEqual('world', DoGet(_REMOTE, '/instances/%s/content/Modality' % b).strip())


    def test_incoming_jpeg(self):
        def storescu(image, acceptUnknownSopClassUid):
            if acceptUnknownSopClassUid:
                tmp = [ '-xf', GetDatabasePath('UnknownSopClassUid.cfg'), 'Default' ]
            else:
                tmp = [ '-xs' ]

            with open(os.devnull, 'w') as FNULL:
                subprocess.check_call([ FindExecutable('storescu') ] + tmp +
                                      [ _REMOTE['Server'], str(_REMOTE['DicomPort']),
                                        GetDatabasePath(image) ],
                                      stderr = FNULL)

        self.assertEqual(0, len(DoGet(_REMOTE, '/patients')))
        InstallLuaScript('Lua/TransferSyntaxDisable.lua')
        self.assertRaises(Exception, lambda: storescu('Knix/Loc/IM-0001-0001.dcm', False))
        self.assertRaises(Exception, lambda: storescu('UnknownSopClassUid.dcm', True))
        self.assertEqual(0, len(DoGet(_REMOTE, '/patients')))
        InstallLuaScript('Lua/TransferSyntaxEnable.lua')
        DoPost(_REMOTE, '/tools/execute-script', "print('All special transfer syntaxes are now accepted')")
        storescu('Knix/Loc/IM-0001-0001.dcm', False)
        storescu('UnknownSopClassUid.dcm', True)
        self.assertEqual(2, len(DoGet(_REMOTE, '/patients')))


    def test_storescu_jpeg(self):
        self.assertEqual(0, len(DoGet(_REMOTE, '/exports')['Exports']))

        knixStudy = 'b9c08539-26f93bde-c81ab0d7-bffaf2cb-a4d0bdd0'
        i = UploadInstance(_REMOTE, 'Knix/Loc/IM-0001-0001.dcm')['ID']

        # This is JPEG lossless
        self.assertEqual('1.2.840.10008.1.2.4.70', DoGet(_REMOTE, '/instances/%s/header?simplify' % i)['TransferSyntaxUID'])

        UploadInstance(_REMOTE, 'Knix/Loc/IM-0001-0002.dcm')
        UploadInstance(_REMOTE, 'Knix/Loc/IM-0001-0003.dcm')

        a = UploadInstance(_REMOTE, 'Brainix/Flair/IM-0001-0001.dcm')['ID']
        b = UploadInstance(_REMOTE, 'ColorTestImageJ.dcm')['ID']
        self.assertEqual(0, len(DoGet(_LOCAL, '/instances')))
        DoPost(_REMOTE, '/modalities/orthanctest/store', [ knixStudy, a, b ])
        self.assertEqual(5, len(DoGet(_LOCAL, '/instances')))

        self.assertEqual(3, len(DoGet(_REMOTE, '/exports')['Exports']))

        DropOrthanc(_REMOTE)
        self.assertEqual(0, len(DoGet(_REMOTE, '/exports')['Exports']))


    def test_pixel_data(self):
        jpeg = UploadInstance(_REMOTE, 'Knix/Loc/IM-0001-0001.dcm')['ID']
        color = UploadInstance(_REMOTE, 'ColorTestImageJ.dcm')['ID']
        phenix = UploadInstance(_REMOTE, 'Phenix/IM-0001-0001.dcm')['ID']
        
        phenixSize = 358 * 512 * 2
        colorSize = 1000 * 1000 * 3
        jpegSize = 51918

        self.assertEqual(1, len(DoGet(_REMOTE, '/instances/%s/content/7fe0-0010' % phenix)))
        self.assertEqual(1, len(DoGet(_REMOTE, '/instances/%s/content/7fe0-0010' % color)))
        self.assertEqual(2, len(DoGet(_REMOTE, '/instances/%s/content/7fe0-0010' % jpeg)))
        
        self.assertEqual(0, len(DoGet(_REMOTE, '/instances/%s/content/7fe0-0010/0' % jpeg)))
        self.assertEqual(jpegSize, len(DoGet(_REMOTE, '/instances/%s/content/7fe0-0010/1' % jpeg)))       

        self.assertEqual(phenixSize, len(DoGet(_REMOTE, '/instances/%s/content/7fe0-0010/0' % phenix)))
        self.assertEqual(colorSize, len(DoGet(_REMOTE, '/instances/%s/content/7fe0-0010/0' % color)))


    def test_decode_brainix(self):
        brainix = [
            UploadInstance(_REMOTE, 'Brainix/Epi/IM-0001-0001.dcm')['ID'], # (*)
            UploadInstance(_REMOTE, 'Formats/JpegLossless.dcm')['ID'],  # JPEG-LS, same as (*) (since Orthanc 0.7.6)
            UploadInstance(_REMOTE, 'Formats/Jpeg.dcm')['ID'],  # JPEG, same as (*) (since Orthanc 0.7.6)
            ]
        h = '6fb11b932d535c2be04beabd99793ff8'
        maxValue = 426.0

        truth = Image.open(GetDatabasePath('Formats/Brainix.png'))
        for i in brainix:
            self.AssertSameImages(truth.getdata(), '/instances/%s/image-int16' % i)
            self.AssertSameImages(truth.getdata(), '/instances/%s/image-uint16' % i)

        truth2 = map(lambda x: min(255, x), truth.getdata())
        for i in brainix:
            self.AssertSameImages(truth2, '/instances/%s/image-uint8' % i)

        truth2 = map(lambda x: x * 255.0 / maxValue, truth.getdata())
        for i in brainix:
            self.AssertSameImages(truth2, '/instances/%s/preview' % i)

        for i in brainix:
            self.assertEqual(h, ComputeMD5(DoGet(_REMOTE, '/instances/%s/matlab' % i)))


    def test_decode_color(self):
        imagej = UploadInstance(_REMOTE, 'ColorTestImageJ.dcm')['ID']
        color = UploadInstance(_REMOTE, 'ColorTestMalaterre.dcm')['ID']

        for i in [ imagej, color ]:
            for j in [ 'image-uint8', 'image-uint16', 'image-int16' ]:
                self.assertRaises(Exception, lambda: DoGet(_REMOTE, '/instances/%s/%s' % (i, j)))

        self.assertEqual('c14c687f7a1ea9fe022479fc87c67274', ComputeMD5(DoGet(_REMOTE, '/instances/%s/preview' % imagej)))
        self.assertEqual('a87d122918a56f803bcfe9d2586b9125', ComputeMD5(DoGet(_REMOTE, '/instances/%s/preview' % color)))

        self.assertEqual('30cc46bfa7aba77a40e4178f6184c25a', ComputeMD5(DoGet(_REMOTE, '/instances/%s/matlab' % imagej)))
        self.assertEqual('ff195005cef06b59666fd220a9b4cd9a', ComputeMD5(DoGet(_REMOTE, '/instances/%s/matlab' % color)))


    def test_decode_rf(self):
        rf = UploadInstance(_REMOTE, 'KarstenHilbertRF.dcm')['ID']
        truth = Image.open(GetDatabasePath('Formats/KarstenHilbertRF.png'))

        self.AssertSameImages(truth.getdata(), '/instances/%s/image-uint8' % rf)
        self.AssertSameImages(truth.getdata(), '/instances/%s/image-uint16' % rf)
        self.AssertSameImages(truth.getdata(), '/instances/%s/image-int16' % rf)
        self.AssertSameImages(truth.getdata(), '/instances/%s/preview' % rf)

        self.assertEqual('42254d70efd2f4a1b8f3455909689f0e', ComputeMD5(DoGet(_REMOTE, '/instances/%s/matlab' % rf)))


    def test_decode_multiframe(self):
        mf = UploadInstance(_REMOTE, 'Multiframe.dcm')['ID']

        # Test the first frame
        truth = Image.open(GetDatabasePath('Formats/Multiframe0.png'))
        self.AssertSameImages(truth.getdata(), '/instances/%s/image-uint8' % mf)
        self.AssertSameImages(truth.getdata(), '/instances/%s/image-uint16' % mf)
        self.AssertSameImages(truth.getdata(), '/instances/%s/image-int16' % mf)
        self.AssertSameImages(truth.getdata(), '/instances/%s/preview' % mf)
        self.assertEqual('9812b99d93bbcd4e7684ded089b5dfb3', ComputeMD5(DoGet(_REMOTE, '/instances/%s/matlab' % mf)))

        self.AssertSameImages(truth.getdata(), '/instances/%s/frames/0/image-uint16' % mf)

        # Test the last frame
        truth = Image.open(GetDatabasePath('Formats/Multiframe75.png'))
        self.AssertSameImages(truth.getdata(), '/instances/%s/frames/75/image-uint16' % mf)


    def test_decode_signed(self):
        signed = UploadInstance(_REMOTE, 'SignedCT.dcm')['ID']
        minValue = -2000
        maxValue = 4042

        truth = Image.open(GetDatabasePath('Formats/SignedCT.png'))
        self.AssertSameImages(truth.getdata(), '/instances/%s/image-int16' % signed)

        truth2 = map(lambda x: 0 if x >= 32768 else x, truth.getdata())
        self.AssertSameImages(truth2, '/instances/%s/image-uint16' % signed)

        truth3 = map(lambda x: 255 if x >= 256 else x, truth2)
        self.AssertSameImages(truth3, '/instances/%s/image-uint8' % signed)

        tmp = map(lambda x: x - 65536 if x >= 32768 else x, truth.getdata())
        tmp = map(lambda x: (255.0 * (x - minValue)) / (maxValue - minValue), tmp)
        self.AssertSameImages(tmp, '/instances/%s/preview' % signed)

        self.assertEqual('b57e6c872a3da50877c7da689b03a444', ComputeMD5(DoGet(_REMOTE, '/instances/%s/matlab' % signed)))


    def test_googlecode_issue_32(self):
        f = UploadInstance(_REMOTE, 'Issue32.dcm')['ID']
        tags = DoGet(_REMOTE, '/instances/%s/tags?simplify' % f)
        self.assertEqual(u'Рентгенография', tags['SeriesDescription'])
        self.assertEqual(u'Таз', tags['BodyPartExamined'])
        self.assertEqual(u'Прямая', tags['ViewPosition'])


    def test_encodings(self):
        # Latin-1 (ISO_IR 100)
        brainix = UploadInstance(_REMOTE, 'Brainix/Epi/IM-0001-0001.dcm')['ID']
        tags = DoGet(_REMOTE, '/instances/%s/tags?simplify' % brainix)
        self.assertEqual(u'IRM cérébrale, neuro-crâne', tags['StudyDescription'])

        # Latin-2 (ISO_IR 101)
        a = UploadInstance(_REMOTE, 'MarekLatin2.dcm')['ID']
        i = DoGet(_REMOTE, '/instances/%s/simplified-tags' % a)
        # dcm2xml MarekLatin2.dcm | iconv -f latin2 -t utf-8 | xmllint --format -
        self.assertEqual('Imię i Nazwisko osoby opisującej', 
                         i['ContentSequence'][4]['ConceptNameCodeSequence'][0]['CodeMeaning'].encode('utf-8'))
        

    def test_storescu_custom_aet(self):
        # This tests a feature introduced in Orthanc 0.9.1: "Custom
        # setting of the local AET during C-Store SCU (both in Lua and
        # in the REST API)."
        # https://groups.google.com/forum/#!msg/orthanc-users/o5qMULformU/wZjW2iSaMcAJ

        self.assertEqual(0, len(DoGet(_LOCAL, '/patients')))
        
        a = UploadInstance(_REMOTE, 'Knee/T1/IM-0001-0001.dcm')
        b = UploadInstance(_REMOTE, 'Knee/T1/IM-0001-0002.dcm')
        c = UploadInstance(_REMOTE, 'Knee/T1/IM-0001-0003.dcm')

        j = DoPost(_REMOTE, '/modalities/orthanctest/store', {
            'LocalAet' : 'YOP',
            'Resources' : [ a['ID'], b['ID'] ]
        })

        self.assertEqual(2, len(DoGet(_LOCAL, '/instances')))
        self.assertEqual('YOP', DoGet(_LOCAL, '/instances/%s/metadata/RemoteAET' % a['ID']))

        DropOrthanc(_LOCAL)
        self.assertEqual(0, len(DoGet(_LOCAL, '/instances')))

        j = DoPost(_REMOTE, '/modalities/orthanctest/store', {
            'Resources' : [ c['ID'] ]
        })

        self.assertEqual(1, len(DoGet(_LOCAL, '/instances')))
        self.assertEqual('ORTHANC', DoGet(_LOCAL, '/instances/%s/metadata/RemoteAET' % c['ID']))

        DropOrthanc(_REMOTE)        
        DropOrthanc(_LOCAL)        

        InstallLuaScript('Lua/AutoroutingChangeAet.lua')
        DoPost(_REMOTE, '/tools/execute-script', 'aet = "HELLO"', 'application/lua')

        self.assertEqual(0, len(DoGet(_LOCAL, '/instances')))
        UploadInstance(_REMOTE, 'Knee/T1/IM-0001-0001.dcm')
        WaitEmpty(_REMOTE)
        self.assertEqual(1, len(DoGet(_LOCAL, '/instances')))
        self.assertEqual('HELLO', DoGet(_LOCAL, '/instances/%s/metadata/RemoteAET' % a['ID']))

        DoPost(_REMOTE, '/tools/execute-script', 'aet = nill', 'application/lua')
        UploadInstance(_REMOTE, 'Knee/T1/IM-0001-0002.dcm')
        WaitEmpty(_REMOTE)
        self.assertEqual(2, len(DoGet(_LOCAL, '/instances')))
        self.assertEqual('ORTHANC', DoGet(_LOCAL, '/instances/%s/metadata/RemoteAET' % b['ID']))

    def test_resources_since_limit(self):
        # Upload 16 instances
        for i in range(4):
            UploadInstance(_REMOTE, 'Brainix/Flair/IM-0001-000%d.dcm' % (i + 1))
            UploadInstance(_REMOTE, 'Brainix/Epi/IM-0001-000%d.dcm' % (i + 1))
            UploadInstance(_REMOTE, 'Knee/T1/IM-0001-000%d.dcm' % (i + 1))
            UploadInstance(_REMOTE, 'Knee/T2/IM-0001-000%d.dcm' % (i + 1))

        self.assertEqual(2, len(DoGet(_REMOTE, '/patients')))
        self.assertEqual(2, len(DoGet(_REMOTE, '/studies')))
        self.assertEqual(4, len(DoGet(_REMOTE, '/series')))
        self.assertEqual(16, len(DoGet(_REMOTE, '/instances')))

        self.assertRaises(Exception, lambda: DoGet(_REMOTE, '/patients&since=10' % i))
        self.assertRaises(Exception, lambda: DoGet(_REMOTE, '/patients&limit=10' % i))

        self.assertEqual(0, len(DoGet(_REMOTE, '/patients?since=0&limit=0')))
        self.assertEqual(2, len(DoGet(_REMOTE, '/patients?since=0&limit=100')))
        self.assertEqual(2, len(DoGet(_REMOTE, '/studies?since=0&limit=100')))
        self.assertEqual(4, len(DoGet(_REMOTE, '/series?since=0&limit=100')))
        self.assertEqual(16, len(DoGet(_REMOTE, '/instances?since=0&limit=100')))
        self.assertEqual(1, len(DoGet(_REMOTE, '/patients?since=1&limit=100')))
        self.assertEqual(0, len(DoGet(_REMOTE, '/patients?since=2&limit=100')))
        self.assertEqual(0, len(DoGet(_REMOTE, '/patients?since=3&limit=100')))
        self.assertEqual(1, len(DoGet(_REMOTE, '/studies?since=1&limit=100')))
        self.assertEqual(3, len(DoGet(_REMOTE, '/series?since=1&limit=100')))
        self.assertEqual(2, len(DoGet(_REMOTE, '/series?since=2&limit=100')))
        self.assertEqual(1, len(DoGet(_REMOTE, '/series?since=3&limit=100')))
        self.assertEqual(0, len(DoGet(_REMOTE, '/series?since=4&limit=100')))
        self.assertEqual(0, len(DoGet(_REMOTE, '/series?since=100&limit=100')))
        self.assertEqual(15, len(DoGet(_REMOTE, '/instances?since=1&limit=100')))

        for limit in [ 1, 2, 3, 7, 16, 17 ]:
            s = {}
            since = 0
            while True:
                t = DoGet(_REMOTE, '/instances?since=%d&limit=%d' % (since, limit))
                if len(t) == 0:
                    break

                since += len(t)
                for i in t:
                    s[i] = None

            self.assertEqual(16, len(s))
            for instance in DoGet(_REMOTE, '/instances'):
                self.assertTrue(instance in s)


    def test_create_pdf(self):
        # Upload 4 instances
        brainixInstance = UploadInstance(_REMOTE, 'Brainix/Flair/IM-0001-0001.dcm')['ID']
        UploadInstance(_REMOTE, 'Brainix/Epi/IM-0001-0001.dcm')
        UploadInstance(_REMOTE, 'Knee/T1/IM-0001-0001.dcm')
        UploadInstance(_REMOTE, 'Knee/T2/IM-0001-0001.dcm')
        
        brainixPatient = '16738bc3-e47ed42a-43ce044c-a3414a45-cb069bd0'
        brainixStudy = '27f7126f-4f66fb14-03f4081b-f9341db2-53925988'
        brainixEpi = '2ac1316d-3e432022-62eabff2-c59f5475-9b1ac3f8'

        with open(GetDatabasePath('HelloWorld.pdf'), 'rb') as f:
            pdf = f.read()

        i = DoPost(_REMOTE, '/tools/create-dicom',
                   json.dumps({
                       'Tags' : {
                           'PatientName' : 'Jodogne',
                           'Modality' : 'CT',
                       },
                       'Content' : 'data:application/pdf;base64,' + base64.b64encode(pdf)
                   }))

        self.assertEqual('Jodogne', DoGet(_REMOTE, '/instances/%s/content/PatientName' % i['ID']).strip())
        self.assertEqual('OT', DoGet(_REMOTE, '/instances/%s/content/Modality' % i['ID']).strip())

        b = DoGet(_REMOTE, '/instances/%s/content/0042-0011' % i['ID'])
        self.assertEqual(len(b), len(pdf) + 1)
        self.assertEqual(ComputeMD5(b), ComputeMD5(pdf + '\0'))

        self.assertRaises(Exception, lambda: DoPost(_REMOTE, '/tools/create-dicom',
                                                    json.dumps({
                                                        'Parent' : brainixPatient,
                                                        'Tags' : {
                                                            'PatientName' : 'Jodogne',
                                                        }
                                                    })))

        i = DoPost(_REMOTE, '/tools/create-dicom',
                   json.dumps({
                       'Parent' : brainixPatient,
                       'Tags' : { 'StudyDescription' : 'PDF^Patient' },
                       'Content' : 'data:application/pdf;base64,' + base64.b64encode(pdf)
                   }))
        
        self.assertEqual(brainixPatient, DoGet(_REMOTE, '/instances/%s/patient' % i['ID'])['ID'])

        i = DoPost(_REMOTE, '/tools/create-dicom',
                   json.dumps({
                       'Parent' : brainixStudy,
                       'Tags' : { 'SeriesDescription' : 'PDF^Study' },
                       'Content' : 'data:application/pdf;base64,' + base64.b64encode(pdf)
                   }))
        
        self.assertEqual(brainixStudy, DoGet(_REMOTE, '/instances/%s/study' % i['ID'])['ID'])

        i = DoPost(_REMOTE, '/tools/create-dicom',
                   json.dumps({
                       'Parent' : brainixEpi,
                       'Tags' : { 'SpecificCharacterSet' : 'ISO_IR 13' },
                       'Content' : 'data:application/pdf;base64,' + base64.b64encode(pdf)
                   }))
        
        self.assertEqual(brainixEpi, DoGet(_REMOTE, '/instances/%s/series' % i['ID'])['ID'])

        b = DoGet(_REMOTE, '/instances/%s/pdf' % i['ID'])
        self.assertEqual(len(b), len(pdf))
        self.assertEqual(ComputeMD5(b), ComputeMD5(pdf))

        self.assertRaises(Exception, lambda: DoGet(_REMOTE, '/instances/%s/pdf' % brainixInstance))


    def test_create_series(self):
        i = DoPost(_REMOTE, '/tools/create-dicom',
                   json.dumps({
                    'Tags' : {
                        'SpecificCharacterSet' : 'ISO_IR 100',
                        'PatientName' : 'Sébastien Jodogne',
                        'Modality' : 'CT',
                        },
                    'Content' : [
                        {
                            'Content': 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAUAAAAFCAYAAACNbyblAAAAHElEQVQI12P4//8/w38GIAXDIBKE0DHxgljNBAAO9TXL0Y4OHwAAAABJRU5ErkJggg==', # red dot in RGBA
                            'Tags' : { 'ImageComments' : 'Tutu' }
                            },
                        'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAAoUlEQVQ4jZ2SWw3EIBREjwUsYAELa2EtoAULFUCyXAtroRZqoRbox254BdLC/DZnZjoXWJFgCDg8egW2CBEhEnDzyRk+Ecxz2KP/0AL8S99T+jQccAVs22qKwAuPuq0uyNg9cPLh3am+pe/dkHLZtqJHj6vXJrZ7nvzvxxgemXgUwnGfXqpee09mUwp8m022OYP6bLF7mVuVe0y/umxinsAXRd9z0k1ubWsAAAAASUVORK5CYII=',
                        ]
                    }))

        s = DoGet(_REMOTE, i['Path'])
        self.assertEqual('Series', s['Type'])
        self.assertEqual(s['ID'], i['ID'])
        self.assertEqual(2, len(s['Instances']))
        self.assertEqual(2, s['ExpectedNumberOfInstances'])
        self.assertEqual('Complete', s['Status'])

        a = DoGet(_REMOTE, '/instances/%s/tags?simplify' % s['Instances'][0])
        b = DoGet(_REMOTE, '/instances/%s/tags?simplify' % s['Instances'][1])
        self.assertTrue('ImageComments' in a or 'ImageComments' in b)
        if 'ImageComments' in a:
            self.assertEqual('Tutu', a['ImageComments'])
        else:
            self.assertEqual('Tutu', b['ImageComments'])

        patient = DoGet(_REMOTE, '/instances/%s/patient' % s['Instances'][0])
        self.assertEqual(patient['MainDicomTags']['PatientName'].encode('utf-8'),
                         'Sébastien Jodogne')


    def test_create_binary(self):
        binary = ''.join(map(chr, range(256)))
        encoded = 'data:application/octet-stream;base64,' + base64.b64encode(binary)
        tags = {
            'PatientName' : 'Jodogne',
            '8899-8899' : encoded
        }

        i = DoPost(_REMOTE, '/tools/create-dicom',
                   json.dumps({
                       'Tags' : tags
                   }))

        self.assertEqual('Jodogne', DoGet(_REMOTE, '/instances/%s/content/PatientName' % i['ID']).strip())
        self.assertEqual(binary, DoGet(_REMOTE, '/instances/%s/content/8899-8899' % i['ID']).strip())

        i = DoPost(_REMOTE, '/tools/create-dicom',
                   json.dumps({
                       'InterpretBinaryTags' : False,
                       'Tags' : tags
                   }))

        self.assertEqual('Jodogne', DoGet(_REMOTE, '/instances/%s/content/PatientName' % i['ID']).strip())
        self.assertEqual(encoded, DoGet(_REMOTE, '/instances/%s/content/8899-8899' % i['ID'])[0:-1])


    def test_patient_ids_collision(self):
        # Upload 3 instances from 3 different studies, but with the
        # same PatientID
        for i in range(3):
            UploadInstance(_REMOTE, 'PatientIdsCollision/Image%d.dcm' % (i + 1))

        a = DoPost(_REMOTE, '/tools/find', { 'Level' : 'Patient',
                                             'Query' : { 'PatientName' : '*' }})
        self.assertEqual(1, len(a))
        self.assertEqual('COMMON', DoGet(_REMOTE, '/patients/%s' % a[0]) ['MainDicomTags']['PatientID'])

        a = DoPost(_REMOTE, '/tools/find', { 'Level' : 'Study',
                                             'CaseSensitive' : True,
                                             'Query' : { 'PatientName' : 'FOO\\HELLO' }})
        self.assertEqual(2, len(a))

        a = DoPost(_REMOTE, '/tools/find', { 'Level' : 'Series',
                                             'CaseSensitive' : False,
                                             'Query' : { 'PatientName' : 'Foo' }})
        self.assertEqual(1, len(a))
        self.assertEqual('FOO^SERIES', DoGet(_REMOTE, '/series/%s/study' % a[0]) ['MainDicomTags']['StudyDescription'])
        self.assertEqual('FOO', DoGet(_REMOTE, '/series/%s/study' % a[0]) ['PatientMainDicomTags']['PatientName'])
        self.assertEqual('COMMON', DoGet(_REMOTE, '/series/%s/study' % a[0]) ['PatientMainDicomTags']['PatientID'])

        a = DoPost(_REMOTE, '/tools/find', { 'Level' : 'Study',
                                             'Query' : { 'PatientName' : '*' }})
        self.assertEqual(3, len(a))
        d = map(lambda x: DoGet(_REMOTE, '/studies/%s' % x) ['MainDicomTags']['StudyDescription'], a)
        self.assertTrue('FOO^SERIES' in d)
        self.assertTrue('HELLO^SERIES' in d)
        self.assertTrue('WORLD^SERIES' in d)

        d = map(lambda x: DoGet(_REMOTE, '/studies/%s' % x) ['PatientMainDicomTags']['PatientID'], a)
        self.assertEqual(1, len(set(d)))
        self.assertEqual('COMMON', d[0])

        for i in a:
            d = DoGet(_REMOTE, '/studies/%s' % i) ['MainDicomTags']['StudyDescription']
            p = DoGet(_REMOTE, '/studies/%s' % i) ['PatientMainDicomTags']['PatientName']
            self.assertEqual('%s^SERIES' % p, d)


    def test_bitbucket_issue_4(self):
        UploadInstance(_REMOTE, 'Brainix/Epi/IM-0001-0001.dcm')
        UploadInstance(_REMOTE, 'Brainix/Epi/IM-0001-0002.dcm')
        UploadInstance(_REMOTE, 'Brainix/Epi/IM-0001-0003.dcm')
        UploadInstance(_REMOTE, 'Formats/Jpeg.dcm')
        UploadInstance(_REMOTE, 'Formats/JpegLossless.dcm')
        UploadInstance(_REMOTE, 'Formats/Rle.dcm')
       
        self.assertEqual(0, len(DoGet(_LOCAL, '/instances')))
        self.assertEqual(6, len(DoGet(_REMOTE, '/instances')))

        p = DoGet(_REMOTE, '/patients')
        self.assertEqual(2, len(p))
        i1 = map(lambda x: x['ID'], DoGet(_REMOTE, '/patients/%s/instances' % p[0]))
        i2 = map(lambda x: x['ID'], DoGet(_REMOTE, '/patients/%s/instances' % p[1]))
        self.assertEqual(3, len(i1))
        self.assertEqual(3, len(i2))

        j = DoPost(_REMOTE, '/modalities/orthanctest/store', i2[0:1] + i1 + i2[1:3])

        self.assertEqual(6, len(DoGet(_LOCAL, '/instances')))


    def test_create_sequence(self):
        i = DoPost(_REMOTE, '/tools/create-dicom',
                   json.dumps({
                    'Tags' : {
                        'SpecificCharacterSet': 'ISO_IR 100',  # Encode using Latin1
                        'PatientName': 'Jodogne^',
                        'ReferencedStudySequence': GenerateTestSequence(),
                    }
                   }))['ID']

        self.assertEqual('Jodogne^', DoGet(_REMOTE, '/instances/%s/content/PatientName' % i))
        self.assertEqual('Hello^', DoGet(_REMOTE, '/instances/%s/content/ReferencedStudySequence/0/StudyDescription' % i))
        self.assertEqual('Toto', DoGet(_REMOTE, '/instances/%s/content/ReferencedStudySequence/0/ReferencedStudySequence/0/StudyDescription' % i))
        self.assertEqual('Tata', DoGet(_REMOTE, '/instances/%s/content/ReferencedStudySequence/0/ReferencedStudySequence/1/StudyDescription' % i))
        self.assertEqual(u'Sébastien^'.encode('latin-1'),
                         DoGet(_REMOTE, '/instances/%s/content/ReferencedStudySequence/1/StudyDescription' % i))


    def test_modify_sequence(self):
        i = UploadInstance(_REMOTE, 'PrivateTags.dcm')['ID']
        self.assertRaises(Exception, lambda: DoGet(_REMOTE, '/instances/%s/content/ReferencedStudySequence' % i))

        j = DoPost(_REMOTE, '/instances/%s/modify' % i,
                   json.dumps({
                    "Replace" : {
                        "PatientName" : "hello",
                        'ReferencedStudySequence': GenerateTestSequence(),
                        },
                    }),
                   'application/json')
        j = DoPost(_REMOTE, '/instances', j, 'application/dicom')['ID']
        DoDelete(_REMOTE, '/instances/%s' % i)

        self.assertEqual(2, len(DoGet(_REMOTE, '/instances/%s/content/ReferencedStudySequence' % j)))


    def test_compression(self):
        i = UploadInstance(_REMOTE, 'DummyCT.dcm')['ID']

        data = DoGetRaw(_REMOTE, '/instances/%s/attachments/dicom-as-json/data' % i)[1]

        # "StorageCompression" is enabled in the Orthanc to be tested,
        # uncompress the data before running the test
        if DoGet(_REMOTE, '/instances/%s/attachments/dicom-as-json/is-compressed' % i) != 0:
            DoPost(_REMOTE, '/instances/%s/attachments/dicom-as-json/uncompress' % i)
 
        cs = DoGet(_REMOTE, '/statistics')['TotalDiskSize']
        us = DoGet(_REMOTE, '/statistics')['TotalUncompressedSize']
        size = DoGet(_REMOTE, '/instances/%s/attachments/dicom-as-json/size' % i)
        md5 = DoGet(_REMOTE, '/instances/%s/attachments/dicom-as-json/md5' % i)
        self.assertEqual(data, DoGetRaw(_REMOTE, '/instances/%s/attachments/dicom-as-json/compressed-data' % i)[1])
        self.assertEqual(md5, DoGet(_REMOTE, '/instances/%s/attachments/dicom-as-json/compressed-md5' % i))
        self.assertEqual(size, DoGet(_REMOTE, '/instances/%s/attachments/dicom-as-json/compressed-size' % i))

        ops = DoGet(_REMOTE, '/instances/%s/attachments/dicom-as-json' % i)
        self.assertTrue('compress' in ops)
        self.assertTrue('uncompress' in ops)
        self.assertTrue('is-compressed' in ops)
        self.assertEqual(0, DoGet(_REMOTE, '/instances/%s/attachments/dicom-as-json/is-compressed' % i))
        DoPost(_REMOTE, '/instances/%s/attachments/dicom-as-json/verify-md5' % i)

        DoPost(_REMOTE, '/instances/%s/attachments/dicom-as-json/compress' % i)
        DoPost(_REMOTE, '/instances/%s/attachments/dicom-as-json/verify-md5' % i)
        self.assertEqual(1, DoGet(_REMOTE, '/instances/%s/attachments/dicom-as-json/is-compressed' % i))
        self.assertLess(cs, DoGet(_REMOTE, '/statistics')['TotalDiskSize'])
        self.assertEqual(us, DoGet(_REMOTE, '/statistics')['TotalUncompressedSize'])
        self.assertGreater(len(data), len(DoGetRaw(_REMOTE, '/instances/%s/attachments/dicom-as-json/compressed-data' % i)[1]))
        self.assertGreater(size, DoGet(_REMOTE, '/instances/%s/attachments/dicom-as-json/compressed-size' % i))
        self.assertEqual(size, DoGet(_REMOTE, '/instances/%s/attachments/dicom-as-json/size' % i))
        self.assertEqual(md5, DoGet(_REMOTE, '/instances/%s/attachments/dicom-as-json/md5' % i))
        self.assertNotEqual(md5, DoGet(_REMOTE, '/instances/%s/attachments/dicom-as-json/compressed-md5' % i))

        DoPost(_REMOTE, '/instances/%s/attachments/dicom-as-json/uncompress' % i)
        DoPost(_REMOTE, '/instances/%s/attachments/dicom-as-json/verify-md5' % i)
        self.assertEqual(0, DoGet(_REMOTE, '/instances/%s/attachments/dicom-as-json/is-compressed' % i))
        self.assertEqual(data, DoGetRaw(_REMOTE, '/instances/%s/attachments/dicom-as-json/compressed-data' % i)[1])
        self.assertEqual(size, DoGet(_REMOTE, '/instances/%s/attachments/dicom-as-json/compressed-size' % i))
        self.assertEqual(size, DoGet(_REMOTE, '/instances/%s/attachments/dicom-as-json/size' % i))
        self.assertEqual(md5, DoGet(_REMOTE, '/instances/%s/attachments/dicom-as-json/md5' % i))
        self.assertEqual(md5, DoGet(_REMOTE, '/instances/%s/attachments/dicom-as-json/compressed-md5' % i))
        self.assertEqual(cs, DoGet(_REMOTE, '/statistics')['TotalDiskSize'])
        self.assertEqual(us, DoGet(_REMOTE, '/statistics')['TotalUncompressedSize'])


    def test_ordered_slices(self):
        i = UploadInstance(_REMOTE, 'Multiframe.dcm')['ID']
        s = DoGet(_REMOTE, '/instances/%s' % i)['ParentSeries']
        o = DoGet(_REMOTE, '/series/%s/ordered-slices' % s)
        self.assertEqual('Sequence', o['Type'])
        self.assertEqual(1, len(o['Dicom']))
        self.assertEqual('/instances/9e05eb0a-18b6268c-e0d36085-8ddab517-3b5aec02/file', o['Dicom'][0])
        self.assertEqual(76, len(o['Slices']))
        for j in range(76):
            self.assertEqual('/instances/9e05eb0a-18b6268c-e0d36085-8ddab517-3b5aec02/frames/%d' % j, o['Slices'][j])

        i = UploadInstance(_REMOTE, 'Brainix/Epi/IM-0001-0001.dcm')['ID']
        j = UploadInstance(_REMOTE, 'Brainix/Epi/IM-0001-0002.dcm')['ID']
        k = UploadInstance(_REMOTE, 'Brainix/Epi/IM-0001-0003.dcm')['ID']
        s = DoGet(_REMOTE, '/instances/%s' % i)['ParentSeries']
        o = DoGet(_REMOTE, '/series/%s/ordered-slices' % s)

        self.assertEqual('Volume', o['Type'])
        self.assertEqual(3, len(o['Dicom']))
        self.assertEqual(3, len(o['Slices']))
        self.assertEqual('/instances/%s/file' % i, o['Dicom'][2])
        self.assertEqual('/instances/%s/file' % j, o['Dicom'][1])
        self.assertEqual('/instances/%s/file' % k, o['Dicom'][0])
        self.assertEqual('/instances/%s/frames/0' % i, o['Slices'][2])
        self.assertEqual('/instances/%s/frames/0' % j, o['Slices'][1])
        self.assertEqual('/instances/%s/frames/0' % k, o['Slices'][0])

        i = UploadInstance(_REMOTE, 'Beaufix/IM-0001-0001.dcm')['ID']
        j = UploadInstance(_REMOTE, 'Beaufix/IM-0001-0002.dcm')['ID']
        s = DoGet(_REMOTE, '/instances/%s' % i)['ParentSeries']
        o = DoGet(_REMOTE, '/series/%s/ordered-slices' % s)

        self.assertEqual('Sequence', o['Type'])
        self.assertEqual(2, len(o['Dicom']))
        self.assertEqual(2, len(o['Slices']))
        self.assertEqual('/instances/%s/file' % i, o['Dicom'][0])
        self.assertEqual('/instances/%s/file' % j, o['Dicom'][1])
        self.assertEqual('/instances/%s/frames/0' % i, o['Slices'][0])
        self.assertEqual('/instances/%s/frames/0' % j, o['Slices'][1])


    def test_incoming_movescu_accession(self):
        UploadInstance(_REMOTE, 'Knee/T1/IM-0001-0001.dcm')
        
        self.assertEqual(0, len(DoGet(_LOCAL, '/patients')))
        CallMoveScu([ '--study', '-k', '0008,0052=STUDY', '-k', 'AccessionNumber=nope' ])
        self.assertEqual(0, len(DoGet(_LOCAL, '/patients')))
        CallMoveScu([ '--study', '-k', '0008,0052=PATIENT', '-k', 'AccessionNumber=A10003245599' ])
        self.assertEqual(0, len(DoGet(_LOCAL, '/patients')))
        CallMoveScu([ '--study', '-k', '0008,0052=STUDY', '-k', 'AccessionNumber=A10003245599' ])
        self.assertEqual(1, len(DoGet(_LOCAL, '/patients')))


    def test_dicom_to_json(self):
        i = UploadInstance(_REMOTE, 'PrivateMDNTags.dcm')['ID']
        j = UploadInstance(_REMOTE, 'PrivateTags.dcm')['ID']

        t = DoGet(_REMOTE, '/instances/%s/tags?simplify' % i)
        with open(GetDatabasePath('PrivateMDNTagsSimplify.json'), 'r') as f:
            self.assertEqual(json.loads(f.read()), t)

        t = DoGet(_REMOTE, '/instances/%s/tags' % i)
        with open(GetDatabasePath('PrivateMDNTagsFull.json'), 'r') as f:
            self.assertEqual(json.loads(f.read()), t)

        t = DoGet(_REMOTE, '/instances/%s/tags?simplify' % j)
        with open(GetDatabasePath('PrivateTagsSimplify.json'), 'r') as f:
            a = json.loads(f.read())
            self.assertEqual(a, t)

        t = DoGet(_REMOTE, '/instances/%s/tags' % j)
        with open(GetDatabasePath('PrivateTagsFull.json'), 'r') as f:
            a = json.loads(f.read())

            aa = json.dumps(a).replace('2e+022', '2e+22')
            tt = json.dumps(t).replace('2e+022', '2e+22')
            self.assertEqual(aa, tt)


    def test_batch_archive(self):
        UploadInstance(_REMOTE, 'Knee/T1/IM-0001-0001.dcm')
        UploadInstance(_REMOTE, 'Knee/T1/IM-0001-0002.dcm')
        UploadInstance(_REMOTE, 'Knee/T2/IM-0001-0001.dcm')
        UploadInstance(_REMOTE, 'Knee/T2/IM-0001-0002.dcm')
        UploadInstance(_REMOTE, 'Brainix/Epi/IM-0001-0001.dcm')
        UploadInstance(_REMOTE, 'Brainix/Epi/IM-0001-0002.dcm')
        UploadInstance(_REMOTE, 'Brainix/Flair/IM-0001-0001.dcm')
        UploadInstance(_REMOTE, 'Brainix/Flair/IM-0001-0002.dcm')

        s = DoPost(_REMOTE, '/tools/create-archive', [ ])
        z = zipfile.ZipFile(StringIO(s), "r")
        self.assertEqual(0, len(z.namelist()))
       
        # One patient
        s = DoPost(_REMOTE, '/tools/create-archive', [ 'ca29faea-b6a0e17f-067743a1-8b778011-a48b2a17' ])
        z = zipfile.ZipFile(StringIO(s), "r")
        self.assertEqual(4, len(z.namelist()))

        # One patient + twice its study + one series from other patient
        s = DoPost(_REMOTE, '/tools/create-archive', [ 
            'ca29faea-b6a0e17f-067743a1-8b778011-a48b2a17',
            '0a9b3153-2512774b-2d9580de-1fc3dcf6-3bd83918',
            '1e2c125c-411b8e86-3f4fe68e-a7584dd3-c6da78f0'
        ])
        z = zipfile.ZipFile(StringIO(s), "r")
        self.assertEqual(6, len(z.namelist()))        

        # One patient + one series + one instance
        s = DoPost(_REMOTE, '/tools/create-archive', [ 
            'ca29faea-b6a0e17f-067743a1-8b778011-a48b2a17',
            '1e2c125c-411b8e86-3f4fe68e-a7584dd3-c6da78f0',
            '1d429ccb-bdcc78a1-7d129d6a-ba4966ed-fe4dbd87'
        ])
        z = zipfile.ZipFile(StringIO(s), "r")
        self.assertEqual(7, len(z.namelist()))


    def test_decode_brainix_as_jpeg(self):
        i = UploadInstance(_REMOTE, 'Brainix/Epi/IM-0001-0001.dcm')['ID']

        j = GetImage(_REMOTE, '/instances/%s/preview' % i)
        self.assertEqual('PNG', j.format)
        self.assertEqual(j.size[0], 256)
        self.assertEqual(j.size[1], 256)

        j = GetImage(_REMOTE, '/instances/%s/preview' % i, headers = { 'Accept' : '*/*' })
        self.assertEqual('PNG', j.format)

        j = GetImage(_REMOTE, '/instances/%s/preview' % i, headers = { 'Accept' : 'image/*' })
        self.assertEqual('PNG', j.format)

        j = GetImage(_REMOTE, '/instances/%s/preview' % i, headers = { 'Accept' : 'image/png' })
        self.assertEqual('PNG', j.format)

        j = GetImage(_REMOTE, '/instances/%s/preview' % i, headers = { 'Accept' : 'image/jpeg' })
        self.assertEqual('JPEG', j.format)
        self.assertEqual(j.size[0], 256)
        self.assertEqual(j.size[1], 256)

        a = len(DoGet(_REMOTE, '/instances/%s/preview?quality=50' % i, headers = { 'Accept' : 'image/jpeg' }))
        b = len(DoGet(_REMOTE, '/instances/%s/preview' % i, headers = { 'Accept' : 'image/jpeg' }))
        self.assertLess(a, b)

        j = GetImage(_REMOTE, '/instances/%s/image-uint8' % i, headers = { 'Accept' : 'image/jpeg' })
        self.assertEqual('JPEG', j.format)

        # 16bit encoding is not supported with JPEG
        self.assertRaises(Exception, lambda: GetImage(_REMOTE, '/instances/%s/image-uint16' % i, headers = { 'Accept' : 'image/jpeg' }))
        self.assertRaises(Exception, lambda: GetImage(_REMOTE, '/instances/%s/image-int16' % i, headers = { 'Accept' : 'image/jpeg' }))

        # No matching content type
        self.assertRaises(Exception, lambda: GetImage(_REMOTE, '/instances/%s/preview' % i, headers = { 'Accept' : 'application/pdf' }))
