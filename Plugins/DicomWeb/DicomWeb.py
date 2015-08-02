#!/usr/bin/python

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


import os
import sys
import email
import urllib2

from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication

sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'Tests'))
from Toolbox import *


def _AttachPart(related, path, contentType):
    with open(path, 'rb') as f:
        part = MIMEApplication(f.read(), contentType, email.encoders.encode_noop)
        related.attach(part)


def SendStow(orthanc, uri, dicom):
    related = MIMEMultipart('related')
    related.set_boundary('boundary_0123456789_boundary')

    if isinstance(dicom, list):
        for i in range(dicom):
            _AttachPart(related, dicom[i], 'dicom')
    else:
        _AttachPart(related, dicom, 'dicom')

    headers = dict(related.items())
    body = related.as_string()

    # Discard the header
    body = body.split('\n\n', 1)[1]

    headers['Content-Type'] = 'multipart/related; type=application/dicom; boundary=%s' % related.get_boundary()
    headers['Accept'] = 'application/json'

    return DoPost(orthanc, uri, body, headers = headers)


def GetMultipart(uri, headers = {}):
    tmp = urllib2.urlopen(uri)
    info = str(tmp.info())
    answer = tmp.read()

    s = info + "\n" + answer

    msg = email.message_from_string(s)

    result = []

    for i, part in enumerate(msg.walk(), 1):
        payload = part.get_payload(decode = True)
        if payload != None:
            result.append(payload)

    return result
