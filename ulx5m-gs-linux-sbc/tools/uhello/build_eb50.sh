#!/bin/bash
# TASK-4999: build eb50 (beacon, TXC from a negedge IOSEL FF on clk50).  build_eb50.sh <name> [fpga_mode]
set -e
cd "$(dirname "$0")"
export PATH=/home/klaudio/app/raid/tools/oss-cad-suite-20260923/bin:$PATH
N=$1; FM=${2:-2}; FL=${3:-60}
python3 gen_core.py
yosys -q -p "read_verilog ethbeacon50.v mdio_core.v; chparam -set FL $FL top; synth_gatemate -luttree -nomx8 -top top -run begin:map_regs; dffunmap -ce-only; synth_gatemate -luttree -nomx8 -top top -run map_regs:json; write_json $N.json" 2>&1 | grep -v -E "experimental|tri-state" || true
for SEED in 1 2 3 4 5 6 7 8 9 10 11 12; do
  if nextpnr-himbaechel --device CCGM1A1 --json $N.json --vopt ccf=ethbeacon50.ccf --vopt out=$N.txt \
       --vopt fpga_mode=$FM --router router2 --freq 25 --timing-allow-fail --seed $SEED --write $N.routed.json > $N.pnr.log 2>&1; then echo "seed $SEED routed"; break; fi
  echo "seed $SEED: $(grep -m1 ERROR $N.pnr.log | cut -c1-60)"; rm -f $N.txt
done
grep -E "Max frequency" $N.pnr.log | tail -3
gmpack --reset $N.txt $N.bit && ls -la $N.bit
