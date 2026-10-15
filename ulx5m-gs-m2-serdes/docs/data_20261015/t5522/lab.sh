#!/bin/bash
# TASK-5482 (uputa #304): long serial BER run after TASK-5483/5487. Standard procedure per load: m2 then gs -r, SET_ACC 2->0
# on both, health (start), ber_jtag_check 200, ber_long.py (cumulative counters over the gs UART, snapshot every EVERY s),
# health (end), ber_jtag_check 200. 2.5 G: NL loads x SECS. 5 G P2: 1 load, JTAG PEER 1000 + 300 s (only reported, TASK-5487
# measured 88 % valid words). Usage: lab22.sh [loads=3]
F=/home/pi/fpga; T=/home/pi/ulx5m-serdes/tools; L=/home/pi/ulx5m-serdes/t5522/log; mkdir -p $L
NL=${1:-3}; SECS=${SECS:-3600}; EVERY=${EVERY:-60}
echo "TASK-5522 $(date +%s) lab (regoc)" > /home/pi/gs.owner
one() {  # one <label> <m2.bit> <gs.bit> <secs> <every> <jtag_samples>
  O=$L/$1; echo "-- $1 $(date +%T) $(vcgencmd get_throttled) m2=$(basename $2) gs=$(basename $3)"
  fpga-jtag m2 $2 -r 2>&1 | tail -1; fpga-jtag gs $3 -r 2>&1 | tail -1; sleep 3
  for b in m2 gs; do (cd $T; fpga-jtag $b run python3 eyescan.py set RX_CDR_SET_ACC_CONFIG=2 >/dev/null 2>&1; fpga-jtag $b run python3 eyescan.py set RX_CDR_SET_ACC_CONFIG=0 >/dev/null 2>&1); done
  for b in m2 gs; do (cd $T; fpga-jtag $b run python3 eyescan.py health --raw -n 3 --interval 0.2 --label "$1 start" --out "$O.start_$b.json" 2>&1 | grep -E "^HEALTH|PLL_LOCKED|Error" | cut -c1-260); done
  for b in m2 gs; do echo "JTAG $1 $b start: $(cd $T; fpga-jtag $b run python3 ber_jtag_check.py --samples $6 2>&1 | tail -1 | sed 's/.*rx: /rx: /')"; done
  (cd $T; timeout $(($4+600)) python3 lab/ber_long.py --secs $4 --every $5 --out $O.jsonl 2>&1 | tail -2)
  for b in m2 gs; do (cd $T; fpga-jtag $b run python3 eyescan.py health --raw -n 3 --interval 0.2 --label "$1 end" --out "$O.end_$b.json" 2>&1 | grep -E "^HEALTH|Error" | cut -c1-200); done
  for b in m2 gs; do echo "JTAG $1 $b end: $(cd $T; fpga-jtag $b run python3 ber_jtag_check.py --samples $6 2>&1 | tail -1 | sed 's/.*rx: /rx: /')"; done
  echo "== $1 END $(date +%T)"
}
for r in $(seq 1 $NL); do one 2g5_r$r $F/m2_2g5.bit $F/gs_2g5.bit $SECS $EVERY 200; done
one 5g_p2 $F/m2_5g.bit $F/gs_5g.bit ${SECS5:-300} 60 1000
rm -f /home/pi/gs.owner; echo "LAB DONE $(date +%T)"
