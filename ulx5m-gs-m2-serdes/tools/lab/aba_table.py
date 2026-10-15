#!/usr/bin/env python3
"""aba_table.py <log dir> <out dir> [title] [B label] - TASK-5527 A/B/A table + picture per load (lab28 and later).

Step files r<N>_A1 / r<N>_B_<what> / r<N>_A2 .jsonl (ber_long). Per load and direction: BER of each step
(0 errors -> 95 % upper bound, flagged), gain = geomean(A1, A2) / B; medians per step and pooled A.
Writes aba_table.md and aba.png (left: per load A1/B/A2 bars, log BER, with morning lab22 and lab27 references;
right: BER per 60 s window over the whole run, B steps shaded).
"""
import glob
import os
import re
import statistics
import sys

sys.path.insert(0, os.path.dirname(__file__))
from eye_cc_report import ber_total  # noqa: E402

DIRS = ('m2_to_gs', 'gs_to_m2')
L_ = {'m2_to_gs': 'M2→GS', 'gs_to_m2': 'GS→M2'}
STEP = re.compile(r'^r(\d+)_(A1|A2|B)(_.*)?$')
# references (VERIFY §16 lab22 15.10. morning, §17 lab27 15.10. afternoon)
REF = {'morning': {'gs_to_m2': 3.6e-10, 'm2_to_gs': 4.1e-9},
       'quick30': {'gs_to_m2': 8.9e-9, 'm2_to_gs': 8.9e-11},   # REGOC 18:51, after the C143/C144 repair (TASK-5527)
       'lab27_A': (3.6e-8, 7.4e-8), 'lab27_B': (4.7e-9, 1.1e-8)}


PAYLOAD_BITS, M32 = 40, 0xFFFFFFFF
CNT = {'m2_to_gs': ('words', 'errb'), 'gs_to_m2': ('pwords', 'perrb')}


def robust(snaps):
    """BER per direction from cumulative snapshots, skipping corrupt m2 (peer) readings.

    The m2 counters reach the Pi inside the gs UART line, i.e. over the m2->gs link; when that direction is bad
    (lab28: ~1e-2) they arrive corrupted although ber_long.plausible() passed them (it checks word counters only
    against the line before). A peer reading is accepted against the last accepted one only if its words advanced
    0..1.05 x the gs words (+1000) and its bit-error counter did not go back below 2^31 (a real 32-bit wrap of the peer counter needs
    the counter near 2^32). Own gs counters are local and kept (32-bit wrap allowed)."""
    snaps = [s for s in snaps if not s.get('nouart') and s.get('words') is not None]
    out = {}
    for k, (wk, ek) in CNT.items():
        w = e = skipped = 0
        ref = snaps[0] if snaps else None
        for b in snaps[1:]:
            dw, own = b[wk] - ref[wk], b['words'] - ref['words']
            back = wk == 'pwords' and b[ek] < ref[ek] < (1 << 31)
            if dw < 0 or back or (wk == 'pwords' and dw > 1.05 * own + 1000):
                skipped += 1
                continue
            w, e, ref = w + dw, e + ((b[ek] - ref[ek]) & M32), b
        bits = w * PAYLOAD_BITS
        out[k] = {'words': w, 'errb': e, 'bits': bits, 'skipped': skipped,
                  'ber': (e / float(bits)) if bits and e else ((3.0 / bits) if bits else None), 'zero': e == 0}
    return out


def snaps_of(path):
    import json
    out = []
    for ln in open(path):
        try:
            d = json.loads(ln)
        except ValueError:
            continue
        if d.get('kind') in ('baseline', 'snap'):
            out.append(d)
    return out


def step_files(d):
    """{(load, step): path}"""
    out = {}
    for p in glob.glob(os.path.join(d, 'r*_*.jsonl')):
        m = STEP.match(os.path.basename(p)[:-6])
        if m:
            out[(int(m.group(1)), m.group(2))] = p
    return out


def step_ber(path):
    """robust() over the snapshots; files without snapshots -> ber_long's own total line."""
    sn = snaps_of(path)
    if len(sn) >= 2:
        return robust(sn)
    v = ber_total(path)
    return v and {k: {'ber': v[k], 'zero': v[k + '_err'] == 0, 'skipped': 0} for k in DIRS}


