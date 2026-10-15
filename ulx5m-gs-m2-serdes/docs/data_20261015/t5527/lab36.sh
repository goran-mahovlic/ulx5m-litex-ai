#!/bin/bash
# TASK-5527 lab36 (uputa #338, EYE_MEAS_UZROK.md §4): P1 do W/C strobes execute (TX_PRBS_FORCE_ERR on gs, RX_PRBS_CNT_RESET on m2),
# P2 does N TCK in Run-Test/Idle after the write make them execute (cnt_reset, eye). PRBS-15 gs TX -> m2 RX. Standard pair reloaded at the end.
F=/home/pi/fpga; T=/home/pi/ulx5m-serdes/tools
echo "TASK-5527 $(date +%s) lab36 P1/P2 strobes (jelena)" > /home/pi/gs.owner
P() { (cd $T; fpga-jtag $1 run python3 lab/strobe_probe.py "${@:2}" 2>&1 | grep -E "^(STATE|FORCE|CNT_RESET|EYE)|Error|Trace" | cut -c1-260); }
echo "-- lab36 $(date +%T) $(vcgencmd get_throttled)"
P gs tx_prbs_on; P m2 rx_prbs_on; sleep 1
P m2 cnt; sleep 5; P m2 cnt                     # natural PRBS error rate over ~5 s + JTAG time
P m2 cnt; P gs force 200; P m2 cnt              # P1a: +200 expected if FORCE_ERR executes
P m2 cnt_reset 0                                # P1b: ERR_CNT -> 0 expected if CNT_RESET executes
P m2 cnt_reset 100000                           # P2: same + 100k TCK in RTI
P gs force 0; P m2 cnt; P gs force 20; P m2 cnt # repeat P1a small
P m2 eye 0; P m2 eye 100000; P m2 eye 1000000   # P2: eye engine with 0 / 1e5 / 1e6 TCK in RTI
P m2 rx_prbs_off; P gs tx_prbs_off
echo "-- reload standard pair $(date +%T)"
fpga-jtag m2 $F/m2_2g5.bit -r 2>&1 | tail -1; fpga-jtag gs $F/gs_2g5.bit -r 2>&1 | tail -1; sleep 3
for b in m2 gs; do (cd $T; fpga-jtag $b run python3 eyescan.py set RX_CDR_SET_ACC_CONFIG=2 >/dev/null 2>&1; fpga-jtag $b run python3 eyescan.py set RX_CDR_SET_ACC_CONFIG=0 >/dev/null 2>&1); done
for b in m2 gs; do echo "JTAG end $b: $(cd $T; fpga-jtag $b run python3 ber_jtag_check.py --samples 200 2>&1 | tail -1 | sed 's/.*rx: /rx: /')"; done
rm -f /home/pi/gs.owner; echo "LAB36 DONE $(date +%T)"
