#!/bin/bash
# lx_cmd.sh "<cmd>" [wait]: type one shell command into the Linux console (char by char), print the output
U=/dev/ttyACM0; W=${2:-6}
fuser $U 2>/dev/null && { echo BUSY; exit 2; }
stty -F $U 115200 raw -echo; timeout 1 cat $U >/dev/null 2>&1
timeout $((W+3)) cat $U > /tmp/lx_cmd.txt & CP=$!
sleep 0.3; c="$1"
for ((i=0; i<${#c}; i++)); do printf "%s" "${c:$i:1}" > $U; sleep 0.08; done; printf "\r" > $U
sleep $W; kill $CP 2>/dev/null
tr '\r' '\n' < /tmp/lx_cmd.txt | tr -c '[:print:]\n' '.' | grep -av "^\.*$"
