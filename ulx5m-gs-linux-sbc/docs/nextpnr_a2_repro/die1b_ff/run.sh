#!/bin/bash
# Die-1B hardware test (TASK-5092). Builds two bitstreams:
#   top_1a.bit : everything on die 1A (control, --vopt force_die=1A)
#   top_x.bit  : per bit g: a[g] (1A) -> CC_DFF on 1B -> CC_DFF on 1A      mask E (registered through 1B)
#                          a[g] (1A) -> CC_LUT1 on 1B -> CC_DFF on 1A       mask K bits 31..4 (combinational through 1B)
#                plus probes on 1B: K bit0 = toggle FF seen toggling, bit1 = FF with D=1, bit2 = FF with D=0, bit3 = 1
# UART 115200 on IO_NB_B5 prints "E<hex> K<hex> N<frames>" every 0.67 s. Send a byte with a zero bit (0x00) on
# IO_NA_B6 to clear the masks after loading (GateMate ignores init values; CC_USR_RSTN gave no reset pulse on the A2).
# Expected when everything works: top_1a and top_x both E00000000 K0000000B (toggle seen, D=1 -> 1, D=0 -> 0).
# Measured 29.09.2026 (nextpnr t5092-a2, gmpack oss-cad 2026-09-28): top_1a E00000000 K0000000B;
#   top_x EFFFFFFFF K0000000C -> LUT path through 1B OK on 32/32, 1B flip-flops never update (D=1 reads 0, D=0 reads 1).
set -e
cd "$(dirname "$0")"
yosys -q -p "read_verilog top.v; synth_gatemate -top top -luttree -nomx8; write_json top.json"
python3 mark_dies.py top.json top_x.json
NP=${NEXTPNR:-nextpnr-himbaechel}
$NP --device CCGM1A2 --json top.json --vopt ccf=top.ccf --vopt force_die=1A --vopt out=top_1a.txt --freq 25 --timing-allow-fail
$NP --device CCGM1A2 --json top_x.json --vopt ccf=top.ccf --vopt out=top_x.txt --freq 25 --timing-allow-fail --write top_x.routed.json
gmpack --reset top_1a.txt top_1a.bit; gmpack --reset top_x.txt top_x.bit
# on the Pi: fpga-jtag gs top_x.bit -r --index-chain 0; printf '\000' > $UART; cat $UART
