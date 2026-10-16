#!/usr/bin/env python3
"""gate_table.py <dir> [--md out.md] - TASK-5542: tables from link_gate.py logs (<run>.jsonl, <run>_soak.jsonl).

Per run: attempts, verdict, level that passed, per-attempt code (P pass, q Q fail, c C fail, h health fail, u UART).
Per group (run name up to the last '_' or trailing digits: b1..b5 -> b, a10_2 -> a10): runs passed, attempts to a
pass, first-attempt pass share, per-attempt pass share, and per ladder level (K3) the pass share of that level.
Soak: BER per direction from snapshot deltas, first window dropped, Garwood 95 %, bursts (10 s windows > 20 errors)."""
import argparse
import glob
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ber_windows import windows, summarize  # noqa: E402
from link_gate import DIRS, bursts  # noqa: E402


def group(run):
    if '_' in run:
        return run.rsplit('_', 1)[0]
    return re.sub(r'\d+$', '', run) or run


def code(r):
    if r['verdict'] == 'PASS':
        return 'P'
    if r['verdict'] == 'UNDECIDED':
        return 'u'
    if (r.get('c') or {}).get('verdict') == 'FAIL':
        return 'c'
    if (r.get('q') or {}).get('verdict') == 'FAIL':
        return 'q'
    return 'h'


def load(path):
    rows = [json.loads(l) for l in open(path) if l.strip()]
    att = [r for r in rows if 'attempt' in r]
    gate = [r for r in rows if r.get('kind') == 'gate']
    return att, (gate[-1] if gate else None)


def ber(err, bits):
    return err / float(bits) if bits else None


def run_row(name, att, gate):
    p = [r for r in att if r['verdict'] == 'PASS']
    acc = p[-1] if p else None
    row = {'run': name, 'group': group(name), 'set': ' '.join(att[0].get('set') or []) if att else '',
           'verdict': gate['verdict'] if gate else 'RUNNING', 'attempts': gate['attempts'] if gate else len(att),
           'codes': ''.join(code(r) for r in att), 'levels': [r['level'] for r in att],
           'level': acc['level'] if acc else None, 't_link': acc.get('t_link_s') if acc else None}
    if acc:
        for st in ('q', 'c'):
            for k in DIRS:
                row['%s_%s' % (st, k)] = (acc[st]['err'][k], acc[st]['bits'][k])
    return row


def group_stats(rows, att_by_run):
    out = {}
    for g in sorted(set(r['group'] for r in rows)):
        rs = [r for r in rows if r['group'] == g and r['verdict'] != 'RUNNING']
        atts = [a for r in rs for a in att_by_run[r['run']] if a['verdict'] in ('PASS', 'FAIL')]
        firsts = [att_by_run[r['run']][0] for r in rs if att_by_run[r['run']]]
        lv = {}
        for a in atts:
            lv.setdefault(a['level'], [0, 0])
            lv[a['level']][0] += a['verdict'] == 'PASS'
            lv[a['level']][1] += 1
        out[g] = {'runs': len(rs), 'pass': sum(r['verdict'] == 'PASS' for r in rs),
                  'attempts_to_pass': [r['attempts'] for r in rs if r['verdict'] == 'PASS'],
                  'first_pass': (sum(f['verdict'] == 'PASS' for f in firsts), len(firsts)),
                  'attempt_pass': (sum(a['verdict'] == 'PASS' for a in atts), len(atts)), 'levels': lv}
    return out


def soak_summary(path, skip=1):
    rows = [json.loads(l) for l in open(path) if l.strip()]
    snaps = [r for r in rows if r.get('kind') in ('baseline', 'snap')]
    ws = windows(snaps)
    if len(ws) <= skip:
        return None
    t = summarize(ws[skip:])
    b = bursts([{'t0': w['t0'], 't1': w['t1'], 'm2_to_gs': w['m2_to_gs'], 'gs_to_m2': w['gs_to_m2']} for w in ws[skip:]])
    t['bursts'] = {k: len(v) for k, v in b.items()}
    t['burst_err'] = {k: sum(ws[skip + i][k]['errb'] for i in v) for k, v in b.items()}
    return t


