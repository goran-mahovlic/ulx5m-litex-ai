#!/bin/bash
# TASK-5487 uputa #308 step 3 (after lab19): eye-counter hypotheses on m2 with the 2.5 G baseline pair loaded.
# Order (Goran): H7 -> H2 -> H1 -> H3 -> H4 (+ H8 from TASK-5488 §6.3), then the bathtub feasibility test (phase override).
F=/home/pi/fpga; T=/home/pi/ulx5m-serdes/tools; H=/home/pi/ulx5m-serdes/t5483
until grep -q "LAB19 DONE" $H/lab19.out; do sleep 20; done
echo "TASK-5487 $(date +%s) eye20 (jelena)" > /home/pi/gs.owner
fpga-jtag m2 $F/m2_2g5.bit -r 2>&1 | tail -1; fpga-jtag gs $F/gs_2g5.bit -r 2>&1 | tail -1; sleep 3
for b in m2 gs; do (cd $T; fpga-jtag $b run python3 eyescan.py set RX_CDR_SET_ACC_CONFIG=2 >/dev/null 2>&1; fpga-jtag $b run python3 eyescan.py set RX_CDR_SET_ACC_CONFIG=0 >/dev/null 2>&1); done
cd $T
echo "### eyeprobe H7/H2/H3 (link untouched)"; timeout 300 fpga-jtag m2 run python3 eyeprobe.py --skip h1 --out $H/probe_m2_noh1.json 2>&1
echo "### eyeprobe H1 (near-end PMA loopback + PRBS-7)"; timeout 300 fpga-jtag m2 run python3 eyeprobe.py --skip h7,h2,h3 --out $H/probe_m2_h1.json 2>&1
fpga-jtag m2 run python3 eyescan.py health -n 2 2>&1 | grep -E "^HEALTH"
for t in h7 h2 h3 h4 h8; do echo "### eye_tests $t"; timeout 300 fpga-jtag m2 run python3 $H/eye_tests.py $t 2>&1; done
fpga-jtag m2 run python3 eyescan.py recal 2>&1 | grep board=; fpga-jtag m2 run python3 eyescan.py health -n 2 2>&1 | grep -E "^HEALTH"
echo "### eye_tests phase (bathtub feasibility)"; timeout 300 fpga-jtag m2 run python3 $H/eye_tests.py phase 2>&1
fpga-jtag m2 run python3 eyescan.py recal 2>&1 | grep board=; fpga-jtag m2 run python3 eyescan.py health -n 2 2>&1 | grep -E "^HEALTH"
echo "JTAG m2: $(fpga-jtag m2 run python3 ber_jtag_check.py --samples 50 2>&1 | tail -1 | sed 's/.*rx: /rx: /')"
rm -f /home/pi/gs.owner; echo "EYE20 DONE $(date +%T)"
