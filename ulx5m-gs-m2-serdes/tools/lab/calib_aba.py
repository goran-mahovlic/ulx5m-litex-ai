#!/usr/bin/env python3
"""calib_aba.py - TASK-5542 (uputa #347): CALIBRATION_REVIEW_20261016 §3 K4-K9 as A/B/A points on the same load.

    cd ~/ulx5m-serdes/tools; python3 lab/calib_aba.py --loads 3 --secs 45 --out ../t5542/calib/run1.jsonl [--only K4,K5]
    python3 lab/calib_aba.py --table ../t5542/calib/run1.jsonl          # ratios per point, verdict per K rule

Per load: -r m2 then gs (the *_auto bits = PROFILE 1 + TX_AMP 12), wait PEER 10/10 both, then A0, B1, A1, B2, A2, ...
Each state is measured from the gs UART (deltas only, both directions, link_gate.measure) for --secs after a 3 s settle.
B = one change (writes on gs, m2 or both); after B the change is undone (revert writes, or 'restore' for a TAPW pin)
before the next A. The point's ratio = geometric mean of the A before and after / B, per direction (> 1 = B better).
Verdict (§3): win if the median over loads of the summed BER ratio >= 2 and neither direction's median ratio < 0.5.
K7 pins the worse receiver of A0 (TAPW is a per-RX point); K8 changes the EQA loop speed and re-adapts with a DFE
reset (L1) in A and B alike, so the lottery of the reset is in both."""
import argparse
import json
import math
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from link_gate import DIRS, PAYLOAD_BITS, Uart, measure, sum_dir, bad_rx, readapt_cmds  # noqa: E402

