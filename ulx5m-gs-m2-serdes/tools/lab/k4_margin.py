#!/usr/bin/env python3
"""k4_margin.py - TASK-5559 K4 (CALIBRATION_OPTIONS_20261017_v2 §3.1): TX/RX point per direction, judged by MARGIN.

    cd ~/ulx5m-serdes/tools; python3 lab/k4_margin.py --loads 3 --out ../t5559/k4/k4.jsonl --bits-gs .. --bits-m2 ..
    python3 lab/k4_margin.py --table ../t5559/k4/k4.jsonl

At the operating point (AMP 12) B0' is often error-free for minutes, so BER A/B cannot rank points. Margin = the
smallest SENDER TX_AMP at which the direction is still < --ber (1e-9) over --secs (first 10 s window dropped), stepping
--amps 12,10,8,6,4 with an EQA readapt of both RX before every step (v2 §3.0). A direction that fails stops stepping.
One run = one M2->GS point (m2 TX FFE / gs RX CTLE) PAIRED with one GS->M2 point (gs TX FFE / m2 RX CTLE): the two
directions share no lever, so both margins come from the same AMP sweep (gs AMP and m2 AMP step together).
Every write is readback-checked (link_gate.set_check); a field that does not hold makes the run invalid (SET_FAIL).
Point wins (v2 K4) if its margin is >= 1 AMP step better than the base point of the same load on 3/3 loads."""
import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from link_gate import DIRS, Uart, diag_summary, measure, readapt_cmds, set_check  # noqa: E402

BOTH = ('gs', 'm2')
# (name, m2 fields, gs fields): m2 TX_SEL_POST / RX_AFE_PEAK, gs TX_SEL_POST / RX_AFE_PEAK; base = B0' (POST 5, PEAK 24)
RUNS = [
    ('base', {}, {}),
    ('m2post6_m2peak16', {'TX_SEL_POST': 6, 'RX_AFE_PEAK': 16}, {}),
    ('m2post8_gspost0', {'TX_SEL_POST': 8}, {'TX_SEL_POST': 0}),
    ('m2post10_m2peak12', {'TX_SEL_POST': 10, 'RX_AFE_PEAK': 12}, {}),
    ('m2post12', {'TX_SEL_POST': 12}, {}),
    ('gspeak16', {}, {'RX_AFE_PEAK': 16}),
    ('static', {'RX_EN_EQA': 0, 'RX_AFE_PEAK': 15, 'RX_AFE_GAIN': 8}, {'RX_EN_EQA': 0, 'RX_AFE_PEAK': 15, 'RX_AFE_GAIN': 8}),
]
# which lever of a run belongs to which direction (for the table): M2->GS = m2 TX_* + gs RX_*, GS->M2 = gs TX_* + m2 RX_*
SENDER = {'m2_to_gs': 'm2', 'gs_to_m2': 'gs'}


def lever_label(run, k):
    _, m2f, gsf = run
    snd, rcv = (m2f, gsf) if k == 'm2_to_gs' else (gsf, m2f)
    parts = ['%s.%s=%s' % (SENDER[k], f, v) for f, v in sorted(snd.items()) if f.startswith('TX_')]
    parts += ['%s.%s=%s' % ('gs' if k == 'm2_to_gs' else 'm2', f, v) for f, v in sorted(rcv.items()) if f.startswith('RX_')]
    return ' '.join(parts) or 'base'


def margin(steps, k):
    """steps: [(amp, {'ok': {dir: bool}})] in sweep order. -> smallest amp passing before the first fail (None if 12 fails)."""
    best = None
    for amp, st in steps:
        if not st['ok'].get(k):
            break
        best = amp
    return best


def table(recs, amps=(12, 10, 8, 6, 4)):
    """Per direction and lever: margins per load, steps better than base of the same load, verdict (>= 1 step on all)."""
    idx = {a: i for i, a in enumerate(amps)}
    loads = {}
    for r in recs:
        if r.get('kind') == 'run':
            loads.setdefault(r['load'], {})[r['name']] = r
    out = {}
    for ld, runs in loads.items():
        base = runs.get('base')
        if not base:
            continue
        for name, r in runs.items():
            for k in DIRS:
                lab = r['labels'][k]
                if name != 'base' and lab == 'base':
                    continue                                       # this run does not touch direction k
                m, mb = r['margin'][k], base['margin'][k]
                gain = None if r.get('invalid') else (idx.get(m, -1) - idx.get(mb, -1))   # lower AMP passing = more margin
                o = out.setdefault((k, lab), {'loads': 0, 'margins': [], 'gain_steps': []})
                o['loads'] += 1
                o['margins'].append(m)
                o['gain_steps'].append(gain)
    for (k, lab), o in out.items():
        g = [x for x in o['gain_steps'] if x is not None]
        o['win'] = lab != 'base' and len(g) >= 3 and all(x >= 1 for x in g)
    return out


