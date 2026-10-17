#!/bin/bash
# TASK-5542 chain4: recipe R1 (CAL0 + TX_SEL_PRE 0 + RX_EQA_CKP_OFFSET 0 + DFE reset) through the strict gate.
# 1) 3 gate runs, L3 only (compare with K1 b1/b2 = 1 pass in 20 attempts). 2) K3 ladder arms with R1 (2 runs).
# 3) gate + 30 min soak. 4) 5 G (P2 bits, SET_ACC 2->0): bits + CAL0 / + R1 TX_AMP 12 / + R1 TX_AMP 16, 3 attempts,
# soak 30 min on a pass. 5) leave the 2.5 G auto bits + R1 loaded.
cd /home/pi/ulx5m-serdes/tools; O=../t5542/gate; L=../t5542/chain4.out
while pgrep -f "[c]alib_aba.py --base cal0 --loads 2" >/dev/null; do sleep 15; done
echo "== chain4 start $(date '+%F %T') $(vcgencmd get_throttled)" >> $L
for i in 1 2 3; do python3 lab/link_gate.py --r1 --metric errb --out $O --run r1_$i >> $L 2>&1; done
for i in 1 2; do python3 lab/link_gate.py --r1 --out $O --run k3r_$i --ladder L3,L1,L1b,L2tx,L2rx,L3,L1,L1b,L2tx,L2rx >> $L 2>&1; done
python3 lab/link_gate.py --r1 --out $O --run soak_r1 --soak 1800 >> $L 2>&1
echo "== 2.5G done $(date '+%F %T')" >> $L
O5=../t5542/gate5; mkdir -p $O5
G5() { python3 lab/link_gate.py --rate 5g --set-acc --max-attempts 3 --soak 1800 --out $O5 "$@" >> $L 2>&1; }
G5 --run p2_cal0 --cal0
G5 --run p2_r1_amp12 --r1 --set TX_AMP=12
G5 --run p2_r1_amp16 --r1 --set TX_AMP=16
echo "== 5G done $(date '+%F %T')" >> $L
fpga-jtag m2 /home/pi/fpga/m2_2g5_auto.bit -r >> $L 2>&1; fpga-jtag gs /home/pi/fpga/gs_2g5_auto.bit -r >> $L 2>&1
for b in m2 gs; do fpga-jtag $b run python3 eyescan.py set RX_CALIB_OVR=1 RX_CALIB_VAL=0 TX_CALIB_OVR=1 TX_CALIB_VAL=0 TX_SEL_PRE=0 RX_EQA_CKP_OFFSET=0 >> $L 2>&1
  fpga-jtag $b run python3 eyescan.py set RX_EQA_RESET_OVR=1 RX_EQA_RESET=1 >> $L 2>&1; fpga-jtag $b run python3 eyescan.py set RX_EQA_RESET_OVR=0 RX_EQA_RESET=0 >> $L 2>&1; done
echo "== chain4 done, 2.5 G auto bits + R1 left loaded $(date '+%F %T')" >> $L
