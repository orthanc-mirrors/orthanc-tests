#!/usr/bin/python

# Orthanc - A Lightweight, RESTful DICOM Store
# Copyright (C) 2012-2016 Sebastien Jodogne, Medical Physics
# Department, University Hospital of Liege, Belgium
# Copyright (C) 2017-2018 Osimis S.A., Belgium
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
import uuid

from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication

sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'Tests'))
from Toolbox import *


def _AttachPart(body, path, contentType, boundary):
    with open(path, 'rb') as f:
        body += bytearray('--%s\r\n' % boundary, 'ascii')
        body += bytearray('Content-Type: %s\r\n\r\n' % contentType, 'ascii')
        body += f.read()
        body += bytearray('\r\n', 'ascii')


def SendStow(orthanc, uri, dicom):
    # We do not use Python's "email" package, as it uses LF (\n) for line
    # endings instead of CRLF (\r\n) for binary messages, as required by
    # RFC 1341
    # http://stackoverflow.com/questions/3086860/how-do-i-generate-a-multipart-mime-message-with-correct-crlf-in-python
    # https://www.w3.org/Protocols/rfc1341/7_2_Multipart.html

    # Create a multipart message whose body contains all the input DICOM files
    boundary = str(uuid.uuid4())  # The boundary is a random UUID
    body = bytearray()

    if isinstance(dicom, list):
        for i in range(dicom):
            _AttachPart(body, dicom[i], 'application/dicom', boundary)
    else:
        _AttachPart(body, dicom, 'application/dicom', boundary)

    # Closing boundary
    body += bytearray('--%s--' % boundary, 'ascii')

    # Do the HTTP POST request to the STOW-RS server
    headers = {
        'Content-Type' : 'multipart/related; type=application/dicom; boundary=%s' % boundary,
        'Accept' : 'application/json',
    }

    return DoPost(orthanc, uri, body, headers = headers)
