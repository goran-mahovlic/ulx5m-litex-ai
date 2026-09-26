#!/usr/bin/env python3
"""sweep_table.py <run.json>... — Markdown table from ber_mon.py 'run --json' results (one row per run).
Columns: config | measured rate gs TX / m2 TX | words and bit errors per direction | BER (95 % bound) | duration."""
import json
import os
import sys


def ber_s(side):
    if side['words'] == 0:
        return 'no data'
    if side['errb'] == 0:
        return '0 (< %.1e)' % side['ber_95_upper']
    return '%.2e' % side['ber']


def row(name, r):
    g, m = r['m2_to_gs'], r['gs_to_m2']
    return '| %s | %.1f / %.1f | %.3e / %d | %.3e / %d | %s | %s | %d s |' % (
        name, r['gs_tx_rate_bps'] / 1e6, r['m2_tx_rate_bps'] / 1e6, m['words'], m['errb'], g['words'], g['errb'],
        ber_s(m), ber_s(g), round(r['secs']))


HEAD = ('| Config | Measured rate gs TX / m2 TX [Mb/s] | gs→m2 words / bit errors | m2→gs words / bit errors '
        '| BER gs→m2 | BER m2→gs | Duration |\n|---|---|---|---|---|---|---|')


def main(paths):
    print(HEAD)
    for p in paths:
        name = os.path.basename(p).rsplit('.', 1)[0]
        print(row(name, json.load(open(p))))


if __name__ == '__main__':
    main(sys.argv[1:])
