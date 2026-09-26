#!/bin/bash
# ber_run.sh <gs.bit|-> <m2.bit|-> <secs> <label> — load (m2 first, then gs; '-' = keep what is loaded),
# JTAG view of both boards, BER run with cleared counters (JSON), JTAG view again. Log: $LOG/<label>.log
# Paths: TOOLS (default: ..), LOG (default: ./log). Needs fpga-jtag (one probe per board).
T=${TOOLS:-$(cd "$(dirname "$(readlink -f "$0")")/.." && pwd)}; LOG=${LOG:-$PWD/log}; mkdir -p "$LOG"
GS=$1; M2=$2; S=$3; N=$4; O=$LOG/$N.log
{
echo "== $N $(date '+%F %T') gs=$GS m2=$M2 secs=$S"
if [ "$GS" != "-" ]; then fpga-jtag m2 "$M2" -r 2>&1 | tail -1; fpga-jtag gs "$GS" -r 2>&1 | tail -1; sleep 3; fi
fpga-jtag gs run python3 "$T/ber_jtag_check.py" --samples 10 2>&1 | tail -1
fpga-jtag m2 run python3 "$T/ber_jtag_check.py" --samples 10 2>&1 | tail -1
( cd "$T"; python3 ber_mon.py run --secs "$S" --clear --json ) > "$LOG/$N.json"; echo "ber_mon exit=$?"
( cd "$T"; python3 -c "import json,ber_mon;print(ber_mon.fmt(json.load(open('$LOG/$N.json'))))" )
fpga-jtag gs run python3 "$T/ber_jtag_check.py" --samples 10 2>&1 | tail -1
fpga-jtag m2 run python3 "$T/ber_jtag_check.py" --samples 10 2>&1 | tail -1
echo "== END $(date '+%T')"
} > "$O" 2>&1
