#!/bin/bash

pushd /scripts

# TODO: change pg-transactions by the plugin version number !
apt-get update && apt-get install -y wget && wget https://orthanc.uclouvain.be/hg/orthanc-databases/raw-file/pg-transactions/PostgreSQL/Plugins/SQL/Downgrades/V6.2ToV6.1.sql
psql -U postgres -f V6.2ToV6.1.sql

# if you want to test a downgrade procedure, you may use this code ...
# psql -U postgres -f downgrade.sql
popd