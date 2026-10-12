#!/bin/bash
# TASK-5483 uputa #307: is the gs UART dropout caused by JTAG traffic on the same DirtyJTAG (E660583883501E2C)?
# After one load (m2 then gs 2.5 G), (a) 3 x 60 s UART alone, no JTAG at all; (b) 3 x 60 s UART while JTAG reads run
# back to back as in lab17 (ber_jtag_check on m2 and gs, eyescan health on gs). Bytes/lines per window.
F=/home/pi/fpga; T=/home/pi/ulx5m-serdes/tools; P=/home/pi/ulx5m-serdes/t5483/uartprobe.py
echo "TASK-5483 $(date +%s) uart A/B (jelena)" > /home/pi/gs.owner
fpga-jtag m2 $F/m2_2g5.bit -r 2>&1 | tail -1; fpga-jtag gs $F/gs_2g5.bit -r 2>&1 | tail -1; sleep 3
for k in 1 2 3; do echo "A$k $(date +%T) no JTAG: $(python3 $P 60)"; done
for k in 1 2 3; do
  ( t0=$(date +%s); while [ $(( $(date +%s) - t0 )) -lt 58 ]; do
      (cd $T; fpga-jtag gs run python3 ber_jtag_check.py --samples 20 >/dev/null 2>&1; fpga-jtag m2 run python3 ber_jtag_check.py --samples 20 >/dev/null 2>&1; fpga-jtag gs run python3 eyescan.py health -n 1 >/dev/null 2>&1)
    done ) &
  echo "B$k $(date +%T) with JTAG: $(python3 $P 60)"; wait
done
rm -f /home/pi/gs.owner; echo "UART_AB DONE $(date +%T)"
