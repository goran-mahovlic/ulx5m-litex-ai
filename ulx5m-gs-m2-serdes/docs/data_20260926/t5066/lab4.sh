#!/bin/bash
# TASK-5066 lab phase 4: E8 PROFILE=2 5 G (300 s, both directions, no JTAG writes) + 2 more 60 s loads,
# E7 eye scan (0x06[11] fix) on the best 2.5 G pair, 2.5 G best pair 300 s (gs TX_NEG s7 + m2 s2).
cd /home/pi/ulx5m-serdes/t5066; export LOG=$PWD/log ME=TASK-5066 KEEP_LEASE=1; mkdir -p $LOG
T=/home/pi/ulx5m-serdes/tools
own=$(cat /home/pi/gs.owner 2>/dev/null); [ -n "$own" ] && [ "${own%% *}" != TASK-5066 ] && { echo "leased: $own"; exit 3; }
echo "TASK-5066 $(date +%s) SerDes 5G tuning (jelena) phase 4" > /home/pi/gs.owner
echo "== E8 PROFILE 2 5G $(date +%T)"
$T/lab/abrun.sh gs_p2_5g_txneg_s7.bit m2_p2_5g_txneg_s1.bit 300 1 "e8_p2_300s||"
$T/lab/abrun.sh gs_p2_5g_txneg_s7.bit m2_p2_5g_txneg_s1.bit 60 3 "e8_p2_60s||"
for b in m2 gs; do fpga-jtag $b run python3 $T/ber_jtag_check.py --samples 20 2>&1 | tail -1; done
echo "== 2.5G best pair $(date +%T)"
$T/lab/abrun.sh gs_sd_2g5p1_txneg_s7.bit m2_e1_2g5p1_txneg_s2.bit 300 1 "best_2g5_gs7_m22||"
echo "== E7 eye scan on the running 2.5G link $(date +%T)"
for b in m2 gs; do
  fpga-jtag $b run python3 $T/eyescan.py scan --ph=-32:31:8 --th=-15:15:5 --window 512 --label "E7 2g5 $b" --out $LOG/e7_eye_$b.json 2>&1 | grep -vE "^INFO|^$"
  fpga-jtag $b run python3 $T/eyescan.py get RX_EN_EQA RX_EQA_LOCK_CFG RX_EQA_LOCKED RX_CDR_LOCKED 2>&1 | grep board=
done
python3 - <<'PY'
import json
for b in ('m2','gs'):
    d=json.load(open('log/e7_eye_%s.json'%b))
    tot=sum(sum(c[k][0]+c[k][1] for k in c) for th,ph,c in d['points'])
    print('E7 %s: points %d, total counted decisions %d, margin %s' % (b, len(d['points']), tot, d['margin']))
PY
rm -f /home/pi/gs.owner; echo "LAB4 DONE $(date +%T)"
