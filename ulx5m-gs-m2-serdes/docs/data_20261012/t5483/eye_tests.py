#!/usr/bin/env python3
"""TASK-5487 uputa #308 step 3: Manda's eye-counter hypotheses (docs/EYE_SCAN_ISTRAZIVANJE.md §2) + bathtub feasibility (§3.1).
fpga-jtag <board> run python3 eye_tests.py h7|h2|h3|h4|h8|h1rx|phase     (h1rx: run after the far board TX sends PRBS-7)
Counters = RX_EYE_MEAS 0x16..0x1D. Every test prints raw words; 'COUNTERS_NONZERO' marks a hit."""
import sys, time
sys.path.insert(0, "/home/pi/ulx5m-serdes/tools")
from serdes_jtag import Serdes
sd = Serdes(); s = sd.s
R = lambda a: int(s.rd_regfile(a)); W = lambda a, d, m: s.wr_regfile(a, d, m)
cnt = lambda: [R(0x16 + i) for i in range(8)]
G = lambda *n: s.rd_fields(list(n))
hit = lambda c: 'COUNTERS_NONZERO' if any(c) else 'zero'


def h2_seq(tag, cfg_low=0):
    W(0x14, (512 << 4) | cfg_low, 0xFFFE)
    for t in (0, 0.01, 0.1, 1, 5):
        W(0x14, 0, 1); W(0x14, 1, 1); time.sleep(t)
        c = cnt(); print('%s edge0->1 wait=%s 0x14=%s cnt=%s %s' % (tag, t, hex(R(0x14)), c, hit(c)))
    W(0x14, 0, 1); time.sleep(0.5); c = cnt(); print('%s after EN=0 0x14=%s cnt=%s %s' % (tag, hex(R(0x14)), c, hit(c)))


t = sys.argv[1]
print('board=%s test=%s 0x14=%s cnt=%s' % (sd.board, t, hex(R(0x14)), cnt()))
if t == 'h7':      # does a W/C strobe execute over JTAG (no regfile clock problem)?
    print('before', G('RX_CALIB_EN', 'RX_CALIB_DONE')); s.wr_fields({'RX_CALIB_EN': 1})
    for d in (0, 0.05, 0.5):
        time.sleep(d); print('after RX_CALIB_EN=1 +%ss' % d, G('RX_CALIB_EN', 'RX_CALIB_DONE'))
    W(0x14, 1, 1); print('after EYE_MEAS_EN=1 0x14=%s' % hex(R(0x14))); time.sleep(0.5); print('  +0.5 s 0x14=%s' % hex(R(0x14)))
elif t == 'h2':    # EN as edge/level, read later, latch on EN=0
    W(0x14, 0, 0xFFFF); print('after write 0: 0x14=%s' % hex(R(0x14)))
    W(0x14, 1, 0x0001); print('after write 1: 0x14=%s' % hex(R(0x14)))
    h2_seq('H2')
elif t == 'h3':    # 0x14[3:1] writable? then try monitor select 1..7
    W(0x14, 0b1110, 0x000E); v = R(0x14); print('write [3:1]=7 -> 0x14=%s writable=%s' % (hex(v), bool(v & 0xE)))
    if v & 0xE:
        for m in range(1, 8):
            h2_seq('H3 m=%d' % m, m << 1)
    W(0x14, 0, 0x000E)
elif t == 'h4':    # which bit makes RX_TH_MON follow RX_TH_MON2: 0x05[11] (DS) or 0x06[11] (PU)
    f0 = G('RX_TH_MON', 'RX_TH_MON2', 'RX_OFFSET', 'RX_AFE_OFFSET'); w0 = (R(0x05), R(0x06))
    print('start', f0, '0x05=%s 0x06=%s' % tuple(map(hex, w0)))
    s.wr_fields({'RX_AFE_OFFSET': f0['RX_OFFSET']})                    # keep the data threshold if 0x06[11] is AFE_OFFSET_OVR
    for name, a in (('DS 0x05[11]', 0x05), ('PU 0x06[11]', 0x06)):
        s.wr_fields({'RX_TH_MON2': 3}); W(a, 1 << 11, 1 << 11); time.sleep(0.2)
        print(name, 'set TH_MON2=3 ->', G('RX_TH_MON', 'RX_TH_MON2', 'RX_OFFSET'))
        h2_seq('H4 ' + name); W(a, 0, 1 << 11); time.sleep(0.2)
    W(0x05, w0[0], 0xFFFF); W(0x06, w0[1], 0xFFFF)                    # eye20 left TH_MON2 3 / AFE_OFFSET 7 without this
    print('restored 0x05=%s 0x06=%s' % (hex(R(0x05)), hex(R(0x06))))
elif t == 'h1rx':  # PRBS-7 checker on this RX (far TX must send PRBS-7), then the eye sequence
    s.wr_fields({'RX_PRBS_OVR': 1, 'RX_PRBS_SEL': 1}); time.sleep(0.2); s.wr_fields({'RX_PRBS_CNT_RESET': 1}); time.sleep(0.5)
    print('PRBS', G('RX_PRBS_LOCKED', 'RX_PRBS_ERR_CNT', 'RX_CDR_LOCKED', 'RX_EQA_LOCKED'))
    h2_seq('H1 prbs')
    s.wr_fields({'RX_PRBS_OVR': 0}); time.sleep(0.2); h2_seq('H1 control prbs_ovr=0')
elif t == 'h8':    # 0x2B reset bit order (EYE_SCAN_ISTRAZIVANJE.md §6.3): DS [11:10]=RX_RESET -> CDR drops; PR #1 = buffer reset only
    print('before', G('RX_CDR_LOCKED', 'RX_EQA_LOCKED'), '0x2B=%s' % hex(R(0x2B)))
    W(0x2B, 0x0C00, 0x0C00); print('0x2B[11:10]=11 ->', G('RX_CDR_LOCKED', 'RX_EQA_LOCKED'), '0x2B=%s' % hex(R(0x2B)))
    W(0x2B, 0, 0x0C00); time.sleep(0.5); print('released +0.5 s ->', G('RX_CDR_LOCKED', 'RX_EQA_LOCKED'))
elif t == 'phase': # §3.1: does RX_CDR_PHASE_ACC + SET_ACC_CONFIG bit0 hold the CDR phase?
    v = [G('RX_CDR_PHASE_ACC_VAL')['RX_CDR_PHASE_ACC_VAL'] for _ in range(5)]; print('free-running PHASE_ACC_VAL', v)
    tgt = (v[-1] + 0x1000) & 0xFFFF
    s.wr_fields({'RX_CDR_PHASE_ACC': tgt, 'RX_CDR_SET_ACC_CONFIG': 1, 'RX_CDR_FORCE_LOCK': 1}); time.sleep(0.1)
    print('override to %d ->' % tgt, [G('RX_CDR_PHASE_ACC_VAL', 'RX_CDR_LOCKED') for _ in range(5)])
    ckp = G('RX_CDR_CKP', 'RX_CDR_CKI'); s.wr_fields({'RX_CDR_CKP': 0, 'RX_CDR_CKI': 0}); time.sleep(0.1)
    print('CKP=CKI=0 ->', [G('RX_CDR_PHASE_ACC_VAL', 'RX_CDR_LOCKED') for _ in range(5)])
    s.wr_fields(dict(ckp, RX_CDR_SET_ACC_CONFIG=0, RX_CDR_FORCE_LOCK=0)); time.sleep(0.2)
    print('restored', G('RX_CDR_PHASE_ACC_VAL', 'RX_CDR_LOCKED', 'RX_CDR_CKP', 'RX_CDR_CKI'))
sd.close()
