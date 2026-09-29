#!/bin/bash
# run_series_e.sh (TASK-5096, Pi fpga-klaudio ~/t5095, ONLY right after a power cycle of gs). Pre-registered §5.8.
# Candidate: an empty A2 "reset" stream (empty_a2_r.bit, gmpack --reset) between two different layouts.
cd "$(dirname "$0")"
. ./preflight.sh; preflight || exit 3
ok(){ echo "$1" | grep -q "$2" || { echo "STOP: expected '$2'"; mark_wedged "$0 expected $2"; exit 1; }; }
o=$(./uart_nr.sh sr_x_nr.bit 3); echo "E1 $o"; ok "$o" "E00000000 K0000000B"
for i in 1 2 3; do
  o=$(./uart_nr.sh empty_a2_r.bit 2);  echo "E2.$i $o"; ok "$o" "load: Done"   # empty design: silent is expected
  o=$(./uart_nr.sh inv_sr_nr.bit 4);   echo "E3.$i $o"; ok "$o" "K000000DB"; ok "$o" "K0000002B"
  o=$(./uart_nr.sh empty_a2_r.bit 2);  echo "E4.$i $o"; ok "$o" "load: Done"
  o=$(./uart_nr.sh sr_x_nr.bit 4);     echo "E5.$i $o"; ok "$o" "E00000000 K0000000B"
done
echo "SERIES_E_OK: an empty stream between two layouts makes every reload work"
