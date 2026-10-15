#!/usr/bin/env python3
"""eye_cc_report.py <log25 dir> <out dir> [<A/B/A log dir> ...] - TASK-5525 pictures (needs matplotlib; runs on the Pi).

1. diag_chain.png   eye_diagnose PASS/FAIL per board x rate (lab25 diag_*.json)
2. capture_op.png   eye_capture_op x10 per board x rate: RX_OFFSET, TH_MON1/2, TAPW per capture (lab25 capture_*.json)
3. calib_<dir>.png  A/B/A inside one load (lab26, lab26b): serial BER per 60 s step in execution order, both directions
4. tapw_bathtub.png gs RX_TAPW pinned vs serial BER (all tapw<N>.jsonl of the A/B/A dirs; A steps = adapted tap 0)
"""
import glob
import json
import os
import re
import sys

CHECK = re.compile(r'\[(PASS|FAIL)\] (.*)$')


def diag_rows(text):
    """eye_diagnose text -> [(check, 'PASS'|'FAIL', detail)]."""
    out = []
    for ln in text.splitlines():
        m = CHECK.search(ln)
        if not m:
            continue
        rest = m.group(2)                          # f'{name:28} {detail}': padded, or longer than 28 with one space
        g = re.search(r'\s{2,}', rest)
        if g and g.start() <= 28:
            name, detail = rest[:g.start()], rest[g.end():]
        else:
            i = rest.find(' ', 28)
            name, detail = (rest, '') if i < 0 else (rest[:i], rest[i + 1:])
        out.append((name.strip(), m.group(1), detail.strip()))
    return out


def ber_total(path):
    """Last 'total' line of a ber_long jsonl -> {'gs_to_m2': ber, 'm2_to_gs': ber} (None when missing)."""
    tot = None
    for ln in open(path):
        try:
            d = json.loads(ln)
        except ValueError:
            continue
        if d.get('kind') == 'total':
            tot = d
    if tot is None:
        return None
    out = {}
    for k in ('gs_to_m2', 'm2_to_gs'):
        v = tot.get(k)
        out[k] = None if not isinstance(v, dict) else (v['ber'] if v.get('errb') else v.get('ber_95_upper'))
        out[k + '_err'] = v.get('errb') if isinstance(v, dict) else None
    return out


def steps_in_order(d):
    """Step names of an A/B/A run in execution order (ber_long writes each .jsonl once, at the end of its step)."""
    fs = sorted(glob.glob(os.path.join(d, '*.jsonl')), key=os.path.getmtime)
    return [os.path.basename(f)[:-6] for f in fs]


TAPW = re.compile(r'^(A_)?tapw(-?\d+)$')


def tapw_points(dirs):
    """{'B': [(tapw, m2_to_gs, gs_to_m2)], 'A': [...]} from tapw<N> / A_tapw<N> step files (A = adapted, plotted at 0)."""
    out = {'A': [], 'B': []}
    for d in dirs:
        for st in steps_in_order(d):
            m = TAPW.match(st)
            v = m and ber_total(os.path.join(d, st + '.jsonl'))
            if v:
                out['A' if m.group(1) else 'B'].append((0 if m.group(1) else int(m.group(2)), v['m2_to_gs'], v['gs_to_m2']))
    return out


