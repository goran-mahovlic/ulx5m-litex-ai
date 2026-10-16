#!/usr/bin/env python3
"""ber_windows.py <ber_long.jsonl> [--skip N] — TASK-5538 (uputa #345): BER from snapshot DELTAS only.

Per consecutive pair of good (non-NOUART) snapshots: words/errb delta per direction, BER, loss delta (mod 32), synced
flags. The first N windows (default 1, the window right after the link came up) are dropped from the total.
Total over the kept windows with an exact Poisson 95 % interval on the error count (bit errors / payload bits).
A window that spans a NOUART gap is kept (cumulative counters) but flagged with its real length."""
import argparse
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ber_long import DIRS, PAYLOAD_BITS, _delta  # noqa: E402

LOSS = {'m2_to_gs': 'loss', 'gs_to_m2': 'ploss'}


def _cdf(k, mu):
    """Poisson P(X <= k | mu), log-space sum."""
    if k < 0:
        return 0.0
    if mu == 0:
        return 1.0
    lt, s = -mu, math.exp(-mu)
    for i in range(1, k + 1):
        lt += math.log(mu) - math.log(i)
        s += math.exp(lt)
    return min(s, 1.0)


def _bisect(f, lo, hi):
    """Root of a function that goes from True (at lo) to False (at hi)."""
    for _ in range(200):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if f(mid) else (lo, mid)
    return (lo + hi) / 2


def poisson_ci(k, conf=0.95):
    """Exact (Garwood) two-sided interval for a Poisson count k -> (lower, upper) on the mean."""
    a = (1 - conf) / 2
    top = k + 10 * math.sqrt(k + 1) + 10
    upper = _bisect(lambda mu: _cdf(k, mu) > a, 0.0, top)
    lower = 0.0 if k == 0 else _bisect(lambda mu: 1 - _cdf(k - 1, mu) < a, 0.0, top)
    return lower, upper


def windows(snaps):
    out = []
    for a, b in zip(snaps, snaps[1:]):
        r = {'t0': a['t'], 't1': b['t']}
        for k, wk, ek in DIRS:
            dw, de, rs = _delta(a, b, wk, ek)
            r[k] = {'words': dw, 'errb': de, 'restart': rs,
                    'ber': de / (dw * float(PAYLOAD_BITS)) if dw else None,
                    'dloss': (b[LOSS[k]] - a[LOSS[k]]) & 0x1F}
        r['synced'] = (b.get('synced'), b.get('psynced'))
        out.append(r)
    return out


def summarize(ws):
    t = {}
    for k, _, _ in DIRS:
        w = sum(x[k]['words'] for x in ws)
        e = sum(x[k]['errb'] for x in ws)
        bits = w * PAYLOAD_BITS
        lo, hi = poisson_ci(e)
        t[k] = {'words': w, 'errb': e, 'bits': bits, 'ber': e / bits if bits else None,
                'ci95': (lo / bits, hi / bits) if bits else None,
                'dloss': sum(x[k]['dloss'] for x in ws), 'restarts': sum(x[k]['restart'] for x in ws),
                'win_ber': sorted(x[k]['ber'] for x in ws if x[k]['ber'] is not None)}
    t['secs'] = sum(x['t1'] - x['t0'] for x in ws)
    t['n'] = len(ws)
    return t


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('jsonl')
    ap.add_argument('--skip', type=int, default=1)
    a = ap.parse_args()
    rows = [json.loads(l) for l in open(a.jsonl)]
    snaps = [r for r in rows if r.get('kind') in ('baseline', 'snap') and not r.get('nouart')]
    nou = sum(1 for r in rows if r.get('kind') == 'snap' and r.get('nouart'))
    ws = windows(snaps)
    print('snapshots ok=%d nouart=%d windows=%d skip=%d' % (len(snaps), nou, len(ws), a.skip))
    for i, x in enumerate(ws):
        print('%s w%02d %6.1f-%6.1f s  m2->gs %s (e=%d dl=%d)  gs->m2 %s (e=%d dl=%d)  synced=%s' % (
            'skip' if i < a.skip else '    ', i, x['t0'], x['t1'],
            '%.2e' % x['m2_to_gs']['ber'] if x['m2_to_gs']['ber'] is not None else 'None', x['m2_to_gs']['errb'],
            x['m2_to_gs']['dloss'],
            '%.2e' % x['gs_to_m2']['ber'] if x['gs_to_m2']['ber'] is not None else 'None', x['gs_to_m2']['errb'],
            x['gs_to_m2']['dloss'], x['synced']))
    if len(ws) <= a.skip:
        print('NO WINDOW after skip (gs UART gave too few snapshots)')
        return 3
    t = summarize(ws[a.skip:])
    for k, _, _ in DIRS:
        d = t[k]
        wb = d['win_ber']
        print('TOTAL %s secs=%.1f n=%d errb=%d bits=%.3e BER=%.2e CI95=[%.2e, %.2e] dloss=%d restarts=%d '
              'win median=%.2e min=%.2e max=%.2e' % (
                  k, t['secs'], t['n'], d['errb'], d['bits'], d['ber'], d['ci95'][0], d['ci95'][1], d['dloss'],
                  d['restarts'], wb[len(wb) // 2], wb[0], wb[-1]))
    return 0


if __name__ == '__main__':
    sys.exit(main())
