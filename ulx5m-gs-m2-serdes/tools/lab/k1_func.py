#!/usr/bin/env python3
"""k1_func.py - TASK-5559 K1-c (CALIBRATION_OPTIONS_20261017_v2 §3.1): does a 0x2B reset level work, judged by BER.

    cd ~/ulx5m-serdes/tools; python3 lab/k1_func.py --rx gs --levels eqa,cdr,rx --reps 3 --out ../t5559/k1/k1c.jsonl

Per repetition on the receiver --rx: damage the adaptation (freeze RX_TAPW=+3, then restore = adaptation on again from
the damaged point; aba2 left 1e-6..2e-5 this way), measure --secs (first 10 s window dropped), apply the level
(link_gate.readapt_cmds: OVR=1 + W/C strobe, then release), wait --settle, measure again. The 0x2B readback is not used.
A level WORKS if the received direction drops >= 2 decades on every repetition (v2 §3.1: >= 2 decades on 3/3).
--table prints the verdict per level from the JSONL."""
import argparse
import signal
import json
import math
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from link_gate import Uart, diag_summary, measure, readapt_cmds, DIRS  # noqa: E402

RXDIR = {'gs': 'm2_to_gs', 'm2': 'gs_to_m2'}
POINT = ['RX_CDR_LOCKED', 'RX_EQA_LOCKED', 'RX_EQA_TAPW', 'RX_TH_MON', 'RX_OFFSET', 'RX_EN_EQA']


def decades(before, after, floor_bits):
    """log10(BER before / BER after); a 0-error 'after' counts as 1 error (conservative)."""
    b = before['ber']
    a = after['ber'] if after['err'] else 1.0 / floor_bits if floor_bits else None
    if not b or not a:
        return None
    return math.log10(b / a)


def table(recs, min_dec=2.0, min_before=1e-7):
    """Per level: reps, reps with a real damage (before >= min_before), reps with >= min_dec decades, verdict."""
    out = {}
    for r in recs:
        o = out.setdefault(r['level'], {'reps': 0, 'damaged': 0, 'win': 0, 'dec': []})
        o['reps'] += 1
        if (r['before']['ber'] or 0) >= min_before:
            o['damaged'] += 1
            if r['dec'] is not None and r['dec'] >= min_dec:
                o['win'] += 1
        o['dec'].append(None if r['dec'] is None else round(r['dec'], 2))
    for o in out.values():
        o['works'] = o['damaged'] > 0 and o['win'] == o['damaged'] and o['damaged'] == o['reps']
    return out


def sh(cmd, timeout=120):
    p = subprocess.run(cmd, shell=True, cwd=os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'),
                       capture_output=True, text=True, timeout=timeout)
    return p.returncode, (p.stdout + p.stderr).strip().splitlines()[-1:] or ['']


def get(board, fields):
    _, l = sh('fpga-jtag %s run python3 eyescan.py get %s' % (board, ' '.join(fields)))
    return dict(kv.split('=', 1) for kv in l[0].split() if '=' in kv and not kv.startswith('board='))


def meas(secs, wps=31.25e6):
    u = Uart()
    try:
        d = diag_summary(measure(u, secs, 10, wps, dirs=DIRS), DIRS)
    finally:
        u.close()
    return d


def one(level, rx, secs, settle, dwell=0):
    k = RXDIR[rx]
    rec = {'level': level, 'rx': rx, 't': time.strftime('%Y-%m-%dT%H:%M:%S%z')}
    rec['damage'] = [sh('fpga-jtag %s run python3 eyescan.py freeze RX_TAPW=3' % rx)[1][0][:120]]
    try:
        if dwell:                               # aba2 held the pin ~48 s (3 s settle + 45 s measured) before restore
            p = meas(dwell)
            rec['pinned'] = {'ber': p['ber'].get(k), 'err': p['err'].get(k), 'bits': p['bits'].get(k)}
    finally:                                    # a kill during the dwell left gs frozen at TAPW 3 (k1p_b0p_frozen_invalid)
        rec['damage'].append(sh('fpga-jtag %s run python3 eyescan.py restore' % rx)[1][0][:160])
    time.sleep(2)
    rec['point_before'] = get(rx, POINT)
    m0 = meas(secs)
    rec['level_out'] = [sh('fpga-jtag %s run python3 eyescan.py %s' % (rx, c))[1][0][:120] for c in readapt_cmds(level)]
    time.sleep(settle)
    rec['point_after'] = get(rx, POINT)
    m1 = meas(secs)
    rec['before'] = {'ber': m0['ber'].get(k), 'err': m0['err'].get(k), 'bits': m0['bits'].get(k), 'all': m0}
    rec['after'] = {'ber': m1['ber'].get(k), 'err': m1['err'].get(k), 'bits': m1['bits'].get(k), 'all': m1}
    rec['dec'] = decades(rec['before'], rec['after'], m1['bits'].get(k))
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--rx', choices=RXDIR, default='gs')
    ap.add_argument('--levels', default='eqa,cdr,rx')
    ap.add_argument('--reps', type=int, default=3)
    ap.add_argument('--secs', type=float, default=30)
    ap.add_argument('--settle', type=float, default=3)
    ap.add_argument('--dwell', type=float, default=45, help='seconds the TAPW +3 pin is held (measured) before restore')
    ap.add_argument('--out')
    ap.add_argument('--table')
    a = ap.parse_args()
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(143))   # run the finally (restore) on kill
    if a.table:
        print(json.dumps(table([json.loads(l) for l in open(a.table) if l.strip()]), indent=1))
        return 0
    f = open(a.out, 'a')
    for rep in range(a.reps):
        for level in a.levels.split(','):
            r = one(level, a.rx, a.secs, a.settle, a.dwell)
            r['rep'] = rep + 1
            f.write(json.dumps(r) + '\n')
            f.flush()
            print('K1C %s rep=%d rx=%s pinned=%s before=%s (%s) after=%s (%s) dec=%s pt_after=%s' % (
                level, rep + 1, a.rx, (r.get('pinned') or {}).get('ber'), r['before']['ber'], r['before']['err'], r['after']['ber'], r['after']['err'],
                None if r['dec'] is None else round(r['dec'], 2), r['point_after']), flush=True)
    f.close()
    return 0


if __name__ == '__main__':
    sys.exit(main())
