#!/bin/bash
# TASK-5527 lab35: CONDITIONAL recipe per load (lab33/34: a TAPW+2 pin helps only the receiver that is bad on that load
# and hurts a good one ~x10-100). Per fresh load: A1 120 s -> rule: dir BER > 5e-9 -> pin TAPW +2 on ITS receiver
# (M2->GS -> gs, GS->M2 -> m2); B 300 s; restore; A2 300 s. Plain A/B/A, both dirs; A1 decides, A1+A2 are the reference.
F=/home/pi/fpga; T=/home/pi/ulx5m-serdes/tools; L=/home/pi/ulx5m-serdes/t5527/log35; mkdir -p $L
echo "TASK-5527 $(date +%s) lab35 conditional recipe (jelena)" > /home/pi/gs.owner
TH=5e-9
ber() { (cd $T; timeout $(($2+300)) python3 lab/ber_long.py --secs $2 --every 60 --out $L/$1.jsonl 2>&1 | grep TOTAL | cut -c1-200); }
J() { (cd $T; fpga-jtag $1 run python3 eyescan.py "${@:2}" 2>&1 | tail -1); }
JT() { for b in m2 gs; do echo "JTAG $1 $b: $(cd $T; fpga-jtag $b run python3 ber_jtag_check.py --samples 200 2>&1 | tail -1 | sed 's/.*rx: /rx: /')"; done; }
bad() { python3 -c "import re,sys; m=re.search(r'$1 BER=(\S+)', sys.argv[1]); v=m and m.group(1); print(1 if v not in (None,'None') and float(v)>$TH else 0)" "$2"; }
for r in 1 2 3; do
  echo "-- load r$r $(date +%T) $(vcgencmd get_throttled)"
  fpga-jtag m2 $F/m2_2g5.bit -r 2>&1 | tail -1; fpga-jtag gs $F/gs_2g5.bit -r 2>&1 | tail -1; sleep 3
  for b in m2 gs; do J $b set RX_CDR_SET_ACC_CONFIG=2 >/dev/null; J $b set RX_CDR_SET_ACC_CONFIG=0 >/dev/null; done
  for b in m2 gs; do (cd $T; fpga-jtag $b run python3 eyescan.py capture -n 3 --out $L/r${r}_cap_$b.json 2>&1 | grep -E "CAPSTAT" | tail -1 | cut -c1-200); done
  JT r${r}_start
  a=$(ber r${r}_A1 120); echo "BER r${r}_A1 $a"
  pg=$(bad 'm2->gs' "$a"); pm=$(bad 'gs->m2' "$a"); echo "RULE r$r pin_gs=$pg pin_m2=$pm"
  [ $pg = 1 ] && J gs freeze RX_TAPW=2 | cut -c1-200
  [ $pm = 1 ] && J m2 freeze RX_TAPW=2 | cut -c1-200
  echo "BER r${r}_B_cond_g${pg}m${pm} $(ber r${r}_B_cond_g${pg}m${pm} 300)"
  [ $pg = 1 ] && J gs restore | cut -c1-120
  [ $pm = 1 ] && J m2 restore | cut -c1-120
  sleep 1
  echo "BER r${r}_A2 $(ber r${r}_A2 300)"
  JT r${r}_end
done
rm -f /home/pi/gs.owner; echo "LAB35 DONE $(date +%T)"
