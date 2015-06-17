#!/bin/bash

# Without Docker:
# python ./Tests/Run.py --force

sudo docker run --rm -t -i -v `pwd`:/tmp/tests:ro -p 5000:5000 -p 5001:5001 --entrypoint python jodogne/orthanc-tests /tmp/tests/Tests/Run.py --docker $*
