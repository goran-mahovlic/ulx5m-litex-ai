#!/bin/bash
# TASK-5080 quick health after 2.2 uF on M2 C127/C128 (= h79.sh of TASK-5079, labels only + lease): 0.3 G JTAG RX, then 2.5 G best pair health + 30 s ber_mon (ppm m2-gs)
cd /home/pi/ulx5m-serdes/t5066; T=/home/pi/ulx5m-serdes/tools; L=$PWD/log5080; mkdir -p $L
echo "TASK-5080 $(date +%s) SerDes health after 2.2uF on M2 (jelena)" > /home/pi/gs.owner
echo "== 0g3 $(date +%T)"
fpga-jtag m2 ber_m2_0g3_CFGRST.bit -r 2>&1 | tail -1; fpga-jtag gs ber_gs_0g3_CFGRST.bit -r 2>&1 | tail -1; sleep 3
for b in m2 gs; do echo "0g3 $b: $(fpga-jtag $b run python3 $T/ber_jtag_check.py --samples 200 2>&1 | tail -1)"; done
echo "== 2g5 $(date +%T)"
fpga-jtag m2 m2_e1_2g5p1_txneg_s2.bit -r 2>&1 | tail -1; fpga-jtag gs gs_sd_2g5p1_txneg_s7.bit -r 2>&1 | tail -1; sleep 3
for b in m2 gs; do fpga-jtag $b run python3 $T/eyescan.py health -n 3 --interval 0.5 --label h80 --out $L/h80_2g5_r1.health_$b.json 2>&1 | grep -E "^HEALTH|Error"; done
for b in m2 gs; do echo "2g5 $b: $(fpga-jtag $b run python3 $T/ber_jtag_check.py --samples 200 2>&1 | tail -1)"; done
( cd $T; python3 ber_mon.py run --secs 30 --clear --json ) > $L/h80_2g5_r1.json
cat $L/h80_2g5_r1.json
echo "H80 DONE $(date +%T)"
