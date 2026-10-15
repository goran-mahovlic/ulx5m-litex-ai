#!/bin/bash
# TASK-5525 lab25: Cologne Chip eye path on both receivers. Per rate: lab22 procedure (m2 then gs -r, SET_ACC 2->0),
# health, JTAG PEER, then per board: eyescan.py capture -n 10 (eye_capture_op vs split reads) and diagnose (eye_diagnose),
# JTAG PEER again (freeze/restore did not break the link) and a 60 s serial BER.
F=/home/pi/fpga; T=/home/pi/ulx5m-serdes/tools; L=/home/pi/ulx5m-serdes/t5525/log25; mkdir -p $L
echo "TASK-5525 $(date +%s) lab25 eye CC (jelena)" > /home/pi/gs.owner
one() {  # one <label> <m2.bit> <gs.bit> <rate>
  O=$L/$1; echo "-- $1 $(date +%T) $(vcgencmd get_throttled)"
  fpga-jtag m2 $2 -r 2>&1 | tail -1; fpga-jtag gs $3 -r 2>&1 | tail -1; sleep 3
  for b in m2 gs; do (cd $T; fpga-jtag $b run python3 eyescan.py set RX_CDR_SET_ACC_CONFIG=2 >/dev/null 2>&1; fpga-jtag $b run python3 eyescan.py set RX_CDR_SET_ACC_CONFIG=0 >/dev/null 2>&1); done
  for b in m2 gs; do (cd $T; fpga-jtag $b run python3 eyescan.py health --raw -n 3 --interval 0.2 --label "$1" --out "$O.health_$b.json" 2>&1 | grep -E "^HEALTH" | cut -c1-200); done
  for b in m2 gs; do echo "JTAG $1 $b before: $(cd $T; fpga-jtag $b run python3 ber_jtag_check.py --samples 200 2>&1 | tail -1 | sed 's/.*rx: /rx: /')"; done
  for b in m2 gs; do
    (cd $T; fpga-jtag $b run python3 eyescan.py capture -n 10 --interval 0.2 --label "$1" --out "$O.capture_$b.json" 2>&1 | grep -E "^CAP")
    (cd $T; fpga-jtag $b run python3 eyescan.py diagnose --rate $4 --label "$1" --out "$O.diag_$b.json" 2>&1 | grep -E "^DIAG")
  done
  for b in m2 gs; do echo "JTAG $1 $b after: $(cd $T; fpga-jtag $b run python3 ber_jtag_check.py --samples 200 2>&1 | tail -1 | sed 's/.*rx: /rx: /')"; done
  (cd $T; timeout 300 python3 lab/ber_long.py --secs 60 --every 30 --out $O.ber60.jsonl 2>&1 | tail -2)
  echo "== $1 END $(date +%T)"
}
one 2g5 $F/m2_2g5.bit $F/gs_2g5.bit 2.5e9
one 5g_p2 $F/m2_5g.bit $F/gs_5g.bit 5e9
one 2g5_back $F/m2_2g5.bit $F/gs_2g5.bit 2.5e9
rm -f /home/pi/gs.owner; echo "LAB25 DONE $(date +%T)"
