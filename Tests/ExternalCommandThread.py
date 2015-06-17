#!/usr/bin/python

# Orthanc - A Lightweight, RESTful DICOM Store
# Copyright (C) 2012-2015 Sebastien Jodogne, Medical Physics
# Department, University Hospital of Liege, Belgium
#
# This program is free software: you can redistribute it and/or
# modify it under the terms of the GNU General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.


import os
import signal
import subprocess
import threading

class ExternalCommandThread:
    @staticmethod
    def ExternalCommandFunction(arg, stop_event, command, env):
        external = subprocess.Popen(command, env = env)

        while (not stop_event.is_set()):
            error = external.poll()
            if error != None:
                # http://stackoverflow.com/a/1489838/881731
                os._exit(-1)
            stop_event.wait(0.1)

        print 'Stopping the external command'
        external.terminate()

    def __init__(self, command, env = None):
        self.thread_stop = threading.Event()
        self.thread = threading.Thread(target = self.ExternalCommandFunction, 
                                       args = (10, self.thread_stop, command, env))
        self.daemon = True
        self.thread.start()

    def stop(self):
        self.thread_stop.set()
        self.thread.join()
