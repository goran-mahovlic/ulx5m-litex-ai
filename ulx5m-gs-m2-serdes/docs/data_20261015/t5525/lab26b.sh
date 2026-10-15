#!/bin/bash
# TASK-5525 lab26b: same load as lab26 (no reload). gs TAPW pinned again, now with the freeze readback (lab26 freeze crashed in
# its print after the writes), and the m2 TX_AMP=16 trade-off repeated twice. A/B/A, 60 s each.
T=/home/pi/ulx5m-serdes/tools; L=/home/pi/ulx5m-serdes/t5525/log26b; mkdir -p $L
echo "TASK-5525 $(date +%s) lab26b calib (jelena)" > /home/pi/gs.owner
SECS=${SECS:-60}
ber() { (cd $T; echo "BER $1 $(timeout 300 python3 lab/ber_long.py --secs $SECS --every $SECS --out $L/$1.jsonl 2>&1 | grep TOTAL | cut -c1-160)"); }
J() { (cd $T; fpga-jtag $1 run python3 eyescan.py "${@:2}" 2>&1 | tail -1); }
echo "-- lab26b $(date +%T) $(vcgencmd get_throttled)"
ber A0
for t in -8 -4 4 8; do
  J gs freeze RX_TAPW=$t | cut -c1-260; ber tapw$t
  J gs restore | cut -c1-160; sleep 1; ber A_tapw$t
done
for r in 1 2; do
  J m2 set TX_AMP=16; sleep 1; ber amp16_r$r
  J m2 set TX_AMP=31; sleep 1; ber A_amp16_r$r
done
for b in m2 gs; do echo "JTAG $b end: $(cd $T; fpga-jtag $b run python3 ber_jtag_check.py --samples 200 2>&1 | tail -1 | sed 's/.*rx: /rx: /')"; done
rm -f /home/pi/gs.owner; echo "LAB26B DONE $(date +%T)"
