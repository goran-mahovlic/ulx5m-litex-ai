#!/bin/bash
# TASK-5089 lab13 (28.09. ~16:25): shared refclk RESTORED (M2: X2 removed, C136/C137 100 nF back), GS R106/R105 5R1, M2 R105/R106 4R7
# (Goran), GS 1 uF on C127/C128/C42 unchanged. = lab9.sh protocol: 2.5 G best pair 3 x 300 s; 5 G P2 + P3 3 x 60 s interleaved; jtag_check 200.
cd /home/pi/ulx5m-serdes/t5066; L=/home/pi/ulx5m-serdes/t5089/log13; T=/home/pi/ulx5m-serdes/tools; mkdir -p $L
echo "TASK-5089 $(date +%s) lab13 shared clk + 5R1/4R7 (regoc)" > /home/pi/gs.owner
sha256sum gs_sd_2g5p1_txneg_s7.bit m2_e1_2g5p1_txneg_s2.bit gs_p2_5g_txneg_s7.bit m2_p2_5g_txneg_s1.bit gs_p3_5g_txneg_s7.bit m2_p3_5g_txneg_s1.bit
export ME=TASK-5089 KEEP_LEASE=1
echo "== 2.5G $(date +%T)"
LOG=$L $T/lab/abrun.sh gs_sd_2g5p1_txneg_s7.bit m2_e1_2g5p1_txneg_s2.bit 300 3 "t13_2g5||"
for k in 1 2 3; do
  echo "== 5G round $k $(date +%T)"
  LOG=$L/tmp $T/lab/abrun.sh gs_p2_5g_txneg_s7.bit m2_p2_5g_txneg_s1.bit 60 1 "t13_p2_60s||"
  LOG=$L/tmp $T/lab/abrun.sh gs_p3_5g_txneg_s7.bit m2_p3_5g_txneg_s1.bit 60 1 "t13_p3_60s||"
  for f in $L/tmp/*_r1*; do b=$(basename $f); mv $f $L/${b/_r1/_r$k}; done
done
for b in m2 gs; do echo "jtag_check P3 $b: $(fpga-jtag $b run python3 $T/ber_jtag_check.py --samples 200 2>&1 | tail -1)"; done
python3 $T/lab/ab_table.py --runs --rank $L/t13_*_r*.json
python3 $T/lab/health_table.py $L/t13_*_r*.health_*.json
rm -f /home/pi/gs.owner; echo "LAB13 DONE $(date +%T)"