def table(d):
    files = step_files(d)
    rows = []
    for load in sorted({k[0] for k in files}):
        row = {'load': load}
        for k in DIRS:
            row[k], row[k + '_zero'] = {}, {}
            row[k + '_skipped'] = {}
            for st in ('A1', 'B', 'A2'):
                v = step_ber(files[(load, st)]) if (load, st) in files else None
                row[k][st] = v[k]['ber'] if v else None
                row[k + '_zero'][st] = bool(v) and v[k]['zero']
                row[k + '_skipped'][st] = v[k]['skipped'] if v else 0
            a = [x for x in (row[k]['A1'], row[k]['A2']) if x]
            b = row[k]['B']
            row['gain_' + k] = _geomean(a) / b if a and b else None
        rows.append(row)
    return rows


def _geomean(xs):
    p = 1.0
    for x in xs:
        p *= x
    return p ** (1.0 / len(xs))


def medians(rows):
    out = {}
    for k in DIRS:
        out[k] = {}
        for st in ('A1', 'B', 'A2'):
            xs = [r[k][st] for r in rows if r[k][st] is not None]
            out[k][st] = statistics.median(xs) if xs else None
        xs = [r[k][st] for r in rows for st in ('A1', 'A2') if r[k][st] is not None]
        out[k]['A'] = statistics.median(xs) if xs else None
        gs = [r['gain_' + k] for r in rows if r['gain_' + k]]
        out[k]['gain'] = statistics.median(gs) if gs else None
    return out


def _f(v, zero=False):
    return '—' if v is None else ('≤%.1e' % v if zero else '%.1e' % v)


def markdown(rows, b_label='gs TAPW+2'):
    h = ('| load | M2→GS A1 | M2→GS B (%s) | M2→GS A2 | gain M2→GS | GS→M2 A1 | GS→M2 B (%s) | GS→M2 A2 | gain GS→M2 |\n'
         % (b_label, b_label) +
         '|---|---|---|---|---|---|---|---|---|\n')
    for r in rows:
        c = ['r%d' % r['load']]
        for k in DIRS:
            c += [_f(r[k][s], r[k + '_zero'][s]) for s in ('A1', 'B', 'A2')]
            c.append('×%.1f' % r['gain_' + k] if r['gain_' + k] else '—')
        h += '| ' + ' | '.join(c) + ' |\n'
    m = medians(rows)
    c = ['median']
    for k in DIRS:
        c += [_f(m[k][s]) for s in ('A1', 'B', 'A2')]
        c.append('×%.1f' % m[k]['gain'] if m[k]['gain'] else '—')
    h += '| ' + ' | '.join(c) + ' |\n'
    sk = ['r%d %s %s ×%d' % (r['load'], st, L_[k], r[k + '_skipped'][st])
          for r in rows for k in DIRS for st in ('A1', 'B', 'A2') if r[k + '_skipped'][st]]
    if sk:
        h += '\nPeer (m2) snapshots dropped as corrupt (they travel over the m2->gs link): ' + ', '.join(sk) + '\n'
    return h


def segments(d):
    """[(step label, [(m2_to_gs, gs_to_m2) per 60 s window])] in load/step order."""
    import json
    files = step_files(d)
    out = []
    for key in sorted(files, key=lambda k: (k[0], ('A1', 'B', 'A2').index(k[1]))):
        seg = []
        for ln in open(files[key]):
            try:
                t = json.loads(ln)
            except ValueError:
                continue
            if t.get('kind') == 'total':
                seg = [(s.get('m2_to_gs'), s.get('gs_to_m2')) for s in t.get('segments', [])]
        out.append(('r%d %s' % key, seg))
    return out


