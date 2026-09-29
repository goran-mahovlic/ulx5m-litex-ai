#!/bin/bash
# Minimal repro (TASK-5092): with the default 'mirror' strategy a BUFG clock X gets a copy X$die1 on die 1B. A path from
# an IOSEL register on die 1B (clocked by X$die1) to a CPE register on die 1A (clocked by X) is reported only as
# "Max delay posedge X$die1 -> posedge X: ~11.5 ns" and never checked against the 125 MHz (8 ns) constraint, so the
# run says PASS. On CCGM1A1 (no copy) the same path is a normal, checked same-clock path.
# usage: NEXTPNR=/path/to/nextpnr-himbaechel ./run.sh   (force_die=1A puts the two registers on die 1A)
set -e
cd "$(dirname "$0")"
yosys -q -p "read_verilog top.v; synth_gatemate -top top -luttree -nomx8; write_json top.json"
${NEXTPNR:-nextpnr-himbaechel} --device CCGM1A2 --vopt force_die=1A --json top.json --vopt ccf=top.ccf --vopt out=top.txt \
    --freq 125 "$@" 2>&1 | grep -E "Max frequency|Max delay|cross-domain"
