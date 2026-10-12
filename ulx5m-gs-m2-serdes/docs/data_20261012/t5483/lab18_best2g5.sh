#!/bin/bash
# TASK-5487 step 3: 2.5 G best point vs baseline, 3 loads each, interleaved; 240 s ber_mon sparse windows, ber_jtag_check 1000.
H=/home/pi/ulx5m-serdes/t5483; export SECS=240
for r in 1 2 3; do
  bash $H/lab18.sh b2g5r$r gs_2g5.bit m2_2g5.bit 1000 "base|" "m2p15|m2:TX_SEL_POST=15" "m2p15th16|m2:TX_SEL_POST=15,RX_CDR_TRANS_TH=16"
done
echo "LAB18_BEST2G5 ALL DONE $(date +%T)"
