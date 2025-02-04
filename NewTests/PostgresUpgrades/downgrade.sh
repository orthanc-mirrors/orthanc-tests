#!/bin/bash

pushd /scripts

apt-get update && apt-get install -y wget mercurial
hg clone https://orthanc.uclouvain.be/hg/orthanc-databases
# TODO: change attach-custom-data by the plugin version number or "default" !
pushd orthanc-databases
hg update -r attach-custom-data

psql -U postgres -f /scripts/orthanc-databases/PostgreSQL/Plugins/SQL/Downgrades/Rev4ToRev3.sql

# if you want to test a downgrade procedure, you may use this code ...
# psql -U postgres -f downgrade.sql
popd
