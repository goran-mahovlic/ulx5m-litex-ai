#!/bin/bash
# TASK-5531 P4 (REVIEW_INIT §8): health + short BER after a FLASH boot (Goran's reset), with NO JTAG write.
# Only reads: eyescan.py get (SerDes regs; TX_AMP 12 = the amp12 *_auto bits booted, 31 = an old bit), read-only
# ber_jtag_check (PEER), gs UART ber_long (BER both directions + delta loss_cnt + synced share of the window).
# Usage on the Pi:  RESET="<kind of reset, from Goran>" BS=300 bash p4_flash_boot.sh <outdir>
set -u
O=${1:?outdir}; T=/home/pi/ulx5m-serdes/tools; mkdir -p $O; BS=${BS:-300}
echo "TASK-5531 $(date +%s) P4 flash-boot read-only check ~$((BS/60+3)) min (jelena)" > /home/pi/gs.owner
J() { (cd $T; fpga-jtag $1 run python3 eyescan.py "${@:2}" 2>&1 | tail -1 | sed 's/board=//'); }
PEER() { (cd $T; fpga-jtag $1 run python3 ber_jtag_check.py --samples $2 2>&1 | tail -1 | sed 's/.*rx: /rx: /'); }
ST="RX_CDR_LOCKED RX_EQA_LOCKED RX_CDR_SET_ACC_CONFIG RX_CDR_FREQ_ACC_VAL TX_AMP RX_TH_MON RX_OFFSET PLL_LOCKED"
{
echo "== P4 $(date '+%F %T') reset='${RESET:-?}' $(vcgencmd get_throttled) $(vcgencmd measure_temp)"
echo "S gs: $(J gs get $ST)"
echo "S m2: $(J m2 get $ST)"
echo "PEER m2: $(PEER m2 200) | gs: $(PEER gs 200)"
(cd $T; timeout $((BS+300)) python3 lab/ber_long.py --secs $BS --every 60 --out $O/p4.jsonl 2>&1 | grep -E 'TOTAL|SYNC|NOUART')
echo "S2 gs: $(J gs get $ST)"
echo "S2 m2: $(J m2 get $ST)"
echo "P4 DONE $(date +%T)"
} 2>&1 | tee $O/p4.out
rm -f /home/pi/gs.owner
