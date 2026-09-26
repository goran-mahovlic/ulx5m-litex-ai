#!/bin/bash
# flash -r, wait, ping sizes; usage pt.sh <bit> [wait]
BIT=$1; W=${2:-20}
echo "### $(date +%T) $BIT"
/usr/local/bin/openFPGALoader -c dirtyJtag "$BIT" -r 2>&1 | grep -E "^Done|rror" | tail -1
sleep $W
for s in 0 18 20 30 56 200 1000 1472; do echo "-s $s: $(ping -c 5 -i 0.5 -W 1 -s $s 192.168.10.212 | grep -o '[0-9]* received')"; done
ip neigh show 192.168.10.212
