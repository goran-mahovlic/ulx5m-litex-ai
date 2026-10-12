#!/bin/bash
# TASK-5487 (dorada 5483) step 0+1: boards were power-cycled (Goran 19:31). Load m2 then gs 2.5 G (-r), SET_ACC 2->0, health on both,
# then A/B UART: (A) 3 x 60 s UART alone, no JTAG; (B) 3 x 60 s UART while JTAG reads run back to back as in lab17. Bytes/lines per window.
F=/home/pi/fpga; T=/home/pi/ulx5m-serdes/tools; P=/home/pi/ulx5m-serdes/t5483/uartprobe.py; L=/home/pi/ulx5m-serdes/t5483/log18; mkdir -p $L
echo "TASK-5487 $(date +%s) uart A/B 2 (jelena)" > /home/pi/gs.owner
vcgencmd get_throttled
fpga-jtag m2 $F/m2_2g5.bit -r 2>&1 | tail -1; fpga-jtag gs $F/gs_2g5.bit -r 2>&1 | tail -1; sleep 3
for b in m2 gs; do (cd $T; fpga-jtag $b run python3 eyescan.py set RX_CDR_SET_ACC_CONFIG=2 >/dev/null 2>&1; fpga-jtag $b run python3 eyescan.py set RX_CDR_SET_ACC_CONFIG=0 >/dev/null 2>&1); done; sleep 2
for b in m2 gs; do (cd $T; fpga-jtag $b run python3 eyescan.py health -n 3 --interval 0.5 --label "ab2 2g5" --out "$L/ab2.health_$b.json" 2>&1 | grep -E "^HEALTH|^  PLL|Error"); done
for b in m2 gs; do echo "JTAG 2g5 $b: $(cd $T; fpga-jtag $b run python3 ber_jtag_check.py --samples 50 2>&1 | tail -1)"; done
for k in 1 2 3; do echo "A$k $(date +%T) no JTAG: $(python3 $P 60 2>&1 | tail -1)"; done
for k in 1 2 3; do
  ( t0=$(date +%s); while [ $(( $(date +%s) - t0 )) -lt 58 ]; do
      (cd $T; fpga-jtag gs run python3 ber_jtag_check.py --samples 20 >/dev/null 2>&1; fpga-jtag m2 run python3 ber_jtag_check.py --samples 20 >/dev/null 2>&1; fpga-jtag gs run python3 eyescan.py health -n 1 >/dev/null 2>&1)
    done ) &
  echo "B$k $(date +%T) with JTAG: $(python3 $P 60 2>&1 | tail -1)"; wait
done
vcgencmd get_throttled
rm -f /home/pi/gs.owner; echo "UART_AB2 DONE $(date +%T)"
