#!/bin/bash
# TASK-5078 lab phase 8: A/B after the 1 uF caps on GS (C128 VDD_SER, C127 VDD_SER_PLL, C42 VDD_PLL; Goran 27.09. 15:54).
# Same bits as the baseline (sha256 checked), CFGRST, SRAM -r, no power-cycle. Every load = fresh load m2 then gs (abrun.sh).
# 2.5 G: best pair of §9.3/§9.7 (gs TX_NEG s7 + m2 s2), 3 loads x 300 s.
# 5 G: PROFILE 2 and PROFILE 3 (= PEAK 24 point (d)), 3 loads x 60 s INTERLEAVED, then 1 x 300 s each; ber_jtag_check 200.
cd /home/pi/ulx5m-serdes/t5066; export ME=TASK-5078 KEEP_LEASE=1; L=$PWD/log5078; mkdir -p $L
T=/home/pi/ulx5m-serdes/tools
own=$(cat /home/pi/gs.owner 2>/dev/null)
if [ -n "$own" ] && [ "${own%% *}" != TASK-5078 ]; then
  age=$(( $(date +%s) - $(echo "$own" | awk '{print $2}') )); [ "$age" -lt 7200 ] && { echo "leased: $own"; exit 3; }
fi
echo "TASK-5078 $(date +%s) SerDes A/B after 1uF caps on GS (jelena)" > /home/pi/gs.owner
sha256sum gs_sd_2g5p1_txneg_s7.bit m2_e1_2g5p1_txneg_s2.bit gs_p2_5g_txneg_s7.bit m2_p2_5g_txneg_s1.bit gs_p3_5g_txneg_s7.bit m2_p3_5g_txneg_s1.bit
echo "== 2.5G $(date +%T)"
LOG=$L $T/lab/abrun.sh gs_sd_2g5p1_txneg_s7.bit m2_e1_2g5p1_txneg_s2.bit 300 3 "t78_2g5_gs7_m22||"
for k in 1 2 3; do
  echo "== 5G round $k $(date +%T)"
  LOG=$L/tmp $T/lab/abrun.sh gs_p2_5g_txneg_s7.bit m2_p2_5g_txneg_s1.bit 60 1 "t78_p2_60s||"
  LOG=$L/tmp $T/lab/abrun.sh gs_p3_5g_txneg_s7.bit m2_p3_5g_txneg_s1.bit 60 1 "t78_p3_60s||"
  for f in $L/tmp/*_r1*.json; do b=$(basename $f); mv $f $L/${b/_r1/_r$k}; done
done
LOG=$L $T/lab/abrun.sh gs_p2_5g_txneg_s7.bit m2_p2_5g_txneg_s1.bit 300 1 "t78_p2_300s||"
for b in m2 gs; do echo "jtag_check P2 $b: $(fpga-jtag $b run python3 $T/ber_jtag_check.py --samples 200 2>&1 | tail -1)"; done
LOG=$L $T/lab/abrun.sh gs_p3_5g_txneg_s7.bit m2_p3_5g_txneg_s1.bit 300 1 "t78_p3_300s||"
for b in m2 gs; do echo "jtag_check P3 $b: $(fpga-jtag $b run python3 $T/ber_jtag_check.py --samples 200 2>&1 | tail -1)"; done
python3 $T/lab/ab_table.py --runs --rank $L/t78*_r*.json
rm -f /home/pi/gs.owner; echo "LAB8 DONE $(date +%T)"
