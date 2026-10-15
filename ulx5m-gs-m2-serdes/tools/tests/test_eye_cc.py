"""Cologne Chip eye path (serdestool 15.10.2026) on a fake regfile that models the rules from Patrick's docstrings
(TASK-5525): 0x08 RX_EQA_CONFIG is ignored while RX_EN_EQA=1, RX_TH_MON2 is write-protected while
RX_EN_EQA_EXT_VALUE[3]=0x06[11]=1, a read of 0x07 is a capture, and the counters only count when the monitor is routed
(sel_comp_data=2) with adaptation off. Runs without hardware, pyftdi or matplotlib."""
import argparse, os, sys, types, unittest
HERE = os.path.join(os.path.dirname(__file__), '..')
sys.path.insert(0, HERE)


def _stub(name, **attrs):
    if name in sys.modules:
        return
    try:
        __import__(name)
        return
    except ImportError:
        pass
    m = types.ModuleType(name)
    for k, v in attrs.items():
        setattr(m, k, v)
    sys.modules[name] = m


class _Any:
    def __init__(self, *a, **k): pass


_stub('pyftdi'); _stub('pyftdi.ftdi', Ftdi=_Any)
_stub('pyftdi.jtag', JtagEngine=_Any, JtagController=_Any, JtagStateMachine=_Any)
_stub('pyftdi.usbtools', UsbTools=_Any); _stub('pyftdi.bits', BitSequence=_Any)
_stub('matplotlib', use=lambda *a, **k: None); _stub('matplotlib.pyplot'); _stub('matplotlib.colors', LogNorm=_Any)

import serdes_jtag as sj
import eyescan as E

ST = sj._load_serdestool()
ST.args = argparse.Namespace(idx=0)


class FakeST(ST.SerdesTool):
    """Regfile model. Eye: closed for |ph| > 20 or |th| > 10 (one closed region per 64-code wrap)."""

    def __init__(self, offsets=(3,), th2=12):
        self.r = {a: 0 for a in range(0x80)}
        self.r[0x04] = (1 << 13) | (12 << 9) | (1 << 8)        # EQA_LOCKED, LOCK_CFG=12, EN_EQA=1
        self.r[0x08] = 0x01C0
        self.r[0x5C] = 0b101
        self.cap_reads, self.offsets, self.started, self.th2 = 0, list(offsets), 0, th2
        cdr = self.regfile.fields['RX_CDR_LOCKED']
        self.r[cdr['addr']] |= 1 << cdr['lbit']

    # --- raw access (upstream signature; _idx0_compat adds ours)
    def rd_regfile(self, idx, addr):
        if addr == 0x07:
            off = self.offsets[self.cap_reads % len(self.offsets)]
            self.cap_reads += 1
            mon2 = (self.r[0x04] >> 10) & 1                     # LOCK_CFG[1] picks the reported threshold
            th = self.th2 if mon2 else 9
            return (off & 0xF) << 10 | (th & 0x1F) << 5 | 4     # offset sm, TH_MON, TAPW=+4
        return self.r[addr]

    def wr_regfile(self, idx, addr, data, mask):
        old = self.r[addr]
        if addr == 0x08 and old is not None and self.r[0x04] & (1 << 8):
            return                                              # frozen while adaptation runs: silently dropped
        if addr == 0x05 and self.r[0x06] & (1 << 11):
            mask &= ~0x07C0                                     # TH_MON2 protected by EXT_VALUE[3]
        new = (old & ~mask) | (data & mask)
        if addr == 0x14 and data & mask & 1:
            self.started += 1
            self._count(new)
            new &= ~1                                           # start/status: 0 = done
        self.r[addr] = new & 0xFFFF

    def _count(self, w14):
        win = (w14 >> 4) & 0xFFF
        routed = ((self.r[0x08] >> 3) & 7) == 2 and not self.r[0x04] & (1 << 8)
        ph = E.s6_value(self.r[0x15]); th = E.s5_value(self.r[0x05] >> 6)
        for i in range(4):
            if not routed:
                c, w = 0, 0
            elif abs(ph) > 20 or abs(th) > 10:
                c, w = win // 2, win - win // 2
            else:
                c, w = win, 0
            self.r[0x16 + 2 * i], self.r[0x17 + 2 * i] = c, w


def fake(**k):
    f = FakeST(**k)
    sj._idx0_compat(f)
    return f


class Capture(unittest.TestCase):
    def test_one_read_of_0x07_per_monitor(self):
        f = fake()
        op = f.eye_capture_op()
        self.assertEqual(f.cap_reads, 2)
        self.assertEqual((op['tapw'], op['th_mon1'], op['th_mon2'], op['offset']), (4, 9, 12, 3))

    def test_split_reads_fire_three_captures(self):
        f = fake(offsets=(2, 3, 1))
        q = E.capture_split(f)
        self.assertEqual(f.cap_reads, 3)
        self.assertEqual(q['offset'], 1)          # third capture: a value from another moment than tapw/th_mon

    def test_kept_restores_lock_cfg(self):
        f = fake()
        E.capture_op_kept(f)
        self.assertEqual((f.r[0x04] >> 9) & 0xF, 12)

    def test_sign_magnitude_offset(self):
        f = fake(offsets=(0b1010,))               # sign bit + magnitude 2
        self.assertEqual(f.eye_capture_op()['offset'], -2)

    def test_stats(self):
        st = E.capture_stats([{'offset': 2, 'tapw': 4}, {'offset': 3, 'tapw': 4}], ('offset', 'tapw'))
        self.assertEqual(st['offset'], {'min': 2, 'max': 3, 'distinct': [2, 3]})
        self.assertEqual(st['tapw']['distinct'], [4])


