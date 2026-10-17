#!/bin/bash
# k6_chain.sh <gs bit> <m2 bit> [gates] [soaks] - TASK-5559 K6 (CALIBRATION_OPTIONS_20261017_v2 §3.3), no JTAG writes
# except the EQA readapt after each load:
#   D2: <gates> (30) gate runs, every one a fresh L3 load, first-attempt pass counted by k2_table.py (run names k2_k6_nn)
#   D1: d1_readback.py against ../t5559/k6/intent.json on 2 separate loads before the gates (no JTAG during a soak)
#   D3/D4: <soaks> (3) independent accepted loads x 5040 s soak (fixed length, never extended), BER by ber_windows.py
#   cd ~/ulx5m-serdes/tools; setsid nohup bash lab/k6_chain.sh <gs> <m2> 30 3 > ../t5559/k6/k6.out 2>&1 &
set -u
GS=$1; M2=$2; G=${3:-30}; S=${4:-3}; O=../t5559/k6
mkdir -p $O
echo "== k6 start $(date -Iseconds) gs=$(sha256sum $GS | cut -c1-8) m2=$(sha256sum $M2 | cut -c1-8) gates=$G soaks=$S"
for d in 1 2; do
  fpga-jtag m2 $M2 -r > /dev/null 2>&1; fpga-jtag gs $GS -r > /dev/null 2>&1; sleep 60
  python3 lab/d1_readback.py --intent $O/intent.json --out $O/d1_load$d.json
done
for i in $(seq 1 $G); do
  python3 -u lab/link_gate.py --run k2_k6_$(printf %02d $i) --out $O --bits-gs $GS --bits-m2 $M2 --readapt eqa \
    --max-attempts 10 | grep --line-buffered -E '^(GATE|BUSY)'
done
echo "== k6 gates done $(date -Iseconds)"
for s in $(seq 1 $S); do
  python3 -u lab/link_gate.py --run soak_k6_$s --out $O --bits-gs $GS --bits-m2 $M2 --readapt eqa --max-attempts 10 \
    --soak 5040 | grep --line-buffered -E '^(GATE|SOAK|BUSY)'
  echo "== soak $s done $(date -Iseconds) $(vcgencmd get_throttled) $(vcgencmd measure_temp)"
done
echo "== k6 done $(date -Iseconds)"
