#!/bin/bash
# TASK-5044 (Dora, revizija TASK-5040/5043): which supply path turns SDRAM traffic into PLL lock loss?
# Software-only discriminator, no soldering. Same dvipll_1 bitstream as the reference measurement (+3787/+2665).
#
#   P1 VDD_CORE -> VDD_PLL (R23 1R + C42 100n)      : lock loss follows controller/core ACTIVITY, not data
#   P2 +1V8 rail (SDRAM VDD/VDDQ + banks WB/WC/NA/NB : lock loss follows DQ DATA TOGGLING; +1V8 also feeds the
#      via R116 0R) -> Y1 25 MHz XO / VDD_CLK / SB     25 MHz XO Y1 (no filter), VDD_CLK (U4.T14) and, via R122
#                                                      4R7, VDD_SB (clk25 input IO_SB_A8)
#
# Same address range and length in every step, so the command count on the SDRAM bus is comparable; only the
# data on DQ changes: constant writes (DQ static) vs mem_test (LFSR data), reads of zeros vs reads of LFSR data.
# Step A of the HW patch (10 uF on TP6) only fixes P1. If this shows P2, step A is expected to NOT help.
#
# Use (container):  tools/dvi/pll_discriminator.sh [bit] [tag]
# Needs the Pi (fpga-klaudio@192.168.10.14), ttyACM0 free. Output: ~/.tmp/t5044/pd_<tag>/{uart.txt,result.txt}
set -e
BIT=${1:-build/s_dvipll_1/gateware/intergalaktik_ulx5m_gs.bit}; TAG=${2:-dvipll1}
PI=fpga-klaudio@192.168.10.14; D=~/.tmp/t5044/pd_$TAG; mkdir -p $D; rm -f $D/*
UA=0xf0002000                      # main_pll_sys_unlocks, +4 = main_pll_video_unlocks (build/s_dvipll_1/csr.csv)
A=0x41000000; N=0x800000           # 32 MiB = 8 Mi words, clear of the framebuffer at 0x43f00000
R="mem_read $UA 8"
CMDS=( "$R"
       "mem_write $A 0x00000000 $N" "$R"        # W0: writes, DQ static low
       "mem_write $A 0xffffffff $N" "$R"        # W1: writes, DQ static high
       "crc $A 0x2000000" "$R"                  # R1: reads of constant data
       "mem_test $A 0x2000000" "$R"             # WR: LFSR data written + read back (reference load)
       "crc $A 0x2000000" "$R"                  # RX: reads of LFSR data (SDRAM drives toggling DQ)
       "mem_write $A 0x00000000 $N" "$R" )      # W0 again: repeatability
timeout 5 ssh -o ConnectTimeout=4 $PI true || { echo "Pi unreachable"; exit 2; }
scp -q "$BIT" $PI:/tmp/pd_$TAG.bit
scp -q tools/sd/bios_cmds.sh $PI:/tmp/t5044_bios_cmds.sh
ssh $PI "fuser /dev/ttyACM0 >/dev/null 2>&1 && { echo ttyACM0 BUSY; exit 2; }; cd /tmp && \
  NOHIDE=1 WAIT=14 CONSOLE_WAIT=40 TAILN=400 timeout 300 bash t5044_bios_cmds.sh /tmp/pd_$TAG.bit $(printf "'%s' " "${CMDS[@]}")" \
  > $D/uart.txt 2>&1 || true
# counters -> deltas per step
python3 - "$D/uart.txt" > $D/result.txt <<'PY'
import re, sys
t = open(sys.argv[1], errors="replace").read().splitlines()
vals = []
for i, l in enumerate(t):
    if re.search(r"mem_read 0xf0002000", l):
        for m in t[i+1:i+4]:
            w = re.findall(r"^0xf0002000\s+((?:[0-9a-f]{2} ){8})", m)
            if w:
                b = w[0].split(); vals.append((int(b[1]+b[0], 16), int(b[5]+b[4], 16))); break
steps = ["W0 const 0", "W1 const 1", "R1 read const", "WR mem_test", "RX read LFSR", "W0 repeat"]
print("step            sys_delta  video_delta")
for s, (a, b) in zip(steps, zip(vals, vals[1:])):
    print(f"{s:15s} {(b[0]-a[0]) & 0xffff:9d}  {(b[1]-a[1]) & 0xffff:11d}")
if len(vals) < 7: print(f"WARN: only {len(vals)} counter reads parsed (expected 7)")
PY
cat $D/result.txt
cat <<'EOF'
Read: P2 (+1V8 data toggling) if WR >> W0/W1 and RX >> R1. P1 (core activity) if W0 ~ W1 ~ WR and R1 ~ RX.
EOF
