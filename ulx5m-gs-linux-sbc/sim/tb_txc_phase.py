#!/usr/bin/env python3
# RGMII 100M TX timing: which TXC phase can the KSZ9031 sample correctly? (TASK-4999)
#
# KSZ9031RNX DS00002117F:
#   p.22  TX path: the PHY adds NO delay at GTX_CLK/TX_EN/TXD inputs; the MAC must provide it.
#   p.58  Table 7-1: receiver setup >= 1.0 ns, hold >= 1.0 ns.
#   p.59  10/100: TXD sampled on the RISING TXC edge, TX_CTL on BOTH edges (rise = TX_EN,
#         fall = TX_EN xor TX_ER); data-to-clock skew relaxed to <= 16 ns at 100 Mbps.
#
# Method: the real 100M datapath (LiteEthRGMIITX100MCore) runs in migen sim and yields the
# per-eth_tx-cycle DDR inputs (tx_ctl[1:0], tx_data[7:0]). They become pin waveforms
# (CC_ODDR: i1 from the rising edge, i2 from the falling edge, + clock-to-out), TXC is built per
# candidate mode, then a PHY model samples TXD/TX_EN on each TXC rise and TX_EN^TX_ER on the
# following fall, flags any sample whose +-1 ns window contains a transition, and rebuilds the
# frame. Board/pad skew between TXC and data is swept.
#
# Modes:
#   same  : TXC = DDR(1,0) on eth_tx          (original fixed_100m design)
#   inv   : TXC = DDR(0,1) on eth_tx          (180 deg)
#   pll90 : TXC = PLL CLK90 straight to pad   (+10 ns, plus fabric route delay swept 0..8 ns)
#
# Run:  source ./env.sh && python3 sim/tb_txc_phase.py
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

T      = 40.0   # ns, 25 MHz
TSU    = 1.0    # ns, KSZ9031 receiver setup (Table 7-1)
TH     = 1.0    # ns, receiver hold
TCO    = 1.5    # ns, CC_ODDR clock-to-out (common to data and a DDR-forwarded TXC)

random.seed(4999)
FRAME = [0x55]*7 + [0xD5] + [random.randrange(256) for _ in range(64)]


def dut_trace():
    dut = LiteEthRGMIITX100MCore(store_forward=False)
    trace = []
    def src():
        for _ in range(5):
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
        for _ in range(2*len(FRAME) + 40):
            yield
            trace.append(((yield dut.tx_ctl), (yield dut.tx_data)))
    run_simulation(dut, [src(), mon()])
    return trace


def waves(trace):
    """Per pin: list of (t_start, value) half-cycle segments; i1 in [kT, kT+T/2), i2 after."""
    ctl, txd = [], [[] for _ in range(4)]
    for k, (c, d) in enumerate(trace):
        t = k*T + TCO
        ctl += [(t, c & 1), (t + T/2, (c >> 1) & 1)]
        for b in range(4):
            txd[b] += [(t, (d >> b) & 1), (t + T/2, (d >> (4 + b)) & 1)]
    return ctl, txd


def sample(wave, ts):
    """Value at ts and whether a transition lies inside [ts-TSU, ts+TH] (setup/hold violation)."""
    val, bad = None, False
    for i, (t, v) in enumerate(wave):
        if t <= ts:
            val = v
        if i and wave[i - 1][1] != v and ts - TSU <= t <= ts + TH:
            bad = True
    return val, bad


def txc_rises(mode, n, route):
    if mode == "same":
        return [k*T + TCO + route for k in range(n)]
    if mode == "inv":
        return [k*T + T/2 + TCO + route for k in range(n)]
    if mode == "pll90":
        return [k*T + T/4 + route for k in range(n)]   # CLK90 net straight to the pad
    raise ValueError(mode)


def phy_receive(trace, mode, route):
    ctl, txd = waves(trace)
    nib, viol, err = [], 0, 0
    for tr in txc_rises(mode, len(trace) - 1, route):
        en, b1 = sample(ctl, tr)
        x,  b2 = sample(ctl, tr + T/2)            # falling edge: TX_EN xor TX_ER
        bits = [sample(w, tr) for w in txd]
        bad = b1 or b2 or any(b for _, b in bits)
        if en:
            viol += bad
            err  += (en ^ x)                       # TX_ER asserted inside the frame
            nib.append(sum(v << i for i, (v, _) in enumerate(bits)))
        elif bad and (x or any(v for v, _ in bits)):
            viol += 1
    got = [nib[2*i] | (nib[2*i + 1] << 4) for i in range(len(nib)//2)]
    return got == FRAME and viol == 0 and err == 0, viol, err


def main():
    trace = dut_trace()
    results = {}
    for mode, routes in [("same", [-1.0, -0.5, 0.0, 0.5, 1.0]),
                         ("inv",  [-1.0, 0.0, 1.0]),
                         ("pll90", [0.0, 2.0, 4.0, 6.0, 8.0])]:
        for r in routes:
            ok, viol, err = phy_receive(trace, mode, r)
            results[(mode, r)] = ok
            print("  %-5s skew %+4.1f ns : %s  (setup/hold violations %d, TX_ER in frame %d)"
                  % (mode, r, "OK  " if ok else "FAIL", viol, err))
    assert not any(results[("same", r)] for r in [-0.5, 0.0, 0.5]), "same-edge TXC should fail"
    assert not any(results[("inv", r)] for r in [-1.0, 0.0, 1.0]), "180 deg TXC should fail (TX_CTL fall sample)"
    assert all(results[("pll90", r)] for r in [0.0, 2.0, 4.0, 6.0, 8.0]), "90 deg TXC must pass"
    print("PASS txc phase: same-edge FAIL, 180 deg FAIL, 90 deg (PLL CLK90) OK for 0..8 ns route delay")


if __name__ == "__main__":
    main()
