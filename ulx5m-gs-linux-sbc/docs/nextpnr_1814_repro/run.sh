#!/bin/bash
# Minimal repro: nextpnr 3c42800d (#1814) aborts with dict::at(); ad8527f8 (#1817) and 073bb87e do not.
# usage: NEXTPNR=/path/to/nextpnr-himbaechel ./run.sh
set -e
cd "$(dirname "$0")"
yosys -q -p "synth_gatemate -top top -json top.json" top.v
${NEXTPNR:-nextpnr-himbaechel} --device CCGM1A1 --json top.json --vopt ccf=top.ccf --vopt out=top.txt
