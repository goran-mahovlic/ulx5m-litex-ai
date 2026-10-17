#!/bin/bash
# TASK-5542 chain3 (replaces the tail of chain2): after aba2, E-EQA = is the DFE better held in reset / off than adapted?
# 2 loads, base CAL0, steps on both boards, fields read twice after each step, 30 s BER per step. Then K3 gates.
cd /home/pi/ulx5m-serdes/tools
while pgrep -f "[c]alib_aba.py --base cal0 --loads 3" >/dev/null; do sleep 15; done
echo "== chain3 start $(date '+%F %T') $(vcgencmd get_throttled)" >> ../t5542/chain2.out
S='a0 | hold=RX_EQA_RESET_OVR=1 RX_EQA_RESET=1 | hold_b | rel=RX_EQA_RESET=0 | ovr0=RX_EQA_RESET_OVR=0 | a1 | hold3=RX_EQA_RESET_OVR=1 RX_EQA_RESET=1 | both0=RX_EQA_RESET_OVR=0 RX_EQA_RESET=0 | a2 | dfeoff=RX_EN_EQA=0 | dfeoff_b | dfeon=RX_EN_EQA=1 | a3'
python3 lab/calib_aba.py --base cal0 --loads 2 --secs 30 --steps "$S" --out ../t5542/calib/eeqa.jsonl >> ../t5542/calib/eeqa.out 2>&1
echo "== eeqa done $(date '+%F %T')" >> ../t5542/chain2.out
for i in 1 2 3; do python3 lab/link_gate.py --cal0 --out ../t5542/gate --run k3c_$i --ladder L3,L1,L1b,L2tx,L2rx,L3,L1,L1b,L2tx,L2rx >> ../t5542/chain2.out 2>&1; done
echo "== chain3 done $(date '+%F %T')" >> ../t5542/chain2.out
