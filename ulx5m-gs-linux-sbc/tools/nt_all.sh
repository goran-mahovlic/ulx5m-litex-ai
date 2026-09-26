#!/bin/bash
# TASK-4999: flash -r, capture ALL frames, list src MACs, read UART ttyACM0/1
BIT=$1; T=${2:-20}
echo "### $(date +%T) $BIT"
/usr/sbin/tcpdump -i eth0 -n -e -l -U -w /tmp/na.pcap 2>/dev/null &
TD=$!
sleep 1
for a in /dev/ttyACM0 /dev/ttyACM1; do stty -F $a 115200 raw -echo 2>/dev/null; timeout 1 cat $a >/dev/null 2>&1; done
sudo -n /usr/local/bin/openFPGALoader -c dirtyJtag "$BIT" -r 2>&1 | grep -E "^Done|fail|rror" | tail -2
for a in /dev/ttyACM0 /dev/ttyACM1; do (timeout $T cat $a > /tmp/na_$(basename $a).txt 2>/dev/null &) ; done
sleep $T
ping -c 5 -W 2 192.168.10.212 > /tmp/na_ping.txt 2>&1
ip neigh show 192.168.10.212
kill $TD; sleep 1
echo "ping: $(grep -E 'transmitted' /tmp/na_ping.txt)"
for a in ttyACM0 ttyACM1; do echo "UART $a: $(wc -c < /tmp/na_$a.txt) B"; head -c 300 /tmp/na_$a.txt | tr -c '[:print:]\n' '.'; echo; done
echo "src MACs:"; /usr/sbin/tcpdump -n -e -r /tmp/na.pcap 2>/dev/null | awk '{print $2}' | sort | uniq -c | sort -rn
