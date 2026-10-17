#!/usr/bin/env python3
"""link_gate.py - TASK-5542 link quality gate with automatic re-connect (CALIBRATION_REVIEW_20261016.md §4).

    cd ~/ulx5m-serdes/tools; python3 lab/link_gate.py --run gate_a --out ../t5542/gate [--soak 1800] [--ladder L3]
    python3 lab/link_gate.py --rate 5g --set TX_AMP=12 --run g5_a --out ../t5542/gate    # 5 G: GS->M2 + PEER only

Per attempt (up to --max-attempts, default 10): re-connect at the ladder level (L3 = -r m2 then gs, L2rx/L2tx = -r of
one board, L1 = DFE reset / L1b = whole-RX reset of the bad receiver over the regfile, L0 = nothing), wait for PEER
10/10 both ways (t_link), health of both boards (PLL/CDR/EQA lock, FT_OF/UF, adapted point) + PEER 200, settle,
then from the gs UART (cumulative counters, deltas only, never 'Z'):
    Q  10 s: <= 8 bit errors per direction, dloss 0, synced (early exit as soon as > 8)
    C  60 s: 10 s windows, <= 60 errors per direction, no window > 20 (burst), dloss 0, synced share >= 0.999999
UART silent > 60 s = UNDECIDED (not counted, next try L0, at most 3). One JSON line per attempt in <out>/<run>.jsonl.
After a PASS an optional soak (--soak s) logs a snapshot every 10 s in ber_long format (<run>_soak.jsonl) for
ber_windows.py (first window dropped, Poisson 95 %); bursts = 10 s windows > 20 errors.
5 G: the gs checker of these bits cannot follow 62.5 M words/s, so verdicts use GS->M2 only (m2 checker), M2->GS
is judged by PEER 1000 (CALIBRATION_REVIEW §5.1 P5-3 (a)); Q <= 16, C <= 120 (twice the bits per second).
No power cycle, no flash write: only fpga-jtag ... -r and regfile writes."""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ber_windows import poisson_ci  # noqa: E402

M32, M48 = 0xFFFFFFFF, (1 << 48) - 1
DIRS = ('m2_to_gs', 'gs_to_m2')
KEYS = {'m2_to_gs': ('words', 'errb', 'loss', 'synced', 'rcnt', 'errw', 'code'),       # gs checker; sender m2
        'gs_to_m2': ('pwords', 'perrb', 'ploss', 'psynced', 'tcnt', 'perrw', 'pcode')}  # m2 checker; sender gs
# errb over-counts: a word whose K28.5 is hit by one line error is not aligned and counts 40 bit errors
# (ber_link.v d1 <= wv_g ? diff_g : {40{1'b1}}). errw (bad words) counts error EVENTS; --metric errw judges by it.
PAYLOAD_BITS = 40
EOF = object()
# power-up termination state (CAL 0/0) forced over the override: a JTAG recal leaves CAL 9/7 that -r does not clear
CAL0 = 'RX_CALIB_OVR=1 RX_CALIB_VAL=0 TX_CALIB_OVR=1 TX_CALIB_VAL=0'
# 0x2B reset strobes (corrected map, prjpeppercorn PR #20): OVR R/W + W/C pulse, then release. W/C reads back 0, so
# these writes are never readback-checked (CALIBRATION_OPTIONS_20261017 §1.1); their effect is checked by BER (K1-c).
READAPT = {'eqa': 'RX_EQA_RESET', 'cdr': 'RX_CDR_RESET', 'rx': 'RX_RESET', 'pma': 'RX_PMA_RESET'}


def readapt_cmds(level):
    if level in (None, 'none'):
        return []
    f = READAPT[level]
    return ['set %s_OVR=1 %s=1' % (f, f), 'set %s_OVR=0 %s=0' % (f, f)]


EQARST = readapt_cmds('eqa')
RAW = ('0x01', '0x03', '0x04', '0x2B')      # TASK-5559 K0-b: reset times/WAIT_CDR_LOCK, CKP_LF/HF, CKP_OFFSET/EN_EQA, resets


def set_check(last, rc, fields):
    """TASK-5559 K0-b: problems of one 'eyescan.py set' (its last output line + exit code) against the asked
    'F=v ...' (values may be hex). [] = every field reads back what was written."""
    got = {}
    for kv in last.split():
        if '=' in kv and not kv.startswith('board='):
            k, v = kv.split('=', 1)
            try:
                got[k] = int(v, 0)
            except ValueError:
                got[k] = v
    bad = []
    for kv in fields.split():
        k, v = kv.split('=', 1)
        if got.get(k) != int(v, 0):
            bad.append('%s want %d got %s' % (k, int(v, 0), got.get(k)))
    if not bad and rc:
        bad.append('exit %d' % rc)
    return bad


