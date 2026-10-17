#!/usr/bin/env python3
"""k1_write.py - TASK-5559 K1 a/b/b'/0x2B (CALIBRATION_OPTIONS_20261017_v2 §2.3, §3.1): which regfile writes hold.

    fpga-jtag gs run python3 lab/k1_write.py --out ../t5559/k1/k1w_gs.json

One board (the probe of FPGA_JTAG_BUSDEV). Every step writes, then reads the whole word back (raw), and the steps that
ask 'does it hold' read it 10 x over 5 s. Hypotheses (v2 §2.3):
  H-a  CKP_* (0x03, 0x04[7:0]) are write-protected while RX_EN_EQA=1 (the blocked write is silently dropped)
  H-b  the reset/EQA FSM (or the bit) rewrites the field after a good write (readback right after = write, later not)
  0x2B the R/W override bits alone (no W/C strobe in the same write) - do they read back?
The script leaves EN_EQA=1 and puts the CKP fields back to what they read at the start, using whatever path worked.
Pure logic (step table, verdicts) is tested in tests/test_k1_write.py on a fake regfile."""
import argparse
import json
import os
import sys
import time

CKP_ADDR = (0x03, 0x04)


def word_fields(w4):
    """0x04 word -> (CKP_OFFSET, EN_EQA, LOCK_CFG, EQA_LOCKED)."""
    return {'CKP_OFFSET': w4 & 0xFF, 'EN_EQA': (w4 >> 8) & 1, 'LOCK_CFG': (w4 >> 9) & 0xF, 'EQA_LOCKED': (w4 >> 13) & 1}


def hold(series, want, mask=0xFFFF):
    """'held' if every raw read has want under mask, 'lost' if the first read has it and a later one not,
    'never' if the first read does not have it."""
    if not series:
        return 'none'
    if (series[0] & mask) != (want & mask):
        return 'never'
    return 'held' if all((x & mask) == (want & mask) for x in series) else 'lost'


class Steps:
    """Runs the K1 sequence on a regfile object with rd(addr) -> int and wr(addr, data, mask)."""

    def __init__(self, rd, wr, sleep=time.sleep, n=10, dt=0.5):
        self.rd, self.wr, self.sleep, self.n, self.dt = rd, wr, sleep, n, dt
        self.log = []

    def series(self, addr):
        out = []
        for i in range(self.n):
            out.append(int(self.rd(addr)))
            if i < self.n - 1:
                self.sleep(self.dt)
        return out

    def step(self, name, addr, data, mask, watch=True):
        before = int(self.rd(addr))
        self.wr(addr, data, mask)
        after = int(self.rd(addr))
        want = (before & ~mask & 0xFFFF) | (data & mask)
        rec = {'step': name, 'addr': '0x%02X' % addr, 'data': '0x%04X' % data, 'mask': '0x%04X' % mask,
               'before': '0x%04X' % before, 'after': '0x%04X' % after, 'want': '0x%04X' % want,
               'ok': (after & mask) == (data & mask)}
        if watch:
            s = self.series(addr)
            rec['series'] = ['0x%04X' % x for x in s]
            rec['hold'] = hold(s, data, mask)
        self.log.append(rec)
        return rec

    def run(self):
        w3, w4 = int(self.rd(0x03)), int(self.rd(0x04))
        start = {'0x03': '0x%04X' % w3, '0x04': '0x%04X' % w4, 'f04': word_fields(w4), '0x01': '0x%04X' % int(self.rd(0x01)),
                 '0x2B': '0x%04X' % int(self.rd(0x2B))}
        off0, lf0 = w4 & 0xFF, w3 & 0xFF
        # (a) CKP_OFFSET = 2 with EN_EQA as loaded (1), field write as eyescan set does (mask 0x00FF)
        self.step('a_offset2_eqa1', 0x04, 0x0002, 0x00FF)
        # (b') raw word 0x04, mask 0x00FF, data 0x55, EN_EQA still 1
        self.step('b1_raw55_eqa1', 0x04, 0x0055, 0x00FF)
        # control: 0x01 (reset times / WAIT_CDR_LOCK) is R/W and not an EQA loop field
        w1 = int(self.rd(0x01))
        self.step('ctl_0x01_eqa_time7', 0x01, 7 << 5, 0x1F << 5)
        self.step('ctl_0x01_back', 0x01, w1 & (0x1F << 5), 0x1F << 5, watch=False)
        # (b) H-a: EN_EQA 0 -> CKP_OFFSET 2, CKP_LF 0x83 -> readback -> EN_EQA 1 -> readback (never write CKP back to 0)
        self.step('b_en_eqa0', 0x04, 0x0000, 0x0100)
        self.step('b_offset2_eqa0', 0x04, 0x0002, 0x00FF)
        self.step('b_lf83_eqa0', 0x03, 0x0083, 0x00FF)
        self.step('b_raw55_eqa0', 0x04, 0x0055, 0x00FF)
        self.step('b_offset2_again_eqa0', 0x04, 0x0002, 0x00FF)
        r = self.step('b_en_eqa1', 0x04, 0x0100, 0x0100)
        s3 = self.series(0x03)
        self.log.append({'step': 'b_after_en1_0x03', 'series': ['0x%04X' % x for x in s3], 'hold': hold(s3, 0x83, 0xFF)})
        self.log.append({'step': 'b_after_en1_0x04', 'series': r.get('series'), 'hold': hold([int(x, 16) for x in r['series']], 2, 0xFF)})
        # 0x2B: R/W override bits alone, then together with the W/C strobe as link_gate does
        self.step('x2b_eqa_ovr1', 0x2B, 0x0004, 0x0004)
        self.step('x2b_eqa_ovr0', 0x2B, 0x0000, 0x0004)
        self.step('x2b_pol_ovr_same', 0x2B, int(self.rd(0x2B)) & 0x3000, 0x3000)   # write back what it holds
        self.step('x2b_eqa_ovr1_rst1', 0x2B, 0x000C, 0x000C)
        self.step('x2b_eqa_ovr0_rst0', 0x2B, 0x0000, 0x000C)
        # put CKP back to the loaded values over the path that is known to accept writes (EN_EQA 0 -> write -> 1)
        self.step('restore_en0', 0x04, 0x0000, 0x0100, watch=False)
        self.step('restore_offset', 0x04, off0, 0x00FF, watch=False)
        self.step('restore_lf', 0x03, lf0, 0x00FF, watch=False)
        self.step('restore_en1', 0x04, 0x0100, 0x0100, watch=False)
        end = {'0x03': '0x%04X' % int(self.rd(0x03)), '0x04': '0x%04X' % int(self.rd(0x04))}
        return {'start': start, 'steps': self.log, 'end': end, 'verdict': verdict(self.log)}


