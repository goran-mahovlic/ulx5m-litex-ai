#!/usr/bin/env python3
"""k3_table.py <calib_aba jsonl> - TASK-5559 K3: A/B ratios with the FIRST 10 s window of every state dropped.

calib_aba measures right after the readapt; its first window carries the EQA reset burst (~2500 bit errors, k3.jsonl),
so calib_aba --table over-counts A and B alike. Here: errors and bits = windows 2..n, ratio = gmean(A before, A after)/B
per direction (0 errors -> 0.5), per load; a TX idle point only judges the direction that still runs."""
import json
import math
import sys

DIRS = ('m2_to_gs', 'gs_to_m2')
WORDS_PER_WIN = 31.25e6 * 10 * 40      # bits in a 10 s window (window length is ~10 s; ratio uses equal-length windows)


def kept(r, k):
    w = r['win'][1:]
    return sum(x[k] for x in w), len(w)


def ber(r, k):
    e, n = kept(r, k)
    return None if n == 0 else (e if e else 0.5) / (n * WORDS_PER_WIN)


def main(path):
    rows = [json.loads(l) for l in open(path) if l.strip()]
    loads = {}
    for r in rows:
        if r.get('kind') in ('A', 'B'):
            loads.setdefault(r['load'], []).append(r)
    print('| load | point | M2->GS A (gmean) | M2->GS B | A/B | GS->M2 A (gmean) | GS->M2 B | A/B |')
    print('|---|---|---|---|---|---|---|---|')
    for ld, rs in loads.items():
        for i, r in enumerate(rs):
            if r['kind'] != 'B':
                continue
            a0 = next(x for x in reversed(rs[:i]) if x['kind'] == 'A')
            a1 = next((x for x in rs[i + 1:] if x['kind'] == 'A'), None)
            cells = []
            for k in DIRS:
                b = ber(r, k) if r['bits'][k] else None
                As = [ber(x, k) for x in (a0, a1) if x]
                a = math.exp(sum(math.log(x) for x in As) / len(As))
                cells += ['%.1e' % a, '-' if b is None else '%.1e' % b, '-' if b is None else 'x%.2g' % (a / b)]
            print('| %s | %s | %s |' % (ld, r['name'], ' | '.join(cells)))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1]))
