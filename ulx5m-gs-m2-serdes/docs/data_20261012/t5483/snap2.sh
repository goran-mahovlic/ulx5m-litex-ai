#!/bin/bash
# TASK-5483 retry (uputa #305, 12.10. 18:00): step-1 snapshot of gs PLL at 2.5G (+m2), then gs alone at 0.3/1.25/5G
F=/home/pi/fpga; T=/home/pi/ulx5m-serdes/tools; L=/home/pi/ulx5m-serdes/t5483/log2; mkdir -p $L
echo "TASK-5483 $(date +%s) step1 retry (jelena)" > /home/pi/gs.owner
echo "snap2 $(date '+%F %T')"; vcgencmd get_throttled
fpga-jtag m2 $F/m2_2g5.bit -r 2>&1 | tail -1; fpga-jtag gs $F/gs_2g5.bit -r 2>&1 | tail -1; sleep 3
for b in m2 gs; do (cd $T; fpga-jtag $b run python3 eyescan.py set RX_CDR_SET_ACC_CONFIG=2 >/dev/null 2>&1; fpga-jtag $b run python3 eyescan.py set RX_CDR_SET_ACC_CONFIG=0 >/dev/null 2>&1); done; sleep 2
for b in m2 gs; do (cd $T; fpga-jtag $b run python3 eyescan.py health -n 3 --interval 0.5 --label "snap2 2g5" --out "$L/snap2_2g5.health_$b.json" 2>&1 | grep -E "^HEALTH|^  PLL|Error"); done
for b in m2 gs; do echo "JTAG 2g5 $b: $(cd $T; fpga-jtag $b run python3 ber_jtag_check.py --samples 50 2>&1 | tail -1)"; done
for x in "0g3 /home/pi/ulx5m-serdes/t5066/ber_gs_0g3_CFGRST.bit" "1g25 /home/pi/ulx5m-serdes/t5066/ber_gs_1g25_CFGRST.bit" "5g $F/gs_5g.bit"; do
  set -- $x; [ -f $2 ] || { echo "missing $2"; continue; }
  fpga-jtag gs $2 -r 2>&1 | tail -1; sleep 3
  echo "gs $1: $(cd $T; fpga-jtag gs run python3 eyescan.py get PLL_LOCKED PLL_CAP_FT PLL_CAP_STATE PLL_BISC_CO PLL_BISC_CP 2>&1 | tr '\n' ' ')"
done
rm -f /home/pi/gs.owner; echo "SNAP2 DONE $(date +%T)"
