#!/bin/bash
# REGOC 15.10. ~18:51: brzi test nakon Goranove provjere C143/C144 (standardni par 2,5G, postupak lab22)
F=/home/pi/fpga; T=/home/pi/ulx5m-serdes/tools; L=/home/pi/ulx5m-serdes/t5527/q30
echo "TASK-5527 $(date +%s) quick30 (regoc)" > /home/pi/gs.owner
echo "-- quick30 $(date +%T) $(vcgencmd get_throttled)"
fpga-jtag m2 $F/m2_2g5.bit -r 2>&1 | tail -1; fpga-jtag gs $F/gs_2g5.bit -r 2>&1 | tail -1; sleep 3
for b in m2 gs; do (cd $T; fpga-jtag $b run python3 eyescan.py set RX_CDR_SET_ACC_CONFIG=2 >/dev/null 2>&1; fpga-jtag $b run python3 eyescan.py set RX_CDR_SET_ACC_CONFIG=0 >/dev/null 2>&1); done
for b in m2 gs; do (cd $T; fpga-jtag $b run python3 eyescan.py health --raw -n 3 --interval 0.2 --label q30 --out $L/start_$b.json 2>&1 | grep -E "^HEALTH" | cut -c1-200); done
for b in m2 gs; do (cd $T; fpga-jtag $b run python3 eyescan.py capture -n 3 2>&1 | grep -E "CAPSTAT|op " | tail -1 | cut -c1-160); done
for b in m2 gs; do echo "JTAG $b: $(cd $T; fpga-jtag $b run python3 ber_jtag_check.py --samples 200 2>&1 | tail -1 | sed "s/.*rx: /rx: /")"; done
(cd $T; timeout 400 python3 lab/ber_long.py --secs 60 --every 20 --out $L/ber60.jsonl 2>&1 | tail -1)
rm -f /home/pi/gs.owner; echo "QUICK30 DONE $(date +%T)"
