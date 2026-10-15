#!/bin/bash
# TASK-5525 lab26d: same load. Fine gs TAPW pin around the adapted 0 (lab26c: -8 3e-4, -4 2e-5, +4 7e-7, +8 7e-4 vs A ~1.5e-7).
T=/home/pi/ulx5m-serdes/tools; L=/home/pi/ulx5m-serdes/t5525/log26d; mkdir -p $L
echo "TASK-5525 $(date +%s) lab26d calib (jelena)" > /home/pi/gs.owner
SECS=${SECS:-60}
ber() { (cd $T; echo "BER $1 $(timeout 300 python3 lab/ber_long.py --secs $SECS --every $SECS --out $L/$1.jsonl 2>&1 | grep TOTAL | cut -c1-160)"); }
J() { (cd $T; fpga-jtag $1 run python3 eyescan.py "${@:2}" 2>&1 | tail -1); }
echo "-- lab26d $(date +%T) $(vcgencmd get_throttled)"
ber A0
for t in -2 -1 1 2 3; do
  J gs freeze RX_TAPW=$t | cut -c1-260; ber tapw$t
  J gs restore | cut -c1-160; sleep 1; ber A_tapw$t
done
for b in m2 gs; do echo "JTAG $b end: $(cd $T; fpga-jtag $b run python3 ber_jtag_check.py --samples 200 2>&1 | tail -1 | sed 's/.*rx: /rx: /')"; done
rm -f /home/pi/gs.owner; echo "LAB26D DONE $(date +%T)"
