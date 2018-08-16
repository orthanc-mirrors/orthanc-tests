import typing
from orthancRestApi import OrthancClient

from DbSize import DbSize

class DbPopulator:

    def __init__(self, orthanc: OrthancClient, dbSize: DbSize):
        self._orthanc = orthanc
        self._dbSize = dbSize
        self._sourceInstanceId = None

    def populate(self):
        self._sourceInstanceId = self._orthanc.uploadDicomFile("../Database/DummyCT.dcm")

        if self._dbSize == DbSize.Small:
            patientCount = 3
            smallStudiesPerPatient = 2
            largeStudiesPerPatient = 1
        else:
            patientCount = 100
            smallStudiesPerPatient = 4
            largeStudiesPerPatient = 8

        # data that are the same in small and large DBs (and that can be used in tests for comparing the same things !!)

        # used in TestFindStudyByPatientId5Results
        self.createStudy(studyIndex=99994, patientIndex=99998, seriesCount=1, instancesPerSeries=1)
        self.createStudy(studyIndex=99995, patientIndex=99998, seriesCount=1, instancesPerSeries=1)
        self.createStudy(studyIndex=99996, patientIndex=99998, seriesCount=1, instancesPerSeries=1)
        self.createStudy(studyIndex=99997, patientIndex=99998, seriesCount=1, instancesPerSeries=1)
        self.createStudy(studyIndex=99998, patientIndex=99998, seriesCount=1, instancesPerSeries=1)

        # used in TestFindStudyByStudyDescription1Result
        # used in TestFindStudyByPatientId1Result
        self.createStudy(studyIndex=99999, patientIndex=99999, seriesCount=1, instancesPerSeries=1)

        # data to make the DB "large" or "small"
        for patientIndex in range(0, patientCount):
            studyIndex=0
            print("Generating data for patient " + str(patientIndex))
            for i in range(0, smallStudiesPerPatient):
                print("Generating small study " + str(i))
                self.createStudy(studyIndex=studyIndex, patientIndex=patientIndex, seriesCount=2, instancesPerSeries=2)
                studyIndex+=1
            for i in range(0, largeStudiesPerPatient):
                print("Generating large study " + str(i))
                self.createStudy(studyIndex=studyIndex, patientIndex=patientIndex, seriesCount=4, instancesPerSeries=500)
                studyIndex+=1



        print("Generation completed")    

    def createStudy(self, studyIndex: int, patientIndex: int, seriesCount: int, instancesPerSeries: int):
        for seriesIndex in range(0, seriesCount):
            for instanceIndex in range(0, instancesPerSeries):
                dicomFile = self.createDicomFile(patientIndex=patientIndex, studyIndex=studyIndex, seriesIndex=seriesIndex, instanceIndex=instanceIndex)
                self._orthanc.uploadDicom(dicomFile)

    def createDicomFile(self, patientIndex: int, studyIndex: int, seriesIndex: int, instanceIndex: int) -> object:
        return self._orthanc.instances.modify(
            instanceId=self._sourceInstanceId,
            replaceTags={
                "PatientName": "Patient-" + str(patientIndex),
                "PatientID": str(patientIndex),
                "StudyDescription": str(patientIndex) + "-" + str(studyIndex),
                "SeriesDescription": str(patientIndex) + "-" + str(studyIndex) + "-" + str(seriesIndex),
                "SOPInstanceUID": str(patientIndex) + "." + str(studyIndex) + "." + str(seriesIndex) + "." + str(instanceIndex),
                "StudyInstanceUID": str(patientIndex) + "." + str(studyIndex),
                "SeriesInstanceUID": str(patientIndex) + "." + str(studyIndex) + "." + str(seriesIndex),
                "SeriesNumber": str(seriesIndex),
                "InstanceNumber": str(instanceIndex)
            },
            deleteOriginal=False
        )