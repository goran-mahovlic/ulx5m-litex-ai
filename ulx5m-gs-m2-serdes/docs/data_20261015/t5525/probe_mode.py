# TASK-5525: undocumented 0x14[3:1] with the CC freeze (monitor 2 routed); PRBS on the link
import sys, time
sys.path.insert(0, '/home/pi/ulx5m-serdes/tools')
from serdes_jtag import Serdes
import eyescan as E
sd = Serdes(); s = sd.s
R = lambda a: int(s.rd_regfile(a)); cnt = lambda: [R(0x16 + i) for i in range(8)]
keep = E.eye_keep(s)
try:
    st = s.rd_fields(['RX_PRBS_LOCKED', 'RX_PRBS_ERR_CNT', 'RX_CDR_LOCKED', 'RX_EQA_LOCKED'])
    op = E.capture_op_kept(s); print('board', sd.board, st, 'op', op)
    s.eye_freeze(op, monitor=2)
    for m in range(8):
        s.wr_regfile(addr=0x14, data=0, mask=0xF)
        s.wr_regfile(addr=0x14, data=(64 << 4) | (m << 1), mask=0xFFFE)
        s.wr_regfile(addr=0x14, data=(64 << 4) | (m << 1) | 1, mask=0xFFFF)
        time.sleep(0.05)
        print('m=%d 0x14=%04X cnt=%s' % (m, R(0x14), cnt()), flush=True)
finally:
    s.wr_regfile(addr=0x14, data=0, mask=0xF)
    E.eye_put_back(s, keep)
    print('restored', s.rd_fields(['RX_EN_EQA', 'RX_EQA_LOCKED', 'RX_CDR_LOCKED', 'RX_EQA_CONFIG', 'RX_EN_EQA_EXT_VALUE']))
sd.close()
