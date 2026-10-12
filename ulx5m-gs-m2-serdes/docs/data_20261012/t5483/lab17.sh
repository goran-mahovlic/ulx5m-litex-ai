#!/bin/bash
# TASK-5483 lab17 (12.10.2026 ~18:40, upute #305/#306): search sweep after the supply-filter rework, JTAG metric.
# Per point: load m2 then gs (-r, CFGRST bits /home/pi/fpga), SET_ACC 2->0 pulse on both, write the point's fields on BOTH
# boards (TX field -> far RX only, RX field -> own RX only => each point gives both directions), eyescan.py recal on both,
# health on both, then ber_jtag_check N samples on m2, then on gs (fpga-jtag holds one global JTAG lock) (primary metric: PEER share of raw RX words
# + CDR/EQA lock) and, in parallel with that, one ber_mon 'sparse' window (secondary: fabric counters read once at the end; UART may be silent ->
# 'NOUART', the point still counts). Eye scan is not used: its counters read 0 (VERIFY_RATES §9.6, E7).
# Usage: lab17.sh <tag> <gsbit> <m2bit> <N> "label|FIELD=V,FIELD=V" ...   (empty field list = baseline + recal)
F=/home/pi/fpga; T=/home/pi/ulx5m-serdes/tools; L=/home/pi/ulx5m-serdes/t5483/log17; mkdir -p $L
TAG=$1; GB=$2; MB=$3; N=$4; shift 4
echo "TASK-5483 $(date +%s) lab17 $TAG sweep (jelena)" > /home/pi/gs.owner
for st in "$@"; do
  IFS='|' read -r lab fl <<< "$st"; O=$L/${TAG}_$lab
  fpga-jtag m2 $F/$MB -r 2>&1 | tail -1 | grep -v -i done; fpga-jtag gs $F/$GB -r 2>&1 | tail -1 | grep -v -i done; sleep 3
  for b in m2 gs; do (cd $T; fpga-jtag $b run python3 eyescan.py set RX_CDR_SET_ACC_CONFIG=2 >/dev/null 2>&1; fpga-jtag $b run python3 eyescan.py set RX_CDR_SET_ACC_CONFIG=0 >/dev/null 2>&1); done
  if [ -n "$fl" ]; then for b in m2 gs; do (cd $T; fpga-jtag $b run python3 eyescan.py set ${fl//,/ } 2>&1 | grep -E "board=|Error" | tr '\n' ' '); done; echo; fi
  for b in m2 gs; do (cd $T; fpga-jtag $b run python3 eyescan.py recal 2>&1 | grep -E "board=|Error" | cut -c1-150); done; sleep 2
  for b in m2 gs; do (cd $T; fpga-jtag $b run python3 eyescan.py health -n 3 --interval 0.5 --label "$TAG $lab" --out "$O.health_$b.json" 2>&1 | grep -E "^HEALTH|Error" | cut -c1-160); done
  ( cd $T; timeout 400 python3 ber_mon.py sparse --secs 60 --json > ${O}_r1.json 2>&1 ) &
  for b in m2 gs; do ( cd $T; fpga-jtag $b run python3 ber_jtag_check.py --samples $N 2>&1 | tail -1 > $O.jtag_$b.txt ); done
  wait
  for b in m2 gs; do echo "JTAG $TAG $lab $b: $(sed 's/.*CDR=/CDR=/; s/LOOPBACK_SEL.*rx: /rx: /' $O.jtag_$b.txt)"; done
  echo "== $TAG $lab $(date +%T) [$fl]: $( cd $T; python3 -c "
import json,sys;sys.path.insert(0,'lab');import ab_table as A;d=json.load(open('${O}_r1.json'))
print('UART gs->m2 %.2e  m2->gs %.2e  fabric_s %s m2short %s' % (A.ber(d['gs_to_m2']), A.ber(d['m2_to_gs']), d.get('fabric_secs'), d['gs_to_m2'].get('words_short')))" 2>/dev/null || echo 'UART NOUART')"
done
rm -f /home/pi/gs.owner; echo "LAB17 $TAG DONE $(date +%T)"
