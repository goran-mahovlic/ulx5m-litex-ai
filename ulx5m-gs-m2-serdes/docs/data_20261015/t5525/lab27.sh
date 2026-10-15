#!/bin/bash
# TASK-5525 lab27: confirmation of the gs RX operating point TAPW=+2 (lab26d: m2->gs 6.7e-9 vs adapted 0 ~1e-7..2e-7, one load)
# on 2 fresh loads (load scatter, TASK-5487): per load lab22 procedure, ber_jtag_check, A 300 s (adapted), B 300 s (gs freeze
# RX_TAPW=2), A 300 s, then exploratory m2 freeze RX_TAPW=2 120 s (gs->m2) + restore.
F=/home/pi/fpga; T=/home/pi/ulx5m-serdes/tools; L=/home/pi/ulx5m-serdes/t5525/log27; mkdir -p $L
echo "TASK-5525 $(date +%s) lab27 confirm (jelena)" > /home/pi/gs.owner
ber() { (cd $T; echo "BER $1 $(timeout $(($2+300)) python3 lab/ber_long.py --secs $2 --every 60 --out $L/$1.jsonl 2>&1 | grep TOTAL | cut -c1-200)"); }
J() { (cd $T; fpga-jtag $1 run python3 eyescan.py "${@:2}" 2>&1 | tail -1); }
JT() { for b in m2 gs; do echo "JTAG $1 $b: $(cd $T; fpga-jtag $b run python3 ber_jtag_check.py --samples 200 2>&1 | tail -1 | sed 's/.*rx: /rx: /')"; done; }
for r in 1 2; do
  echo "-- load r$r $(date +%T) $(vcgencmd get_throttled)"
  fpga-jtag m2 $F/m2_2g5.bit -r 2>&1 | tail -1; fpga-jtag gs $F/gs_2g5.bit -r 2>&1 | tail -1; sleep 3
  for b in m2 gs; do J $b set RX_CDR_SET_ACC_CONFIG=2 >/dev/null; J $b set RX_CDR_SET_ACC_CONFIG=0 >/dev/null; done
  JT r${r}_start
  ber r${r}_A1 300
  J gs freeze RX_TAPW=2 | cut -c1-260; JT r${r}_B
  ber r${r}_B_gs_tapw2 300
  J gs restore | cut -c1-160; sleep 1
  ber r${r}_A2 300
  J m2 freeze RX_TAPW=2 | cut -c1-260
  ber r${r}_m2_tapw2 120
  J m2 restore | cut -c1-160; JT r${r}_end
done
rm -f /home/pi/gs.owner; echo "LAB27 DONE $(date +%T)"
