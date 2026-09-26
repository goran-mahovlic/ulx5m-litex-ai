#!/usr/bin/env python3
# io50 TX (TASK-4999): eth_tx = 50 MHz, the real 100M datapath (LiteEthRGMIITX100MCore) paced by
# tx_enable = ph (ph toggles every cycle), TXD/TX_CTL = posedge IOSEL FFs, TXC = IOSEL FF on CLK180
# sampling ph. A KSZ9031 model (DS00002117F: TXD on TXC rise, TX_CTL on both edges, setup/hold
# >= 1 ns, Table 7-1) rebuilds the frame. Pin skew between TXC and data (IOSEL-to-pad, board) is
# swept; the design point must also tolerate the PHASE of ph (which cycle of the pair) -- if the
# alignment were wrong by one cycle, TXC would sit on the data transition.
#
# Run:  source ./env.sh && python3 sim/tb_io50.py
#
# SPDX-License-Identifier: BSD-2-Clause
import sys, os, random
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "gateware"))
from migen import *
from migen.fhdl import specials as _sp
from litex.gen.sim import run_simulation

_get_port = _sp.Memory.get_port
def _get_port_sim(self, *a, **kw):
    port = _get_port(self, *a, **kw)
    if port.dat_r is None:
        port.dat_r = Signal(self.width)
    return port
_sp.Memory.get_port = _get_port_sim

from phy_rgmii_gatemate import LiteEthRGMIITX100MCore

TC  = 20.0   # ns, 50 MHz eth_tx
TSU = 1.0
TH  = 1.0

random.seed(4999)
FRAME = [0x55]*7 + [0xD5] + [random.randrange(256) for _ in range(64)]


class DUT(Module):
    def __init__(self):
        self.ph = ph = Signal()
        self.sync += ph.eq(~ph)
        self.submodules.core = LiteEthRGMIITX100MCore(store_forward=False, tx_enable=ph)
        self.sink = self.core.sink


def dut_trace():
    dut = DUT()
    trace = []   # per 50 MHz cycle k: values of (ph, tx_ctl[0], tx_data[0:4]) DURING cycle k
    def src():
        for _ in range(7):
            yield
        for i, b in enumerate(FRAME):
            yield dut.sink.valid.eq(1)
            yield dut.sink.data.eq(b)
            yield dut.sink.last.eq(i == len(FRAME) - 1)
            yield
            while not (yield dut.sink.ready):
                yield
        yield dut.sink.valid.eq(0)
    def mon():
        for _ in range(4*len(FRAME) + 60):
            trace.append(((yield dut.ph), (yield dut.core.tx_ctl) & 1, (yield dut.core.tx_data) & 0xF))
            yield
    run_simulation(dut, [src(), mon()])
    return trace


def pins(trace, skew):
    """IO FFs: at posedge k (t = k*TC) TXD/TX_CTL take the datapath value of cycle k-1; the TXC FF on
    CLK180 (t = k*TC + TC/2) takes ph of cycle k. skew = extra TXC delay vs data (pad/board)."""
    ctl, txd, txc = [], [[] for _ in range(4)], []
    for k in range(1, len(trace)):
        _, c, d = trace[k - 1]
        ctl.append((k*TC, c))
        for b in range(4):
            txd[b].append((k*TC, (d >> b) & 1))
        txc.append((k*TC + TC/2 + skew, trace[k][0]))
    return ctl, txd, txc


def sample(wave, ts):
    val, bad = None, False
    for i, (t, v) in enumerate(wave):
        if t <= ts:
            val = v
        if i and wave[i - 1][1] != v and ts - TSU <= t <= ts + TH:
            bad = True
    return val, bad


def edges(txc, rising):
    return [t for i, (t, v) in enumerate(txc) if i and txc[i - 1][1] != v and v == (1 if rising else 0)]


def phy_receive(trace, skew):
    ctl, txd, txc = pins(trace, skew)
    rises, falls = edges(txc, True), edges(txc, False)
    nib, viol, err, margins = [], 0, 0, []
    for tr in rises:
        tf = min([t for t in falls if t > tr], default=None)
        if tf is None:
            break
        en, b1 = sample(ctl, tr)
        x,  b2 = sample(ctl, tf)
        bits = [sample(w, tr) for w in txd]
        bad = b1 or b2 or any(b for _, b in bits)
        if en:
            viol += bad
            err  += (en ^ x)
            nib.append(sum(v << i for i, (v, _) in enumerate(bits)))
            chg = [t for t, _ in ctl]
            margins.append(min(tr - max(t for t in chg if t <= tr), min(t for t in chg if t > tf) - tf))
    got = [nib[2*i] | (nib[2*i + 1] << 4) for i in range(len(nib)//2)]
    return got == FRAME and viol == 0 and err == 0, viol, err, (min(margins) if margins else 0)


def main():
    trace = dut_trace()
    ok_all = True
    for skew in [-8.0, -4.0, -2.0, 0.0, 2.0, 4.0, 8.0]:
        ok, viol, err, m = phy_receive(trace, skew)
        ok_all &= ok if abs(skew) <= 8.0 else True
        print("  io50 TXC skew %+4.1f ns : %s  (setup/hold violations %d, TX_ER %d, min margin %.1f ns)"
              % (skew, "OK  " if ok else "FAIL", viol, err, m))
    ok0, _, _, m0 = phy_receive(trace, 0.0)
    assert ok0 and m0 >= 9.9, "io50 must give >= 10 ns margin at zero skew"
    assert ok_all, "io50 must tolerate +-8 ns TXC-to-data skew"
    print("PASS io50: frame intact, 10 ns setup/hold at 0 skew, tolerates +-8 ns")


if __name__ == "__main__":
    main()
