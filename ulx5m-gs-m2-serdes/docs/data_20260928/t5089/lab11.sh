#!/bin/bash
# TASK-5089 lab11: 2.5 G with SEPARATE refclks (local X2 on M2, C136/C137 off; Goran 28.09. ~11:00). GS unchanged (1 uF C127/C128/C42).
# Every load = fresh load m2 then gs (CFGRST, SRAM -r). After each load: RX_CDR_SET_ACC_CONFIG 2 -> 0 pulse on both boards
# (start-up rail trap, LOCAL_REFCLK_M2.md §4C; harmless with CKI 0), then health + 300 s ber_mon.
# Points, interleaved per round: cki1 = best pair + CDR_CKI 1; cki0 = best pair (same bits as §10.4 t79 reference).
cd /home/pi/ulx5m-serdes/t5089; L=$PWD/log; T=/home/pi/ulx5m-serdes/tools; mkdir -p $L
echo "TASK-5089 $(date +%s) 2.5G separate refclk A/B (regoc)" > /home/pi/gs.owner
sha256sum gs_cki1_2g5p1_txneg_s7.bit m2_cki1_2g5p1_txneg_s2.bit gs_sd_2g5p1_txneg_s7.bit m2_e1_2g5p1_txneg_s2.bit
run() { # label gsbit m2bit secs k
  O=$L/$1_r$5
  fpga-jtag m2 $3 -r 2>&1 | tail -1 | grep -v -i done; fpga-jtag gs $2 -r 2>&1 | tail -1 | grep -v -i done; sleep 3
  for b in m2 gs; do (cd $T; fpga-jtag $b run python3 eyescan.py set RX_CDR_SET_ACC_CONFIG=2 >/dev/null 2>&1; fpga-jtag $b run python3 eyescan.py set RX_CDR_SET_ACC_CONFIG=0 >/dev/null 2>&1); done; sleep 2
  for b in m2 gs; do (cd $T; fpga-jtag $b run python3 eyescan.py health -n 3 --interval 0.5 --label "$1 r$5" --out "$O.health_$b.json" 2>&1 | grep -E "^HEALTH|Error"); done
  ( cd $T; python3 ber_mon.py run --secs $4 --clear --json ) > $O.json
  echo "== $1 r$5 $(date +%T): $( cd $T; python3 -c "import json,sys;sys.path.insert(0,'lab');import ab_table as A;d=json.load(open('$O.json'));print('gs->m2 %.2e  m2->gs %.2e  rate gs %.0f m2 %.0f' % (A.ber(d['gs_to_m2']), A.ber(d['m2_to_gs']), d['gs_tx_rate_bps'], d['m2_tx_rate_bps']))" )"
}
for k in 1 2 3; do
  echo "== round $k $(date +%T)"
  run t89_cki1 gs_cki1_2g5p1_txneg_s7.bit m2_cki1_2g5p1_txneg_s2.bit 300 $k
  run t89_cki0 gs_sd_2g5p1_txneg_s7.bit m2_e1_2g5p1_txneg_s2.bit 300 $k
done
for b in m2 gs; do echo "jtag_check cki0 $b: $(cd $T; fpga-jtag $b run python3 ber_jtag_check.py --samples 200 2>&1 | tail -1)"; done
python3 $T/lab/ab_table.py --runs --rank $L/t89_*_r*.json
python3 $T/lab/health_table.py $L/t89_*_r*.health_*.json
rm -f /home/pi/gs.owner; echo "LAB11 DONE $(date +%T)"
