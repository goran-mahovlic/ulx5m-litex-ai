#!/usr/bin/env python3
"""scatter_table.py <log19 dir> — TASK-5487 (uputa #308): does a bad 2.5 G load coincide with a calibration/CDR state?
Per load r<k>: r<k>.start_<board>.json (eyescan.py health --raw right after SET_ACC) + r<k>_ber.json (ber_mon sparse).
Prints a markdown table (state per load, BER both directions) and the Spearman rank correlation of every varying state
value with log10(BER) of the direction that board RECEIVES (m2 RX = gs->m2, gs RX = m2->gs) and the one it SENDS.
BER 0 counts as 1e-12 (below the floor of a 240 s window); NOUART loads are listed but not correlated."""
import glob
import json
import math
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
import ab_table as A

FIELDS = ('PLL_CAP_FT', 'RX_CALIB_CAL', 'TX_CALIB_CAL', 'RX_OFFSET', 'RX_EQA_TAPW', 'RX_TH_MON', 'RX_EQA_LOCKED', 'RX_CDR_LOCKED')
RECV = {'m2': 'gs_to_m2', 'gs': 'm2_to_gs'}
SEND = {'m2': 'm2_to_gs', 'gs': 'gs_to_m2'}


def ranks(v):
    o = sorted(range(len(v)), key=lambda i: v[i]); r = [0.0] * len(v); i = 0
    while i < len(o):
        j = i
        while j + 1 < len(o) and v[o[j + 1]] == v[o[i]]:
            j += 1
        for k in range(i, j + 1):
            r[o[k]] = (i + j) / 2.0
        i = j + 1
    return r


def spearman(x, y):
    if len(set(x)) < 2 or len(set(y)) < 2:
        return None
    rx, ry = ranks(x), ranks(y); mx, my = sum(rx) / len(rx), sum(ry) / len(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    return num / math.sqrt(sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry))


def row(start, ber):
    r = {}
    for b in ('m2', 'gs'):
        h = start.get(b) or {}
        for k, v in h.get('fields', {}).items():
            r['%s.%s' % (b, k)] = v
        if h.get('phase_acc'):
            r['%s.phase_acc' % b] = sum(h['phase_acc']) / len(h['phase_acc'])
        if 'afe_offset' in h:
            r['%s.afe_offset' % b] = h['afe_offset']
        for a, v in (h.get('raw') or {}).items():
            r['%s.raw%s' % (b, a)] = v
    for d in A.DIRS:
        r['ber_' + d] = A.ber(ber[d]) if ber and d in ber else None
    return r


def load(dirn):
    rows = []
    for f in sorted(glob.glob(os.path.join(dirn, 'r*_ber.json')), key=lambda p: int(re.search(r'r(\d+)_', os.path.basename(p)).group(1))):
        k = re.search(r'r(\d+)_', os.path.basename(f)).group(1)
        st = {}
        for b in ('m2', 'gs'):
            p = os.path.join(dirn, 'r%s.start_%s.json' % (k, b))
            st[b] = json.load(open(p)) if os.path.exists(p) else {}
        try:
            ber = json.load(open(f))
        except ValueError:
            ber = None
        r = row(st, ber); r['load'] = 'r' + k; rows.append(r)
    return rows


def lg(v):
    return math.log10(max(v, 1e-12))


def main(args):
    rows = load(args[0])
    cols = ['load', 'ber_gs_to_m2', 'ber_m2_to_gs'] + ['%s.%s' % (b, f) for b in ('m2', 'gs') for f in FIELDS + ('afe_offset', 'phase_acc')]
    cols = [c for c in cols if any(c in r for r in rows)]
    print('| ' + ' | '.join(cols) + ' |'); print('|' + '---|' * len(cols))
    for r in rows:
        print('| ' + ' | '.join(('%.1e' % r[c] if c.startswith('ber') and r.get(c) is not None else
                                 'NOUART' if c.startswith('ber') else '%s' % (round(r[c], 1) if isinstance(r.get(c), float) else r.get(c, '')))
                                for c in cols) + ' |')
    ok = [r for r in rows if r['ber_gs_to_m2'] is not None]
    print('\nSpearman rho vs log10 BER (n=%d loads with UART; |rho| >= 0.65 at n=10 is p < 0.05):' % len(ok))
    keys = sorted({k for r in ok for k in r if k[:3] in ('m2.', 'gs.')})
    out = []
    for k in keys:
        b = k[:2]; x = [r.get(k) for r in ok]
        if any(v is None for v in x):
            continue
        for tag, d in (('recv', RECV[b]), ('send', SEND[b])):
            rho = spearman(x, [lg(r['ber_' + d]) for r in ok])
            if rho is not None:
                out.append((abs(rho), k, tag, d, rho, min(x), max(x)))
    for _, k, tag, d, rho, lo, hi in sorted(out, reverse=True)[:20]:
        print('  %-22s %-4s %-9s rho=%+.2f  range %s..%s' % (k, tag, d, rho, lo, hi))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
