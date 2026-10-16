#!/bin/bash
# TASK-5542 5 G after the 2.5 G campaign: same gate (GS->M2 by the m2 checker, M2->GS by PEER >= 990/1000), old P2 bits
# (CKI != 0 -> SET_ACC 2->0 after the load). Before calibration = bits as built (TX_AMP 31), after = TX_AMP 12 (2.5 G
# calibration, CALIBRATION_REVIEW §1) and the S1 points 20/16. 3 attempts per point; a pass gets a 30 min soak.
cd /home/pi/ulx5m-serdes/tools; O=../t5542/gate5
while pgrep -f campaign25.sh >/dev/null; do sleep 20; done
mkdir -p $O; echo "== campaign5 start $(date '+%F %T') $(vcgencmd get_throttled)" >> $O/campaign5.out
G() { python3 lab/link_gate.py --rate 5g --set-acc --max-attempts 3 --soak 1800 --out $O "$@" 2>&1 | tee -a $O/campaign5.out | grep -E '^(GATE|SOAK|BUSY)'; }
G --run p2_amp31
G --run p2_amp12 --set TX_AMP=12
G --run p2_amp20 --set TX_AMP=20
G --run p2_amp16 --set TX_AMP=16
echo "== campaign5 done $(date '+%F %T')" >> $O/campaign5.out
# leave the boards on the calibrated 2.5 G pair (as found before TASK-5542)
fpga-jtag m2 /home/pi/fpga/m2_2g5_auto.bit -r >> $O/campaign5.out 2>&1; fpga-jtag gs /home/pi/fpga/gs_2g5_auto.bit -r >> $O/campaign5.out 2>&1
echo "== restored 2.5 G auto bits $(date '+%F %T')" >> $O/campaign5.out
