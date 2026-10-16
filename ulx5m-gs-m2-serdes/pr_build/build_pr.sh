#!/bin/bash
# build_pr.sh <gs|m2> <name> [chparam args...]   e.g. build_pr.sh gs 2g5p1_txneg_amp12 N1 1 N2 5 ... OV_TX_AMP 12
# Same design as ../gateware/ber/build_ber.sh (sources read from there, not copied), but the Cologne Chip flow:
# CC yosys (synth_gatemate -vlog) -> CC p_r 4.2 -> gm_add_cfgrst.py (gmunpack -> gmpack --reset) -> gm_cfgrst_check.
# Differences to build_ber.sh, all forced by the tools (docs/PR_BUILD_20261016.md §2):
#  - p_r defaults otherwise. NB: p_r "-opt" RESETS a boolean (+opt sets), so "-cCP" (CC workspace Makefile) turns the
#    default cCP=True off; we keep cCP=True (the try with -cCP False needed 49k ripups vs 25).
#  - no -luttree: p_r 4.2 stops with exit 4 at "ROUTER started" on the -luttree netlist (L2T5 cells), every variant;
#  - no seed (p_r has none, it is deterministic), no --freq (p_r has no clock target; -tm 3 = worst corner as nextpnr);
#  - no --device: p_r 4.2 builds CCGM1A1 only; both boards are A1 (gs: 1 device in the JTAG chain, docs/PR_BUILD §1).
# CC_TOOLCHAIN (env): cc-toolchain-linux dir. OSS_CAD_SUITE (env): for gmunpack/gmpack (default oss-cad-suite-20260923).
set -e
cd "$(dirname "$0")"
CC=${CC_TOOLCHAIN:-/home/klaudio/app/raid/tools/cc-toolchain/cc-toolchain-linux}/bin
export OSS_CAD_SUITE=${OSS_CAD_SUITE:-/home/klaudio/app/raid/tools/oss-cad-suite-20260923}
B=$1; N=$2; shift 2; CP=""
while [ $# -ge 2 ]; do CP="$CP chparam -set $1 $2 top_$B;"; shift 2; done
S=$(cd ../gateware/ber && pwd); LINK=ber_link.v; [ "$B" = gs ] && LINK=ber_link_gs.v
O=build/${B}_${N}; mkdir -p $O
"$CC/yosys/yosys" -q -l $O/yosys.log -p "read_verilog -I$S $S/$LINK $S/ber_top.v; $CP synth_gatemate -top top_$B -nomx8 -vlog $O/s.v"
(cd $O && "$CC/p_r/p_r" -i s.v -o g -ccf $S/top_$B.ccf -tm 3 > pr.log 2>&1) || { echo "p_r FAILED, see $O/pr.log"; exit 1; }
grep -q "not routed: 0" $O/pr.log || { echo "p_r left unrouted nets"; exit 1; }
"$OSS_CAD_SUITE/bin/gmunpack" $O/g_00.cfg.bit $O/pr_unpacked.txt > $O/gmunpack.log 2>&1
python3 /home/klaudio/.claude/regoc/tools/fpga/gm_add_cfgrst.py $O/g_00.cfg.bit $O/${B}_${N}_pr_CFGRST.bit > $O/cfgrst.log
python3 /home/klaudio/.claude/regoc/tools/fpga/gm_cfgrst_check.py $O/${B}_${N}_pr_CFGRST.bit   # gate: exit 1 = no CMD_CFGRST
echo "$O/${B}_${N}_pr_CFGRST.bit $(python3 tools/pr_clocks.py $O g | sed 's/.*= //; s/ *longest.*//' | tr -s ' ' | tr '\n' ' ')"