def verdict(log):
    by = {r['step']: r for r in log}
    g = lambda k, f='ok': by.get(k, {}).get(f)                                               # noqa: E731
    return {
        'offset_writable_eqa1': g('a_offset2_eqa1'), 'offset_hold_eqa1': g('a_offset2_eqa1', 'hold'),
        'raw55_writable_eqa1': g('b1_raw55_eqa1'),
        'ctl_0x01_writable': g('ctl_0x01_eqa_time7'),
        'offset_writable_eqa0': g('b_offset2_eqa0'), 'lf_writable_eqa0': g('b_lf83_eqa0'),
        'offset_after_en1': g('b_after_en1_0x04', 'hold'), 'lf_after_en1': g('b_after_en1_0x03', 'hold'),
        'H_a': (g('a_offset2_eqa1') is False) and bool(g('b_offset2_eqa0')),
        'x2b_ovr_alone': g('x2b_eqa_ovr1'), 'x2b_ovr_with_strobe': g('x2b_eqa_ovr1_rst1'),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
    from serdes_jtag import Serdes
    sd = Serdes()
    s = sd.s
    res = Steps(lambda ad: s.rd_regfile(addr=ad), lambda ad, d, m: s.wr_regfile(addr=ad, data=d, mask=m)).run()
    res.update(board=sd.board, t=time.strftime('%Y-%m-%dT%H:%M:%S%z'))
    sd.close()
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    json.dump(res, open(a.out, 'w'), indent=1)
    for r in res['steps']:
        print('%-22s %s d=%s m=%s before=%s after=%s ok=%s hold=%s' % (r['step'], r.get('addr'), r.get('data'), r.get('mask'),
                                                                    r.get('before'), r.get('after'), r.get('ok'), r.get('hold')))
    print('K1W board=%s start=%s end=%s verdict=%s' % (res['board'], res['start'], res['end'], json.dumps(res['verdict'])))
    return 0


if __name__ == '__main__':
    sys.exit(main())
