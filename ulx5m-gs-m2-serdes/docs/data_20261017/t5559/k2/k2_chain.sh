#!/bin/bash
# k2_chain.sh - TASK-5559 K2 (CALIBRATION_OPTIONS_20261017_v2 §3.1): reset sequence arms through the link gate.
#   cd ~/ulx5m-serdes/tools; setsid nohup bash lab/k2_chain.sh <readapt> [n] > ../t5559/k2/k2.out 2>&1 &
# Arms B0' / B1 / B2 (bits in /home/pi/fpga/t5559) INTERLEAVED (round i: b0p, b1, b2) so drift over the hours hits all
# arms alike; n rounds (default 20). Every gate run starts with a fresh L3 load (m2 -r, gs -r), then --readapt on both
# after PLL+TX_RESET_DONE, up to 10 attempts. First-attempt pass per arm = runs with attempts == 1 (gate_table/k2_table).
set -u
RA=${1:-eqa}; N=${2:-20}; B=/home/pi/fpga/t5559; O=../t5559/k2
declare -A GS=([b0p]=$B/gs_2g5_b0p_s7.bit [b1]=$B/gs_2g5_b1_s7.bit [b2]=$B/gs_2g5_b2_s1.bit)
declare -A M2=([b0p]=$B/m2_2g5_b0p_s2.bit [b1]=$B/m2_2g5_b1_s2.bit [b2]=$B/m2_2g5_b2_s2.bit)
mkdir -p $O
echo "== k2 start $(date -Iseconds) readapt=$RA rounds=$N"
for i in $(seq 1 $N); do
  for arm in b0p b1 b2; do
    python3 lab/link_gate.py --run k2_${arm}_$(printf %02d $i) --out $O --bits-gs ${GS[$arm]} --bits-m2 ${M2[$arm]} \
      --readapt $RA --max-attempts 10 2>&1 | grep -E '^(ATTEMPT|GATE|BUSY)'
  done
  echo "== round $i done $(date +%T) $(vcgencmd get_throttled) $(vcgencmd measure_temp)"
done
echo "== k2 done $(date -Iseconds)"
