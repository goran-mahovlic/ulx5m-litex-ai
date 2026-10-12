#!/bin/bash
# TASK-5487 uputa #308 step 3b: (1) phase-override feasibility again on a FRESH load (eye20's run followed H8, which left 0x2B=0x100);
# (2) vertical bathtub on gs RX (m2->gs): RX_AFE_OFFSET=v with RX_EN_EQA_EXT_VALUE[3]=1 (0x06[11]), 30 s ber_mon sparse per point.
# Also tests the lab19 hint that a low gs RX_OFFSET (2) goes with the bad m2->gs loads.
F=/home/pi/fpga; T=/home/pi/ulx5m-serdes/tools; H=/home/pi/ulx5m-serdes/t5483; L=$H/log21; mkdir -p $L
echo "TASK-5487 $(date +%s) eye21 (jelena)" > /home/pi/gs.owner
load() { fpga-jtag m2 $F/m2_2g5.bit -r 2>&1 | tail -1 | grep -v -i done; fpga-jtag gs $F/gs_2g5.bit -r 2>&1 | tail -1 | grep -v -i done; sleep 3
  for b in m2 gs; do (cd $T; fpga-jtag $b run python3 eyescan.py set RX_CDR_SET_ACC_CONFIG=2 >/dev/null 2>&1; fpga-jtag $b run python3 eyescan.py set RX_CDR_SET_ACC_CONFIG=0 >/dev/null 2>&1); done; }
ber() { (cd $T; timeout 400 python3 ber_mon.py sparse --secs ${1:-30} --json > $2 2>&1; python3 -c "
import json,sys;sys.path.insert(0,'lab');import ab_table as A;d=json.load(open('$2'))
print('gs->m2 %.2e m2->gs %.2e fabric_s %s' % (A.ber(d['gs_to_m2']), A.ber(d['m2_to_gs']), d.get('fabric_secs')))" 2>/dev/null || echo NOUART); }
cd $T
echo "### phase on m2 (fresh load)"; load
fpga-jtag m2 run python3 eyescan.py get RX_CDR_PHASE_ACC_VAL RX_CDR_LOCKED 2>&1 | tail -1
timeout 300 fpga-jtag m2 run python3 $H/eye_tests.py phase 2>&1
echo "### vertical bathtub gs RX (fresh load)"; load
echo "gs before: $(fpga-jtag gs run python3 eyescan.py get RX_OFFSET RX_AFE_OFFSET RX_TH_MON 'RX_EN_EQA_EXT_VALUE[3]' 2>&1 | tail -1)"
echo "base (no override): $(ber 30 $L/base0.json)"
for v in 0 2 4 6 7 8 9 10 12 14 16 18 20 24 28 31; do
  r=$(fpga-jtag gs run python3 eyescan.py set RX_AFE_OFFSET=$v 'RX_EN_EQA_EXT_VALUE[3]=1' 2>&1 | tail -1); sleep 0.5
  st=$(fpga-jtag gs run python3 eyescan.py get RX_OFFSET RX_CDR_LOCKED RX_EQA_LOCKED 2>&1 | tail -1 | sed 's/board=gs //')
  echo "AFE_OFFSET=$v [$st] $(ber 30 $L/afe$v.json)"
done
fpga-jtag gs run python3 eyescan.py set 'RX_EN_EQA_EXT_VALUE[3]=0' RX_AFE_OFFSET=8 2>&1 | tail -1
echo "base (override off): $(ber 30 $L/base1.json)"
rm -f /home/pi/gs.owner; echo "EYE21 DONE $(date +%T)"
