#!/bin/bash
# start PLL serial receiver in background: rxstart.sh <log> <args...>
LOG=$1; shift
cd /tmp
nohup setsid python3 /tmp/pll_serial_rx.py rx "$@" > "$LOG" 2>&1 < /dev/null &
echo "started pid $!"
