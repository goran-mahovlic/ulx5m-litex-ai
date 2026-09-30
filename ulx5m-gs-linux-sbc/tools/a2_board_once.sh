#!/bin/bash
# a2_board_once.sh <bit> [tag] (TASK-5094, runs on the Pi as fpga-klaudio in ~/t5094 next to preflight.sh/dj_probe.sh):
# ONE load of an A2 SoC on gs per power cycle (a reload of another layout over a running A2 design wedges the chip,
# A2_CCGM1A2_TASK-5092.md §5.7-§5.8). The BIOS runs its memtest and netboots Linux 6.12 (boot.json "linux").
#   - "login:"  -> log in, eth0 up, ping the Pi, USB/DVI/dmesg checks, Pi pings the board;
#                  STAB=<s> then runs the TASK-5091 stability test: SDRAM load loop on the board + Pi ping for <s> s.
#   - "litex>"  -> netboot failed: BIOS diagnostics (PHY status, RXC counter, MAC counters), no reload.
#   - no output for 40 s after the load -> the chip is wedged: write ./NEEDS_POWER_CYCLE and stop (exit 4).
# Exit: 0 login, 5 BIOS only, 7 console stopped (CPU hang), 4 silent (marker written), 3 preflight stop, 2 no bitstream,
# 6 load failed.
# Log: ./<tag>.uart (raw console) and ./<tag>.txt (summary). Board IP 192.168.10.213 (tools/linux/README.md).
cd "$(dirname "$(readlink -f "$0")")"
BIT=$1; TAG=${2:-$(basename "$BIT" .bit)}; LOG=$PWD/$TAG.uart; SUM=$PWD/$TAG.txt
[ -r "$BIT" ] || { echo "no bitstream $BIT"; exit 2; }
export MARK_FILE=${MARK_FILE:-$HOME/t5095/NEEDS_POWER_CYCLE}   # shared with the ~/t5095 series
. ./preflight.sh; preflight || exit 3
DJ_LOAD_ARGS="--index-chain 0"; . ./dj_probe.sh; U=$DJ_UART
fuser $U >/dev/null 2>&1 && { echo "$U BUSY"; exit 2; }
exec > >(tee $SUM) 2>&1
echo "== $TAG $(date '+%F %T') sha256 $(sha256sum "$BIT" | cut -c1-16)"
# boot.json = Linux 6.12 (Goran's default); the pi copy is current, the agent copy in ~/FPGA writes the old 5.14 set
${NETBOOT:-/home/pi/FPGA/netboot_app.sh} linux >/dev/null 2>&1 || true
stty -F $U 115200 raw -echo; timeout 2 cat $U >/dev/null 2>&1
cat $U > $LOG 2>/dev/null & CP=$!      # capture from before the load: the BIOS memtest line comes right after it
trap 'kill $CP 2>/dev/null' EXIT
L=$(dj_load "$BIT"); echo "load: $L"; T0=$(date +%s)
# only a load that reports Done can wedge the chip; anything else is reported without the power-cycle marker
case "$L" in Done*) ;; *) echo "LOAD FAILED (no marker; check fpga-jtag gs --detect --index-chain 0)"; exit 6 ;; esac
TYPE() { local c="$1"; for ((i=0; i<${#c}; i++)); do printf "%s" "${c:$i:1}" > $U; sleep ${D:-0.08}; done; printf "\r" > $U; }
SHOW() { tr '\r' '\n' < $LOG | tr -c '[:print:]\n' '.' | sed 's/\.\[[0-9;]*m//g' | grep -av "^\.*$" | tail -${1:-40}; }
state=silent; sz=0; still=0
for ((t=0; t<${BOOT_WAIT:-600}; t+=2)); do
  sleep 2
  grep -aq "login:" $LOG && { state=login; break; }
  tr -d '\033' < $LOG | sed 's/\[[0-9;]*m//g' | grep -aq "litex>" && { state=bios; break; }   # prompt is ANSI-coloured
  [ $t -ge ${SILENT_S:-40} ] && [ ! -s $LOG ] && break
  # output started and then stopped: the design runs (selfrst works), the CPU hangs -> no power-cycle marker
  n=$(stat -c %s $LOG); if [ "$n" -gt 0 ] && [ "$n" = "$sz" ]; then still=$((still+2)); else still=0; sz=$n; fi
  [ $still -ge ${HANG_S:-150} ] && { state=hang; break; }
done
echo "state after $(( $(date +%s) - T0 )) s: $state"
case $state in
  silent)
    mark_wedged "TASK-5094 $TAG: no console output 40 s after the load"; echo "SILENT -> marked NEEDS_POWER_CYCLE"; exit 4 ;;
  hang)
    echo "HANG: console stopped after $(stat -c %s $LOG) bytes (no marker: the design runs, use R! before the next load)"
    SHOW 12; exit 7 ;;
  bios)
    D=0.03 TYPE ""; sleep 1
    for c in "mem_read 0xf0002804 8" "ident"; do D=0.03 TYPE "$c"; sleep 3; done
    SHOW 70; exit 5 ;;
esac
SHOW 100000 | grep -aE "Memtest|Booting|Local IP|Remote IP|Copying|Executing|Linux version|login" || true
sleep 3; TYPE root; sleep 6
for c in "uname -a" "ip addr add 192.168.10.213/24 dev eth0; ip link set eth0 up" "ping -c 5 192.168.10.14" \
         "cat /proc/bus/input/devices | grep -E 'Name|Handlers'" "ls /dev/fb* /dev/input/" \
         "dmesg | grep -ciE 'error|fail|oops'" "dmesg | grep -iE 'fb0|litex|usb|eth0' | tail -12"; do
  TYPE "$c"; sleep ${W:-8}
done
echo "--- Pi -> board"; ping -c 20 -s 1400 -i 0.5 192.168.10.213 | tail -3
if [ -n "$STAB" ]; then
  TYPE "dd if=/dev/urandom of=/tmp/r bs=1M count=8 2>/dev/null; (while true; do cat /tmp/r > /tmp/c; md5sum /tmp/c > /dev/null; done) &"
  sleep 5; echo "--- stability $STAB s: SDRAM load loop + ping 1400 B every 1 s"
  ping -c $STAB -s 1400 -i 1 192.168.10.213 | tail -3
  TYPE "uptime"; sleep 4; TYPE "dmesg | grep -ciE 'error|fail|oops'"; sleep 4
fi
SHOW 60
