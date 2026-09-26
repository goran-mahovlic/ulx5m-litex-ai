#!/bin/bash
# iso.sh <bit> "<bios cmd>": load, optional BIOS command at t=8 s, ping 1472 every 0.5 s for 70 s; replies per 10 s bin
BIT=$1; MT=$2; IP=192.168.10.212; U=/dev/ttyACM0
stty -F $U 115200 raw -echo; timeout 2 cat $U >/dev/null 2>&1
ip neigh del $IP dev eth0 2>/dev/null
sudo -n /usr/local/bin/openFPGALoader -c dirtyJtag "$BIT" -r 2>&1 | grep -E "^Done|rror" | tail -1
T0=$(date +%s)
timeout 75 cat $U > /tmp/iso_uart.txt 2>/dev/null & CP=$!
ping -D -i 0.5 -W 1 -c 140 -s 1472 $IP > /tmp/iso_ping.txt 2>&1 & PP=$!
sleep 8
if [ -n "$MT" ]; then for ((i=0; i<${#MT}; i++)); do printf "%s" "${MT:$i:1}" > $U; sleep 0.02; done; printf "\r" > $U; fi
wait $PP; kill $CP 2>/dev/null
python3 - $T0 <<'PY'
import sys,re; t0=float(sys.argv[1]); b=[0]*8
for l in open('/tmp/iso_ping.txt'):
    m=re.match(r'\[([0-9.]+)\].*bytes from',l)
    if m: b[min(7,int((float(m.group(1))-t0)//10))]+=1
print("replies per 10 s (max 20):", b)
PY
C=$(tr '\r' '\n' < /tmp/iso_uart.txt | tr -c '[:print:]\n' '.')
echo "$C" | grep -vE "(Write|Read): 0x" | grep -iE "sdcard|card|timeout|Command|litex>" | tail -6
echo "banners: $(echo "$C" | grep -c 'CPU:') memtestOK: $(echo "$C" | grep -c 'Memtest OK')"
dmesg -T | grep -i voltage | tail -3
