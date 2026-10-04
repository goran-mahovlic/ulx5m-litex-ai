#!/bin/bash
# autoboot_session.sh (TASK-5224, on the Pi as pi in ~/t5224): A1 np1817 -> SPI flash + proof of automatic Linux boot.
# Starts while gs needs a power cycle (JTAG lost, 04.10. 13:4x) and waits for it. ONE UART reader for the whole session
# (session.uart, restarted after every re-enumeration), no typing into the console at any step.
#   W0  wait for a new DirtyJTAG busdev (= gs power cycle) -> PC1
#   F0  what the OLD flash boots: 90 s UART + ping .213
#   F1  JTAG detect must see the chip, else STOP
#   F2  backup: --dump-flash 4 MiB -> flash_before_T5224.bin (STOP if it fails; nothing written)
#   F3  write np1817 to flash with --verify at 1 MHz JTAG (6 MHz failed verify twice at random offsets, 04.10.)
#       SKIP_FLASH=1 starts at S1 (flash already written).
#   S1,S2  reset = `fpga-jtag gs <np1817> -r` (CFGRST), then wait for "login:" with NO input, Pi pings .213 20x1400 B
#   ST  stability: 300 pings x 1400 B, 1/s, after S2
#   W1  ask for a second power cycle (Telegram via REGOČ = the agent, not here) and wait -> PC2
#   P1  power-on from flash: login with no JTAG load and no input, ping 20x
# Exit codes: 0 all, 3 stop (see session.txt). Marker lines start with "== ".
cd "$(dirname "$(readlink -f "$0")")"
BIT=/home/pi/FPGA/ETH_GateMateA1_2909_1015_Linux_GbE_DVI_USBPNRU_pll60s2_np1817.bit
IP=192.168.10.213; LOG=$PWD/session.uart; SUM=$PWD/session.txt
exec > >(tee -a $SUM) 2>&1
say(){ echo "== $(date +%T) $*"; }
busdev(){ fpga-jtag list | awk '/^gs /{for(i=1;i<=NF;i++) if($i ~ /^busdev=/) print substr($i,8)}'; }
reader(){ kill $RD 2>/dev/null; U=$(fpga-jtag uart gs) || return 1; stty -F $U 115200 raw -echo; cat $U >> $LOG & RD=$!; }
# A moved DirtyJTAG cable also changes busdev (13:36), so busdev is NOT a power-cycle sign:
#   PC1 = the JTAG chain answers again (a design using bank WA hid it); PC2 = .213 stops answering ping, then boots.
jtag_ok(){ timeout 40 sudo fpga-jtag gs --detect 2>&1 | grep -q idcode; }
wait_pc1(){ local t=0; say "PC1: waiting until the JTAG chain answers (board power cycle)"
  until jtag_ok; do sleep 15; t=$((t+15)); [ $t -ge 14400 ] && { say "PC1: none in $t s"; return 1; }; done
  say "PC1: JTAG answers, busdev $(busdev)"; reader; }
wait_pc2(){ local t=0 miss=0; say "PC2: waiting for a board power cycle (.213 stops answering)"
  while [ $miss -lt 3 ]; do if ping -c 1 -W 1 $IP >/dev/null 2>&1; then miss=0; else miss=$((miss+1)); fi
    sleep 2; t=$((t+3)); [ $t -ge 14400 ] && { say "PC2: none in $t s"; return 1; }; done
  say "PC2: board went down"; sleep 4; reader; }
wait_login(){ local from=$1 lim=$2 t=0
  while [ $t -lt $lim ]; do sleep 2; t=$((t+2)); kill -0 $RD 2>/dev/null || reader; tail -c +$from $LOG | grep -aq "login:" && { echo $t; return 0; }; done; echo FAIL; return 1; }
snap(){ curl -s -m 10 -o $PWD/dvi_$1.jpg http://127.0.0.1:8090/snap.jpg; python3 -c "from PIL import Image; im=Image.open('$PWD/dvi_$1.jpg').convert('L'); print('   DVI $1 luma min/max', im.getextrema())" 2>&1 | tail -1; }
pings(){ ping -c ${1:-20} -s 1400 -i ${2:-0.5} $IP | tail -2 | tr '\n' ' '; echo; }
trap 'kill $RD 2>/dev/null' EXIT
say "session start, bit $(sha256sum $BIT | cut -c1-16)"
if [ -z "$SKIP_FLASH" ]; then
wait_pc1 || exit 3
say "F0 old flash: 90 s UART + ping"; o=$(stat -c %s $LOG); sleep 90
echo "   UART bytes since power-on: $(( $(stat -c %s $LOG) - o ))"; tail -c +$((o+1)) $LOG | tr -d '\033' | tr '\r' '\n' | grep -a -v '^$' | tail -5
ping -c 3 -W 1 $IP | tail -2 | tr '\n' ' '; echo
say "F1 detect"; d=$(timeout 60 sudo fpga-jtag gs --detect 2>&1); echo "$d" | grep -E "idcode|model"
echo "$d" | grep -q idcode || { say "STOP F1: JTAG chain empty"; exit 3; }
say "F2 flash backup"; timeout 1800 sudo fpga-jtag gs --dump-flash --file-size 4194304 $PWD/flash_before_T5224.bin 2>&1 | grep -v -E "^\s*$|\[" | tail -4
[ "$(stat -c %s flash_before_T5224.bin 2>/dev/null)" = 4194304 ] || { say "STOP F2: backup missing/short, flash NOT written"; exit 3; }
sudo chown pi:pi flash_before_T5224.bin; sha256sum flash_before_T5224.bin
say "F3 write np1817 to flash (--verify)"; w=$(timeout 3600 sudo fpga-jtag gs -f --verify --freq 1000000 $BIT 2>&1); echo "$w" | grep -v -E "^\s*$" | grep -v "\[" | tail -8
echo "$w" | grep -qiE "error|fail" && { say "STOP F3: write/verify error"; exit 3; }
echo "$w" | grep -qiE "verify.*(ok|done|success)|Done" || { say "STOP F3: no success line"; exit 3; }
else say "SKIP_FLASH: flash already written + verified (F3c.txt, flash_after_T5224.bin = bit)"; reader; fi
for n in 1 2; do
  say "S$n reset: fpga-jtag gs <np1817> -r (CFGRST), no input afterwards"; o=$(( $(stat -c %s $LOG) + 1 ))
  sudo fpga-jtag gs $BIT -r 2>&1 | grep -E "^Done|rror" | tail -1
  t=$(wait_login $o 600); say "S$n login after: $t s"; [ "$t" = FAIL ] && exit 3
  sleep 20; snap S$n; echo -n "   S$n Pi -> board: "; pings 20 0.5
done
say "ST stability 300 s (ping 1400 B every 1 s, no input)"; echo -n "   "; pings 300 1
say "W1 flash proof needs a second power cycle (no JTAG load after it)"
wait_pc2 || exit 3
o=$(( $(stat -c %s $LOG) + 1 )); t=$(wait_login $o 600); say "P1 power-on from flash, login after: $t s"; [ "$t" = FAIL ] && exit 3
sleep 20; snap P1; echo -n "   P1 Pi -> board: "; pings 20 0.5
tail -c +$o $LOG | tr -d '\033' | tr '\r' '\n' | grep -a -E "Memtest|Booting|Linux version|IP-Config|fb0|login" | head -12
say "SESSION_OK"