BOTH = ('gs', 'm2')
# (K, name, who, B command). who: '*' both boards, 'rx' the worse receiver of A0 ('both' -> both). The revert is
# automatic: the fields a 'F=v' command touches are read before B and written back after it (plus 'recal' if B had
# one); a 'freeze' is undone by 'restore'. So A is always the load's own adapted state of the bits in use.
PLAN = [
    ('K4', 'amp8', '*', 'TX_AMP=8'), ('K4', 'amp10', '*', 'TX_AMP=10'),
    ('K4', 'amp14', '*', 'TX_AMP=14'), ('K4', 'amp16', '*', 'TX_AMP=16'),
    ('K5', 'ffe_q0', '*', 'TX_SEL_PRE=0 TX_SEL_POST=0'), ('K5', 'post3', '*', 'TX_SEL_POST=3'),
    ('K5', 'post8', '*', 'TX_SEL_POST=8'), ('K5', 'pre0', '*', 'TX_SEL_PRE=0'), ('K5', 'pre3', '*', 'TX_SEL_PRE=3'),
    ('K6', 'gain1', '*', 'RX_AFE_GAIN=1'), ('K6', 'peak16', '*', 'RX_AFE_PEAK=16'), ('K6', 'peak31', '*', 'RX_AFE_PEAK=31'),
    ('K7', 'tapw-2', 'rx', 'freeze RX_TAPW=-2'), ('K7', 'tapw0', 'rx', 'freeze RX_TAPW=0'),
    ('K7', 'tapw1', 'rx', 'freeze RX_TAPW=1'), ('K7', 'tapw2', 'rx', 'freeze RX_TAPW=2'),
    ('K7', 'tapw3', 'rx', 'freeze RX_TAPW=3'),
    ('K8', 'eqa_off0', '*', 'RX_EQA_CKP_OFFSET=0;eqarst'), ('K8', 'eqa_lfhf83', '*', 'RX_EQA_CKP_LF=0x83 RX_EQA_CKP_HF=0x83;eqarst'),
    ('K8', 'eqa_ctrl', '*', 'eqarst'),
    ('K9', 'ckp1e', '*', 'RX_CDR_CKP=0x1E'), ('K9', 'ckp7e', '*', 'RX_CDR_CKP=0x7E'), ('K9', 'trans16', '*', 'RX_CDR_TRANS_TH=16'),
    # K12 (new, TASK-5542): termination calibration code. A JTAG recal (TX/RX_CALIB_EN strobe) leaves CAL 9/7 that
    # survives -r (CFGRST) and costs ~x100; power-up state is CAL 0/0. OVR=1 + VAL forces the code.
    ('K12', 'cal0', '*', 'RX_CALIB_OVR=1 RX_CALIB_VAL=0 TX_CALIB_OVR=1 TX_CALIB_VAL=0'),
    ('K12', 'rxcal0', '*', 'RX_CALIB_OVR=1 RX_CALIB_VAL=0'),
    ('K12', 'txcal0', '*', 'TX_CALIB_OVR=1 TX_CALIB_VAL=0'),
    # with --base CAL0 (forced 0/0) the sweep is relative to code 0
    ('K12', 'rxval1', '*', 'RX_CALIB_VAL=1'), ('K12', 'rxval2', '*', 'RX_CALIB_VAL=2'),
    ('K12', 'rxval4', '*', 'RX_CALIB_VAL=4'), ('K12', 'txval2', '*', 'TX_CALIB_VAL=2'),
    ('K12', 'txval4', '*', 'TX_CALIB_VAL=4'),
    # TASK-5559 K3 (CALIBRATION_OPTIONS_20261017_v2 §3.1): is the floor crosstalk of the board's own TX? Idle one TX and
    # read the OTHER direction (gs idle -> M2->GS; the idled direction is dead in B by design). Then 2x2 TX_AMP 12/16.
    ('K3', 'gs_txidle', 'gs', 'TX_ELEC_IDLE_OVR=1 TX_ELEC_IDLE=1'), ('K3', 'm2_txidle', 'm2', 'TX_ELEC_IDLE_OVR=1 TX_ELEC_IDLE=1'),
    ('K3', 'amp_g16', 'gs', 'TX_AMP=16'), ('K3', 'amp_m16', 'm2', 'TX_AMP=16'), ('K3', 'amp_both16', '*', 'TX_AMP=16'),
]
CAL0 = 'RX_CALIB_OVR=1 RX_CALIB_VAL=0 TX_CALIB_OVR=1 TX_CALIB_VAL=0'
# DFE (EQA) reset only - NOT eyescan 'recal', which also strobes TX/RX_CALIB_EN (that is what left CAL 9/7)
EQARST = ['set RX_EQA_RESET_OVR=1 RX_EQA_RESET=1', 'set RX_EQA_RESET_OVR=0 RX_EQA_RESET=0']
POINT_FIELDS = ['RX_CDR_LOCKED', 'RX_EQA_LOCKED', 'RX_TH_MON', 'RX_EQA_TAPW', 'RX_OFFSET']
CAL_FIELDS = ['RX_CALIB_CAL', 'TX_CALIB_CAL', 'RX_CALIB_OVR', 'RX_CALIB_VAL', 'TX_CALIB_OVR', 'TX_CALIB_VAL']


def boards(who, rx):
    if who in BOTH:
        return (who,)
    if who == 'rx' and rx != 'both':
        return (rx,)
    return BOTH


def fields_of(cmd):
    """Field names written by the 'F=v' parts of a command."""
    out = []
    for part in cmd.split(';'):
        w = part.split()
        if w and w[0] not in ('freeze', 'restore', 'recal', 'eqarst'):
            out += [x.split('=')[0] for x in w if '=' in x]
    return out


def revert_cmd(cmd, orig):
    """Undo of a B command: the original field values (+ recal if B had one), or restore after a freeze."""
    if cmd.split()[0] == 'freeze':
        return 'restore'
    parts = []
    if orig:
        parts.append(' '.join('%s=%s' % kv for kv in orig.items()))
    for x in ('recal', 'eqarst'):
        if x in cmd.split(';'):
            parts.append(x)
    return ';'.join(parts)


