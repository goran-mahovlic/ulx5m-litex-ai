#!/bin/bash
while kill -0 5256 2>/dev/null; do sleep 5; done
cd /home/pi/ulx5m-serdes/t5522 && SECS=300 EVERY=60 SECS5=300 ./lab.sh 3 > long.out 2>&1
