#!/bin/bash
# TASK-5073 lab phase 7: PROFILE 3 (= point (d): PROFILE 1 + CDR CKP 0x1E TRANS_TH 16) in the bitstream, no JTAG writes:
# 300 s (both directions run at the same time) + 3 loads x 60 s, as §9.7 did for PROFILE 2.
cd /home/pi/ulx5m-serdes/t5066; export ME=TASK-5073 KEEP_LEASE=1; export LOG=$PWD/log5073; mkdir -p $LOG
T=/home/pi/ulx5m-serdes/tools
own=$(cat /home/pi/gs.owner 2>/dev/null)
if [ -n "$own" ] && [ "${own%% *}" != TASK-5073 ]; then
  age=$(( $(date +%s) - $(echo "$own" | awk '{print $2}') )); [ "$age" -lt 7200 ] && { echo "leased: $own"; exit 3; }
fi
echo "TASK-5073 $(date +%s) SerDes 5G PROFILE 3 (jelena)" > /home/pi/gs.owner
$T/lab/abrun.sh gs_p3_5g_txneg_s7.bit m2_p3_5g_txneg_s1.bit 300 1 "t73f_p3_300s||"
$T/lab/abrun.sh gs_p3_5g_txneg_s7.bit m2_p3_5g_txneg_s1.bit 60 3 "t73f_p3_60s||"
for b in m2 gs; do fpga-jtag $b run python3 $T/ber_jtag_check.py --samples 200 2>&1 | tail -1; done
python3 $T/lab/ab_table.py --runs --rank $LOG/t73*_r*.json
rm -f /home/pi/gs.owner; echo "LAB7 DONE $(date +%T)"
