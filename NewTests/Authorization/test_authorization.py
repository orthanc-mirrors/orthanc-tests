import unittest
import time
import pprint
import subprocess
from helpers import OrthancTestCase, Helpers

from orthanc_api_client import OrthancApiClient, generate_test_dicom_file
from orthanc_api_client import exceptions as orthanc_exceptions

import logging
import pathlib
here = pathlib.Path(__file__).parent.resolve()



class TestAuthorization(OrthancTestCase):

    label_a_study_id = None
    label_b_study_id = None
    no_label_study_id = None
    auth_service_process = None

    @classmethod
    def terminate(cls):
        cls.auth_service_process.terminate()

    @classmethod
    def prepare(cls):
        test_name = "Authorization"
        storage_name = "authorization"

        print(f'-------------- preparing {test_name} tests')

        cls.clear_storage(storage_name=storage_name)

        auth_service_hostname = "localhost"
        if Helpers.is_docker():
            auth_service_hostname = "auth-service"
            cls.create_docker_network("auth-test-network")

        config = {
                "AuthenticationEnabled": False,
                "Authorization": {
                    "WebServiceRootUrl": f"http://{auth_service_hostname}:8020/",
                    "StandardConfigurations": [
                        "orthanc-explorer-2",
                        "stone-webviewer"
                    ],
                    "CheckedLevel": "studies",
                    "TokenHttpHeaders": ["user-token-key", "resource-token-key"],
                    "TokenGetArguments": ["resource-token-key"]
                }
            }

        config_path = cls.generate_configuration(
            config_name=f"{test_name}",
            storage_name=storage_name,
            config=config,
            plugins=Helpers.plugins
        )

        if Helpers.is_exe():
            # Start the auth-service application as a subprocess and wait for it to start
            cls.auth_service_process = subprocess.Popen(["uvicorn", "auth_service:app", "--host", "0.0.0.0", "--port", "8020"], cwd=here)
            time.sleep(2)
        else:
            # first build the docker image for the auth-service
            subprocess.run(["docker", "build", "-t", "auth-service", "."], cwd=here)
            cls.auth_service_process = subprocess.Popen(["docker", "run", "-p", "8020:8020", "--network", "auth-test-network", "--name", "auth-service", "auth-service"])
            pass


        if Helpers.break_before_preparation:
            print(f"++++ It is now time to start your Orthanc under tests with configuration file '{config_path}' +++++")
            input("Press Enter to continue")
        else:
            cls.launch_orthanc_under_tests(
                config_name=f"{test_name}",
                storage_name=storage_name,
                config=config,
                plugins=Helpers.plugins,
                docker_network="auth-test-network"
            )

        uploader = OrthancApiClient(cls.o._root_url, headers={"user-token-key": "token-uploader"})

        uploader.delete_all_content()

        # upload a few studies and add labels
        instances_ids = uploader.upload_file(here / "../../Database/Knix/Loc/IM-0001-0001.dcm")
        cls.label_a_study_id = uploader.instances.get_parent_study_id(instances_ids[0])
        uploader.studies.add_label(cls.label_a_study_id, "label_a")

        instances_ids = uploader.upload_file(here / "../../Database/Brainix/Epi/IM-0001-0001.dcm")
        cls.label_b_study_id = uploader.instances.get_parent_study_id(instances_ids[0])
        uploader.studies.add_label(cls.label_b_study_id, "label_b")

        instances_ids = uploader.upload_file(here / "../../Database/Comunix/Pet/IM-0001-0001.dcm")
        cls.no_label_study_id = uploader.instances.get_parent_study_id(instances_ids[0])


    def assert_is_forbidden(self, api_call):
        with self.assertRaises(orthanc_exceptions.HttpError) as ctx:
            api_call()
        self.assertEqual(403, ctx.exception.http_status_code)


    def test_admin_user(self):
        
        o = OrthancApiClient(self.o._root_url, headers={"user-token-key": "token-admin"})

        # make sure we can access all these urls (they would throw if not)
        system = o.get_system()

        # make sure we can access all studies
        o.studies.get_tags(self.no_label_study_id)
        o.studies.get_tags(self.label_a_study_id)
        o.studies.get_tags(self.label_b_study_id)

        # make sure we can access series and instances of these studies
        series_ids = o.studies.get_series_ids(self.label_a_study_id)
        instances_ids = o.series.get_instances_ids(series_ids[0])
        o.instances.get_tags(instances_ids[0])

        # make sure labels filtering still works
        self.assertEqual(3, len(o.studies.find(query={},
                                               labels=[],
                                               labels_constraint='Any')))

        self.assertEqual(2, len(o.studies.find(query={},
                                               labels=['label_a', 'label_b'],
                                               labels_constraint='Any')))

        self.assertEqual(2, len(o.studies.find(query={},
                                               labels=['label_a'],
                                               labels_constraint='None')))

        all_labels = o.get_all_labels()
        self.assertEqual(2, len(all_labels))

    def test_user_a(self):
        
        o = OrthancApiClient(self.o._root_url, headers={"user-token-key": "token-user-a"})

        # # make sure we can access all these urls (they would throw if not)
        # system = o.get_system()

        all_labels = o.get_all_labels()
        self.assertEqual(1, len(all_labels))
        self.assertEqual("label_a", all_labels[0])

        # make sure we can access only the label_a studies
        self.assert_is_forbidden(lambda: o.studies.get_tags(self.label_b_study_id))
        self.assert_is_forbidden(lambda: o.studies.get_tags(self.no_label_study_id))

        # should not raise
        o.studies.get_tags(self.label_a_study_id)

        # make sure we can access series and instances of the label_a studies
        series_ids = o.studies.get_series_ids(self.label_a_study_id)
        instances_ids = o.series.get_instances_ids(series_ids[0])
        o.instances.get_tags(instances_ids[0])

        # make sure we can not access series and instances of the label_b studies
        self.assert_is_forbidden(lambda: o.studies.get_series_ids(self.label_b_study_id))

        # make sure tools/find only returns the label_a studies
        studies = o.studies.find(query={},
                                 labels=[],
                                 labels_constraint='Any')
        self.assertEqual(1, len(studies))
        self.assertEqual(self.label_a_study_id, studies[0].orthanc_id)

        # if searching Any of label_a & label_b, return only label_a
        studies = o.studies.find(query={},
                                 labels=['label_a', 'label_b'],
                                 labels_constraint='Any')
        self.assertEqual(1, len(studies))
        self.assertEqual(self.label_a_study_id, studies[0].orthanc_id)

        # if searching Any of label_b, expect a Forbidden access
        self.assert_is_forbidden(lambda: o.studies.find(query={},
                                                        labels=['label_b'],
                                                        labels_constraint='Any'))

        # if searching None of label_b, expect a Forbidden access because we are not able to compute this filter
        self.assert_is_forbidden(lambda: o.studies.find(query={},
                                                        labels=['label_b'],
                                                        labels_constraint='None'))

        # if searching All of label_b, expect a Forbidden access because we are not able to compute this filter
        self.assert_is_forbidden(lambda: o.studies.find(query={},
                                                        labels=['label_b'],
                                                        labels_constraint='All'))

        studies = o.studies.find(query={"PatientName": "KNIX"},  # KNIX is label_a
                                 labels=[],
                                 labels_constraint='Any')
        self.assertEqual(1, len(studies))

        studies = o.studies.find(query={"PatientName": "KNIX"},  # KNIX is label_a
                                 labels=['label_a'],
                                 labels_constraint='Any')
        self.assertEqual(1, len(studies))

        self.assert_is_forbidden(lambda: o.studies.find(query={"PatientName": "KNIX"},  # KNIX is label_a
                                                        labels=['label_b'],
                                                        labels_constraint='Any'))

        # make sure some generic routes are not accessible
        self.assert_is_forbidden(lambda: o.get_json('patients?expand'))
        self.assert_is_forbidden(lambda: o.get_json('studies?expand'))
        self.assert_is_forbidden(lambda: o.get_json('series?expand'))
        self.assert_is_forbidden(lambda: o.get_json('instances?expand'))
        self.assert_is_forbidden(lambda: o.get_json('studies'))
        self.assert_is_forbidden(lambda: o.get_json('studies/'))



    def test_resource_token(self):

        o = OrthancApiClient(self.o._root_url, headers={"resource-token-key": "token-knix-study"})

        # with a resource token, we can access only the given resource, not generic resources or resources from other studies

        # generic resources are forbidden
        self.assert_is_forbidden(lambda: o.studies.find(query={"PatientName": "KNIX"},  # KNIX is label_a
                                                        labels=['label_b'],
                                                        labels_constraint='Any'))
        self.assert_is_forbidden(lambda: o.get_all_labels())
        self.assert_is_forbidden(lambda: o.studies.get_all_ids())
        self.assert_is_forbidden(lambda: o.patients.get_all_ids())
        self.assert_is_forbidden(lambda: o.series.get_all_ids())
        self.assert_is_forbidden(lambda: o.instances.get_all_ids())
        self.assert_is_forbidden(lambda: o.get_json('patients?expand'))
        self.assert_is_forbidden(lambda: o.get_json('studies?expand'))
        self.assert_is_forbidden(lambda: o.get_json('series?expand'))
        self.assert_is_forbidden(lambda: o.get_json('instances?expand'))
        
        # some resources are still accessible to the 'anonymous' user  -> does not throw
        o.get_system()
        o.lookup("1.2.3")   # this route is still explicitely authorized because it is used by Stone

        # other studies are forbidden
        self.assert_is_forbidden(lambda: o.studies.get_series_ids(self.label_b_study_id))

        # the label_a study is allowed
        o.studies.get_series_ids(self.label_a_study_id)

        # TODO: test with DicomWEB routes + sub-routes