#!/bin/bash
# TASK-5527 lab38 = G3 (uputa #338): SYMMETRIC TX swing, both TX together 31 -> 24 -> 20 -> 16 -> 12 (default FFE 5/5), plus FFE off
# (TX_SEL_PRE=TX_SEL_POST=0) at 31 and 20; until RX_TH_MON leaves +15 on both RX. 60 s per point, A between, 3 fresh loads.
# Then G7 map on the last load: RX_AFE_OFFSET 0..31 pinned (freeze --ext 0b1111) -> RX_OFFSET read back, both boards, no BER.
F=/home/pi/fpga; T=/home/pi/ulx5m-serdes/tools; L=/home/pi/ulx5m-serdes/t5527/log38; mkdir -p $L
echo "TASK-5527 $(date +%s) lab38 G3 symmetric TX_AMP + G7 map (jelena)" > /home/pi/gs.owner
SECS=60
J() { (cd $T; fpga-jtag $1 run python3 eyescan.py "${@:2}" 2>&1 | tail -1); }
JT() { for b in m2 gs; do echo "JTAG $1 $b: $(cd $T; fpga-jtag $b run python3 ber_jtag_check.py --samples 200 2>&1 | tail -1 | sed 's/.*rx: /rx: /')"; done; }
M() {
  sleep 2
  local g=$(J gs get RX_CDR_LOCKED RX_TH_MON RX_OFFSET RX_EQA_TAPW | sed 's/board=//')
  local m=$(J m2 get RX_CDR_LOCKED RX_TH_MON RX_OFFSET RX_EQA_TAPW | sed 's/board=//')
  local b=$(cd $T; timeout 300 python3 lab/ber_long.py --secs $SECS --every $SECS --out $L/$1.jsonl 2>&1 | grep TOTAL | sed 's/.*secs=//' | cut -c1-150)
  echo "PT $1 | $g | $m | $b"
}
S() { for b in m2 gs; do J $b set "$@" >/dev/null; done; }
for r in 1 2 3; do
  echo "-- load r$r $(date +%T) $(vcgencmd get_throttled)"
  fpga-jtag m2 $F/m2_2g5.bit -r 2>&1 | tail -1; fpga-jtag gs $F/gs_2g5.bit -r 2>&1 | tail -1; sleep 3
  for b in m2 gs; do J $b set RX_CDR_SET_ACC_CONFIG=2 >/dev/null; J $b set RX_CDR_SET_ACC_CONFIG=0 >/dev/null; done
  JT r${r}_start
  M r${r}_A0
  for a in 24 20 16 12; do S TX_AMP=$a; M r${r}_amp$a; done
  S TX_AMP=31; M r${r}_A1
  S TX_SEL_PRE=0 TX_SEL_POST=0; M r${r}_ffe0_amp31
  S TX_AMP=20; M r${r}_ffe0_amp20
  S TX_AMP=31 TX_SEL_PRE=5 TX_SEL_POST=5; M r${r}_A2
  JT r${r}_end
done
echo "-- G7 map $(date +%T)"
for b in gs m2; do
  for v in $(seq 0 31); do echo "MAP $b AFE=$v $(J $b freeze RX_AFE_OFFSET=$v --ext 0b1111 | grep -o "'RX_AFE_OFFSET': [0-9]*") RX_OFFSET=$(J $b get RX_OFFSET | grep -o 'RX_OFFSET=[-0-9]*')"; done
  J $b restore | cut -c1-120
done
rm -f /home/pi/gs.owner; echo "LAB38 DONE $(date +%T)"
