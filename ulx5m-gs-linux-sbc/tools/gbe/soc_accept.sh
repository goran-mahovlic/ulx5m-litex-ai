#!/bin/bash
# TASK-5033 (runs on the Pi): soc_accept.sh <dirty_bit> <soc_bit> [memtest_wait_s]
# One acceptance attempt of the phase-2 SoC: load a different ("dirty") design, then the SoC with -r, and in
# one UART window: BIOS banner, `mem_test` over the whole 64 MiB, `sdcard_init` (LiteSDCard present; "no card"
# is fine), time to the first ping reply after the load, ping -s sweep 5/5, Etherbone CSR read.
# Output: /tmp/sa_* files + summary on stdout.
DIRTY=$1; BIT=$2; MW=${3:-150}; IP=192.168.10.212; U=/dev/ttyACM0
rm -f /tmp/sa_*
# SEND: one character per 20 ms (a burst lost characters: "sdcard_init" arrived as "sdId_init", TASK-5033)
SEND() { local c="$1"; for ((i=0; i<${#c}; i++)); do printf "%s" "${c:$i:1}" > $U; sleep 0.02; done; printf "\r" > $U; }
LOAD() { sudo -n /usr/local/bin/openFPGALoader -c dirtyJtag "$1" -r 2>&1 | grep -E "^Done|rror" | tail -1; }
echo "dirty: $(basename $DIRTY) -> $(LOAD $DIRTY)"
sleep 3
# another user (ttyACM0 open elsewhere) invalidates the attempt
fuser $U 2>/dev/null && { echo "ttyACM0 BUSY - attempt invalid"; exit 2; }
stty -F $U 115200 raw -echo; timeout 2 cat $U >/dev/null 2>&1          # E4: drop the stale UART buffer
ip neigh del $IP dev eth0 2>/dev/null
echo "soc:   $(basename $BIT) -> $(LOAD $BIT)"
T0=$(date +%s.%N)
timeout $((MW+30)) cat $U > /tmp/sa_uart.txt 2>/dev/null & CP=$!
ping -D -i 0.2 -W 1 -c 100 $IP > /tmp/sa_ping0.txt 2>&1 & PP=$!
# wait for the BIOS console: with --boot netboot the boot sequence (TFTP, serialboot timeout) takes ~10 s and
# swallows characters sent earlier ("000 0x4000000" -> Command not found, TASK-5033)
for ((t=0; t<30; t++)); do grep -aq "Console" /tmp/sa_uart.txt && break; sleep 1; done
sleep 1; SEND ""; sleep 1
SEND "mem_test 0x40000000 0x4000000"
# the 64 MiB mem_test takes ~78 s at 20 MHz (UART progress output); 1472 B pings lose frames WHILE it runs
# (TASK-5033 timed.py), so wait for its "Memtest OK" (2nd one; the 1st is the BIOS boot test) before the sweep
for ((t=0; t<MW; t++)); do [ $(grep -ac "Memtest OK" /tmp/sa_uart.txt) -ge 2 ] && break; sleep 1; done
echo "mem_test finished $(python3 -c "import time; print(round(time.time() - $T0, 1))") s after load"
SEND "sdcard_init"
sleep 8
wait $PP
kill $CP 2>/dev/null     # UART window closed before the sweep (by PID: pkill -f also matches the calling ssh shell)
FIRST=$(grep -m1 "bytes from" /tmp/sa_ping0.txt | sed 's/^\[\([0-9.]*\)\].*/\1/')
[ -n "$FIRST" ] && echo "first ping reply after load: $(python3 -c "print(round($FIRST - $T0, 2))") s" \
                || echo "first ping reply after load: NONE"
echo "ping0: $(grep -c 'bytes from' /tmp/sa_ping0.txt)/100 replies"
for s in 0 18 56 100 1000 1472; do
  echo "ping -s $s: $(ping -c 5 -W 1 -i 0.3 -s $s $IP 2>&1 | grep transmitted | sed 's/, time.*//')"
done
echo "ping -s 1472 x20: $(ping -c 20 -W 1 -i 0.2 -s 1472 $IP 2>&1 | grep transmitted | sed 's/, time.*//')"
python3 ~/FPGA/eb_read.py $IP 0xf0000004 2>&1 | tail -1
C=$(tr '\r' '\n' < /tmp/sa_uart.txt | tr -c '[:print:]\n' '.' | sed 's/\.\[[0-9;]*m//g')
echo "UART $(wc -c < /tmp/sa_uart.txt) B:"
echo "$C" | grep -E "CPU|BUS|CSR|SDRAM|MAIN-RAM|Memtest|64.0MiB|rror|SD|sdcard|litex>|Card|card" | grep -v "Read: 0x40000000-0x43" | head -30