def commands(cmd):
    """'F=1 G=2;recal' -> ['set F=1 G=2', 'recal']; 'freeze ...'/'restore' pass through."""
    out = []
    for part in cmd.split(';'):
        part = part.strip()
        if not part:
            continue
        if part == 'eqarst':
            out += EQARST
            continue
        out.append(part if part.split()[0] in ('freeze', 'restore', 'recal') else 'set ' + part)
    return out


def parse_steps(spec):
    """'name=cmd | name=cmd' (cmd as in PLAN; '-' = measure only) -> [(name, cmd)]."""
    out = []
    for part in spec.split('|'):
        part = part.strip()
        if part:
            name, cmd = part.split('=', 1) if '=' in part.split()[0] else (part, '-')
            out.append((name.strip(), cmd.strip()))
    return out


def gmean(xs):
    xs = [x for x in xs if x is not None]
    return math.exp(sum(math.log(x) for x in xs) / len(xs)) if xs else None


def ber_of(m, k, floor_bits=True):
    """BER of a state; 0 errors -> 0.5 / bits (half an error) so that a ratio stays finite."""
    if not m or not m['bits'].get(k):
        return None
    e = m['err'][k]
    return (e if e else 0.5) / float(m['bits'][k])


def point_ratios(rows):
    """rows of one load in order (kind A / B). -> {name: {dir: A/B ratio, 'sum': ratio of summed BER}}."""
    out = {}
    for i, r in enumerate(rows):
        if r['kind'] != 'B':
            continue
        a_prev = next((x for x in reversed(rows[:i]) if x['kind'] == 'A'), None)
        a_next = next((x for x in rows[i + 1:] if x['kind'] == 'A'), None)
        rr = {}
        for k in DIRS:
            a = gmean([ber_of(a_prev, k), ber_of(a_next, k)])
            b = ber_of(r, k)
            rr[k] = a / b if a and b else None
        sa = gmean([sum(ber_of(x, k) or 0 for k in DIRS) for x in (a_prev, a_next) if x])
        sb = sum(ber_of(r, k) or 0 for k in DIRS)
        rr['sum'] = sa / sb if sa and sb else None
        out[r['name']] = rr
    return out


