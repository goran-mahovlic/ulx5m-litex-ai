#!/bin/bash
# [APP=linuxsd] linux_boot.sh <bit> [secs]: netboot Linux images from /srv/tftp and watch the serial console (runs on the Pi)
. "$(dirname "$(readlink -f "$0")")/dj_probe.sh" 2>/dev/null || . "$(dirname "$(readlink -f "$0")")/../dj_probe.sh"   # flat copy on the Pi, or this repo
BIT=$1; T=${2:-300}; U=$DJ_UART
fuser $U 2>/dev/null && { echo "$U BUSY"; exit 2; }
~/FPGA/netboot_app.sh ${APP:-linux} >/dev/null   # APP=linuxsd: SPI-SD SoC (TASK-5039)
stty -F $U 115200 raw -echo; timeout 2 cat $U >/dev/null 2>&1
ip neigh del 192.168.10.213 dev eth0 2>/dev/null
dj_load "$BIT"
T0=$(date +%s)
timeout $T cat $U > /tmp/lx_uart.txt 2>/dev/null & CP=$!
for ((t=0; t<T; t+=5)); do
  sleep 5
  grep -aqE "login:|# $|Welcome to Buildroot" /tmp/lx_uart.txt && { echo "LOGIN PROMPT after $(( $(date +%s) - T0 )) s"; break; }
done
sleep 3
printf "root\r" > $U; sleep 5; printf "uname -a; cat /proc/cpuinfo | head -8; free; ip addr show eth0\r" > $U; sleep 8
ping -c 5 -W 2 192.168.10.213 | grep -E "transmitted|bytes from" | tail -2
kill $CP 2>/dev/null
~/FPGA/netboot_app.sh demo >/dev/null
tr '\r' '\n' < /tmp/lx_uart.txt | tr -c '[:print:]\n' '.' | sed 's/\.\[[0-9;]*m//g' | grep -av "^\.*$" | tail -${TAILN:-60}
