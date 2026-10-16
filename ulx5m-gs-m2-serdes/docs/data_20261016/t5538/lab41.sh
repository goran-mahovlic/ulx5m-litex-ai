#!/bin/bash
# TASK-5538 lab41 (uputa #345): -r reload of the *_auto bits (m2 then gs, no power cycle, NO JTAG write after the load),
# up to LOADS loads; per load t_link, state, PEER 200, ber_long 150 s / 30 s (first window dropped in the analysis).
# The first load with M2->GS < 1e-9 (windows 2..) gets one more ber_long 300 s / 30 s.
W=/home/pi/ulx5m-serdes/t5538; T=/home/pi/ulx5m-serdes/tools; F=/home/pi/fpga; L=$W/log41; mkdir -p $L
LOADS=${LOADS:-3}
echo "TASK-5538 $(date +%s) lab41 -r reload + BER ~$((LOADS*4+6)) min (jelena)" > /home/pi/gs.owner
J() { (cd $T; fpga-jtag $1 run python3 eyescan.py "${@:2}" 2>&1 | tail -1 | sed 's/board=//'); }
PEER() { (cd $T; fpga-jtag $1 run python3 ber_jtag_check.py --samples $2 2>&1 | tail -1 | sed 's/.*rx: /rx: /'); }
ST="RX_CDR_LOCKED RX_EQA_LOCKED RX_CDR_FREQ_ACC_VAL TX_AMP RX_TH_MON RX_OFFSET PLL_LOCKED"
echo "== lab41 $(date '+%F %T') $(vcgencmd get_throttled) $(vcgencmd measure_temp) m2=$(sha256sum $F/m2_2g5_auto.bit|cut -c1-8) gs=$(sha256sum $F/gs_2g5_auto.bit|cut -c1-8)"
for k in $(seq 1 $LOADS); do
  fpga-jtag m2 $F/m2_2g5_auto.bit -r 2>&1 | tail -1; fpga-jtag gs $F/gs_2g5_auto.bit -r 2>&1 | tail -1
  t0=$(date +%s.%N); ok=0 n=0
  while [ $n -lt 20 ]; do n=$((n+1)); a=$(PEER m2 10); b=$(PEER gs 10)
    if echo "$a" | grep -q PASS && echo "$b" | grep -q PASS; then ok=1; break; fi; done
  echo "LOAD l$k t_link<=$(python3 -c "print('%.1f' % ($(date +%s.%N)-$t0))")s ok=$ok polls=$n"
  echo "S l$k $(J gs get $ST) | $(J m2 get $ST)"
  echo "PEER l$k m2: $(PEER m2 200) | gs: $(PEER gs 200)"
  (cd $T; timeout 600 python3 lab/ber_long.py --secs 150 --every 30 --out $L/l$k.jsonl 2>&1 | grep -E 'TOTAL|SYNC|NOUART')
  r=$(python3 $T/lab/ber_windows.py $L/l$k.jsonl 2>&1 | tee $L/l$k.win | grep "TOTAL m2_to_gs" | sed 's/.* BER=\([^ ]*\).*/\1/')
  echo "WIN l$k m2->gs(after skip)=$r"; grep TOTAL $L/l$k.win
  if [ -n "$r" ] && python3 -c "import sys; sys.exit(0 if float('$r') < 1e-9 else 1)" 2>/dev/null; then
    echo "ACCEPT l$k -> 300 s"
    (cd $T; timeout 900 python3 lab/ber_long.py --secs 300 --every 30 --out $L/l${k}_300.jsonl 2>&1 | grep -E 'TOTAL|SYNC|NOUART')
    python3 $T/lab/ber_windows.py $L/l${k}_300.jsonl --skip 0 | tee $L/l${k}_300.win | grep TOTAL
    break
  fi
done
echo "S end $(J gs get $ST) | $(J m2 get $ST)"
rm -f /home/pi/gs.owner; echo "LAB41 DONE $(date +%T)"
