import unittest
from orthanc_api_client import OrthancApiClient
import subprocess
import json
import os
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
    orthanc_under_tests_http_port: int = 8052
    orthanc_under_tests_dicom_port: int = 4252
    orthanc_under_tests_exe: str = None
    orthanc_previous_version_exe: str = None
    orthanc_under_tests_docker_image: str = None
    skip_preparation: bool = False
    break_after_preparation: bool = False
    break_before_preparation: bool = False
    plugins: typing.List[str] = []

    @classmethod
    def get_orthanc_url(cls):
        return f"http://{cls.orthanc_under_tests_hostname}:{cls.orthanc_under_tests_http_port}"

    @classmethod
    def get_orthanc_ip(cls):
        return cls.orthanc_under_tests_hostname

    @classmethod
    def get_orthanc_dicom_port(cls):
        return cls.orthanc_under_tests_dicom_port

    @classmethod
    def is_docker(cls):
        return cls.orthanc_under_tests_exe is None and cls.orthanc_under_tests_docker_image is not None

    @classmethod
    def is_exe(cls):
        return cls.orthanc_under_tests_exe is not None and cls.orthanc_under_tests_docker_image is None

    @classmethod
    def find_executable(cls, name):
        p = os.path.join('/usr/local/bin', name)
        if os.path.isfile(p):
            return p

        p = os.path.join('/usr/local/sbin', name)
        if os.path.isfile(p):
            return p

        return name


class OrthancTestCase(unittest.TestCase):

    o: OrthancApiClient = None  # the orthanc under tests api client
    _orthanc_process = None
    _orthanc_container_name = None
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
        if plugins and len(plugins) > 0:
            config["Plugins"] = plugins

        if Helpers.is_exe() and not "StorageDirectory" in config:
            config["StorageDirectory"] = cls.get_storage_path(storage_name=storage_name)

        if not "Name" in config:
            config["Name"] = config_name

        if not "HttpPort" in config:
            config["HttpPort"] = Helpers.orthanc_under_tests_http_port

        if not "DicomPort" in config:
            config["DicomPort"] = Helpers.orthanc_under_tests_dicom_port

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
        if Helpers.is_exe():
            storage_path = cls.get_storage_path(storage_name=storage_name)
            shutil.rmtree(storage_path, ignore_errors=True)
        elif Helpers.is_docker():
            subprocess.run(["docker", "volume", "rm", "-f", storage_name])

    @classmethod
    def launch_orthanc_to_prepare_db(cls, config_name: str = None, config: object = None, config_path: str = None, storage_name: str = None, plugins = []):
        if config_name and storage_name and config:
            # generate the configuration file
            config_path = cls.generate_configuration(
                config_name=config_name,
                storage_name=storage_name,
                config=config,
                plugins=plugins
                )
        elif not config_path or not storage_name or not config_name:
            raise RuntimeError("Invalid configuration")

        # run orthanc
        if Helpers.orthanc_previous_version_exe:
            cls.launch_orthanc_exe(
                exe_path=Helpers.orthanc_previous_version_exe,
                config_path=config_path
            )
        elif Helpers.orthanc_previous_version_docker_image:
            cls.launch_orthanc_docker(
                docker_image=Helpers.orthanc_previous_version_docker_image,
                storage_name=storage_name,
                config_name=config_name,
                config_path=config_path
            )
        else:
            raise RuntimeError("Invalid configuration, can not launch Orthanc")

    @classmethod
    def launch_orthanc_under_tests(cls, config_name: str = None, config: object = None, config_path: str = None, storage_name: str = None, plugins = []):
        if config_name and storage_name and config:
            # generate the configuration file
            config_path = cls.generate_configuration(
                config_name=config_name,
                storage_name=storage_name,
                config=config,
                plugins=plugins
                )
        elif not config_path or not storage_name or not config_name:
            raise RuntimeError("Invalid configuration")

        # run orthanc
        if Helpers.orthanc_under_tests_exe:
            cls.launch_orthanc_exe(
                exe_path=Helpers.orthanc_under_tests_exe,
                config_path=config_path
            )
        elif Helpers.orthanc_under_tests_docker_image:
            cls.launch_orthanc_docker(
                docker_image=Helpers.orthanc_under_tests_docker_image,
                storage_name=storage_name,
                config_name=config_name,
                config_path=config_path
            )
        else:
            raise RuntimeError("Invalid configuration, can not launch Orthanc")

    @classmethod
    def launch_orthanc_exe(cls, exe_path: str, config_path: str):
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
    def launch_orthanc_docker(cls, docker_image: str, storage_name: str, config_path: str, config_name: str):
            storage_path = cls.get_storage_path(storage_name=storage_name)

            cmd = [
                    "docker", "run", "--rm", 
                    "-e", "VERBOSE_ENABLED=true",
                    "-e", "VERBOSE_STARTUP=true", 
                    "-v", f"{config_path}:/etc/orthanc/orthanc.json",
                    "-v", f"{storage_path}:/var/lib/orthanc/db/",
                    "--name", config_name,
                    "-p", f"{Helpers.orthanc_under_tests_http_port}:{Helpers.orthanc_under_tests_http_port}",
                    "-p", f"{Helpers.orthanc_under_tests_dicom_port}:{Helpers.orthanc_under_tests_dicom_port}",
                    docker_image
                ]
            cls._orthanc_container_name = config_name
            print("docker cmd line: " + " ".join(cmd))

            cls._orthanc_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )

            cls.o.wait_started(10)
            if not cls.o.is_alive():
                output = cls.get_orthanc_process_output()
                print("Orthanc output\n" + output)

                raise RuntimeError(f"Orthanc failed to start Orthanc through Docker '{docker_image}', conf = '{config_path}'.  Check output above")


    @classmethod
    def kill_orthanc(cls):
        if Helpers.is_exe():
            cls._orthanc_process.kill()
        else:
            subprocess.run(["docker", "stop", cls._orthanc_container_name])
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
