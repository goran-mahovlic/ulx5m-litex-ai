#!/bin/bash
# TASK-5095: build sr_x_nr.bit (die1b_ff + selfrst) and inv_sr_nr.bit (inv discriminator + selfrst) with the local A2
# toolchain ~/app/raid/tools/nextpnr-a2fix (nextpnr ad8527f8 + fixes B, C; gmpack b1eb52f) and run the simulations.
# Same flow as TASK-5093 (checked: it rebuilds inv_nr.bit byte-identical, sha256 2bcd50523a23de25).
set -euo pipefail
H=$(cd "$(dirname "$0")" && pwd); O=${OUT:-$HOME/.tmp/a2/t5095sr}; mkdir -p $O
export PATH=$HOME/app/raid/tools/oss-cad-suite-20260928/bin:$PATH; T=$HOME/app/raid/tools/nextpnr-a2fix/bin
CS=$(dirname "$(which yosys)")/../share/yosys/gatemate/cells_sim.v
cp $H/sr/selfrst.v $H/sr/selfrst_tb.v $H/sr/top_tb.v $H/sr/stub.v $H/sr/top.ccf $H/../die1b_ff/mark_dies.py $O/
cp $H/sr/top.v $O/sr_top.v; cp $H/inv_sr/top.v $O/inv_sr_top.v; cd $O
iverilog -o selfrst_tb selfrst_tb.v selfrst.v && vvp -n selfrst_tb | grep RESULT
for d in sr inv_sr; do
  yosys -q -p "read_verilog ${d}_top.v selfrst.v; synth_gatemate -top top -luttree -nomx8; write_json $d.json" 2>&1 | grep -v tri-state || true
  yosys -q -p "read_json $d.json; write_verilog -noattr ${d}_gate.v"
  iverilog -g2012 -o ${d}_gate_tb top_tb.v ${d}_gate.v stub.v $CS 2>/dev/null && echo "$d gate: $(vvp -n ${d}_gate_tb | grep RESULT)"
  python3 mark_dies.py $d.json ${d}_x.json
  $T/nextpnr-himbaechel --device CCGM1A2 --json ${d}_x.json --vopt ccf=top.ccf --vopt out=$d.txt --freq 25 \
    --timing-allow-fail --write $d.routed.json > $d.np.log 2>&1
  grep -q "rst_pad\[0\]' to pad 'IO_SB_B8' on die '1A'" $d.np.log
  $T/gmpack $d.txt ${d}_nr.bit   # no --reset, as the fresh-chip loads of TASK-5093
done
mv sr_nr.bit sr_x_nr.bit; sha256sum sr_x_nr.bit inv_sr_nr.bit
