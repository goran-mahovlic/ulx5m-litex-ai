#!/bin/bash
# uart_rst.sh <bit> <secs>: load on gs, send 0x00 to clear the masks, print the UART for <secs>
B=$(readlink -f $1); cd ~/t5092; . ./dj_probe.sh; U=$DJ_UART; DJ_LOAD_ARGS="--index-chain 0"
stty -F $U 115200 raw -echo; timeout 1 cat $U >/dev/null
echo "load $(dj_load $B)"; sleep 1; printf '\000\000' > $U; timeout $2 cat $U | tr -d '\r'
