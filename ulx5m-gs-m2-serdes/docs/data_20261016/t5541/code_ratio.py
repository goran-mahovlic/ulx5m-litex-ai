#!/usr/bin/env python3
"""TASK-5541: kodne greske (8b10b) po losoj rijeci, po ucitavanju i smjeru.
Linijska greska u 8b10b daje >= 1 kodnu gresku po losoj rijeci; greska na neuskladenom
fabric<->SerDes putu (prije kodera / poslije dekodera) daje lose rijeci BEZ kodnih gresaka.
Ulaz: ber_long JSONL (lab39, lab41, b900). Delta prvi -> zadnji snimak; payload 40 b/rijec.
Pokretanje iz docs/: python3 data_20261016/t5541/code_ratio.py"""
import glob, json, statistics
files = sorted(glob.glob('data_20261015/t5527/log39/*.jsonl') + glob.glob('data_20261016/t5538/log41/*.jsonl')
               + glob.glob('data_20261016/t5538/*.jsonl'))
ratios = {'m2_to_gs': [], 'gs_to_m2': []}
zero_code_bad = 0
print(f"{'datoteka':34} {'M2>GS BER':>9} {'errw':>6} {'code':>6} {'c/w':>5} | {'GS>M2 BER':>9} {'errw':>6} {'code':>6} {'c/w':>5}")
for f in files:
    s = [json.loads(l) for l in open(f) if '"errb"' in l and '"pwords"' in l]
    if len(s) < 2:
        continue
    a, b = s[0], s[-1]
    d = lambda k: b[k] - a[k]
    w, pw = d('words'), d('pwords')
    if w <= 0 or pw <= 0:
        continue
    row = []
    for key, (eb, ew, c, n) in (('m2_to_gs', (d('errb'), d('errw'), d('code'), w)),
                                ('gs_to_m2', (d('perrb'), d('perrw'), d('pcode'), pw))):
        if ew >= 10:
            ratios[key].append(c / ew)
            if c == 0:
                zero_code_bad += 1
        row += [eb / (n * 40), ew, c, f"{c/ew:.2f}" if ew else "-"]
    print(f"{f[-34:]:34} {row[0]:9.2e} {row[1]:6} {row[2]:6} {row[3]:>5} | {row[4]:9.2e} {row[5]:6} {row[6]:6} {row[7]:>5}")
for k, v in ratios.items():
    print(f"{k}: ucitavanja s >=10 losih rijeci = {len(v)}, kodnih/lose rijeci min {min(v):.2f} medijan {statistics.median(v):.2f} max {max(v):.2f}")
print(f"ucitavanja s >=10 losih rijeci i 0 kodnih gresaka: {zero_code_bad}")
