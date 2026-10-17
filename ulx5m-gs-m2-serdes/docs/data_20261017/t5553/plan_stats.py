"""TASK-5553: statistika za plan pokusa (2,5G: 1,25e9 bit/s po smjeru; 5G: 2,5e9)."""
import math
import math

def binom_sf(k, n, p):  # P(X >= k)
    return sum(math.comb(n, i) * p**i * (1-p)**(n-i) for i in range(k, n+1))
def cp_lower(k, n, a=0.05):  # Clopper-Pearson jednostrano donja granica
    if k == 0: return 0.0
    lo, hi = 0.0, 1.0
    for _ in range(60):
        m = (lo + hi) / 2
        (lo, hi) = (m, hi) if binom_sf(k, n, m) < a else (lo, m)
    return lo
R = {'2g5': 1.25e9, '5g': 2.5e9}
print('# 1) nula gresaka -> gornja granica BER (95 %): bitovi = 3.0/BER')
for ber in (1e-11, 1e-12, 1e-13):
    for r, bps in R.items():
        print(f'BER<{ber:.0e} {r}: {3/ber:.2e} bit = {3/ber/bps:8.0f} s = {3/ber/bps/3600:6.2f} h')
print('# 2) usporedba dviju tocaka, omjer BER x2 / x3, 95 % dvostrano, snaga 80 %: potrebne greske po kraku')
za, zb = 1.96, 0.8416
for ratio in (2, 3, 5):
    k = 2 * ((za + zb) / math.log(ratio)) ** 2  # 1/k1+1/k2 = 2/k
    for ber in (2e-11, 5e-10):
        t = k / (ber * R['2g5'])
        print(f'omjer x{ratio}: ~{k:.0f} gresaka po kraku; pri BER {ber:.0e} (2,5G) = {t:.0f} s po kraku')
print('# 3) udio dobrih ucitavanja p0 -> p1 (Fisher/2-proporcije, 95 %/80 %): ucitavanja po kraku')
for p0, p1 in ((0.33, 0.66), (0.33, 0.80), (0.33, 0.90), (0.5, 0.9)):
    pb = (p0 + p1) / 2
    n = ((za * math.sqrt(2 * pb * (1 - pb)) + zb * math.sqrt(p0 * (1 - p0) + p1 * (1 - p1))) / (p1 - p0)) ** 2
    print(f'p {p0:.2f} -> {p1:.2f}: n = {math.ceil(n)} po kraku')
print('# 4) "iz 1. pokusaja": najmanji k/n s Clopper-Pearson donjom 95 % granicom >= 0.8')
for n in (10, 15, 20, 30):
    for k in range(0, n + 1):
        lo = cp_lower(k, n)
        if lo >= 0.8:
            print(f'n={n}: k>={k} prolaza iz 1. -> donja 95 % granica {lo:.3f}'); break
print('# 5) soak "bez gresaka" 1800 s: P(0 gresaka) ako je BER ...')
for ber in (1e-13, 4e-13, 1e-12, 2.23e-11):
    lam = ber * R['2g5'] * 1800
    print(f'BER {ber:.2e}: ocekivano {lam:.2f} gresaka, P(0) = {math.exp(-lam):.3f}')
