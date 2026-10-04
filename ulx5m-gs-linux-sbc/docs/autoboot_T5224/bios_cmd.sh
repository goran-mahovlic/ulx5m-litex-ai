#!/bin/bash
# bios_cmd.sh "<cmd>" [wait_s] : type a command into the LiteX BIOS console on gs (30 ms/char) and print the reply
U=$(fpga-jtag uart gs) || exit 2
stty -F $U 115200 raw -echo; timeout 0.5 cat $U >/dev/null
( timeout ${2:-3} cat $U > /tmp/bios_cmd.$$ ) &
c="$1"; for ((i=0;i<${#c};i++)); do printf "%s" "${c:$i:1}" > $U; sleep 0.03; done; printf "\r" > $U
wait; tr -d "\033" < /tmp/bios_cmd.$$ | sed "s/\[[0-9;]*m//g" | tr -d "\r"; rm -f /tmp/bios_cmd.$$
