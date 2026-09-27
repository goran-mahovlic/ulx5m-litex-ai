#!/bin/bash
# TASK-5066 lab phase 5: E7 eye scan with the DONE-polarity fix, on the best 2.5 G pair and on PROFILE 2 at 5 G;
# JTAG RX word samples (fabric-independent) at 5 G PROFILE 2, 200 per board.
cd /home/pi/ulx5m-serdes/t5066; export LOG=$PWD/log; T=/home/pi/ulx5m-serdes/tools
own=$(cat /home/pi/gs.owner 2>/dev/null); [ -n "$own" ] && [ "${own%% *}" != TASK-5066 ] && { echo "leased: $own"; exit 3; }
echo "TASK-5066 $(date +%s) SerDes 5G tuning (jelena) phase 5 eye scan" > /home/pi/gs.owner
for cfg in "2g5 gs_sd_2g5p1_txneg_s7.bit m2_e1_2g5p1_txneg_s2.bit" "5g gs_p2_5g_txneg_s7.bit m2_p2_5g_txneg_s1.bit"; do
  set -- $cfg; echo "== E7 $1 $(date +%T)"
  fpga-jtag m2 $3 -r 2>&1 | tail -1; fpga-jtag gs $2 -r 2>&1 | tail -1; sleep 5
  for b in m2 gs; do
    fpga-jtag $b run python3 $T/eyescan.py scan --ph=-32:31:4 --th=-15:15:3 --window 512 --label "E7 $1 $b" --out $LOG/e7_eye_$1_$b.json 2>&1 | grep -vE "^INFO|^$"
  done
  for b in m2 gs; do fpga-jtag $b run python3 $T/ber_jtag_check.py --samples 200 2>&1 | tail -1; done
done
rm -f /home/pi/gs.owner; echo "LAB5 DONE $(date +%T)"
