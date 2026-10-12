#!/bin/bash
# TASK-5487: after lab18_best2g5 finishes -> lab18_5g, then Manda H2 eye test on m2 (one 2.5 G load).
H=/home/pi/ulx5m-serdes/t5483
until grep -q "LAB18_BEST2G5 ALL DONE" $H/lab18_best2g5.out; do sleep 20; done
bash $H/lab18_5g.sh > $H/lab18_5g.out 2>&1
{ echo "TASK-5487 $(date +%s) eye H2 (jelena)" > /home/pi/gs.owner
  fpga-jtag m2 /home/pi/fpga/m2_2g5.bit -r 2>&1 | tail -1; fpga-jtag gs /home/pi/fpga/gs_2g5.bit -r 2>&1 | tail -1; sleep 3
  cd /home/pi/ulx5m-serdes/tools; timeout 300 fpga-jtag m2 run python3 $H/eye_h2.py 2>&1
  rm -f /home/pi/gs.owner; echo "EYE_H2 DONE $(date +%T)"; } > $H/eye_h2.out 2>&1
