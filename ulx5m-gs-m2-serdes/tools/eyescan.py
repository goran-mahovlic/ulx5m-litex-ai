#!/usr/bin/env python3
"""On-chip eye scan and analog tuning of ONE GateMate SerDes receiver over the JTAG regfile (TASK-5063).

    fpga-jtag m2 run python3 eyescan.py scan --ph=-32:31:2 --th=-15:15:2 --window 512 --out eye_m2.json
    fpga-jtag gs run python3 eyescan.py set RX_EN_EQA=1 RX_AFE_PEAK=24 TX_SEL_PRE=5   # any serdestool field
    fpga-jtag gs run python3 eyescan.py get RX_EN_EQA RX_EQA_LOCKED RX_EQA_TAPW RX_TH_MON RX_OFFSET
    fpga-jtag gs run python3 eyescan.py recal [--rx]      # after field writes: TX/RX calibration + DFE (or RX) reset
    fpga-jtag gs run python3 eyescan.py health -n 10 --out h.json   # E0: PLL/BISC/calib/EQA/CDR + FREQ_ACC x10
    python3 eyescan.py margin eye_m2.json [--target 1e-3]
    python3 eyescan.py plot eye_m2.json eye_m2.png        # needs numpy + matplotlib (eyetools.py, pu-cc 83d7858)

How a point is measured (DS1001 2026-09, tables 2.44-2.47, regfile 0x05, 0x14-0x1D): monitor 2 samples the
received signal at phase RX_MON_PH_OFFSET (0x15[5:0], signed, 64 codes = 1 UI as in eyetools) against threshold
RX_TH_MON2 (0x05[10:6], signed). Its override enable is 0x06[11] (vendor map, serdestool 56aa48b: RX_TH_MON2_OVR +
RX_AFE_OFFSET_OVR; 0x05[11] is unused - TUNING_5G.md §5.1). The monitor only runs with RX_EN_EQA=1 and
RX_EQA_LOCK_CFG bit1 (select monitor output for capturing); scan sets both and restores them. Writing RX_EYE_MEAS_EN=1 with
the window count in RX_EYE_MEAS_CFG (0x14[15:4]) starts a measurement; the bit clears when it is done. The
counters 0x16-0x1D hold correct/wrong decisions of the monitor for the bit classes X11, X00, 001, 110 (the data
sampler's decision is the reference). BER of a point = wrong / (correct + wrong) over all classes.
Needs SERDES_TESTMODE=1 (the BER bitstreams have it). The data path is not touched: run ber_mon.py alongside to
see that the fabric BER does not change while scanning.
"""
import argparse
import json
import sys
import time

CLASSES = ('11S', '00S', '001S', '110S')
REG_CNT = 0x16                      # 0x16..0x1D: CORRECT_11S, WRONG_11S, CORRECT_00S, WRONG_00S, ... 110S


def s5_code(v):
    if not -16 <= v <= 15:
        raise ValueError('threshold %d outside -16..15' % v)
    return v & 0x1F


def s5_value(c):
    c &= 0x1F
    return c - 32 if c & 0x10 else c


def s6_code(v):
    if not -32 <= v <= 31:
        raise ValueError('phase %d outside -32..31' % v)
    return v & 0x3F


def s6_value(c):
    c &= 0x3F
    return c - 64 if c & 0x20 else c


def th2_write(th):
    """(addr, data, mask): RX_TH_MON2 = th (0x05[10:6]); the override bit is separate (th2_ovr_write)."""
    return 0x05, s5_code(th) << 6, 0x07C0


def th2_ovr_write(on):
    """(addr, data, mask): RX_TH_MON2_OVR (+ RX_AFE_OFFSET_OVR) = 0x06[11]. It also makes the RX_AFE_OFFSET register
    field (0x06[10:6]) active, so the scan leaves that field as it is and restores 0x06 afterwards."""
    return 0x06, (1 << 11) if on else 0, 0x0800


def scan_prep(cur):
    """Field writes needed before a scan: DFE adaption on and EQA_LOCK_CFG bit1 (monitor output for capturing)."""
    w = {}
    if cur['RX_EN_EQA'] != 1:
        w['RX_EN_EQA'] = 1
    if not cur['RX_EQA_LOCK_CFG'] & 2:
        w['RX_EQA_LOCK_CFG'] = cur['RX_EQA_LOCK_CFG'] | 2
    return w


def ph_write(ph):
    return 0x15, s6_code(ph), 0x3F


def start_write(window):
    """RX_EYE_MEAS_CFG = window (12 bit) and RX_EYE_MEAS_EN = 1 in one write."""
    if not 0 < window < 4096:
        raise ValueError('window %d outside 1..4095' % window)
    return 0x14, (window << 4) | 1, 0xFFF1


