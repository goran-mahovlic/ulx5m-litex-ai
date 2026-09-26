#!/bin/bash
# TASK-5032 (runs on the Pi): pitest.sh <bit> [seconds]
# tcpdump (board MAC + ARP/ICMP for .212) -> flash -r -> UART window (mdio_core lines) -> ping -D -i 0.2
# (first-reply time after the load) -> ping -s sweep. Output: /tmp/g_* files + summary on stdout.
BIT=$1; T=${2:-25}; IP=192.168.10.212
rm -f /tmp/g_*
/usr/sbin/tcpdump -i eth0 -n -e -xx -l -U -w /tmp/g_cap.pcap "ether host 10:e2:d5:00:00:00 or host $IP" 2>/dev/null &
TD=$!
sleep 1
for a in /dev/ttyACM0; do stty -F $a 115200 raw -echo 2>/dev/null; timeout 1 cat $a >/dev/null 2>&1; done
ip neigh del $IP dev eth0 2>/dev/null
sudo -n /usr/local/bin/openFPGALoader -c dirtyJtag "$BIT" -r 2>&1 | grep -E "^Done|fail|rror" | tail -2
T0=$(date +%s.%N)
(timeout $T cat /dev/ttyACM0 > /tmp/g_uart.txt 2>/dev/null &)
ping -D -i 0.2 -W 1 -c $((T*5)) $IP > /tmp/g_ping0.txt 2>&1 &
PP=$!
sleep $T
kill $PP 2>/dev/null
FIRST=$(grep -m1 "bytes from" /tmp/g_ping0.txt | sed 's/^\[\([0-9.]*\)\].*/\1/')
if [ -n "$FIRST" ]; then echo "first reply after load: $(python3 -c "print(round($FIRST - $T0, 2))") s"; else echo "first reply after load: NONE in $T s"; fi
echo "ping0: $(grep -c 'bytes from' /tmp/g_ping0.txt) replies / $(grep -c '' /tmp/g_ping0.txt) lines"
for s in 0 18 19 56 100 1000 1472; do
  r=$(ping -c 5 -W 1 -i 0.3 -s $s $IP 2>&1 | grep -E "transmitted" | sed 's/, time.*//')
  echo "ping -s $s: $r"
done
ip neigh show $IP
kill $TD; sleep 1
echo "UART: $(wc -c < /tmp/g_uart.txt) B"; tr -c '[:print:]\n' '.' < /tmp/g_uart.txt | grep "P=" | tail -3
python3 ~/FPGA/beacon.py /tmp/g_cap.pcap
