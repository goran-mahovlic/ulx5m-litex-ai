#!/bin/bash
# TASK-5487 lab18 = lab17 + per-board fields + optional serialized UART + JTAG retry.
# Point spec: "label|FIELD=V,gs:FIELD=V,m2:FIELD=V"  (no prefix = both boards; gs:/m2: = that board only).
# TX field on a board -> its own TX (far RX direction); RX field -> its own RX. gs TX = gs->m2, m2 TX = m2->gs.
# SER=1 (env): JTAG checks first, then the ber_mon sparse window with no JTAG traffic (else in parallel as lab17).
# SECS (env, default 60): ber_mon sparse window.  Usage: lab18.sh <tag> <gsbit> <m2bit> <N> "spec" ...
F=/home/pi/fpga; T=/home/pi/ulx5m-serdes/tools; L=/home/pi/ulx5m-serdes/t5483/log18; mkdir -p $L
TAG=$1; GB=$2; MB=$3; N=$4; shift 4; SECS=${SECS:-60}
echo "TASK-5487 $(date +%s) lab18 $TAG sweep (jelena)" > /home/pi/gs.owner
jt() { local b=$1 o=$2; for t in 1 2; do (cd $T; fpga-jtag $b run python3 ber_jtag_check.py --samples $N 2>&1 | tail -1 > $o); grep -q "rx:" $o && return; done; }
for st in "$@"; do
  IFS='|' read -r lab fl <<< "$st"; O=$L/${TAG}_$lab; fgs=""; fm2=""
  for f in ${fl//,/ }; do case $f in gs:*) fgs="$fgs ${f#gs:}";; m2:*) fm2="$fm2 ${f#m2:}";; *) fgs="$fgs $f"; fm2="$fm2 $f";; esac; done
  fpga-jtag m2 $F/$MB -r 2>&1 | tail -1 | grep -v -i done; fpga-jtag gs $F/$GB -r 2>&1 | tail -1 | grep -v -i done; sleep 3
  for b in m2 gs; do (cd $T; fpga-jtag $b run python3 eyescan.py set RX_CDR_SET_ACC_CONFIG=2 >/dev/null 2>&1; fpga-jtag $b run python3 eyescan.py set RX_CDR_SET_ACC_CONFIG=0 >/dev/null 2>&1); done
  [ -n "$fm2" ] && (cd $T; fpga-jtag m2 run python3 eyescan.py set $fm2 2>&1 | grep -E "board=|Error" | tr '\n' ' ')
  [ -n "$fgs" ] && (cd $T; fpga-jtag gs run python3 eyescan.py set $fgs 2>&1 | grep -E "board=|Error" | tr '\n' ' '); [ -n "$fl" ] && echo
  for b in m2 gs; do (cd $T; fpga-jtag $b run python3 eyescan.py recal 2>&1 | grep -E "board=|Error" | cut -c1-150); done; sleep 2
  for b in m2 gs; do (cd $T; fpga-jtag $b run python3 eyescan.py health -n 3 --interval 0.5 --label "$TAG $lab" --out "$O.health_$b.json" 2>&1 | grep -E "^HEALTH|Error" | cut -c1-160); done
  if [ "${SER:-0}" = 1 ]; then
    for b in m2 gs; do jt $b $O.jtag_$b.txt; done
    ( cd $T; timeout $((SECS+340)) python3 ber_mon.py sparse --secs $SECS --json > ${O}_r1.json 2>&1 )
  else
    ( cd $T; timeout $((SECS+340)) python3 ber_mon.py sparse --secs $SECS --json > ${O}_r1.json 2>&1 ) &
    for b in m2 gs; do jt $b $O.jtag_$b.txt; done; wait
  fi
  for b in m2 gs; do echo "JTAG $TAG $lab $b: $(sed 's/.*CDR=/CDR=/; s/LOOPBACK_SEL.*rx: /rx: /' $O.jtag_$b.txt)"; done
  echo "== $TAG $lab $(date +%T) [$fl]: $( cd $T; python3 -c "
import json,sys;sys.path.insert(0,'lab');import ab_table as A;d=json.load(open('${O}_r1.json'))
print('UART gs->m2 %.2e  m2->gs %.2e  fabric_s %s m2short %s' % (A.ber(d['gs_to_m2']), A.ber(d['m2_to_gs']), d.get('fabric_secs'), d['gs_to_m2'].get('words_short')))" 2>/dev/null || echo 'UART NOUART')"
done
rm -f /home/pi/gs.owner; echo "LAB18 $TAG DONE $(date +%T)"
