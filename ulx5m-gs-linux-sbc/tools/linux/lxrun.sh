#!/bin/bash
# lxrun.sh <bit> <dtb> <rootfs> [secs] "<shell cmd>"... (runs on the Pi, TASK-5047/5051): netboot Linux with
# Image + <dtb> + <rootfs> + opensbi.bin from /srv/tftp, wait for the login prompt, log in as root, type the commands
# (80 ms per character, W seconds after each, default 6) and print the UART log (also in /tmp/lx_run.txt).
# TFTP goes back to `linux` mode at the end. IMAGE/SBI env: kernel and OpenSBI file names (default Image, opensbi.bin). The bitstream must be packed with `gmpack --reset`.
. "$(dirname "$(readlink -f "$0")")/dj_probe.sh" 2>/dev/null || . "$(dirname "$(readlink -f "$0")")/../dj_probe.sh"
BIT=$1; DTB=$2; RFS=$3; T=${4:-600}; shift 4; U=$DJ_UART
fuser $U 2>/dev/null && { echo "$U BUSY"; exit 2; }
rm -f /srv/tftp/boot.json 2>/dev/null
printf '{\n  "%s": "0x40000000",\n  "%s": "0x40ef0000",\n  "%s": "0x41000000",\n  "%s": "0x40f00000"\n}\n' \
    "${IMAGE:-Image}" "$DTB" "$RFS" "${SBI:-opensbi.bin}" > /srv/tftp/boot.json   # IMAGE=Image612 SBI=opensbi612.bin: Buildroot 6.12
stty -F $U 115200 raw -echo; timeout 2 cat $U >/dev/null 2>&1
dj_load "$BIT"
T0=$(date +%s); cat $U > /tmp/lx_run.txt 2>/dev/null & CP=$!
for ((t=0; t<T; t+=5)); do sleep 5; grep -aq "login:" /tmp/lx_run.txt && { echo "LOGIN after $(( $(date +%s) - T0 )) s"; break; }; done
TYPE() { local c="$1"; for ((i=0; i<${#c}; i++)); do printf "%s" "${c:$i:1}" > $U; sleep 0.08; done; printf "\r" > $U; }
sleep 3; TYPE root; sleep 6
for c in "$@"; do TYPE "$c"; sleep ${W:-6}; done
kill $CP 2>/dev/null
~/FPGA/netboot_app.sh linux >/dev/null
tr '\r' '\n' < /tmp/lx_run.txt | tr -c '[:print:]\n' '.' | sed 's/\.\[[0-9;]*m//g' | grep -av "^\.*$" | tail -${TAILN:-60}
