#!/bin/bash
# TASK-5527 lab32: recipe selection on 2 FRESH loads (lab30/31 = one load only; the worse direction flips per load).
# Per load: A, R1 = gs RX_TAPW+2 (pin), R2 = R1 + gs TX_AMP 16, R3 = R1 + gs TX_BRANCH_EN_POST 0, R5 = R1 + m2 TX_SEL_POST 10
# (lab31: M2->GS x9, GS->M2 unchanged), R4 = gs TX_AMP 16 alone, R6 = m2 TX_SEL_POST 10 alone, A; 60 s each, both dirs.
F=/home/pi/fpga; T=/home/pi/ulx5m-serdes/tools; L=/home/pi/ulx5m-serdes/t5527/log32; mkdir -p $L
echo "TASK-5527 $(date +%s) lab32 recipe select (jelena)" > /home/pi/gs.owner
SECS=60
J() { (cd $T; fpga-jtag $1 run python3 eyescan.py "${@:2}" 2>&1 | tail -1); }
JT() { for b in m2 gs; do echo "JTAG $1 $b: $(cd $T; fpga-jtag $b run python3 ber_jtag_check.py --samples 200 2>&1 | tail -1 | sed 's/.*rx: /rx: /')"; done; }
M() {
  sleep 2
  local g=$(J gs get RX_CDR_LOCKED RX_EQA_LOCKED RX_TH_MON RX_OFFSET RX_EQA_TAPW RX_TAPW)
  local m=$(J m2 get RX_CDR_LOCKED RX_TH_MON RX_OFFSET RX_EQA_TAPW | sed 's/board=//')
  local b=$(cd $T; timeout 300 python3 lab/ber_long.py --secs $SECS --every $SECS --out $L/$1.jsonl 2>&1 | grep TOTAL | sed 's/.*secs=//' | cut -c1-150)
  echo "PT $1 | $g | $m | $b"
}
for r in 1 2; do
  echo "-- load r$r $(date +%T) $(vcgencmd get_throttled)"
  fpga-jtag m2 $F/m2_2g5.bit -r 2>&1 | tail -1; fpga-jtag gs $F/gs_2g5.bit -r 2>&1 | tail -1; sleep 3
  for b in m2 gs; do J $b set RX_CDR_SET_ACC_CONFIG=2 >/dev/null; J $b set RX_CDR_SET_ACC_CONFIG=0 >/dev/null; done
  for b in m2 gs; do (cd $T; fpga-jtag $b run python3 eyescan.py capture -n 3 --out $L/r${r}_cap_$b.json 2>&1 | grep -E "CAPSTAT" | tail -1 | cut -c1-200); done
  JT r${r}_start
  M r${r}_A1
  J gs freeze RX_TAPW=2 | cut -c1-240; M r${r}_R1_tapw2
  J gs set TX_AMP=16 >/dev/null; M r${r}_R2_tapw2_amp16; J gs set TX_AMP=31 >/dev/null
  J gs set TX_BRANCH_EN_POST=0 >/dev/null; M r${r}_R3_tapw2_brpost0; J gs set TX_BRANCH_EN_POST=12 >/dev/null
  J m2 set TX_SEL_POST=10 >/dev/null; M r${r}_R5_tapw2_m2post10; J m2 set TX_SEL_POST=5 >/dev/null
  J gs restore >/dev/null
  J m2 set TX_SEL_POST=10 >/dev/null; M r${r}_R6_m2post10; J m2 set TX_SEL_POST=5 >/dev/null
  J gs set TX_AMP=16 >/dev/null; M r${r}_R4_amp16; J gs set TX_AMP=31 >/dev/null
  M r${r}_A2
  JT r${r}_end
done
rm -f /home/pi/gs.owner; echo "LAB32 DONE $(date +%T)"
