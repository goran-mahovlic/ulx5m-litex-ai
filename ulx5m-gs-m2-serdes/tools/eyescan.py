#!/usr/bin/env python3
"""On-chip eye scan and analog tuning of ONE GateMate SerDes receiver over the JTAG regfile (TASK-5063).

    fpga-jtag m2 run python3 eyescan.py scan --ph=-32:31:2 --th=-15:15:2 --window 512 --out eye_m2.json
    fpga-jtag gs run python3 eyescan.py set RX_EN_EQA=1 RX_AFE_PEAK=24 TX_SEL_PRE=5   # any serdestool field
    fpga-jtag gs run python3 eyescan.py get RX_EN_EQA RX_EQA_LOCKED RX_EQA_TAPW RX_TH_MON RX_OFFSET
    fpga-jtag gs run python3 eyescan.py recal [--rx]      # after field writes: TX/RX calibration + DFE (or RX) reset
    fpga-jtag gs run python3 eyescan.py health -n 10 --out h.json   # E0: PLL/BISC/calib/EQA/CDR + FREQ_ACC x10
    python3 eyescan.py margin eye_m2.json [--target 1e-3]
    python3 eyescan.py plot eye_m2.json eye_m2.png        # needs numpy + matplotlib (eyetools.py, pu-cc 83d7858)

Cologne Chip eye path (serdestool 15.10.2026, Patrick Urban; TASK-5525) - use these, not 'scan':
    fpga-jtag gs run python3 eyescan.py capture -n 10 --out cap.json      # eye_capture_op: ONE 0x07 read per monitor
    fpga-jtag gs run python3 eyescan.py diagnose --rate 2.5e9 --out d.json  # eye_diagnose PASS/FAIL chain
    fpga-jtag gs run python3 eyescan.py eye --rate 2.5e9 --out eye.json [--tapw-sweep]   # freeze, 64 ph x 31 th, restore
    fpga-jtag gs run python3 eyescan.py freeze RX_TAPW=3 [--ext 0b0111]   # pin the adapted point (+overrides), stays frozen
    fpga-jtag gs run python3 eyescan.py restore                          # adaptation back on (eye_restore)
'scan' below is the E7 path and is WRONG (kept for the record): it sets 0x06[11] = RX_EN_EQA_EXT_VALUE[3], which
write-protects RX_TH_MON2, and it never routes the monitor (RX_EQA_CONFIG sel_comp_data, writable only with RX_EN_EQA=0).

How a point is measured (DS1001 2026-09, tables 2.44-2.47, regfile 0x05, 0x14-0x1D): monitor 2 samples the
received signal at phase RX_MON_PH_OFFSET (0x15[5:0], signed, 64 codes = 1 UI as in eyetools) against threshold
RX_TH_MON2 (0x05[10:6], signed). Its override enable is 0x06[11] (vendor map, serdestool 56aa48b: RX_TH_MON2_OVR +
RX_AFE_OFFSET_OVR; 0x05[11] is unused - TUNING_5G.md §5.1). The monitor only runs with RX_EN_EQA=1 and
RX_EQA_LOCK_CFG bit1 (select monitor output for capturing); scan sets both and restores them. Writing RX_EYE_MEAS_EN=1 with
the window count in RX_EYE_MEAS_CFG (0x14[15:4]) starts a measurement; 0x14[0] reads back as EYE_MEAS_DONE
(DS1001 Table 2.59), so a read of 1 means done (until TASK-5066 this loop waited for 0 and timed out). The
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
    while not int(s.rd_regfile(0x14)) & 1:          # 0x14[0] reads back as EYE_MEAS_DONE (DS1001 Table 2.59)
        if time.time() - t > timeout:
            raise TimeoutError('EYE_MEAS_DONE not set (ph %d th %d)' % (ph, th))
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


# raw regfile words for the scatter snapshot (TASK-5487, uputa #308): cal 0x02/0x3C, EQA/AFE 0x04-0x07, CDR 0x0B-0x0D, PLL 0x55/0x5A/0x5B
RAW_REGS = (0x02, 0x04, 0x05, 0x06, 0x07, 0x0B, 0x0C, 0x0D, 0x3C, 0x55, 0x5A, 0x5B)


def raw_snapshot(s, regs=RAW_REGS):
    return {'0x%02X' % a: int(s.rd_regfile(a)) for a in regs}


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
    if a.raw:
        out['afe_offset'] = sd.s.rd_fields(['RX_AFE_OFFSET'])['RX_AFE_OFFSET']
        out['raw'] = raw_snapshot(sd.s)
    if a.out:
        json.dump(out, open(a.out, 'w'))
    print('HEALTH board=%s %s problems=%s freq_acc=%s span=%d' % (sd.board, a.label, ','.join(v['problems']) or 'none',
                                                              v['freq_acc'], v['freq_acc_span']))
    print('  ' + ' '.join('%s=%s' % kv for kv in f.items()))
    if a.raw:
        print('  RAW AFE_OFFSET=%s %s' % (out['afe_offset'], ' '.join('%s=%04X' % kv for kv in out['raw'].items())))
    sd.close()
    return 0


# ------------------------------------------------------------------ Cologne Chip eye path (TASK-5525)
OP_KEYS = ('tapw', 'th_mon1', 'th_mon2', 'offset')
# words the eye path touches: 0x04 EN_EQA/LOCK_CFG, 0x05 TH_MON1/2, 0x06 TAPW/AFE_OFFSET/EXT, 0x08 EQA_CONFIG, 0x14/0x15 monitor
EYE_KEEP = (0x04, 0x05, 0x06, 0x08, 0x14, 0x15)


def capture_split(s):
    """The pre-TASK-5525 way: three field reads = three captures of 0x07 (eye_capture_op docstring). For comparison."""
    return {'tapw': s.rd_field('RX_EQA_TAPW'), 'th_mon': s.rd_field('RX_TH_MON'), 'offset': s.rd_field('RX_OFFSET')}


def capture_stats(passes, keys=OP_KEYS):
    """[{key: value}] -> {key: {'min', 'max', 'distinct'}}: is the operating point stable across captures?"""
    out = {}
    for k in keys:
        v = [p[k] for p in passes if k in p]
        if v:
            out[k] = {'min': min(v), 'max': max(v), 'distinct': sorted(set(v))}
    return out


def eye_keep(s):
    return {a: int(s.rd_regfile(a)) for a in EYE_KEEP}


def eye_put_back(s, keep):
    """eye_restore with the bitstream's own words: adaptation off (0x08 is only writable with RX_EN_EQA=0), overrides
    off, 0x08/0x05/0x06/0x15 and the window back, then 0x04 (RX_EN_EQA + LOCK_CFG) last. 0x14[0] is start/status."""
    s.wr_fields({'RX_EN_EQA': 0})
    s.wr_fields({'RX_EN_EQA_EXT_VALUE': 0})
    for a in (0x08, 0x05, 0x06, 0x15):
        s.wr_regfile(addr=a, data=keep[a], mask=0xFFFF)
    s.wr_regfile(addr=0x14, data=keep[0x14] & 0xFFF0, mask=0xFFF0)
    s.wr_regfile(addr=0x04, data=keep[0x04], mask=0xFFFF)


def capture_op_kept(s):
    """eye_capture_op leaves RX_EQA_LOCK_CFG[1]=1; restore the bitstream value."""
    lk = s.rd_field('RX_EQA_LOCK_CFG')
    try:
        return s.eye_capture_op()
    finally:
        s.wr_field('RX_EQA_LOCK_CFG', lk)


def eye_to_json(e):
    """EyeData -> our points list [[th, ph, {class: (correct, wrong)}]] (margin/plot/load use it)."""
    return [[th, ph, {c: (e.correct[c][iy][ix], e.wrong[c][iy][ix]) for c in e.EYE_CLASSES}]
            for iy, th in enumerate(e.thresholds) for ix, ph in enumerate(e.phases)]


def _testmode_ok(sd):
    if sd.field('SERDES_TESTMODE') != 1:
        print('board=%s: SERDES_TESTMODE=0, regfile writes are ignored' % sd.board)
        return False
    return True


def cmd_capture(a):
    from serdes_jtag import Serdes
    sd = Serdes(); s = sd.s
    ops, split = [], []
    for i in range(a.n):
        ops.append(capture_op_kept(s))
        split.append(capture_split(s))
        if i < a.n - 1:
            time.sleep(a.interval)
    st = capture_stats(ops); st_split = capture_stats(split, ('tapw', 'th_mon', 'offset'))
    out = {'board': sd.board, 'label': a.label, 'time': time.strftime('%F %T'), 'n': a.n, 'interval': a.interval,
           'capture_op': ops, 'split_reads': split, 'stats': st, 'stats_split': st_split}
    if a.out:
        json.dump(out, open(a.out, 'w'))
    for i, (o, q) in enumerate(zip(ops, split)):
        print('CAP %s %2d op tapw=%+d th1=%+d th2=%+d off=%+d locked=%d | split tapw=%+d th=%+d off=%+d' % (
            sd.board, i, o['tapw'], o['th_mon1'], o['th_mon2'], o['offset'], o['locked'], q['tapw'], q['th_mon'],
            q['offset']))
    print('CAPSTAT board=%s %s op=%s split=%s' % (sd.board, a.label, json.dumps({k: v['distinct'] for k, v in st.items()}),
                                                 json.dumps({k: v['distinct'] for k, v in st_split.items()})))
    sd.close()
    return 0


def cmd_diagnose(a):
    import contextlib, io
    from serdes_jtag import Serdes
    sd = Serdes(); s = sd.s
    if not _testmode_ok(sd):
        return 1
    keep, buf, ok, dump = eye_keep(s), io.StringIO(), None, None
    try:
        with contextlib.redirect_stdout(buf):
            try:
                ok = s.eye_diagnose(window=a.window, monitor=2, line_rate=a.rate)
            except Exception as e:                          # e.g. TimeoutError: RX_EYE_MEAS_EN stuck at 1
                print('  [FAIL] exception                  %s: %s' % (type(e).__name__, e)); ok = False
            try:                                             # raw per-class counters at the data sampler's phase
                op = capture_op_kept(s); s.eye_freeze(op, monitor=2)
                dump = s.eye_dump_point(phase=0, threshold=0, window=a.window, repeats=1, line_rate=a.rate)
            except Exception as e:
                print('  dump_point failed %s: %s' % (type(e).__name__, e))
    finally:
        eye_put_back(s, keep)
    text = buf.getvalue()
    print('\n'.join('DIAG %s %s' % (sd.board, ln) for ln in text.splitlines()))
    after = s.rd_fields(['RX_EN_EQA', 'RX_EQA_LOCKED', 'RX_CDR_LOCKED', 'RX_EN_EQA_EXT_VALUE', 'RX_EQA_CONFIG'])
    print('DIAGRESULT board=%s %s ok=%s restored=%s' % (sd.board, a.label, ok, after))
    if a.out:
        json.dump({'board': sd.board, 'label': a.label, 'time': time.strftime('%F %T'), 'ok': ok, 'text': text,
                   'dump_point': {k: list(v) for k, v in dump.items()} if dump else None, 'after': after}, open(a.out, 'w'))
    sd.close()
    return 0 if ok else 1


def tapw_pick(areas):
    """[(tapw, open_area)] -> tapw with the largest open area (first one on a tie, as tc_eyemeas)."""
    best, best_a = None, -1
    for t, ar in areas:
        if ar > best_a:
            best, best_a = t, ar
    return best


def cmd_eye(a):
    from serdes_jtag import Serdes
    sd = Serdes(); s = sd.s
    if not _testmode_ok(sd):
        return 1
    keep, t0 = eye_keep(s), time.time()
    phs, ths = parse_range(a.ph), parse_range(a.th)
    op = capture_op_kept(s)
    print('EYE board=%s adapted op %s' % (sd.board, op), flush=True)
    sweep = []
    done = [0]

    def progress(eye, iy, ix):
        done[0] += 1
        if ix == len(eye.phases) - 1 or done[0] % 200 == 0:
            print('  %d/%d points %.0fs' % (done[0], len(phs) * len(ths), time.time() - t0), flush=True)
    try:
        s.eye_freeze(op, monitor=2)
        if a.tapw_sweep:
            for tw in range(-15, 16) if a.tapw_signed else range(0, 16):
                s.wr_field('RX_TAPW', tw)
                pr = s.eye_scan(phases=range(-32, 32, 8), thresholds=range(-15, 16, 3), window=a.window,
                                line_rate=a.rate)
                sweep.append((tw, pr.open_area(a.target)))
                print('  TAPW %+3d open area %d' % sweep[-1], flush=True)
            s.wr_field('RX_TAPW', tapw_pick(sweep))
        e = s.eye_scan(phases=phs, thresholds=ths, window=a.window, repeats=a.repeats, line_rate=a.rate,
                       on_point=progress)
        try:
            from serdestool import eye_codes_per_ui
            cpu = list(eye_codes_per_ui(e)) if len(phs) >= 64 else None
        except ValueError as x:
            cpu = str(x)
    finally:
        eye_put_back(s, keep)
    pts = {(th, ph): c for th, ph, c in eye_to_json(e)}
    m = margin(pts, a.target)
    out = {'board': sd.board, 'time': time.strftime('%F %T'), 'secs': round(time.time() - t0, 1), 'window': a.window,
           'repeats': a.repeats, 'label': a.label, 'path': 'cc_eye_freeze_monitor2', 'op': op, 'tapw_sweep': sweep,
           'tapw_used': tapw_pick(sweep) if sweep else op['tapw'], 'codes_per_ui': cpu, 'phases': phs, 'thresholds': ths,
           'points': eye_to_json(e), 'margin': m, 'open_area': e.open_area(a.target),
           'hits_total': sum(e.hits(iy, ix) for iy in range(len(ths)) for ix in range(len(phs)))}
    if a.out:
        json.dump(out, open(a.out, 'w'))
    print('EYE board=%s %s width=%d codes (%.2f UI) height=%d codes centre_ph=%s open_area=%d hits=%d cpu=%s %.0fs' % (
        sd.board, a.label, m['width_codes'], m['width_ui'], m['height_codes'], m['center_phase'], out['open_area'],
        out['hits_total'], cpu, time.time() - t0))
    sd.close()
    return 0


def parse_ext(v):
    return int(v, 0)


def cmd_freeze(a):
    """Pin the adapted operating point, then apply field overrides (e.g. RX_TAPW=3 RX_AFE_OFFSET=5) and leave it frozen."""
    from serdes_jtag import Serdes
    sd = Serdes(); s = sd.s
    if not _testmode_ok(sd):
        return 1
    op = capture_op_kept(s)
    s.eye_freeze(op, monitor=2)                      # 0b0111: eye_freeze refuses bit 3 for monitor 2
    vals = {kv.split('=')[0]: int(kv.split('=')[1], 0) for kv in a.fields}
    if vals:
        s.wr_fields(vals)                            # values first, with EXT_VALUE[3] still clear (TH_MON2 writable)
    if a.ext != 0b0111:
        s.wr_fields({'RX_EN_EQA_EXT_VALUE': a.ext})  # e.g. 0b1111: RX_AFE_OFFSET override on, enabled last
    got = s.rd_fields(['RX_EN_EQA', 'RX_EN_EQA_EXT_VALUE', 'RX_TAPW', 'RX_TH_MON1', 'RX_TH_MON2', 'RX_AFE_OFFSET',
                       'RX_CDR_LOCKED'] + list(vals))
    print('FREEZE board=%s op=%s ext=0b%04b now %s' % (sd.board, op, a.ext, got))
    sd.close()
    return 0 if all(got[k] == v for k, v in vals.items()) else 1


def cmd_restore(a):
    from serdes_jtag import Serdes
    sd = Serdes(); s = sd.s
    s.eye_restore()
    got = s.rd_fields(['RX_EN_EQA', 'RX_EN_EQA_EXT_VALUE', 'RX_EQA_CONFIG', 'RX_EQA_LOCKED', 'RX_CDR_LOCKED'])
    print('RESTORE board=%s %s' % (sd.board, got))
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
    h.add_argument('--raw', action='store_true', help='also RX_AFE_OFFSET + raw regfile words RAW_REGS into --out')
    c = sp.add_parser('capture'); c.add_argument('-n', type=int, default=10); c.add_argument('--interval', type=float, default=0.2)
    c.add_argument('--label', default=''); c.add_argument('--out')
    d = sp.add_parser('diagnose'); d.add_argument('--window', type=int, default=2048)
    d.add_argument('--rate', type=float, default=2.5e9); d.add_argument('--label', default=''); d.add_argument('--out')
    e = sp.add_parser('eye'); e.add_argument('--ph', default='-32:31:1'); e.add_argument('--th', default='-15:15:1')
    e.add_argument('--window', type=int, default=2048); e.add_argument('--repeats', type=int, default=1)
    e.add_argument('--rate', type=float, default=2.5e9); e.add_argument('--target', type=float, default=1e-3)
    e.add_argument('--tapw-sweep', action='store_true'); e.add_argument('--tapw-signed', action='store_true')
    e.add_argument('--label', default=''); e.add_argument('--out')
    fz = sp.add_parser('freeze'); fz.add_argument('fields', nargs='*'); fz.add_argument('--ext', type=parse_ext, default=0b0111)
    sp.add_parser('restore')
    a = p.parse_args(argv)
    fn = {'scan': cmd_scan, 'margin': cmd_margin, 'plot': cmd_plot, 'set': cmd_set, 'get': cmd_get, 'recal': cmd_recal,
          'health': cmd_health, 'capture': cmd_capture, 'diagnose': cmd_diagnose, 'eye': cmd_eye, 'freeze': cmd_freeze,
          'restore': cmd_restore}.get(a.cmd)
    if fn is None:
        p.print_help(); return 2
    return fn(a)


if __name__ == '__main__':
    sys.exit(main())
