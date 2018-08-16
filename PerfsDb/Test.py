import time
import statistics
from orthancRestApi import OrthancClient

from TestResult import TestResult

class Test:

    def __init__(self, name: str):
        self.name = name
        self._orthanc = None
        self.repeatCount = 10
        
    def setOrthancClient(self, orthanc: OrthancClient):
        self._orthanc = orthanc

    def setRepeatCount(self, repeatCount: int):
        self.repeatCount = repeatCount

    def prepare(self):
        """
        Code to execute before the execution of a test; i.e: upload a file (not including in timings)
        """
        pass

    def test(self):
        """
        Code whose execution time will be measured
        """
        pass

    def cleanup(self):
        """
        Code to execute after the execution of a test; i.e: remove an instance (not including in timings)
        """
        pass

    def run(self) -> TestResult:
        result = TestResult(self.name)

        for i in range(0, self.repeatCount):
            self.prepare()
            startTime = time.time()
            self.test()
            endTime = time.time()
            self.cleanup()

            result.add((endTime - startTime) * 1000)

        result.compute()
        return result

    def __str__(self):
        return "{name:<40}: {avg:>8.2f} ms {min:>8.2f} ms {max:>8.2f} ms".format(
            name=self.name,
            avg = self.averageTimeInMs,
            min=self.minTimeInMs,
            max=self.maxTimeInMs
        )