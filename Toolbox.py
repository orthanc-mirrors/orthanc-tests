#!/usr/bin/python

# sudo docker run --rm -v `pwd`/Toolbox.py:/tmp/Toolbox.py:ro --entrypoint python jodogne/orthanc-tests /tmp/Toolbox.py


import hashlib
import httplib2
import json
import os.path
from PIL import Image
import zipfile
import time
from urllib import urlencode



# http://stackoverflow.com/a/1313868/881731
try:
    from cStringIO import StringIO
except:
    from StringIO import StringIO



def CreateOrthanc(url = 'http://localhost:8042',
                  username = None,
                  password = None):
    if not url.endswith('/'):
        url += '/'

    return [ url, username, password ]


def _SetupCredentials(orthanc, http):
    if orthanc[1] != None and orthanc[2] != None:
        http.add_credentials(orthanc[1], orthanc[2])


def DoGet(orthanc, uri, data = {}, body = None, headers = {}):
    d = ''
    if len(data.keys()) > 0:
        d = '?' + urlencode(data)

    http = httplib2.Http()
    _SetupCredentials(orthanc, http)

    resp, content = http.request(orthanc[0] + uri + d, 'GET', body = body,
                                 headers = headers)
    if not (resp.status in [ 200 ]):
        raise Exception(resp.status)
    else:
        try:
            return json.loads(content)
        except:
            return content

def _DoPutOrPost(orthanc, uri, method, data, contentType, headers):
    http = httplib2.Http()
    _SetupCredentials(orthanc, http)

    if isinstance(data, str):
        body = data
        if len(contentType) != 0:
            headers['content-type'] = contentType
    else:
        body = json.dumps(data)
        headers['content-type'] = 'application/json'
    
    headers['expect'] = ''

    resp, content = http.request(orthanc[0] + uri, method,
                                 body = body,
                                 headers = headers)
    if not (resp.status in [ 200, 302 ]):
        raise Exception(resp.status)
    else:
        try:
            return json.loads(content)
        except:
            return content

def DoDelete(orthanc, uri):
    http = httplib2.Http()
    _SetupCredentials(orthanc, http)

    resp, content = http.request(orthanc[0] + uri, 'DELETE')
    if not (resp.status in [ 200 ]):
        raise Exception(resp.status)
    else:
        try:
            return json.loads(content)
        except:
            return content

def DoPut(orthanc, uri, data = {}, contentType = ''):
    return DoPutOrPost(orthanc, uri, 'PUT', data, contentType)

def DoPost(orthanc, uri, data = {}, contentType = '', headers = {}):
    return _DoPutOrPost(orthanc, uri, 'POST', data, contentType, headers)

def UploadInstance(orthanc, filename):
    p = os.path.join(HERE, DICOM_DB, filename)
    f = open(p, 'rb')
    d = f.read()
    f.close()
    return DoPost(orthanc, '/instances', d, 'application/dicom')

def UploadFolder(orthanc, path):
     p = os.path.join(HERE, DICOM_DB, path)
     for i in os.listdir(p):
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

def GetImage(orthanc, uri):
    # http://www.pythonware.com/library/pil/handbook/introduction.htm
    data = DoGet(orthanc, uri)
    return Image.open(StringIO(data))

def GetArchive(orthanc, uri):
    # http://stackoverflow.com/a/1313868/881731
    s = DoGet(orthanc, uri)
    return zipfile.ZipFile(StringIO(s), "r")

def IsDefinedInLua(name):
    s = DoPost(orthanc, '/tools/execute-script', 'print(type(%s))' % name, 'application/lua')
    return (s.strip() != 'nil')

def WaitEmpty():
    while True:
        if len(orthanc, DoGet('/instances')) == 0:
            return
        time.sleep(0.1)


print DoGet(CreateOrthanc('http://192.168.215.82:8042'), '/system')
