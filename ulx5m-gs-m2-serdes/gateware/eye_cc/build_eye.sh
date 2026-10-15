#!/bin/bash
# build_eye.sh <name> <seed> [chparam args...] - TASK-5525: Patrick's serdes_lb.v (upstream_cc_20261015) + top_eye.v for GS and M2
# (same bit on both boards: no board-specific pins). yosys -> nextpnr-himbaechel -> gmpack --reset -> gm_cfgrst_check.
set -e
cd "$(dirname "$0")"; export PATH=${OSS_CAD_SUITE:-$HOME/app/raid/tools/oss-cad-suite-20260923}/bin:$PATH
N=$1; S=$2; shift 2; CP=""
while [ $# -ge 2 ]; do CP="$CP chparam -set $1 $2 top_eye;"; shift 2; done
mkdir -p build; O=build/eye_${N}_s$S
yosys -q -l $O.yosys.log -p "read_verilog -sv ../upstream_cc_20261015/serdes_lb.v top_eye.v; $CP synth_gatemate -top top_eye -luttree -nomx8 -json $O.json"
nextpnr-himbaechel --device CCGM1A1 --json $O.json -o ccf=top_eye.ccf -o out=$O.txt --router router2 --seed $S > $O.pnr.log 2>&1
gmpack --reset $O.txt $O.bit
python3 ../../tools/gm_cfgrst_check.py $O.bit >/dev/null
echo "$O.bit CFGRST $(sha256sum $O.bit | cut -c1-16)"
