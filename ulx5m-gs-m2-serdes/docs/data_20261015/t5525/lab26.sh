#!/bin/bash
# TASK-5525 lab26: operating-point calibration of the gs RX (m2->gs) at 2.5 G, A/B/A inside ONE load (single-load
# sweeps across loads are not valid, TASK-5487). Levers: (1) m2 TX_AMP down so the gs adapted thresholds leave the +15 rail
# (eye_diagnose hint), (2) gs DFE tap pinned by freeze (TAPW). Each B and each A = 60 s serial BER (ber_long, both dirs).
F=/home/pi/fpga; T=/home/pi/ulx5m-serdes/tools; L=/home/pi/ulx5m-serdes/t5525/log26; mkdir -p $L
echo "TASK-5525 $(date +%s) lab26 calib (jelena)" > /home/pi/gs.owner
SECS=${SECS:-60}
ber() { (cd $T; echo "BER $1 $(timeout 300 python3 lab/ber_long.py --secs $SECS --every $SECS --out $L/$1.jsonl 2>&1 | grep TOTAL | cut -c1-160)"); }
cap() { (cd $T; fpga-jtag gs run python3 eyescan.py capture -n 3 --interval 0.2 --label "$1" --out $L/$1.cap_gs.json 2>&1 | grep CAPSTAT); }
J() { (cd $T; fpga-jtag $1 run python3 eyescan.py "${@:2}" 2>&1 | tail -1); }
echo "-- load $(date +%T) $(vcgencmd get_throttled)"
fpga-jtag m2 $F/m2_2g5.bit -r 2>&1 | tail -1; fpga-jtag gs $F/gs_2g5.bit -r 2>&1 | tail -1; sleep 3
for b in m2 gs; do J $b set RX_CDR_SET_ACC_CONFIG=2 >/dev/null; J $b set RX_CDR_SET_ACC_CONFIG=0 >/dev/null; done
for b in m2 gs; do echo "JTAG $b: $(cd $T; fpga-jtag $b run python3 ber_jtag_check.py --samples 200 2>&1 | tail -1 | sed 's/.*rx: /rx: /')"; done
cap A0; ber A0
for amp in 24 16 10; do
  J m2 set TX_AMP=$amp; sleep 1; cap amp$amp; ber amp$amp
  J m2 set TX_AMP=31; sleep 1; ber A_amp$amp
done
for t in -4 -2 2 4; do
  J gs freeze RX_TAPW=$t | cut -c1-200; ber tapw$t
  J gs restore | cut -c1-160; sleep 1; ber A_tapw$t
done
cap END
for b in m2 gs; do echo "JTAG $b end: $(cd $T; fpga-jtag $b run python3 ber_jtag_check.py --samples 200 2>&1 | tail -1 | sed 's/.*rx: /rx: /')"; done
rm -f /home/pi/gs.owner; echo "LAB26 DONE $(date +%T)"