def parse_raw(last):
    """'board=gs RAW 0x01=0063 ...' -> {'0x01': 0x63, ...} (hex words)."""
    return {k: int(v, 16) for k, v in (kv.split('=', 1) for kv in last.split() if kv.startswith('0x') and '=' in kv)}
# TASK-5542 recipe R1 (K5 + K8 winners over 3 loads, on top of CAL0): TX pre-cursor off, slower EQA offset loop
R1 = ['TX_SEL_PRE=0', 'RX_EQA_CKP_OFFSET=0']


# ------------------------------------------------------------------ window accounting (pure, tested)
def fabric_dt(a, b):
    """Seconds between two lines on the 25 MHz fabric clock; the host time picks the 171.8 s wrap count."""
    mod = (b['t25'] - a['t25']) & M32
    wraps = round(((b['_t'] - a['_t']) * 25e6 - mod) / 2 ** 32)
    return (mod + max(wraps, 0) * 2 ** 32) / 25e6


def plausible(a, b, wps):
    """b can follow a: both word counters advanced by 0..1.05 x the line rate (+1000), errors <= 40 per word."""
    lim = 1.05 * fabric_dt(a, b) * wps + 1000
    for k in DIRS:
        wk, ek = KEYS[k][0], KEYS[k][1]
        dw, de = (b[wk] - a[wk]) & M48, (b[ek] - a[ek]) & M32
        if dw > lim or de > 40 * dw + 40:
            return False
    return True


def window(a, b, syncmin):
    """Deltas a -> b per direction (words, bit errors, loss mod 32, expected words from the sender clock count)."""
    dt = fabric_dt(a, b)
    r = {'t0': a['_t'], 't1': b['_t'], 'secs': dt, 'syncmin': syncmin}
    for k in DIRS:
        wk, ek, lk, _, ck, ewk, ck2 = KEYS[k]
        sender = ((b[ck] - a[ck]) & M32) if dt < 130 else None
        r[k] = {'words': (b[wk] - a[wk]) & M48, 'errb': (b[ek] - a[ek]) & M32, 'dloss': (b[lk] - a[lk]) & 0x1F,
                'expected': sender}
        if ewk in a and ewk in b:
            r[k]['errw'] = (b[ewk] - a[ewk]) & M32
            r[k]['code'] = (b[ck2] - a[ck2]) & M32
    return r


def sum_dir(ws, k):
    return {'words': sum(w[k]['words'] for w in ws), 'errb': sum(w[k]['errb'] for w in ws),
            'dloss': sum(w[k]['dloss'] for w in ws), 'errw': sum(w[k].get('errw', 0) for w in ws),
            'code': sum(w[k].get('code', 0) for w in ws)}


def sync_frac(ws, k):
    """Words counted / words sent over windows whose sender count is known (None if none)."""
    e = [w for w in ws if w[k].get('expected')]
    s = sum(w[k]['expected'] for w in e)
    return (sum(w[k]['words'] for w in e) / float(s)) if s else None


def measure(src, secs, win, wps, early_max=None, silence=60, restart_n=5, dirs=DIRS, on_edge=None, metric='errb'):
    """Read status lines from src.next_line() (a parsed line, None = 1 s without a line, EOF) for secs of host time
    from the first accepted line. Windows of >= win s between accepted lines. status: done | early (errors > early_max
    in a judged direction) | nouart (silent > silence s) | eof. A line that is not plausible after the anchor is
    skipped (corrupted back channel); restart_n mutually plausible rejects in a row = a checker restarted."""
    r = {'status': 'eof', 'windows': [], 'rejected': 0, 'restart': False, 'secs': 0.0, 'lines': 0}
    start = anchor = wstart = None
    syncmin, quiet, rej = 1, 0, []
    while True:
        l = src.next_line()
        if l is EOF:
            break
        if l is None:
            quiet += 1
            if quiet > silence:
                r['status'] = 'nouart'
                break
            continue
        r['lines'] += 1
        if anchor is None:
            start = anchor = wstart = l
            syncmin = min(l['synced'], l['psynced'])
            quiet = 0
            if on_edge:
                on_edge(l)
            continue
        if not plausible(anchor, l, wps):
            r['rejected'] += 1
            rej = rej + [l] if (not rej or plausible(rej[-1], l, wps)) else [l]
            if len(rej) >= restart_n:
                r['restart'] = True
                anchor = wstart = rej[-1]
                rej = []
            continue
        rej, quiet, anchor = [], 0, l
        syncmin = min(syncmin, l['synced'], l['psynced'])
        r['secs'] = l['_t'] - start['_t']
        done = r['secs'] >= secs
        if l['_t'] - wstart['_t'] >= win or done:
            r['windows'].append(window(wstart, l, syncmin))
            wstart, syncmin = l, min(l['synced'], l['psynced'])
            if on_edge:
                on_edge(l)
        if early_max is not None:
            open_w = [window(wstart, l, syncmin)] if wstart is not l else []
            if any(sum_dir(r['windows'] + open_w, k)[metric] > early_max for k in dirs):
                if open_w:
                    r['windows'] += open_w
                r['status'] = 'early'
                break
        if done:
            r['status'] = 'done'
            break
    return r


