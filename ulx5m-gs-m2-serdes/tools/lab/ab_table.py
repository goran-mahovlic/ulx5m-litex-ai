#!/usr/bin/env python3
"""ab_table.py <run.json>... — median BER per point from repeated loads (TASK-5066, TUNING_5G.md §3 repeat rule).
Files are ber_mon.py 'run --json' results named <label>_r<k>.json (one per bitstream load). Per point and direction:
median BER, worst run, and the 95 % upper bound 3/bits when every run was clean. BER = errb / (40 * words)
(40 checked bits per word, README). A run without sync (0 words) counts as BER 0.5."""
import json
import os
import re
import statistics
import sys

DIRS = ('gs_to_m2', 'm2_to_gs')


def is_run(path):
    return re.search(r'_r\d+\.json$', path) is not None


def label_of(path):
    return re.sub(r'_r\d+$', '', os.path.basename(path).rsplit('.', 1)[0])


def ber(side):
    return side['errb'] / (40.0 * side['words']) if side['words'] else 0.5


def point(runs):
    out = {'n': len(runs)}
    for d in DIRS:
        b = [ber(r[d]) for r in runs]
        out[d] = statistics.median(b)
        out[d + '_max'] = max(b)
        bits = sum(40 * r[d]['words'] for r in runs)
        out[d + '_ub95'] = 3.0 / bits if bits and not any(r[d]['errb'] for r in runs) else None
        out[d + '_bits'] = bits
    return out


def fmt_ber(v, ub=None):
    return ('0 (<%.1e)' % ub) if (v == 0 and ub) else ('%.2e' % v)


def main(paths):
    groups = {}
    for p in filter(is_run, paths):
        groups.setdefault(label_of(p), []).append(json.load(open(p)))
    print('| Point | n | BER gs→m2 median (worst) | BER m2→gs median (worst) | bits per direction |\n|---|---|---|---|---|')
    for lab, runs in groups.items():
        m = point(runs)
        print('| %s | %d | %s (%s) | %s (%s) | %.2e |' % (
            lab, m['n'], fmt_ber(m['gs_to_m2'], m['gs_to_m2_ub95']), fmt_ber(m['gs_to_m2_max']),
            fmt_ber(m['m2_to_gs'], m['m2_to_gs_ub95']), fmt_ber(m['m2_to_gs_max']), m['gs_to_m2_bits']))


if __name__ == '__main__':
    main(sys.argv[1:])