def counts(words):
    """8 counter words (0x16..0x1D) -> {class: (correct, wrong)}."""
    return {c: (words[2 * i], words[2 * i + 1]) for i, c in enumerate(CLASSES)}


def point_ber(c):
    n = sum(a + b for a, b in c.values())
    return None if n == 0 else sum(b for _, b in c.values()) / float(n)


def _runs(ok):
    """Longest run of True in a list of (key, bool): (length, first key, last key)."""
    best, cur, start = (0, None, None), 0, None
    for k, v in ok:
        if v:
            cur, start = cur + 1, (k if cur == 0 else start)
            if cur > best[0]:
                best = (cur, start, k)
        else:
            cur = 0
    return best


def margin(points, target=1e-3):
    """Eye opening from {(th, ph): counts}: horizontal run at the threshold nearest 0, vertical run at its centre.
    A point is open when BER < target; a point with 0 errors in N decisions is open when 1/N < target."""
    def good(key):
        c = points.get(key)
        if c is None:
            return False
        b = point_ber(c)
        if b is None:
            return False
        n = sum(a + w for a, w in c.values())
        return (b if b > 0 else 1.0 / n) < target
    ths = sorted({t for t, _ in points}); phs = sorted({p for _, p in points})
    th0 = min(ths, key=abs)
    w, p0, p1 = _runs([(p, good((th0, p))) for p in phs])
    if w == 0:
        return {'width_codes': 0, 'height_codes': 0, 'center_phase': None, 'threshold_row': th0, 'target': target,
                'width_ui': 0.0}
    step = (phs[1] - phs[0]) if len(phs) > 1 else 1
    pc = p0 + ((p1 - p0) // step // 2) * step
    h, t0, t1 = _runs([(t, good((t, pc))) for t in ths])
    tstep = (ths[1] - ths[0]) if len(ths) > 1 else 1
    return {'width_codes': w * step, 'height_codes': h * tstep, 'center_phase': pc, 'threshold_row': th0,
            'phase_range': [p0, p1], 'threshold_range': [t0, t1], 'target': target, 'width_ui': w * step / 64.0}


def parse_range(s):
    a = [int(x) for x in s.split(':')]
    lo, hi, st = a[0], a[1], (a[2] if len(a) > 2 else 1)
    return list(range(lo, hi + 1, st))


# ------------------------------------------------------------------ hardware (via serdes_jtag, one probe per board)
def measure(s, ph, th, window, timeout=2.0):
    s.wr_regfile(*ph_write(ph))
    s.wr_regfile(*th2_write(th))
    s.wr_regfile(*start_write(window))
    t = time.time()
    while int(s.rd_regfile(0x14)) & 1:
        if time.time() - t > timeout:
            raise TimeoutError('RX_EYE_MEAS_EN did not clear (ph %d th %d)' % (ph, th))
    return counts([int(s.rd_regfile(REG_CNT + i)) for i in range(8)])


def cmd_scan(a):
    from serdes_jtag import Serdes
    sd = Serdes()
    if sd.field('SERDES_TESTMODE') != 1:
        print('board=%s: SERDES_TESTMODE=0, regfile writes are ignored' % sd.board); return 1
    s = sd.s
    keep = {x: int(s.rd_regfile(x)) for x in (0x04, 0x05, 0x06, 0x14, 0x15)}
    status = s.rd_fields(['RX_EN_EQA', 'RX_EQA_LOCK_CFG', 'RX_EQA_LOCKED', 'RX_EQA_TAPW', 'RX_TH_MON', 'RX_OFFSET',
                          'RX_AFE_OFFSET', 'RX_CDR_LOCKED', 'RX_AFE_PEAK', 'RX_AFE_GAIN', 'RX_CDR_CKP', 'TX_SEL_PRE',
                          'TX_SEL_POST', 'TX_AMP'])
    prep = scan_prep(status)
    if prep:
        s.wr_fields(prep)
        time.sleep(0.5)
    s.wr_regfile(*th2_ovr_write(1))
    phs, ths = parse_range(a.ph), parse_range(a.th)
    pts, t0 = {}, time.time()
    try:
        for th in ths:
            for ph in phs:
                c = measure(s, ph, th, a.window)
                for _ in range(a.repeats - 1):
                    c2 = measure(s, ph, th, a.window)
                    c = {k: (c[k][0] + c2[k][0], c[k][1] + c2[k][1]) for k in CLASSES}
                pts[(th, ph)] = c
            b = [point_ber(pts[(th, p)]) for p in phs]
            print('th %+3d  %s' % (th, ''.join('.' if x is not None and x < 1e-3 else ('o' if x is not None and x < 0.1 else '#') for x in b)), flush=True)
    finally:
        for addr, v in keep.items():                    # restore monitor settings (EN bit 0x14[0] self-clears)
            s.wr_regfile(addr=addr, data=v & (0xFFFE if addr == 0x14 else 0xFFFF), mask=0xFFFE if addr == 0x14 else 0xFFFF)
    m = margin(pts, a.target)
    out = {'board': sd.board, 'time': time.strftime('%F %T'), 'secs': round(time.time() - t0, 1), 'window': a.window,
           'repeats': a.repeats, 'label': a.label, 'status_before': status, 'phases': phs, 'thresholds': ths,
           'points': [[th, ph, pts[(th, ph)]] for th in ths for ph in phs], 'margin': m}
    if a.out:
        json.dump(out, open(a.out, 'w'))
    print('EYE board=%s %s width=%d codes (%.2f UI) height=%d codes centre_ph=%s @BER<%g  %.0fs' % (
        sd.board, a.label or '', m['width_codes'], m['width_ui'], m['height_codes'], m['center_phase'], a.target,
        time.time() - t0))
    sd.close()
    return 0


def load(path):
    d = json.load(open(path))
    pts = {(th, ph): {k: tuple(v) for k, v in c.items()} for th, ph, c in d['points']}
    return d, pts


def cmd_margin(a):
    d, pts = load(a.file)
    m = margin(pts, a.target)
    print(json.dumps(dict(m, board=d['board'], label=d.get('label'))))
    return 0


def cmd_plot(a):
    from eyetools import EyeData, EyePlot
    d, pts = load(a.file)
    e = EyeData(d['phases'], d['thresholds'], meta={'board': d['board'], 'label': d.get('label'), 'window': d['window'],
                                                    'repeats': d['repeats'], 'monitor': 2})
    for iy, th in enumerate(d['thresholds']):
        for ix, ph in enumerate(d['phases']):
            e.add(iy, ix, pts[(th, ph)])
    EyePlot().eye_plot_report(e, filename=a.png)
    print('wrote', a.png)
    return 0


def cmd_set(a):
    from serdes_jtag import Serdes
    sd = Serdes()
    vals = {kv.split('=')[0]: int(kv.split('=')[1], 0) for kv in a.fields}
    sd.s.wr_fields(vals)
    got = sd.s.rd_fields(list(vals))
    print('board=%s set %s' % (sd.board, ' '.join('%s=%s' % kv for kv in got.items())))
    sd.close()
    return 0 if all(got[k] == v for k, v in vals.items()) else 1


def cmd_get(a):
    from serdes_jtag import Serdes
    sd = Serdes()
    got = sd.s.rd_fields(a.fields)
    print('board=%s %s' % (sd.board, ' '.join('%s=%s' % kv for kv in got.items())))
    sd.close()
    return 0


# ------------------------------------------------------------------ E0 health, sweep procedure (TASK-5066)
HEALTH_FIELDS = ['PLL_LOCKED', 'PLL_CAP_FT_OF', 'PLL_CAP_FT_UF', 'PLL_CAP_FT', 'PLL_CAP_STATE',          # 0x55
                 'PLL_BISC_TIMER_DONE', 'PLL_BISC_CP_VALID', 'PLL_BISC_CP', 'PLL_BISC_OPT_DET', 'PLL_BISC_CO',  # 0x5A/5B
                 'RX_CALIB_DONE', 'RX_CALIB_CAL', 'TX_CALIB_DONE', 'TX_CALIB_CAL',                             # 0x02/0x3C
                 'RX_EN_EQA', 'RX_EQA_LOCK_CFG', 'RX_EQA_LOCKED', 'RX_EQA_TAPW', 'RX_TH_MON', 'RX_OFFSET',      # 0x04/0x07
                 'RX_CDR_LOCK_CFG', 'RX_CDR_TRANS_TH', 'RX_CDR_LOCKED',                                          # 0x0B
                 'RX_PRESENT', 'RX_DETECT_DONE', 'RX_BUF_ERR',                                                   # 0x2A[12..14]
                 'RX_AFE_PEAK', 'RX_AFE_GAIN', 'RX_AFE_VCMSEL', 'RX_RTERM_VCMSEL', 'RX_CDR_CKP',
                 'TX_AMP', 'TX_SEL_PRE', 'TX_SEL_POST', 'PLL_REF_RTERM']


def s15_value(c):
    c &= 0x7FFF
    return c - 0x8000 if c & 0x4000 else c


def health_verdict(f, freq_acc):
    """E0 verdict from one field snapshot + RX_CDR_FREQ_ACC_VAL samples (15 bit, read as two's complement)."""
    p = []
    for k in ('PLL_CAP_FT_OF', 'PLL_CAP_FT_UF'):
        if f[k]:
            p.append(k)
    for k in ('PLL_LOCKED', 'PLL_BISC_TIMER_DONE', 'PLL_BISC_CP_VALID', 'RX_CALIB_DONE', 'TX_CALIB_DONE', 'RX_CDR_LOCKED'):
        if not f[k]:
            p.append('%s=0' % k)
    if f['RX_EN_EQA'] and not f['RX_EQA_LOCKED']:
        p.append('RX_EQA_LOCKED=0')
    v = [s15_value(x) for x in freq_acc]
    return {'problems': p, 'freq_acc': v, 'freq_acc_span': max(v) - min(v)}


def recal_steps(rx=False):
    """Field writes after a JTAG change (TUNING_5G.md §3): TX/RX termination calibration (W/C), then reset the DFE
    (or the whole RX) through the 0x2B override, then release the override. Not upstream reset_serdes_rx (0x3F)."""
    r = ('RX_RESET_OVR', 'RX_RESET') if rx else ('RX_EQA_RESET_OVR', 'RX_EQA_RESET')
    return [{'TX_CALIB_EN': 1}, {'RX_CALIB_EN': 1}, {r[0]: 1, r[1]: 1}, {r[0]: 0}]


def do_recal(s, rx=False, timeout=3.0):
    for w in recal_steps(rx):
        s.wr_fields(w)
        time.sleep(0.05)
    t = time.time()
    while time.time() - t < timeout:
        f = s.rd_fields(['RX_EN_EQA', 'RX_EQA_LOCKED', 'RX_CDR_LOCKED', 'TX_CALIB_DONE', 'RX_CALIB_DONE'])
        if f['RX_CDR_LOCKED'] and (f['RX_EQA_LOCKED'] or not f['RX_EN_EQA']):
            break
        time.sleep(0.1)
    f['wait_s'] = round(time.time() - t, 2)
    return f


def cmd_recal(a):
    from serdes_jtag import Serdes
    sd = Serdes()
    f = do_recal(sd.s, a.rx)
    print('board=%s recal %s' % (sd.board, ' '.join('%s=%s' % kv for kv in f.items())))
    sd.close()
    return 0 if f['RX_CDR_LOCKED'] else 1


def cmd_health(a):
    from serdes_jtag import Serdes
    sd = Serdes()
    f = sd.s.rd_fields(HEALTH_FIELDS)
    acc, ph = [], []
    for i in range(a.n):
        g = sd.s.rd_fields(['RX_CDR_FREQ_ACC_VAL', 'RX_CDR_PHASE_ACC_VAL', 'RX_CDR_LOCKED'])
        acc.append(g['RX_CDR_FREQ_ACC_VAL']); ph.append(g['RX_CDR_PHASE_ACC_VAL'])
        f['RX_CDR_LOCKED'] = f['RX_CDR_LOCKED'] and g['RX_CDR_LOCKED']
        if i < a.n - 1:
            time.sleep(a.interval)
    v = health_verdict(f, acc)
    out = dict(board=sd.board, label=a.label, time=time.strftime('%F %T'), fields=f, phase_acc=ph, **v)
    if a.out:
        json.dump(out, open(a.out, 'w'))
    print('HEALTH board=%s %s problems=%s freq_acc=%s span=%d' % (sd.board, a.label, ','.join(v['problems']) or 'none',
                                                              v['freq_acc'], v['freq_acc_span']))
    print('  ' + ' '.join('%s=%s' % kv for kv in f.items()))
    sd.close()
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = p.add_subparsers(dest='cmd')
    s = sp.add_parser('scan'); s.add_argument('--ph', default='-32:31:2'); s.add_argument('--th', default='-15:15:2')
    s.add_argument('--window', type=int, default=512); s.add_argument('--repeats', type=int, default=1)
    s.add_argument('--target', type=float, default=1e-3); s.add_argument('--out'); s.add_argument('--label', default='')
    m = sp.add_parser('margin'); m.add_argument('file'); m.add_argument('--target', type=float, default=1e-3)
    pl = sp.add_parser('plot'); pl.add_argument('file'); pl.add_argument('png')
    st = sp.add_parser('set'); st.add_argument('fields', nargs='+')
    g = sp.add_parser('get'); g.add_argument('fields', nargs='+')
    rc = sp.add_parser('recal'); rc.add_argument('--rx', action='store_true', help='reset the whole RX, not only the DFE')
    h = sp.add_parser('health'); h.add_argument('-n', type=int, default=10); h.add_argument('--interval', type=float, default=1.0)
    h.add_argument('--label', default=''); h.add_argument('--out')
    a = p.parse_args(argv)
    fn = {'scan': cmd_scan, 'margin': cmd_margin, 'plot': cmd_plot, 'set': cmd_set, 'get': cmd_get, 'recal': cmd_recal,
          'health': cmd_health}.get(a.cmd)
    if fn is None:
        p.print_help(); return 2
    return fn(a)


if __name__ == '__main__':
    sys.exit(main())
