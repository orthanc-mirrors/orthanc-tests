#!/bin/bash
set -e
set -x

pushd /scripts

psql -v ON_ERROR_STOP=1  -U postgres -f downgrade.sql
popd
