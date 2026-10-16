#!/usr/bin/env python3
"""proof_table.py <lab39.out> <soak.jsonl> <out dir> - TASK-5527 uputa #339 proof summary.
(B) repeatability: one row per fresh load (t_link, PEER 200/200, 60 s A and G2 BER, result) + counts.
(A) soak: total BER per direction with a 95 % Poisson interval, hourly BER, share of 60 s intervals with 0 errors.
Writes proof_table.md and proof.png (left: soak BER per 60 s interval + hourly, log; right: worse direction per load)."""
import json
import math
import os
import re
import sys

from ber_long import DIRS, PAYLOAD_BITS, _delta, segments, total

TOT = r'TOTAL secs=\S+ gs->m2 BER=(\S+) \(<(\S+)\) m2->gs BER=(\S+) \(<(\S+)\)'
LOADRE = re.compile(r'^LOAD (\S+) t_link=([\d.]+)s ok=(\d) .*?gs RX_OFFSET=(-?\d+) m2 RX_OFFSET=(-?\d+)')
BERRE = re.compile(r'^BER (\S+?)_(A|g2_\S+) ' + TOT)
RESRE = re.compile(r'^RESULT (\S+) (accepted=first|accepted=G2|rejected)')
DIRNAME = {'m2_to_gs': 'M2→GS', 'gs_to_m2': 'GS→M2'}


def _num(s):
    return None if s == 'None' else float(s)


def parse(text):
    """Attempts in order, one per fresh load."""
    out, cur = [], None
    for ln in text.splitlines():
        m = LOADRE.match(ln)
        if m:
            tag = m.group(1)
            cur = {'tag': tag, 'trial': tag.rsplit('_', 1)[0], 't_link': float(m.group(2)), 'ok': m.group(3) == '1',
                   'gs_off': int(m.group(4)), 'm2_off': int(m.group(5)), 'peer_ok': None, 'A': None, 'G2': None,
                   'result': None}
            out.append(cur)
            continue
        if cur is None:
            continue
        if ln.startswith('PEER %s ' % cur['tag']):
            cur['peer_ok'] = ln.count('PEER 200/200') == 2 and 'FAIL' not in ln
        m = BERRE.match(ln)
        if m and m.group(1) == cur['tag']:
            g, gu, mg, mu = (_num(x) for x in m.groups()[2:])
            cur['A' if m.group(2) == 'A' else 'G2'] = {'gs_to_m2': g, 'gs_to_m2_upper': gu, 'm2_to_gs': mg,
                                                        'm2_to_gs_upper': mu}
        m = RESRE.match(ln)
        if m and m.group(1) == cur['tag']:
            cur['result'] = {'accepted=first': 'first', 'accepted=G2': 'G2', 'rejected': 'rejected'}[m.group(2)]
    return out


def summary(att):
    tl = [a['t_link'] for a in att]
    return {'loads': len(att), 'peer_ok': sum(1 for a in att if a['peer_ok']),
            'first': sum(1 for a in att if a['result'] == 'first'), 'g2': sum(1 for a in att if a['result'] == 'G2'),
            't_link_min': min(tl), 't_link_max': max(tl)}