def attempt_rows(att_by_run):
    """One row per attempt: Q BER (errors / bits measured until the verdict, early exit included), adapted point."""
    L = ['| run | n | razina | t_link s | gs CAP_FT / TH_MON / TAPW / OFFSET | m2 CAP_FT / TH_MON / TAPW / OFFSET | '
         'Q M2→GS BER (err, s) | Q GS→M2 BER (err) | C M2→GS / GS→M2 err | ishod |', '|---|---|---|---|---|---|---|---|---|---|']
    for run, att in att_by_run.items():
        for r in att:
            h = r.get('health') or {}
            pt = ['%s / %s / %s / %s' % tuple((h.get(b) or {}).get(k, '—') for k in
                                              ('PLL_CAP_FT', 'RX_TH_MON', 'RX_EQA_TAPW', 'RX_OFFSET')) for b in ('gs', 'm2')]
            q, c = r.get('q') or {}, r.get('c') or {}
            qs = ['%s (%d%s)' % (fmt(ber(q['err'][k], q['bits'][k])), q['err'][k],
                                 ', %.0f s' % q['secs'] if k == 'm2_to_gs' and 'secs' in q else '')
                  if q.get('bits') else '—' for k in DIRS]
            cs = '%d / %d' % (c['err']['m2_to_gs'], c['err']['gs_to_m2']) if c.get('err') else '—'
            L.append('| %s | %d | %s | %s | %s | %s | %s | %s | %s | %s |' % (
                run, r['attempt'], r['level'], r.get('t_link_s') if r.get('t_link_s') is not None else '—', pt[0], pt[1],
                qs[0], qs[1], cs, code(r) + ('' if r['verdict'] == 'PASS' else ' ' + str(r.get('reason') or '')[:60])))
    return '\n'.join(L)


def fmt(x):
    return '%.1e' % x if x else ('0' if x == 0 else '—')


def render(d):
    att_by_run, rows = {}, []
    for p in sorted(glob.glob(os.path.join(d, '*.jsonl'))):
        name = os.path.basename(p)[:-6]
        if name.endswith('_soak'):
            continue
        att, gate = load(p)
        att_by_run[name] = att
        rows.append(run_row(name, att, gate))
    L = ['| run | set | ishod | pokušaja | tijek (P/q/c/h/u) | razina | t_link s | Q M2→GS / GS→M2 (greške) | C 60 s M2→GS BER | C 60 s GS→M2 BER |',
         '|---|---|---|---|---|---|---|---|---|---|']
    for r in rows:
        q = ('%d / %d' % (r['q_m2_to_gs'][0], r['q_gs_to_m2'][0])) if 'q_m2_to_gs' in r else '—'
        c1 = ('%s (%d)' % (fmt(ber(*r['c_m2_to_gs'])), r['c_m2_to_gs'][0])) if 'c_m2_to_gs' in r else '—'
        c2 = ('%s (%d)' % (fmt(ber(*r['c_gs_to_m2'])), r['c_gs_to_m2'][0])) if 'c_gs_to_m2' in r else '—'
        L.append('| %s | %s | %s | %d | `%s` | %s | %s | %s | %s | %s |' % (
            r['run'], r['set'] or '—', r['verdict'], r['attempts'], r['codes'], r['level'] or '—',
            r['t_link'] if r['t_link'] is not None else '—', q, c1, c2))
    gs = group_stats(rows, att_by_run)
    L += ['', '| skupina | vrata prošla | pokušaja do prolaza | prolaz iz prve | prolaz po pokušaju | po razini (prolaz/pokušaja) |',
          '|---|---|---|---|---|---|']
    for g, s in gs.items():
        L.append('| %s | %d/%d | %s | %d/%d | %d/%d = %.0f %% | %s |' % (
            g, s['pass'], s['runs'], s['attempts_to_pass'] or '—', s['first_pass'][0], s['first_pass'][1],
            s['attempt_pass'][0], s['attempt_pass'][1],
            100.0 * s['attempt_pass'][0] / s['attempt_pass'][1] if s['attempt_pass'][1] else 0,
            ', '.join('%s %d/%d' % (k, v[0], v[1]) for k, v in sorted(s['levels'].items()))))
    for p in sorted(glob.glob(os.path.join(d, '*_soak.jsonl'))):
        t = soak_summary(p)
        if not t:
            continue
        L += ['', 'Soak `%s`: %.0f s zadržano u %d prozora (prvi odbačen)' % (os.path.basename(p), t['secs'], t['n']), '',
              '| smjer | greške | bita | BER | 95 % | Δloss | rafala (>20/10 s) | grešaka u rafalima | medijan prozora |',
              '|---|---|---|---|---|---|---|---|---|']
        for k in DIRS:
            x = t[k]
            wb = x['win_ber']
            L.append('| %s | %d | %.3e | %s | %s – %s | %d | %d | %d | %s |' % (
                k.replace('_to_', '→').upper(), x['errb'], x['bits'], fmt(x['ber']), fmt(x['ci95'][0]),
                fmt(x['ci95'][1]), x['dloss'], t['bursts'][k], t['burst_err'][k], fmt(wb[len(wb) // 2]) if wb else '—'))
    return '\n'.join(L), rows, gs, att_by_run


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('dir')
    ap.add_argument('--md')
    ap.add_argument('--attempts', action='store_true', help='append the per-attempt table')
    a = ap.parse_args()
    md, _, _, att = render(a.dir)
    if a.attempts:
        md += '\n\n' + attempt_rows(att)
    print(md)
    if a.md:
        open(a.md, 'w').write(md + '\n')
    return 0


if __name__ == '__main__':
    sys.exit(main())
