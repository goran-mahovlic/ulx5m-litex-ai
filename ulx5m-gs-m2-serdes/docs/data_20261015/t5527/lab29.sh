#!/bin/bash
# TASK-5527 lab29 (upute #335, Goran 17:59): re-tune M2->GS after the C143/C144 swap (17:45) on ONE fresh 2.5 G load.
# Metric per candidate: 20 s serial BER (ber_long, gs own counters for m2->gs; m2->gs ~1e-2 = ~1e8 errors, no resolution
# problem) + RX_CDR/EQA lock + TH_MON/OFFSET of gs; every change is undone before the next one; reference A every block.
# JTAG PEER (200 samples = ~40 s) only at start/end. Order: gs RX AFE_GAIN, AFE_PEAK, TAPW (freeze), CDR_CKP/CKI,
# EQA_LOCK_CFG; m2 TX AMP, SEL_PRE/POST, BRANCH_EN_PRE/POST, DC_OFFSET.
F=/home/pi/fpga; T=/home/pi/ulx5m-serdes/tools; L=/home/pi/ulx5m-serdes/t5527/log29; mkdir -p $L
echo "TASK-5527 $(date +%s) lab29 retune M2->GS (jelena)" > /home/pi/gs.owner
J() { (cd $T; fpga-jtag $1 run python3 eyescan.py "${@:2}" 2>&1 | tail -1); }
JT() { for b in m2 gs; do echo "JTAG $1 $b: $(cd $T; fpga-jtag $b run python3 ber_jtag_check.py --samples 200 2>&1 | tail -1 | sed 's/.*rx: /rx: /')"; done; }
M() {  # M <label>: 20 s serial BER + gs lock state
  sleep 2
  local g=$(J gs get RX_CDR_LOCKED RX_EQA_LOCKED RX_TH_MON RX_OFFSET RX_EQA_TAPW | sed 's/board=gs //')
  local b=$(cd $T; timeout 200 python3 lab/ber_long.py --secs 20 --every 20 --out $L/$1.jsonl 2>&1 | grep TOTAL | sed 's/.*secs=//' | cut -c1-150)
  echo "PT $1 | $g | $b"
}
T1() { J $1 set $3 >/dev/null; M $2; J $1 set $4 >/dev/null; }   # T1 <board> <label> <try> <undo>
GSB="RX_AFE_GAIN=0 RX_AFE_PEAK=24 RX_CDR_CKP=62 RX_CDR_CKI=0 RX_EQA_LOCK_CFG=12"
M2B="TX_AMP=31 TX_SEL_PRE=5 TX_SEL_POST=5 TX_BRANCH_EN_PRE=12 TX_BRANCH_EN_POST=12 TX_DC_OFFSET=8"
echo "-- load $(date +%T) $(vcgencmd get_throttled)"
fpga-jtag m2 $F/m2_2g5.bit -r 2>&1 | tail -1; fpga-jtag gs $F/gs_2g5.bit -r 2>&1 | tail -1; sleep 3
for b in m2 gs; do J $b set RX_CDR_SET_ACC_CONFIG=2 >/dev/null; J $b set RX_CDR_SET_ACC_CONFIG=0 >/dev/null; done
JT start
M A0
for v in 1 2 3 4 6 8; do T1 gs gs_gain$v RX_AFE_GAIN=$v RX_AFE_GAIN=0; done
for v in 8 16 20 28 31; do T1 gs gs_peak$v RX_AFE_PEAK=$v RX_AFE_PEAK=24; done
M A1
for v in -4 -2 -1 1 2 4; do J gs freeze RX_TAPW=$v >/dev/null; M gs_tapw$v; J gs restore >/dev/null; done
for v in 31 124 248; do T1 gs gs_ckp$v RX_CDR_CKP=$v RX_CDR_CKP=62; done
for v in 1 4 16; do T1 gs gs_cki$v RX_CDR_CKI=$v RX_CDR_CKI=0; done
for v in 0 4 8 14; do T1 gs gs_lockcfg$v RX_EQA_LOCK_CFG=$v RX_EQA_LOCK_CFG=12; done
M A2
for v in 24 16 8; do T1 m2 m2_amp$v TX_AMP=$v TX_AMP=31; done
for v in 0 10 15; do T1 m2 m2_post$v TX_SEL_POST=$v TX_SEL_POST=5; done
for v in 0 10; do T1 m2 m2_pre$v TX_SEL_PRE=$v TX_SEL_PRE=5; done
for v in 0 31; do T1 m2 m2_brpost$v TX_BRANCH_EN_POST=$v TX_BRANCH_EN_POST=12; done
for v in 0 31; do T1 m2 m2_brpre$v TX_BRANCH_EN_PRE=$v TX_BRANCH_EN_PRE=12; done
for v in 0 4 12 16; do T1 m2 m2_dc$v TX_DC_OFFSET=$v TX_DC_OFFSET=8; done
M A3
echo "BASE gs $(J gs get $(echo $GSB | sed 's/=[0-9]*//g'))"; echo "BASE m2 $(J m2 get $(echo $M2B | sed 's/=[0-9]*//g'))"
JT end
rm -f /home/pi/gs.owner; echo "LAB29 DONE $(date +%T)"
