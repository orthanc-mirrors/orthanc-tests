#!/usr/bin/python
# -*- coding: utf-8 -*-


# Orthanc - A Lightweight, RESTful DICOM Store
# Copyright (C) 2012-2016 Sebastien Jodogne, Medical Physics
# Department, University Hospital of Liege, Belgium
# Copyright (C) 2017-2023 Osimis S.A., Belgium
# Copyright (C) 2021-2023 Sebastien Jodogne, ICTEAM UCLouvain, Belgium
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
parser.add_argument('--dicomizer',
                    default = '/home/jodogne/Subversion/orthanc-wsi/Applications/i/OrthancWSIDicomizer',
                    help = 'Password to the REST API')
parser.add_argument('--to-tiff',
                    default = '/home/jodogne/Subversion/orthanc-wsi/Applications/i/OrthancWSIDicomToTiff',
                    help = 'Password to the REST API')
parser.add_argument('--valgrind', help = 'Use valgrind while running the DICOM-izer',
                    action = 'store_true')
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

def CallCommand(command):
    prefix = []
    if args.valgrind:
        prefix = [ 'valgrind' ]
    
    log = subprocess.check_output(prefix + command,
                                  stderr=subprocess.STDOUT)
                                  
    # If using valgrind, only print the lines from the log starting
    # with '==' (they contain the report from valgrind)
    if args.valgrind:
        print('\n'.join(filter(lambda x: x.startswith('=='), log.splitlines())))

        
def CallDicomizer(suffix):
    CallCommand([ args.dicomizer,
                  '--orthanc=http://%s:%s' % (args.server, args.rest),
                  '--username=%s' % args.username,
                  '--password=%s' % args.password ] + suffix
                  )

    
def CallDicomToTiff(suffix):
    CallCommand([ args.to_tiff,
                  '--orthanc=http://%s:%s' % (args.server, args.rest),
                  '--username=%s' % args.username,
                  '--password=%s' % args.password ] + suffix)


def CallTiffInfoOnSeries(series):
    with tempfile.NamedTemporaryFile(delete = False) as temp:
        temp.close()
        CallDicomToTiff([ series, temp.name ])
        try:
            tiff = subprocess.check_output([ 'tiffinfo', temp.name ])
        except:
            print('\ntiffinfo is probably not installed => sudo apt-get install libtiff-tools\n')
            tiff = None
            
        os.unlink(temp.name)

    return tiff


