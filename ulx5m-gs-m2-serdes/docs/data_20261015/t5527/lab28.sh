#!/bin/bash
# TASK-5527 lab28 (Goran 15.10. 17:46, state after the 17:45 USB re-enumeration of both probes): weaker direction m2->gs,
# 3 fresh 2.5 G loads x (A1 300 s adapted / B 300 s gs RX_TAPW pinned +2 / A2 300 s adapted). Per load lab22 procedure
# (m2 then gs -r, SET_ACC 2->0), health + eyescan capture (eye_capture_op) on both boards, JTAG PEER at start/B/end.
F=/home/pi/fpga; T=/home/pi/ulx5m-serdes/tools; L=/home/pi/ulx5m-serdes/t5527/log28; mkdir -p $L
echo "TASK-5527 $(date +%s) lab28 m2->gs A/B/A (jelena)" > /home/pi/gs.owner
ber() { (cd $T; echo "BER $1 $(timeout $(($2+300)) python3 lab/ber_long.py --secs $2 --every 60 --out $L/$1.jsonl 2>&1 | grep TOTAL | cut -c1-200)"); }
J() { (cd $T; fpga-jtag $1 run python3 eyescan.py "${@:2}" 2>&1 | tail -1); }
JT() { for b in m2 gs; do echo "JTAG $1 $b: $(cd $T; fpga-jtag $b run python3 ber_jtag_check.py --samples 200 2>&1 | tail -1 | sed 's/.*rx: /rx: /')"; done; }
HC() { for b in m2 gs; do
    (cd $T; fpga-jtag $b run python3 eyescan.py health --raw -n 3 --interval 0.2 --label "$1" --out "$L/$1.health_$b.json" 2>&1 | grep -E "^HEALTH|PLL_LOCKED|Error" | cut -c1-260)
    (cd $T; fpga-jtag $b run python3 eyescan.py capture -n 10 --interval 0.2 --label "$1" --out "$L/$1.capture_$b.json" 2>&1 | grep -E "^CAP" | cut -c1-260)
  done; }
for r in 1 2 3; do
  echo "-- load r$r $(date +%T) $(vcgencmd get_throttled)"
  fpga-jtag m2 $F/m2_2g5.bit -r 2>&1 | tail -1; fpga-jtag gs $F/gs_2g5.bit -r 2>&1 | tail -1; sleep 3
  for b in m2 gs; do J $b set RX_CDR_SET_ACC_CONFIG=2 >/dev/null; J $b set RX_CDR_SET_ACC_CONFIG=0 >/dev/null; done
  HC r${r}_start; JT r${r}_start
  ber r${r}_A1 300
  J gs freeze RX_TAPW=2 | cut -c1-260; JT r${r}_B
  ber r${r}_B_gs_tapw2 300
  J gs restore | cut -c1-160; sleep 1
  ber r${r}_A2 300
  HC r${r}_end; JT r${r}_end
done
rm -f /home/pi/gs.owner; echo "LAB28 DONE $(date +%T)"