def verdict(ratios, min_gain=2.0, max_loss=0.5):
    """ratios: list over loads of {dir: r, 'sum': r}. -> (verdict, medians)."""
    med = {}
    for k in DIRS + ('sum',):
        v = sorted(x[k] for x in ratios if x.get(k) is not None)
        med[k] = v[len(v) // 2] if len(v) % 2 else (math.sqrt(v[len(v) // 2 - 1] * v[len(v) // 2]) if v else None)
    if med['sum'] is None:
        return 'NO DATA', med
    if med['sum'] >= min_gain and all(med[k] is None or med[k] >= max_loss for k in DIRS):
        return 'WIN', med
    if med['sum'] <= 1.0 / min_gain:
        return 'WORSE', med
    return 'NEUTRAL', med


def table(path, metric='errb'):
    """metric errb = bit errors, errw = bad words (error events; a K28.5 hit is 1 word but 40 'bit errors')."""
    rows = [json.loads(l) for l in open(path) if l.strip()]
    if metric != 'errb':
        rows = [dict(r, err=r[metric]) if metric in r else r for r in rows]
    loads = {}
    for r in rows:
        if r.get('kind') in ('A', 'B'):
            loads.setdefault(r['load'], []).append(r)
    per = {}
    for ld, rs in loads.items():
        for name, rr in point_ratios(rs).items():
            per.setdefault(name, []).append(rr)
    kof = {p[1]: p[0] for p in PLAN}
    L = ['| K | točka | učitavanja | M2→GS A/B medijan | GS→M2 A/B medijan | zbroj A/B medijan | po učitavanju (zbroj) | sud |',
         '|---|---|---|---|---|---|---|---|']
    res = {}
    for name in [p[1] for p in PLAN if p[1] in per]:
        v, med = verdict(per[name])
        res[name] = (v, med)
        f = lambda x: '×%.2g' % x if x is not None else '—'  # noqa: E731
        L.append('| %s | %s | %d | %s | %s | %s | %s | %s |' % (
            kof[name], name, len(per[name]), f(med['m2_to_gs']), f(med['gs_to_m2']), f(med['sum']),
            ' '.join(f(x['sum']) for x in per[name]), v))
    A = [r for r in rows if r.get('kind') == 'A']
    L += ['', 'Referenca A po učitavanju (medijan BER M2→GS / GS→M2): ' + '; '.join(
        '%s %.1e / %.1e' % (ld, sorted(ber_of(x, 'm2_to_gs') or 0 for x in A if x['load'] == ld)[len([x for x in A if x['load'] == ld]) // 2],
                            sorted(ber_of(x, 'gs_to_m2') or 0 for x in A if x['load'] == ld)[len([x for x in A if x['load'] == ld]) // 2])
        for ld in loads)]
    return '\n'.join(L), res


# ------------------------------------------------------------------ rig
class Rig:
    def __init__(self, a):
        import link_gate
        self.a = a
        self.g = link_gate.Rig(argparse.Namespace(peer_min=1.0, bits={'gs': a.bits_gs, 'm2': a.bits_m2},
                                                  set=[], set_acc=False, recal=False, cal0=False, eqarst=False))

    def state(self, kind, name, load, f):
        time.sleep(self.a.settle)
        u = Uart()
        try:
            for _ in range(2):
                u.next_line()
            m = measure(u, self.a.secs, 10, 31.25e6)
        finally:
            u.close()
        r = {'kind': kind, 'name': name, 'load': load, 't': time.strftime('%H:%M:%S'), 'status': m['status'],
             'restart': m['restart'], 'secs': round(m['secs'], 1),
             'err': {k: sum_dir(m['windows'], k)['errb'] for k in DIRS},
             'errw': {k: sum_dir(m['windows'], k)['errw'] for k in DIRS},
             'code': {k: sum_dir(m['windows'], k)['code'] for k in DIRS},
             'bits': {k: sum_dir(m['windows'], k)['words'] * PAYLOAD_BITS for k in DIRS},
             'dloss': {k: sum_dir(m['windows'], k)['dloss'] for k in DIRS},
             'win': [{k: w[k]['errb'] for k in DIRS} for w in m['windows']]}
        if self.a.points:
            r['pt'] = {b: self.g.get(b, POINT_FIELDS) for b in BOTH}
        f.write(json.dumps(r) + '\n')
        f.flush()
        print('%s %-14s %s M2->GS %s/%.2e GS->M2 %s/%.2e %s' % (kind, name, load, r['err']['m2_to_gs'],
              r['bits']['m2_to_gs'], r['err']['gs_to_m2'], r['bits']['gs_to_m2'], m['status']), flush=True)
        return r

    def run_cmd(self, b, cmd):
        return ['%s:%s' % (b, self.g.jtag(b, c)[-120:]) for c in commands(cmd)]

    def readapt(self):
        """TASK-5559: 0x2B reset (--readapt level) on both RX, so A and B are both freshly adapted (v1 §1.2)."""
        return [] if self.a.readapt == 'none' else \
            ['%s:%s' % (b, self.g.jtag(b, c)[-60:]) for b in BOTH for c in readapt_cmds(self.a.readapt)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--table')
    ap.add_argument('--metric', choices=('errb', 'errw', 'code'), default='errb')
    ap.add_argument('--out')
    ap.add_argument('--loads', type=int, default=3)
    ap.add_argument('--secs', type=float, default=45)
    ap.add_argument('--settle', type=float, default=3)
    ap.add_argument('--only', default='', help='comma list of K groups or point names')
    ap.add_argument('--points', action='store_true', help='read TH_MON/TAPW/OFFSET after every state (+~10 s)')
    ap.add_argument('--steps', default='', help="'name=cmd|name=cmd' on both boards, no revert, after one load "
                                                "(each step measured; --read fields read twice after it)")
    ap.add_argument('--read', default='RX_EN_EQA RX_EQA_RESET_OVR RX_EQA_RESET RX_EQA_LOCKED RX_TH_MON RX_EQA_TAPW RX_OFFSET')
    ap.add_argument('--base', default='', help="fields written on both boards after every load ('F=v ...'), part of A; "
                                             "'cal0' = %s" % CAL0)
    ap.add_argument('--readapt', choices=('none', 'eqa', 'cdr', 'rx', 'pma'), default='none',
                    help='TASK-5559: this 0x2B reset on both RX after the base, after every B change and every revert')
    ap.add_argument('--bits-gs', default='/home/pi/fpga/gs_2g5_auto.bit')
    ap.add_argument('--bits-m2', default='/home/pi/fpga/m2_2g5_auto.bit')
    a = ap.parse_args()
    if a.table:
        md, _ = table(a.table, a.metric)
        print(md)
        return 0
    only = set(x for x in a.only.split(',') if x)
    plan = [p for p in PLAN if not only or p[0] in only or p[1] in only]
    if a.base == 'cal0':
        a.base = CAL0
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    owner = '/home/pi/gs.owner'
    if os.path.exists(owner):
        print('BUSY: ' + open(owner).read().strip())
        return 4
    open(owner, 'w').write('TASK-5542 %d calib_aba (jelena)\n' % time.time())
    rig = Rig(a)
    f = open(a.out, 'a')
    try:
        for ld in range(1, a.loads + 1):
            load = 'l%d_%s' % (ld, time.strftime('%H%M'))
            rig.g.load('m2')
            rig.g.load('gs')
            t0, ok = time.time(), False
            for _ in range(20):
                if rig.g.peer('m2', 10)['pass'] and rig.g.peer('gs', 10)['pass']:
                    ok = True
                    break
            base = [x for bd in BOTH for x in rig.run_cmd(bd, a.base)] if a.base else []
            h = {b: rig.g.get(b, ['PLL_LOCKED', 'PLL_CAP_FT'] + POINT_FIELDS + CAL_FIELDS + ['TX_AMP']) for b in BOTH}
            f.write(json.dumps({'kind': 'load', 'load': load, 'link': ok, 't_link_s': round(time.time() - t0, 1),
                                'health': h, 'base': base}) + '\n')
            if not ok:
                print('LOAD %s no link' % load, flush=True)
                continue
            if a.steps:
                for name, cmd in parse_steps(a.steps):
                    act = [] if cmd == '-' else [x for bd in BOTH for x in rig.run_cmd(bd, cmd)]
                    rd = {bd: [rig.g.get(bd, a.read.split()), rig.g.get(bd, a.read.split())] for bd in BOTH}
                    f.write(json.dumps({'kind': 'step', 'load': load, 'name': name, 'cmd': cmd, 'act': act, 'read': rd}) + '\n')
                    print('STEP %s %s read=%s' % (name, cmd, {b: v[1] for b, v in rd.items()}), flush=True)
                    rig.state('S', name, load, f)
                continue
            rig.readapt()
            a0 = rig.state('A', 'A0', load, f)
            rx = bad_rx(a0['err'])
            for i, (K, name, who, cmd) in enumerate(plan):
                act, undo = [], {}
                for bd in boards(who, rx):
                    fl = fields_of(cmd)
                    undo[bd] = revert_cmd(cmd, rig.g.get(bd, fl) if fl else {})
                    act += rig.run_cmd(bd, cmd)
                act += rig.readapt()
                f.write(json.dumps({'kind': 'act', 'load': load, 'name': name, 'act': act, 'undo': undo}) + '\n')
                rig.state('B', name, load, f)
                for bd, u in undo.items():
                    rig.run_cmd(bd, u)
                rig.readapt()
                rig.state('A', 'A%d' % (i + 1), load, f)
            print('LOAD %s done rx=%s' % (load, rx), flush=True)
    finally:
        f.close()
        try:
            os.remove(owner)
        except OSError:
            pass
    return 0


if __name__ == '__main__':
    sys.exit(main())
