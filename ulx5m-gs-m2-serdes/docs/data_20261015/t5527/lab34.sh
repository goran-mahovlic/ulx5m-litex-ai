#!/bin/bash
# TASK-5527 lab34: SAME load as lab33 r3 (no reload) where GS->M2 is the bad direction (A1 3.6e-8). lab30 swept the m2 RX
# on a load with GS->M2 ~2e-11 (no resolution) -> repeat the m2 RX TAPW pin here, 60 s each, A between, both dirs.
T=/home/pi/ulx5m-serdes/tools; L=/home/pi/ulx5m-serdes/t5527/log34; mkdir -p $L
echo "TASK-5527 $(date +%s) lab34 m2 RX tapw on bad GS->M2 load (jelena)" > /home/pi/gs.owner
SECS=60
J() { (cd $T; fpga-jtag $1 run python3 eyescan.py "${@:2}" 2>&1 | tail -1); }
M() {
  sleep 2
  local g=$(J $1 get RX_CDR_LOCKED RX_EQA_LOCKED RX_TH_MON RX_OFFSET RX_EQA_TAPW)
  local b=$(cd $T; timeout 300 python3 lab/ber_long.py --secs $SECS --every $SECS --out $L/$2.jsonl 2>&1 | grep TOTAL | sed 's/.*secs=//' | cut -c1-150)
  echo "PT $2 | $g | $b"
}
echo "-- lab34 $(date +%T) $(vcgencmd get_throttled)"
M m2 A0
for v in 1 2 3; do J m2 freeze RX_TAPW=$v >/dev/null; M m2 m2_tapw$v; J m2 restore >/dev/null; done
M m2 A1
for v in -1 4; do J m2 freeze RX_TAPW=$v >/dev/null; M m2 m2_tapw$v; J m2 restore >/dev/null; done
J m2 freeze RX_AFE_OFFSET=6 --ext 0b1111 >/dev/null; M m2 m2_off6; J m2 restore >/dev/null
J m2 freeze RX_AFE_OFFSET=8 --ext 0b1111 >/dev/null; M m2 m2_off8; J m2 restore >/dev/null
J gs freeze RX_TAPW=2 >/dev/null; M gs gs_tapw2; J gs restore >/dev/null
M m2 A2
rm -f /home/pi/gs.owner; echo "LAB34 DONE $(date +%T)"
