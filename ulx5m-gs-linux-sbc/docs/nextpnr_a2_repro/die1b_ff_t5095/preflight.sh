#!/bin/bash
# preflight.sh (TASK-5096): sourced by run_series.sh. Refuses to load anything on gs while the lease says
# "NEEDS POWER CYCLE" and the DirtyJTAG probes have not re-enumerated since that note (a power cycle of gs
# re-enumerates both probes, §5.7). Fails closed: no lease file or no DirtyJTAG line in dmesg -> exit 3.
# Test hooks: OWNER_FILE, DMESG (command), UPTIME_S, NOW.
preflight(){
  local own=${OWNER_FILE:-/home/pi/gs.owner} now=${NOW:-$(date +%s)} up=${UPTIME_S:-$(cut -d. -f1 /proc/uptime)}
  [ -r "$own" ] || { echo "STOP preflight: no lease file $own"; return 3; }
  grep -q "NEEDS POWER CYCLE" "$own" || { echo "preflight: lease has no power-cycle note"; return 0; }
  local note rel enum
  note=$(awk '{print $2}' "$own")
  rel=$(${DMESG:-dmesg} | grep "Product: DirtyJTAG" | tail -1 | sed -E 's/^\[ *([0-9]+)\..*/\1/')
  [[ "$rel" =~ ^[0-9]+$ ]] || { echo "STOP preflight: no DirtyJTAG enumeration in dmesg, cannot prove a power cycle"; return 3; }
  enum=$((now - up + rel))
  [ "$enum" -gt "$note" ] || { echo "STOP preflight: last DirtyJTAG enumeration $(date -d @$enum +%T) is before the note $(date -d @$note +%T) -> gs still needs a power cycle"; return 3; }
  echo "preflight: probes re-enumerated $(date -d @$enum +%T), after the note $(date -d @$note +%T)"
}
