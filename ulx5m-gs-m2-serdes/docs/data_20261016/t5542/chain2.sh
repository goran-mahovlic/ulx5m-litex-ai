#!/bin/bash
# TASK-5542 chain2: base = termination code forced 0/0 after every load (K12; CAL 9/7 is sticky since the 19:15 recal).
# 1) K4-K9 + K12 code sweep, A/B/A, 3 fresh loads, 30 s per state. 2) K3 ladder arms (L1/L1b without CALIB strobes).
cd /home/pi/ulx5m-serdes/tools
echo "== chain2 start $(date '+%F %T') $(vcgencmd get_throttled)" >> ../t5542/chain2.out
python3 lab/calib_aba.py --base cal0 --loads 3 --secs 30 --only K4,K5,K6,K7,K8,K9,rxval1,rxval2,rxval4,txval2,txval4 \
  --out ../t5542/calib/aba2.jsonl >> ../t5542/calib/aba2.out 2>&1
echo "== aba2 done $(date '+%F %T')" >> ../t5542/chain2.out
for i in 1 2 3; do python3 lab/link_gate.py --cal0 --out ../t5542/gate --run k3c_$i --ladder L3,L1,L1b,L2tx,L2rx,L3,L1,L1b,L2tx,L2rx >> ../t5542/chain2.out 2>&1; done
echo "== chain2 done $(date '+%F %T')" >> ../t5542/chain2.out
