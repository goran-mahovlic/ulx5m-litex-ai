#!/bin/bash
# TASK-5487 step 4: 5 G P2 / P3, baseline vs m2 TX_SEL_POST=15 (2.5 G winner), 3 loads interleaved, 60 s ber_mon sparse, ber_jtag_check 1000.
H=/home/pi/ulx5m-serdes/t5483; export SECS=60
for r in 1 2 3; do
  bash $H/lab18.sh p2r$r gs_5g.bit m2_5g.bit 1000 "base|" "m2p15|m2:TX_SEL_POST=15"
  bash $H/lab18.sh p3r$r gs_5g_p3.bit m2_5g_p3.bit 1000 "base|" "m2p15|m2:TX_SEL_POST=15"
done
echo "LAB18_5G ALL DONE $(date +%T)"
