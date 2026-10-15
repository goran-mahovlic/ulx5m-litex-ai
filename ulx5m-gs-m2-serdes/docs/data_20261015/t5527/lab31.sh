#!/bin/bash
# TASK-5527 lab31: SAME load as lab30 (no reload). lab30 found this load flipped: GS->M2 2e-11, M2->GS 1.5e-7..2.6e-7
# (quick30 was the other way round) -> calibrate the gs RX / m2 TX side here, M2->GS has resolution now.
# 30 s serial BER both dirs per candidate, every change undone, reference A between blocks.
T=/home/pi/ulx5m-serdes/tools; L=/home/pi/ulx5m-serdes/t5527/log31; mkdir -p $L
echo "TASK-5527 $(date +%s) lab31 calib gs RX / m2 TX (jelena)" > /home/pi/gs.owner
SECS=${SECS:-30}
J() { (cd $T; fpga-jtag $1 run python3 eyescan.py "${@:2}" 2>&1 | tail -1); }
JT() { for b in m2 gs; do echo "JTAG $1 $b: $(cd $T; fpga-jtag $b run python3 ber_jtag_check.py --samples 200 2>&1 | tail -1 | sed 's/.*rx: /rx: /')"; done; }
M() {
  sleep 2
  local g=$(J $1 get RX_CDR_LOCKED RX_EQA_LOCKED RX_TH_MON RX_OFFSET RX_EQA_TAPW)
  local b=$(cd $T; timeout 200 python3 lab/ber_long.py --secs $SECS --every $SECS --out $L/$2.jsonl 2>&1 | grep TOTAL | sed 's/.*secs=//' | cut -c1-150)
  echo "PT $2 | $g | $b"
}
T1() { J $1 set $4 >/dev/null; M $2 $3; J $1 set $5 >/dev/null; }
echo "-- lab31 $(date +%T) $(vcgencmd get_throttled)"
M gs A0
# uputa #337: fixed AFE offset instead of adaptive (quick30 gs OFFSET 1 -> M2->GS 8.9e-11; lab30 OFFSET 2 -> 1.5e-7)
# control: freeze with no override (adapted op pinned), then gs RX_AFE_OFFSET 1/0/3, m2 7+-1; 60 s each.
SECS=60
J gs freeze | cut -c1-240; M gs gs_frz_ctrl; J gs restore >/dev/null
for v in 1 0 3 1b; do J gs freeze RX_AFE_OFFSET=${v%b} --ext 0b1111 | cut -c1-240; M gs gs_off$v; J gs restore >/dev/null; done
M gs A0b
for v in 6 8; do J m2 freeze RX_AFE_OFFSET=$v --ext 0b1111 | cut -c1-240; M m2 m2_off$v; J m2 restore >/dev/null; done
M gs A0c
SECS=30
for v in -1 1 2 3; do J gs freeze RX_TAPW=$v >/dev/null; M gs gs_tapw$v; J gs restore >/dev/null; done
M gs A1
for v in 1 2 4 8; do T1 gs gs gs_gain$v RX_AFE_GAIN=$v RX_AFE_GAIN=0; done
for v in 8 16 28 31; do T1 gs gs gs_peak$v RX_AFE_PEAK=$v RX_AFE_PEAK=24; done
M gs A2
for v in 31 124; do T1 gs gs gs_ckp$v RX_CDR_CKP=$v RX_CDR_CKP=62; done
for v in 4 16; do T1 gs gs gs_cki$v RX_CDR_CKI=$v RX_CDR_CKI=0; done
for v in 0 8 14; do T1 gs gs gs_lockcfg$v RX_EQA_LOCK_CFG=$v RX_EQA_LOCK_CFG=12; done
M gs A3
for v in 24 16 10; do T1 m2 gs m2_amp$v TX_AMP=$v TX_AMP=31; done
for v in 0 10 15; do T1 m2 gs m2_post$v TX_SEL_POST=$v TX_SEL_POST=5; done
for v in 0 10; do T1 m2 gs m2_pre$v TX_SEL_PRE=$v TX_SEL_PRE=5; done
for v in 0 31; do T1 m2 gs m2_brpost$v TX_BRANCH_EN_POST=$v TX_BRANCH_EN_POST=12; done
for v in 0 31; do T1 m2 gs m2_brpre$v TX_BRANCH_EN_PRE=$v TX_BRANCH_EN_PRE=12; done
M gs A4
echo "BASE m2 $(J m2 get RX_AFE_GAIN RX_AFE_PEAK RX_CDR_CKP RX_CDR_CKI RX_EQA_LOCK_CFG TX_AMP TX_SEL_PRE TX_SEL_POST TX_BRANCH_EN_PRE TX_BRANCH_EN_POST)"
echo "BASE gs $(J gs get RX_AFE_GAIN RX_AFE_PEAK RX_CDR_CKP RX_CDR_CKI RX_EQA_LOCK_CFG TX_AMP TX_SEL_PRE TX_SEL_POST TX_BRANCH_EN_PRE TX_BRANCH_EN_POST)"
JT end
rm -f /home/pi/gs.owner; echo "LAB31 DONE $(date +%T)"
