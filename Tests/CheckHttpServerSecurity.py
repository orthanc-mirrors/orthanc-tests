#!/usr/bin/env python3

# Orthanc - A Lightweight, RESTful DICOM Store
# Copyright (C) 2012-2016 Sebastien Jodogne, Medical Physics
# Department, University Hospital of Liege, Belgium
# Copyright (C) 2017-2023 Osimis S.A., Belgium
# Copyright (C) 2024-2026 Orthanc Team SRL, Belgium
# Copyright (C) 2021-2026 Sebastien Jodogne, ICTEAM UCLouvain, Belgium
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

if len(sys.argv) != 2:
    print('Must provide a path to Orthanc binaries')
    exit(-1)


TMP = '/tmp/OrthancTest'
CONFIG = os.path.join(TMP, 'Configuration.json')

if os.path.exists(TMP):
    print('Temporary path already exists: %s' % TMP)
    exit(-1)

os.mkdir(TMP)




def IsHttpServerSecure(config,
                       username = 'orthanc',
                       password = 'orthanc'):
    ORTHANC = Toolbox.DefineOrthanc(username = username,
                                    password = password)

    with open(CONFIG, 'w') as f:
        f.write(json.dumps(config))
    
    process = subprocess.Popen(
        [ sys.argv[1], CONFIG ],
        cwd = TMP,
        #stdout=subprocess.PIPE, 
        stderr=subprocess.PIPE, 
        #shell=True
        )

    success = False

    while process.poll() is None:  # Orthanc is still running
        try:
            system = Toolbox.DoGet(ORTHANC, '/system')
            success = True
            break
        except:
            pass

        time.sleep(0.1)

    process.terminate()
    process.wait()

    if success:
        return system['IsHttpServerSecure']
    else:
        return None  # Orthanc has not started


def Assert(expected, actual):
    if expected != actual:
        raise Exception('Bad result')


print('==== TEST 1 ====')
Assert(True, IsHttpServerSecure({
            'RemoteAccessAllowed': False,
            'RegisteredUsers' : { }
            }))

print('==== TEST 2 ====')
Assert(True, IsHttpServerSecure({
            'RemoteAccessAllowed': False,
            'AuthenticationEnabled': False,
            'RegisteredUsers' : { }
            }))

print('==== TEST 3a ====')
Assert(False, IsHttpServerSecure({
            'RemoteAccessAllowed': False,
            'AuthenticationEnabled': True,
            'RegisteredUsers' : { 'orthanc' : 'orthanc' }
            }))

print('==== TEST 3b ====')
Assert(False, IsHttpServerSecure({
            'RemoteAccessAllowed': False,
            'AuthenticationEnabled': True,
            'RegisteredUsers' : { 'alice' : 'orthanctest' }
            }, 'alice', 'orthanctest'))

print('==== TEST 3c ====')
Assert(True, IsHttpServerSecure({
            'RemoteAccessAllowed': False,
            'AuthenticationEnabled': True,
            'RegisteredUsers' : { 'orthanc' : 'SECURE' }
            }, 'orthanc', 'SECURE'))

print('==== TEST 4 ====')  # Orthanc refuses to start since Orthanc 1.13.0
Assert(None, IsHttpServerSecure({
            'RemoteAccessAllowed': True
            }))

print('==== TEST 5 (server application scenario) ====')
Assert(False, IsHttpServerSecure({
            'RemoteAccessAllowed': True,
            'AuthenticationEnabled': False,
            }))

print('==== TEST 6a ====')
Assert(False, IsHttpServerSecure({
            'RemoteAccessAllowed': True,
            'AuthenticationEnabled': True,
            'RegisteredUsers' : { 'orthanc' : 'orthanc' }
            }))

print('==== TEST 6b ====')
Assert(True, IsHttpServerSecure({
            'RemoteAccessAllowed': True,
            'AuthenticationEnabled': True,
            'RegisteredUsers' : { 'orthanc' : 'SECURE' }
            }, 'orthanc', 'SECURE'))

print('==== TEST 7 (Docker scenario) ====')  # Orthanc refuses to start since Orthanc 1.13.0
Assert(None, IsHttpServerSecure({
            'RemoteAccessAllowed': True,
            'AuthenticationEnabled': True
            }))

print('Success!')
