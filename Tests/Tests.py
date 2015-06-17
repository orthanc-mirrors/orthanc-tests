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


import unittest

from Toolbox import *

_LOCAL = None
_REMOTE = None


def SetOrthancParameters(local, remote):
    global _LOCAL, _REMOTE
    _LOCAL = local
    _REMOTE = remote


class Orthanc(unittest.TestCase):
    def setUp(self):
        DropOrthanc(_LOCAL)
        DropOrthanc(_REMOTE)

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


    def test_multi_frame(self):
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
        a = subprocess.check_output([ 'dciodvfy', '/tmp/DICOMDIR' ],
                                    stderr = subprocess.STDOUT).split('\n')
        self.assertEqual(3, len(a))
        self.assertTrue(a[0].startswith('Warning'))
        self.assertEqual('BasicDirectory', a[1])
        self.assertEqual('', a[2])

        a = subprocess.check_output([ 'dcentvfy', '/tmp/DICOMDIR' ],
                                    stderr = subprocess.STDOUT).split('\n')
        self.assertEqual(1, len(a))
        self.assertEqual('', a[0])

        a = subprocess.check_output([ 'dcm2xml', '/tmp/DICOMDIR' ])
        self.assertTrue(re.search('1.3.46.670589.11.17521.5.0.3124.2008081908590448738', a) != None)
        self.assertTrue(re.search('1.3.46.670589.11.17521.5.0.3124.2008081909113806560', a) != None)

        os.remove('/tmp/DICOMDIR')
