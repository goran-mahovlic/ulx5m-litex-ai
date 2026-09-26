#!/bin/bash
# TASK-5047: one row of the mitigation table per build: PLL lock drops under SDRAM load -> picture drop-outs.
#   tools/dvi/mitigation_sweep.sh dvistdy_1 dvilr0_1 dvislew_1 dvis16_1 dvipix_1      (two-clock BIOS builds)
# Per build (bitstream build/s_<n>/gateware/*.bit, CSR addresses from build/s_<n>/csr.csv):
#   BIOS: test picture, counters + STDY, re-arm STDY (pll_stdy_rst 1 -> 0), STDY, 2x mem_test 32 MiB, counters + STDY
#   HDMI capture: 40 snapshots every 2 s during the load (N = no signal).
# Output: ~/.tmp/t5047/sw_<n>/{uart.txt,cap/,row.txt}; all rows in ~/.tmp/t5047/sweep_table.txt
# Reading: pll_*_unlocks = falling edges of the RAW USR_PLL_LOCKED seen at 25 MHz (lower bound);
#   pll_stdy bit i = 1 if the PLL's own sticky LOCKED_STDY never dropped since the re-arm (DS1001 Fig. 2.33).
cd "$(dirname "$0")/../.."
PI=fpga-klaudio@192.168.10.14
timeout 5 ssh -o ConnectTimeout=4 $PI true || { echo "Pi unreachable"; exit 2; }
scp -q tools/sd/bios_cmds.sh $PI:/tmp/t5040_bios_cmds.sh; scp -q tools/dvi/testimg_cmds.sh $PI:/tmp/t5040_testimg.sh
csr() { awk -F, -v n="$2" '$1=="csr_register" && $2==n {print $3}' build/s_$1/csr.csv; }
for n in "$@"; do
  D=~/.tmp/t5047/sw_$n; mkdir -p $D/cap; rm -f $D/uart.txt $D/cap/*
  BIT=$(ls build/s_$n/gateware/*.bit); UA=$(csr $n main_pll_sys_unlocks); SR=$(csr $n main_pll_stdy_rst)
  FA=$(csr $n video_fb2x_frames)
  R="mem_read $UA 12"
  NH=1; grep -q "csr_base,ethmac" build/s_$n/csr.csv && NH=     # netboot SoC: hide boot.json -> BIOS console
  HOLD=$(grep -c "Hold/min time violation for" ~/.tmp/t5032/soc_$n.log 2>/dev/null)
  [ "${HOLD:-0}" != 0 ] && echo "WARN $n: nextpnr reports $HOLD hold violation(s) - such builds were dead on the board (TASK-5047)"
  scp -q $BIT $PI:/tmp/sw_$n.bit
  ( ssh $PI "fuser /dev/ttyACM0 >/dev/null 2>&1 && { echo ttyACM0 BUSY; exit 2; }; cd /tmp && mapfile -t T < <(bash t5040_testimg.sh); \
      NOHIDE=$NH WAIT=1 CONSOLE_WAIT=90 TAILN=400 timeout 300 bash t5040_bios_cmds.sh /tmp/sw_$n.bit \"\${T[@]}\" \
      \"$R\" \"mem_write $SR 1\" \"mem_write $SR 0\" \"$R\" \
      'mem_test 0x41000000 0x2000000' 'mem_test 0x41000000 0x2000000' \"$R\" \"mem_read $FA 12\"" > $D/uart.txt 2>&1 ) &
  sleep 30; tools/dvi/idle_series.sh $D/cap 40 2 > $D/cap/series.txt; wait
  python3 - "$D/uart.txt" "$D/cap/series.txt" "$n" > $D/row.txt <<'PY'
import re, sys
t = open(sys.argv[1], errors="replace").read().splitlines()
v = []
for i, l in enumerate(t):
    if re.search(r"mem_read 0xf000[0-9a-f]{4} 12", l):
        for m in t[i+1:i+4]:
            w = re.findall(r"^0x[0-9a-f]{8}\s+((?:[0-9a-f]{2} ){12})", m)
            if w:
                b = w[0].split(); v.append([int("".join(b[k+3:k-1 if k else None:-1]), 16) for k in (0, 4, 8)]); break
ns = re.findall(r"NO-SIGNAL frames: (\d+)/(\d+)", open(sys.argv[2]).read())
if len(v) >= 3:
    a, b = v[1], v[2]
    print(f"{sys.argv[3]:12s} sys_unl +{(b[0]-a[0]) & 0xffff:5d}  2nd_unl +{(b[1]-a[1]) & 0xffff:5d}  "
          f"stdy re-armed={a[2]:#x} after_load={b[2]:#x}  no-signal {ns[0][0] if ns else '?'}/{ns[0][1] if ns else '?'}")
else:
    print(f"{sys.argv[3]:12s} parse error: {len(v)} counter reads")
PY
  cat $D/row.txt | tee -a ~/.tmp/t5047/sweep_table.txt
done
