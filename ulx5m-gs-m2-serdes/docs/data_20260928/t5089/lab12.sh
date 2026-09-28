#!/bin/bash
# TASK-5089 lab12: M2 refclk INTERNAL termination A/B with separate refclks (X2 on M2, C136/C137 off). Goran 28.09. 12:45:
# "treba probati internu terminaciju, vanjska nije opcija". Best pair, CKI 0 (lab11: CKI 1 not better).
# rterm1 = as loaded (PLL_REF_RTERM=1, = lab11 cki0); rterm0 = PLL_REF_RTERM=0 written on m2 over JTAG after the load
# (PLL stays locked, checked 12:47). Every load = fresh m2 then gs; 3 rounds interleaved x 300 s.
cd /home/pi/ulx5m-serdes/t5089; L=$PWD/log; T=/home/pi/ulx5m-serdes/tools
echo "TASK-5089 $(date +%s) refclk RTERM A/B (regoc)" > /home/pi/gs.owner
run() { # label field k
  O=$L/$1_r$3
  fpga-jtag m2 m2_e1_2g5p1_txneg_s2.bit -r 2>&1 | tail -1 | grep -v -i done; fpga-jtag gs gs_sd_2g5p1_txneg_s7.bit -r 2>&1 | tail -1 | grep -v -i done; sleep 3
  [ -n "$2" ] && (cd $T; fpga-jtag m2 run python3 eyescan.py set $2 2>&1 | grep -E "set|Error"); sleep 2
  (cd $T; fpga-jtag m2 run python3 eyescan.py get PLL_REF_RTERM 2>&1 | tail -1)
  for b in m2 gs; do (cd $T; fpga-jtag $b run python3 eyescan.py health -n 3 --interval 0.5 --label "$1 r$3" --out "$O.health_$b.json" 2>&1 | grep -E "^HEALTH|Error"); done
  ( cd $T; python3 ber_mon.py run --secs 300 --clear --json ) > $O.json
  echo "== $1 r$3 $(date +%T): $( cd $T; python3 -c "import json,sys;sys.path.insert(0,'lab');import ab_table as A;d=json.load(open('$O.json'));print('gs->m2 %.2e  m2->gs %.2e' % (A.ber(d['gs_to_m2']), A.ber(d['m2_to_gs'])))" )"
}
for k in 1 2 3; do
  echo "== round $k $(date +%T)"
  run t89_rterm0 PLL_REF_RTERM=0 $k
  run t89_rterm1 "" $k
done
python3 $T/lab/ab_table.py --runs --rank $L/t89_rterm*_r*.json $L/t89_cki0_r*.json
python3 $T/lab/health_table.py $L/t89_rterm*_r*.health_*.json
rm -f /home/pi/gs.owner; echo "LAB12 DONE $(date +%T)"
