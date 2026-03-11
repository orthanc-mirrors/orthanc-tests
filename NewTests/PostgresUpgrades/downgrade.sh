#!/bin/bash

pushd /scripts

apt-get update && apt-get install -y wget

# hg clone is often rejected from Azure runners, let's try a download from http
wget https://orthanc.uclouvain.be/downloads/sources/orthanc-postgresql/OrthancPostgreSQL-10.0.tar.gz --output-document /tmp/pg.tar.gz
# ex for an intermediate release (or if download from uclouvain is rejected)
# wget https://public-files.orthanc.team/tmp-builds/hg-repos/orthanc-databases-81d837d7d20d.tar.gz --output-document /tmp/pg.tar.gz

tar xvf /tmp/pg.tar.gz --strip-components=1
pushd /scripts/orthanc-databases/

psql -U postgres -f /scripts/orthanc-databases/PostgreSQL/Plugins/SQL/Downgrades/Rev10ToRev5.sql

# if you want to test a downgrade procedure, you may use this code ...
# psql -U postgres -f downgrade.sql
popd
popd
