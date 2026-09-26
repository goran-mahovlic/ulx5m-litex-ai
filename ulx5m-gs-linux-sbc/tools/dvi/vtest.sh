#!/bin/bash
# vtest.sh <local bit> <tag>: load on the board (BIOS console, netboot hidden), paint bands, read FrameBuffer2x
# counters 3x (5 s apart) and take 12 HDMI-capture snapshots (every 3 s) -> ~/.tmp/t5040/vt_<tag>/
BIT=$1; TAG=$2; D=~/.tmp/t5040/vt_$TAG; mkdir -p $D; rm -f $D/*
scp -q $BIT fpga-klaudio@192.168.10.14:/tmp/vt_$TAG.bit
C="mem_read 0xf0003818 12"
( ssh fpga-klaudio@192.168.10.14 "cd /tmp && mapfile -t T < <(bash t5040_testimg.sh); WAIT=3 CONSOLE_WAIT=40 TAILN=30 timeout 200 bash t5040_bios_cmds.sh /tmp/vt_$TAG.bit \"\${T[@]}\" \"$C\" \"$C\" \"$C\" \"$C\"" > $D/uart.txt 2>&1 ) &
sleep 35
for i in $(seq -w 1 12); do curl -s -m 5 -o $D/s_$i.jpg http://192.168.10.14:8090/snap.jpg; sleep 3; done
wait
grep -A1 "0xf0003818" $D/uart.txt | grep "^0x" ; ls -la $D | awk '{print $5}' | grep -v "^$" | tr '\n' ' '; echo
