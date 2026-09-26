#!/bin/bash
# TASK-5007: full 1,1 V sequence. Run on the Pi: /tmp/t5007_run_all.sh > /tmp/t5007_run.log 2>&1
# Pre-check: JTAG must answer (TDO not stuck).
sudo -n /usr/local/bin/openFPGALoader -c dirtyJtag --detect 2>&1 | grep -qi idcode || { echo "JTAG DEAD (no IDCODE) - abort"; exit 3; }
# 1) PLL frequency (spare PLL fine-tune: 12.5 MHz ref -> ~0x09A, 10 -> 0x046, 8.33 -> 0x01A, 6.25 -> 0x004)
for b in t4999_b66 t4999_b52 t4999_b54 t4999_b55 t5007_sys_lp t5007_sys_sp t5007_sys_ec; do
  [ -f /tmp/$b.bit ] && /tmp/t5007_pitest.sh /tmp/$b.bit 0
done
# 2) best bitstreams, full net test
for b in t4999_diag6 t4999_b2 t4999_prod_clk25_ddr12 t4999_b62; do
  /tmp/t5007_pitest.sh /tmp/$b.bit 1
done
