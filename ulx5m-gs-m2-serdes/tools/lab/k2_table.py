#!/usr/bin/env python3
"""k2_table.py <dir> [--arms b0p,b1,b2] [--md out.md] - TASK-5559 K2/K6: first-attempt pass per arm from link_gate logs.

Run files <dir>/k2_<arm>_<nn>.jsonl (one gate run each, attempt lines + one 'gate' line). Per arm: runs, first-attempt
passes k/n with the one-sided 95 % Clopper-Pearson lower bound, mean attempts to pass, gate failures, set failures, and
the accepted-attempt C 60 s errors per direction. Arms are compared with a one-sided Fisher exact test against --ref
(v2 §3.1: an arm wins if its first-attempt share is higher with p < 0.05)."""
import argparse
import glob
import json
import math
import os
import re

comb = getattr(math, 'comb', None) or (lambda n, k: math.factorial(n) // (math.factorial(k) * math.factorial(n - k)))  # Pi: py3.7


def lbeta_cdf_lower(k, n, conf=0.95):
    """One-sided lower Clopper-Pearson bound for k/n (bisection on the binomial tail)."""
    if k == 0:
        return 0.0
    def tail(p):                                        # P(X >= k | n, p)
        return sum(comb(n, i) * p ** i * (1 - p) ** (n - i) for i in range(k, n + 1))
    lo, hi = 0.0, 1.0
    for _ in range(60):
        mid = (lo + hi) / 2
        if tail(mid) < 1 - conf:
            lo = mid
        else:
            hi = mid
    return lo


def fisher_greater(a, n1, b, n2):
    """One-sided Fisher exact p: arm 1 (a of n1) has a higher success share than arm 2 (b of n2)."""
    K, N = a + b, n1 + n2
    def h(x):
        return comb(K, x) * comb(N - K, n1 - x) / comb(N, n1)
    return sum(h(x) for x in range(a, min(K, n1) + 1))


def runs(d, arm):
    out = []
    for p in sorted(glob.glob(os.path.join(d, 'k2_%s_*.jsonl' % arm))):
        rows = [json.loads(l) for l in open(p) if l.strip()]
        gate = [r for r in rows if r.get('kind') == 'gate']
        att = [r for r in rows if 'attempt' in r]
        if not gate:
            continue                                     # run still going / interrupted
        g = gate[-1]
        acc = [r for r in att if r['verdict'] == 'PASS']
        out.append({'run': os.path.basename(p)[:-6], 'verdict': g['verdict'], 'attempts': g['attempts'],
                    'c_err': (acc[-1].get('c') or {}).get('err') if acc else None,
                    'codes': ''.join('P' if r['verdict'] == 'PASS' else 'S' if r['verdict'] == 'SET_FAIL' else
                                     'u' if r['verdict'] == 'UNDECIDED' else 'c' if (r.get('c') or {}).get('verdict') == 'FAIL'
                                     else 'q' if (r.get('q') or {}).get('verdict') == 'FAIL' else 'h' for r in att)})
    return out


def arm_stats(rs):
    n = len(rs)
    k = sum(1 for r in rs if r['verdict'] == 'PASS' and r['attempts'] == 1)
    att = [r['attempts'] for r in rs if r['verdict'] == 'PASS']
    return {'n': n, 'first': k, 'share': (k / n) if n else None, 'cp95_low': lbeta_cdf_lower(k, n) if n else None,
            'mean_attempts': (sum(att) / len(att)) if att else None, 'gate_failed': sum(r['verdict'] == 'GATE_FAILED' for r in rs),
            'set_fail': sum(r['verdict'] == 'SET_FAIL' for r in rs),
            'c_err_m2_to_gs': [r['c_err']['m2_to_gs'] for r in rs if r['c_err']],
            'c_err_gs_to_m2': [r['c_err']['gs_to_m2'] for r in rs if r['c_err']]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('dir')
    ap.add_argument('--arms', default='b0p,b1,b2')
    ap.add_argument('--ref', default='b0p')
    ap.add_argument('--md')
    a = ap.parse_args()
    st = {arm: arm_stats(runs(a.dir, arm)) for arm in a.arms.split(',')}
    ref = st.get(a.ref)
    lines = ['| arm | runs | 1st-attempt pass | share | CP 95 %% low | mean attempts | gate failed | set fail | Fisher p vs %s |' % a.ref,
             '|---|---|---|---|---|---|---|---|---|']
    for arm, s in st.items():
        p = fisher_greater(s['first'], s['n'], ref['first'], ref['n']) if (ref and arm != a.ref and s['n'] and ref['n']) else None
        s['fisher_p_vs_ref'] = p
        f = lambda v, d=3: '-' if v is None else ('%.*f' % (d, v))      # noqa: E731
        lines.append('| %s | %d | %d/%d | %s | %s | %s | %d | %d | %s |' % (arm, s['n'], s['first'], s['n'], f(s['share'], 2),
                     f(s['cp95_low']), f(s['mean_attempts'], 2), s['gate_failed'], s['set_fail'], f(p)))
    print('\n'.join(lines))
    print(json.dumps(st))
    if a.md:
        open(a.md, 'w').write('\n'.join(lines) + '\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
