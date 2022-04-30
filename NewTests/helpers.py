import unittest
from orthanc_api_client import OrthancApiClient
import subprocess
import json
import time
import typing
import shutil
from threading import Thread


import pathlib
here = pathlib.Path(__file__).parent.resolve()


default_base_config = {
    "AuthenticationEnabled": False,
    "RemoteAccessAllowed": True
}

class Helpers:

    orthanc_under_tests_hostname: str = 'localhost'
    orthanc_under_tests_http_port: int = 8042
    orthanc_under_tests_exe: str = None
    orthanc_previous_version_exe: str = None
    orthanc_under_tests_docker_image: str = None
    skip_preparation: bool = False
    break_after_preparation: bool = False
    plugins: typing.List[str] = []

    @classmethod
    def get_orthanc_url(cls):
        return f"http://{cls.orthanc_under_tests_hostname}:{cls.orthanc_under_tests_http_port}"

class OrthancTestCase(unittest.TestCase):

    o: OrthancApiClient = None  # the orthanc under tests api client
    _orthanc_process = None
    _orthanc_is_running = False
    _orthanc_logger_thread = None

    @classmethod
    def setUpClass(cls):

        cls.o = OrthancApiClient(Helpers.get_orthanc_url())
        cls._prepare()

    @classmethod
    def tearDownClass(cls):
        if not Helpers.break_after_preparation:
            cls.kill_orthanc()

    @classmethod
    def prepare(cls):
        pass # to override

    @classmethod
    def _prepare(cls):
        if not Helpers.skip_preparation:
            cls.prepare()

    @classmethod
    def get_storage_path(cls, storage_name: str):
        return str(here / "storages" / f"{storage_name}")

    @classmethod
    def generate_configuration(cls, config_name: str, config: object, storage_name: str, plugins = []):
        
        # add plugins and default storge directory
        config["Plugins"] = plugins

        if not "StorageDirectory" in config:
            config["StorageDirectory"] = cls.get_storage_path(storage_name=storage_name)

        if not "Name" in config:
            config["Name"] = config_name

        if not "HttpPort" in config:
            config["HttpPort"] = Helpers.orthanc_under_tests_http_port

        # copy the values from the base config
        for k, v in default_base_config.items():
            if not k in config:
                config[k] = v

        # save to disk
        path = str(here / "configurations" / f"{config_name}.json")
        with open(path, "w") as f:
            json.dump(config, f, indent=4)

        return path

    @classmethod
    def clear_storage(cls, storage_name: str):
        storage_path = cls.get_storage_path(storage_name=storage_name)
        shutil.rmtree(storage_path)


    @classmethod
    def launch_orthanc_to_prepare_db(cls, config_name: str, config: object, storage_name: str, plugins = []):
        # generate the configuration file
        config_path = cls.generate_configuration(
            config_name=config_name,
            storage_name=storage_name,
            config=config,
            plugins=plugins
            )

        # run orthanc
        if Helpers.orthanc_previous_version_exe:
            cls.launch_orthanc(
                exe_path=Helpers.orthanc_previous_version_exe,
                config_path=config_path
            )
        else:
            raise RuntimeError("No orthanc_previous_version_exe defined, can not launch Orthanc")

    @classmethod
    def launch_orthanc(cls, exe_path: str, config_path: str):
            cls._orthanc_process = subprocess.Popen(
                [exe_path, "--verbose", config_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )

            cls.o.wait_started(10)
            if not cls.o.is_alive():
                output = cls.get_orthanc_process_output()
                print("Orthanc output\n" + output)

                raise RuntimeError(f"Orthanc failed to start '{exe_path}', conf = '{config_path}'.  Check output above")

    @classmethod
    def kill_orthanc(cls):
        cls._orthanc_process.kill()
        output = cls.get_orthanc_process_output()
        print("Orthanc output\n" + output)
        cls._orthanc_process = None

    @classmethod
    def get_orthanc_process_output(cls):
        outputs = cls._orthanc_process.communicate()
        output = ""
        for o in outputs:
            output += o.decode('utf-8')
        return output
