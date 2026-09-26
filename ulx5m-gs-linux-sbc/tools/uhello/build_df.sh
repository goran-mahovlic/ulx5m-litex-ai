#!/bin/bash
# TASK-4999: build diagflags SET <n> [REG0] [DEFS]; prints PLL slot of each flag (g[0], g[1], g[2]=one)
cd "$(dirname "$0")"; export PATH=/home/klaudio/app/raid/tools/oss-cad-suite-20260923/bin:$PATH
S=$1; R0=${2:-1200}; DEFS=${3:--DMDIO_WO}; N=df_s$S${4:-}
python3 gen_core.py
yosys -q -p "read_verilog $DEFS diagflags.v mdio_core.v pllflags.v; chparam -set SET $S -set REG0 16'h$R0 top; synth_gatemate -luttree -nomx8 -top top -run begin:map_regs; dffunmap -ce-only; synth_gatemate -luttree -nomx8 -top top -run map_regs:json; write_json $N.json" 2>&1 | grep -v -E "experimental|tri-state"
for SEED in 1 2 3 4 5 6; do nextpnr-himbaechel --device CCGM1A1 --json $N.json --vopt ccf=diagflags.ccf --vopt out=$N.txt --vopt fpga_mode=3 --router router2 --freq 25 --seed $SEED --write $N.routed.json > $N.pnr.log 2>&1 && break; done
gmpack $N.txt $N.bit
python3 -c "
import json
j=json.load(open('$N.routed.json'))
print('$N', ' '.join(sorted(n.split('.')[1]+'->'+c['attributes']['NEXTPNR_BEL'].split('/')[1] for n,c in j['modules']['top']['cells'].items() if c['type']=='PLL')))
"
