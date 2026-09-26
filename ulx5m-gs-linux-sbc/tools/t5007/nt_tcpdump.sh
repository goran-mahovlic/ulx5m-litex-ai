#!/bin/bash
# TASK-4999 net test: flash -r, tcpdump (no sudo) from flash on, ping + ip neigh
BIT=$1; T=${2:-20}
echo "### $(date +%T) $BIT"
F="ether src 10:e2:d5:00:00:00 or ether proto 0x88b5 or ether proto 0x88b6 or udp port 4999 or (arp and host 192.168.10.212) or (icmp and host 192.168.10.212)"
/usr/sbin/tcpdump -i eth0 -n -e -l -U -w /tmp/nt.pcap "$F" 2>/tmp/nt_td.err &
TD=$!
sleep 1
sudo -n /usr/local/bin/openFPGALoader -c dirtyJtag "$BIT" -r 2>&1 | grep -E "^Done|fail|rror" | tail -2
sleep $T
ping -c 5 -W 2 192.168.10.212 > /tmp/nt_ping.txt 2>&1 &
for i in $(seq 1 10); do ip neigh show 192.168.10.212; sleep 1; done | sort | uniq -c
wait %2 2>/dev/null; sleep 1
kill $TD; sleep 1
echo "ping: $(grep -E 'transmitted' /tmp/nt_ping.txt)"
/usr/sbin/tcpdump -n -e -r /tmp/nt.pcap 2>/dev/null | awk '{print $2,$3,$4,$6,$7,$8,$9,$10,$11,$12,$13,$14}' | sort | uniq -c | sort -rn | head -15
echo "board-src frames: $(/usr/sbin/tcpdump -n -r /tmp/nt.pcap 'not ether src b8:27:eb:00:00:00/ff:ff:ff:00:00:00' 2>/dev/null | grep -vc 'Request who-has')"
