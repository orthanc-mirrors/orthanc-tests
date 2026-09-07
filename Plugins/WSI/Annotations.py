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
import copy
import os
import pprint
import sys
import unittest

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


ALL_USERS = [
    'admin@uclouvain.be',
    'instructor@uclouvain.be',
    'learner2@uclouvain.be',
    'learner@uclouvain.be',
]


ALL_PROJECTS = [
    '',
    'hello',
]


def Execute(uri, args = {}, user = 'admin@uclouvain.be'):
    body = {
        'level' : 'Series',
        'resource' : 'test'
    }

    for (key, value) in args.items():
        body[key] = value

    return DoPost(ORTHANC, uri, body, headers = { 'Mail' : user })


CREATED_USERS = {}

for user in ALL_USERS:
    CREATED_USERS[user] = Execute('/wsi/api/create-standard-user', { 'name' : user })

    for project in ALL_PROJECTS:
        # Enforce the existence as an active user
        layer = Execute('/wsi/api/create-user-layer', { 'project' : project }, user = user)
        Execute('/wsi/api/delete-user-layer', { 'layer-id' : layer['id'], 'project' : project }, user = user)


class Orthanc(unittest.TestCase):
    def setUp(self):
        if (sys.version_info >= (3, 0)):
            # Remove annoying warnings about unclosed socket in Python 3
            import warnings
            warnings.simplefilter("ignore", ResourceWarning)

        DropOrthanc(ORTHANC)

        for user in ALL_USERS:
            for project in ALL_PROJECTS:
                layers = Execute('/wsi/api/list-user-layers', { 'project' : project }, user = user)

                for l in layers['user-layers']:
                    Execute('/wsi/api/delete-user-layer', {
                        'layer-id' : l['id'],
                        'project' : project,
                    }, user = user)

                for l in layers['imported-layers']:
                    Execute('/wsi/api/remove-imported-layer', {
                        'layer' : l['id'],
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

        self.assertEqual(11, len(info))
        self.assertEqual('', info['description'])
        self.assertEqual('', info['name'])
        self.assertEqual('', info['project'])
        self.assertEqual('admin@uclouvain.be', info['user'])
        self.assertFalse(info['is_learner'])
        self.assertTrue(info['is_instructor'])
        self.assertTrue(info['enabled'])
        self.assertTrue(info['persistent'])
        self.assertTrue(info['sharing'])
        self.assertTrue('learner_to_learner_sharing' in info)

        info = DoPost(ORTHANC, '/wsi/api/workspace-info', {
            'level' : 'Series',
            'resource' : 'test',
            'project' : 'hello',
        }, headers = { 'Mail' : 'learner@uclouvain.be' })

        self.assertEqual(11, len(info))
        self.assertEqual('', info['description'])
        self.assertEqual('', info['name'])
        self.assertEqual('hello', info['project'])
        self.assertEqual('learner@uclouvain.be', info['user'])
        self.assertTrue(info['is_learner'])
        self.assertFalse(info['is_instructor'])
        self.assertTrue(info['enabled'])
        self.assertTrue(info['persistent'])
        self.assertTrue(info['sharing'])
        self.assertTrue('learner_to_learner_sharing' in info)


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


    def test_update_layer(self):
        user = Execute('/wsi/api/create-standard-user', { 'name' : 'world' })
        self.assertEqual(2, len(user))
        self.assertEqual('world', user['name'])
        self.assertEqual(1, user['type'])  # This corresponds to int(OrthancWSI::UserId::Type_Standard) in C++ code

        a = Execute('/wsi/api/create-user-layer')

        layers = Execute('/wsi/api/list-user-layers')
        self.assertEqual(json.dumps(a), json.dumps(layers['user-layers'][0]))

        Execute('/wsi/api/save-user-layer', { 'layer' : a })
        self.assertEqual(json.dumps(a), json.dumps(layers['user-layers'][0]))  # No change

        b = copy.copy(a)
        b['id'] = 'nope'
        self.assertRaises(Exception, lambda: Execute('/wsi/api/save-user-layer', { 'layer' : b }))

        self.assertEqual(json.dumps(a), json.dumps(layers['user-layers'][0]))  # No change

        b = {
            'id' : a['id'],
            'color' : '#112233',
            'name' : 'Hello',
            'public' : True,
            'shared_with' : [ user ],
            'visible' : False,
        }

        Execute('/wsi/api/save-user-layer', { 'layer' : b })

        layers = Execute('/wsi/api/list-user-layers')
        self.assertEqual(json.dumps(b, sort_keys=True),
                         json.dumps(layers['user-layers'][0], sort_keys=True))


        b['color'] = 'invalid'
        self.assertRaises(Exception, lambda: Execute('/wsi/api/save-user-layer', { 'layer' : b }))


    def test_search_active_users(self):
        def UnpackSetOfStandardUsers(users):
            s = []
            for user in users:
                self.assertEqual(1, user['type'])  # This corresponds to int(OrthancWSI::UserId::Type_Standard) in C++ code
                self.assertFalse(user['name'] in s)
                s.append(user['name'])
            return s

        v = UnpackSetOfStandardUsers(Execute('/wsi/api/search-active-users', { 'query' : '' }))
        self.assertEqual(3, len(v))
        self.assertTrue('instructor@uclouvain.be' in v)
        self.assertTrue('learner@uclouvain.be' in v)
        self.assertTrue('learner2@uclouvain.be' in v)

        v = UnpackSetOfStandardUsers(Execute('/wsi/api/search-active-users', { 'query' : 'l' }))
        self.assertEqual(3, len(v))
        self.assertTrue('instructor@uclouvain.be' in v)
        self.assertTrue('learner@uclouvain.be' in v)
        self.assertTrue('learner2@uclouvain.be' in v)

        v = UnpackSetOfStandardUsers(Execute('/wsi/api/search-active-users', { 'query' : 'lear' }))
        self.assertEqual(2, len(v))
        self.assertTrue('learner@uclouvain.be' in v)
        self.assertTrue('learner2@uclouvain.be' in v)

        v = UnpackSetOfStandardUsers(Execute('/wsi/api/search-active-users', { 'query' : 'ins' }))
        self.assertEqual(1, len(v))
        self.assertTrue('instructor@uclouvain.be' in v)

        v = UnpackSetOfStandardUsers(Execute('/wsi/api/search-active-users', { 'query' : '' }, user = 'instructor@uclouvain.be'))
        self.assertEqual(3, len(v))
        self.assertTrue('admin@uclouvain.be' in v)
        self.assertTrue('learner@uclouvain.be' in v)
        self.assertTrue('learner2@uclouvain.be' in v)

        info = Execute('/wsi/api/workspace-info')

        v = UnpackSetOfStandardUsers(Execute('/wsi/api/search-active-users', { 'query' : '' }, user = 'learner@uclouvain.be'))
        if info['learner_to_learner_sharing']:
            self.assertEqual(3, len(v))
            self.assertTrue('admin@uclouvain.be' in v)
            self.assertTrue('instructor@uclouvain.be' in v)
            self.assertTrue('learner2@uclouvain.be' in v)
        else:
            self.assertEqual(2, len(v))
            self.assertTrue('admin@uclouvain.be' in v)
            self.assertTrue('instructor@uclouvain.be' in v)


    def test_user_features(self):
        Execute('/wsi/api/save-user-features', {
            'features' : [
                # Those are the minimal fields enforced by the plugin, the rest is managed by the JavaScript
                { 'type' : 'a',
                  'layer-id' : 'b' },
                { 'type' : 'c',
                  'layer-id' : 'd' }
            ]
        })

        a = Execute('/wsi/api/load-user-features') ['features']
        self.assertEqual(2, len(a))
        self.assertEqual('a', a[0]['type'])
        self.assertEqual('b', a[0]['layer-id'])
        self.assertEqual('c', a[1]['type'])
        self.assertEqual('d', a[1]['layer-id'])


    def test_list_sharing_users(self):
        def CheckNoSharing(viewer):
            s = Execute('/wsi/api/list-sharing-users', user = viewer)
            self.assertEqual(0, len(s))

            for i in ALL_USERS:
                s = Execute('/wsi/api/list-shared-layers', { 'author' : CREATED_USERS[i] }, user = viewer)
                self.assertEqual(0, len(s))

        def CheckSharingUser(expected_author, expected_layer, viewer):
            s = Execute('/wsi/api/list-sharing-users', user = viewer)
            self.assertEqual(1, len(s))
            self.assertEqual(2, len(s[0]))
            self.assertEqual(1, s[0]['type'])
            self.assertEqual(expected_author, s[0]['name'])

            for i in ALL_USERS:
                import_body = {
                    'author' : CREATED_USERS[i],
                    'layer' : expected_layer,
                }

                if i == expected_author:
                    s = Execute('/wsi/api/list-shared-layers', { 'author' : CREATED_USERS[i] }, user = viewer)
                    self.assertEqual(1, len(s))

                    t = Execute('/wsi/api/import-layer', import_body, user = viewer)
                    Execute('/wsi/api/remove-imported-layer', { 'layer' : expected_layer }, user = viewer)
                else:
                    s = Execute('/wsi/api/list-shared-layers', { 'author' : CREATED_USERS[i] }, user = viewer)
                    self.assertEqual(0, len(s))

                    self.assertRaises(Exception, lambda: Execute('/wsi/api/import-layer', import_body, user = viewer))


        instructor = CREATED_USERS['instructor@uclouvain.be']
        learner = CREATED_USERS['learner@uclouvain.be']
        learner2 = CREATED_USERS['learner2@uclouvain.be']

        # Test sharing from instructors
        a = Execute('/wsi/api/create-user-layer', user = 'admin@uclouvain.be')

        CheckNoSharing('admin@uclouvain.be')
        CheckNoSharing('instructor@uclouvain.be')
        CheckNoSharing('learner2@uclouvain.be')
        CheckNoSharing('learner@uclouvain.be')

        a['shared_with'] = []
        a['public'] = True
        Execute('/wsi/api/save-user-layer', { 'layer' : a }, user = 'admin@uclouvain.be')

        CheckSharingUser('admin@uclouvain.be', a['id'], 'instructor@uclouvain.be')
        CheckSharingUser('admin@uclouvain.be', a['id'], 'learner@uclouvain.be')
        CheckSharingUser('admin@uclouvain.be', a['id'], 'learner2@uclouvain.be')

        a['shared_with'] = []
        a['public'] = False
        Execute('/wsi/api/save-user-layer', { 'layer' : a }, user = 'admin@uclouvain.be')

        CheckNoSharing('instructor@uclouvain.be')
        CheckNoSharing('learner@uclouvain.be')
        CheckNoSharing('learner2@uclouvain.be')

        a['shared_with'] = [ learner ]
        a['public'] = False
        Execute('/wsi/api/save-user-layer', { 'layer' : a }, user = 'admin@uclouvain.be')

        CheckSharingUser('admin@uclouvain.be', a['id'], 'learner@uclouvain.be')
        CheckNoSharing('instructor@uclouvain.be')
        CheckNoSharing('learner2@uclouvain.be')

        a['shared_with'] = [ instructor ]
        a['public'] = False
        Execute('/wsi/api/save-user-layer', { 'layer' : a }, user = 'admin@uclouvain.be')

        CheckSharingUser('admin@uclouvain.be', a['id'], 'instructor@uclouvain.be')
        CheckNoSharing('learner@uclouvain.be')
        CheckNoSharing('learner2@uclouvain.be')

        Execute('/wsi/api/delete-user-layer', { 'layer-id' : a['id'] }, user = 'admin@uclouvain.be')


        # Test sharing from learners
        a = Execute('/wsi/api/create-user-layer', user = 'learner@uclouvain.be')

        CheckNoSharing('admin@uclouvain.be')
        CheckNoSharing('instructor@uclouvain.be')
        CheckNoSharing('learner2@uclouvain.be')
        CheckNoSharing('learner@uclouvain.be')

        a['shared_with'] = []
        a['public'] = True
        Execute('/wsi/api/save-user-layer', { 'layer' : a }, user = 'learner@uclouvain.be')

        CheckSharingUser('learner@uclouvain.be', a['id'], 'instructor@uclouvain.be')
        CheckSharingUser('learner@uclouvain.be', a['id'], 'admin@uclouvain.be')
        CheckNoSharing('learner2@uclouvain.be')  # For learners, "public" means "shared with any instructor"

        a['shared_with'] = []
        a['public'] = False
        Execute('/wsi/api/save-user-layer', { 'layer' : a }, user = 'learner@uclouvain.be')

        CheckNoSharing('instructor@uclouvain.be')
        CheckNoSharing('admin@uclouvain.be')
        CheckNoSharing('learner2@uclouvain.be')

        a['shared_with'] = [ learner2 ]
        a['public'] = False
        Execute('/wsi/api/save-user-layer', { 'layer' : a }, user = 'learner@uclouvain.be')

        info = Execute('/wsi/api/workspace-info')
        if info['learner_to_learner_sharing']:
            CheckSharingUser('learner@uclouvain.be', a['id'], 'learner2@uclouvain.be')
        else:
            CheckNoSharing('learner2@uclouvain.be')

        CheckNoSharing('instructor@uclouvain.be')
        CheckNoSharing('admin@uclouvain.be')

        a['shared_with'] = [ instructor ]
        a['public'] = False
        Execute('/wsi/api/save-user-layer', { 'layer' : a }, user = 'learner@uclouvain.be')

        CheckSharingUser('learner@uclouvain.be', a['id'], 'instructor@uclouvain.be')
        CheckNoSharing('admin@uclouvain.be')
        CheckNoSharing('learner2@uclouvain.be')

        Execute('/wsi/api/delete-user-layer', { 'layer-id' : a['id'] }, user = 'learner@uclouvain.be')


    def test_import_layer(self):
        a = Execute('/wsi/api/create-user-layer', user = 'learner@uclouvain.be')
        a['public'] = True

        self.assertRaises(Exception, lambda: Execute('/wsi/api/save-user-layer', { 'layer' : a }))
        Execute('/wsi/api/save-user-layer', { 'layer' : a }, user = 'learner@uclouvain.be')

        b = Execute('/wsi/api/list-user-layers')
        self.assertEqual(0, len(b['imported-layers']))

        Execute('/wsi/api/import-layer', {
            'author' : CREATED_USERS['learner@uclouvain.be'],
            'layer' : a['id'],
        })

        b = Execute('/wsi/api/list-user-layers')
        self.assertEqual(1, len(b['imported-layers']))
        imported = b['imported-layers'][0]

        self.assertEqual(5, len(imported))
        self.assertEqual('learner@uclouvain.be', imported['author']['name'])
        self.assertEqual(1, imported['author']['type'])
        self.assertEqual('#e63946', imported['color'])
        self.assertEqual(a['id'], imported['id'])
        self.assertEqual('Default', imported['name'])
        self.assertTrue(imported['visible'])

        Execute('/wsi/api/save-imported-layer', {
            'layer' : {
                'author' : imported['author'],
                'id' : a['id'],
                'color' : '#0000ff',
                'visible' : False,
                'name' : 'Hello',
            }
        })

        b = Execute('/wsi/api/list-user-layers')
        self.assertEqual(1, len(b['imported-layers']))
        imported = b['imported-layers'][0]

        self.assertEqual(5, len(imported))
        self.assertEqual('learner@uclouvain.be', imported['author']['name'])
        self.assertEqual(1, imported['author']['type'])
        self.assertEqual('#0000ff', imported['color'])
        self.assertEqual(a['id'], imported['id'])
        self.assertEqual('Hello', imported['name'])
        self.assertFalse(imported['visible'])

        Execute('/wsi/api/remove-imported-layer', { 'layer' : a['id'] })


    def test_import_features(self):
        a = Execute('/wsi/api/create-user-layer')
        a['public'] = True
        Execute('/wsi/api/save-user-layer', { 'layer' : a })  # Make layer "a" public

        b = Execute('/wsi/api/create-user-layer')  # Layer "b" is private

        Execute('/wsi/api/import-layer', {
            'author' : CREATED_USERS['admin@uclouvain.be'],
            'layer' : a['id'],
        }, user = 'learner@uclouvain.be')

        c = Execute('/wsi/api/load-imported-features', user = 'learner@uclouvain.be')
        self.assertEqual(0, len(c['features']))

        Execute('/wsi/api/save-user-features', {
            'features' : [
                # Those are the minimal fields enforced by the plugin, the rest is managed by the JavaScript
                { 'type' : 'a',
                  'layer-id' : a['id'] },
                { 'type' : 'b',
                  'layer-id' : b['id'] },
                { 'type' : 'c',
                  'layer-id' : a['id'] }
            ]
        })

        c = Execute('/wsi/api/load-imported-features', user = 'learner@uclouvain.be')
        self.assertEqual(2, len(c['features']))
        self.assertEqual('a', c['features'][0]['type'])
        self.assertEqual(a['id'], c['features'][0]['layer-id'])
        self.assertEqual('c', c['features'][1]['type'])
        self.assertEqual(a['id'], c['features'][1]['layer-id'])

        Execute('/wsi/api/save-user-features', {
            'features' : [
                { 'type' : 'b',
                  'layer-id' : a['id'] },
            ]
        })

        c = Execute('/wsi/api/load-imported-features', user = 'learner@uclouvain.be')
        self.assertEqual(1, len(c['features']))
        self.assertEqual('b', c['features'][0]['type'])
        self.assertEqual(a['id'], c['features'][0]['layer-id'])

        Execute('/wsi/api/remove-imported-layer', { 'layer' : a['id'] }, user = 'learner@uclouvain.be')

        c = Execute('/wsi/api/load-imported-features', user = 'learner@uclouvain.be')
        self.assertEqual(0, len(c['features']))


try:
    print('\nStarting the tests...')
    unittest.main(argv = [ sys.argv[0] ] + args.options)

finally:
    print('\nDone')
