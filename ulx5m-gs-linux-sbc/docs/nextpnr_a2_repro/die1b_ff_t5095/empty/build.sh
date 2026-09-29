#!/bin/bash
# build.sh (TASK-5096): "reset" streams with no logic (UART TX held idle-high on IO_NB_B5) for series E and J (§5.8).
# empty_a2_r.bit   = CCGM1A2, gmpack --reset   (A2 stream: 1B then 1A, each PATH/CFGRST/D2D/PLL/CHG_STATUS)
# empty_a1_r.bit   = CCGM1A1, gmpack --reset   (single-die stream, for 1B's own TAP at --index-chain 1)
set -euo pipefail
H=$(cd "$(dirname "$0")" && pwd); O=${OUT:-$HOME/.tmp/a2/t5096empty}; mkdir -p $O; cd $O
export PATH=$HOME/app/raid/tools/oss-cad-suite-20260928/bin:$PATH; T=$HOME/app/raid/tools/nextpnr-a2fix/bin
yosys -q -p "read_verilog $H/empty.v; synth_gatemate -top top -luttree -nomx8; write_json empty.json"
for dev in CCGM1A2 CCGM1A1; do
  $T/nextpnr-himbaechel --device $dev --json empty.json --vopt ccf=$H/empty.ccf --vopt out=empty_$dev.txt \
    --timing-allow-fail > np_$dev.log 2>&1
done
$T/gmpack --reset empty_CCGM1A2.txt empty_a2_r.bit; $T/gmpack --reset empty_CCGM1A1.txt empty_a1_r.bit
sha256sum empty_a2_r.bit empty_a1_r.bit
