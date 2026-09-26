#!/bin/bash
# lx_session.sh <secs> "<cmd1>" "<cmd2>" ... : type commands (80 ms/char) into the Linux console and capture the UART
U=/dev/ttyACM0; T=$1; shift; L=/tmp/t5040_sess_$$.txt
fuser $U 2>/dev/null && { echo BUSY; exit 2; }
stty -F $U 115200 raw -echo; timeout 1 cat $U >/dev/null 2>&1
timeout $T cat $U > $L & CP=$!
for c in "$@"; do sleep 1; for ((i=0; i<${#c}; i++)); do printf "%s" "${c:$i:1}" > $U; sleep 0.08; done; printf "\r" > $U; sleep 2; done
wait $CP
tr '\r' '\n' < $L | tr -c '[:print:]\n' '.' | grep -av "^\.*$"
