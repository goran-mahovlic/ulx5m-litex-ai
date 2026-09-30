#!/bin/bash
# a2_board_once_test.sh (TASK-5094): offline test of tools/a2_board_once.sh with stubbed probe/UART/ping/netboot.
# Cases: console reaches "login:" -> exit 0; BIOS prompt only -> exit 5; no output -> exit 4 + power-cycle marker;
# lease with a power-cycle note and no re-enumeration -> exit 3 without loading.
H=$(cd "$(dirname "$0")/.." && pwd); W=$(mktemp -d -p "${TMPDIR:-$HOME/.tmp}"); nok=0; nbad=0
cp $H/a2_board_once.sh $W/; cp $H/../docs/nextpnr_a2_repro/die1b_ff_t5095/preflight.sh $W/

mkdir -p $W/home/FPGA $W/bin; printf '#!/bin/sh\nexit 0\n' > $W/home/FPGA/netboot_app.sh; chmod +x $W/home/FPGA/netboot_app.sh
printf '#!/bin/sh\necho "3 packets transmitted, 3 received, 0%% packet loss"\n' > $W/bin/ping; chmod +x $W/bin/ping
printf '#!/bin/sh\necho "[    5.000000] usb 1-1: Product: DirtyJTAG"\n' > $W/bin/dmesg; chmod +x $W/bin/dmesg
run(){ # $1 canned console text, $2 expected exit, $3 name, $4 lease text
  rm -f $W/mark $W/loaded; : > $W/uart; echo "$4" > $W/lease
  cat > $W/dj_probe.sh <<EOS
DJ_UART=$W/uart
dj_load(){ touch $W/loaded; printf '%b' "$1" >> \$LOG; echo "\${LOADOUT:-Done}"; }   # the console "arrives" in the capture
EOS
  (cd $W && HOME=$W/home NETBOOT=$W/home/FPGA/netboot_app.sh PATH=$W/bin:$PATH OWNER_FILE=$W/lease MARK_FILE=$W/mark W=0 D=0 SILENT_S=4 HANG_S=6 BOOT_WAIT=20 \
     ./a2_board_once.sh ${BITARG:-$W/a2_board_once.sh} case >/dev/null 2>&1); rc=$?
  local extra=ok
  [ "$2" = 4 ] && { [ -s $W/mark ] || extra="no-marker"; }
  [ "$2" = 3 ] || [ "$2" = 2 ] && { [ -e $W/loaded ] && extra="loaded-anyway"; }
  [ "$2" = 2 ] || [ "$2" = 6 ] || [ "$2" = 7 ] && { [ -s $W/mark ] && extra="marker-written"; }
  if [ $rc = $2 ] && [ $extra = ok ]; then nok=$((nok+1)); echo "ok   $3 (exit $rc)"
  else nbad=$((nbad+1)); echo "FAIL $3: exit $rc want $2, $extra"; fi
}
run 'Memtest OK\r\nBooting from network...\r\nbuildroot login: ' 0 "login" "klaudio 1 x gs"
run 'Memtest OK\r\nNetwork boot failed.\r\nlitex> ' 5 "bios only" "klaudio 1 x gs"
run 'Network boot failed.\r\n\033[92;1mlitex\033[0m> ' 5 "bios only, ANSI prompt" "klaudio 1 x gs"
run '' 4 "silent" "klaudio 1 x gs"
run 'Memtest at 0x40000000 (2.0MiB)...\r\n  Write: 0x40000000' 7 "console stops (hang): no marker" "klaudio 1 x gs"
run 'litex> ' 3 "preflight stops a wedged chip" "jelena $(date +%s) x gs NEEDS POWER CYCLE"
BITARG=/nonexistent.bit run 'litex> ' 2 "missing bitstream: no load, no marker" "klaudio 1 x gs"
LOADOUT="Error: fail to open" run 'litex> ' 6 "load error: no marker" "klaudio 1 x gs"
rm -rf $W; echo "a2_board_once_test: $nok ok, $nbad fail"; [ $nbad = 0 ]
