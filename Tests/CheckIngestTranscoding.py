#!/usr/bin/env python

# Orthanc - A Lightweight, RESTful DICOM Store
# Copyright (C) 2012-2016 Sebastien Jodogne, Medical Physics
# Department, University Hospital of Liege, Belgium
# Copyright (C) 2017-2021 Osimis S.A., Belgium
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


import json
import os
import subprocess
import sys
import time
import Toolbox


if len(sys.argv) < 2:
    print('Must provide a path to Orthanc binaries')
    exit(-1)


TMP = '/tmp/OrthancTest'
CONFIG = os.path.join(TMP, 'Configuration.json')
ORTHANC = Toolbox.DefineOrthanc()

if os.path.exists(TMP):
    print('Temporary path already exists: %s' % TMP)
    exit(-1)

os.mkdir(TMP)


def DropOrthanc():
    while True:
        try:
            instances = Toolbox.DoGet(ORTHANC, '/instances')
            if len(instances) == 0:
                break
            else:
                for i in instances:
                    Toolbox.DoDelete(ORTHANC, '/instances/%s' % i)
        except:
            time.sleep(0.05)
    


def TestTranscoding(config, tests):
    with open(CONFIG, 'w') as f:
        f.write(json.dumps(config))
    
    process = subprocess.Popen(
        sys.argv[1:] + [ CONFIG ],
        cwd = TMP,
        #stdout=subprocess.PIPE, 
        stderr=subprocess.PIPE, 
        #shell=True
        )

    success = True

    try:
        for test in tests:
            DropOrthanc()
            with open(Toolbox.GetDatabasePath(test[0]), 'rb') as f:
                Toolbox.DoPost(ORTHANC, '/instances', f.read(), 'application/dicom')

            instances = Toolbox.DoGet(ORTHANC, '/instances')
            if len(instances) != 1:
                print('BAD NUMBER OF INSTANCES')
                success = False
                break

            metadata = Toolbox.DoGet(ORTHANC, '/instances/%s/metadata?expand' % instances[0])
            if not 'TransferSyntax' in metadata:
                print('NO METADATA')
                success = False
                break

            if metadata['TransferSyntax'] != test[1]:
                print('TRANSFER SYNTAX MISMATCH: %s vs %s' % (metadata['TransferSyntax'], test[1]))
                success = False
    except:
        success = False
            
    process.terminate()
    process.wait()

    return success


def Assert(b):
    if not b:
        raise Exception('Bad result')


print('==== TEST 1 ====')  # No transcoding by default
Assert(TestTranscoding({ }, [
    ('TransferSyntaxes/1.2.840.10008.1.2.1.dcm', '1.2.840.10008.1.2.1'),
    ('TransferSyntaxes/1.2.840.10008.1.2.2.dcm', '1.2.840.10008.1.2.2'),
    ('TransferSyntaxes/1.2.840.10008.1.2.4.51.dcm', '1.2.840.10008.1.2.4.51'),
]))

print('==== TEST 2 ====')
Assert(TestTranscoding({
    'IngestTranscoding' : '1.2.840.10008.1.2.1',
}, [
    ('TransferSyntaxes/1.2.840.10008.1.2.1.dcm', '1.2.840.10008.1.2.1'),
    ('TransferSyntaxes/1.2.840.10008.1.2.2.dcm', '1.2.840.10008.1.2.1'),
    ('TransferSyntaxes/1.2.840.10008.1.2.4.51.dcm', '1.2.840.10008.1.2.1'),
]))

print('==== TEST 3 ====')
Assert(TestTranscoding({
    'IngestTranscoding' : '1.2.840.10008.1.2.1',
    'IngestTranscodingOfUncompressed' : True,
    'IngestTranscodingOfCompressed' : True,
}, [
    ('TransferSyntaxes/1.2.840.10008.1.2.1.dcm', '1.2.840.10008.1.2.1'),
    ('TransferSyntaxes/1.2.840.10008.1.2.2.dcm', '1.2.840.10008.1.2.1'),
    ('TransferSyntaxes/1.2.840.10008.1.2.4.51.dcm', '1.2.840.10008.1.2.1'),
]))

