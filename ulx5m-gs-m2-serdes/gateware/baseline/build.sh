#!/bin/bash
# build.sh [seed] — baseline GS<->M2 SerDes link test (CologneChip serdes_lb.v, K28.5 + D10.2, 0.3 Gb/s)
# with RX_POLARITY_I=1 in the bitstream. The SAME bitstream is loaded on both boards.
# Needs yosys, nextpnr-himbaechel and gmpack; default OSS_CAD_SUITE = ~/app/raid/tools/oss-cad-suite (default chain, TASK-5549).
set -e
cd "$(dirname "$0")"; export PATH=${OSS_CAD_SUITE:-$HOME/app/raid/tools/oss-cad-suite}/bin:$PATH
S=${1:-1}; mkdir -p build; O=build/serdes_p1_s$S
yosys -q -l $O.yosys.log -p "read_verilog serdes_lb_p1.v dut_top.v; chparam -set LOOPBACK_SEL 0 serdes_lb; synth_gatemate -top dut_top -luttree -nomx8 -json $O.json"
nextpnr-himbaechel --device CCGM1A1 --json $O.json -o ccf=dut_top.ccf -o out=$O.txt --router router2 --seed $S > $O.pnr.log 2>&1
gmpack --reset $O.txt ${O}_CFGRST.bit                  # --reset = CMD_CFGRST first: clean chip on every load
python3 ../../tools/gm_cfgrst_check.py ${O}_CFGRST.bit  # gate: must print CFGRST (exit 0)
echo "hold violations: $(grep -c 'Hold/min time violation' $O.pnr.log)"
