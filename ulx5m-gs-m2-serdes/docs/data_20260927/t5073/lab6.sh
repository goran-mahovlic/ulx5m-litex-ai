#!/bin/bash
# TASK-5073 lab phase 6 (5 Gb/s): re-test of the PEAK 24 variants vs PROFILE 2 (VERIFY §9.9 next step).
# 5 points x 3 loads x 60 s, loads INTERLEAVED (round k runs a..e once) so drift hits every point alike.
# (a)-(d): E1 5G PROFILE 1 bits + JTAG writes + recal (as E2/E3/E4 in lab2b/lab3); (e): PROFILE 2 bits, no writes (§9.7).
cd /home/pi/ulx5m-serdes/t5066; export ME=TASK-5073 KEEP_LEASE=1; L=$PWD/log5073; mkdir -p $L
T=/home/pi/ulx5m-serdes/tools
own=$(cat /home/pi/gs.owner 2>/dev/null)
if [ -n "$own" ] && [ "${own%% *}" != TASK-5073 ]; then
  age=$(( $(date +%s) - $(echo "$own" | awk '{print $2}') )); [ "$age" -lt 7200 ] && { echo "leased: $own"; exit 3; }
fi
echo "TASK-5073 $(date +%s) SerDes 5G PEAK24 re-test (jelena)" > /home/pi/gs.owner
G=gs_e1_5gp1_txneg_s7.bit; M=m2_e1_5gp1_txneg_s1.bit
A="RX_AFE_GAIN=0,RX_AFE_PEAK=24"
FFE="TX_BRANCH_EN_PRE=0,TX_BRANCH_EN_POST=31,TX_DC_ENABLE=47,TX_SEL_PRE=0"
CDR="RX_CDR_CKP=0x1E,RX_CDR_TRANS_TH=16"
for k in 1 2 3; do
  echo "== round $k $(date +%T)"
  LOG=$L/tmp $T/lab/abrun.sh $G $M 60 1 "t73a_p24|gs:$A|m2:$A" "t73b_p24_post0|gs:$A,$FFE,TX_SEL_POST=0|m2:$A,$FFE,TX_SEL_POST=0" \
      "t73c_p24_post6|gs:$A,$FFE,TX_SEL_POST=6|m2:$A,$FFE,TX_SEL_POST=6" "t73d_p24_ckp1e_tt16|gs:$A,$CDR|m2:$A,$CDR"
  LOG=$L/tmp $T/lab/abrun.sh gs_p2_5g_txneg_s7.bit m2_p2_5g_txneg_s1.bit 60 1 "t73e_p2||"
  for f in $L/tmp/*_r1*.json; do b=$(basename $f); mv $f $L/${b/_r1/_r$k}; done
done
python3 $T/lab/ab_table.py --runs --rank $L/t73*_r*.json
rm -f /home/pi/gs.owner; echo "LAB6 DONE $(date +%T)"
