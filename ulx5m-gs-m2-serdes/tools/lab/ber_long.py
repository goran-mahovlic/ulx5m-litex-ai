#!/usr/bin/env python3
"""ber_long.py --secs 3600 --every 300 --out r1.jsonl — TASK-5482 long serial BER run (one load).
No clear: a baseline reading, then every --every seconds open the port, read the cumulative counters (48-bit words,
32-bit errb; the last of 4 lines whose counters advance plausibly) and close it again. One JSON line per snapshot, then a 'total' line:
BER of the whole window (sum of intervals) + 95 % upper bound (rule of three when 0 errors) and per-interval BER (drift).
A word counter that goes back = that checker restarted -> counted, the interval uses the count since the restart.
A snapshot with no UART line is logged as {'nouart': true} and skipped; the series continues."""
import argparse
import json
import os
import sys
import time

PAYLOAD_BITS = 40
M48, M32 = (1 << 48) - 1, 0xFFFFFFFF
DIRS = (('m2_to_gs', 'words', 'errb'), ('gs_to_m2', 'pwords', 'perrb'))


def _delta(a, b, wk, ek):
    """(words, bit errors, restarted) between two cumulative readings; a word counter that went back = restart,
    then the reading itself is the count since the restart."""
    if b[wk] < a[wk]:
        return b[wk], b[ek], True
    return (b[wk] - a[wk]) & M48, (b[ek] - a[ek]) & M32, False


def segments(snaps):
    """Per-interval BER between consecutive cumulative snapshots."""
    out = []
    for a, b in zip(snaps, snaps[1:]):
        r = {'t0': a['t'], 't1': b['t'], 'restarts': []}
        for k, wk, ek in DIRS:
            dw, de, rs = _delta(a, b, wk, ek)
            if rs:
                r['restarts'].append(k)
            r[k] = de / (dw * float(PAYLOAD_BITS)) if dw else None
        r['restart'] = bool(r['restarts'])
        out.append(r)
    return out


def total(snaps):
    """Whole-window BER = sum of the intervals (the baseline need not be a cleared counter)."""
    r = {'secs': snaps[-1]['t'] - snaps[0]['t'], 'restarts': {}}
    for k, wk, ek in DIRS:
        w = e = n = 0
        for a, b in zip(snaps, snaps[1:]):
            dw, de, rs = _delta(a, b, wk, ek)
            w, e, n = w + dw, e + de, n + rs
        bits = w * PAYLOAD_BITS
        r['restarts'][k] = n
        r[k] = {'words': w, 'errb': e, 'bits': bits, 'ber': (e / float(bits)) if bits else None,
                'ber_95_upper': (3.0 / bits) if bits and e == 0 else None}
    r['restart'] = any(r['restarts'].values())
    return r


def plausible(L):
    """Last status line whose words AND pwords advanced by 0..1.05 x gs TX words (+1000) since the line before:
    rejects m2 counters corrupted in the back channel. None if no such consecutive pair."""
    best = None
    for a, b in zip(L, L[1:]):
        dt = (b['tcnt'] - a['tcnt']) & M32
        if all(0 <= b[k] - a[k] <= 1.05 * dt + 1000 for k in ('words', 'pwords')):
            best = b
    return best


def read_snap(M, t0):
    s = M.open_port()
    try:
        L = M.read_until(s, 4, 90)
    finally:
        s.close()
    d = plausible(L) if L else None
    if d is None:
        return {'t': round(time.time() - t0, 1), 'nouart': True, 'lines': len(L)}
    r = {'t': round(time.time() - t0, 1)}
    for k in ('words', 'errb', 'errw', 'code', 'synced', 'pwords', 'perrb', 'perrw', 'pcode', 'psynced', 'loss', 'ploss', 'inj', 'pinj', 'pexec'):
        r[k] = d.get(k)
    return r


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--secs', type=int, default=3600)
    ap.add_argument('--every', type=int, default=300)
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
    import ber_mon as M
    f = open(a.out, 'w')

    def w(o):
        f.write(json.dumps(o) + '\n'); f.flush()
    t0 = time.time()
    first = None
    for _ in range(5):                          # baseline, no clear: a 'Z' leaves cmd low nibble 1 in the aux frame and
        first = read_snap(M, t0)                # every corrupted+restored cmd byte then re-clears m2 (ber_top.v r.146)
        if not first.get('nouart'):
            break
    if first.get('nouart'):
        w({'error': 'no plausible gs UART line for the baseline'}); print('NOUART'); return 2
    snaps = [first]
    w(dict(first, kind='baseline'))
    while time.time() - t0 < a.secs:
        time.sleep(max(1, min(a.every, a.secs - (time.time() - t0))))
        d = read_snap(M, t0); d['kind'] = 'snap'; w(d)
        if not d.get('nouart'):
            snaps.append(d)
    if len(snaps) < 2:
        w({'error': 'no snapshot after the clear'}); print('NOUART'); return 2
    t = total(snaps); t['kind'] = 'total'; t['segments'] = segments(snaps); t['snaps_ok'] = len(snaps) - 1
    w(t)
    print('TOTAL secs=%s gs->m2 BER=%s (<%s) m2->gs BER=%s (<%s) restarts=%s snaps=%d' % (
        t['secs'], t['gs_to_m2']['ber'], t['gs_to_m2']['ber_95_upper'], t['m2_to_gs']['ber'],
        t['m2_to_gs']['ber_95_upper'], t['restarts'], t['snaps_ok']))
    return 0


if __name__ == '__main__':
    sys.exit(main())
