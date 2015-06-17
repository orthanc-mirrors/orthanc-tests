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


    def test_rest_grid(self):
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



