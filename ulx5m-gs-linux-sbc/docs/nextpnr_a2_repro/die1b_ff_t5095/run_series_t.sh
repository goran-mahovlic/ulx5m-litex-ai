#!/bin/bash
# run_series_t.sh (TASK-5096, on the Pi as fpga-klaudio in ~/t5095, ONLY right after a power cycle of gs).
# Tool fix under test: gmpack --reset-all-first (local prjpeppercorn b1eb52f + patch 0001) resets BOTH dies before
# either is configured, so die 1A no longer runs the old design while die 1B is written (H8, §5.8).
# Reloads of a DIFFERENT layout WITHOUT any R! in between - exactly the case that failed 4 of 5 times (§5.7).
# Pre-registered in A2_CCGM1A2_TASK-5092.md §5.8. Stops at the first result that differs from the expectation.
cd "$(dirname "$0")"
. ./preflight.sh; preflight || exit 3
ok(){ echo "$1" | grep -q "$2" || { echo "STOP: expected '$2'"; mark_wedged "$0 expected $2"; exit 1; }; }
o=$(./uart_nr.sh sr_x_raf.bit 3);   echo "T1 $o"; ok "$o" "E00000000 K0000000B"
for i in 1 2 3; do
  o=$(./uart_nr.sh inv_sr_raf.bit 4); echo "T2.$i $o"; ok "$o" "K000000DB"; ok "$o" "K0000002B"
  o=$(./uart_nr.sh sr_x_raf.bit 4);   echo "T3.$i $o"; ok "$o" "E00000000 K0000000B"
done
echo "SERIES_T_OK: 7 loads, 6 of them a different layout over a running A2 design, all as on a fresh chip"
