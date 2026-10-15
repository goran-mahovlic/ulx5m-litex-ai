#!/bin/bash
cd /home/pi/ulx5m-serdes/t5527
while kill -0 29658 2>/dev/null; do sleep 10; done
bash lab39.sh > lab39.out 2>&1
