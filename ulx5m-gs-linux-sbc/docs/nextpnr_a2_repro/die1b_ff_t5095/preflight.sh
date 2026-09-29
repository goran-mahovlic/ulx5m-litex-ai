#!/bin/bash
# preflight.sh (TASK-5096): sourced by run_series*.sh. Refuses to load anything on gs while a power-cycle note is
# newer than the last DirtyJTAG enumeration (a power cycle of gs re-enumerates both probes, §5.7). Notes:
#   - the lease /home/pi/gs.owner with "NEEDS POWER CYCLE" (epoch = field 2; agents cannot always write it),
#   - the local marker ./NEEDS_POWER_CYCLE ("<epoch> <reason>") that a series writes when it stops (mark_wedged).
# Fails closed: no lease file, or a note but no DirtyJTAG line in dmesg -> exit 3.
# Test hooks: OWNER_FILE, MARK_FILE, DMESG (command), UPTIME_S, NOW.
preflight(){
  local own=${OWNER_FILE:-/home/pi/gs.owner} mark=${MARK_FILE:-./NEEDS_POWER_CYCLE}
  local now=${NOW:-$(date +%s)} up=${UPTIME_S:-$(cut -d. -f1 /proc/uptime)} note=0 n rel enum
  [ -r "$own" ] || { echo "STOP preflight: no lease file $own"; return 3; }
  grep -q "NEEDS POWER CYCLE" "$own" && note=$(awk '{print $2}' "$own")
  [ -r "$mark" ] && { n=$(awk '{print $1; exit}' "$mark"); [ "$n" -gt "$note" ] && note=$n; }
  [ "$note" -gt 0 ] || { echo "preflight: no power-cycle note"; return 0; }
  rel=$(${DMESG:-dmesg} | grep "Product: DirtyJTAG" | tail -1 | sed -E 's/^\[ *([0-9]+)\..*/\1/')
  [[ "$rel" =~ ^[0-9]+$ ]] || { echo "STOP preflight: no DirtyJTAG enumeration in dmesg, cannot prove a power cycle"; return 3; }
  enum=$((now - up + rel))
  [ "$enum" -gt "$note" ] || { echo "STOP preflight: last DirtyJTAG enumeration $(date -d @$enum +%T) is before the note $(date -d @$note +%T) -> gs still needs a power cycle"; return 3; }
  echo "preflight: probes re-enumerated $(date -d @$enum +%T), after the note $(date -d @$note +%T)"
}
# mark_wedged <reason>: called by a series when a known-good step comes back silent/erratic.
mark_wedged(){ echo "$(date +%s) $*" > "${MARK_FILE:-./NEEDS_POWER_CYCLE}"; }
