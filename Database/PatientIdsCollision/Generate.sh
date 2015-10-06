#!/bin/bash

rm *.dcm

for i in `seq 1 3` 
do
  dump2dcm +Ug --write-xfer-little Image$i.dump Image$i.dcm
done
