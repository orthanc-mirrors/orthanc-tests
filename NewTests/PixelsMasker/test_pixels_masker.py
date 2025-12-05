import unittest
import time
import os
from helpers import OrthancTestCase, Helpers

from orthanc_api_client import OrthancApiClient, generate_test_dicom_file
from orthanc_tools import OrthancTestDbPopulator

import pathlib
import glob
import pprint
here = pathlib.Path(__file__).parent.resolve()


class TestPixelsMasker(OrthancTestCase):

    @classmethod
    def prepare(cls):
        print('-------------- preparing TestPixelsMasker tests')

        cls.clear_storage(storage_name="PixelsMasker")

        config = {
                "PixelsMasker": {
                    "Enable": True
                }
            }

        config_path = cls.generate_configuration(
            config_name="pixels_masker",
            storage_name="PixelsMasker",
            config=config,
            plugins=Helpers.plugins
        )

        print('-------------- prepared PixelsMasker tests')
        if Helpers.break_after_preparation:
            print(f"++++ It is now time to start your Orthanc under tests with configuration file '{config_path}' +++++")
            input("Press Enter to continue")
        else:
            print('-------------- launching PixelsMasker tests')
            cls.launch_orthanc_under_tests(
                config_path=config_path,
                config_name="pixels_masker",
                storage_name="PixelsMasker",
                plugins=Helpers.plugins
            )

        print('-------------- waiting for orthanc-under-tests to be available')
        cls.o.wait_started()
        
    def are_instances_identical(self, series_id_a, series_id_b, instance_index):
        instance_id_a = self.o.series.get_ordered_instances_ids(series_id_a)[instance_index]
        instance_id_b = self.o.series.get_ordered_instances_ids(series_id_b)[instance_index]

        raw_a = self.o.get_binary(f"/instances/{instance_id_a}/numpy").decode('latin1')
        raw_b = self.o.get_binary(f"/instances/{instance_id_b}/numpy").decode('latin1')

        return raw_a == raw_b


    def test_basic_study(self):

        self.o.delete_all_content()
        uploaded_instances_ids = self.o.upload_folder(here / "../../Database/Brainix/Epi")
        original_study_id = self.o.instances.get_parent_study_id(uploaded_instances_ids[0])

        r = self.o.post(endpoint=f"/plugins/pixels-masker/studies/{original_study_id}/modify",
                    json={
                        "KeepSource": True,
                        "Force": True,
                        "Replace": {
                            "PatientID": "averaged"
                        },
                        "MaskPixelData": {
                            "Regions": [{
                                "MaskType": "MeanFilter",
                                "FilterWidth": 30,
                                "RegionType" : "3D",
                                "Origin": [-100, -100, 0],
                                "End": [100, 100, 40]
                        }]
                        }
                    }).json()

        modified_study = self.o.studies.get(r['ID'])
        self.assertEqual("averaged", modified_study.patient_main_dicom_tags.get("PatientID"))
        self.assertEqual(original_study_id, r['ParentResources'][0])
        self.assertEqual(22, len(self.o.studies.get_instances_ids(modified_study.orthanc_id)))


        # compare instances, only the middle one should have been modified
        self.assertTrue(self.are_instances_identical(self.o.studies.get_series_ids(original_study_id)[0],
                                                     self.o.studies.get_series_ids(modified_study.orthanc_id)[0],
                                                     1))

        self.assertTrue(self.are_instances_identical(self.o.studies.get_series_ids(original_study_id)[0],
                                                     self.o.studies.get_series_ids(modified_study.orthanc_id)[0],
                                                     20))

        self.assertFalse(self.are_instances_identical(self.o.studies.get_series_ids(original_study_id)[0],
                                                     self.o.studies.get_series_ids(modified_study.orthanc_id)[0],
                                                     10))
