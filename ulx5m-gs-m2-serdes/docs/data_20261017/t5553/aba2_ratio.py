"""TASK-5553: aba2 (TASK-5542 K4-K12, 3 ucitavanja) -> omjer BER(B) / geom. sredina BER(A prije, A poslije), po smjeru.
<1 = B bolji. Medijan preko 3 ucitavanja; 'n<1' = na koliko ucitavanja je B bolji u OBA smjera."""
import re, os, math, statistics, collections
src = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'aba2.out')
rows = [m for m in (re.match(r'([AB]) (\S+)\s+(\S+) M2->GS (\d+)/(\S+) GS->M2 (\d+)/(\S+)', l) for l in open(src)) if m]
ber = lambda k, n: (k + 0.5) / float(n)          # +0.5: 0 gresaka ne daje log(0)
res = collections.defaultdict(list)
for i, m in enumerate(rows):
    if m[1] != 'B' or i == 0 or i + 1 >= len(rows): continue
    a0, a1 = rows[i - 1], rows[i + 1]
    r = []
    for kk, nn in ((4, 5), (6, 7)):
        ref = math.sqrt(ber(int(a0[kk]), a0[nn]) * ber(int(a1[kk]), a1[nn]))
        r.append(ber(int(m[kk]), m[nn]) / ref)
    res[m[2]].append(r)
print('korak | omjer M2->GS po ucitavanju | omjer GS->M2 po ucitavanju | medijan M2->GS / GS->M2 | ucitavanja B bolji u oba')
for k, v in res.items():
    a = [x[0] for x in v]; b = [x[1] for x in v]
    both = sum(1 for x in v if x[0] < 1 and x[1] < 1)
    print(f'{k} | {" ".join("%.2g" % x for x in a)} | {" ".join("%.2g" % x for x in b)} | {statistics.median(a):.2g} / {statistics.median(b):.2g} | {both}/{len(v)}')
