#!/bin/bash
# TASK-5079 quick health after chain reseat: 0.3 G JTAG RX, then 2.5 G best pair health + 30 s ber_mon (ppm m2-gs)
cd /home/pi/ulx5m-serdes/t5066; T=/home/pi/ulx5m-serdes/tools; L=$PWD/log5079; mkdir -p $L
echo "== 0g3 $(date +%T)"
fpga-jtag m2 ber_m2_0g3_CFGRST.bit -r 2>&1 | tail -1; fpga-jtag gs ber_gs_0g3_CFGRST.bit -r 2>&1 | tail -1; sleep 3
for b in m2 gs; do echo "0g3 $b: $(fpga-jtag $b run python3 $T/ber_jtag_check.py --samples 200 2>&1 | tail -1)"; done
echo "== 2g5 $(date +%T)"
fpga-jtag m2 m2_e1_2g5p1_txneg_s2.bit -r 2>&1 | tail -1; fpga-jtag gs gs_sd_2g5p1_txneg_s7.bit -r 2>&1 | tail -1; sleep 3
for b in m2 gs; do fpga-jtag $b run python3 $T/eyescan.py health -n 3 --interval 0.5 --label h79 --out $L/h79_2g5_r1.health_$b.json 2>&1 | grep -E "^HEALTH|Error"; done
for b in m2 gs; do echo "2g5 $b: $(fpga-jtag $b run python3 $T/ber_jtag_check.py --samples 200 2>&1 | tail -1)"; done
( cd $T; python3 ber_mon.py run --secs 30 --clear --json ) > $L/h79_2g5_r1.json
cat $L/h79_2g5_r1.json
echo "H79 DONE $(date +%T)"
