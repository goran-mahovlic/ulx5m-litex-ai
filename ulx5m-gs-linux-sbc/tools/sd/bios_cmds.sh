#!/bin/bash
# TASK-5039: bios_cmds.sh <bit> "<cmd1>" "<cmd2>" ... : load a SoC bitstream (-r), wait for the BIOS console and type
# each command (30 ms per character; faster loses characters, lesson J-UART). Runs on the Pi as fpga-klaudio.
# NOHIDE=1 keeps /srv/tftp as is; by default boot.json/boot.bin are hidden so netboot fails and the console appears.
. "$(dirname "$(readlink -f "$0")")/dj_probe.sh" 2>/dev/null || . "$(dirname "$(readlink -f "$0")")/../dj_probe.sh"   # flat copy on the Pi, or this repo
BIT=$1; shift; T=/srv/tftp; W=${WAIT:-8}; U=$DJ_UART
fuser $U >/dev/null 2>&1 && { echo "$U BUSY"; exit 2; }
restore() { for f in boot.json boot.bin; do [ -f $T/$f.t5039 ] && mv $T/$f.t5039 $T/$f; done; }
if [ -z "$NOHIDE" ]; then trap restore EXIT; for f in boot.json boot.bin; do [ -f $T/$f ] && mv $T/$f $T/$f.t5039; done; fi
SEND() { local c="$1"; for ((i=0; i<${#c}; i++)); do printf "%s" "${c:$i:1}" > $U; sleep 0.03; done; printf "\r" > $U; }
stty -F $U 115200 raw -echo; timeout 2 cat $U >/dev/null 2>&1
dj_load "$BIT"
cat $U > /tmp/bios_cmds.txt 2>/dev/null & CP=$!
for ((t=0; t<${CONSOLE_WAIT:-90}; t++)); do grep -aq "litex>" /tmp/bios_cmds.txt && break; sleep 1; done
sleep 1; SEND ""; sleep 1
for c in "$@"; do SEND "$c"; sleep $W; done
kill $CP 2>/dev/null
tr '\r' '\n' < /tmp/bios_cmds.txt | tr -c '[:print:]\n' '.' | sed 's/\.\[[0-9;]*m//g' | grep -av "^\.*$" | tail -${TAILN:-80}
