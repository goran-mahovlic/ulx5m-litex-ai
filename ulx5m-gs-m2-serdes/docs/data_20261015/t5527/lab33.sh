#!/bin/bash
# TASK-5527 lab33 = STEP 2 (uputa #336): measurement with the recipe chosen in lab30-32:
#   R5 = gs RX_TAPW +2 pinned (eyescan freeze, pin_fields) + m2 TX_SEL_POST 10 (default 5).
# 3 fresh 2.5 G loads (lab22 procedure: m2 then gs -r, SET_ACC 2->0), per load A1 300 s / B (R5) 300 s / A2 300 s, both dirs.
F=/home/pi/fpga; T=/home/pi/ulx5m-serdes/tools; L=/home/pi/ulx5m-serdes/t5527/log33; mkdir -p $L
echo "TASK-5527 $(date +%s) lab33 step2 measure (jelena)" > /home/pi/gs.owner
ber() { (cd $T; echo "BER $1 $(timeout $(($2+300)) python3 lab/ber_long.py --secs $2 --every 60 --out $L/$1.jsonl 2>&1 | grep TOTAL | cut -c1-200)"); }
J() { (cd $T; fpga-jtag $1 run python3 eyescan.py "${@:2}" 2>&1 | tail -1); }
JT() { for b in m2 gs; do echo "JTAG $1 $b: $(cd $T; fpga-jtag $b run python3 ber_jtag_check.py --samples 200 2>&1 | tail -1 | sed 's/.*rx: /rx: /')"; done; }
for r in 1 2 3; do
  echo "-- load r$r $(date +%T) $(vcgencmd get_throttled)"
  fpga-jtag m2 $F/m2_2g5.bit -r 2>&1 | tail -1; fpga-jtag gs $F/gs_2g5.bit -r 2>&1 | tail -1; sleep 3
  for b in m2 gs; do J $b set RX_CDR_SET_ACC_CONFIG=2 >/dev/null; J $b set RX_CDR_SET_ACC_CONFIG=0 >/dev/null; done
  for b in m2 gs; do (cd $T; fpga-jtag $b run python3 eyescan.py health --raw -n 3 --interval 0.2 --label r$r --out $L/r${r}_health_$b.json 2>&1 | grep -E "^HEALTH" | cut -c1-200); done
  for b in m2 gs; do (cd $T; fpga-jtag $b run python3 eyescan.py capture -n 3 --out $L/r${r}_cap_$b.json 2>&1 | grep -E "CAPSTAT" | tail -1 | cut -c1-200); done
  JT r${r}_start
  ber r${r}_A1 300
  J gs freeze RX_TAPW=2 | cut -c1-260; J m2 set TX_SEL_POST=10; JT r${r}_B
  ber r${r}_B_R5 300
  J gs restore | cut -c1-160; J m2 set TX_SEL_POST=5; sleep 1
  ber r${r}_A2 300
  JT r${r}_end
done
rm -f /home/pi/gs.owner; echo "LAB33 DONE $(date +%T)"
