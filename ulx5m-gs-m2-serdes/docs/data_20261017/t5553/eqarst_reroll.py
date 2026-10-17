"""TASK-5553: ishodi koraka koji sadrze EQA reset (eqarst) u aba2 (TASK-5542 calib, 3 ucitavanja).
Ulaz: ../../data_20261016/t5542/calib/aba2.out. Svaki A/B korak ~30-60 s, oba smjera, bitne greske / bitovi.
Koraci s eqarst: B eqa_off0, B eqa_lfhf83, B eqa_ctrl i njihovi A koraci (undo = vrati polje + eqarst)."""
import re, math, os
src = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'aba2.out')
rows = []
for l in open(src):
    m = re.match(r'([AB]) (\S+)\s+(\S+) M2->GS (\d+)/(\S+) GS->M2 (\d+)/(\S+)', l)
    if m:
        rows.append((m[1], m[2], m[3], int(m[4]), float(m[5]), int(m[6]), float(m[7])))
EQ = {'eqa_off0', 'eqa_lfhf83', 'eqa_ctrl'}
th = 1e-9
print('ucitavanje | prethodni korak BER(M2->GS) | korak s eqarst | BER M2->GS | BER GS->M2 | oba < 1e-9')
good = tot = 0
for i, r in enumerate(rows):
    prev = rows[i - 1] if i else None
    is_eq = (r[0] == 'B' and r[1] in EQ) or (r[0] == 'A' and prev and prev[0] == 'B' and prev[1] in EQ)
    if not is_eq:
        continue
    b1, b2 = r[3] / r[4], r[5] / r[6]
    ok = b1 < th and b2 < th
    tot += 1; good += ok
    print(f'{r[2]} | {prev[3]/prev[4]:.2e} ({prev[0]} {prev[1]}) | {r[0]} {r[1]} | {b1:.2e} | {b2:.2e} | {"DA" if ok else "ne"}')
lo = 0 if good == 0 else None
print(f'ukupno: {good}/{tot} koraka s eqarst zavrsi s oba smjera < 1e-9')
