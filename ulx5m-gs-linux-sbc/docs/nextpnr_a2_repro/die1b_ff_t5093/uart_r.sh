#!/bin/bash
# uart_r.sh <bit> <secs> (TASK-5093): OLD flow - load on gs WITH -r (--index-chain 0), send 0x00, print UART
B=$(readlink -f $1); U=$(fpga-jtag uart gs) || exit 2
stty -F $U 115200 raw -echo; timeout 1 cat $U >/dev/null
echo "sha256 $(sha256sum $B | cut -c1-16)"
echo "load: $(sudo -n /usr/local/bin/fpga-jtag gs "$B" -r --index-chain 0 2>&1 | grep -E '^Done|rror' | tail -1)"
sleep 1; printf '\000\000' > $U; timeout $2 cat $U | tr -d '\r'