def _common(r, dirs, metric='errb'):
    err = {k: sum_dir(r['windows'], k)[metric] for k in DIRS}
    bits = {k: sum_dir(r['windows'], k)['words'] * PAYLOAD_BITS for k in DIRS}
    dloss = {k: sum_dir(r['windows'], k)['dloss'] for k in DIRS}
    out = {'status': r['status'], 'secs': round(r.get('secs', 0), 1), 'err': err, 'bits': bits, 'dloss': dloss,
           'rejected': r.get('rejected', 0), 'metric': metric,
           'all': {k: sum_dir(r['windows'], k) for k in DIRS},
           'windows': [{k: w[k]['errb'] for k in DIRS} for w in r['windows']],
           'windows_errw': [{k: w[k].get('errw') for k in DIRS} for w in r['windows']],
           'sync_frac': {k: sync_frac(r['windows'], k) for k in DIRS}}
    if r['status'] == 'nouart':
        out.update(verdict='UNDECIDED', reason='uart silent')
    elif r.get('restart'):
        out.update(verdict='FAIL', reason='checker restart')
    elif not r['windows']:
        out.update(verdict='UNDECIDED', reason='no window')
    return out


def q_verdict(r, max_err, dirs=DIRS, metric='errb'):
    out = _common(r, dirs, metric)
    if 'verdict' in out:
        return out
    bad = [k for k in dirs if out['err'][k] > max_err]
    if r['status'] == 'early' or bad:
        out.update(verdict='FAIL', reason='errors > %d: %s' % (max_err, ','.join(bad)))
    elif any(out['dloss'][k] for k in dirs):
        out.update(verdict='FAIL', reason='loss')
    elif any(w['syncmin'] == 0 for w in r['windows']):
        out.update(verdict='FAIL', reason='not synced')
    else:
        out.update(verdict='PASS', reason=None)
    return out


def c_verdict(r, total_max, win_max, sync_min, dirs=DIRS, metric='errb'):
    out = _common(r, dirs, metric)
    if 'verdict' in out:
        return out
    burst = [k for k in dirs for w in r['windows']
             if w[k].get(metric, 0) > win_max * max(1.0, (w['t1'] - w['t0']) / 10.0)]
    over = [k for k in dirs if out['err'][k] > total_max]
    lowsync = [k for k in dirs if out['sync_frac'][k] is not None and out['sync_frac'][k] < sync_min]
    if burst:
        out.update(verdict='FAIL', reason='burst > %d in a 10 s window: %s' % (win_max, ','.join(sorted(set(burst)))))
    elif over:
        out.update(verdict='FAIL', reason='errors > %d: %s' % (total_max, ','.join(over)))
    elif any(out['dloss'][k] for k in dirs):
        out.update(verdict='FAIL', reason='loss')
    elif lowsync:
        out.update(verdict='FAIL', reason='synced share < %g: %s' % (sync_min, ','.join(lowsync)))
    else:
        out.update(verdict='PASS', reason=None)
    return out


def bursts(ws, per10=20):
    """Indices of windows with more than per10 errors per 10 s (threshold scaled to the window length)."""
    return {k: [i for i, w in enumerate(ws) if w[k]['errb'] > per10 * max(1.0, (w['t1'] - w['t0']) / 10.0)]
            for k in DIRS}


def level_for(n, ladder):
    return ladder[min(n, len(ladder)) - 1]


