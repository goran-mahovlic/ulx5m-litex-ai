#!/usr/bin/env python3
"""TASK-5558: statistical limits of the final calibration plan (pure python, no scipy).
Checked bits/s per direction: 2.5G = 31.25 M words/s x 40 payload bits = 1.25e9; 5G = 2.5e9."""
import math

RATE = {'2g5': 1.25e9, '5g': 2.5e9}
CL = 0.95


def pois_cdf(k, lam):
    return sum(math.exp(-lam) * lam ** i / math.factorial(i) for i in range(k + 1))


def bits_needed(k, ber=1e-12, cl=CL):
    """smallest N with P(<=k errors | BER) <= 1-cl  (one-sided upper bound = ber)."""
    lo, hi = 0.0, 100.0
    for _ in range(200):
        mid = (lo + hi) / 2
        if pois_cdf(k, mid) > 1 - cl:
            lo = mid
        else:
            hi = mid
    return hi / ber


def lam_for_pass(k, p):
    """largest mean count with P(<=k) >= p."""
    lo, hi = 0.0, 50.0
    for _ in range(200):
        mid = (lo + hi) / 2
        if pois_cdf(k, mid) >= p:
            lo = mid
        else:
            hi = mid
    return lo


def binom_cdf(k, n, p):
    return sum(math.comb(n, i) * p ** i * (1 - p) ** (n - i) for i in range(k + 1))


def cp_lower(x, n, alpha=0.05):
    """one-sided Clopper-Pearson lower bound for x/n successes."""
    if x == 0:
        return 0.0
    lo, hi = 0.0, 1.0
    for _ in range(200):
        mid = (lo + hi) / 2
        # P(X >= x | mid) = 1 - cdf(x-1)
        if 1 - binom_cdf(x - 1, n, mid) < alpha:
            lo = mid
        else:
            hi = mid
    return hi


print('== 1. soak length for BER <= 1e-12 @95 % (one-sided), per direction')
for k in (0, 1, 2):
    n = bits_needed(k)
    print('k<=%d  N=%.3e bits  2.5G %.0f s (%.1f min)  5G %.0f s (%.1f min)'
          % (k, n, n / RATE['2g5'], n / RATE['2g5'] / 60, n / RATE['5g'], n / RATE['5g'] / 60))

print('\n== 2. true BER needed for P(pass) >= 0.8 / 0.9 in a fixed-length soak')
for k, secs in ((0, 2400), (2, 5040)):
    n = secs * RATE['2g5']
    for p in (0.8, 0.9):
        lam = lam_for_pass(k, p)
        print('rule k<=%d in %d s (N=%.2e): P>=%.1f needs mean <= %.3f -> BER <= %.2e'
              % (k, secs, n, p, lam, lam / n))

print('\n== 3. where we are (soak R1 1800 s): improvement factor needed for P(pass 84 min, k<=2) >= 0.8')
lam80 = lam_for_pass(2, 0.8)
target = lam80 / (5040 * RATE['2g5'])
for name, ber in (('M2->GS', 2.23e-11), ('GS->M2', 8.93e-13)):
    lam = ber * 5040 * RATE['2g5']
    print('%s BER %.2e: expected errors in 5040 s %.1f, P(k<=2) %.3g, needs x%.0f better (to %.2e)'
          % (name, ber, lam, pois_cdf(2, lam), ber / target, target))

print('\n== 4. first-attempt gate pass: one-sided 95 % CP lower bound')
for x, n in ((15, 15), (14, 15), (20, 20), (19, 20), (28, 30), (27, 30), (30, 30), (16, 20)):
    print('%2d/%2d  lower %.3f' % (x, n, cp_lower(x, n)))

print('\n== 5. probability that a link with true first-attempt p passes the 28/30 rule')
for p in (0.8, 0.9, 0.95, 0.98):
    print('p=%.2f  P(>=28/30)=%.3f   P(15/15)=%.3f' % (p, 1 - binom_cdf(27, 30, p), p ** 15))

print('\n== 6. soak 3 loads x rule: P(all 3 pass) if each load has the same true BER')
for ber in (1e-13, 2e-13, 3e-13, 5e-13):
    lam = ber * 5040 * RATE['2g5']
    p1 = pois_cdf(2, lam)
    print('BER %.0e: P(one load k<=2 in 5040 s)=%.3f  P(3/3)=%.3f' % (ber, p1, p1 ** 3))
