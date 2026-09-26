#!/bin/bash
# TASK-4999: build the standalone Ethernet beacon.  build_beacon.sh <name> <REG0 hex>
set -e
cd "$(dirname "$0")"
export PATH=/home/klaudio/app/raid/tools/oss-cad-suite-20260923/bin:$PATH
N=$1; R0=${2:-1200}; DEFS=${3:-}   # DEFS e.g. "-DMDIO_WO"
python3 gen_core.py
# dffunmap -ce-only: wide clock-enable nets do not route on GateMate (nextpnr-himbaechel, 24.9.)
yosys -q -p "read_verilog $DEFS ethbeacon.v mdio_core.v pllflags.v; chparam -set REG0 16'h$R0 top; synth_gatemate -luttree -nomx8 -top top -run begin:map_regs; dffunmap -ce-only; synth_gatemate -luttree -nomx8 -top top -run map_regs:json; write_json $N.json" 2>&1 | grep -v -E "experimental|tri-state" || true
# the GateMate router is seed-fragile ("Failed to route arc"): sweep seeds
for SEED in 1 2 3 4 5 6 7 8 9 10 11 12; do
  if nextpnr-himbaechel --device CCGM1A1 --json $N.json --vopt ccf=ethbeacon.ccf --vopt out=$N.txt \
       --vopt fpga_mode=3 --router router2 --freq 25 --seed $SEED --write $N.routed.json > $N.pnr.log 2>&1; then echo "seed $SEED routed"; break; fi
  echo "seed $SEED: $(grep -m1 ERROR $N.pnr.log | cut -c1-60)"; rm -f $N.txt
done
grep -E "Max frequency" $N.pnr.log | tail -3
gmpack --reset $N.txt $N.bit && ls -la $N.bit