def bad_rx(err, ratio=4.0):
    """Receiver board of the worse direction (m2->gs is received by gs); 'both' unless one is >= ratio x the other."""
    a, b = err.get('m2_to_gs') or 0, err.get('gs_to_m2') or 0
    if a >= ratio * max(b, 1):
        return 'gs'
    if b >= ratio * max(a, 1):
        return 'm2'
    return 'both'


def peer_parse(last, n, peer_min=1.0):
    """ber_jtag_check last line -> PEER count and pass: its own PASS (all n samples PEER) or, with peer_min < 1
    (5 G gate 5G-1: >= 990/1000), the PEER share."""
    m = re.search(r'PEER (\d+)/(\d+)', last)
    k = int(m.group(1)) if m else 0
    ok = 'PASS' in last or (peer_min < 1.0 and k >= peer_min * n)
    return {'pass': ok, 'peer': k, 'n': n}


def prev_err(prev):
    """Error counts of the previous attempt (Q, else C; {} if it failed before measuring)."""
    prev = prev or {}
    return (prev.get('q') or {}).get('err') or (prev.get('c') or {}).get('err') or {}


def peer_err(prev):
    """PEER misses of the previous attempt as error counts per direction (PEER read on gs = what gs receives =
    m2_to_gs); {} without PEER data. TASK-5550: 5 G attempts fail on health before Q, this still names the bad RX."""
    p = (prev or {}).get('peer') or {}
    if 'gs' not in p or 'm2' not in p:
        return {}
    return {'m2_to_gs': p['gs']['n'] - p['gs']['peer'], 'gs_to_m2': p['m2']['n'] - p['m2']['peer']}


def rx_err(prev):
    """Errors that pick the bad receiver for L2rx/L2tx/L1: Q/C counts, else PEER misses."""
    return prev_err(prev) or peer_err(prev)


def ci95(k):
    """95 % interval on a Poisson count: exact Garwood up to 1000, normal above (5 G counts reach 1e8)."""
    if k <= 1000:
        return poisson_ci(k)
    d = 1.96 * k ** 0.5
    return k - d, k + d


def diag_summary(r, dirs):
    """BER per direction from measure() windows with the first one dropped (ber_windows rule), 95 % interval.
    Diagnostic only (an attempt that failed health): never part of a verdict."""
    ws = r['windows'][1:]
    out = {'status': r['status'], 'secs': round(r.get('secs', 0), 1), 'windows_used': len(ws),
           'restart': r.get('restart', False), 'err': {}, 'bits': {}, 'ber': {}, 'ci95': {}, 'sync_frac': {}}
    for k in dirs:
        sd = sum_dir(ws, k)
        bits = sd['words'] * PAYLOAD_BITS
        out['err'][k], out['bits'][k] = sd['errb'], bits
        out['sync_frac'][k] = sync_frac(ws, k)
        if bits:
            lo, hi = ci95(sd['errb'])
            out['ber'][k], out['ci95'][k] = sd['errb'] / float(bits), [lo / bits, hi / bits]
        else:
            out['ber'][k], out['ci95'][k] = None, None
    return out


def gate_loop(attempt, max_attempts=10, max_undecided=3, ladder=('L3',)):
    """attempt(n, level, prev_record) -> record with 'verdict' PASS|FAIL|UNDECIDED. UNDECIDED is not counted and
    is retried with L0 (measure again); max_undecided of them stop the gate (STOP_UART)."""
    recs, n, und, prev = [], 0, 0, None
    while True:
        level = 'L0' if prev is not None and prev['verdict'] == 'UNDECIDED' else level_for(n + 1, list(ladder))
        rec = attempt(n + 1, level, prev)
        recs.append(rec)
        prev = rec
        if rec['verdict'] == 'SET_FAIL':                 # TASK-5559 K0-b: a write did not hold -> the point is invalid
            return recs, {'verdict': 'SET_FAIL', 'attempts': n + 1, 'undecided': und, 'set_fail': rec.get('set_fail')}
        if rec['verdict'] == 'UNDECIDED':
            und += 1
            if und >= max_undecided:
                return recs, {'verdict': 'STOP_UART', 'attempts': n, 'undecided': und}
            continue
        n += 1
        if rec['verdict'] == 'PASS':
            return recs, {'verdict': 'PASS', 'attempts': n, 'undecided': und, 'level': rec['level']}
        if n >= max_attempts:
            return recs, {'verdict': 'GATE_FAILED', 'attempts': n, 'undecided': und}


