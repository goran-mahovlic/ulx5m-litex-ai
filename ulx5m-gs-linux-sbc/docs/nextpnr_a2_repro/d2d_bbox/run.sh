#!/bin/bash
# Router speed repro (TASK-5092): 32 registers on die 1A feed 32 registers on die 1B and back (CC_DFF primitives,
# the 1B ones marked GATEMATE_DIE=1B). The placer puts them near X3..X13, but die-to-die connections exist only
# from X29, so router2 retries every crossing arc without its bounding box ("r2dbg"-style full-chip search).
# ad8527f8: router2 ~250-410 s; with fix_d2d_bbox_estimate.patch: ~11-14 s.
# usage: NEXTPNR=/path/to/nextpnr-himbaechel ./run.sh
set -e
cd "$(dirname "$0")"
yosys -q -p "read_verilog top.v; synth_gatemate -top top -luttree -nomx8; \
             setattr -set GATEMATE_DIE \"1A\" t:*; setattr -set GATEMATE_DIE \"1B\" c:*.ub; \
             setattr -unset GATEMATE_DIE t:CC_IBUF t:CC_OBUF t:CC_BUFG t:CC_USR_RSTN; write_json top.json"
${NEXTPNR:-nextpnr-himbaechel} --device CCGM1A2 --json top.json --vopt ccf=top.ccf --vopt out=top.txt \
    --router router2 --freq 25 --timing-allow-fail --seed ${SEED:-1} 2>&1 | grep -E "Die-to-die|Router2 time|ERROR"