print('==== TEST 4 ====')
Assert(TestTranscoding({
    'IngestTranscoding' : '1.2.840.10008.1.2.1',
    'IngestTranscodingOfUncompressed' : True,
    'IngestTranscodingOfCompressed' : False,
}, [
    ('TransferSyntaxes/1.2.840.10008.1.2.1.dcm', '1.2.840.10008.1.2.1'),
    ('TransferSyntaxes/1.2.840.10008.1.2.2.dcm', '1.2.840.10008.1.2.1'),
    ('TransferSyntaxes/1.2.840.10008.1.2.4.51.dcm', '1.2.840.10008.1.2.4.51'),
]))

print('==== TEST 5 ====')
Assert(TestTranscoding({
    'IngestTranscoding' : '1.2.840.10008.1.2.1',
    'IngestTranscodingOfUncompressed' : False,
    'IngestTranscodingOfCompressed' : True,
}, [
    ('TransferSyntaxes/1.2.840.10008.1.2.1.dcm', '1.2.840.10008.1.2.1'),
    ('TransferSyntaxes/1.2.840.10008.1.2.2.dcm', '1.2.840.10008.1.2.2'),
    ('TransferSyntaxes/1.2.840.10008.1.2.4.51.dcm', '1.2.840.10008.1.2.1'),
]))

print('==== TEST 6 ====')
Assert(TestTranscoding({
    'IngestTranscoding' : '1.2.840.10008.1.2.1',
    'IngestTranscodingOfUncompressed' : False,
    'IngestTranscodingOfCompressed' : False,
}, [
    ('TransferSyntaxes/1.2.840.10008.1.2.1.dcm', '1.2.840.10008.1.2.1'),
    ('TransferSyntaxes/1.2.840.10008.1.2.2.dcm', '1.2.840.10008.1.2.2'),
    ('TransferSyntaxes/1.2.840.10008.1.2.4.51.dcm', '1.2.840.10008.1.2.4.51'),
]))

print('==== TEST 7 ====')
Assert(TestTranscoding({
    'IngestTranscoding' : '1.2.840.10008.1.2.4.51',
    'IngestTranscodingOfUncompressed' : True,
    'IngestTranscodingOfCompressed' : True,
}, [
    ('TransferSyntaxes/1.2.840.10008.1.2.1.dcm', '1.2.840.10008.1.2.4.51'),
    ('TransferSyntaxes/1.2.840.10008.1.2.4.51.dcm', '1.2.840.10008.1.2.4.51'),
    ('TransferSyntaxes/1.2.840.10008.1.2.4.57.dcm', '1.2.840.10008.1.2.4.51'),
]))

print('==== TEST 8 ====')
Assert(TestTranscoding({
    'IngestTranscoding' : '1.2.840.10008.1.2.4.51',
    'IngestTranscodingOfUncompressed' : True,
    'IngestTranscodingOfCompressed' : False,
}, [
    ('TransferSyntaxes/1.2.840.10008.1.2.1.dcm', '1.2.840.10008.1.2.4.51'),
    ('TransferSyntaxes/1.2.840.10008.1.2.4.51.dcm', '1.2.840.10008.1.2.4.51'),
    ('TransferSyntaxes/1.2.840.10008.1.2.4.57.dcm', '1.2.840.10008.1.2.4.57'),
]))

print('==== TEST 9 ====')
Assert(TestTranscoding({
    'IngestTranscoding' : '1.2.840.10008.1.2.4.51',
    'IngestTranscodingOfUncompressed' : False,
    'IngestTranscodingOfCompressed' : True,
}, [
    ('TransferSyntaxes/1.2.840.10008.1.2.1.dcm', '1.2.840.10008.1.2.1'),
    ('TransferSyntaxes/1.2.840.10008.1.2.4.51.dcm', '1.2.840.10008.1.2.4.51'),
    ('TransferSyntaxes/1.2.840.10008.1.2.4.57.dcm', '1.2.840.10008.1.2.4.51'),
]))

print('==== TEST 10 ====')
Assert(TestTranscoding({
    'IngestTranscoding' : '1.2.840.10008.1.2.4.51',
    'IngestTranscodingOfUncompressed' : False,
    'IngestTranscodingOfCompressed' : False,
}, [
    ('TransferSyntaxes/1.2.840.10008.1.2.1.dcm', '1.2.840.10008.1.2.1'),
    ('TransferSyntaxes/1.2.840.10008.1.2.4.51.dcm', '1.2.840.10008.1.2.4.51'),
    ('TransferSyntaxes/1.2.840.10008.1.2.4.57.dcm', '1.2.840.10008.1.2.4.57'),
]))


print('Success!')