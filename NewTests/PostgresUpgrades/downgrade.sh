#!/bin/bash

pushd /scripts

# TODO: change attach-custom-data by the plugin version number or "default" !
apt-get update && apt-get install -y wget && wget https://orthanc.uclouvain.be/hg/orthanc-databases/raw-file/attach-custom-data/PostgreSQL/Plugins/SQL/Downgrades/Rev3ToRev2.sql
psql -U postgres -f Rev3ToRev2.sql

# if you want to test a downgrade procedure, you may use this code ...
# psql -U postgres -f downgrade.sql
popd