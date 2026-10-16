#!/bin/bash
# TASK-5542 uputa #347: K3 ladder arms (3 gate runs), then K4-K9 A/B/A on 3 fresh loads (calib_aba.py).
cd /home/pi/ulx5m-serdes/tools; O=../t5542/gate
while pgrep -f "lab/link_gate.py" >/dev/null; do sleep 15; done
echo "== chain_k start $(date '+%F %T') $(vcgencmd get_throttled)" >> $O/chain_k.out
for i in 1 2 3; do python3 lab/link_gate.py --out $O --run k3_$i --ladder L3,L1,L1b,L2tx,L2rx,L3,L1,L1b,L2tx,L2rx >> $O/chain_k.out 2>&1; done
echo "== K3 done $(date '+%F %T')" >> $O/chain_k.out
mkdir -p ../t5542/calib
python3 lab/calib_aba.py --loads 3 --secs 40 --out ../t5542/calib/aba1.jsonl >> ../t5542/calib/aba1.out 2>&1
echo "== chain_k done $(date '+%F %T')" >> $O/chain_k.out