def buckets(snaps, width):
    """BER per direction in consecutive windows of `width` s (intervals assigned by their start time)."""
    acc = {}
    for a, b in zip(snaps, snaps[1:]):
        i = int((a['t'] - snaps[0]['t']) // width)
        r = acc.setdefault(i, {'i': i})
        for k, wk, ek in DIRS:
            dw, de, _ = _delta(a, b, wk, ek)
            w, e = r.get(k + '_w', 0) + dw, r.get(k + '_e', 0) + de
            r[k + '_w'], r[k + '_e'] = w, e
    out = []
    for i in sorted(acc):
        r = acc[i]
        for k, _, _ in DIRS:
            r[k] = r[k + '_e'] / (r[k + '_w'] * float(PAYLOAD_BITS)) if r[k + '_w'] else None
        out.append(r)
    return out


def clean_intervals(snaps):
    """(intervals with 0 errors, all intervals) per direction."""
    seg = segments(snaps)
    return {k: (sum(1 for s in seg if s[k] == 0), sum(1 for s in seg if s[k] is not None)) for k, _, _ in DIRS}


def poisson95(errors, bits):
    """Two-sided 95 % interval of the BER (normal approximation; 0 errors -> rule of three)."""
    if errors == 0:
        return 0.0, 3.0 / bits
    d = 1.96 * math.sqrt(errors)
    return max(errors - d, 0) / bits, (errors + d) / bits


def _f(v, up=None):
    if v is None:
        return '—'
    if v == 0:
        return '0 (<%.1e)' % up if up else '0'
    return '%.1e' % v


def markdown(att, snaps, soak_tag):
    s, t = summary(att), total(snaps)
    L = ['## (B) Repeatability — %d fresh loads' % s['loads'], '',
         '| Load | t_link s | PEER 200/200 both | offset gs / m2 | M2→GS A | GS→M2 A | M2→GS G2 | GS→M2 G2 | result |',
         '|---|---|---|---|---|---|---|---|---|']
    for a in att:
        A, G = a['A'] or {}, a['G2'] or {}
        L.append('| %s | %.1f | %s | %d / %d | %s | %s | %s | %s | %s |' % (
            a['tag'] + (' (soak)' if a['tag'] == soak_tag else ''), a['t_link'], 'yes' if a['peer_ok'] else 'NO',
            a['gs_off'], a['m2_off'], _f(A.get('m2_to_gs'), A.get('m2_to_gs_upper')),
            _f(A.get('gs_to_m2'), A.get('gs_to_m2_upper')), _f(G.get('m2_to_gs'), G.get('m2_to_gs_upper')),
            _f(G.get('gs_to_m2'), G.get('gs_to_m2_upper')), a['result']))
    L += ['', 'Link up (PEER 200/200 both): **%d/%d** loads, t_link %.1f–%.1f s. Accepted (< 1e-9 both, 60 s): first try **%d/%d**, '
          'after the G2 rule +%d → **%d/%d**.' % (s['peer_ok'], s['loads'], s['t_link_min'], s['t_link_max'], s['first'],
                                                   s['loads'], s['g2'], s['first'] + s['g2'], s['loads']), '',
          '## (A) Soak on load %s — %.2f h' % (soak_tag, t['secs'] / 3600.0), '',
          '| Direction | bits | bit errors | BER | 95 % interval | 60 s intervals with 0 errors | restarts |', '|---|---|---|---|---|---|---|']
    c = clean_intervals(snaps)
    for k, _, _ in DIRS:
        lo, hi = poisson95(t[k]['errb'], t[k]['bits'])
        L.append('| %s | %.2e | %d | %.2e | %.2e – %.2e | %d / %d | %d |' % (
            DIRNAME[k], t[k]['bits'], t[k]['errb'], t[k]['ber'], lo, hi, c[k][0], c[k][1], t['restarts'][k]))
    L += ['', '| Hour | M2→GS | GS→M2 |', '|---|---|---|']
    for h in buckets(snaps, 3600):
        L.append('| %d | %s | %s |' % (h['i'] + 1, _f(h['m2_to_gs']), _f(h['gs_to_m2'])))
    return '\n'.join(L) + '\n'


def plot(att, snaps, out_png, title):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, (ax, bx) = plt.subplots(1, 2, figsize=(14, 5.2), gridspec_kw={'width_ratios': [1.6, 1]})
    seg = segments(snaps)
    col = {'m2_to_gs': '#d62728', 'gs_to_m2': '#1f77b4'}
    floor = 1e-11
    for k, _, _ in DIRS:
        x = [s['t1'] / 3600.0 for s in seg if s[k] is not None]
        y = [max(s[k], floor) for s in seg if s[k] is not None]
        ax.plot(x, y, '.', ms=3, color=col[k], alpha=0.5, label='%s per 60 s' % DIRNAME[k])
        h = [b for b in buckets(snaps, 3600) if b[k] is not None]
        end = (snaps[-1]['t'] - snaps[0]['t']) / 3600.0
        ax.hlines([max(b[k], floor) for b in h], [b['i'] for b in h], [min(b['i'] + 1, end) for b in h], color=col[k],
                  lw=2.5, label='%s hourly' % DIRNAME[k])
    ax.axhline(1e-9, color='k', ls='--', lw=1)
    ax.text(0.05, 1.15e-9, 'acceptance 1e-9', fontsize=8)
    ax.set_yscale('log'); ax.set_ylim(5e-12, 1e-6); ax.set_xlabel('soak time [h]'); ax.set_ylabel('BER')
    ax.set_title('(A) soak, one load, both directions (points at 1e-11 = 0 errors)', fontsize=10)
    ax.legend(fontsize=8, loc='upper right'); ax.grid(True, which='both', alpha=0.3)
    xs, labels = range(len(att)), [a['tag'] for a in att]
    for k, dx, mk in (('m2_to_gs', -0.15, 'v'), ('gs_to_m2', 0.15, '^')):
        bx.scatter([i + dx for i in xs], [max((a['A'] or {}).get(k) or floor, floor) for a in att], marker=mk,
                   color=col[k], label='%s A (60 s)' % DIRNAME[k])
        g = [(i + dx, max(a['G2'][k] or floor, floor)) for i, a in zip(xs, att) if a['G2']]
        bx.scatter([p[0] for p in g], [p[1] for p in g], marker=mk, facecolors='none', edgecolors=col[k],
                   label='%s after G2' % DIRNAME[k])
    for i, a in zip(xs, att):
        if a['result'] != 'rejected':
            bx.axvspan(i - 0.4, i + 0.4, color='#2ca02c', alpha=0.12)
    bx.axhline(1e-9, color='k', ls='--', lw=1)
    bx.set_yscale('log'); bx.set_ylim(5e-12, 1e-6); bx.set_xticks(list(xs)); bx.set_xticklabels(labels, rotation=90, fontsize=7)
    bx.set_title('(B) every fresh load (green = accepted)', fontsize=10); bx.legend(fontsize=7, loc='upper left')
    bx.grid(True, which='both', alpha=0.3)
    fig.suptitle(title, fontsize=11)
    fig.tight_layout()
    fig.savefig(out_png, dpi=110)


def load_snaps(path):
    return [s for s in (json.loads(l) for l in open(path) if l.strip()) if 'words' in s and not s.get('nouart')]


def main():
    if len(sys.argv) < 4:
        sys.exit(__doc__)
    att = parse(open(sys.argv[1]).read())
    snaps = load_snaps(sys.argv[2])
    soak = [a['tag'] for a in att if a['tag'].startswith('soak') and a['result'] != 'rejected']
    soak_tag = soak[-1] if soak else '?'
    os.makedirs(sys.argv[3], exist_ok=True)
    md = markdown(att, snaps, soak_tag)
    open(os.path.join(sys.argv[3], 'proof_table.md'), 'w').write(md)
    print(md)
    if '--no-png' not in sys.argv:
        plot(att, snaps, os.path.join(sys.argv[3], 'proof.png'),
             sys.argv[4] if len(sys.argv) > 4 and not sys.argv[4].startswith('--') else 'TASK-5527 lab39 proof')


if __name__ == '__main__':
    main()
