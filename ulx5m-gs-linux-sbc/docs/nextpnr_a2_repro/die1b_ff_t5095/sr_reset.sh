#!/bin/bash
# sr_reset.sh <secs> (TASK-5095): send "R!" to a running sr/inv_sr design -> it pulls IO_SB_B8 = RST_N low (selfrst.v),
# the chip resets itself. Then listen on the UART: a reset chip is silent (or prints the flash design, CFG_MD permitting).
U=$(fpga-jtag uart gs) || exit 2
stty -F $U 115200 raw -echo; timeout 1 cat $U >/dev/null
printf 'R!' > $U; echo "sent R! $(date +%T.%N | cut -c1-12)"
timeout $1 cat $U | tr -d '\r'; echo "[uart ${1}s end]"
