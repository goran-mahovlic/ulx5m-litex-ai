#!/bin/bash
# TASK-5531 lab40: TX_AMP 12 baked into the bits (OV_TX_AMP=12, only TX_AMP 11111->01100 differs from b1b98a5d/36f09752).
# SRAM (-r) check of the "flash" recipe: NO JTAG write after the load (no SET_ACC pulse, no TX_AMP set, no G2).
# Only reads: eyescan.py get, ber_jtag_check (READ-ONLY), gs UART ber_long. Per load: m2 then gs -r, t_link until
# PEER 10/10 on both, CDR/EQA state + SET_ACC/FREQ_ACC readback, PEER 200/200, 60 s serial BER both directions.
W=/home/pi/ulx5m-serdes/t5531; T=/home/pi/ulx5m-serdes/tools; L=$W/log40; mkdir -p $L
LOADS=${LOADS:-6}; M2B=${M2B:-$W/m2_2g5_amp12.bit}; GSB=${GSB:-$W/gs_2g5_amp12.bit}; BS=${BS:-60}
echo "TASK-5531 $(date +%s) lab40 SRAM no-write check, ~$((LOADS*3)) min (jelena)" > /home/pi/gs.owner
J() { (cd $T; fpga-jtag $1 run python3 eyescan.py "${@:2}" 2>&1 | tail -1 | sed 's/board=//'); }
PEER() { (cd $T; fpga-jtag $1 run python3 ber_jtag_check.py --samples $2 2>&1 | tail -1 | sed 's/.*rx: /rx: /'); }
ber() { (cd $T; timeout $(($2+300)) python3 lab/ber_long.py --secs $2 --every 60 --out $L/$1.jsonl 2>&1 | grep TOTAL | cut -c1-220); }
ST="RX_CDR_LOCKED RX_EQA_LOCKED RX_CDR_SET_ACC_CONFIG RX_CDR_FREQ_ACC_VAL TX_AMP RX_TH_MON RX_OFFSET PLL_LOCKED"
echo "== lab40 $(date +%T) $(vcgencmd get_throttled) $(vcgencmd measure_temp) m2=$(sha256sum $M2B|cut -c1-8) gs=$(sha256sum $GSB|cut -c1-8)"
for k in $(seq 1 $LOADS); do
  fpga-jtag m2 $M2B -r 2>&1 | tail -1 >/dev/null; fpga-jtag gs $GSB -r 2>&1 | tail -1 >/dev/null
  t0=$(date +%s.%N)
  echo "S0 l$k $(J gs get $ST) | $(J m2 get $ST)"
  ok=0 n=0
  while [ $n -lt 20 ]; do n=$((n+1)); a=$(PEER m2 10); b=$(PEER gs 10)
    if echo "$a" | grep -q PASS && echo "$b" | grep -q PASS; then ok=1; break; fi; done
  echo "LOAD l$k t_link=$(python3 -c "print('%.1f' % ($(date +%s.%N)-$t0))")s ok=$ok polls=$n"
  echo "S1 l$k $(J gs get $ST) | $(J m2 get $ST)"
  echo "PEER l$k m2: $(PEER m2 200) | gs: $(PEER gs 200)"
  echo "BER l$k $(ber l$k $BS)"
done
rm -f /home/pi/gs.owner; echo "LAB40 DONE $(date +%T)"
