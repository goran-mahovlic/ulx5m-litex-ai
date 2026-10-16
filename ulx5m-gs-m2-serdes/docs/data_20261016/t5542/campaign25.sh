#!/bin/bash
# TASK-5542 2.5 G campaign (link_gate.py): K1 baseline gates, soak on a passed gate, K3 ladder arms, K4 TX_AMP 10/14.
cd /home/pi/ulx5m-serdes/tools; O=../t5542/gate
G() { python3 lab/link_gate.py --out $O "$@" 2>&1 | tee -a $O/campaign25.out | grep -E '^(GATE|SOAK|BUSY)'; }
echo "== campaign25 start $(date '+%F %T') $(vcgencmd get_throttled)" >> $O/campaign25.out
for i in 1 2 3 4 5; do G --run b$i; done
G --run s1 --soak 1800
for i in 1 2 3; do G --run k3_$i --ladder L3,L1,L1b,L2tx,L2rx,L3,L1,L1b,L2tx,L2rx; done
for i in 1 2 3; do G --run a10_$i --set TX_AMP=10; done
for i in 1 2 3; do G --run a14_$i --set TX_AMP=14; done
echo "== campaign25 done $(date '+%F %T')" >> $O/campaign25.out
