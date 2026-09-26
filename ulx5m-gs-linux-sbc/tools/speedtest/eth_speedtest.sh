#!/bin/bash
# TASK-5033: one command for Goran: load the netboot SoC with speedtest.bin and measure (see README_speedtest.md)
D=$(dirname "$(readlink -f "$0")")
: "${BIT:?set BIT=<netboot SoC bitstream>}"
NB="$D/netboot_app.sh"; [ -x "$NB" ] || NB="$D/../linux/netboot_app.sh"   # flat copy on the Pi, or this repo
"$NB" speedtest >/dev/null
sudo -n /usr/local/bin/openFPGALoader -c dirtyJtag "$BIT" -r 2>&1 | grep -E "^Done|rror" | tail -1
sleep 15                      # BIOS + TFTP boot of speedtest.bin takes ~9 s
python3 "$D/eth_speedtest.py" "$@"
