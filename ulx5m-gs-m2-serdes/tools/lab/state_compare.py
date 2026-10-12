#!/usr/bin/env python3
"""state_compare.py "<name>=<glob>" ... - min-max of the E0 health fields per board for groups of health JSONs (TASK-5483).

Each group is a set of eyescan.py health snapshots (one per load), e.g. "28.09 lab13 2.5G=docs/data_20260928/t5089/log13/t13_2g5_r*".
Prints one Markdown row per (field, board) with the min-max of every group, so a shift after a hardware change is visible
(PLL_CAP_FT, BISC CP/CO, RX/TX calibration codes, DFE tap, RX offset, CDR FREQ_ACC span)."""
import glob, json, sys

FIELDS = ['PLL_LOCKED', 'PLL_CAP_FT', 'PLL_CAP_STATE', 'PLL_CAP_FT_OF', 'PLL_CAP_FT_UF', 'PLL_BISC_CP', 'PLL_BISC_CO',
          'PLL_BISC_TIMER_DONE', 'RX_CALIB_CAL', 'TX_CALIB_CAL', 'RX_OFFSET', 'RX_TH_MON', 'RX_EQA_TAPW',
          'RX_EQA_LOCKED', 'RX_CDR_LOCKED', 'FREQ_ACC_SPAN']


def value(d, f):
    return d['freq_acc_span'] if f == 'FREQ_ACC_SPAN' else d['fields'].get(f)


def span(vals):
    v = [x for x in vals if x is not None]
    if not v:
        return '-'
    return str(v[0]) if min(v) == max(v) else '%d–%d' % (min(v), max(v))


def table(groups):
    """groups: [(name, [health dicts])] -> Markdown lines."""
    out = ['| field | board | ' + ' | '.join('%s (n=%s)' % (n, '/'.join(str(sum(1 for d in ds if d['board'] == b))
                                                                     for b in ('gs', 'm2'))) for n, ds in groups) + ' |',
           '|---|---|' + '---|' * len(groups)]
    for f in FIELDS:
        for b in ('gs', 'm2'):
            out.append('| %s | %s | %s |' % (f, b, ' | '.join(span([value(d, f) for d in ds if d['board'] == b])
                                                             for _, ds in groups)))
    return out


def main(argv):
    groups = []
    for a in argv[1:]:
        name, pat = a.split('=', 1)
        groups.append((name, [json.load(open(p)) for p in sorted(glob.glob(pat))]))
    print('\n'.join(table(groups)))


if __name__ == '__main__':
    main(sys.argv)
