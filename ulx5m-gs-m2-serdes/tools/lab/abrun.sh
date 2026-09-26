#!/bin/bash
# abrun.sh <gs.bit> <m2.bit> <secs> <reps> "<point>" ["<point>" ...] — A/B points with repeated loads (TASK-5066).
#   point = "label|gs:FIELD=V,FIELD=V|m2:FIELD=V"   (serdestool field names; either board part may be empty)
# For every point and every repeat k = 1..reps (TUNING_5G.md §3 repeat rule: >= 3 loads x 60 s, compare medians):
#   load m2 then gs (CFGRST bits), write the fields over JTAG and, if anything was written (or RECAL=1), run the
#   sweep procedure on BOTH boards (eyescan.py recal: TX/RX termination calibration + DFE reset via 0x2B, wait for
#   EQA/CDR lock); a point without writes measures the bitstream exactly as loaded,
#   E0 health of both receivers, BER run with cleared counters -> $LOG/<label>_r<k>.json (+ .health_<b>.json).
# Unlike tune.sh, points are NOT cumulative: every repeat starts from a fresh load.
# Summary: python3 lab/ab_table.py $LOG/<label>_r*.json
# Lease: /home/pi/gs.owner (FPGA_LAB_ARHITEKTURA.md); another owner younger than 2 h -> exit 3. KEEP_LEASE=1: keep it.
H=$(cd "$(dirname "$(readlink -f "$0")")" && pwd); T=$(cd "$H/.." && pwd)
GS=$1; M2=$2; S=$3; R=$4; shift 4
OWNER=${OWNER:-$HOME/gs.owner}; ME=${ME:-TASK-5066}; LOG=${LOG:-$PWD/log}; mkdir -p "$LOG"
own=$(cat "$OWNER" 2>/dev/null)
if [ -n "$own" ] && [ "${own%% *}" != "$ME" ]; then
    age=$(( $(date +%s) - $(echo "$own" | awk '{print $2}') ))
    [ "$age" -lt 7200 ] && { echo "gs is leased: $own (${age}s ago) -> not touching it"; exit 3; }
fi
echo "$ME $(date +%s) SerDes 5G tuning (jelena)" > "$OWNER"
for st in "$@"; do
    IFS='|' read -r lab p1 p2 <<< "$st"
    for k in $(seq 1 "$R"); do
        O=$LOG/${lab}_r$k
        fpga-jtag m2 "$M2" -r 2>&1 | tail -1 | grep -v -i done; fpga-jtag gs "$GS" -r 2>&1 | tail -1 | grep -v -i done; sleep 3
        for part in "$p1" "$p2"; do
            [ -z "$part" ] && continue
            b=${part%%:*}; f=${part#*:}
            fpga-jtag "$b" run python3 "$T/eyescan.py" set ${f//,/ } 2>&1 | grep -E "board=|Error"
        done
        if [ -n "$p1$p2" ] || [ "${RECAL:-0}" = 1 ]; then
            for b in m2 gs; do fpga-jtag $b run python3 "$T/eyescan.py" recal 2>&1 | grep -E "board=|Error"; done
        fi
        for b in m2 gs; do fpga-jtag $b run python3 "$T/eyescan.py" health -n 3 --interval 0.5 --label "$lab r$k" --out "$O.health_$b.json" 2>&1 | grep -E "^HEALTH|Error"; done
        ( cd "$T"; python3 ber_mon.py run --secs "$S" --clear --json ) > "$O.json"
        echo "== $lab r$k: $( cd "$T"; python3 -c "import json,sys;sys.path.insert(0,'lab');import ab_table as A;d=json.load(open('$O.json'));print('gs->m2 %.2e  m2->gs %.2e' % (A.ber(d['gs_to_m2']), A.ber(d['m2_to_gs'])))" )"
    done
done
[ "${KEEP_LEASE:-0}" = 1 ] || rm -f "$OWNER"; echo "ABRUN DONE $(date +%T)"
