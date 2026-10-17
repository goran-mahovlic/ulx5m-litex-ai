#!/usr/bin/env python3
"""k4_amp.py - TASK-5559 K4a: TX_AMP per board after K3 (gs TX couples into gs RX), judged over repeated readapt draws.

    cd ~/ulx5m-serdes/tools; python3 lab/k4_amp.py --loads 2 --cycles 3 --out ../t5559/k4/k4amp.jsonl
    python3 lab/k4_amp.py --table ../t5559/k4/k4amp.jsonl

K3 (k3.jsonl) showed: (1) every EQA readapt is a new draw (A states of one load differ x10-x100), (2) its burst
(~2500 bit errors) lands in the first 10 s window, (3) gs TX idle lowers M2->GS x2.9-x47 and AMP 16 (either board) raises the error rate on most cells, so lower AMPs are tried.
So a point is visited --cycles times per load in interleaved order; per visit: write gs/m2 TX_AMP (readback-checked),
readapt EQA on both RX, wait --skip s (burst out), measure --secs. Per pair and direction: median BER over all visits,
95 % Garwood interval on the pooled count. The pair with the lowest worse-direction median wins if it beats (12, 12)
in that worse direction by >= x2 on every load (median over that load's visits)."""
import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from link_gate import DIRS, Uart, diag_summary, measure, readapt_cmds, set_check, ci95  # noqa: E402

# K4b: FFE/CTLE/B-static on top of the K4a winner (gs AMP 8, m2 AMP 12); every visit writes ALL these fields
BASE = {'gs': {'TX_AMP': 8, 'TX_SEL_POST': 5, 'RX_EN_EQA': 1, 'RX_AFE_PEAK': 24, 'RX_AFE_GAIN': 0},
        'm2': {'TX_AMP': 12, 'TX_SEL_POST': 5, 'RX_EN_EQA': 1, 'RX_AFE_PEAK': 24, 'RX_AFE_GAIN': 0}}
STATIC = {'RX_EN_EQA': 0, 'RX_AFE_PEAK': 15, 'RX_AFE_GAIN': 8}
POINTS = [('base', {}, {}), ('m2post8', {}, {'TX_SEL_POST': 8}), ('m2post12', {}, {'TX_SEL_POST': 12}),
          ('gspost0', {'TX_SEL_POST': 0}, {}), ('gspeak16', {'RX_AFE_PEAK': 16}, {}), ('m2peak16', {}, {'RX_AFE_PEAK': 16}),
          ('static', STATIC, STATIC)]


def point_fields(pt):
    """(name, gs over, m2 over) -> {'gs': fields, 'm2': fields} = BASE + overrides."""
    return {'gs': dict(BASE['gs'], **pt[1]), 'm2': dict(BASE['m2'], **pt[2])}


PAIRS = [(12, 12), (10, 12), (8, 12), (10, 10), (8, 10), (12, 10)]   # (gs TX_AMP, m2 TX_AMP); K3: AMP 16 worse on 3/3


def med(xs):
    xs = sorted(x for x in xs if x is not None)
    if not xs:
        return None
    n = len(xs)
    return xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2.0


def ber_floor(err, bits):
    """0 errors -> 0.5 / bits so medians and ratios stay finite (as calib_aba.ber_of)."""
    return (err if err else 0.5) / float(bits) if bits else None


def drop_first(r):
    """Visit without its first 10 s window: the m2 readapt burst (GS->M2 ~2500) still lands there after --skip 12 s
    (m2 counters reach gs over the back channel late). Bits scale with the kept share of the windows."""
    w = r.get('win') or []
    if len(w) < 2:
        return r
    keep = (len(w) - 1) / float(len(w))
    return dict(r, err={k: sum(x[k] for x in w[1:]) for k in DIRS}, bits={k: r['bits'][k] * keep for k in DIRS})


