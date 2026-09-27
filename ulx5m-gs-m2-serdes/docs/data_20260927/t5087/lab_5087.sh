#!/bin/bash
# TASK-5087: before a local X2 on M2 — does CDR_CKI != 0 keep today's 0 ppm link, and how far can the CDR be pushed off
# frequency? 2.5 G best pair (gs_sd_2g5p1_txneg_s7 / m2_e1_2g5p1_txneg_s2 = the *_cki0 rebuilds, same sha256).
#  A: cki0 (baseline) and cki1/2/4 bits, 2 loads x 60 s each (interleaved per round).
#  B: CKI 0, m2 RX: fixed frequency offset via RX_CDR_FREQ_ACC override (RX_CDR_SET_ACC_CONFIG bit1), +/-X, 1 x 30 s;
#     gs->m2 carries the offset, m2->gs is the control. health_m2 shows whether FREQ_ACC_VAL reads the forced value.
#  C: cki2 bits, m2: force FREQ_ACC=+1024, then release (SET_ACC_CONFIG=0) and read FREQ_ACC_VAL 10 x 1 s -> back to ~0?
cd /home/pi/ulx5m-serdes/t5087; export ME=TASK-5087 KEEP_LEASE=1; L=$PWD/log; mkdir -p $L/tmp
T=/home/pi/ulx5m-serdes/tools
own=$(cat /home/pi/gs.owner 2>/dev/null)
if [ -n "$own" ] && [ "${own%% *}" != TASK-5087 ]; then
  age=$(( $(date +%s) - $(echo "$own" | awk '{print $2}') )); [ "$age" -lt 7200 ] && { echo "leased: $own"; exit 3; }
fi
echo "TASK-5087 $(date +%s) SerDes CDR_CKI / ppm tolerance before local X2 on M2 (jelena)" > /home/pi/gs.owner
sha256sum *.bit
for k in 1 2; do
  for c in 0 1 2 4; do
    echo "== A cki$c round $k $(date +%T)"
    LOG=$L/tmp $T/lab/abrun.sh gs_cki${c}_2g5p1_txneg_s7.bit m2_cki${c}_2g5p1_txneg_s2.bit 60 1 "a_cki$c||"
    for f in $L/tmp/*_r1*.json; do b=$(basename $f); mv $f $L/${b/_r1/_r$k}; done
  done
done
for x in 16 128 1024 8192; do
  for s in p n; do
    v=$x; [ $s = n ] && v=$((32768 - x))
    echo "== B inj $s$x (FREQ_ACC=$v) $(date +%T)"
    LOG=$L $T/lab/abrun.sh gs_cki0_2g5p1_txneg_s7.bit m2_cki0_2g5p1_txneg_s2.bit 30 1 "b_inj_$s$x||m2:RX_CDR_FREQ_ACC=$v,RX_CDR_SET_ACC_CONFIG=2"
  done
done
echo "== C convergence $(date +%T)"
fpga-jtag m2 m2_cki2_2g5p1_txneg_s2.bit -r 2>&1 | tail -1; fpga-jtag gs gs_cki2_2g5p1_txneg_s7.bit -r 2>&1 | tail -1; sleep 3
fpga-jtag m2 run python3 $T/eyescan.py get RX_CDR_CKI RX_CDR_CKP RX_CDR_LOCKED RX_CDR_FREQ_ACC_VAL
fpga-jtag m2 run python3 $T/eyescan.py health -n 3 --label "c_free" --out $L/c_free.json | tail -1
fpga-jtag m2 run python3 $T/eyescan.py set RX_CDR_FREQ_ACC=1024 RX_CDR_SET_ACC_CONFIG=2
fpga-jtag m2 run python3 $T/eyescan.py health -n 3 --label "c_forced" --out $L/c_forced.json | tail -1
fpga-jtag m2 run python3 $T/eyescan.py set RX_CDR_SET_ACC_CONFIG=0
fpga-jtag m2 run python3 $T/eyescan.py health -n 10 --label "c_released" --out $L/c_released.json | tail -1
for b in m2 gs; do echo "jtag_check cki2 $b: $(fpga-jtag $b run python3 $T/ber_jtag_check.py --samples 100 2>&1 | tail -1)"; done
python3 $T/lab/ab_table.py --runs --rank $L/a_*_r*.json $L/b_*_r*.json
rm -f /home/pi/gs.owner; echo "LAB5087 DONE $(date +%T)"
