#!/bin/bash
# build_ber.sh <gs|m2> <name> <seed> [chparam args...]   e.g. build_ber.sh gs od2 1 OUTDIV 2
# yosys -> nextpnr-himbaechel -> gmpack --reset -> gm_cfgrst_check (vrata). Log ostaje u build/.
# OSS_CAD_SUITE (env, default ~/app/raid/tools/oss-cad-suite = link to the default chain, 20261016 since TASK-5549;
#   fallback e.g. OSS_CAD_SUITE=~/app/raid/tools/oss-cad-suite-20260923). The resolved path goes to build/<name>.toolchain.
# NEXTPNR=<path> (env): alternative nextpnr-himbaechel binary (default: from OSS_CAD_SUITE).
# LINK=ber_link_gs.v (env): checker source (default ber_link.v; gs uses ber_link_gs.v, see its header).
# SYNTH_OPTS (env, default "-luttree -nomx8"): extra synth_gatemate options.
# ROUTER=router1|router2 (env, default router2).
# FREQ=<MHz> (env): timing target for all clocks (nextpnr --freq; default 12 = no real target).
#   2.5 Gb/s needs rclk/tclk >= 31.25 MHz, 5 Gb/s >= 62.5 MHz. clk_i (UART) only needs 25 MHz, so a FAIL on clk_i
#   against FREQ is allowed (--timing-allow-fail); read the Fmax numbers in the summary line.
set -e
cd "$(dirname "$0")"; OSS_CAD_SUITE=${OSS_CAD_SUITE:-$HOME/app/raid/tools/oss-cad-suite}; export PATH=$OSS_CAD_SUITE/bin:$PATH
B=$1; N=$2; S=$3; shift 3; CP=""
while [ $# -ge 2 ]; do CP="$CP chparam -set $1 $2 top_$B;"; shift 2; done
mkdir -p build; O=build/${B}_${N}_s$S
{ readlink -f "$OSS_CAD_SUITE"; yosys -V; "${NEXTPNR:-nextpnr-himbaechel}" --version 2>&1 | head -1; } > $O.toolchain
yosys -q -l $O.yosys.log -p "read_verilog -I. ${LINK:-ber_link.v} ber_top.v; $CP synth_gatemate -top top_$B ${SYNTH_OPTS--luttree -nomx8} -json $O.json"
"${NEXTPNR:-nextpnr-himbaechel}" --device CCGM1A1 --json $O.json -o ccf=top_$B.ccf -o out=$O.txt --router ${ROUTER:-router2} --seed $S ${FREQ:+--freq $FREQ --timing-allow-fail} > $O.pnr.log 2>&1
gmpack --reset $O.txt $O.bit
python3 ../../tools/gm_cfgrst_check.py $O.bit >/dev/null   # gate: exit 1 = no CMD_CFGRST, do not load
echo "$O.bit CFGRST hold_viol=$(grep -c 'Hold/min time violation' $O.pnr.log) $(grep 'Max frequency' $O.pnr.log | tail -3 | sed 's/Info: Max frequency for clock//; s/(PASS at [0-9.]* MHz)//' | tr -s ' ' | tr '\n' ' ')"
