#!/usr/bin/env python3
"""calib_table.py <lab.out> [...] - TASK-5527 calibration screening table from the 'PT <label> | <rx state> | <ber_long TOTAL>'
lines of lab29-lab32. Per candidate: BER both directions (0 errors -> '0 (<95 % upper)') and the M2->GS / GS->M2 ratio
against the nearest reference A row above it (A rows re-measure the untouched link inside the same load)."""
import re
import sys

PTRE = re.compile(r'^PT (\S+) \|.*\| (?:board=\S+ )?.*?([\d.]+) gs->m2 BER=(\S+) \(<(\S+)\) m2->gs BER=(\S+) \(<(\S+)\)')


def _num(s):
    return None if s == 'None' else float(s)


def parse_line(ln):
    m = PTRE.match(ln.strip())
    if not m:
        return None
    lab, secs, g, gu, mg, mu = m.groups()
    return {'label': lab, 'secs': float(secs), 'gs_to_m2': _num(g), 'gs_to_m2_upper': _num(gu),
            'm2_to_gs': _num(mg), 'm2_to_gs_upper': _num(mu)}


def _f(p, k):
    v = p[k]
    if v is None:
        return '—'
    return '0 (<%.1e)' % p[k + '_upper'] if v == 0 and p[k + '_upper'] else '%.1e' % v


def _ratio(ref, p, k):
    a, b = ref and ref[k], p[k] or p[k + '_upper']
    if not (a and b):
        return '—'
    r = a / b
    return '×%.0f' % r if r >= 10 else ('×%.1f' % r if r >= 0.1 else '×%.2g' % r)


def markdown(rows, title=''):
    h = (title and '### %s\n\n' % title) + ('| kandidat | s | M2→GS | GS→M2 | M2→GS vs A | GS→M2 vs A |\n'
                                            '|---|---|---|---|---|---|\n')
    ref = None
    for p in rows:
        if re.match(r'^(r\d+_)?A\d*[a-z]?$', p['label']):
            ref = p
        h += '| %s | %.0f | %s | %s | %s | %s |\n' % (p['label'], p['secs'], _f(p, 'm2_to_gs'), _f(p, 'gs_to_m2'),
                                                   _ratio(ref, p, 'm2_to_gs'), _ratio(ref, p, 'gs_to_m2'))
    return h


def main(paths):
    for path in paths:
        rows = [p for p in (parse_line(ln) for ln in open(path, errors='replace')) if p]
        print(markdown(rows, path.split('/')[-1]))


if __name__ == '__main__':
    main(sys.argv[1:])