def stats(runs, recs):
    dec = [r for r in recs if r['verdict'] in ('PASS', 'FAIL')]
    p = [r['attempts'] for r in runs if r['verdict'] == 'PASS']
    return {'runs': len(runs), 'runs_pass': len(p), 'attempts_to_pass': p,
            'attempts_decided': len(dec), 'attempt_pass_frac': (sum(r['verdict'] == 'PASS' for r in dec) / float(len(dec)))
            if dec else None}


# ------------------------------------------------------------------ the rig (Pi: fpga-jtag + gs UART)
HEALTH = ['TX_RESET_DONE', 'RX_RESET_DONE', 'RX_WAIT_CDR_LOCK', 'RX_EN_EQA', 'RX_EQA_CKP_OFFSET', 'PLL_LOCKED', 'PLL_CAP_FT_OF', 'PLL_CAP_FT_UF', 'PLL_CAP_FT', 'RX_CALIB_CAL', 'TX_CALIB_CAL', 'RX_CALIB_OVR',
          'RX_CALIB_VAL', 'TX_CALIB_OVR', 'TX_CALIB_VAL', 'RX_CDR_LOCKED',
          'RX_EQA_LOCKED', 'RX_TH_MON', 'RX_EQA_TAPW', 'RX_OFFSET', 'TX_AMP']


class Uart:
    """Parsed gs status lines; next_line() waits <= 1 s (None), reopens the port after 15 s of silence."""
    def __init__(self):
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
        import ber_mon
        import ber_parse
        self.M, self.parse = ber_mon, ber_parse.parse
        self.s, self.buf, self.q, self.quiet = None, b'', [], 0

    def _open(self):
        if self.s:
            try:
                self.s.close()
            except Exception:
                pass
        try:
            self.s = self.M.serial.Serial(self.M.PORT, 115200, timeout=0.2)
            self.s.reset_input_buffer()
        except Exception:
            self.s = None
        self.buf = b''

    def next_line(self):
        if self.q:
            return self.q.pop(0)
        if self.s is None or self.quiet >= 15:
            self._open()
            self.quiet = 0
        t0 = time.time()
        while time.time() - t0 < 1.0 and self.s is not None:
            try:
                self.buf += self.s.read(512)
            except Exception:
                self.s = None
                break
            while b'\n' in self.buf:
                raw, self.buf = self.buf.split(b'\n', 1)
                d = self.parse(raw.decode('ascii', 'replace'))
                if d:
                    d['_t'] = time.time()
                    self.q.append(d)
            if self.q:
                self.quiet = 0
                return self.q.pop(0)
        if self.s is None:
            time.sleep(1.0)
        self.quiet += 1
        return None

    def close(self):
        if self.s:
            self.s.close()
            self.s = None


