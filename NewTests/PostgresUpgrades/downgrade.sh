#!/bin/bash

pushd /scripts

apt-get update && apt-get install -y wget mercurial
hg clone https://orthanc.uclouvain.be/hg/orthanc-databases
psql -U postgres -f /scripts/orthanc-databases/PostgreSQL/Plugins/SQL/Downgrades/Rev2ToRev1.sql

# if you want to test a downgrade procedure, you may use this code ...
# psql -U postgres -f downgrade.sql
popd