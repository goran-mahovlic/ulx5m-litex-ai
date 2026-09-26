#!/bin/bash
# sweep.sh "<cfg:secs> ..." [seed] — rate sweep with the BER design. For each cfg loads BIT/gs_<cfg>_s<seed>.bit and
# BIT/m2_<cfg>_s<seed>.bit (gateware/ber/build_ber.sh names), runs ber_run.sh, prints the result lines.
# Board lease (shared lab): OWNER file; if it names another task and is younger than 2 h, gs is not touched.
# Env: BIT (bitstream dir), OWNER (lease file, default $HOME/gs.owner), ME (lease name), REST_GS/REST_M2 (bits to leave loaded).
H=$(cd "$(dirname "$(readlink -f "$0")")" && pwd)
CFGS=${1:-"od4:300 od2:180 od1:120 n155od4:120 n155od2:120"}; SEED=${2:-1}
BIT=${BIT:-$PWD/bit}; OWNER=${OWNER:-$HOME/gs.owner}; ME=${ME:-serdes-sweep}; LOG=${LOG:-$PWD/log}; export LOG
own=$(cat "$OWNER" 2>/dev/null)
if [ -n "$own" ] && [ "${own%% *}" != "$ME" ]; then
    age=$(( $(date +%s) - $(echo "$own" | awk '{print $2}') ))
    [ "$age" -lt 7200 ] && { echo "gs is leased: $own (${age}s ago) -> not touching it"; exit 3; }
fi
echo "$ME $(date +%s) SerDes rate sweep ($CFGS)" > "$OWNER"
for c in $CFGS; do
    n=${c%%:*}; s=${c##*:}
    bash "$H/ber_run.sh" "$BIT/gs_${n}_s$SEED.bit" "$BIT/m2_${n}_s$SEED.bit" "$s" "sweep_${n}_s$SEED"
    grep -E "rate|->gs|->m2|expect" "$LOG/sweep_${n}_s$SEED.log"
done
fpga-jtag m2 "${REST_M2:-$BIT/m2_od4_s1.bit}" -r >/dev/null 2>&1; fpga-jtag gs "${REST_GS:-$BIT/gs_od4_s1.bit}" -r >/dev/null 2>&1
rm -f "$OWNER"; echo "SWEEP DONE $(date +%T): both boards back on the 0.3 Gb/s BER design, lease released"
