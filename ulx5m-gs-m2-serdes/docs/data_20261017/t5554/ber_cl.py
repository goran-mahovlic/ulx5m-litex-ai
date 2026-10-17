#!/usr/bin/env python3
"""BER confidence (Poisson, exact): bits needed for upper bound < target at CL, given k errors. TASK-5554."""
import math
class chi2:  # only even dof (2(k+1)) needed: chi2.ppf(p, 2m)/2 = Poisson mean mu with P(X<=m-1; mu) = 1-p
    @staticmethod
    def ppf(p, dof):
        m = dof // 2
        def cdf(mu):  # P(X <= m-1)
            return sum(math.exp(-mu) * mu**i / math.factorial(i) for i in range(m))
        lo, hi = 0.0, 1000.0
        for _ in range(200):
            mid = (lo + hi) / 2
            if cdf(mid) > 1 - p: lo = mid
            else: hi = mid
        return 2 * lo
def bits_needed(ber, cl, k):   # N such that upper CL bound of rate == ber
    return chi2.ppf(cl, 2*(k+1)) / 2 / ber
def upper(k, n, cl=0.95):      # one-sided upper bound
    return chi2.ppf(cl, 2*(k+1)) / 2 / n
def ci(k, n, cl=0.95):         # two-sided (Garwood)
    a = 1-cl
    lo = chi2.ppf(a/2, 2*k)/2/n if k else 0.0
    return lo, chi2.ppf(1-a/2, 2*(k+1))/2/n
print("| cilj BER | CL | k grešaka | bitova N | 2,5 Gb/s (linija) | 1,25e9 b/s (naš checker na 2,5G) | 5 Gb/s (linija) | 2,5e9 b/s (naš checker na 5G) |")
print("|---|---|---|---|---|---|---|---|")
for ber in (1e-12, 1e-15):
  for cl in (0.95, 0.99):
    for k in (0, 1, 2):
      n = bits_needed(ber, cl, k)
      f = lambda r: f"{n/r:,.0f} s = {n/r/60:,.1f} min" if n/r < 86400*2 else f"{n/r/86400:,.1f} dana"
      print(f"| {ber:.0e} | {cl*100:.0f} % | {k} | {n:.3e} | {f(2.5e9)} | {f(1.25e9)} | {f(5e9)} | {f(2.5e9)} |")
print()
N = 2.239e12
for name,k in (("M2->GS",50),("GS->M2",2)):
    lo,hi = ci(k,N); print(f"{name}: k={k} N={N:.3e} BER={k/N:.3e} 95% two-sided [{lo:.3e},{hi:.3e}] one-sided upper95 {upper(k,N):.3e}")
    for kk in (k,):
        need = bits_needed(1e-12,0.95,kk); print(f"   bits for <1e-12@95% if total errors stayed {kk}: {need:.3e} -> {need/1.25e9:,.0f} s at 1.25e9 b/s")
# vendor PRBS test: 10 s at 1.25 Gb/s, 0 errors
n=10*1.25e9; print(f"CC serdestool tc_prbs 10 s @1.25G, 0 err: N={n:.2e}, upper95={upper(0,n):.2e}")
# WP428 rule: 3 min to 1e-12 at 6 Gb/s
print(f"WP428 '3 min @6G for 1e-12': bits={3*60*6e9:.2e} = {3*60*6e9*1e-12:.2f}/BER; 95% 0-err needs {bits_needed(1e-12,0.95,0)/6e9/60:.1f} min")
