#!/bin/bash
# TASK-5527 lab37 = G2 (uputa #338, SERDES_UMJERAVANJE_KAKO_DRUGI §6): adapt on PRBS-15 instead of the 8b10b frame, then freeze.
# Per fresh load (5): A1 60 s (adapted on 8b10b as always) -> both TX PRBS-15 on -> 5 s -> eyescan freeze on BOTH RX (EN_EQA=0,
# EXT 0b0111: tap/thresholds pinned at the PRBS-adapted point) -> both TX PRBS off -> B 60 s -> restore both -> A2 60 s.
# Spread across loads (worst/median) is the metric, both directions.
F=/home/pi/fpga; T=/home/pi/ulx5m-serdes/tools; L=/home/pi/ulx5m-serdes/t5527/log37; mkdir -p $L
echo "TASK-5527 $(date +%s) lab37 G2 PRBS-adapt freeze (jelena)" > /home/pi/gs.owner
ber() { (cd $T; timeout $(($2+300)) python3 lab/ber_long.py --secs $2 --every 60 --out $L/$1.jsonl 2>&1 | grep TOTAL | cut -c1-200); }
J() { (cd $T; fpga-jtag $1 run python3 eyescan.py "${@:2}" 2>&1 | tail -1); }
P() { (cd $T; fpga-jtag $1 run python3 lab/strobe_probe.py "${@:2}" 2>&1 | grep -E "^STATE" | cut -c1-200); }
JT() { for b in m2 gs; do echo "JTAG $1 $b: $(cd $T; fpga-jtag $b run python3 ber_jtag_check.py --samples 200 2>&1 | tail -1 | sed 's/.*rx: /rx: /')"; done; }
for r in 1 2 3 4 5; do
  echo "-- load r$r $(date +%T) $(vcgencmd get_throttled)"
  fpga-jtag m2 $F/m2_2g5.bit -r 2>&1 | tail -1; fpga-jtag gs $F/gs_2g5.bit -r 2>&1 | tail -1; sleep 3
  for b in m2 gs; do J $b set RX_CDR_SET_ACC_CONFIG=2 >/dev/null; J $b set RX_CDR_SET_ACC_CONFIG=0 >/dev/null; done
  for b in m2 gs; do (cd $T; fpga-jtag $b run python3 eyescan.py capture -n 3 --out $L/r${r}_cap_$b.json 2>&1 | grep -E "CAPSTAT" | tail -1 | cut -c1-200); done
  JT r${r}_start
  echo "BER r${r}_A1 $(ber r${r}_A1 60)"
  P gs tx_prbs_on; P m2 tx_prbs_on; sleep 5
  for b in m2 gs; do J $b freeze | cut -c1-230; done
  P gs tx_prbs_off; P m2 tx_prbs_off; sleep 2
  JT r${r}_B
  echo "BER r${r}_B_prbsfrz $(ber r${r}_B_prbsfrz 60)"
  for b in m2 gs; do J $b restore | cut -c1-140; done; sleep 1
  echo "BER r${r}_A2 $(ber r${r}_A2 60)"
done
rm -f /home/pi/gs.owner; echo "LAB37 DONE $(date +%T)"
