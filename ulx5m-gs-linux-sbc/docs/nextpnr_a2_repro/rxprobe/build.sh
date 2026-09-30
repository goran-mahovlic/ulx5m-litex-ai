#!/bin/bash
# rxprobe/build.sh (TASK-5094): RX pin probe for the CCGM1A2, two variants (IDDR on die 1B / fabric FFs), local A2
# toolchain, force_die=1A for the logic, gmpack --reset. Prints the sha256 of rxp_iddr.bit and rxp_fab.bit.
set -euo pipefail
H=$(cd "$(dirname "$0")" && pwd); O=${OUT:-$HOME/.tmp/a2/t5094rxp}; mkdir -p $O
export TMPDIR=${TMPDIR:-$HOME/.tmp} PATH=$HOME/app/raid/tools/oss-cad-suite-20260928/bin:$PATH
T=$HOME/app/raid/tools/nextpnr-a2fix/bin; CS=$(dirname "$(which yosys)")/../share/yosys/gatemate/cells_sim.v
cd $O; cp $H/top.v $H/top_tb.v $H/top.ccf $H/../die1b_ff_t5095/sr/selfrst.v .
iverilog -g2012 -DTICKW=16 -o tb top_tb.v top.v selfrst.v $CS && vvp -n tb | grep LINE | tail -1
for v in iddr fab; do
  D=""; [ $v = fab ] && D="-DFAB"
  yosys -q -p "read_verilog $D top.v selfrst.v; synth_gatemate -top top -luttree -nomx8; write_json rxp_$v.json" 2>&1 | grep -v tri-state || true
  $T/nextpnr-himbaechel --device CCGM1A2 --json rxp_$v.json --vopt ccf=top.ccf --vopt out=rxp_$v.txt --vopt force_die=1A \
    --freq 125 --timing-allow-fail > rxp_$v.np.log 2>&1
  $T/gmpack --reset rxp_$v.txt rxp_$v.bit
  python3 $HOME/app/regoc_system/tools/gm_cfgrst_check.py rxp_$v.bit
done
grep -h "Constraining.*eth_rx_ctl" rxp_*.np.log
sha256sum rxp_iddr.bit rxp_fab.bit