def plot(d, out_png, title, b_label='gs RX_TAPW=+2'):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    rows = table(d)
    C = {'m2_to_gs': '#e07b00', 'gs_to_m2': '#2a6fdb'}
    L = {'m2_to_gs': 'M2 → GS', 'gs_to_m2': 'GS → M2'}
    floor = 1e-11
    fig, (ax, bx) = plt.subplots(1, 2, figsize=(17, 6.6), gridspec_kw={'width_ratios': [1.15, 1]})
    # left: per load bars
    w = 0.13
    for i, r in enumerate(rows):
        for j, k in enumerate(DIRS):
            for s_i, st in enumerate(('A1', 'B', 'A2')):
                v = r[k][st]
                if v is None:
                    continue
                x = i + (j * 3 + s_i - 2.5) * w
                ax.bar(x, v, w * 0.92, color=C[k], alpha=1.0 if st == 'B' else 0.45,
                       hatch='//' if st == 'B' else None, edgecolor='white' if st != 'B' else 'k', linewidth=0.5)
                ax.text(x, v * 1.25, st, ha='center', fontsize=7)
        g = r['gain_m2_to_gs']
        if g:
            ax.text(i, 2.5e-7, 'M2→GS ×%.1f' % g, ha='center', fontsize=9, weight='bold', color=C['m2_to_gs'])
    for k, ls in (('m2_to_gs', '--'), ('gs_to_m2', ':')):
        ax.axhline(REF['morning'][k], color=C[k], ls=ls, lw=1.2, label='%s jutro 15.10. (lab22) %.1e' % (L[k], REF['morning'][k]))
        ax.axhline(REF['quick30'][k], color=C[k], ls='-.', lw=1.0, alpha=0.7,
                   label='%s quick30 18:51 (nakon C143/C144) %.1e' % (L[k], REF['quick30'][k]))
    ax.axhspan(*REF['lab27_A'], color='#e07b00', alpha=0.08, label='M2→GS lab27 A (prije) 3,6e-8–7,4e-8')
    ax.axhspan(*REF['lab27_B'], color='#7a3d00', alpha=0.12, label='M2→GS lab27 B (TAPW+2) 4,7e-9–1,1e-8')
    ax.set_yscale('log'); ax.set_ylim(1e-12, 1e-5)
    ax.set_xticks(range(len(rows)))
    ax.set_xticklabels(['učitavanje %d' % r['load'] for r in rows])
    ax.set_ylabel('BER (niže = bolje)')
    ax.set_title('2,5 Gb/s, 300 s po koraku: A1 (adaptirano) / B (%s) / A2' % b_label)
    ax.grid(axis='y', alpha=0.3)
    ax.legend(fontsize=7.5, loc='upper center', ncol=2)
    # right: timeline
    segs = segments(d)
    x0 = 0
    for lab, seg in segs:
        n = len(seg)
        if 'B' in lab.split()[1]:
            bx.axvspan(x0 - 0.5, x0 + n - 0.5, color='#ddd', alpha=0.6, lw=0)
        bx.text(x0 + n / 2 - 0.5, 4e-6, lab, ha='center', fontsize=7, rotation=90)
        for k, ii in (('m2_to_gs', 0), ('gs_to_m2', 1)):
            ys = [max(s[ii], floor) if s[ii] is not None else None for s in seg]
            bx.plot(range(x0, x0 + n), ys, 'o-', ms=3.5, color=C[k], label=L[k] if x0 == 0 else None)
        x0 += n
        bx.axvline(x0 - 0.5, color='#999', lw=0.6, ls=':')
    bx.axhspan(1e-12, floor, color='#ccc', alpha=0.5)
    bx.set_yscale('log'); bx.set_ylim(1e-12, 1e-5)
    bx.set_xlabel('prozori od 60 s (sivo = B: %s)' % b_label); bx.set_title('BER po minuti kroz cijeli lab')
    bx.grid(alpha=0.3); bx.legend(fontsize=8, loc='lower right')
    fig.suptitle(title, fontsize=11)
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(out_png, dpi=110)
    plt.close(fig)


def main(d, outdir, title='ULX5M GS ↔ M2 SerDes 2,5G — A/B/A', b_label='gs TAPW+2'):
    os.makedirs(outdir, exist_ok=True)
    rows = table(d)
    md = markdown(rows, b_label)
    open(os.path.join(outdir, 'aba_table.md'), 'w').write(md)
    print(md)
    m = medians(rows)
    print('MEDIANS', {k: {s: _f(v) if s != 'gain' else v for s, v in m[k].items()} for k in DIRS})
    plot(d, os.path.join(outdir, 'aba.png'), title, b_label)


if __name__ == '__main__':
    main(*sys.argv[1:])
