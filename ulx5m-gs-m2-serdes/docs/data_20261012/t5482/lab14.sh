#!/bin/bash
# TASK-5482 lab14 (12.10.2026): retest 2.5 G / 5 G after Goran fixed M2 JTAG (TDO stuck at 0).
# gs UART (ber_mon BER counters) is SILENT today (0 bytes at 9600..1M baud, also LiteX BIOS) -> BER counters unreadable.
# This lab measures what JTAG can: per load (m2 then gs, -r), SET_ACC 2->0 pulse on both (LOCAL_REFCLK_M2.md §4C),
# health (PLL/CAP_FT/FT_OF/UF/CDR/EQA) on both, and ber_jtag_check 200 samples on both (PEER share = word align + data from peer).
# Same six bits as lab9/lab13. 3 loads per point, interleaved 5 G.
cd /home/pi/ulx5m-serdes/t5066; L=/home/pi/ulx5m-serdes/t5482/log; T=/home/pi/ulx5m-serdes/tools; mkdir -p $L
echo "TASK-5482 $(date +%s) lab14 JTAG-only retest (jelena)" > /home/pi/gs.owner
sha256sum gs_sd_2g5p1_txneg_s7.bit m2_e1_2g5p1_txneg_s2.bit gs_p2_5g_txneg_s7.bit m2_p2_5g_txneg_s1.bit gs_p3_5g_txneg_s7.bit m2_p3_5g_txneg_s1.bit
run() { # label gsbit m2bit k
  O=$L/$1_r$4
  fpga-jtag m2 $3 -r 2>&1 | tail -1 | grep -v -i done; fpga-jtag gs $2 -r 2>&1 | tail -1 | grep -v -i done; sleep 3
  for b in m2 gs; do (cd $T; fpga-jtag $b run python3 eyescan.py set RX_CDR_SET_ACC_CONFIG=2 >/dev/null 2>&1; fpga-jtag $b run python3 eyescan.py set RX_CDR_SET_ACC_CONFIG=0 >/dev/null 2>&1); done; sleep 2
  for b in m2 gs; do (cd $T; fpga-jtag $b run python3 eyescan.py health -n 3 --interval 0.5 --label "$1 r$4" --out "$O.health_$b.json" 2>&1 | grep -E "^HEALTH|Error"); done
  for b in m2 gs; do echo "JTAG $1 r$4 $b: $(cd $T; fpga-jtag $b run python3 ber_jtag_check.py --samples 200 2>&1 | tail -1)"; done
  (cd $T; timeout 8 python3 ber_mon.py watch --secs 4 2>&1 | tail -1 | sed "s/^/UART $1 r$4: /")
}
for k in 1 2 3; do run t14_2g5 gs_sd_2g5p1_txneg_s7.bit m2_e1_2g5p1_txneg_s2.bit $k; done
for k in 1 2 3; do
  run t14_p2 gs_p2_5g_txneg_s7.bit m2_p2_5g_txneg_s1.bit $k
  run t14_p3 gs_p3_5g_txneg_s7.bit m2_p3_5g_txneg_s1.bit $k
done
python3 $T/lab/health_table.py $L/t14_*_r*.health_*.json
rm -f /home/pi/gs.owner; echo "LAB14 DONE $(date +%T)"
