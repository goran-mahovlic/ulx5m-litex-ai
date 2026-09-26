#!/bin/bash
# TASK-5066 lab phase 1 (2.5 Gb/s): E0 health, E1 A/B TX_DETECT_RX_I, #98 sides (TX_NEG on both, seeds)
cd /home/pi/ulx5m-serdes/t5066; export LOG=$PWD/log; mkdir -p $LOG
T=/home/pi/ulx5m-serdes/tools; B=/home/pi/ulx5m-serdes/bitstreams
own=$(cat /home/pi/gs.owner 2>/dev/null); [ -n "$own" ] && [ "${own%% *}" != TASK-5066 ] && { echo "leased: $own"; exit 3; }
echo "TASK-5066 $(date +%s) SerDes 5G tuning (jelena) E0/E1/sides" > /home/pi/gs.owner
echo "== E0 2.5G $(date +%T)"
fpga-jtag m2 $B/ber_m2_2g5_p1_txneg_CFGRST.bit -r 2>&1 | tail -1; fpga-jtag gs $B/ber_gs_2g5_p1_CFGRST.bit -r 2>&1 | tail -1; sleep 5
for b in gs m2; do fpga-jtag $b run python3 $T/eyescan.py health -n 10 --label "E0 2g5 p1" --out $LOG/e0_2g5_$b.json 2>&1 | grep -v "^$"; done
export ME=TASK-5066 KEEP_LEASE=1
echo "== E1 2.5G $(date +%T)"
$T/lab/abrun.sh $B/ber_gs_2g5_p1_CFGRST.bit $B/ber_m2_2g5_p1_txneg_CFGRST.bit 60 3 "e1_2g5_det1||"
$T/lab/abrun.sh gs_e1_2g5p1_s7.bit m2_e1_2g5p1_txneg_s1.bit 60 3 "e1_2g5_det0||"
echo "TASK-5066 $(date +%s) SerDes 5G tuning (jelena) sides" > /home/pi/gs.owner
echo "== sides 2.5G $(date +%T)"
$T/lab/abrun.sh gs_sd_2g5p1_txneg_s7.bit m2_e1_2g5p1_txneg_s1.bit 300 1 "sd_gs7_m21||"
$T/lab/abrun.sh gs_sd_2g5p1_txneg_s2.bit m2_e1_2g5p1_txneg_s1.bit 300 1 "sd_gs2_m21||"
$T/lab/abrun.sh gs_sd_2g5p1_txneg_s3.bit m2_e1_2g5p1_txneg_s1.bit 300 1 "sd_gs3_m21||"
$T/lab/abrun.sh gs_sd_2g5p1_txneg_s7.bit m2_e1_2g5p1_txneg_s2.bit 300 1 "sd_gs7_m22||"
$T/lab/abrun.sh gs_sd_2g5p1_txneg_s7.bit m2_e1_2g5p1_txneg_s3.bit 300 1 "sd_gs7_m23||"
$T/lab/abrun.sh gs_e1_2g5p1_s7.bit m2_e1_2g5p1_txneg_s1.bit 300 1 "sd_gs7nt_m21||"
python3 $T/lab/ab_table.py $LOG/e1_*_r*.json $LOG/sd_*_r*.json
rm -f /home/pi/gs.owner; echo "LAB1 DONE $(date +%T)"