class Orthanc(unittest.TestCase):
    def setUp(self):
        if (sys.version_info >= (3, 0)):
            # Remove annoying warnings about unclosed socket in Python 3
            import warnings
            warnings.simplefilter("ignore", ResourceWarning)

        DropOrthanc(ORTHANC)


    def test_single(self):
        CallDicomizer([ GetDatabasePath('Lena.jpg') ])

        i = DoGet(ORTHANC, '/instances')
        self.assertEqual(1, len(i))

        tags = DoGet(ORTHANC, '/instances/%s/tags?simplify' % i[0])
        self.assertEqual(1, int(tags['NumberOfFrames']))
        self.assertEqual(512, int(tags['Columns']))
        self.assertEqual(512, int(tags['Rows']))
        self.assertEqual('YBR_FULL_422', tags['PhotometricInterpretation'])
        
        s = DoGet(ORTHANC, '/series')
        self.assertEqual(1, len(s))

        pyramid = DoGet(ORTHANC, '/wsi/pyramids/%s' % s[0])
        self.assertEqual(s[0], pyramid['ID'])
        self.assertEqual(1, len(pyramid['Resolutions']))
        self.assertEqual(1, len(pyramid['Sizes']))
        self.assertEqual(1, len(pyramid['TilesCount']))
        self.assertEqual(1, pyramid['Resolutions'][0])
        self.assertEqual(512, pyramid['Sizes'][0][0])
        self.assertEqual(512, pyramid['Sizes'][0][1])
        self.assertEqual(1, len(pyramid['TilesSizes']))
        self.assertEqual(2, len(pyramid['TilesSizes'][0]))
        self.assertEqual(512, pyramid['TilesSizes'][0][0])
        self.assertEqual(512, pyramid['TilesSizes'][0][1])
        self.assertEqual(512, pyramid['TotalWidth'])
        self.assertEqual(512, pyramid['TotalHeight'])
        self.assertEqual(1, pyramid['TilesCount'][0][0])
        self.assertEqual(1, pyramid['TilesCount'][0][1])

        tiff = CallTiffInfoOnSeries(s[0])
        p = filter(lambda x: 'Photometric Interpretation' in x, tiff.splitlines())
        self.assertEqual(1, len(p))
        self.assertTrue('YCbCr' in p[0])


    def test_grayscale_pyramid(self):
        CallDicomizer([ GetDatabasePath('LenaGrayscale.png'), '--tile-width=64', '--tile-height=64' ])

        i = DoGet(ORTHANC, '/instances')
        self.assertEqual(4, len(i))

        for j in range(4):
            tags = DoGet(ORTHANC, '/instances/%s/tags?simplify' % i[j])
            self.assertEqual(64, int(tags['Columns']))
            self.assertEqual(64, int(tags['Rows']))
            self.assertEqual('MONOCHROME2', tags['PhotometricInterpretation'])
        
        s = DoGet(ORTHANC, '/series')
        self.assertEqual(1, len(s))

        pyramid = DoGet(ORTHANC, '/wsi/pyramids/%s' % s[0])
        self.assertEqual(s[0], pyramid['ID'])
        self.assertEqual(4, len(pyramid['Resolutions']))
        self.assertEqual(4, len(pyramid['Sizes']))
        self.assertEqual(4, len(pyramid['TilesCount']))
        self.assertEqual(4, len(pyramid['TilesSizes']))

        self.assertEqual(1, pyramid['Resolutions'][0])
        self.assertEqual(2, pyramid['Resolutions'][1])
        self.assertEqual(4, pyramid['Resolutions'][2])
        self.assertEqual(8, pyramid['Resolutions'][3])
        self.assertEqual(512, pyramid['Sizes'][0][0])
        self.assertEqual(512, pyramid['Sizes'][0][1])
        self.assertEqual(256, pyramid['Sizes'][1][0])
        self.assertEqual(256, pyramid['Sizes'][1][1])
        self.assertEqual(128, pyramid['Sizes'][2][0])
        self.assertEqual(128, pyramid['Sizes'][2][1])
        self.assertEqual(64, pyramid['Sizes'][3][0])
        self.assertEqual(64, pyramid['Sizes'][3][1])
        for i in range(4):
            self.assertEqual(2, len(pyramid['TilesSizes'][i]))
            self.assertEqual(64, pyramid['TilesSizes'][i][0])
            self.assertEqual(64, pyramid['TilesSizes'][i][1])
        self.assertEqual(512, pyramid['TotalWidth'])
        self.assertEqual(512, pyramid['TotalHeight'])
        self.assertEqual(8, pyramid['TilesCount'][0][0])
        self.assertEqual(8, pyramid['TilesCount'][0][1])
        self.assertEqual(4, pyramid['TilesCount'][1][0])
        self.assertEqual(4, pyramid['TilesCount'][1][1])
        self.assertEqual(2, pyramid['TilesCount'][2][0])
        self.assertEqual(2, pyramid['TilesCount'][2][1])
        self.assertEqual(1, pyramid['TilesCount'][3][0])
        self.assertEqual(1, pyramid['TilesCount'][3][1])

        tiff = CallTiffInfoOnSeries(s[0])
        p = filter(lambda x: 'Photometric Interpretation' in x, tiff.splitlines())
        self.assertEqual(4, len(p))
        for j in range(4):
            self.assertTrue('min-is-black' in p[j])


    def test_import_tiff_grayscale(self):
        CallDicomizer([ GetDatabasePath('WSI/LenaGrayscaleJpeg.tiff') ])

        s = DoGet(ORTHANC, '/series')
        self.assertEqual(1, len(s))

        pyramid = DoGet(ORTHANC, '/wsi/pyramids/%s' % s[0])
        self.assertEqual(4, len(pyramid['Resolutions']))

        tiff = CallTiffInfoOnSeries(s[0])
        p = filter(lambda x: 'Photometric Interpretation' in x, tiff.splitlines())
        self.assertEqual(4, len(p))
        for j in range(4):
            self.assertTrue('min-is-black' in p[j])

            
    def test_import_tiff_ycbcr(self):
        CallDicomizer([ GetDatabasePath('WSI/LenaColorJpegYCbCr.tiff') ])

        s = DoGet(ORTHANC, '/series')
        self.assertEqual(1, len(s))

        pyramid = DoGet(ORTHANC, '/wsi/pyramids/%s' % s[0])
        self.assertEqual(4, len(pyramid['Resolutions']))

        tiff = CallTiffInfoOnSeries(s[0])
        p = filter(lambda x: 'Photometric Interpretation' in x, tiff.splitlines())
        self.assertEqual(4, len(p))
        for j in range(4):
            self.assertTrue('YCbCr' in p[j])


    def test_import_tiff_rgb(self):
        CallDicomizer([ GetDatabasePath('WSI/LenaColorJpegRGB.tiff') ])

        s = DoGet(ORTHANC, '/series')
        self.assertEqual(1, len(s))

        pyramid = DoGet(ORTHANC, '/wsi/pyramids/%s' % s[0])
        self.assertEqual(4, len(pyramid['Resolutions']))

        tiff = CallTiffInfoOnSeries(s[0])
        p = filter(lambda x: 'Photometric Interpretation' in x, tiff.splitlines())
        self.assertEqual(4, len(p))
        for j in range(4):
            self.assertTrue('RGB' in p[j])


    def test_concatenation(self):
        # https://bugs.orthanc-server.com/show_bug.cgi?id=145
        CallDicomizer([ GetDatabasePath('LenaGrayscale.png'), '--levels=1', ])
        i = DoGet(ORTHANC, '/instances')
        self.assertEqual(1, len(i))
        tags = DoGet(ORTHANC, '/instances/%s/tags?short' % i[0])
        self.assertTrue('0020,0242' in tags)  # SOP Instance UID of Concatenation Source
        self.assertTrue('0020,9161' in tags)  # Concatenation UID
        self.assertTrue('0020,9162' in tags)  # In-concatenation Number
        self.assertTrue('0020,9228' in tags)  # Concatenation Frame Offset Number
        self.assertEqual('1', tags['0020,9162'])
        self.assertEqual('0', tags['0020,9228'])

        DropOrthanc(ORTHANC)

        # "--max-size" disables the concatenation
        CallDicomizer([ GetDatabasePath('LenaGrayscale.png'), '--levels=1', '--max-size=0' ])
        i = DoGet(ORTHANC, '/instances')
        self.assertEqual(1, len(i))
        tags = DoGet(ORTHANC, '/instances/%s/tags?short' % i[0])
        self.assertFalse('0020,0242' in tags)
        self.assertFalse('0020,9161' in tags)
        self.assertFalse('0020,9162' in tags)
        self.assertFalse('0020,9228' in tags)
            
        DropOrthanc(ORTHANC)

        # This creates a series with 2 instances of roughly 1.5MB (= 2 frames x 512 x 512 x 3 (RGB24) + DICOM overhead)
        CallDicomizer([ GetDatabasePath('WSI/Lena2x2.png'), '--levels=1', '--max-size=1', '--compression=none' ])
        i = DoGet(ORTHANC, '/instances')
        self.assertEqual(2, len(i))
        t1 = DoGet(ORTHANC, '/instances/%s/tags?short' % i[0])
        t2 = DoGet(ORTHANC, '/instances/%s/tags?short' % i[1])
        self.assertTrue('0020,0242' in t1)
        self.assertTrue('0020,9161' in t1)
        self.assertTrue('0020,9162' in t1)
        self.assertTrue('0020,9228' in t1)
        self.assertEqual(t1['0020,0242'], t2['0020,0242'])
        self.assertEqual(t1['0020,9161'], t2['0020,9161'])
        if t1['0020,9162'] == '1':
            self.assertEqual('1', t1['0020,9162'])
            self.assertEqual('0', t1['0020,9228'])
            self.assertEqual('2', t2['0020,9162'])
            self.assertEqual('2', t2['0020,9228'])
        else:
            self.assertEqual('1', t2['0020,9162'])
            self.assertEqual('0', t2['0020,9228'])
            self.assertEqual('2', t1['0020,9162'])
            self.assertEqual('2', t1['0020,9228'])


    def test_pixel_spacing(self):
        # https://bugs.orthanc-server.com/show_bug.cgi?id=139
        CallDicomizer([ GetDatabasePath('LenaGrayscale.png'),  # Image is 512x512
                        '--levels=4', '--tile-width=64', '--tile-height=64', '--max-size=0',
                        '--imaged-width=20', '--imaged-height=10' ])

        instances = DoGet(ORTHANC, '/instances')
        self.assertEqual(4, len(instances))

        spacings = {}
        for i in instances:
            t = DoGet(ORTHANC, '/instances/%s/tags?short' % i)
            spacings[t['0028,0008']] = t['5200,9229'][0]['0028,9110'][0]['0028,0030']

        self.assertEqual(4, len(spacings))
        for i in range(4):
            s = spacings[str(4 ** i)].split('\\')
            self.assertEqual(2, len(s))
            self.assertEqual(20.0 / 512.0 * (2.0 ** (3 - i)), float(s[0])) 
            self.assertEqual(10.0 / 512.0 * (2.0 ** (3 - i)), float(s[1])) 

        
try:
    print('\nStarting the tests...')
    unittest.main(argv = [ sys.argv[0] ] + args.options)

finally:
    print('\nDone')