class Freeze(unittest.TestCase):
    def test_e7_path_locks_th_mon2(self):
        # what eyescan.py scan did since E7: 0x06[11]=1 then TH_MON2 -> the write is dropped
        f = fake()
        f.wr_regfile(*E.th2_ovr_write(1))
        f.wr_regfile(*E.th2_write(-5))
        self.assertNotEqual(E.s5_value(f.r[0x05] >> 6), -5)

    def test_e7_path_counts_nothing(self):
        f = fake()
        f.wr_regfile(*E.start_write(512))
        self.assertEqual([f.r[0x16 + i] for i in range(8)], [0] * 8)

    def test_config_dropped_while_adapting(self):
        f = fake()
        f.wr_fields({'RX_EQA_CONFIG': 0x01D0})
        self.assertEqual(f.r[0x08], 0x01C0)

    def test_freeze_routes_monitor(self):
        f = fake()
        f.eye_freeze(f.eye_capture_op(), monitor=2)
        got = f.rd_fields(['RX_EN_EQA', 'RX_EN_EQA_EXT_VALUE', 'RX_EQA_CONFIG', 'RX_TH_MON2', 'RX_TAPW'])
        self.assertEqual(got['RX_EN_EQA'], 0)
        self.assertEqual(got['RX_EN_EQA_EXT_VALUE'], 0b0111)
        self.assertEqual((got['RX_EQA_CONFIG'] >> 3) & 7, 2)
        self.assertEqual((got['RX_TH_MON2'], got['RX_TAPW']), (12, 4))

    def test_freeze_refuses_bit3(self):
        with self.assertRaises(ValueError):
            fake().eye_freeze({'tapw': 0, 'th_mon1': 0, 'th_mon2': 0, 'offset': 0}, monitor=2, ext_value=0b1111)

    def test_negative_offset_does_not_crash_without_bit3(self):
        f = fake(offsets=(0b1010,))
        f.eye_freeze(f.eye_capture_op(), monitor=2)       # upstream: ValueError (-2 into unsigned RX_AFE_OFFSET)

    def test_put_back_restores_words(self):
        f = fake()
        keep = E.eye_keep(f)
        f.eye_freeze(f.eye_capture_op(), monitor=2)
        f.wr_fields({'RX_MON_PH_OFFSET': 7, 'RX_EYE_MEAS_CFG': 99})
        E.eye_put_back(f, keep)
        for a in (0x04, 0x05, 0x06, 0x08, 0x15):
            self.assertEqual(f.r[a], keep[a], hex(a))
        self.assertEqual(f.r[0x14] & 0xFFF0, keep[0x14] & 0xFFF0)


class Scan(unittest.TestCase):
    def test_scan_counts_after_freeze(self):
        f = fake()
        f.eye_freeze(f.eye_capture_op(), monitor=2)
        e = f.eye_scan(phases=range(-32, 32, 4), thresholds=range(-15, 16, 5), window=100, line_rate=2.5e9)
        pts = {(th, ph): c for th, ph, c in E.eye_to_json(e)}
        self.assertEqual(pts[(0, 0)]['11S'], (100, 0))
        self.assertEqual(pts[(15, 0)]['11S'], (50, 50))
        m = E.margin(pts, target=0.05)
        self.assertEqual(m['center_phase'], 0)
        self.assertGreater(m['width_codes'], 0)

    def test_codes_per_ui(self):
        f = fake()
        f.eye_freeze(f.eye_capture_op(), monitor=2)
        e = f.eye_scan(phases=range(-32, 32), thresholds=[0], window=64, line_rate=2.5e9)
        self.assertEqual(ST.eye_codes_per_ui(e), (64, 1))

    def test_tapw_pick(self):
        self.assertEqual(E.tapw_pick([(0, 5), (1, 9), (2, 9), (3, 1)]), 1)


class Diagnose(unittest.TestCase):
    def test_healthy_fake_passes(self):
        import contextlib, io
        f = fake()
        f.r[0x06] |= 0                                     # no override at start
        with contextlib.redirect_stdout(io.StringIO()) as out:
            ok = f.eye_diagnose(window=64, line_rate=2.5e9)
        self.assertTrue(ok, out.getvalue())
        self.assertIn('need 0b0111', out.getvalue())

    def test_railed_threshold_fails(self):
        import contextlib, io
        f = fake(th2=15)                                   # what the boards report (RX_TH_MON 15, VERIFY r. 204)
        with contextlib.redirect_stdout(io.StringIO()) as out:
            ok = f.eye_diagnose(window=64, line_rate=2.5e9)
        self.assertFalse(ok)
        self.assertIn('[FAIL] adapted threshold in range', out.getvalue())

    def test_upstream_check_would_fail(self):
        # upstream eye_diagnose freezes with ext 0b0111 and then demands 0b1111 -> FAIL on a healthy receiver
        import inspect
        src = open(os.path.join(HERE, 'upstream_cc_20261015', 'serdestool.py')).read()
        self.assertIn("rb['RX_EN_EQA_EXT_VALUE'] == 0b1111", src)
        self.assertIn('ext_value = 0b0111 if monitor == 2', src)
        self.assertNotIn("== 0b1111", inspect.getsource(ST.SerdesTool.eye_diagnose))


if __name__ == '__main__':
    unittest.main()
