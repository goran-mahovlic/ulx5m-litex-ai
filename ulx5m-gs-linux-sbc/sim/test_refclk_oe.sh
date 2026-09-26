#!/usr/bin/env bash
# TASK-4999 regression: in --diag builds the PHY XI clock (IO_EB_A3) must NOT depend on the
# sys PLL lock. refclk_oe used to be a sys-domain register -> held at 0 by the LiteX PLL reset
# (~locked) -> PHY without XI whenever the sys PLL did not lock (1.1 V SPEED: PLL0 OVF).
# Checks the generated Verilog: refclk_oe must be clocked by clk25 and never cleared by sys_rst.
set -e
cd "$(dirname "$0")/.."
export OSS_CAD_SUITE=${OSS_CAD_SUITE:-/home/klaudio/app/raid/tools/oss-cad-suite-20260923}
export LXROOT=${LXROOT:-/home/klaudio/app/litex-rgmii-ulx5m}
source ./env.sh >/dev/null 2>&1
out=$(mktemp -d)
python3 gateware/target_eth.py --gen-only --diag --ip 192.168.10.212 --output-dir "$out" >/dev/null 2>&1
v="$out/gateware/intergalaktik_ulx5m_gs.v"
fail=0
# the always block that assigns refclk_oe <= 1 must be clocked by the refoe domain (clk25)
blk=$(awk '/always @\(posedge/{hdr=$0} /refclk_oe <= 1.d1;/{print hdr}' "$v")
echo "refclk_oe set in: $blk"
echo "$blk" | grep -q "refoe_clk" || { echo "FAIL: refclk_oe not in the clk25 (refoe) domain"; fail=1; }
# and sys_rst must not clear it
if awk '/if \(sys_rst\)/{s=1} s&&/refclk_oe <= 1.d0/{print; exit}' "$v" | grep -q refclk_oe; then
  echo "FAIL: refclk_oe cleared by sys_rst"; fail=1; fi
rm -rf "$out"
[ $fail = 0 ] && echo "PASS" || exit 1
