# TASK-5525: does any RX_EQA_CONFIG routing / EN_EQA state make the eye engine run (EN self-clears or counters move)?
import sys, time
sys.path.insert(0, '/home/pi/ulx5m-serdes/tools')
from serdes_jtag import Serdes
import eyescan as E
sd = Serdes(); s = sd.s
R = lambda a: int(s.rd_regfile(a)); cnt = lambda: [R(0x16 + i) for i in range(8)]
keep = E.eye_keep(s)
def pulse(win=64):
    s.wr_regfile(addr=0x14, data=0, mask=1)
    s.wr_regfile(addr=0x14, data=win << 4, mask=0xFFF0)
    s.wr_regfile(addr=0x14, data=1, mask=1)
    time.sleep(0.05)
    return R(0x14) & 1, cnt()
try:
    op = E.capture_op_kept(s); s.eye_freeze(op, monitor=2)
    for sel in range(8):
        for tap in (0, 1):
            cfg = (sel << 3) | tap
            s.wr_fields({'RX_EQA_CONFIG': cfg})
            en, c = pulse()
            print('frozen cfg=%04X rb=%04X en=%d cnt=%s' % (cfg, R(0x08), en, c), flush=True)
    s.wr_fields({'RX_EQA_CONFIG': 0x10})
    s.wr_fields({'RX_EN_EQA_EXT_VALUE': 0})
    s.wr_fields({'RX_EN_EQA': 1})                  # adapting, monitor routed (written while EN_EQA was 0)
    time.sleep(0.2)
    en, c = pulse(); print('adapting cfg=%04X en=%d cnt=%s' % (R(0x08), en, c))
    s.wr_fields({'RX_EQA_LOCK_CFG': 14}); en, c = pulse(); print('adapting lockcfg=14 en=%d cnt=%s' % (en, c))
finally:
    E.eye_put_back(s, keep)
    print('restored', s.rd_fields(['RX_EN_EQA', 'RX_EQA_LOCKED', 'RX_CDR_LOCKED', 'RX_EQA_CONFIG', 'RX_EN_EQA_EXT_VALUE', 'RX_EQA_LOCK_CFG']))
sd.close()
