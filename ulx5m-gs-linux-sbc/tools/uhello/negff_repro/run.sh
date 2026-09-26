#!/bin/bash
# nextpnr GateMate: negedge CC_DFF merged into IOSEL (FF_OBF=true) loses CLK_INV (TASK-4999, 24.9.2026).
# Expected: q_neg IOSEL has INV_OUT1_CLOCK=1. Observed (nextpnr-0.11.1-31-g3edea68e): no INV -> posedge.
set -e; cd "$(dirname "$0")"; export PATH=/home/klaudio/app/raid/tools/oss-cad-suite-20260923/bin:$PATH
yosys -q -p "read_verilog neg.v; synth_gatemate -top top; write_json /tmp/neg.json"
nextpnr-himbaechel --device CCGM1A1 --json /tmp/neg.json --vopt ccf=neg.ccf --vopt out=/tmp/neg.txt --write /tmp/neg.r.json >/tmp/neg.log 2>&1
python3 -c "
import json;c=json.load(open('/tmp/neg.r.json'))['modules']['top']['cells']
p=c['\$iopadmap\$top.q_neg\$iosel']['parameters']; print('q_neg IOSEL:', p)
print('BUG PRESENT' if 'INV_OUT1_CLOCK' not in p else 'OK')"
