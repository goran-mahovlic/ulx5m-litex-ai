#!/usr/bin/env python3
"""health_table.py <label>_r<k>.health_<board>.json ... - PLL (0x55) and CDR/EQA flags of the receivers per load and per point.

abrun.sh writes one E0 health snapshot per board right before the BER run (eyescan.py health -n 3). This prints, per load,
PLL_LOCKED, PLL_CAP_FT_OF/UF, PLL_CAP_FT (all register 0x55), RX_CDR_LOCKED, RX_EQA_LOCKED and the span of the CDR phase
accumulator, then per (point, board) how many loads had each flag set (TASK-5078: A/B after the 1 uF caps on GS).
"""
import json, re, sys

NAME = re.compile(r'(.*)_r(\d+)\.health_(\w+)\.json$')


def split_name(path):
    m = NAME.search(path.rsplit('/', 1)[-1])
    return m.group(1), int(m.group(2)), m.group(3)


def row(d):
    f = d['fields']; pa = d.get('phase_acc') or [0]
    return {'board': d['board'], 'lock': f['PLL_LOCKED'], 'of': f['PLL_CAP_FT_OF'], 'uf': f['PLL_CAP_FT_UF'],
            'cap_ft': f['PLL_CAP_FT'], 'cdr': f['RX_CDR_LOCKED'], 'eqa': f['RX_EQA_LOCKED'], 'phase_span': max(pa) - min(pa)}


def summary(paths):
    out = {}
    for p in paths:
        lab, _, board = split_name(p); r = row(json.load(open(p)))
        s = out.setdefault((lab, board), {'n': 0, 'lock': 0, 'of': 0, 'uf': 0, 'cdr': 0, 'eqa': 0, 'cap_ft': None})
        s['n'] += 1
        for k in ('lock', 'of', 'uf', 'cdr', 'eqa'):
            s[k] += r[k]
        lo, hi = s['cap_ft'] or (r['cap_ft'], r['cap_ft'])
        s['cap_ft'] = (min(lo, r['cap_ft']), max(hi, r['cap_ft']))
    return out


def main(paths):
    print('| Point | load | board | PLL lock | FT_OF / FT_UF | CAP_FT | CDR lock | EQA lock | phase span |')
    print('|---|---|---|---|---|---|---|---|---|')
    for p in sorted(paths, key=split_name):
        lab, k, _ = split_name(p); r = row(json.load(open(p)))
        print(f"| {lab} | r{k} | {r['board']} | {r['lock']} | {r['of']} / {r['uf']} | {r['cap_ft']} | {r['cdr']} | {r['eqa']} | {r['phase_span']} |")
    print('\n| Point | board | loads | PLL lock | FT_OF | FT_UF | CDR lock | EQA lock | CAP_FT range |')
    print('|---|---|---|---|---|---|---|---|---|')
    for (lab, b), s in sorted(summary(paths).items()):
        print(f"| {lab} | {b} | {s['n']} | {s['lock']}/{s['n']} | {s['of']}/{s['n']} | {s['uf']}/{s['n']} | {s['cdr']}/{s['n']} | "
              f"{s['eqa']}/{s['n']} | {s['cap_ft'][0]}–{s['cap_ft'][1]} |")


if __name__ == '__main__':
    main(sys.argv[1:])
