#!/bin/bash
# tools/a2_soc_sr_build.sh (TASK-5094): the Linux SoC for the CCGM1A2 (A2) with the design-driven chip reset.
#  1. takes the LiteX gateware of an existing ULX5M-GS build (default build/s_usb5_pll60_s2_np1817, the TASK-5091 SoC),
#  2. adds selfrst.v (UART "R!" -> IO_SB_B8 low = RST_N net on gs, docs/nextpnr_a2_repro/die1b_ff_t5095/sr) to the top
#     level, clocked by the 20 MHz sys clock (clk25 would need a third GLBOUT): the console RX is sniffed in parallel,
#     the CPU still gets every byte,
#  3. synthesises once (yosys, same .ys as LiteX plus selfrst.v),
#  4. per variant: split (eth PHY domains on die 1B, tools/a2_die_split.py --from-io) or force_die=1A,
#  5. places/routes with the local A2 toolchain ~/app/raid/tools/nextpnr-a2fix (fixes B + C) for every seed in SEEDS,
#     in parallel, gmpack --reset + gm_cfgrst_check.py.
# Usage: tools/a2_soc_sr_build.sh [split|f1A] ...   env: SEEDS="1 2 3 4 5 6" OUT=~/.tmp/a2/t5094 SRC=<build dir>
set -euo pipefail
cd "$(dirname "$0")/.."
R=$PWD; SRC=${SRC:-build/s_usb5_pll60_s2_np1817}; G=$R/$SRC/gateware; O=${OUT:-$HOME/.tmp/a2/t5094}; mkdir -p $O
T=$HOME/app/raid/tools/nextpnr-a2fix/bin; SR=$R/docs/nextpnr_a2_repro/die1b_ff_t5095/sr
export PATH=$HOME/app/raid/tools/oss-cad-suite-20260928/bin:$PATH TMPDIR=$HOME/.tmp   # /tmp is a full 100 MB tmpfs: ABC fails there
SEEDS=${SEEDS:-"1 2 3 4 5 6"}; VARIANTS=${*:-split}

if [ ! -s $O/soc_sr.json ]; then
  cp $SR/selfrst.v $O/
  python3 - "$G/intergalaktik_ulx5m_gs.v" "$O/soc_sr.v" <<'EOF'
import re, sys
src = open(sys.argv[1]).read()
head = "module intergalaktik_ulx5m_gs ("
assert src.count(head) == 1, "top module header not found exactly once"
# new port: open-drain pad on IO_SB_B8 (= RST_N net on ULX5M-GS)
src = src.replace(head, head + "\n    inout  wire          a2_rst_pad,", 1)
top_start = src.index(head)
end = src.index("\nendmodule", top_start)
body = """
// TASK-5094: design-driven chip reset (selfrst.v). UART "R!" on serial_rx pulls IO_SB_B8 = RST_N low; the reset
// tri-states the pad, so the pulse ends by itself (~0.3 ms, A2_CCGM1A2_TASK-5092.md 5.8).
wire a2_rst_oe;
selfrst a2_selfrst (.clk(sys_clk), .rx(serial_rx), .rst_oe(a2_rst_oe));   // 20 MHz: -DSR_HALF=87 -DSR_FULL=174
assign a2_rst_pad = a2_rst_oe ? 1'b0 : 1'bz;
"""
src = src[:end] + body + src[end:]
open(sys.argv[2], "w").write(src)
EOF
  cp $G/intergalaktik_ulx5m_gs.ccf $O/soc_sr.ccf
  echo 'Net "a2_rst_pad" Loc = "IO_SB_B8";   # = RST_N (U4.T15) on ULX5M-GS, open drain from selfrst.v (TASK-5094)' >> $O/soc_sr.ccf
  sed -e "s#$G/intergalaktik_ulx5m_gs.v#$O/soc_sr.v\"\nread_verilog -DSR_HALF=87 -DSR_FULL=174 \"$O/selfrst.v#" \
      -e "s#write_json  *intergalaktik_ulx5m_gs.json#write_json $O/soc_sr.json#" \
      $G/intergalaktik_ulx5m_gs.ys > $O/soc_sr.ys
  grep -q "DSR_FULL=174 \"$O/selfrst.v" $O/soc_sr.ys && grep -q "$O/soc_sr.json" $O/soc_sr.ys
  (cd $G && yosys -l $O/soc_sr.yosys.log -q -s $O/soc_sr.ys)
  echo "[a2_soc_sr] synth done $(date +%T)"
fi
python3 - $O/soc_sr.json <<'EOF'
import json, sys
m = json.load(open(sys.argv[1]))["modules"]["intergalaktik_ulx5m_gs"]
# after flatten the cells are $abc$/$auto$ names; selfrst.v cells carry it in their src attribute (25 DFF + 12 ADDF)
n = [c for c in m["cells"].values() if "selfrst.v" in c.get("attributes", {}).get("src", "")]
pad = m["ports"]["a2_rst_pad"]["bits"]
buf = [c["type"] for c in m["cells"].values() if c["type"] == "CC_IOBUF" and c["connections"].get("IO") == pad]
assert len(n) >= 20 and sum(c["type"] == "CC_DFF" for c in n) >= 16, f"selfrst logic missing ({len(n)} cells)"
assert buf == ["CC_IOBUF"], f"a2_rst_pad has no tri-state pad buffer: {buf}"
print(f"[a2_soc_sr] netlist check: a2_rst_pad on a CC_IOBUF, {len(n)} selfrst cells")
EOF

# --placer-heap-cell-placement-timeout 0: placer_heap.cc computes max(10000, int(cells)*int(cells)/8) in int, which
# overflows from 46341 cells on; this SoC has more, so the limit silently drops to 10000 and every seed fails
# ("Unable to find legal placement for cell ... CPE_FF"). 0 = no limit (the pre-overflow limit was ~2.7e8).
CLKS="--clk grx_clk --clk gtx0_clk --clk gtx90_clk --clk ulx5msoc_gbephy_txc_g"
for v in $VARIANTS; do
  case $v in
    split) [ -s $O/soc_sr_split.json ] || python3 tools/a2_die_split.py $O/soc_sr.json $O/soc_sr_split.json --from-io $CLKS
           J=$O/soc_sr_split.json; X="" ;;
    f1A)   J=$O/soc_sr.json; X="--vopt force_die=1A" ;;
    *) echo "unknown variant $v"; exit 2 ;;
  esac
  for s in $SEEDS; do
    ( $T/nextpnr-himbaechel --device CCGM1A2 --json $J --vopt ccf=$O/soc_sr.ccf --vopt out=$O/${v}_s$s.txt \
        --vopt fpga_mode=3 $X --placer-heap-cell-placement-timeout 0 --router router2 --timing-allow-fail --freq 125 --seed $s > $O/${v}_s$s.log 2>&1 \
      && $T/gmpack --reset $O/${v}_s$s.txt $O/t5094_A2_sr_${v}_s$s.bit \
      && python3 $HOME/app/regoc_system/tools/gm_cfgrst_check.py $O/t5094_A2_sr_${v}_s$s.bit > $O/${v}_s$s.cfgrst 2>&1 \
      ; echo "$v s$s exit=$? $(date +%T)" >> $O/done.txt ) &
  done
done
wait
cat $O/done.txt
