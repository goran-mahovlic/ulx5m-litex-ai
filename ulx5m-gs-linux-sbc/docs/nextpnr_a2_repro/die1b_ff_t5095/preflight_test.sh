#!/bin/bash
# preflight_test.sh (TASK-5096): offline tests for preflight.sh with a fake dmesg, uptime and lease file. No board.
cd "$(dirname "$0")"; T=$(mktemp -d); pass=0; fail=0
now=$(date +%s)
case_(){ # name expect_exit owner_text uptime_s dmesg_line [local_marker]
  printf '%s\n' "$3" > "$T/owner"; printf '%s\n' "$5" > "$T/dmesg"
  [ -z "$3" ] && rm -f "$T/owner"
  rm -f "$T/mark"; [ -n "$6" ] && printf '%s\n' "$6" > "$T/mark"
  out=$(OWNER_FILE="$T/owner" MARK_FILE="$T/mark" DMESG="cat $T/dmesg" UPTIME_S=$4 NOW=$now bash -c '. ./preflight.sh; preflight' 2>&1); rc=$?
  if [ $rc -eq $2 ]; then pass=$((pass+1)); else fail=$((fail+1)); echo "FAIL $1: rc=$rc want $2: $out"; fi; }
note=$((now-1000))   # lease note written 1000 s ago; boot 5000 s ago -> the note is at uptime 4000 s
case_ "no power cycle since the note"   3 "jelena $note TASK-5095 gs NEEDS POWER CYCLE" 5000 "[ 3000.1] usb 1-1.1.2.4: Product: DirtyJTAG"
case_ "power cycle after the note"      0 "jelena $note TASK-5095 gs NEEDS POWER CYCLE" 5000 "[ 4500.2] usb 1-1.1.2.4: Product: DirtyJTAG"
case_ "no DirtyJTAG in dmesg (rotated)" 3 "jelena $note TASK-5095 gs NEEDS POWER CYCLE" 5000 "[   10.0] something else"
case_ "lease without the note"          0 "jelena $note TASK-5096 gs" 5000 "[ 3000.1] usb 1-1.1.2.4: Product: DirtyJTAG"
case_ "missing lease file"              3 "" 5000 "[ 4500.2] usb 1-1.1.2.4: Product: DirtyJTAG"
late=$((now-500))    # a series stopped 500 s ago (uptime 4500 s) and wrote the local marker
case_ "marker newer than the enumeration" 3 "jelena $note TASK-5095 gs NEEDS POWER CYCLE" 5000 "[ 4200.0] usb 1-1.1.2.4: Product: DirtyJTAG" "$late T2.1 silent"
case_ "enumeration after the marker"      0 "jelena $note TASK-5095 gs NEEDS POWER CYCLE" 5000 "[ 4800.0] usb 1-1.1.2.4: Product: DirtyJTAG" "$late T2.1 silent"
case_ "marker, lease without a note"      3 "jelena $note TASK-5096 gs" 5000 "[ 4200.0] usb 1-1.1.2.4: Product: DirtyJTAG" "$late T2.1 silent"
rm -rf "$T"; echo "preflight_test: $pass pass, $fail fail"; [ $fail -eq 0 ]