def table(recs):
    vis = [drop_first(r) for r in recs if r.get('kind') == 'visit' and not r.get('set_fail')]
    out = {}
    for r in vis:
        o = out.setdefault(r.get('point') or tuple(r['pair']), {'n': 0, 'ber': {k: [] for k in DIRS}, 'err': {k: 0 for k in DIRS},
                                              'bits': {k: 0 for k in DIRS}, 'load_med': {}})
        o['n'] += 1
        for k in DIRS:
            o['ber'][k].append(ber_floor(r['err'][k], r['bits'][k]))
            o['err'][k] += r['err'][k]
            o['bits'][k] += r['bits'][k]
        o['load_med'].setdefault(r['load'], {k: [] for k in DIRS})
        for k in DIRS:
            o['load_med'][r['load']][k].append(ber_floor(r['err'][k], r['bits'][k]))
    for p, o in out.items():
        o['median'] = {k: med(o['ber'][k]) for k in DIRS}
        o['pooled'] = {k: (o['err'][k] / float(o['bits'][k]) if o['bits'][k] else None) for k in DIRS}
        o['ci95'] = {k: ([x / float(o['bits'][k]) for x in ci95(o['err'][k])] if o['bits'][k] else None) for k in DIRS}
        o['worse'] = max(DIRS, key=lambda k: o['median'][k] or 0)
        o['load_med'] = {ld: {k: med(v[k]) for k in DIRS} for ld, v in o['load_med'].items()}
    bkey = 'base' if 'base' in out else (12, 12)
    base = out.get(bkey)
    if base:
        for p, o in out.items():
            k = base['worse']
            o['beats_base_every_load'] = p != bkey and all(
                (o['load_med'].get(ld, {}).get(k) or 1) * 2 <= (bm[k] or 0) for ld, bm in base['load_med'].items())
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--table')
    ap.add_argument('--out')
    ap.add_argument('--loads', type=int, default=2)
    ap.add_argument('--cycles', type=int, default=3)
    ap.add_argument('--skip', type=float, default=12)
    ap.add_argument('--secs', type=float, default=40)
    ap.add_argument('--points', action='store_true', help='K4b: POINTS (FFE/CTLE/static on BASE) instead of AMP PAIRS')
    ap.add_argument('--bits-gs', default='/home/pi/fpga/t5559/gs_2g5_b0p_s7.bit')
    ap.add_argument('--bits-m2', default='/home/pi/fpga/t5559/m2_2g5_b0p_s2.bit')
    a = ap.parse_args()
    if a.table:
        t = table([json.loads(l) for l in open(a.table) if l.strip()])
        print('| gs AMP | m2 AMP | visits | M2->GS median | GS->M2 median | M2->GS pooled [95 %] | GS->M2 pooled [95 %] | beats (12,12) every load |')
        print('|---|---|---|---|---|---|---|---|')
        f = lambda x: '-' if x is None else '%.1e' % x                                    # noqa: E731
        for p, o in sorted(t.items(), key=lambda kv: str(kv[0])):
            p = p if isinstance(p, tuple) else (p, '')
            print('| %s | %s | %d | %s | %s | %s [%s, %s] | %s [%s, %s] | %s |' % (
                p[0], p[1], o['n'], f(o['median']['m2_to_gs']), f(o['median']['gs_to_m2']),
                f(o['pooled']['m2_to_gs']), f(o['ci95']['m2_to_gs'][0]), f(o['ci95']['m2_to_gs'][1]),
                f(o['pooled']['gs_to_m2']), f(o['ci95']['gs_to_m2'][0]), f(o['ci95']['gs_to_m2'][1]),
                'yes' if o.get('beats_base_every_load') else ''))
        return 0
    import link_gate
    g = link_gate.Rig(argparse.Namespace(peer_min=1.0, bits={'gs': a.bits_gs, 'm2': a.bits_m2}, set=[], set_acc=False,
                                         recal=False, cal0=False, eqarst=False, readapt='none'))
    owner = '/home/pi/gs.owner'
    if os.path.exists(owner):
        print('BUSY: ' + open(owner).read().strip())
        return 4
    open(owner, 'w').write('TASK-5559 %d k4_amp (jelena)\n' % time.time())
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    f = open(a.out, 'a')
    try:
        for ld in range(1, a.loads + 1):
            load = 'l%d_%s' % (ld, time.strftime('%H%M'))
            g.load('m2')
            g.load('gs')
            ok = any(g.peer('m2', 10)['pass'] and g.peer('gs', 10)['pass'] for _ in range(20))
            f.write(json.dumps({'kind': 'load', 'load': load, 'link': ok}) + '\n')
            if not ok:
                print('LOAD %s no link' % load, flush=True)
                continue
            for cyc in range(a.cycles):
                items = POINTS if a.points else PAIRS
                order = items if cyc % 2 == 0 else list(reversed(items))
                for pair in order:
                    fail = []
                    if a.points:
                        flds = point_fields(pair)
                        writes = [(b, ' '.join('%s=%d' % kv for kv in flds[b].items())) for b in ('gs', 'm2')]
                    else:
                        writes = [(b, 'TX_AMP=%d' % amp) for b, amp in zip(('gs', 'm2'), pair)]
                    for b, txt in writes:
                        rc, out = g.sh_rc('fpga-jtag %s run python3 eyescan.py set %s' % (b, txt))
                        bad = set_check(out.strip().splitlines()[-1] if out.strip() else '', rc, txt)
                        if bad:
                            fail.append({'board': b, 'problems': bad})
                    for b in ('gs', 'm2'):
                        for c in readapt_cmds('eqa'):
                            g.jtag(b, c)
                    time.sleep(a.skip)
                    u = Uart()
                    try:
                        m = measure(u, a.secs, 10, 31.25e6, dirs=DIRS)
                    finally:
                        u.close()
                    d = diag_summary(dict(m, windows=[None] + m['windows']), DIRS)   # keep all windows (burst skipped by time)
                    pr = [flds['gs']['TX_AMP'], flds['m2']['TX_AMP']] if a.points else list(pair)
                    rec = {'kind': 'visit', 'load': load, 'cycle': cyc + 1, 'pair': pr, 'point': pair[0] if a.points else None,
                           'fields': flds if a.points else None, 't': time.strftime('%H:%M:%S'),
                           'err': d['err'], 'bits': d['bits'], 'ber': d['ber'], 'sync': d['sync_frac'], 'set_fail': fail,
                           'win': [{k: w[k]['errb'] for k in DIRS} for w in m['windows']]}
                    f.write(json.dumps(rec) + '\n')
                    f.flush()
                    print('V %s c%d %s gs%d m2%d M2->GS %s/%.1e GS->M2 %s/%.1e%s' % (
                        load, cyc + 1, pair[0] if a.points else '', pr[0], pr[1], d['err']['m2_to_gs'], d['bits']['m2_to_gs'] or 0,
                        d['err']['gs_to_m2'], d['bits']['gs_to_m2'] or 0, ' SET_FAIL' if fail else ''), flush=True)
    finally:
        f.close()
        try:
            os.remove(owner)
        except OSError:
            pass
    return 0


if __name__ == '__main__':
    sys.exit(main())
