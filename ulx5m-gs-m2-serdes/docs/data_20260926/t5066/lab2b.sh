#!/bin/bash
# TASK-5066 lab phase 2b (5 Gb/s): E2 AFE sweep, GAIN {0..3} x PEAK {24,16,12,8,4,0}, 1 load x 60 s per point
cd /home/pi/ulx5m-serdes/t5066; export LOG=$PWD/log ME=TASK-5066 KEEP_LEASE=1; mkdir -p $LOG
T=/home/pi/ulx5m-serdes/tools
own=$(cat /home/pi/gs.owner 2>/dev/null); [ -n "$own" ] && [ "${own%% *}" != TASK-5066 ] && { echo "leased: $own"; exit 3; }
echo "TASK-5066 $(date +%s) SerDes 5G tuning (jelena) E2" > /home/pi/gs.owner
echo "== E2 5G AFE $(date +%T)"
PTS=()
for g in 0 1 2 3; do for p in 24 16 12 8 4 0; do
  PTS+=("e2_g${g}_p${p}|gs:RX_AFE_GAIN=$g,RX_AFE_PEAK=$p|m2:RX_AFE_GAIN=$g,RX_AFE_PEAK=$p")
done; done
$T/lab/abrun.sh gs_e1_5gp1_txneg_s7.bit m2_e1_5gp1_txneg_s1.bit 60 1 "${PTS[@]}"
python3 $T/lab/ab_table.py $LOG/e2_*_r*.json
rm -f /home/pi/gs.owner; echo "LAB2B DONE $(date +%T)"
