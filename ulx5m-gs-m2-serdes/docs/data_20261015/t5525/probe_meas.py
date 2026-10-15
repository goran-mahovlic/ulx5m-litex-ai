# TASK-5525 raw probe: after a CC freeze, does RX_EYE_MEAS_EN ever clear and do the counters move?
import sys, time
sys.path.insert(0, '/home/pi/ulx5m-serdes/tools')
from serdes_jtag import Serdes
import eyescan as E
sd = Serdes(); s = sd.s
R = lambda a: int(s.rd_regfile(a)); cnt = lambda: [R(0x16 + i) for i in range(8)]
keep = E.eye_keep(s)
try:
    print('before freeze 0x14=%04X cnt=%s' % (R(0x14), cnt()))
    op = E.capture_op_kept(s); s.eye_freeze(op, monitor=2)
    print('op', op, 'frozen 0x04=%04X 0x05=%04X 0x06=%04X 0x08=%04X 0x14=%04X' % (R(4), R(5), R(6), R(8), R(0x14)))
    for win in (1, 15, 255, 2048):
        s.wr_field('RX_EYE_MEAS_CFG', win)
        s.wr_regfile(addr=0x14, data=0, mask=1)
        a0 = R(0x14)
        s.wr_field('RX_EYE_MEAS_EN', 1)
        seq = []
        t = time.time()
        while time.time() - t < 1.5:
            seq.append(R(0x14) & 1)
            if seq[-1] == 0:
                break
        print('win %4d: 0x14 before=%04X polls=%d last=%d after=%04X t=%.2fs cnt=%s' % (
            win, a0, len(seq), seq[-1], R(0x14), time.time() - t, cnt()))
    # does 0x14[0] clear if written 0 (level vs edge)?
    s.wr_regfile(addr=0x14, data=0, mask=1); print('after write 0: 0x14=%04X cnt=%s' % (R(0x14), cnt()))
finally:
    E.eye_put_back(s, keep)
    print('restored', s.rd_fields(['RX_EN_EQA', 'RX_EQA_LOCKED', 'RX_CDR_LOCKED', 'RX_EQA_CONFIG', 'RX_EN_EQA_EXT_VALUE']))
sd.close()
