#!/bin/bash
# TASK-5007 net test without root: flash -r, 20 s, UART, beacon_rx (UDP 4999), ping + ip neigh each second
BIT=$1
stty -F /dev/ttyACM0 115200 raw -echo; timeout 2 cat /dev/ttyACM0 >/dev/null
echo "### $(date +%T) $BIT"
sudo -n /usr/local/bin/openFPGALoader -c dirtyJtag "$BIT" -r 2>&1 | grep -E "^Done|fail" | tail -1
sleep 3; timeout 1 cat /dev/ttyACM0 >/dev/null; sleep 17
timeout 4 cat /dev/ttyACM0 > /tmp/t5007_uart.bin; echo "UART: $(wc -c < /tmp/t5007_uart.bin) B $(tr -c '[:print:]' '?' < /tmp/t5007_uart.bin | head -c 120)"
python3 /tmp/beacon_rx.py 12 > /tmp/t5007_bc.txt 2>&1 &
ping -c 5 -W 2 192.168.10.212 > /tmp/t5007_ping.txt 2>&1 &
for i in $(seq 1 12); do ip neigh show 192.168.10.212; sleep 1; done | sort | uniq -c
wait
echo "ping: $(grep -E 'transmitted' /tmp/t5007_ping.txt)"
echo "beacon: $(tail -1 /tmp/t5007_bc.txt) $(grep -v beacons /tmp/t5007_bc.txt | head -2 | tr '\n' ' ')"
