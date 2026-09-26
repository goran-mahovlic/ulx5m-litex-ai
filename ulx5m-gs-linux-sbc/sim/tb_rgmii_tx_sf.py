#!/usr/bin/env python3
# RGMII 100M TX core (store-and-forward FIFO + LiteEth 10/100 nibble datapath), TASK-4999.
#
# The sys domain may run no faster than the line byte rate (12.5 MHz sys on a 0.9 V core),
# so the TX CDC can underflow mid-frame. The PHY therefore buffers each whole frame in the
# eth_tx domain before sending it. This bench feeds frames WITH random bubbles and checks,
# on the wire side (tx_ctl/tx_data before the DDR pads):
#   1) TX_CTL (TX_EN) is one contiguous burst per frame -- no mid-frame gaps.
#   2) low nibble first, then high nibble, byte for byte equal to the input.
#   3) the control case (no store-and-forward) DOES produce gaps -> the test can fail.
#
# Run:  source ./env.sh && python3 sim/tb_rgmii_tx_sf.py
#
# SPDX-License-Identifier: BSD-2-Clause
import sys, os, random
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "gateware"))
from migen import *
from migen.fhdl import specials as _sp
from litex.gen.sim import run_simulation

# Sim-only shim: this migen fork creates write-only memory ports with dat_r=None, which its
# own simulator lowering (fhdl/simplify.py) cannot handle. Give such ports a dummy dat_r.
_get_port = _sp.Memory.get_port
def _get_port_sim(self, *a, **kw):
    port = _get_port(self, *a, **kw)
    if port.dat_r is None:
        port.dat_r = Signal(self.width)
    return port
_sp.Memory.get_port = _get_port_sim

from phy_rgmii_gatemate import LiteEthRGMIITX100MCore

random.seed(4999)
FRAMES = [[0x55]*7 + [0xD5] + [random.randrange(256) for _ in range(n)] for n in (60, 64, 97)]


def source_gen(dut, frames, bubble_p):
    for f in frames:
        for i, b in enumerate(f):
            while random.random() < bubble_p:
                yield dut.sink.valid.eq(0)
                yield
            yield dut.sink.valid.eq(1)
            yield dut.sink.data.eq(b)
            yield dut.sink.last.eq(i == len(f) - 1)
            yield
            while not (yield dut.sink.ready):
                yield
        yield dut.sink.valid.eq(0)
        yield dut.sink.last.eq(0)
        for _ in range(30):
            yield


def wire_monitor(dut, trace, cycles):
    for _ in range(cycles):
        yield
        trace.append(((yield dut.tx_ctl), (yield dut.tx_data)))


def decode(trace):
    """Split the wire trace into bursts of TX_EN=1 and rebuild bytes (low nibble first)."""
    bursts, cur = [], None
    for ctl, data in trace:
        en = ctl & 1
        assert (ctl >> 1) == en, "TX_CTL halves differ -> PHY would see TX_ER"
        if en:
            assert (data & 0xF) == (data >> 4), "100M: same nibble on both DDR edges"
            cur = (cur or []) + [data & 0xF]
        elif cur is not None:
            bursts.append(cur)
            cur = None
    return bursts


def run(store_forward, bubble_p=0.35):
    dut = LiteEthRGMIITX100MCore(store_forward=store_forward, depth=256)
    trace = []
    run_simulation(dut, [source_gen(dut, FRAMES, bubble_p), wire_monitor(dut, trace, 6000)])
    return decode(trace)


def main():
    bursts = run(store_forward=True)
    assert len(bursts) == len(FRAMES), "expected %d contiguous bursts, got %d" % (len(FRAMES), len(bursts))
    for f, nib in zip(FRAMES, bursts):
        assert len(nib) == 2*len(f), "burst length %d nibbles, want %d" % (len(nib), 2*len(f))
        got = [nib[2*i] | (nib[2*i + 1] << 4) for i in range(len(f))]
        assert got == f, "byte/nibble order mismatch"
    print("PASS store-and-forward: %d frames, contiguous TX_EN, nibble order OK" % len(bursts))

    ctrl = run(store_forward=False)
    assert len(ctrl) > len(FRAMES), "control case should break frames into gaps (got %d bursts)" % len(ctrl)
    print("PASS control: without store-and-forward frames split into %d bursts (test is sensitive)" % len(ctrl))


if __name__ == "__main__":
    main()
