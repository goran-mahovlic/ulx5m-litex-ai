#!/bin/bash
# TASK-5033 (runs on the Pi): nb_accept.sh <dirty_bit> <soc_bit> [uart_s]
# One netboot attempt: dirty design -> SoC (--boot netboot) with -r; the BIOS fetches boot.bin over TFTP from
# this Pi (/srv/tftp, service tftp-litex) and jumps to it; the LiteX demo app answers `help` on the serial
# (GPIO4/5). Also: first ping reply time on the hardware stack (.212) and the ping -s sweep.
DIRTY=$1; BIT=$2; W=${3:-45}; IP=192.168.10.212; U=/dev/ttyACM0
rm -f /tmp/nb_*
fuser $U 2>/dev/null && { echo "ttyACM0 BUSY - attempt invalid"; exit 2; }
SEND() { local c="$1"; for ((i=0; i<${#c}; i++)); do printf "%s" "${c:$i:1}" > $U; sleep 0.02; done; printf "\r" > $U; }
LOAD() { sudo -n /usr/local/bin/openFPGALoader -c dirtyJtag "$1" -r 2>&1 | grep -E "^Done|rror" | tail -1; }
echo "dirty: $(basename $DIRTY) -> $(LOAD $DIRTY)"
sleep 3
stty -F $U 115200 raw -echo; timeout 2 cat $U >/dev/null 2>&1
ip neigh del $IP dev eth0 2>/dev/null
# CPU port evidence (uputa #32): ARP and TFTP of 192.168.10.213 / MAC 10:e2:d5:00:00:01 during the BIOS netboot
/usr/sbin/tcpdump -i eth0 -n -e -l "ether host 10:e2:d5:00:00:01" 2>/dev/null > /tmp/nb_cpu.txt & TD=$!
echo "soc:   $(basename $BIT) -> $(LOAD $BIT)"
T0=$(date +%s.%N)
timeout $((W+10)) cat $U > /tmp/nb_uart.txt 2>/dev/null & CP=$!
ping -D -i 0.2 -W 1 -c 100 $IP > /tmp/nb_ping0.txt 2>&1 & PP=$!
for ((t=0; t<W; t++)); do grep -aq "litex-demo-app" /tmp/nb_uart.txt && break; sleep 1; done
echo "demo prompt: $(grep -aq 'litex-demo-app' /tmp/nb_uart.txt && python3 -c "import time; print(round(time.time() - $T0, 1), 's after load')" || echo NONE)"
SEND "help"; sleep 3
kill $TD 2>/dev/null
echo "CPU port .213: $(grep -c 'ARP.*tell 192.168.10.213' /tmp/nb_cpu.txt) ARP requests, $(grep -c 'is-at .* 10:e2:d5:00:00:01\|> 10:e2:d5:00:00:01, ethertype ARP' /tmp/nb_cpu.txt) ARP replies to it, $(grep -c 'RRQ' /tmp/nb_cpu.txt) TFTP RRQ, $(grep -c '192.168.10.213.[0-9]* > 192.168.10.14' /tmp/nb_cpu.txt) frames .213 -> Pi"
grep -m3 -E "ARP|RRQ" /tmp/nb_cpu.txt | cut -c17-140
wait $PP; kill $CP 2>/dev/null
FIRST=$(grep -m1 "bytes from" /tmp/nb_ping0.txt | sed 's/^\[\([0-9.]*\)\].*/\1/')
[ -n "$FIRST" ] && echo "first ping reply after load: $(python3 -c "print(round($FIRST - $T0, 2))") s" \
                || echo "first ping reply after load: NONE"
echo "ping0: $(grep -c 'bytes from' /tmp/nb_ping0.txt)/100 replies"
for s in 0 18 56 100 1000 1472; do
  echo "ping -s $s: $(ping -c 5 -W 1 -i 0.3 -s $s $IP 2>&1 | grep transmitted | sed 's/, time.*//')"
done
echo "ping -s 1472 x20: $(ping -c 20 -W 1 -i 0.2 -s 1472 $IP 2>&1 | grep transmitted | sed 's/, time.*//')"
echo "UART $(wc -c < /tmp/nb_uart.txt) B:"
tr '\r' '\n' < /tmp/nb_uart.txt | tr -c '[:print:]\n' '.' | sed 's/\.\[[0-9;]*m//g' | grep -aE \
  "CPU|SDRAM|Memtest|Local IP|Remote IP|Booting|boot|Download|download|Executing|Timeout|demo|help|donut|litex" | head -30
