#!/bin/bash
# TASK-5482 lab15 (12.10.2026 ~16:55, Goran uputa #301): retest from /home/pi/fpga after both boards were refreshed and the
# gs UART is back (608 B / 4 s right after loading gs_2g5.bit). = lab12/lab13 protocol + lab14 SET_ACC pulse:
# per load m2 then gs (-r, CFGRST bits), RX_CDR_SET_ACC_CONFIG 2->0 on both (LOCAL_REFCLK_M2.md 4C), health on both,
# ber_jtag_check 50 on both, ber_mon 300 s with cleared counters. 2.5 G x3, then 5 G P2/P3 interleaved x3 (all 300 s).
F=/home/pi/fpga; L=/home/pi/ulx5m-serdes/t5482/log15; T=/home/pi/ulx5m-serdes/tools; mkdir -p $L
echo "TASK-5482 $(date +%s) lab15 BER retest (jelena)" > /home/pi/gs.owner
sha256sum $F/*.bit
run() { # label gsbit m2bit k
  O=$L/$1_r$4
  fpga-jtag m2 $F/$3 -r 2>&1 | tail -1 | grep -v -i done; fpga-jtag gs $F/$2 -r 2>&1 | tail -1 | grep -v -i done; sleep 3
  for b in m2 gs; do (cd $T; fpga-jtag $b run python3 eyescan.py set RX_CDR_SET_ACC_CONFIG=2 >/dev/null 2>&1; fpga-jtag $b run python3 eyescan.py set RX_CDR_SET_ACC_CONFIG=0 >/dev/null 2>&1); done; sleep 2
  for b in m2 gs; do (cd $T; fpga-jtag $b run python3 eyescan.py health -n 3 --interval 0.5 --label "$1 r$4" --out "$O.health_$b.json" 2>&1 | grep -E "^HEALTH|Error"); done
  for b in m2 gs; do echo "JTAG $1 r$4 $b: $(cd $T; fpga-jtag $b run python3 ber_jtag_check.py --samples 50 2>&1 | tail -1)"; done
  ( cd $T; python3 ber_mon.py run --secs 300 --clear --json ) > $O.json
  echo "== $1 r$4 $(date +%T): $( cd $T; python3 -c "import json,sys;sys.path.insert(0,'lab');import ab_table as A;d=json.load(open('$O.json'));print('gs->m2 %.2e  m2->gs %.2e' % (A.ber(d['gs_to_m2']), A.ber(d['m2_to_gs'])))" 2>&1 | tail -1)"
}
for k in 1 2 3; do run t15_2g5 gs_2g5.bit m2_2g5.bit $k; done
for k in 1 2 3; do
  run t15_p2 gs_5g.bit m2_5g.bit $k
  run t15_p3 gs_5g_p3.bit m2_5g_p3.bit $k
done
python3 $T/lab/ab_table.py --runs --rank $L/t15_*_r*.json
python3 $T/lab/health_table.py $L/t15_*_r*.health_*.json
rm -f /home/pi/gs.owner; echo "LAB15 DONE $(date +%T)"
