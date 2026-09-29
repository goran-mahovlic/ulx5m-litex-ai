#!/bin/bash
# run_series_j.sh (TASK-5096, Pi fpga-klaudio ~/t5095, ONLY right after a power cycle of gs). Pre-registered §5.8.
# Candidate: reset die 1B through its OWN TAP (--index-chain 1) with a single-die empty stream (empty_a1_r.bit),
# then load the A2 stream through 1A (--index-chain 0) as usual.
cd "$(dirname "$0")"
. ./preflight.sh; preflight || exit 3
ok(){ echo "$1" | grep -q "$2" || { echo "STOP: expected '$2'"; mark_wedged "$0 expected $2"; exit 1; }; }
U=$(fpga-jtag uart gs) || exit 2
load1(){ echo "load idx1: $(sudo -n /usr/local/bin/fpga-jtag gs "$(readlink -f $1)" --index-chain 1 2>&1 | grep -E '^Done|rror' | tail -1)"; }
o=$(./uart_nr.sh sr_x_nr.bit 3); echo "J1 $o"; ok "$o" "E00000000 K0000000B"
for i in 1 2 3; do
  o=$(load1 empty_a1_r.bit; sleep 1; printf '\000\000' > $U; timeout 3 cat $U | tr -d '\r'); echo "J2.$i $o"   # observed, not judged
  o=$(./uart_nr.sh inv_sr_nr.bit 4); echo "J3.$i $o"; ok "$o" "K000000DB"; ok "$o" "K0000002B"
  o=$(load1 empty_a1_r.bit; sleep 1; printf '\000\000' > $U; timeout 3 cat $U | tr -d '\r'); echo "J4.$i $o"
  o=$(./uart_nr.sh sr_x_nr.bit 4);   echo "J5.$i $o"; ok "$o" "E00000000 K0000000B"
done
echo "SERIES_J_OK: resetting 1B through its own TAP before each A2 load makes every reload work"
