#!/bin/bash
# TASK-5066 lab phase 3 (5 Gb/s): seeds, CLK_DIRECT, E4 CDR, E3 TX FFE, E5 VCM, E6 gs PLL_REF_RTERM=0.
# AFE="RX_AFE_GAIN=g,RX_AFE_PEAK=p" = E2 winner, written on both boards in every E3-E5 point. 1 load x 60 s per point.
cd /home/pi/ulx5m-serdes/t5066; export LOG=$PWD/log ME=TASK-5066 KEEP_LEASE=1; mkdir -p $LOG
T=/home/pi/ulx5m-serdes/tools; A=${AFE:?AFE=...}
own=$(cat /home/pi/gs.owner 2>/dev/null); [ -n "$own" ] && [ "${own%% *}" != TASK-5066 ] && { echo "leased: $own"; exit 3; }
echo "TASK-5066 $(date +%s) SerDes 5G tuning (jelena) phase 3" > /home/pi/gs.owner
G=gs_e1_5gp1_txneg_s7.bit; M=m2_e1_5gp1_txneg_s1.bit
echo "== seeds 5G $(date +%T)"
for s in 2 3 4 5; do $T/lab/abrun.sh $G m2_e1_5gp1_txneg_s$s.bit 60 1 "sd5_gs7_m2$s||"; done
for s in 2 3 4; do $T/lab/abrun.sh gs_e1_5gp1_txneg_s$s.bit $M 60 1 "sd5_gs${s}_m21||"; done
$T/lab/abrun.sh gs_x_5g_clkdir_s7.bit m2_x_5g_clkdir_s1.bit 60 1 "x5_clkdir||"
echo "== E4 CDR $(date +%T)"
P=()
for ckp in 0xF8 0x7E 0x3E 0x1E; do for tt in 8 16 32; do
  f="$A,RX_CDR_CKP=$ckp,RX_CDR_TRANS_TH=$tt"; P+=("e4_ckp${ckp#0x}_tt$tt|gs:$f|m2:$f"); done; done
$T/lab/abrun.sh $G $M 60 1 "${P[@]}"
echo "== E3 TX FFE $(date +%T)"
P=()
for sp in 0 6 12 17 20; do
  f="$A,TX_BRANCH_EN_PRE=0,TX_BRANCH_EN_POST=31,TX_DC_ENABLE=47,TX_SEL_PRE=0,TX_SEL_POST=$sp"; P+=("e3_post$sp|gs:$f|m2:$f"); done
for sq in 2 5; do
  f="$A,TX_BRANCH_EN_PRE=12,TX_BRANCH_EN_POST=31,TX_DC_ENABLE=53,TX_SEL_PRE=$sq,TX_SEL_POST=12"; P+=("e3_pre${sq}_post12|gs:$f|m2:$f"); done
for amp in 20 24 28; do f="$A,TX_AMP=$amp"; P+=("e3_amp$amp|gs:$f|m2:$f"); done
$T/lab/abrun.sh $G $M 60 1 "${P[@]}"
echo "== E5 VCM $(date +%T)"
P=()
for v in 2 4 5; do f="$A,RX_AFE_VCMSEL=$v,RX_RTERM_VCMSEL=$v"; P+=("e5_vcm$v|gs:$f|m2:$f"); done
$T/lab/abrun.sh $G $M 60 1 "${P[@]}"
echo "== E6 gs PLL_REF_RTERM=0 $(date +%T)"
$T/lab/abrun.sh gs_e6_5gp1_txneg_rterm0_s7.bit $M 60 3 "e6_rterm0|gs:$A|m2:$A"
$T/lab/abrun.sh $G $M 60 3 "e6_rterm1|gs:$A|m2:$A"
python3 $T/lab/ab_table.py $LOG/sd5_*_r*.json $LOG/x5_*_r*.json $LOG/e4_*_r*.json $LOG/e3_*_r*.json $LOG/e5_*_r*.json $LOG/e6_*_r*.json
rm -f /home/pi/gs.owner; echo "LAB3 DONE $(date +%T)"
