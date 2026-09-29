#!/bin/bash
# a2_session.sh <soc1.bit> [<soc2.bit> ...] (TASK-5094, on the Pi as fpga-klaudio in ~/t5094, right after a power
# cycle of gs; pre-registered in A2_CCGM1A2_TASK-5092.md §5.9). Stops at the first miss.
#   P1  a2_board_once.sh soc1 (fresh chip): BIOS memtest -> netboot Linux 6.12 -> login/ping/USB/DVI (STAB=<s> adds the
#       30 min stability test). Its result is the Linux/Ethernet answer and does not depend on anything below.
#   R1  "R!" on the console (selfrst in the SoC pulls IO_SB_B8 = RST_N): proof of a reset = the board stops answering
#       ping (a Linux console may stay silent anyway, so UART silence proves nothing).
#   S1  ~/t5095 sr_x_nr.bit (another layout) on the chip after R1: "E00000000 K0000000B" = R! returns the chip to the
#       power-on state (H7 flow fix); silent = R! is not enough (only 1A reset? too short?) -> NEEDS_POWER_CYCLE, stop.
#   R2  "R!" to sr_x, then every further <socN.bit> through a2_board_once.sh, each followed by "R!" again.
# The power-cycle marker is shared with ~/t5095 (MARK_FILE), so every series there sees a miss from here.
cd "$(dirname "$(readlink -f "$0")")"
export MARK_FILE=$HOME/t5095/NEEDS_POWER_CYCLE
. ./preflight.sh; preflight || exit 3
IP=192.168.10.213
alive(){ ping -c 3 -W 1 -i 0.5 $IP >/dev/null 2>&1; }
rbang(){   # R! and prove the SoC is gone: it answered ping before (if it had Linux), must not after
  local before=0; alive && before=1
  (cd ~/t5095 && ./sr_reset.sh 3) | head -3
  sleep 2; if alive; then echo "STOP $1: board still answers ping after R!"; mark_wedged "TASK-5094 $1 R! did not reset"; exit 1; fi
  echo "$1: R! ok (ping before=$before, after=0)"
}
first=$1; shift
./a2_board_once.sh "$first" P1_$(basename "$first" .bit); rc=$?
echo "P1 exit=$rc (0 login, 5 BIOS only, 4 silent)"; [ $rc -eq 4 ] && exit 4
rbang R1
o=$(cd ~/t5095 && ./uart_nr.sh sr_x_nr.bit 3); echo "S1 $o"
echo "$o" | grep -q "E00000000 K0000000B" || { echo "STOP S1: sr_x after R! not as on a fresh chip"; mark_wedged "TASK-5094 S1 sr_x after SoC+R! silent"; exit 1; }
echo "S1 OK: R! after a SoC returns the chip to the power-on state"
(cd ~/t5095 && ./sr_reset.sh 2) | head -2
n=2
for b in "$@"; do
  STAB= ./a2_board_once.sh "$b" P${n}_$(basename "$b" .bit); rc=$?
  echo "P$n exit=$rc"; [ $rc -eq 4 ] && exit 4
  rbang R$n; n=$((n+1))
done
echo "SESSION_OK"