def main(l25, outdir, *aba):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    os.makedirs(outdir, exist_ok=True)

    # 1. diagnose chain
    cols = [(r, b) for r in ('2g5', '5g_p2', '2g5_back') for b in ('m2', 'gs')]
    data = {}
    for r, b in cols:
        p = os.path.join(l25, '%s.diag_%s.json' % (r, b))
        if os.path.exists(p):
            data[(r, b)] = diag_rows(json.load(open(p))['text'])
    names = []
    for rows in data.values():
        for n, _, _ in rows:
            if n not in names:
                names.append(n)
    fig, ax = plt.subplots(figsize=(13, 0.5 * len(names) + 1.8))
    ax.set_xlim(0, len(cols)); ax.set_ylim(0, len(names)); ax.invert_yaxis(); ax.axis('off')
    for j, c in enumerate(cols):
        ax.text(j + 0.5, -0.3, '%s RX\n%s' % (c[1], c[0].replace('_', ' ')), ha='center', va='bottom', fontsize=10, weight='bold')
        rows = {n: (v, d) for n, v, d in data.get(c, [])}
        for i, n in enumerate(names):
            v = rows.get(n, ('—', ''))[0]
            col = {'PASS': '#2e7d32', 'FAIL': '#c62828'}.get(v, '#9e9e9e')
            ax.add_patch(plt.Rectangle((j + 0.05, i + 0.08), 0.9, 0.84, color=col, alpha=0.85))
            ax.text(j + 0.5, i + 0.5, v, ha='center', va='center', color='white', fontsize=9, weight='bold')
    for i, n in enumerate(names):
        ax.text(-0.05, i + 0.5, n, ha='right', va='center', fontsize=9)
    ax.set_title('eye_diagnose (Cologne Chip serdestool 15.10.2026) on ULX5M GS/M2 - TASK-5525\n'
                 'freeze + routing PASS; RX_EYE_MEAS_EN never clears (counters 0); adapted thresholds railed at +15 on 2.5 G',
                 fontsize=10, pad=40)
    fig.subplots_adjust(left=0.25, right=0.98, top=0.82)
    fig.savefig(os.path.join(outdir, 'diag_chain.png'), dpi=110); plt.close(fig)

    # 2. capture series
    fig, axs = plt.subplots(2, 3, figsize=(13, 6.5), sharex=True)
    for i, b in enumerate(('m2', 'gs')):
        for j, r in enumerate(('2g5', '5g_p2', '2g5_back')):
            ax = axs[i][j]
            p = os.path.join(l25, '%s.capture_%s.json' % (r, b))
            if not os.path.exists(p):
                ax.set_visible(False); continue
            d = json.load(open(p))
            x = list(range(len(d['capture_op'])))
            for k, st in (('offset', 'o-'), ('th_mon1', 's--'), ('th_mon2', '^:'), ('tapw', 'd-')):
                ax.plot(x, [o[k] for o in d['capture_op']], st, label=k, ms=5)
            ax.plot(x, [o['offset'] for o in d['split_reads']], 'x', color='k', label='offset, split reads')
            ax.set_ylim(-2, 16.5); ax.grid(alpha=0.3)
            ax.set_title('%s RX, %s' % (b, r.replace('_', ' ')), fontsize=10)
            if i == 1:
                ax.set_xlabel('capture # (0.2 s apart)')
    axs[0][0].legend(fontsize=7, loc='center right')
    fig.suptitle('eye_capture_op x10 (ONE read of 0x07 per monitor) - gs RX_OFFSET moves 1<->2 also when read correctly', fontsize=11)
    fig.tight_layout(); fig.savefig(os.path.join(outdir, 'capture_op.png'), dpi=110); plt.close(fig)

    # 3. A/B/A
    for l26 in aba:
        tag = os.path.basename(os.path.normpath(l26))
        steps = steps_in_order(l26)
        vals = {s: ber_total(os.path.join(l26, s + '.jsonl')) for s in steps}
        fig, ax = plt.subplots(figsize=(13, 5))
        xs = range(len(steps))
        for k, col, dx in (('m2_to_gs', '#c62828', -0.2), ('gs_to_m2', '#1565c0', 0.2)):
            ys = [(vals[s] or {}).get(k) or 1e-12 for s in steps]
            ax.bar([x + dx for x in xs], ys, width=0.38, color=col,
                   label=k.replace('_to_', '->') + (' (gs RX, tuned)' if k == 'm2_to_gs' else ' (m2 RX, control)'))
        for x, s in zip(xs, steps):
            if not s.startswith('A'):
                ax.axvspan(x - 0.5, x + 0.5, color='#fff59d', alpha=0.35, lw=0)
        ax.set_yscale('log'); ax.set_xticks(list(xs)); ax.set_xticklabels(steps, rotation=35, fontsize=9)
        ax.set_ylabel('serial BER, 60 s'); ax.grid(axis='y', alpha=0.3); ax.legend(fontsize=9)
        ax.set_title('%s: gs RX operating point, A/B/A inside one 2.5 G load (yellow = B: m2 TX_AMP or gs TAPW pinned)' % tag,
                     fontsize=10)
        fig.tight_layout(); fig.savefig(os.path.join(outdir, 'calib_%s.png' % tag), dpi=110); plt.close(fig)
        json.dump(vals, open(os.path.join(outdir, 'calib_%s.json' % tag), 'w'), indent=1)
    # 4. TAPW bathtub
    tp = tapw_points(aba)
    if tp['B']:
        fig, ax = plt.subplots(figsize=(9, 5))
        b = sorted(tp['B'])
        ax.semilogy([x for x, _, _ in b], [y or 1e-12 for _, y, _ in b], 'o-', color='#c62828', ms=8,
                    label='m2->gs (gs RX), gs RX_TAPW pinned (freeze, readback ok)')
        ax.semilogy([x for x, _, _ in tp['A']], [y or 1e-12 for _, y, _ in tp['A']], 'x', color='#555', ms=8,
                    label='m2->gs, A steps: adapted tap (reads 0)')
        ax.semilogy([x for x, _, _ in b], [z or 1e-12 for _, _, z in b], 's--', color='#1565c0', ms=5, alpha=0.7,
                    label='gs->m2 (m2 RX, control)')
        ax.set_xlabel('gs RX_TAPW (DFE tap, signed code)'); ax.set_ylabel('serial BER, 60 s per point')
        ax.grid(alpha=0.3, which='both'); ax.legend(fontsize=8)
        ax.set_title('gs receiver bathtub over the pinned DFE tap, 2.5 G, one load (lab26c + lab26d)\n'
                     'adapted tap = 0 because both monitors rail at +15; bottom at +2', fontsize=10)
        fig.tight_layout(); fig.savefig(os.path.join(outdir, 'tapw_bathtub.png'), dpi=110); plt.close(fig)
    print('wrote', ' '.join(sorted(os.path.basename(p) for p in glob.glob(os.path.join(outdir, '*.png')))))


if __name__ == '__main__':
    main(*sys.argv[1:])
