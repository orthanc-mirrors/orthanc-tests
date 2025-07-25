#!/bin/bash

pushd /scripts

apt-get update && apt-get install -y wget mercurial
hg clone https://orthanc.uclouvain.be/hg/orthanc-databases
pushd orthanc-databases

hg update -r default

psql -U postgres -f /scripts/orthanc-databases/PostgreSQL/Plugins/SQL/Downgrades/Rev5ToRev4.sql

# if you want to test a downgrade procedure, you may use this code ...
# psql -U postgres -f downgrade.sql
popd
popd
