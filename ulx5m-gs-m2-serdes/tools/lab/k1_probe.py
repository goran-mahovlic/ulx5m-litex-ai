#!/usr/bin/env python3
"""k1_probe.py - TASK-5559 K1-c, second method: does a 0x2B reset level EXECUTE on the silicon?

    cd ~/ulx5m-serdes/tools; python3 lab/k1_probe.py --boards gs,m2 --levels none,eqa,cdr,rx,pma --reps 3 --out ../t5559/k1/k1p.jsonl

On B0' the 'damage -> level -> BER' test of the plan cannot run: a TAPW +3 pin held 45 s gives 1e-7 and the adaptation
returns to 0 errors on its own after restore (k1c_b0p_d45). So instead: read the gs UART status line (cumulative
counters of both checkers), apply the level on one receiver, follow the lines for --follow s and record the deltas of
the RECEIVED direction of that board: sync losses (loss mod 32), bit errors, lowest synced flag. A level that executes
disturbs its receiver (an RX/CDR/PMA reset must drop sync; an EQA reset at least errors or a TH_MON/TAPW jump);
'none' (no write) is the control. Verdict per level: executes if every rep shows loss or errors above the control."""
import argparse
import json
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from link_gate import EOF, KEYS, M32, Uart, readapt_cmds  # noqa: E402

RXDIR = {'gs': 'm2_to_gs', 'm2': 'gs_to_m2'}
POINT = ['RX_CDR_LOCKED', 'RX_EQA_LOCKED', 'RX_EQA_TAPW', 'RX_TH_MON', 'RX_OFFSET']


def deltas(l0, ls, k):
    """Received direction k: max loss delta (mod 32), bit error delta, lowest synced over the lines after l0."""
    wk, ek, lk, sk = KEYS[k][0], KEYS[k][1], KEYS[k][2], KEYS[k][3]
    if not ls:
        return {'lines': 0, 'dloss': None, 'derr': None, 'synced_min': None}
    return {'lines': len(ls), 'dloss': max((l[lk] - l0[lk]) & 0x1F for l in ls),
            'derr': (ls[-1][ek] - l0[ek]) & M32, 'synced_min': min(l[sk] for l in ls)}


def verdict(recs):
    """Per (board, level): reps, reps disturbed (loss or errors or not synced), executes = all reps disturbed and the
    control 'none' of that board never disturbed."""
    out = {}
    for r in recs:
        o = out.setdefault('%s:%s' % (r['board'], r['level']), {'reps': 0, 'disturbed': 0})
        o['reps'] += 1
        d = r['d']
        if d['lines'] and (d['dloss'] or d['derr'] or d['synced_min'] == 0):
            o['disturbed'] += 1
    for key, o in out.items():
        b = key.split(':')[0]
        ctl = out.get(b + ':none', {'disturbed': 0})
        o['executes'] = o['reps'] > 0 and o['disturbed'] == o['reps'] and ctl['disturbed'] == 0 and not key.endswith(':none')
    return out


def sh(cmd):
    p = subprocess.run(cmd, shell=True, cwd=os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'),
                       capture_output=True, text=True, timeout=120)
    return (p.stdout + p.stderr).strip().splitlines()[-1:] or ['']


def get(board):
    l = sh('fpga-jtag %s run python3 eyescan.py get %s' % (board, ' '.join(POINT)))[0]
    return dict(kv.split('=', 1) for kv in l.split() if '=' in kv and not kv.startswith('board='))


def first_line(u, tmax=15):
    t = time.time()
    while time.time() - t < tmax:
        l = u.next_line()
        if l is EOF:
            return None
        if l:
            return l
    return None


def one(board, level, follow):
    rec = {'board': board, 'level': level, 't': time.strftime('%Y-%m-%dT%H:%M:%S%z'), 'pt0': get(board)}
    u = Uart()
    try:
        l0 = first_line(u)
        rec['out'] = [sh('fpga-jtag %s run python3 eyescan.py %s' % (board, c))[0][:100] for c in readapt_cmds(level)]
        ls, t = [], time.time()
        while time.time() - t < follow:
            l = u.next_line()
            if l is EOF:
                break
            if l:
                ls.append(l)
    finally:
        u.close()
    rec['d'] = deltas(l0, ls, RXDIR[board]) if l0 else {'lines': 0, 'dloss': None, 'derr': None, 'synced_min': None}
    rec['d_other'] = deltas(l0, ls, RXDIR['m2' if board == 'gs' else 'gs']) if l0 else None
    rec['pt1'] = get(board)
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--boards', default='gs,m2')
    ap.add_argument('--levels', default='none,eqa,cdr,rx,pma')
    ap.add_argument('--reps', type=int, default=3)
    ap.add_argument('--follow', type=float, default=8)
    ap.add_argument('--out')
    ap.add_argument('--table')
    a = ap.parse_args()
    if a.table:
        print(json.dumps(verdict([json.loads(l) for l in open(a.table) if l.strip()]), indent=1, sort_keys=True))
        return 0
    f = open(a.out, 'a')
    for rep in range(a.reps):
        for b in a.boards.split(','):
            for lv in a.levels.split(','):
                r = one(b, lv, a.follow)
                r['rep'] = rep + 1
                f.write(json.dumps(r) + '\n')
                f.flush()
                print('K1P %s %s rep=%d d=%s other=%s pt0=%s pt1=%s' % (b, lv, rep + 1, r['d'], r['d_other'], r['pt0'], r['pt1']),
                      flush=True)
    f.close()
    return 0


if __name__ == '__main__':
    sys.exit(main())
