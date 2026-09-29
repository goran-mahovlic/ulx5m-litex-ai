#!/bin/bash
# Minimal repro (TASK-5092): on CCGM1A2 the GateMate clock router routes a PLL output without CC_BUFG through CPE
# bridges (CPE.IN*_int -> CPE.MUXOUT_int) to its users on die 1B and binds them before router2; router2 then aborts
# at once with "Failed to route arc 0.0 ... to Xn/CPE.D*_*_int". Same design on CCGM1A1, or with --vopt no-bridges: OK.
# (With the fix the design routes; the fabric clock then shows hold violations, hence --timing-allow-fail.)
# usage: NEXTPNR=/path/to/nextpnr-himbaechel [SEED=1] [DEVICE=CCGM1A2] ./run.sh [extra nextpnr args]
set -e
cd "$(dirname "$0")"
# all logic to die 1B (the PLL stays on die 1A, its CLK0 is used as a clock without CC_BUFG); CCGM1A1 has no 1B
DIE='setattr -set GATEMATE_DIE "1B" t:CC_DFF t:CC_LUT* t:CC_L2T*;'
[ "${DEVICE:-CCGM1A2}" = CCGM1A1 ] && DIE=
yosys -q -p "read_verilog top.v; synth_gatemate -top top -luttree -nomx8 -noclkbuf; $DIE write_json top.json"
${NEXTPNR:-nextpnr-himbaechel} --device ${DEVICE:-CCGM1A2} --json top.json --vopt ccf=top.ccf --vopt out=top.txt \
    --router router2 --freq 60 --timing-allow-fail --seed ${SEED:-1} "$@"
