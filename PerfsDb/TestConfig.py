import typing
import subprocess
import os
from orthancRestApi import OrthancClient

from DbSize import DbSize
from DbType import DbType
from ConfigFileBuilder import ConfigFileBuilder
from DbServer import DbServer
from DbPopulator import DbPopulator
from Tests import *
from TestResult import TestResult

class TestConfig:

    def __init__(self,
        label: str,
        dbSize: DbSize,
        dbType: DbType=None,
        dbServer: DbServer=None
        ):

        self._dbSize = dbSize
        self._dbServer = dbServer
        self._label = label
        self._port = None
        self._name = "unknown"
        self._orthancProcess = None
        self._repeatCount = 10

        if dbServer is not None:
            self._dbType = dbServer.dbType
            self._dbServer.setLabel(self._label)
            self._port = dbServer.port
        else:
            self._dbType = dbType
        
    def setName(self, name: str):
        self._name = name
        
    def setRepeatCount(self, repeatCount: int):
        self._repeatCount = repeatCount

    def launchDbServer(self):
        if self._dbServer is not None:
            self._dbServer.launch()

    def launchOrthanc(self, orthancPath):
        orthanc = OrthancClient("http://127.0.0.1:8042")
        
        print("Checking if Orthanc is already running")
        if orthanc.isAlive():
            print("Orthanc is already running")
            return
        
        print("Launching Orthanc")
        self._orthancProcess = subprocess.Popen([
            os.path.join(orthancPath, "Orthanc"), 
            os.path.join("ConfigFiles", self._name + ".json"), 
        ])
       
        print("Waiting for Orthanc to start")
        orthanc.waitStarted(timeout=30)
        print("Orthanc has started")

    def stopOrthanc(self):
        if self._orthancProcess is not None:
            self._orthancProcess.terminate()
            self._orthancProcess.wait()

    def initializeDb(self):
        dbPopulator = DbPopulator(orthanc=OrthancClient("http://127.0.0.1:8042"), dbSize=self._dbSize)
        dbPopulator.populate()

    def runTests(self) -> typing.List[TestResult]:
        allTests = [
            TestFindStudyByStudyDescription1Result(),
            TestFindStudyByPatientId1Result(),
            TestFindStudyByStudyDescription0Results(),
            TestFindStudyByPatientId0Results(),
            TestFindStudyByPatientId5Results(),
            TestUploadFile()
        ]

        results = []
        for test in allTests:
            test.setOrthancClient(OrthancClient("http://127.0.0.1:8042"))
            test.setRepeatCount(self._repeatCount)
            result = test.run()
            print(str(result))

            results.append(result)
        return results

    def clearDb(self):
        if self._dbServer is not None:
            self._dbServer.clear()

    def generateOrthancConfigurationFile(self, pluginsPath: str):
        
        ConfigFileBuilder.generate(
            outputPath="ConfigFiles/{name}.json".format(name=self._name), 
            plugins=[pluginsPath],
            storagePath="Storages/{name}".format(name=self._name),
            dbType=self._dbType,
            dbSize=self._dbSize,
            port=self._port
            )
