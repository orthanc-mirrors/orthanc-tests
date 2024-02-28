import unittest
import time
import os
from helpers import OrthancTestCase, Helpers

from orthanc_api_client import OrthancApiClient, generate_test_dicom_file
from orthanc_tools import OrthancTestDbPopulator

import pathlib
import glob
here = pathlib.Path(__file__).parent.resolve()


class TestExtraMainDicomTags(OrthancTestCase):

    @classmethod
    def prepare(cls):
        print('-------------- preparing TestExtraMainDicomTags tests')

        cls.clear_storage(storage_name="ExtraMainDicomTags")

        config = {
                "ExtraMainDicomTags": {
                    "Instance" : [
                        "Rows",
                        "PerformedProtocolCodeSequence"
                    ],
                    "Series" : [
                        "RequestAttributesSequence"
                    ],
                    "Study": [],
                    "Patient": []
                },
                "OverwriteInstances": True,
                "DicomWeb" : {
                    "StudiesMetadata" : "MainDicomTags",
                    "SeriesMetadata": "MainDicomTags"
                }
            }

        config_path = cls.generate_configuration(
            config_name="extra_main_dicom_tags",
            storage_name="ExtraMainDicomTags",
            config=config,
            plugins=Helpers.plugins
        )

        print('-------------- prepared ExtraMainDicomTags tests')
        if Helpers.break_after_preparation:
            print(f"++++ It is now time to start your Orthanc under tests with configuration file '{config_path}' +++++")
            input("Press Enter to continue")
        else:
            print('-------------- launching ExtraMainDicomTags tests')
            cls.launch_orthanc_under_tests(
                config_path=config_path,
                config_name="extra_main_dicom_tags",
                storage_name="ExtraMainDicomTags",
                plugins=Helpers.plugins
            )

        print('-------------- waiting for orthanc-under-tests to be available')
        cls.o.wait_started()
        
    def test_main_dicom_tags(self):

        # upload a study
        self.o.upload_file(here / "../../Database/Brainix/Flair/IM-0001-0001.dcm")

        instance = self.o.get(endpoint="instances/4dc71dc0-6093b5f8-ca67aa8a-07b18ff5-95dbe3c8").json()

        self.assertIn("Rows", instance["MainDicomTags"])
        self.assertIn("PerformedProtocolCodeSequence", instance["MainDicomTags"])

    def test_main_dicom_tags_full(self):

        # upload a study
        self.o.upload_file(here / "../../Database/Brainix/Flair/IM-0001-0001.dcm")

        instance = self.o.get(endpoint="instances/4dc71dc0-6093b5f8-ca67aa8a-07b18ff5-95dbe3c8?full").json()

        self.assertIn("0028,0010", instance["MainDicomTags"])
        self.assertIn("0040,0260", instance["MainDicomTags"])


    def test_main_reconstruct(self):

        # upload a study
        self.o.upload_file(here / "../../Database/Brainix/Flair/IM-0001-0001.dcm")

        instance = self.o.get(endpoint="instances/4dc71dc0-6093b5f8-ca67aa8a-07b18ff5-95dbe3c8").json()

        self.assertIn("Rows", instance["MainDicomTags"])
        self.assertIn("PerformedProtocolCodeSequence", instance["MainDicomTags"])

        # reconstruct instance
        self.o.post(endpoint="instances/4dc71dc0-6093b5f8-ca67aa8a-07b18ff5-95dbe3c8/reconstruct", json={})
        instance = self.o.get(endpoint="instances/4dc71dc0-6093b5f8-ca67aa8a-07b18ff5-95dbe3c8").json()
        self.assertIn("Rows", instance["MainDicomTags"])
        self.assertIn("PerformedProtocolCodeSequence", instance["MainDicomTags"])


    def test_tools_find(self):

        # upload a study
        self.o.upload_file(here / "../../Database/Brainix/Flair/IM-0001-0001.dcm")

        # instance level
        r = self.o.post(
            endpoint="tools/find",
            json={
                "Level": "Instances",
                "Query": {
                    "PatientID": "5Yp0E"
                },
                "Expand": True,
                "RequestedTags" : ["Rows", "PerformedProtocolCodeSequence", "ReferencedStudySequence"]  # "ReferencedStudySequence" is not stored in MainDicomTags !
            }
        )

        instances = r.json()
        self.assertEqual(1, len(instances))
        self.assertIn("Rows", instances[0]["RequestedTags"])
        self.assertIn("PerformedProtocolCodeSequence", instances[0]["RequestedTags"])
        self.assertIn("ReferencedStudySequence", instances[0]["RequestedTags"])
       

        # series level, request a sequence
        r = self.o.post(
            endpoint="tools/find",
            json={
                "Level": "Series",
                "Query": {
                    "PatientID": "5Yp0E"
                },
                "Expand": True,
                "RequestedTags" : ["RequestAttributesSequence"]
            }
        )

        series = r.json()
        self.assertEqual(1, len(series))
        self.assertIn("RequestAttributesSequence", series[0]["RequestedTags"])



    def test_dicom_web_metadata(self):

        # upload a study
        self.o.upload_file(here / "../../Database/Brainix/Flair/IM-0001-0001.dcm")

        metadata = self.o.get(
            endpoint="dicom-web/studies/2.16.840.1.113669.632.20.1211.10000357775/metadata"
        ).json()

        self.assertEqual(1, len(metadata))
        self.assertIn("00280010", metadata[0])   # Rows
        self.assertNotIn("00280011", metadata[0])   # Columns should not be stored !
        self.assertIn("00400260", metadata[0])   # PerformedProtocolCodeSequence