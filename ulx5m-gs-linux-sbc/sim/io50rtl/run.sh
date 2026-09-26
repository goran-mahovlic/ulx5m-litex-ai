#!/bin/bash
# TASK-4999: RTL sim of the generated LiteEth SoC (Verilator --timing). run.sh <build/<dir>/gateware>
# Stimulus: ICMP echo requests (frames.py SIZES) on RGMII RX + ARP reply on request; checks the TX
# frames (FCS, length, payload). Exit 0 = every ICMP reply <= 128 B payload OK.
set -e; G=$(realpath "$1"); cd "$(dirname "$0")"
export PATH=/home/klaudio/app/raid/tools/oss-cad-suite-20260923/bin:$PATH TMPDIR=/home/klaudio/.tmp
python3 frames.py gen >/dev/null
python3 - <<'PY'
lines=[l.strip() for l in open('rx_frames.hex') if l.strip()]
b=[]; idx=[]
for l in lines:
    fr=bytes.fromhex(l); idx.append((len(b),len(fr))); b+=list(fr)
open('rx_bytes.memh','w').write('\n'.join('%02x'%x for x in b)+'\n')
open('rx_index.memh','w').write('\n'.join('%08x'%v for p in idx for v in p)+'\n')
PY
N=$(( $(grep -c . rx_frames.hex) - 1 ))
cp "$G"/*_mem.init . 2>/dev/null || true
rm -rf obj_dir
verilator --binary --timing -j 24 -Wno-fatal -Wno-lint -Wno-style -Wno-MULTIDRIVEN -Wno-TIMESCALEMOD \
  --top-module tb -DNREQ=$N -o vsim tb.v stubs.v "$G"/intergalaktik_ulx5m_gs.v ../../tools/uhello/mdio_core.v cells_min.v > vbuild.log 2>&1
./obj_dir/vsim > vrun.log 2>&1
grep -E 'TX frame|END' vrun.log
python3 frames.py check frames_tx.txt
