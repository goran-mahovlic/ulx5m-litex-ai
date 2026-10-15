#!/bin/bash
# TASK-5527 lab30 (uputa #336, Goran 19:05): CALIBRATION after the C143/C144 repair (18:49), ONE fresh 2.5 G load.
# quick30 18:51: M2->GS 8.9e-11, GS->M2 8.9e-9 -> GS->M2 is now the worse one. Goal: both dirs within ~3x, without
# hurting M2->GS. Screening metric: 30 s serial BER both dirs (ber_long) + lock/TH_MON/OFFSET/TAPW of the touched RX.
# Every change undone before the next; reference A between blocks. Order: m2 RX TAPW freeze, AFE_GAIN, AFE_PEAK,
# CDR CKP/CKI, EQA_LOCK_CFG; gs TX AMP, SEL_PRE/POST, BRANCH_EN_PRE/POST; gs RX TAPW +1/+2 (old M2->GS recipe).
F=/home/pi/fpga; T=/home/pi/ulx5m-serdes/tools; L=/home/pi/ulx5m-serdes/t5527/log30; mkdir -p $L
echo "TASK-5527 $(date +%s) lab30 calib (jelena)" > /home/pi/gs.owner
SECS=${SECS:-30}
J() { (cd $T; fpga-jtag $1 run python3 eyescan.py "${@:2}" 2>&1 | tail -1); }
JT() { for b in m2 gs; do echo "JTAG $1 $b: $(cd $T; fpga-jtag $b run python3 ber_jtag_check.py --samples 200 2>&1 | tail -1 | sed 's/.*rx: /rx: /')"; done; }
M() {  # M <board-rx> <label>
  sleep 2
  local g=$(J $1 get RX_CDR_LOCKED RX_EQA_LOCKED RX_TH_MON RX_OFFSET RX_EQA_TAPW)
  local b=$(cd $T; timeout 200 python3 lab/ber_long.py --secs $SECS --every $SECS --out $L/$2.jsonl 2>&1 | grep TOTAL | sed 's/.*secs=//' | cut -c1-150)
  echo "PT $2 | $g | $b"
}
T1() { J $1 set $4 >/dev/null; M $2 $3; J $1 set $5 >/dev/null; }   # T1 <board-set> <board-rx> <label> <try> <undo>
echo "-- load $(date +%T) $(vcgencmd get_throttled)"
fpga-jtag m2 $F/m2_2g5.bit -r 2>&1 | tail -1; fpga-jtag gs $F/gs_2g5.bit -r 2>&1 | tail -1; sleep 3
for b in m2 gs; do J $b set RX_CDR_SET_ACC_CONFIG=2 >/dev/null; J $b set RX_CDR_SET_ACC_CONFIG=0 >/dev/null; done
for b in m2 gs; do (cd $T; fpga-jtag $b run python3 eyescan.py health --raw -n 3 --interval 0.2 --label l30 --out $L/start_$b.json 2>&1 | grep -E "^HEALTH" | cut -c1-200); done
for b in m2 gs; do (cd $T; fpga-jtag $b run python3 eyescan.py capture -n 3 --out $L/start_cap_$b.json 2>&1 | grep -E "CAPSTAT" | tail -1 | cut -c1-200); done
JT start
M m2 A0
for v in -2 -1 1 2 3; do J m2 freeze RX_TAPW=$v >/dev/null; M m2 m2_tapw$v; J m2 restore >/dev/null; done
M m2 A1
for v in 1 2 4 8; do T1 m2 m2 m2_gain$v RX_AFE_GAIN=$v RX_AFE_GAIN=0; done
for v in 8 16 28 31; do T1 m2 m2 m2_peak$v RX_AFE_PEAK=$v RX_AFE_PEAK=24; done
M m2 A2
for v in 31 124; do T1 m2 m2 m2_ckp$v RX_CDR_CKP=$v RX_CDR_CKP=62; done
for v in 4 16; do T1 m2 m2 m2_cki$v RX_CDR_CKI=$v RX_CDR_CKI=0; done
for v in 0 8 14; do T1 m2 m2 m2_lockcfg$v RX_EQA_LOCK_CFG=$v RX_EQA_LOCK_CFG=12; done
M m2 A3
for v in 24 16 10; do T1 gs m2 gs_amp$v TX_AMP=$v TX_AMP=31; done
for v in 0 10 15; do T1 gs m2 gs_post$v TX_SEL_POST=$v TX_SEL_POST=5; done
for v in 0 10; do T1 gs m2 gs_pre$v TX_SEL_PRE=$v TX_SEL_PRE=5; done
for v in 0 31; do T1 gs m2 gs_brpost$v TX_BRANCH_EN_POST=$v TX_BRANCH_EN_POST=12; done
for v in 0 31; do T1 gs m2 gs_brpre$v TX_BRANCH_EN_PRE=$v TX_BRANCH_EN_PRE=12; done
M m2 A4
for v in 1 2; do J gs freeze RX_TAPW=$v >/dev/null; M gs gs_tapw$v; J gs restore >/dev/null; done
M m2 A5
echo "BASE m2 $(J m2 get RX_AFE_GAIN RX_AFE_PEAK RX_CDR_CKP RX_CDR_CKI RX_EQA_LOCK_CFG TX_AMP TX_SEL_PRE TX_SEL_POST TX_BRANCH_EN_PRE TX_BRANCH_EN_POST)"
echo "BASE gs $(J gs get RX_AFE_GAIN RX_AFE_PEAK RX_CDR_CKP RX_CDR_CKI RX_EQA_LOCK_CFG TX_AMP TX_SEL_PRE TX_SEL_POST TX_BRANCH_EN_PRE TX_BRANCH_EN_POST)"
JT end
rm -f /home/pi/gs.owner; echo "LAB30 DONE $(date +%T)"
