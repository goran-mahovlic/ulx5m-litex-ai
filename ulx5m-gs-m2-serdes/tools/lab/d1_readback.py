#!/usr/bin/env python3
"""d1_readback.py - TASK-5559 K6/D1 (CALIBRATION_OPTIONS_20261017_v2 §3.3): after a load of the final bits, every field
of the final settings table reads back what the bit is meant to hold, on both boards. No writes.

    cd ~/ulx5m-serdes/tools; python3 lab/d1_readback.py --intent ../t5559/k6/intent.json --out ../t5559/k6/d1_<load>.json

intent.json = {"gs": {"FIELD": value, ...}, "m2": {...}}. Exit 0 = 0 differences on both boards."""
import argparse
import json
import subprocess
import sys
import os


def diff(intent, got):
    """{board: {field: (want, got)}} for every field whose readback differs (missing = None)."""
    out = {}
    for b, want in intent.items():
        d = {f: (v, got.get(b, {}).get(f)) for f, v in want.items() if got.get(b, {}).get(f) != v}
        if d:
            out[b] = d
    return out


def read(board, fields):
    p = subprocess.run('fpga-jtag %s run python3 eyescan.py get %s' % (board, ' '.join(fields)), shell=True,
                       cwd=os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'), capture_output=True, text=True)
    last = (p.stdout + p.stderr).strip().splitlines()[-1]
    return {k: int(v) for k, v in (kv.split('=', 1) for kv in last.split() if '=' in kv and not kv.startswith('board='))}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--intent', required=True)
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    intent = json.load(open(a.intent))
    got = {b: read(b, list(f)) for b, f in intent.items()}
    d = diff(intent, got)
    json.dump({'intent': intent, 'got': got, 'diff': d}, open(a.out, 'w'), indent=1)
    n = sum(len(f) for f in intent.values())
    print('D1 fields=%d diff=%d %s' % (n, sum(len(x) for x in d.values()), json.dumps(d)))
    return 0 if not d else 1


if __name__ == '__main__':
    sys.exit(main())
