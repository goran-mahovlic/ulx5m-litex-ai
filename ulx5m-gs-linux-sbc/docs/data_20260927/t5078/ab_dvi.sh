#!/bin/bash
# TASK-5078: ab_dvi.sh <bit> <csr.csv> <tag> - the TASK-5047 ab3.sh procedure (grec_3 baseline, SBC_DVI_USB_TASK-5047.md §2.4)
# repeated after the 1 uF caps on GS (C42 VDD_PLL). Container side. Same steps: BIOS -> test image -> re-arm STDY -> 20 s idle ->
# 2x mem_test 32 MiB with 30 grabber snapshots (4 s) -> counters. Differences to ab3.sh: load through fpga-jtag and the gs
# by-id console (FPGA_LAB_ARHITEKTURA.md §3), not openFPGALoader -c dirtyJtag / ttyACM0.
BIT=$1; CSV=$2; n=$3; D=$(dirname "$(readlink -f "$0")")/ab_$n; mkdir -p $D; rm -f $D/*
PI=fpga-klaudio@192.168.10.14; SBC=$(cd "$(dirname "$(readlink -f "$0")")/../../.." && pwd)
csr() { awk -F, -v k="$1" '$1=="csr_register" && $2==k {print $3}' "$CSV"; }
UA=$(csr main_pll_sys_unlocks); RC=$(csr main_video_recoveries); SR=$(csr main_pll_stdy_rst); FA=$(csr video_fb2x_frames)
NH=1; grep -q "csr_base,ethmac" "$CSV" && NH=
ssh $PI "mkdir -p /tmp/t5078"
scp -q "$BIT" $PI:/tmp/t5078/ab_$n.bit
scp -q $SBC/tools/dj_probe.sh $SBC/tools/sd/bios_cmds.sh $SBC/tools/dvi/testimg_cmds.sh $PI:/tmp/t5078/
ssh $PI "cat > /tmp/t5078/uart_cmd.sh" <<'UEOF'
#!/bin/bash
# type commands into the running BIOS of gs (no load), print the answer
. /tmp/t5078/dj_probe.sh; U=$DJ_UART; fuser $U >/dev/null 2>&1 && { echo BUSY; exit 2; }
stty -F $U 115200 raw -echo
cat $U > /tmp/t5078/uc.txt & CP=$!
SEND() { local c="$1"; for ((i=0; i<${#c}; i++)); do printf "%s" "${c:$i:1}" > $U; sleep 0.03; done; printf "\r" > $U; }
SEND ""; sleep 0.5
for c in "$@"; do SEND "$c"; sleep ${W:-1}; done
kill $CP; tr '\r' '\n' < /tmp/t5078/uc.txt | tr -c '[:print:]\n' '.'
UEOF
echo "bit sha256 $(sha256sum "$BIT" | cut -c1-16) csr sys_unl=$UA rec=$RC stdy_rst=$SR frames=$FA"
snap() { curl -s -m 8 -o $D/$1.jpg http://192.168.10.14:8090/snap.jpg; python3 -c "
from PIL import Image; im=Image.open('$D/$1.jpg').convert('RGB'); u=len(set(im.resize((32,24)).getdata())); print('$1', 'colours', u, 'px', im.getpixel((320,15)), im.getpixel((320,300)))" 2>/dev/null || echo "$1 no-snap"; }
rd() { ssh $PI "W=2 bash /tmp/t5078/uart_cmd.sh 'mem_read $UA 12' 'mem_read $FA 12' 'mem_read $RC 4'" | grep -a "^0x" | sed "s/^/$1 /"; }
ssh $PI "cd /tmp/t5078 && mapfile -t T < <(bash testimg_cmds.sh); NOHIDE=$NH WAIT=1 CONSOLE_WAIT=90 TAILN=5 timeout 200 bash bios_cmds.sh /tmp/t5078/ab_$n.bit \"\${T[@]}\"" | tail -2
sleep 3; snap t0_testimg; rd t0
ssh $PI "W=1 bash /tmp/t5078/uart_cmd.sh 'mem_write $SR 1' 'mem_write $SR 0'" >/dev/null
sleep 20; snap t20_idle; rd t20_idle
ssh $PI "W=70 bash /tmp/t5078/uart_cmd.sh 'mem_test 0x41000000 0x2000000' 'mem_test 0x41000000 0x2000000'" | grep -a -i "memtest\|error\|OK" | tail -2 &
for i in $(seq -w 1 30); do sleep 4; snap load_$i; done; wait
rd after_load; sleep 3; snap after
