#!/usr/bin/env python3
"""strobe_probe.py <step> [N] - TASK-5527 uputa #338 / EYE_MEAS_UZROK.md §4 P1+P2 on ONE board per call
(fpga-jtag <board> run python3 lab/strobe_probe.py <step>): do W/C strobes execute at all, and does extra TCK in Run-Test/Idle
make them execute (regfile clock = TCK hypothesis H-A)?

  tx_prbs_on | tx_prbs_off      (gs)  TX PRBS-15 on/off (TX_PRBS_OVR/SEL)
  rx_prbs_on | rx_prbs_off      (m2)  RX PRBS-15 checker on/off
  cnt                           (m2)  RX_PRBS_LOCKED / ERR_CNT now
  force N                       (gs)  N x TX_PRBS_FORCE_ERR=1 (W/C), then read the field back
  cnt_reset [N]                 (m2)  RX_PRBS_CNT_RESET=1 (W/C), [N TCK in RTI], read field + ERR_CNT
  eye [N]                       (any) freeze, RX_EYE_MEAS_CFG=15, RX_EYE_MEAS_EN=1, [N TCK in RTI], read 0x14 + 0x16..0x1D, put back
"""
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))


def rti(sd, n):
    """n TCK with TMS=0: the engine is in Run-Test/Idle after every DR/IR update (dirtyjtag_engine._shift)."""
    if n:
        t = time.time()
        sd.eng._clock(tms=0, tdi=0, n=n)
        return time.time() - t
    return 0.0


def main(argv):
    from serdes_jtag import Serdes
    step, n = argv[0], int(argv[1]) if len(argv) > 1 else 0
    sd = Serdes(); s = sd.s
    R = lambda a: int(s.rd_regfile(0, a))
    cnt = lambda: s.rd_fields(['RX_PRBS_LOCKED', 'RX_PRBS_ERR_CNT'])
    t0 = time.time()
    if step == 'tx_prbs_on':
        s.wr_fields({'TX_PRBS_OVR': 1, 'TX_PRBS_SEL': 2})
    elif step == 'tx_prbs_off':
        s.wr_fields({'TX_PRBS_SEL': 0, 'TX_PRBS_OVR': 0})
    elif step == 'rx_prbs_on':
        s.wr_fields({'RX_PRBS_OVR': 1, 'RX_PRBS_SEL': 2})
    elif step == 'rx_prbs_off':
        s.wr_fields({'RX_PRBS_SEL': 0, 'RX_PRBS_OVR': 0})
    elif step == 'cnt':
        pass
    elif step == 'force':
        for _ in range(n):
            s.wr_field('TX_PRBS_FORCE_ERR', 1)
        print('FORCE board=%s n=%d secs=%.2f field_after=%d' % (sd.board, n, time.time() - t0, s.rd_field('TX_PRBS_FORCE_ERR')))
    elif step == 'cnt_reset':
        a = cnt()
        s.wr_field('RX_PRBS_CNT_RESET', 1)
        dt = rti(sd, n)
        print('CNT_RESET board=%s rti=%d (%.3fs) before=%s field_after=%d after=%s' % (
            sd.board, n, dt, a, s.rd_field('RX_PRBS_CNT_RESET'), cnt()))
    elif step == 'eye':
        import eyescan as E
        keep = E.eye_keep(s)
        try:
            op = E.capture_op_kept(s); s.eye_freeze(op, monitor=2)
            s.wr_field('RX_EYE_MEAS_CFG', 15)
            s.wr_regfile(0, 0x14, 0, 1)
            before = R(0x14)
            s.wr_field('RX_EYE_MEAS_EN', 1)
            dt = rti(sd, n)
            print('EYE board=%s rti=%d (%.3fs) 0x14 before=%04X after=%04X cnt=%s' % (
                sd.board, n, dt, before, R(0x14), [R(0x16 + i) for i in range(8)]))
        finally:
            E.eye_put_back(s, keep)
    else:
        raise SystemExit(__doc__)
    if step != 'eye':
        print('STATE board=%s step=%s %s %s' % (sd.board, step, cnt(), s.rd_fields(
            ['RX_PRBS_OVR', 'RX_PRBS_SEL', 'TX_PRBS_OVR', 'TX_PRBS_SEL', 'RX_CDR_LOCKED'])))
    sd.close()


if __name__ == '__main__':
    main(sys.argv[1:])