class Rig:
    def __init__(self, a):
        import link_gate
        self.a = a
        self.g = link_gate.Rig(argparse.Namespace(peer_min=1.0, bits={'gs': a.bits_gs, 'm2': a.bits_m2}, set=[],
                                                  set_acc=False, recal=False, cal0=False, eqarst=False, readapt='none'))
        self.fail = []

    def put(self, board, fields):
        if not fields:
            return []
        txt = ' '.join('%s=%s' % kv for kv in fields.items())
        rc, out = self.g.sh_rc('fpga-jtag %s run python3 eyescan.py set %s' % (board, txt))
        last = out.strip().splitlines()[-1] if out.strip() else ''
        bad = set_check(last, rc, txt)
        if bad:
            self.fail.append({'board': board, 'set': txt, 'problems': bad})
        return [last[-100:]]

    def readapt(self):
        for b in BOTH:
            for c in readapt_cmds('eqa'):
                self.g.jtag(b, c)

    def meas(self):
        time.sleep(self.a.settle)
        u = Uart()
        try:
            return diag_summary(measure(u, self.a.secs, 10, 31.25e6, dirs=DIRS), DIRS)
        finally:
            u.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--table')
    ap.add_argument('--out')
    ap.add_argument('--loads', type=int, default=3)
    ap.add_argument('--secs', type=float, default=30)
    ap.add_argument('--settle', type=float, default=3)
    ap.add_argument('--ber', type=float, default=1e-9)
    ap.add_argument('--amps', default='12,10,8,6,4')
    ap.add_argument('--only', default='', help='comma list of run names')
    ap.add_argument('--bits-gs', default='/home/pi/fpga/t5559/gs_2g5_b0p_s7.bit')
    ap.add_argument('--bits-m2', default='/home/pi/fpga/t5559/m2_2g5_b0p_s2.bit')
    a = ap.parse_args()
    amps = [int(x) for x in a.amps.split(',')]
    if a.table:
        t = table([json.loads(l) for l in open(a.table) if l.strip()], tuple(amps))
        print('| direction | lever | loads | margin (lowest AMP < %g) per load | steps vs base | win |' % a.ber)
        print('|---|---|---|---|---|---|')
        for (k, lab), o in sorted(t.items()):
            print('| %s | %s | %d | %s | %s | %s |' % (k, lab, o['loads'], o['margins'], o['gain_steps'], 'WIN' if o['win'] else ''))
        return 0
    runs = [r for r in RUNS if not a.only or r[0] in a.only.split(',')]
    owner = '/home/pi/gs.owner'
    if os.path.exists(owner):
        print('BUSY: ' + open(owner).read().strip())
        return 4
    open(owner, 'w').write('TASK-5559 %d k4_margin (jelena)\n' % time.time())
    rig = Rig(a)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    f = open(a.out, 'a')
    try:
        for ld in range(1, a.loads + 1):
            load = 'l%d_%s' % (ld, time.strftime('%H%M'))
            rig.g.load('m2')
            rig.g.load('gs')
            ok = False
            for _ in range(20):
                if rig.g.peer('m2', 10)['pass'] and rig.g.peer('gs', 10)['pass']:
                    ok = True
                    break
            orig = {b: rig.g.get(b, ['TX_AMP', 'TX_SEL_POST', 'RX_AFE_PEAK', 'RX_AFE_GAIN', 'RX_EN_EQA']) for b in BOTH}
            f.write(json.dumps({'kind': 'load', 'load': load, 'link': ok, 'orig': orig}) + '\n')
            if not ok:
                print('LOAD %s no link' % load, flush=True)
                continue
            for run in runs:
                name, m2f, gsf = run
                rig.fail = []
                rec = {'kind': 'run', 'load': load, 'name': name, 'm2': m2f, 'gs': gsf,
                       'labels': {k: lever_label(run, k) for k in DIRS}, 't': time.strftime('%H:%M:%S'), 'steps': []}
                rec['act'] = rig.put('m2', m2f) + rig.put('gs', gsf)
                live = set(DIRS)
                for amp in amps:
                    if rig.fail or not live:
                        break
                    rig.put('m2', {'TX_AMP': amp})
                    rig.put('gs', {'TX_AMP': amp})
                    rig.readapt()
                    m = rig.meas()
                    okd = {k: (k in live and m['bits'].get(k, 0) > 0 and m['ber'][k] is not None and m['ber'][k] < a.ber
                               and m['sync_frac'].get(k) not in (None,) and m['sync_frac'][k] > 0.999)
                           for k in DIRS}
                    rec['steps'].append([amp, {'ok': okd, 'ber': m['ber'], 'err': m['err'], 'bits': m['bits'],
                                               'sync': m['sync_frac']}])
                    live = {k for k in live if okd[k]}
                    print('K4 %s %s amp=%d ber=%s ok=%s' % (load, name, amp, m['ber'], okd), flush=True)
                rec['margin'] = {k: margin(rec['steps'], k) for k in DIRS}
                rec['invalid'] = bool(rig.fail)
                rec['set_fail'] = rig.fail
                # back to the load's own values (readback-checked as well), then readapt
                for b in BOTH:
                    rig.put(b, {kk: orig[b][kk] for kk in ('RX_EN_EQA', 'RX_AFE_GAIN', 'RX_AFE_PEAK', 'TX_SEL_POST', 'TX_AMP')})
                rig.readapt()
                rec['restore_fail'] = rig.fail[len(rec['set_fail']):]
                f.write(json.dumps(rec) + '\n')
                f.flush()
                print('RUN %s %s margin=%s invalid=%s' % (load, name, rec['margin'], rec['invalid']), flush=True)
    finally:
        f.close()
        try:
            os.remove(owner)
        except OSError:
            pass
    return 0


if __name__ == '__main__':
    sys.exit(main())
