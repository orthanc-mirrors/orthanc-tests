import subprocess
import time
import unittest
from orthanc_api_client import OrthancApiClient
from orthanc_tools import OrthancTestDbPopulator
from helpers import Helpers, wait_container_healthy
from contextlib import contextmanager
from typing import Callable, Tuple
from urllib.parse import urlparse
import shutil

import pathlib
import os
import requests
here = pathlib.Path(__file__).parent.resolve()


# test_configs = {
#     "ref": {
#         "orthanc-url": "http://localhost:8142"
#     },
#     "new": {
#         "orthanc-url": "http://localhost:8143"
#     },
#     "ref-s3": {
#         "orthanc-url": "http://localhost:8242"
#     },
#     "new-s3": {
#         "orthanc-url": "http://localhost:8243"
#     }
# }

# test_results = {}

# Download a file localy (only the first time) and return its local_path and content
def download_test_file(url: str) -> Tuple[str, bytes]:
    local_path = here / "DownloadedTestFiles" / urlparse(url).path.split('/')[-1]
    if not os.path.exists(local_path):
        http_stream = requests.get(url, stream=True)
        with open(local_path, 'wb') as file_stream:
            shutil.copyfileobj(http_stream.raw, file_stream)

    with open(local_path, 'rb') as file_stream:
        content = file_stream.read()

    return local_path, content


class TestNonRegressionPerfs(unittest.TestCase):

    @classmethod
    def cleanup(cls):
        os.chdir(here)
        print("Cleaning old compose")
        subprocess.run(["docker", "compose", "down", "-v", "--remove-orphans"], check=True)


    # @classmethod
    # def setUpClass(cls):
    #     os.chdir(here)
    #     subprocesss_env = os.environ.copy()
    #     subprocesss_env["ORTHANC_IMAGE_UNDER_TESTS"] = Helpers.orthanc_under_tests_docker_image

    #     # print("Pullling containers")
    #     # subprocess.run(["docker", "compose", "pull"], env=subprocesss_env, check=True)

    #     print("Launching containers")
    #     subprocess.run(["docker", "compose", "up", "-d"], env=subprocesss_env, check=True)
        
    #     o_ref = OrthancApiClient(test_configs["ref"]["orthanc-url"])
    #     o_new = OrthancApiClient(test_configs["new"]["orthanc-url"])

    #     o_ref.wait_started()
    #     o_new.wait_started()


    @classmethod
    def tearDownClass(cls):
        cls.cleanup()


    def measure(self, test_name: str, perform_test: Callable[[OrthancApiClient], None], test_configs, test_results, reapeat_count: int = 1, tolerance_pct = 0.25) -> None:

        test_results[test_name] = {}

        for (test_config_name, test_config) in test_configs.items():
            o = OrthancApiClient(orthanc_root_url=test_config["orthanc-url"])

            start_time = time.perf_counter()
            for i in range(0, reapeat_count):
                perform_test(o)

            end_time = time.perf_counter()
            test_results[test_name][test_config_name] = (end_time - start_time) * 1000

        ref_time = test_results[test_name]["ref"]
        new_time = test_results[test_name]["new"]

        delta_perf = new_time / ref_time - 1
        
        if (delta_perf) > tolerance_pct:
            delta_text = f"+ {(delta_perf*100):>8.1f} % (FAILED)"
            failed = True
        elif (delta_perf) > 0:
            delta_text = f"+ {(delta_perf*100):>8.1f} %"
            failed = False
        else:
            delta_text = f"- {abs((delta_perf*100)):>8.1f} %"
            failed = False

        print(f"{test_name:<50} | {ref_time:>20.3f} | {new_time:>20.3f} | {delta_text:>20}")
        test_results[test_name]["success"] = not failed


    def test_non_regression_s3(self):
        print("Launching tests (s3)")

        test_configs = {
            "ref": {
                "orthanc-url": "http://localhost:8242"
            },
            "new": {
                "orthanc-url": "http://localhost:8243"
            }
        }
        test_results = {}
        self.compare(config_name='s3'
                     test_configs=test_configs,
                     test_results=test_results)


    def test_non_regression_classic(self):
        print("Launching tests (classic)")

        test_configs = {
            "ref": {
                "orthanc-url": "http://localhost:8142"
            },
            "new": {
                "orthanc-url": "http://localhost:8143"
            }
        }
        test_results = {}
        self.compare(config_name='file-system'
                     test_configs=test_configs,
                     test_results=test_results)


    def compare(self, config_name, test_configs, test_results):

        os.chdir(here)
        subprocesss_env = os.environ.copy()
        subprocesss_env["ORTHANC_IMAGE_UNDER_TESTS"] = Helpers.orthanc_under_tests_docker_image

        # print("Pullling containers")
        # subprocess.run(["docker", "compose", "pull"], env=subprocesss_env, check=True)

        print("Launching containers")
        subprocess.run(["docker", "compose", "up", "-d"], env=subprocesss_env, check=True)
        
        o_ref = OrthancApiClient(test_configs["ref"]["orthanc-url"])
        o_new = OrthancApiClient(test_configs["new"]["orthanc-url"])

        o_ref.wait_started()
        o_new.wait_started()

        print(f"---------- {config_name} -----------")
        print(f"{'TEST NAME':<50} | {'REF ORTHANC [ms]':>20} | {'NEW ORTHANC [ms]':>20} | {'DELTA [PCT]':>20}")
        print(f"{'-'*119}")

        self.measure(test_name="populate 3000 instances with 5 workers",
                     perform_test=lambda o: OrthancTestDbPopulator(o, studies_count=5, series_count=3, instances_count=120, random_seed=65, worker_threads_count=5).execute(),
                     reapeat_count=1,
                     test_configs=test_configs,
                     test_results=test_results)

        self.measure(test_name="studies statistics 5x5",
                     perform_test=lambda o: [o.studies.get_json_statistics(i) for i in o.studies.get_all_ids()],
                     reapeat_count=5,
                     test_configs=test_configs,
                     test_results=test_results)
        
        reg_of_path, reg_of_content = download_test_file("https://public-files.orthanc.team/test-files/429_MB_REG_OF.dcm")
        reg_ow_path, reg_ow_content = download_test_file("https://public-files.orthanc.team/test-files/429_MB_REG_OW.dcm")

        self.measure(test_name="upload large Reg file with OW VectorGridData",
                     perform_test=lambda o: o.upload(reg_ow_content),
                     reapeat_count=1,
                     test_configs=test_configs,
                     test_results=test_results)
        
        self.measure(test_name="upload large Reg file with OF VectorGridData",
                     perform_test=lambda o: o.upload(reg_of_content),
                     reapeat_count=1,
                     test_configs=test_configs,
                     test_results=test_results)

        self.measure(test_name="upload same file 50x",
                     perform_test=lambda o: o.upload_file(here / "../../Database/Knee/T1/IM-0001-0001.dcm"),
                     reapeat_count=50,
                     test_configs=test_configs,
                     test_results=test_results)

        self.measure(test_name="upload same file SEG 50x",
                     perform_test=lambda o: o.upload_file(here / "../../Database/DicomSeg.dcm"),
                     reapeat_count=50,
                     test_configs=test_configs,
                     test_results=test_results)

        print("Stopping containers")
        subprocess.run(["docker", "compose", "down"], check=True)
        time.sleep(2)

        regressionsCount = 0
        for (test_name, test_result) in test_results.items():
            if not test_result["success"]:
                regressionsCount += 1

        self.assertEqual(0, regressionsCount)  # check the regressions in the report above