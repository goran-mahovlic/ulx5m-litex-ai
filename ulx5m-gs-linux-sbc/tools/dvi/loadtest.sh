#!/bin/bash
# loadtest.sh <bit> <tag> <unlock_addr> <fb2x_frames_addr>: bands, counters, 3x mem_test (SDRAM load) with capture, counters
BIT=$1; TAG=$2; UA=$3; FA=$4; D=~/.tmp/t5040/lt_$TAG; mkdir -p $D; rm -f $D/*
scp -q $BIT fpga-klaudio@192.168.10.14:/tmp/lt_$TAG.bit
R="mem_read $UA 8"; F="mem_read $FA 12"
( ssh fpga-klaudio@192.168.10.14 "fuser -k /dev/ttyACM0 >/dev/null 2>&1; sleep 1; cd /tmp && mapfile -t T < <(bash t5040_testimg.sh); NOHIDE=1 WAIT=1 CONSOLE_WAIT=40 TAILN=400 timeout 260 bash t5040_bios_cmds.sh /tmp/lt_$TAG.bit \"\${T[@]}\" \"$R\" \"$F\" 'mem_test 0x41000000 0x2000000' 'mem_test 0x41000000 0x2000000' \"$R\" \"$F\"" > $D/uart.txt 2>&1 ) &
sleep 30
~/.tmp/t5040/idle_series.sh $D/cap 40 2 >/dev/null
wait
grep -aA1 -E "mem_read ($UA|$FA)" $D/uart.txt | grep -a "^0x"
cd $D/cap && python3 - <<'PY' 2>/dev/null
from PIL import Image
import glob
s='';ns=0
for f in sorted(glob.glob('l_*.jpg')):
    px=set(Image.open(f).convert('RGB').resize((32,24)).getdata())
    if len(px)==1 and list(px)[0][0] in range(5,10): s+='N'; ns+=1
    elif len(px)<=2 and max(max(p) for p in px)<5: s+='b'
    else: s+='.'
print(s, 'nosignal', ns)
PY
