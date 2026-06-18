import unittest
import time
import subprocess
import pprint
import os
from helpers import OrthancTestCase, Helpers

from orthanc_api_client import OrthancApiClient, generate_test_dicom_file
from orthanc_api_client import exceptions as orthanc_exceptions
from orthanc_tools import OrthancTestDbPopulator
import requests
import tempfile

import pathlib
here = pathlib.Path(__file__).parent.resolve()



class TestInterruptedDownloads(OrthancTestCase):

    @classmethod
    def prepare(cls):
        test_name = "InterruptedDownloads"
        storage_name = "interrupted_downloads"

        cls.clear_storage(storage_name=storage_name)

        config_path = cls.generate_configuration(
            config_name=f"{test_name}_under_test",
            storage_name=storage_name,
            config={
                "HttpThreadsCount": 3,
                "ConcurrentJobs": 3,
                "LoaderThreads": 3
            },
            plugins=Helpers.plugins
        )

        print(f'-------------- prepared {test_name} tests')
        if Helpers.break_after_preparation:
            print(f"++++ It is now time to start your Orthanc under tests with configuration file '{config_path}' +++++")
            input("Press Enter to continue")
        else:
            print(f'-------------- launching {test_name} tests')
            cls.launch_orthanc_under_tests(
                config_path=config_path,
                config_name=f"{test_name}_under_test",
                storage_name=storage_name,
                plugins=Helpers.plugins
            )

        print('-------------- waiting for orthanc-under-tests to be available')
        cls.o.wait_started()


    def download_with_cancel(self, url, chunk_size=1024, cancel_after_size=25000):
        with tempfile.NamedTemporaryFile(delete = True) as f:

            try:
                    response = requests.get(url, stream=True)
                    response.raise_for_status()

                    with open(f.name, "wb") as file:
                        for chunk in response.iter_content(chunk_size=chunk_size):
                            if chunk:
                                file.write(chunk)
                                # Simulate user canceling the download
                                if file.tell() > cancel_after_size:
                                    print("User canceled the download!")
                                    raise requests.exceptions.RequestException("Download canceled by user.")

                    print("Download completed successfully!")

            except requests.exceptions.RequestException as e:
                print(f"Download canceled: {e}")
                if os.path.exists(f.name):
                    os.remove(f.name)  # Clean up the partial file


    # note: there was a regression between 1.12.10 and 1.12.11
    def test_interrupting_a_download_should_cancel_the_archive_job(self):
        
        # note: there was a regression between 1.12.10 and 1.12.11
        if self.o.is_orthanc_version_at_least(1, 12, 12) and self.o.get_system()["ApiVersion"] >= 32:  # 1.12.11+ and 32 = streaming branch
            self.o.delete_all_content()
            populator = OrthancTestDbPopulator(self.o, studies_count=1, series_count=2, instances_count=200, random_seed=65)
            populator.execute()

            study_id = self.o.studies.get_all_ids()[0]
            self.download_with_cancel(f"{self.o._root_url}/studies/{study_id}/archive")

            time.sleep(1)
            metrics = self.o.get_metrics()

            self.assertEqual(0, int(metrics.get('orthanc_jobs_running')))


    def test_interrupting_a_download_should_release_the_http_thread(self):
        
        # note: there was a regression between 1.12.10 and 1.12.11
        if self.o.is_orthanc_version_at_least(1, 12, 12) and self.o.get_system()["ApiVersion"] >= 32:  # 1.12.11+ and 32 = streaming branch
            self.o.delete_all_content()
            populator = OrthancTestDbPopulator(self.o, studies_count=1, series_count=2, instances_count=200, random_seed=65)
            populator.execute()

            study_id = self.o.studies.get_all_ids()[0]
            # cancel 4 downloads
            self.download_with_cancel(f"{self.o._root_url}/studies/{study_id}/archive")
            self.download_with_cancel(f"{self.o._root_url}/studies/{study_id}/archive")
            self.download_with_cancel(f"{self.o._root_url}/studies/{study_id}/archive")
            self.download_with_cancel(f"{self.o._root_url}/studies/{study_id}/archive")

            time.sleep(1)
            metrics = self.o.get_metrics().metrics
            # pprint.pprint(metrics)
            self.assertGreaterEqual(2, int(metrics.get('orthanc_available_http_threads_count')))  # anyway, we won't be able to get the metrics if this is not true !
