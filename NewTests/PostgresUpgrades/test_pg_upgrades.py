import subprocess
import time
import unittest
from orthanc_api_client import OrthancApiClient
from helpers import Helpers

import pathlib
import os
here = pathlib.Path(__file__).parent.resolve()


def get_container_health(container_name):
    try:
        # Run the docker inspect command
        result = subprocess.run(
            ["docker", "inspect", "--format", "{{.State.Health.Status}}", container_name],
            capture_output=True,
            text=True,
            check=True,
        )
        
        # Extract the health status from the command output
        return result.stdout.strip()

    except subprocess.CalledProcessError as e:
        print(f"Error checking container health: {e}")
        return None

def wait_container_healthy(container_name):
    retry = 0

    while (get_container_health(container_name) != "healthy" and retry < 200):
        print(f"Waiting for {container_name} to be healty")
        time.sleep(1)

class TestPgUpgrades(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        os.chdir(here)
        print("Cleaning old compose")
        subprocess.run(["docker", "compose", "down", "-v", "--remove-orphans"], check=True)

    def test_upgrades_downgrades_with_pg_15(self):

        print("Launching PG-15 server")
        subprocess.run(["docker", "compose", "up", "pg-15", "-d"], check=True)
        wait_container_healthy("pg-15")

        print("Launching old Orthanc (PG v2.0)")
        subprocess.run(["docker", "compose", "up", "orthanc-pg-15-2", "-d"], check=True)

        o = OrthancApiClient("http://localhost:8049")
        o.wait_started()

        instances = o.upload_folder(here / "../../Database/Knee")

        print("Stopping old Orthanc ")
        subprocess.run(["docker", "compose", "stop", "orthanc-pg-15-2"], check=True)
        time.sleep(2)

        print("Launching newest Orthanc")
        subprocess.run(["docker", "compose", "up", "orthanc-pg-15-under-tests", "-d"], check=True)

        o = OrthancApiClient("http://localhost:8050")
        o.wait_started()

        # make sure we can 'play' with Orthanc
        o.instances.get_tags(orthanc_id=instances[0])
        o.instances.delete_all()
        instances = o.upload_folder(here / "../../Database/Knee")

        print("Stopping new Orthanc ")
        subprocess.run(["docker", "compose", "stop", "orthanc-pg-15-under-tests"], check=True)
        time.sleep(2)

        print("TODO Downgrading Orthanc DB and restart an Orthanc 23.12.1")
        # ...

    def test_latest_orthanc_with_pg_9(self):
        print("Launching PG-9 server")
        subprocess.run(["docker", "compose", "up", "pg-9", "-d"], check=True)
        wait_container_healthy("pg-9")

        print("Launching newest Orthanc")
        subprocess.run(
            ["docker", "compose", "up", "orthanc-pg-9-under-tests", "-d"], 
            env= {
                "ORTHANC_IMAGE_UNDER_TESTS": Helpers.orthanc_under_tests_docker_image
            },
            check=True)

        o = OrthancApiClient("http://localhost:8051")
        o.wait_started()
        instances = o.upload_folder(here / "../../Database/Knee")
        o.instances.delete(orthanc_ids=instances)

        subprocess.run(["docker", "compose", "down", "-v", "--remove-orphans"], check=True)