class Rig:
    def __init__(self, a):
        self.a, self.tools = a, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')

    def sh(self, cmd, timeout=180):
        return self.sh_rc(cmd, timeout)[1]

    def sh_rc(self, cmd, timeout=180):
        try:
            p = subprocess.run(cmd, shell=True, cwd=self.tools, capture_output=True, text=True, timeout=timeout)
            return p.returncode, p.stdout + p.stderr
        except subprocess.TimeoutExpired:
            return -1, 'TIMEOUT'

    def set_checked(self, board, fields):
        """eyescan set with readback + exit code; problems go to self.set_fail (the attempt becomes SET_FAIL)."""
        rc, out = self.sh_rc('fpga-jtag %s run python3 eyescan.py set %s' % (board, fields))
        last = out.strip().splitlines()[-1] if out.strip() else ''
        bad = set_check(last, rc, fields)
        if bad:
            self.set_fail.append({'board': board, 'set': fields, 'problems': bad, 'line': last[:160]})
        return last

    def raw(self, board):
        return parse_raw(self.jtag(board, 'raw ' + ' '.join(RAW)))

    def wait_tx(self, boards, polls=20):
        """PLL_LOCKED and TX_RESET_DONE on every board (v2 §3.0: readapt only after both TX are up)."""
        for i in range(polls):
            st = {b: self.get(b, ['PLL_LOCKED', 'TX_RESET_DONE']) for b in boards}
            if all(s.get('PLL_LOCKED') == 1 and s.get('TX_RESET_DONE') == 1 for s in st.values()):
                return {'polls': i + 1, 'ok': True}
            time.sleep(0.5)
        return {'polls': polls, 'ok': False, 'state': st}

    def jtag(self, board, args):
        out = self.sh('fpga-jtag %s run python3 eyescan.py %s' % (board, args))
        return out.strip().splitlines()[-1] if out.strip() else ''

    def get(self, board, fields):
        last = self.jtag(board, 'get ' + ' '.join(fields))
        d = {}
        for kv in last.split():
            if '=' in kv and not kv.startswith('board='):
                k, v = kv.split('=', 1)
                try:
                    d[k] = int(v)
                except ValueError:
                    d[k] = v
        return d

    def peer(self, board, n):
        out = self.sh('fpga-jtag %s run python3 ber_jtag_check.py --samples %d' % (board, n))
        last = out.strip().splitlines()[-1] if out.strip() else ''
        return dict(peer_parse(last, n, self.a.peer_min), line=last.split('rx: ')[-1][:80])

    def load(self, board):
        bit = self.a.bits[board]
        return self.sh('fpga-jtag %s %s -r' % (board, bit)).strip().splitlines()[-1:]

    def after_load(self, boards):
        for b in boards:
            if self.a.cal0:
                self.set_checked(b, CAL0)
            if self.a.set_acc:
                self.jtag(b, 'set RX_CDR_SET_ACC_CONFIG=2')
                self.jtag(b, 'set RX_CDR_SET_ACC_CONFIG=0')
            if self.a.set:
                self.set_checked(b, ' '.join(self.a.set))
                if self.a.recal:
                    self.jtag(b, 'recal')
            if self.a.eqarst:                       # re-adapt the DFE with the new loop settings (no CALIB strobe)
                for c in EQARST:
                    self.jtag(b, c)
        if self.a.readapt != 'none':                # TASK-5559: both TX up first, then the K1-c level on both RX
            self.last_wait = self.wait_tx(boards)
            for b in boards:
                for c in readapt_cmds(self.a.readapt):
                    self.jtag(b, c)

    def reconnect(self, level, prev):
        rx = bad_rx(rx_err(prev))
        boards = ['m2', 'gs'] if rx == 'both' else [rx]
        act = {'level': level}
        if level == 'L3':
            act['out'] = [self.load('m2'), self.load('gs')]
            self.after_load(['m2', 'gs'])
        elif level in ('L2rx', 'L2tx'):
            b = boards[0] if level == 'L2rx' else {'gs': 'm2', 'm2': 'gs'}[boards[0]]
            b = 'gs' if rx == 'both' else b
            act.update(board=b, out=self.load(b))
            self.after_load([b])
        elif level in ('L1', 'L1b'):
            act['before'] = {b: self.get(b, ['RX_CDR_LOCKED', 'RX_TH_MON', 'RX_EQA_TAPW', 'RX_OFFSET']) for b in boards}
            # reset over the 0x2B override only; NOT eyescan 'recal' (it strobes TX/RX_CALIB_EN -> sticky CAL 9/7)
            f = 'RX_EQA_RESET' if level == 'L1' else 'RX_RESET'
            act['out'] = {b: [self.jtag(b, 'set %s_OVR=1 %s=1' % (f, f))[:120],
                              self.jtag(b, 'set %s_OVR=0 %s=0' % (f, f))[:120]] for b in boards}
            act['after'] = {b: self.get(b, ['RX_CDR_LOCKED', 'RX_TH_MON', 'RX_EQA_TAPW', 'RX_OFFSET', 'RX_CALIB_CAL'])
                            for b in boards}
        return act

    def attempt(self, n, level, prev):
        a = self.a
        rec = {'run': a.run, 'rate': a.rate, 'attempt': n, 'level': level, 'metric': a.metric,
               't': time.strftime('%Y-%m-%dT%H:%M:%S%z'), 'bits': a.sha, 'set': a.set}
        t0 = time.time()
        self.set_fail, self.last_wait = [], None
        rec['action'] = self.reconnect(level, prev)
        rec['readapt'] = {'level': a.readapt, 'wait_tx': self.last_wait}
        if self.set_fail:
            rec.update(verdict='SET_FAIL', reason='readback != write', set_fail=self.set_fail, q=None, c=None)
            return rec
        ok, polls = False, 0
        need = int(10 * a.peer_min)                  # 2.5 G 10/10 (as lab39-41), 5 G 9/10
        while polls < a.link_polls:
            polls += 1
            if self.peer('m2', 10)['peer'] >= need and self.peer('gs', 10)['peer'] >= need:
                ok = True
                break
        rec['t_link_s'] = round(time.time() - t0, 1) if ok else None
        rec['link_polls'] = polls
        rec['health'] = {b: self.get(b, HEALTH) for b in ('gs', 'm2')}
        rec['raw'] = {b: self.raw(b) for b in ('gs', 'm2')}
        rec['peer'] = {b: self.peer(b, a.peer_n) for b in ('gs', 'm2')}
        rec['pi'] = self.sh('vcgencmd get_throttled; vcgencmd measure_temp').split()
        prob = []
        for b, h in rec['health'].items():
            for k in ('PLL_LOCKED', 'RX_CDR_LOCKED', 'RX_EQA_LOCKED'):
                if h.get(k) != 1:
                    prob.append('%s %s=%s' % (b, k, h.get(k)))
            for k in ('PLL_CAP_FT_OF', 'PLL_CAP_FT_UF'):
                if h.get(k):
                    prob.append('%s %s' % (b, k))
        for b, p in rec['peer'].items():
            if not p['pass']:
                prob.append('%s PEER %s' % (b, p['line']))
        if not ok:
            prob.append('no link (PEER 10) after %d polls' % polls)
        if prob:
            rec.update(verdict='FAIL', reason='health: ' + '; '.join(prob), q=None, c=None)
            if a.diag_secs:                          # TASK-5550: still a BER for the table (5G-2), not a verdict
                u = Uart()
                try:
                    rec['diag'] = diag_summary(measure(u, a.diag_secs, 10, a.wps, dirs=a.dirs), a.dirs)
                finally:
                    u.close()
            return rec
        time.sleep(a.settle)
        u = Uart()
        try:
            for _ in range(int(a.settle)):          # drop the first lines after link-up (ber_windows skip 1)
                u.next_line()
            q = q_verdict(measure(u, a.q_secs, a.q_secs, a.wps, early_max=a.q_max, dirs=a.dirs, metric=a.metric),
                          a.q_max, a.dirs, a.metric)
            rec['q'] = q
            if q['verdict'] != 'PASS':
                rec.update(verdict=q['verdict'], reason='Q: ' + str(q['reason']), c=None)
                return rec
            c = c_verdict(measure(u, a.c_secs, 10, a.wps, dirs=a.dirs), a.c_max, a.c_win, a.sync_min, a.dirs, a.metric)
            rec['c'] = c
            rec.update(verdict=c['verdict'], reason=None if c['verdict'] == 'PASS' else 'C: ' + str(c['reason']))
        finally:
            u.close()
        return rec

    def soak(self, path):
        f = open(path, 'w')
        t0 = time.time()

        def edge(l):
            d = {k: l[k] for k in ('words', 'errb', 'pwords', 'perrb', 'loss', 'ploss', 'synced', 'psynced', 't25',
                                   'tcnt', 'rcnt', 'errw', 'perrw', 'code', 'pcode')}
            d.update(t=round(l['_t'] - t0, 1), kind='snap' if f.tell() else 'baseline')
            f.write(json.dumps(d) + '\n')
            f.flush()
        u = Uart()
        try:
            r = measure(u, self.a.soak, 10, self.a.wps, silence=600, dirs=self.a.dirs, on_edge=edge)
        finally:
            u.close()
        ws = r['windows']
        t = {'kind': 'total', 'status': r['status'], 'secs': round(r.get('secs', 0), 1), 'restart': r['restart'],
             'rejected': r['rejected'], 'bursts': bursts(ws[1:], self.a.c_win),
             'kept': {k: sum_dir(ws[1:], k) for k in DIRS}, 'sync_frac': {k: sync_frac(ws[1:], k) for k in DIRS}}
        f.write(json.dumps(t) + '\n')
        f.close()
        return t


