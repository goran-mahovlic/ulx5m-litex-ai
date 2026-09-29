#!/bin/bash
# run_series.sh (TASK-5095, on the Pi as fpga-klaudio in ~/t5095, ONLY right after a power cycle of gs).
# Pre-registered in A2_CCGM1A2_TASK-5092.md §5.7. Stops at the first result that differs from the expectation.
cd "$(dirname "$0")"
. ./preflight.sh; preflight || exit 3   # TASK-5096: never load on a chip that still needs a power cycle
ok(){ echo "$1" | grep -q "$2" || { echo "STOP: expected '$2'"; mark_wedged "$0 expected $2"; exit 1; }; }
o=$(./uart_nr.sh sr_x_nr.bit 3);   echo "S1 $o";  ok "$o" "E00000000 K0000000B"
o=$(./sr_reset.sh 3);              echo "S2 $o";  ok "$o" "sent R!"; echo "$o" | grep -q "K0000000B" && { echo "STOP: design still running after R!"; exit 1; }
o=$(./uart_nr.sh inv_sr_nr.bit 4); echo "S3 $o";  ok "$o" "K000000DB"; ok "$o" "K0000002B"
o=$(./sr_reset.sh 3);              echo "S4 $o";  echo "$o" | grep -q "K000000" && { echo "STOP: design still running after R!"; exit 1; }
for i in 1 2 3; do
  o=$(./uart_nr.sh sr_x_nr.bit 3); echo "S5.$i $o"; ok "$o" "E00000000 K0000000B"
  o=$(./sr_reset.sh 2);            echo "S5.$i reset"; echo "$o" | grep -q "K000000" && { echo "STOP: still running"; exit 1; }
  o=$(./uart_nr.sh inv_sr_nr.bit 3); echo "S6.$i $o"; ok "$o" "K000000DB"; ok "$o" "K0000002B"
  o=$(./sr_reset.sh 2);            echo "S6.$i reset"; echo "$o" | grep -q "K000000" && { echo "STOP: still running"; exit 1; }
done
echo "SERIES_OK: 8 loads with self-reset in between, all as on a fresh chip"
# TASK-5096, opt-in: control run without R! (reproduces Q2 if H7 holds). Leaves the chip in the bad state ->
# the next session needs a power cycle again; the lease note is the caller's job.
[ "$1" = "--control" ] || exit 0
o=$(./uart_nr.sh inv_sr_nr.bit 3); echo "C1 $o"; ok "$o" "K000000DB"
o=$(./uart_nr.sh sr_x_nr.bit 4);   echo "C2 $o"
echo "$o" | grep -q "K0000000B" && echo "CONTROL: sr_x over inv_sr WITHOUT R! worked -> H7 not reproduced" \
                               || echo "CONTROL: sr_x over inv_sr WITHOUT R! failed -> H7 reproduced, R! is what makes reloads work"
