#!/usr/bin/env python3
"""TASK-5541: pragovi vrata kvalitete linka (2,5 G: 31,25 M rijeci/s x 40 provjerenih bita = 1,25e9 b/s po smjeru).
P(prolaz | stvarni BER) za prag 'greske <= k' u T sekundi, Poisson; i broj pokusaja za p(dobro ucitavanje)."""
from math import exp
def cdf(k, lam):
    s, t = 0.0, exp(-lam)
    for i in range(k + 1):
        s += t; t *= lam / (i + 1)
    return s
for rate, label in ((1.25e9, '2,5G'), (2.5e9, '5G')):
    for T, k in ((10, 8), (60, 60)) if label == '2,5G' else ((10, 16), (60, 120)):
        n = rate * T
        ps = '  '.join(f"{b:.0e}:{cdf(k, b*n):.3f}" for b in (1e-10, 3e-10, 5e-10, 1e-9, 2e-9))
        print(f"{label} T={T:>2}s bita={n:.2e} prag k<={k:<3} (BER<={k/n:.1e})  P(prolaz|BER) {ps}")
n10 = 1.25e9 * 10
print(f"2,5G prozor 10 s, prag praska >20 gresaka: P(>20 | 5e-10) = {1-cdf(20, 5e-10*n10):.1e}")
for p in (0.25, 0.33, 0.48):
    print(f"p(dobro ucitavanje)={p:.2f}: ocekivano pokusaja {1/p:.1f}, P(nijedan od 10) = {(1-p)**10:.4f}")
