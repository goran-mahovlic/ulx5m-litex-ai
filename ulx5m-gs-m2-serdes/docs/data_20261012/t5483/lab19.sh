#!/bin/bash
# TASK-5487 uputa #308 step 2: load-to-load scatter at 2.5 G, baseline bits, NO sweep and NO recal (standard procedure:
# load m2 then gs -r, SET_ACC 2->0 on both). Right after SET_ACC: health --raw on both (cal/EQA/AFE_OFFSET/CDR FREQ+PHASE_ACC
# 0x0B-0x0D/PLL_CAP_FT), then ber_mon sparse 240 s (UART dropouts are logged, the series continues), then health --raw again
# (end of window) and ber_jtag_check 200 on both. Usage: lab19.sh [loads=10]
F=/home/pi/fpga; T=/home/pi/ulx5m-serdes/tools; L=/home/pi/ulx5m-serdes/t5483/log19; mkdir -p $L; NL=${1:-10}; SECS=${SECS:-240}
echo "TASK-5487 $(date +%s) lab19 scatter (jelena)" > /home/pi/gs.owner
for r in $(seq 1 $NL); do
  O=$L/r$r; echo "-- r$r $(date +%T) $(vcgencmd get_throttled)"
  fpga-jtag m2 $F/m2_2g5.bit -r 2>&1 | tail -1 | grep -v -i done; fpga-jtag gs $F/gs_2g5.bit -r 2>&1 | tail -1 | grep -v -i done; sleep 3
  for b in m2 gs; do (cd $T; fpga-jtag $b run python3 eyescan.py set RX_CDR_SET_ACC_CONFIG=2 >/dev/null 2>&1; fpga-jtag $b run python3 eyescan.py set RX_CDR_SET_ACC_CONFIG=0 >/dev/null 2>&1); done
  for b in m2 gs; do (cd $T; fpga-jtag $b run python3 eyescan.py health --raw -n 5 --interval 0.2 --label "r$r start" --out "$O.start_$b.json" 2>&1 | grep -E "^HEALTH|RAW|Error" | cut -c1-200); done
  ( cd $T; timeout $((SECS+340)) python3 ber_mon.py sparse --secs $SECS --json > ${O}_ber.json 2>&1 )
  for b in m2 gs; do (cd $T; fpga-jtag $b run python3 eyescan.py health --raw -n 5 --interval 0.2 --label "r$r end" --out "$O.end_$b.json" 2>&1 | grep -E "^HEALTH|Error" | cut -c1-160); done
  for b in m2 gs; do echo "JTAG r$r $b: $(cd $T; fpga-jtag $b run python3 ber_jtag_check.py --samples 200 2>&1 | tail -1 | sed 's/.*rx: /rx: /')"; done
  echo "== r$r $(date +%T): $( cd $T; python3 -c "
import json,sys;sys.path.insert(0,'lab');import ab_table as A;d=json.load(open('${O}_ber.json'))
print('UART gs->m2 %.2e  m2->gs %.2e  fabric_s %s' % (A.ber(d['gs_to_m2']), A.ber(d['m2_to_gs']), d.get('fabric_secs')))" 2>/dev/null || echo 'UART NOUART')"
done
rm -f /home/pi/gs.owner; echo "LAB19 DONE $(date +%T)"
