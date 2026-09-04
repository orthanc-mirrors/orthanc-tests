#!/usr/bin/python3
# -*- coding: utf-8 -*-


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


def Execute(uri, args = {}, user = 'admin@uclouvain.be'):
    body = {
        'level' : 'Series',
        'resource' : 'test'
    }

    for (key, value) in args.items():
        body[key] = value

    return DoPost(ORTHANC, uri, body, headers = { 'Mail' : user })


class Orthanc(unittest.TestCase):
    def setUp(self):
        if (sys.version_info >= (3, 0)):
            # Remove annoying warnings about unclosed socket in Python 3
            import warnings
            warnings.simplefilter("ignore", ResourceWarning)

        DropOrthanc(ORTHANC)

        for user in [ 'admin@uclouvain.be' ]:
            for project in [ '', 'hello' ]:
                layers = Execute('/wsi/api/list-user-layers', { 'project' : project }, user = user)

                for l in layers['user-layers']:
                    Execute('/wsi/api/delete-user-layer', {
                        'layer-id' : l['id'],
                        'project' : project,
                    }, user = user)

                for l in layers['imported-layers']:
                    Execute('/wsi/api/remove-imported-layer', {
                        'layer-id' : l['id'],
                        'project' : project,
                    }, user = user)



    def test_permissions(self):
        info = DoPostRaw(ORTHANC, '/wsi/api/workspace-info', {})
        self.assertEqual(403, info[0].status)

        info = DoPostRaw(ORTHANC, '/wsi/api/workspace-info', {}, headers = { 'Mail' : '' })
        self.assertEqual(400, info[0].status)  # Bad request

        info = DoPostRaw(ORTHANC, '/wsi/api/workspace-info', {
            'level' : 'Series',
            'resource' : 'test'
        }, headers = { 'Mail' : '' })
        self.assertEqual(403, info[0].status)  # Guest users cannot access annotations

        info = DoPost(ORTHANC, '/wsi/api/workspace-info', {
            'level' : 'Series',
            'resource' : 'test'
        }, headers = { 'Mail' : 'admin@uclouvain.be' })

        self.assertEqual(8, len(info))
        self.assertEqual('', info['description'])
        self.assertEqual('', info['name'])
        self.assertEqual('', info['project'])
        self.assertEqual('admin@uclouvain.be', info['user'])
        self.assertEqual('instructor', info['role'])
        self.assertTrue(info['enabled'])
        self.assertTrue(info['persistent'])
        self.assertTrue(info['sharing'])

        info = DoPost(ORTHANC, '/wsi/api/workspace-info', {
            'level' : 'Series',
            'resource' : 'test',
            'project' : 'hello',
        }, headers = { 'Mail' : 'learner@uclouvain.be' })

        self.assertEqual(8, len(info))
        self.assertEqual('', info['description'])
        self.assertEqual('', info['name'])
        self.assertEqual('hello', info['project'])
        self.assertEqual('learner', info['role'])
        self.assertEqual('learner@uclouvain.be', info['user'])
        self.assertTrue(info['enabled'])
        self.assertTrue(info['persistent'])
        self.assertTrue(info['sharing'])


    def test_create_delete_layers(self):
        layers = Execute('/wsi/api/list-user-layers')

        self.assertEqual(2, len(layers))
        self.assertTrue('imported-layers' in layers)
        self.assertTrue('user-layers' in layers)
        self.assertEqual(0, len(layers['imported-layers']))
        self.assertEqual(0, len(layers['user-layers']))

        a = Execute('/wsi/api/create-user-layer')
        self.assertEqual(6, len(a))
        self.assertEqual('#e63946', a['color'])
        self.assertEqual('Default', a['name'])
        self.assertFalse(a['public'])
        self.assertEqual(0, len(a['shared_with']))
        self.assertTrue(a['visible'])

        layers = Execute('/wsi/api/list-user-layers')
        self.assertEqual(0, len(layers['imported-layers']))
        self.assertEqual(1, len(layers['user-layers']))
        self.assertEqual(a['id'], layers['user-layers'][0]['id'])
        self.assertEqual(json.dumps(a), json.dumps(layers['user-layers'][0]))

        b = Execute('/wsi/api/create-user-layer')
        self.assertEqual(6, len(b))
        self.assertEqual('#2a9d8f', b['color'])
        self.assertEqual('Layer 2', b['name'])
        self.assertFalse(b['public'])
        self.assertEqual(0, len(b['shared_with']))
        self.assertTrue(b['visible'])

        c = Execute('/wsi/api/create-user-layer')
        self.assertEqual(6, len(c))
        self.assertEqual('#e9c46a', c['color'])
        self.assertEqual('Layer 3', c['name'])
        self.assertFalse(c['public'])
        self.assertEqual(0, len(c['shared_with']))
        self.assertTrue(c['visible'])

        layers = Execute('/wsi/api/list-user-layers')
        self.assertEqual(0, len(layers['imported-layers']))
        self.assertEqual(3, len(layers['user-layers']))

        self.assertEqual(json.dumps(layers), json.dumps(Execute('/wsi/api/list-user-layers', { 'project' : '' })))

        Execute('/wsi/api/delete-user-layer', { 'layer-id' : a['id'] })

        layers = Execute('/wsi/api/list-user-layers')
        self.assertEqual(0, len(layers['imported-layers']))
        self.assertEqual(2, len(layers['user-layers']))

        self.assertRaises(Exception, lambda: Execute('/wsi/api/delete-user-layer', { 'layer-id' : 'nope' }))

        Execute('/wsi/api/delete-user-layer', { 'layer-id' : c['id'] })

        self.assertRaises(Exception, lambda: Execute('/wsi/api/delete-user-layer', { 'layer-id' : c['id'] }))

        layers = Execute('/wsi/api/list-user-layers')
        self.assertEqual(0, len(layers['imported-layers']))
        self.assertEqual(1, len(layers['user-layers']))
        self.assertEqual(b['id'], layers['user-layers'][0]['id'])
        self.assertEqual(json.dumps(b), json.dumps(layers['user-layers'][0]))


    def test_multiple_projects(self):
        def GetNumberOfLayers(project):
            return len(Execute('/wsi/api/list-user-layers', { 'project' : project }) ['user-layers'])

        self.assertEqual(0, GetNumberOfLayers(''))
        self.assertEqual(0, GetNumberOfLayers('hello'))

        a = Execute('/wsi/api/create-user-layer')
        self.assertEqual(1, GetNumberOfLayers(''))
        self.assertEqual(0, GetNumberOfLayers('hello'))

        b = Execute('/wsi/api/create-user-layer', { 'project' : 'hello' })
        self.assertEqual(1, GetNumberOfLayers(''))
        self.assertEqual(1, GetNumberOfLayers('hello'))

        Execute('/wsi/api/delete-user-layer', { 'layer-id' : a['id'] })
        self.assertEqual(0, GetNumberOfLayers(''))
        self.assertEqual(1, GetNumberOfLayers('hello'))

        Execute('/wsi/api/delete-user-layer', { 'layer-id' : b['id'], 'project' : 'hello' })
        self.assertEqual(0, GetNumberOfLayers(''))
        self.assertEqual(0, GetNumberOfLayers('hello'))


try:
    print('\nStarting the tests...')
    unittest.main(argv = [ sys.argv[0] ] + args.options)

finally:
    print('\nDone')
