#!/bin/bash
# TASK-5079: type commands into the logged-in Linux serial console of gs (80 ms/char, W s after each), print the answer
. /home/pi/t5079/dj_probe.sh; U=$DJ_UART; fuser $U >/dev/null 2>&1 && { echo BUSY; exit 2; }
stty -F $U 115200 raw -echo; cat $U > /home/pi/t5079/ux.txt & CP=$!
TYPE() { local c="$1"; for ((i=0; i<${#c}; i++)); do printf "%s" "${c:$i:1}" > $U; sleep 0.08; done; printf "\r" > $U; }
TYPE ""; sleep 1
for c in "$@"; do TYPE "$c"; sleep ${W:-5}; done
kill $CP; tr '\r' '\n' < /home/pi/t5079/ux.txt | tr -c '[:print:]\n' '.'
