from Test import Test

class TestUploadFile(Test):

    def __init__(self, name:str = "UploadFile", filePath:str = "../Database/DummyCT.dcm"):
        super().__init__(name)
        self._instanceId = None
        self._filePath = filePath
        self._dicomFileContent = None

    def prepare(self):
        # get the instance Id and dicom file content
        if self._instanceId is None:
            self._instanceId = self._orthanc.uploadDicomFile(self._filePath)
            self._dicomFileContent = self._orthanc.instances.getDicom(self._instanceId)

        # make sure the file is not in Orthanc before the upload
        self._orthanc.instances.delete(self._instanceId)

    def test(self):
        self._orthanc.uploadDicom(self._dicomFileContent)