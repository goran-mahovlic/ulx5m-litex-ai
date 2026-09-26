#!/usr/bin/env python3
"""ab_table.py <run.json>... — median BER per point from repeated loads (TASK-5066, TUNING_5G.md §3 repeat rule).
Files are ber_mon.py 'run --json' results named <label>_r<k>.json (one per bitstream load). Per point and direction:
median BER, worst run, and the 95 % upper bound 3/bits when every run was clean. BER = errb / (40 * words)
(40 checked bits per word, README), capped at 0.5: at 5 Gb/s the m2 counters come back over a link with errors
and can be corrupted (TASK-5066; ber_mon.py's ber_robust is recorded but not used, it also failed on the boards).
A run without sync (0 words) counts as BER 0.5."""
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
    return min(0.5, side['errb'] / (40.0 * side['words'])) if side['words'] else 0.5


def run_ber(r, d):
    """BER of one direction of one run; a word count above secs x word rate x 1.05 is a corrupted counter -> 0.5."""
    rate = r.get('gs_tx_rate_bps') or 0
    if rate and r[d]['words'] > 1.05 * r['secs'] * rate / 80 + 1000:
        return 0.5
    return ber(r[d])


def point(runs):
    out = {'n': len(runs)}
    for d in DIRS:
        b = [run_ber(r, d) for r in runs]
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
