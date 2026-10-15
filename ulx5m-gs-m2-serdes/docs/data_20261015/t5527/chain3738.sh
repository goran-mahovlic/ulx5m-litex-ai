#!/bin/bash
cd /home/pi/ulx5m-serdes/t5527
while kill -0 24055 2>/dev/null; do sleep 5; done
while pgrep -f "^bash lab36.sh" >/dev/null; do sleep 5; done
bash lab37.sh > lab37.out 2>&1
bash lab38.sh > lab38.out 2>&1
