#!/usr/bin/env bash
# Flash the CPU-less UDP-echo bitstream into ULX5M-GS SRAM over dirtyJTAG on the
# RPi programmer host, then run the network smoke test FROM that host.
#
# Usage: test_script/flash_and_test_remote.sh [bitstream] [fpga-ip] [udp-port]
# Exit: 0 = FPGA answered ICMP + UDP echo, 1 = flash failed, 2 = FPGA silent.
set -u
BIT="${1:-build/litex_eth_192.168.10.212.bit}"
IP="${2:-192.168.10.212}"
PORT="${3:-7000}"
REMOTE="${REMOTE:-fpga-klaudio@192.168.10.14}"
RDIR="${RDIR:-/home/fpga-klaudio/FPGA}"
LOADER="${LOADER:-/usr/local/bin/openFPGALoader}"

[ -f "$BIT" ] || { echo "no bitstream: $BIT"; exit 1; }
echo "local  md5: $(md5sum "$BIT" | cut -d' ' -f1)  ($(stat -c%s "$BIT") B)"
scp -q "$BIT" "$REMOTE:$RDIR/" || { echo "scp failed"; exit 1; }
REMOTE_BIT="$RDIR/$(basename "$BIT")"
echo "remote md5: $(ssh "$REMOTE" "md5sum $REMOTE_BIT" | cut -d' ' -f1)"

# SRAM (-r) only. NEVER -f here: SPI flash writes are slow and persistent.
ssh "$REMOTE" "sudo -n $LOADER -c dirtyJtag $REMOTE_BIT -r" || { echo "flash failed"; exit 1; }

# 20 s minimum: PLL lock, PHY reset release, auto-negotiation, link, ARP.
ssh "$REMOTE" "
  sleep 30
  ping -c 5 -W 2 $IP; ping_rc=\$?
  echo '--- neigh ---'; ip neigh show $IP
  echo '--- udp echo ---'
  python3 -c \"
import socket
s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM); s.settimeout(3)
try:
    s.sendto(b'Test',('$IP',$PORT)); print('UDP-OK', s.recvfrom(1024))
except Exception as e: print('UDP-FAIL', type(e).__name__)
\"
  exit \$ping_rc
" && exit 0

echo "FPGA silent at $IP — check LED7 (heartbeat) and LED1 (link) on the board."
exit 2
