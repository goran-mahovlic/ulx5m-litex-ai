#!/bin/bash
# build_ber.sh <gs|m2> <name> <seed> [chparam args...]   e.g. build_ber.sh gs od2 1 OUTDIV 2
# yosys -> nextpnr-himbaechel -> gmpack --reset -> gm_cfgrst_check (vrata). Log ostaje u build/.
# NEXTPNR=<path> (env): alternative nextpnr-himbaechel binary (default: from PATH / oss-cad-suite).
# FREQ=<MHz> (env): timing target for all clocks (nextpnr --freq; default 12 = no real target).
#   2.5 Gb/s needs rclk/tclk >= 31.25 MHz, 5 Gb/s >= 62.5 MHz. clk_i (UART) only needs 25 MHz, so a FAIL on clk_i
#   against FREQ is allowed (--timing-allow-fail); read the Fmax numbers in the summary line.
set -e
cd "$(dirname "$0")"; [ -n "$OSS_CAD_SUITE" ] && export PATH=$OSS_CAD_SUITE/bin:$PATH   # else yosys/nextpnr/gmpack from PATH
B=$1; N=$2; S=$3; shift 3; CP=""
while [ $# -ge 2 ]; do CP="$CP chparam -set $1 $2 top_$B;"; shift 2; done
mkdir -p build; O=build/${B}_${N}_s$S
yosys -q -l $O.yosys.log -p "read_verilog -I. ber_link.v ber_top.v; $CP synth_gatemate -top top_$B -luttree -nomx8 -json $O.json"
"${NEXTPNR:-nextpnr-himbaechel}" --device CCGM1A1 --json $O.json -o ccf=top_$B.ccf -o out=$O.txt --router router2 --seed $S ${FREQ:+--freq $FREQ --timing-allow-fail} > $O.pnr.log 2>&1
gmpack --reset $O.txt $O.bit
python3 ../../tools/gm_cfgrst_check.py $O.bit >/dev/null   # gate: exit 1 = no CMD_CFGRST, do not load
echo "$O.bit CFGRST hold_viol=$(grep -c 'Hold/min time violation' $O.pnr.log) $(grep 'Max frequency' $O.pnr.log | tail -3 | sed 's/Info: Max frequency for clock//; s/(PASS at [0-9.]* MHz)//' | tr -s ' ' | tr '\n' ' ')"
