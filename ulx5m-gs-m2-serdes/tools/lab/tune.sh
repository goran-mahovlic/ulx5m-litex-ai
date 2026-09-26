#!/bin/bash
# tune.sh <cfg> <secs> "<step>" ["<step>" ...] — analog tuning of a running BER link without rebuilds (TASK-5063).
# Loads BIT/m2_<cfg>.bit then BIT/gs_<cfg>.bit once, then for each step:
#   step = "label|gs:FIELD=V,FIELD=V|m2:FIELD=V"   (serdestool field names; either board part may be empty)
#   writes the fields over JTAG (eyescan.py set), waits 2 s, BER run with cleared counters (ber_mon.py --json),
#   and with EYE=1 an eye scan of both receivers (eyescan.py scan) after the BER run.
# Settings are cumulative (a later step starts from the previous one). Every step's result goes to $LOG/tune_<cfg>_<label>.*
# Lease: same rule as sweep.sh (OWNER file, another task younger than 2 h -> exit 3). REST_GS/REST_M2 = bits to leave loaded.
H=$(cd "$(dirname "$(readlink -f "$0")")" && pwd); T=$(cd "$H/.." && pwd)
CFG=$1; S=$2; shift 2
BIT=${BIT:-$PWD/bit}; OWNER=${OWNER:-$HOME/gs.owner}; ME=${ME:-serdes-tune}; LOG=${LOG:-$PWD/log}; mkdir -p "$LOG"
EYE=${EYE:-0}; EYE_ARGS=${EYE_ARGS:-"--ph=-32:31:4 --th=-15:15:3 --window 512"}
own=$(cat "$OWNER" 2>/dev/null)
if [ -n "$own" ] && [ "${own%% *}" != "$ME" ]; then
    age=$(( $(date +%s) - $(echo "$own" | awk '{print $2}') ))
    [ "$age" -lt 7200 ] && { echo "gs is leased: $own (${age}s ago) -> not touching it"; exit 3; }
fi
echo "$ME $(date +%s) SerDes tuning $CFG" > "$OWNER"
fpga-jtag m2 "$BIT/m2_$CFG.bit" -r 2>&1 | tail -1; fpga-jtag gs "$BIT/gs_$CFG.bit" -r 2>&1 | tail -1; sleep 3
for st in "$@"; do
    IFS='|' read -r lab p1 p2 <<< "$st"
    for part in "$p1" "$p2"; do
        [ -z "$part" ] && continue
        b=${part%%:*}; f=${part#*:}
        fpga-jtag "$b" run python3 "$T/eyescan.py" set ${f//,/ } 2>&1 | grep board=
    done
    sleep 2
    O=$LOG/tune_${CFG}_$lab
    ( cd "$T"; python3 ber_mon.py run --secs "$S" --clear --json ) > "$O.json"
    echo "== $lab ($st)"; ( cd "$T"; python3 -c "import json,ber_mon;print(ber_mon.fmt(json.load(open('$O.json'))))" ) | grep -E "rate|->gs|->m2"
    if [ "$EYE" = 1 ]; then
        for b in m2 gs; do
            fpga-jtag "$b" run python3 "$T/eyescan.py" scan $EYE_ARGS --label "$CFG $lab" --out "$O.eye_$b.json" 2>&1 | grep -E "^EYE|^th|Error"
        done
    fi
done
[ -n "$REST_M2" ] && fpga-jtag m2 "$REST_M2" -r >/dev/null 2>&1; [ -n "$REST_GS" ] && fpga-jtag gs "$REST_GS" -r >/dev/null 2>&1
rm -f "$OWNER"; echo "TUNE DONE $(date +%T), lease released"
