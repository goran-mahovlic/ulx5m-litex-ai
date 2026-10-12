#!/bin/bash
# TASK-5483 lab16 (12.10.2026 ~18:15, uputa #305): search sweep after the supply-filter rework, 60 s per point, 1 load per point.
# Per point: load m2 then gs (-r, CFGRST bits from /home/pi/fpga), SET_ACC 2->0 pulse on both, write the point's fields on BOTH
# boards (a TX field only affects the far RX, an RX field only the own RX -> each point gives both directions),
# eyescan.py recal on both (TX/RX calib + DFE reset, TUNING_5G.md §3), health on both, ber_jtag_check 50, ber_mon 60 s cleared.
# Usage: lab16.sh <tag> <gsbit> <m2bit> <secs> "label|FIELD=V,FIELD=V" ...   (empty field list = baseline + recal)
F=/home/pi/fpga; T=/home/pi/ulx5m-serdes/tools; L=/home/pi/ulx5m-serdes/t5483/log16; mkdir -p $L
TAG=$1; GB=$2; MB=$3; S=$4; shift 4
echo "TASK-5483 $(date +%s) lab16 $TAG sweep (jelena)" > /home/pi/gs.owner
for st in "$@"; do
  IFS='|' read -r lab fl <<< "$st"; O=$L/${TAG}_$lab
  fpga-jtag m2 $F/$MB -r 2>&1 | tail -1 | grep -v -i done; fpga-jtag gs $F/$GB -r 2>&1 | tail -1 | grep -v -i done; sleep 3
  for b in m2 gs; do (cd $T; fpga-jtag $b run python3 eyescan.py set RX_CDR_SET_ACC_CONFIG=2 >/dev/null 2>&1; fpga-jtag $b run python3 eyescan.py set RX_CDR_SET_ACC_CONFIG=0 >/dev/null 2>&1); done
  if [ -n "$fl" ]; then for b in m2 gs; do (cd $T; fpga-jtag $b run python3 eyescan.py set ${fl//,/ } 2>&1 | grep -E "board=|Error" | tr '\n' ' '); done; echo; fi
  for b in m2 gs; do (cd $T; fpga-jtag $b run python3 eyescan.py recal 2>&1 | grep -E "board=|Error" | cut -c1-150); done; sleep 2
  for b in m2 gs; do (cd $T; fpga-jtag $b run python3 eyescan.py health -n 3 --interval 0.5 --label "$TAG $lab" --out "$O.health_$b.json" 2>&1 | grep -E "^HEALTH|Error" | cut -c1-160); done
  for b in m2 gs; do echo "JTAG $TAG $lab $b: $(cd $T; fpga-jtag $b run python3 ber_jtag_check.py --samples 50 2>&1 | tail -1 | sed 's/.*rx: //')"; done
  ( cd $T; python3 ber_mon.py run --secs $S --clear --json ) > ${O}_r1.json
  echo "== $TAG $lab $(date +%T) [$fl]: $( cd $T; python3 -c "import json,sys;sys.path.insert(0,'lab');import ab_table as A;d=json.load(open('${O}_r1.json'));print('gs->m2 %.2e  m2->gs %.2e' % (A.ber(d['gs_to_m2']), A.ber(d['m2_to_gs'])))" 2>&1 | tail -1)"
done
rm -f /home/pi/gs.owner; echo "LAB16 $TAG DONE $(date +%T)"
