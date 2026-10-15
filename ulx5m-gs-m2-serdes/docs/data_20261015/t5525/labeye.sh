#!/bin/bash
# TASK-5525 uputa #333: Patrick's serdes_lb.v (eye_pu2g5_s1.bit, 2.5 G, PRBS-15 both ways, TESTMODE 1) on both boards.
# Does RX_EYE_MEAS_EN clear and do the counters count? Then diagnose; if counting, full 64 x 31 eye on both receivers.
B=/home/pi/ulx5m-serdes/t5525/eye_pu2g5_s1.bit; T=/home/pi/ulx5m-serdes/tools; L=/home/pi/ulx5m-serdes/t5525/logeye; mkdir -p $L
echo "TASK-5525 $(date +%s) labeye (jelena)" > /home/pi/gs.owner
J() { (cd $T; fpga-jtag $1 run python3 eyescan.py "${@:2}" 2>&1 | grep -v "Found 1 device"); }
echo "-- labeye $(date +%T) $(vcgencmd get_throttled) $(sha256sum $B | cut -c1-16)"
fpga-jtag m2 $B -r 2>&1 | tail -1; fpga-jtag gs $B -r 2>&1 | tail -1; sleep 3
for b in m2 gs; do J $b set RX_CDR_SET_ACC_CONFIG=2 >/dev/null; J $b set RX_CDR_SET_ACC_CONFIG=0 >/dev/null; done
for b in m2 gs; do J $b get PLL_LOCKED RX_CDR_LOCKED RX_EQA_LOCKED RX_PRBS_LOCKED RX_PRBS_ERR_CNT SERDES_TESTMODE RX_EQA_LOCK_CFG RX_RESET_DONE | tail -1; done
for b in m2 gs; do echo "PROBE $b"; (cd $T; fpga-jtag $b run python3 /home/pi/ulx5m-serdes/t5525/probe_meas.py 2>&1 | grep -v "Found 1"); done
for b in m2 gs; do J $b diagnose --rate 2.5e9 --label pu --out $L/diag_$b.json | grep -E "^DIAG"; done
if grep -q "counters respond to threshold" $L/diag_m2.json $L/diag_gs.json 2>/dev/null && ! grep -q "stuck at 1" $L/diag_gs.json; then
  for b in gs m2; do J $b eye --rate 2.5e9 --label "pu ${b} RX" --out $L/eye_$b.json | grep -E "^EYE|points" | tail -4; done
fi
# phase 2: our ber bits with only RX_EYE_MEAS_CFG = {12'h800,3'b0} added (EYE_CFG 16384; LOCK_CFG is already C in PROFILE 1)
echo "-- minimal $(date +%T)"
fpga-jtag m2 /home/pi/ulx5m-serdes/t5525/m2_2g5p1_txneg_eyecfg_s2.bit -r 2>&1 | tail -1; fpga-jtag gs /home/pi/ulx5m-serdes/t5525/gs_2g5p1_txneg_eyecfg_s7.bit -r 2>&1 | tail -1; sleep 3
for b in m2 gs; do J $b set RX_CDR_SET_ACC_CONFIG=2 >/dev/null; J $b set RX_CDR_SET_ACC_CONFIG=0 >/dev/null; done
for b in m2 gs; do echo "PROBE min $b"; (cd $T; fpga-jtag $b run python3 /home/pi/ulx5m-serdes/t5525/probe_meas.py 2>&1 | grep -v "Found 1"); done
for b in m2 gs; do J $b diagnose --rate 2.5e9 --label min --out $L/diag_min_$b.json | grep -E "^DIAG"; done
# back to the standard pair
fpga-jtag m2 /home/pi/fpga/m2_2g5.bit -r 2>&1 | tail -1; fpga-jtag gs /home/pi/fpga/gs_2g5.bit -r 2>&1 | tail -1; sleep 3
for b in m2 gs; do J $b set RX_CDR_SET_ACC_CONFIG=2 >/dev/null; J $b set RX_CDR_SET_ACC_CONFIG=0 >/dev/null; done
for b in m2 gs; do echo "JTAG std $b: $(cd $T; fpga-jtag $b run python3 ber_jtag_check.py --samples 200 2>&1 | tail -1 | sed 's/.*rx: /rx: /')"; done
rm -f /home/pi/gs.owner
echo "LABEYE DONE $(date +%T)"