RATES = {'2g5': {'wps': 31.25e6, 'q_max': 8, 'c_max': 60, 'c_win': 20, 'peer_n': 200, 'peer_min': 1.0, 'dirs': DIRS,
                 'bits': {'gs': '/home/pi/fpga/gs_2g5_auto.bit', 'm2': '/home/pi/fpga/m2_2g5_auto.bit'}},
         '5g': {'wps': 62.5e6, 'q_max': 16, 'c_max': 120, 'c_win': 40, 'peer_n': 1000, 'peer_min': 0.99, 'dirs': ('gs_to_m2',),
                'bits': {'gs': '/home/pi/fpga/gs_5g.bit', 'm2': '/home/pi/fpga/m2_5g.bit'}}}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--run', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--rate', choices=RATES, default='2g5')
    ap.add_argument('--max-attempts', type=int, default=10)
    ap.add_argument('--ladder', default='L3', help='comma list, attempt n uses item n (last repeats)')
    ap.add_argument('--soak', type=int, default=0)
    ap.add_argument('--set', nargs='*', default=[], help='regfile fields written on both boards after each load')
    ap.add_argument('--recal', action='store_true', help='eyescan recal after --set (strobes CALIB: avoid)')
    ap.add_argument('--eqarst', action='store_true', help='DFE reset (0x2B override) after --set, no CALIB strobe')
    ap.add_argument('--r1', action='store_true', help='recipe R1 = --cal0 --set %s --eqarst' % ' '.join(R1))
    ap.add_argument('--readapt', choices=('none',) + tuple(READAPT), default='none',
                    help='after every reconnect: wait PLL+TX done on the loaded boards, then this 0x2B reset on them')
    ap.add_argument('--cal0', action='store_true', help='force termination code 0/0 after every load (K12): ' + CAL0)
    ap.add_argument('--set-acc', action='store_true', help='RX_CDR_SET_ACC_CONFIG 2->0 after a load (old bits, CKI != 0)')
    ap.add_argument('--bits-gs')
    ap.add_argument('--bits-m2')
    ap.add_argument('--settle', type=float, default=5)
    ap.add_argument('--q-secs', type=float, default=10)
    ap.add_argument('--c-secs', type=float, default=60)
    ap.add_argument('--sync-min', type=float, default=0.999999)
    ap.add_argument('--link-polls', type=int, default=20)
    ap.add_argument('--diag-secs', type=float, default=0,
                    help='on a health FAIL still measure this long (10 s windows, first dropped) -> rec diag BER')
    ap.add_argument('--metric', choices=('errb', 'errw'), default='errb',
                    help='errb = bit errors (CALIBRATION_REVIEW §4.2), errw = bad words (error events)')
    a = ap.parse_args()
    for k, v in RATES[a.rate].items():
        setattr(a, k, v)
    if a.r1:
        a.cal0, a.eqarst, a.set = True, True, list(R1) + list(a.set)
    a.bits = dict(a.bits)
    if a.bits_gs:
        a.bits['gs'] = a.bits_gs
    if a.bits_m2:
        a.bits['m2'] = a.bits_m2
    a.sha = {b: hashlib.sha256(open(p, 'rb').read()).hexdigest()[:8] for b, p in a.bits.items()}
    os.makedirs(a.out, exist_ok=True)
    path = os.path.join(a.out, a.run + '.jsonl')
    owner = '/home/pi/gs.owner'
    if os.path.exists(owner) and 'link_gate' not in open(owner).read():
        print('BUSY: ' + open(owner).read().strip())
        return 4
    open(owner, 'w').write('TASK-5542 %d link_gate %s (jelena)\n' % (time.time(), a.run))
    rig = Rig(a)
    f = open(path, 'a')

    def attempt(n, level, prev):
        rec = rig.attempt(n, level, prev)
        f.write(json.dumps(rec) + '\n')
        f.flush()
        q, c = rec.get('q') or {}, rec.get('c') or {}
        print('ATTEMPT %s n=%d %s t_link=%s Q=%s %s C=%s %s %s' % (
            a.run, n, level, rec.get('t_link_s'), q.get('verdict'), q.get('err'), c.get('verdict'), c.get('err'),
            rec['verdict'] + ('' if rec['verdict'] == 'PASS' else ' (%s)' % rec.get('reason'))), flush=True)
        return rec
    try:
        recs, res = gate_loop(attempt, a.max_attempts, 3, a.ladder.split(','))
        res.update(kind='gate', run=a.run, rate=a.rate, t=time.strftime('%Y-%m-%dT%H:%M:%S%z'))
        f.write(json.dumps(res) + '\n')
        f.flush()
        print('GATE %s %s attempts=%d undecided=%d' % (a.run, res['verdict'], res['attempts'], res['undecided']),
              flush=True)
        if res['verdict'] == 'PASS' and a.soak:
            t = rig.soak(os.path.join(a.out, a.run + '_soak.jsonl'))
            print('SOAK %s %s secs=%s kept=%s bursts=%s sync=%s' % (a.run, t['status'], t['secs'], t['kept'],
                                                                   {k: len(v) for k, v in t['bursts'].items()},
                                                                   t['sync_frac']), flush=True)
    finally:
        f.close()
        try:
            os.remove(owner)
        except OSError:
            pass
    with open('/home/pi/fpga/gate.log', 'a') as g:
        g.write(json.dumps(res) + '\n')
    return 0 if res['verdict'] == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
