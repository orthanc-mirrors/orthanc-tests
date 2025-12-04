import subprocess
import time
import unittest
from orthanc_api_client import OrthancApiClient, ResourceType
from orthanc_tools import OrthancTestDbPopulator
from helpers import Helpers, wait_container_healthy

import pathlib
import os
here = pathlib.Path(__file__).parent.resolve()




class TestConcurrencyDicomWeb(unittest.TestCase):

    @classmethod
    def cleanup(cls):
        os.chdir(here)
        print("Cleaning old compose")
        subprocesss_env = os.environ.copy()
        subprocesss_env["ORTHANC_IMAGE_UNDER_TESTS"] = Helpers.orthanc_under_tests_docker_image
        subprocess.run(["docker", "compose", "-f", "docker-compose-transfers-concurrency.yml", "down", "-v", "--remove-orphans"], 
                       env=subprocesss_env, check=True)

    @classmethod
    def compose_up(cls):
        # print("Pullling containers")
        # subprocesss_env = os.environ.copy()
        # subprocesss_env["ORTHANC_IMAGE_UNDER_TESTS"] = Helpers.orthanc_under_tests_docker_image
        # subprocess.run(["docker", "compose", "-f", "docker-compose-transfers-concurrency.yml", "pull"], 
        #                env=subprocesss_env, check=True)

        print("Compose up")
        subprocesss_env = os.environ.copy()
        subprocesss_env["ORTHANC_IMAGE_UNDER_TESTS"] = Helpers.orthanc_under_tests_docker_image
        subprocess.run(["docker", "compose", "-f", "docker-compose-transfers-concurrency.yml", "up", "-d"], 
                       env=subprocesss_env, check=True)


    @classmethod
    def setUpClass(cls):
        cls.cleanup()
        cls.compose_up()

    @classmethod
    def tearDownClass(cls):
        cls.cleanup()
        pass

    def clean_start(self):
        oa = OrthancApiClient("http://localhost:8062")
        ob = OrthancApiClient("http://localhost:8063")

        oa.wait_started()
        ob.wait_started()

        oa.delete_all_content()
        ob.delete_all_content()

        return oa, ob

    def test_wado_rs_retrieve(self):
        oa, ob = self.clean_start()

        instances_count_per_series = 30
        series_count_per_study = 3
        populator = OrthancTestDbPopulator(ob, studies_count=5, series_count=series_count_per_study, instances_count=instances_count_per_series, random_seed=65)
        populator.execute()

        all_studies_ids = ob.studies.get_all_ids()

        for study_id in all_studies_ids:
            study_instance_uid = ob.studies.get(study_id).main_dicom_tags.get('StudyInstanceUID')
            oa.dicomweb_servers.retrieve_study(remote_server='b', study_instance_uid=study_instance_uid)

            study_id_a = oa.studies.lookup(study_instance_uid)
            self.assertEqual(study_id, study_id_a)

            self.assertEqual(series_count_per_study * instances_count_per_series, len(oa.studies.get_instances_ids(study_id_a)))

