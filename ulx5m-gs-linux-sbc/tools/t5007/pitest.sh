#!/bin/bash
# t5007 Pi test: flash (SRAM only), 20 s, UART, PLL status/ft, ping, neigh, tcpdump
BIT=$1; NET=${2:-1}
cd ~
stty -F /dev/ttyACM0 115200 raw -echo; timeout 2 cat /dev/ttyACM0 >/dev/null
echo "### $(date +%T) flash $BIT"
sudo -n /usr/local/bin/openFPGALoader -c dirtyJtag "$BIT" -r 2>&1 | grep -iE "done|error|fail|100" | tail -2
sleep 3; timeout 1 cat /dev/ttyACM0 >/dev/null
sleep 17
echo "### UART (4 s)"; timeout 4 cat /dev/ttyACM0 > /tmp/t5007_uart.bin; wc -c < /tmp/t5007_uart.bin; tr -c '[:print:]\n' '?' < /tmp/t5007_uart.bin | tail -c 600; echo
echo "### PLL status"
for i in 1 2 3; do timeout 30 python3 -c "import jtag_mailbox as jm; e,t=jm.load_tool(); print(jm.pll(t))" 2>&1 | tail -1; done
timeout 40 python3 pll_serial_rx.py scan 2>&1 | tail -4
[ "$NET" = 0 ] && exit 0
echo "### net"
echo klaudio | sudo -S -p '' timeout 16 tcpdump -i eth0 -n -e -c 50 'ether proto 0x88b5 or ether proto 0x88b6 or arp or ether host 10:e2:d5:00:00:00 or udp port 4999' > /tmp/t5007_td.txt 2>/tmp/t5007_td.err &
sleep 1
ip neigh flush 192.168.10.212 2>/dev/null
ping -c 5 -W 2 192.168.10.212 | tail -2
ip neigh show 192.168.10.212
wait
echo "tcpdump: $(grep -c . /tmp/t5007_td.txt) lines; from FPGA MAC: $(grep -c '^.\{16\}10:e2:d5:00:00:00' /tmp/t5007_td.txt)"
grep -v "Request who-has 192.168.10.212 tell 192.168.10.14" /tmp/t5007_td.txt | head -6
tail -1 /tmp/t5007_td.err
