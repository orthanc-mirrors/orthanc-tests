#!/bin/bash

sudo docker run --rm -t -i -v `pwd`:/tmp/tests:ro -p 5000:8042 -p 5001:4242 --entrypoint python jodogne/orthanc-tests /tmp/tests/Tests/Run.py --force $*
