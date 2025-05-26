import unittest
import time
import os
import threading
import pprint
import shutil
from helpers import OrthancTestCase, Helpers, DB

from orthanc_api_client import OrthancApiClient, ChangeType
from orthanc_api_client.exceptions import HttpError
from orthanc_api_client import helpers as OrthancHelpers
from orthanc_api_client import exceptions as orthanc_exceptions

from orthanc_tools import OrthancTestDbPopulator

import pathlib
import subprocess
import glob
here = pathlib.Path(__file__).parent.resolve()


class TestAdvancedStorage(OrthancTestCase):

    @classmethod
    def terminate(cls):

        if Helpers.is_docker():
            subprocess.run(["docker", "rm", "-f", "pg-server"])


    @classmethod
    def prepare(cls):
        if Helpers.db == DB.UNSPECIFIED:
            Helpers.db = DB.PG

        pg_hostname = "localhost"
        if Helpers.is_docker():
            pg_hostname = "pg-server"

        if Helpers.db == DB.PG:
            db_config_key = "PostgreSQL"
            db_config_content = {
                "EnableStorage": False,
                "EnableIndex": True,
                "Host": pg_hostname,
                "Port": 5432,
                "Database": "postgres",
                "Username": "postgres",
                "Password": "postgres"
            }
            config_name = "advanced-storage-pg"
            test_name = "AdvancedStoragePG"
            cls._storage_name = "advanced-storage-pg"
            network_name = "advanced-storage-pg"
        else:
            db_config_key = "NoDatabaseConfig"
            db_config_content = {}
            config_name = "advanced-storage"
            test_name = "AdvancedStorage"
            cls._storage_name = "advanced-storage"
            network_name = "advanced-storage"

        cls.clear_storage(storage_name=cls._storage_name)

        print(f'-------------- preparing {test_name} tests')

        if Helpers.db == DB.PG:
            # launch the docker PG server
            print('--------------- launching PostgreSQL server ------------------')

            if Helpers.is_docker():
                # delete previous container if any
                subprocess.run(["docker", "rm", "-f", "pg-server"])
                cls.create_docker_network(network_name)

            pg_cmd = [            
                "docker", "run", "--rm", 
                "-p", "5432:5432", 
                "--name", "pg-server",
                "--env", "POSTGRES_HOST_AUTH_METHOD=trust"
                ]
            
            if Helpers.is_docker():
                pg_cmd.extend(["--network", network_name])
            pg_cmd.append("postgres:15")

            cls.pg_service_process = subprocess.Popen(pg_cmd)
            time.sleep(5)


        cls.launch_orthanc_to_prepare_db(
            config_name=config_name + "-preparation",
            storage_name=cls._storage_name,
            config={
                "AuthenticationEnabled": False,
                "OverwriteInstances": True,
                "AdvancedStorage": {
                    "Enable": False
                },
                db_config_key : db_config_content
            },
            plugins=Helpers.plugins,
            docker_network=network_name,
            enable_verbose=True
        )

        # upload a study and keep track of data before housekeeper runs
        cls.instances_ids_before = []
        cls.instances_ids_before.extend(cls.o.upload_file(here / "../../Database/Knee/T1/IM-0001-0001.dcm"))
        cls.instances_ids_before.extend(cls.o.upload_file(here / "../../Database/Knee/T1/IM-0001-0002.dcm"))
        cls.instances_ids_before.extend(cls.o.upload_file(here / "../../Database/Knee/T1/IM-0001-0003.dcm"))
        cls.instances_ids_before.extend(cls.o.upload_file(here / "../../Database/Knee/T1/IM-0001-0004.dcm"))

        cls.kill_orthanc()
        time.sleep(3)

        shutil.rmtree('/tmp/indexed-files-a', ignore_errors=True)
        shutil.rmtree('/tmp/indexed-files-b', ignore_errors=True)

        pathlib.Path('/tmp/indexed-files-a').mkdir(parents=True, exist_ok=True)
        pathlib.Path('/tmp/indexed-files-b').mkdir(parents=True, exist_ok=True)

        config = { 
            db_config_key : db_config_content,
            "AuthenticationEnabled": False,
            "OverwriteInstances": True,
            "AdvancedStorage": {
                "Enable": True,
                "NamingScheme": "{split(StudyDate)}/{StudyInstanceUID} - {PatientID}/{SeriesInstanceUID}/{pad6(InstanceNumber)} - {UUID}{.ext}",
                "MaxPathLength": 512,
                "MultipleStorages": {
                    "Storages" : {
                        "a" : cls.get_storage_path(cls._storage_name) + "/storage-a",
                        "b" : cls.get_storage_path(cls._storage_name) + "/storage-b"
                    },
                    "CurrentWriteStorage": "b"
                },
                "OtherAttachmentsPrefix": "other-attachments",
                "Indexer" : {
                    "Enable": True,
                    "Folders": [
                        "/tmp/indexed-files-a/",
                        "/tmp/indexed-files-b/"
                    ],
                    "Interval": 1
                },
                "DelayedDeletion": {
                    "Enable": True
                }
            },
            "StableAge": 1
        }

        config_path = cls.generate_configuration(
            config_name=f"{test_name}",
            storage_name=cls._storage_name,
            config=config,
            plugins=Helpers.plugins
        )

        if Helpers.break_after_preparation:
            print(f"++++ It is now time to start your Orthanc under tests with configuration file '{config_path}' +++++")
            input("Press Enter to continue")
        else:
            cls.launch_orthanc_under_tests(
                config_name=f"{test_name}",
                storage_name=cls._storage_name,
                config=config,
                plugins=Helpers.plugins,
                docker_network=network_name,
                enable_verbose=True
            )

        cls.o = OrthancApiClient(cls.o._root_url)
        cls.o.wait_started()

    def test_can_read_files_saved_without_plugin(self):
        info0 = self.o.get_json(endpoint=f"/instances/{self.instances_ids_before[0]}/attachments/dicom/info")
        self.assertTrue(info0['Path'].startswith(self.get_storage_path(self._storage_name)))
        self.assertFalse(info0['Path'].endswith('.dcm'))
        self.assertFalse(info0['IsAdopted'])
        self.assertFalse('IsIndexed' in info0 and info0['IsIndexed'])

        info1 = self.o.get_json(endpoint=f"/instances/{self.instances_ids_before[1]}/attachments/dicom/info")

        # check if we can move the first instance
        # move it to storage A
        self.o.post(endpoint="/plugins/advanced-storage/move-storage",
                    json={
                        'Resources': [self.instances_ids_before[0]],
                        'TargetStorageId' : 'a'
                    })
        
        # check its path after the move
        info_after_move = self.o.get_json(endpoint=f"/instances/{self.instances_ids_before[0]}/attachments/dicom/info")
        self.assertIn('storage-a', info_after_move['Path'])
        self.assertEqual("a", info_after_move['StorageId'])
        self.assertTrue(os.path.exists(info_after_move['Path']))
        
        self.wait_until_no_more_pending_deletion_files()
        self.assertFalse(os.path.exists(info0['Path']))

        # now delete the instance 0 (the one that has been moved) 
        self.o.instances.delete(orthanc_id=self.instances_ids_before[0])
        
        self.wait_until_no_more_pending_deletion_files()
        self.assertFalse(os.path.exists(info_after_move['Path']))

        # now delete the instance 1 (that has NOT been moved) 
        self.o.instances.delete(orthanc_id=self.instances_ids_before[1])
        
        self.wait_until_no_more_pending_deletion_files()
        self.assertFalse(os.path.exists(info1['Path']))


    def test_basic(self):
        # upload a single file
        uploaded_instances_ids = self.o.upload_file(here / "../../Database/Knix/Loc/IM-0001-0001.dcm")

        # check its path
        info = self.o.get_json(endpoint=f"/instances/{uploaded_instances_ids[0]}/attachments/dicom/info")
        
        self.assertIn('storage-b/2007/01/01/1.2.840.113619.2.176.2025.1499492.7391.1171285944.390 - ozp00SjY2xG/1.2.840.113619.2.176.2025.1499492.7391.1171285944.388/000001 - ', info['Path'])
        self.assertTrue(os.path.exists(info['Path']))
        self.assertTrue(info['Path'].endswith(".dcm"))
        self.assertFalse(info['IsAdopted'])
        self.assertFalse(info['IsIndexed'])
        self.assertEqual("b", info['StorageId'])

    def has_no_more_pending_deletion_files(self):
        status = self.o.get_json("/plugins/advanced-storage/status")
        return status['DelayedDeletionIsActive'] and status['FilesPendingDeletion'] == 0

    def wait_until_no_more_pending_deletion_files(self):
        time.sleep(1)
        OrthancHelpers.wait_until(lambda: self.has_no_more_pending_deletion_files(), timeout=10, polling_interval=1)

    def test_move_storage(self):
        # upload a single file
        uploaded_instances_ids = self.o.upload_file(here / "../../Database/Knix/Loc/IM-0001-0001.dcm")

        # check its path
        info_before_move = self.o.get_json(endpoint=f"/instances/{uploaded_instances_ids[0]}/attachments/dicom/info")
        self.assertIn('storage-b', info_before_move['Path'])
        self.assertEqual("b", info_before_move['StorageId'])
        self.assertTrue(os.path.exists(info_before_move['Path']))

        # move it to storage A
        self.o.post(endpoint="/plugins/advanced-storage/move-storage",
                    json={
                        'Resources': [uploaded_instances_ids[0]],
                        'TargetStorageId' : 'a'
                    })
        
        # check its path after the move
        info_after_move = self.o.get_json(endpoint=f"/instances/{uploaded_instances_ids[0]}/attachments/dicom/info")
        self.assertIn('storage-a', info_after_move['Path'])
        self.assertEqual("a", info_after_move['StorageId'])
        self.assertTrue(os.path.exists(info_after_move['Path']))

        self.wait_until_no_more_pending_deletion_files()
        self.assertFalse(os.path.exists(info_before_move['Path']))

        # move it to back to storage B
        self.o.post(endpoint="/plugins/advanced-storage/move-storage",
                    json={
                        'Resources': [uploaded_instances_ids[0]],
                        'TargetStorageId' : 'b'
                    })
        
        # check its path after the move
        info_after_move2 = self.o.get_json(endpoint=f"/instances/{uploaded_instances_ids[0]}/attachments/dicom/info")
        self.assertIn('storage-b', info_after_move2['Path'])
        self.assertEqual("b", info_after_move2['StorageId'])
        self.assertTrue(os.path.exists(info_after_move2['Path']))

        self.wait_until_no_more_pending_deletion_files()
        self.assertFalse(os.path.exists(info_after_move['Path']))


    def test_adopt_abandon(self):
        # adopt a file
        r1 = self.o.post(endpoint="/plugins/advanced-storage/adopt-instance",
                        json={
                            "Path": str(here / "../../Database/Beaufix/IM-0001-0001.dcm")
                        }).json()
        r2 = self.o.post(endpoint="/plugins/advanced-storage/adopt-instance",
                        json={
                            "Path": str(here / "../../Database/Beaufix/IM-0001-0002.dcm")
                        }).json()

        # pprint.pprint(r1)

        # check its path
        info1 = self.o.get_json(endpoint=f"/instances/{r1['InstanceId']}/attachments/dicom/info")
        self.assertNotIn('storage-b', info1['Path'])
        self.assertNotIn('StorageId', info1)
        self.assertTrue(info1['IsAdopted'])
        self.assertFalse(info1['IsIndexed'])
        self.assertTrue(os.path.exists(info1['Path']))
        self.assertEqual(r1['AttachmentUuid'], info1['Uuid'])

        info2 = self.o.get_json(endpoint=f"/instances/{r2['InstanceId']}/attachments/dicom/info")

        # try to move an adopted file -> it should fail
        with self.assertRaises(orthanc_exceptions.HttpError) as ctx:
            self.o.post(endpoint="/plugins/advanced-storage/move-storage",
                        json={
                            'Resources': [r1['InstanceId']],
                            'TargetStorageId' : 'a'
                        })

        # delete an adopted file -> the file shall not be removed
        self.o.instances.delete(orthanc_id=r1['InstanceId'])
        self.assertNotIn(r1['InstanceId'], self.o.instances.get_all_ids())
        self.assertTrue(os.path.exists(info1['Path']))

        # abandon an adopted file -> the file shall not be removed (it shall be equivalent to a delete)
        self.o.post(endpoint="/plugins/advanced-storage/abandon-instance",
                    json={
                        "Path": str(here / "../../Database/Beaufix/IM-0001-0002.dcm")
                    })
        self.assertNotIn(r2['InstanceId'], self.o.instances.get_all_ids())
        self.assertTrue(os.path.exists(info2['Path']))

    def test_indexer(self):
        # add 2 files to the 2 indexed folders
        shutil.copy(here / "../../Database/Comunix/Ct/IM-0001-0001.dcm", "/tmp/indexed-files-a/")
        shutil.copy(here / "../../Database/Comunix/Pet/IM-0001-0001.dcm", "/tmp/indexed-files-b/")

        # wait for the files to be indexed
        time.sleep(3)

        # check that the study has been indexed
        studies = self.o.studies.find(query={"PatientName": "COMUNIX"})
        self.assertEqual(2, len(studies[0].series))
        
        instances_ids = self.o.studies.get_instances_ids(studies[0].orthanc_id)
        info1 = self.o.get_json(endpoint=f"/instances/{instances_ids[0]}/attachments/dicom/info")
        info2 = self.o.get_json(endpoint=f"/instances/{instances_ids[1]}/attachments/dicom/info")

        self.assertTrue(info1['IsIndexed'])
        self.assertTrue(info1['IsAdopted'])

        # remove one of the file from the indexed folders -> it shall disappear from Orthanc
        os.remove(info1['Path'])

        time.sleep(3)
        studies = self.o.studies.find(query={"PatientName": "COMUNIX"})
        self.assertEqual(1, len(studies[0].series))

        # delete the other file from the Orthanc API -> the file shall not be deleted since it is not owned by Orthanc
        # and it shall not be indexed anymore ...

        self.o.studies.delete(orthanc_id=studies[0].orthanc_id)
        time.sleep(5)
        
        studies = self.o.studies.find(query={"PatientName": "COMUNIX"})
        self.assertEqual(0, len(studies))
        self.assertTrue(os.path.exists(info2['Path']))


