#!/usr/bin/python

# Orthanc - A Lightweight, RESTful DICOM Store
# Copyright (C) 2012-2016 Sebastien Jodogne, Medical Physics
# Department, University Hospital of Liege, Belgium
# Copyright (C) 2017 Osimis, Belgium
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


import hashlib
import httplib2
import json
import os
import re
import signal
import subprocess
import threading
import sys
import time
import zipfile

from PIL import Image

if (sys.version_info >= (3, 0)):
    from urllib.parse import urlencode
    from io import StringIO
    from io import BytesIO

else:
    from urllib import urlencode

    # http://stackoverflow.com/a/1313868/881731
    try:
        from cStringIO import StringIO
    except:
        from StringIO import StringIO


def _DecodeJson(s):
    t = s

    if (sys.version_info >= (3, 0)):
        try:
            t = s.decode()
        except:
            pass

    try:
        return json.loads(t)
    except:
        return t


def DefineOrthanc(server = 'localhost',
                  restPort = 8042,
                  username = None,
                  password = None,
                  aet = 'ORTHANC',
                  dicomPort = 4242):
    #m = re.match(r'(http|https)://([^:]+):([^@]+)@([^@]+)', url)
    #if m != None:
    #    url = m.groups()[0] + '://' + m.groups()[3]
    #    username = m.groups()[1]
    #    password = m.groups()[2]

    #if not url.endswith('/'):
    #    url += '/'

    return {
        'Server' : server,
        'Url' : 'http://%s:%d/' % (server, restPort),
        'Username' : username,
        'Password' : password,
        'DicomAet' : aet,
        'DicomPort' : dicomPort
        }


def _SetupCredentials(orthanc, http):
    if (orthanc['Username'] != None and 
        orthanc['Password'] != None):
        http.add_credentials(orthanc['Username'], orthanc['Password'])

def DoGetRaw(orthanc, uri, data = {}, body = None, headers = {}):
    d = ''
    if len(data.keys()) > 0:
        d = '?' + urlencode(data)

    http = httplib2.Http()
    http.follow_redirects = False
    _SetupCredentials(orthanc, http)

    resp, content = http.request(orthanc['Url'] + uri + d, 'GET', body = body,
                                 headers = headers)
    return (resp, content)


def DoGet(orthanc, uri, data = {}, body = None, headers = {}):
    (resp, content) = DoGetRaw(orthanc, uri, data = data, body = body, headers = headers)

    if not (resp.status in [ 200 ]):
        raise Exception(resp.status)
    else:
        return _DecodeJson(content)

def _DoPutOrPost(orthanc, uri, method, data, contentType, headers):
    http = httplib2.Http()
    http.follow_redirects = False
    _SetupCredentials(orthanc, http)

    if isinstance(data, (str, bytearray, bytes)):
        body = data
        if len(contentType) != 0:
            headers['content-type'] = contentType
    else:
        body = json.dumps(data)
        headers['content-type'] = 'application/json'
    
    headers['expect'] = ''

    resp, content = http.request(orthanc['Url'] + uri, method,
                                 body = body,
                                 headers = headers)
    if not (resp.status in [ 200, 302 ]):
        raise Exception(resp.status)
    else:
        return _DecodeJson(content)

def DoDelete(orthanc, uri):
    http = httplib2.Http()
    http.follow_redirects = False
    _SetupCredentials(orthanc, http)

    resp, content = http.request(orthanc['Url'] + uri, 'DELETE')
    if not (resp.status in [ 200 ]):
        raise Exception(resp.status)
    else:
        return _DecodeJson(content)

def DoPut(orthanc, uri, data = {}, contentType = ''):
    return _DoPutOrPost(orthanc, uri, 'PUT', data, contentType, {})

def DoPost(orthanc, uri, data = {}, contentType = '', headers = {}):
    return _DoPutOrPost(orthanc, uri, 'POST', data, contentType, headers)

def GetDatabasePath(filename):
    return os.path.join(os.path.dirname(__file__), '..', 'Database', filename)

def UploadInstance(orthanc, filename):
    with open(GetDatabasePath(filename), 'rb') as f:
        d = f.read()

    return DoPost(orthanc, '/instances', d, 'application/dicom')

def UploadFolder(orthanc, path):
    for i in os.listdir(GetDatabasePath(path)):
        try:
            UploadInstance(orthanc, os.path.join(path, i))
        except:
            pass

def DropOrthanc(orthanc):
    # Reset the Lua callbacks
    DoPost(orthanc, '/tools/execute-script', 'function OnStoredInstance(instanceId, tags, metadata) end', 'application/lua')

    DoDelete(orthanc, '/exports')

    for s in DoGet(orthanc, '/patients'):
        DoDelete(orthanc, '/patients/%s' % s)

def ComputeMD5(data):
    m = hashlib.md5()
    m.update(data)
    return m.hexdigest()

def GetImage(orthanc, uri, headers = {}):
    # http://www.pythonware.com/library/pil/handbook/introduction.htm
    data = DoGet(orthanc, uri, headers = headers)
    if (sys.version_info >= (3, 0)):
        return Image.open(BytesIO(data))
    else:
        return Image.open(StringIO(data))

def GetArchive(orthanc, uri):
    # http://stackoverflow.com/a/1313868/881731
    s = DoGet(orthanc, uri)

    if (sys.version_info >= (3, 0)):
        return zipfile.ZipFile(BytesIO(s), "r")
    else:
        return zipfile.ZipFile(StringIO(s), "r")

def IsDefinedInLua(orthanc, name):
    s = DoPost(orthanc, '/tools/execute-script', 'print(type(%s))' % name, 'application/lua')
    return (s.strip() != 'nil')

def WaitEmpty(orthanc):
    while True:
        if len(DoGet(orthanc, '/instances')) == 0:
            return
        time.sleep(0.1)

def GetDockerHostAddress():
    route = subprocess.check_output([ '/sbin/ip', 'route' ])
    m = re.search(r'default via ([0-9.]+)', route)
    if m == None:
        return 'localhost'
    else:
        return m.groups()[0]

def FindExecutable(name):
    p = os.path.join('/usr/local/bin', name)
    if os.path.isfile(p):
        return p

    p = os.path.join('/usr/local/sbin', name)
    if os.path.isfile(p):
        return p

    return name



class ExternalCommandThread:
    @staticmethod
    def ExternalCommandFunction(arg, stop_event, command, env):
        external = subprocess.Popen(command, env = env)

        while (not stop_event.is_set()):
            error = external.poll()
            if error != None:
                # http://stackoverflow.com/a/1489838/881731
                os._exit(-1)
            stop_event.wait(0.1)

        print('Stopping the external command')
        external.terminate()
        external.communicate()  # Wait for the command to stop

    def __init__(self, command, env = None):
        self.thread_stop = threading.Event()
        self.thread = threading.Thread(target = self.ExternalCommandFunction, 
                                       args = (10, self.thread_stop, command, env))
        #self.daemon = True
        self.thread.start()

    def stop(self):
        self.thread_stop.set()
        self.thread.join()
