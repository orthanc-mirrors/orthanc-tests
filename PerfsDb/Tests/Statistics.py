import json

from Test import Test

class TestStatistics(Test):

    def __init__(self, name:str = "Statistics"):
        super().__init__(name)
        self._response = None

    def test(self):
        self._statistics = self._orthanc.getJson(relativeUrl="statistics")

    def afterAll(self):
        print("Statistics:" + json.dumps(self._statistics))