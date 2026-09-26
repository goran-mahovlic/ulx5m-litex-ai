#!/usr/bin/env python3
# TASK-5040: Scaler2x (gateware/video_sbc.py) - a sw x sh rgb565 frame is shown pixel- and line-doubled.
#
# A tiny VTG (8x6 active) drives the scaler; a source feeds 4x3 frames (pixel = frame*64 + y*8 + x, `last` on
# the final pixel), with random stalls. Checks, for every visible pixel after the discarded first frame:
#   1) output (X, Y) == frame pixel (X//2, Y//2)  (colour bits unpacked from rgb565);
#   2) every frame shown is complete (all 48 active pixels, de count per frame == 48);
#   3) no underflow when the source keeps up.
# Run:  source ./env.sh && python3 sim/tb_scaler2x.py      (or tools/soc_build.sh environment)
#
# SPDX-License-Identifier: BSD-2-Clause
import os, sys, random
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "gateware"))
from migen import *
from litex.gen import LiteXModule
from litex.soc.cores.video import VideoTimingGenerator
from video_sbc import Scaler2x

TIM = {"pix_clk": 1e6, "h_active": 8, "h_blanking": 6, "h_sync_offset": 1, "h_sync_width": 2,
       "v_active": 6, "v_blanking": 3, "v_sync_offset": 1, "v_sync_width": 1}
SW, SH = 4, 3


class DUT(LiteXModule):
    """CE=1: single-clock mode of the ULX5M 1G+DVI SoC - VTG and scaler advance 1 cycle in 5, the source may
    only hand over a pixel when ready & ce, and the line-buffer write is gated by ce (Scaler2x.we_ce)."""
    def __init__(self, ce_mode=False, hdouble=True):
        self.ce = Signal(reset=1)
        sw = SW if hdouble else 2*SW
        if ce_mode:
            self.vtg = CEInserter()(VideoTimingGenerator(TIM))
            self.sc  = CEInserter()(Scaler2x(sw, hdouble=hdouble))
            cnt = Signal(3)
            self.sync += If(cnt == 4, cnt.eq(0)).Else(cnt.eq(cnt + 1))
            self.comb += [self.ce.eq(cnt == 4), self.vtg.ce.eq(self.ce), self.sc.ce.eq(self.ce),
                          self.sc.we_ce.eq(self.ce)]
        else:
            self.vtg = VideoTimingGenerator(TIM)
            self.sc  = Scaler2x(sw, hdouble=hdouble)
        self.pix_ready = Signal()
        self.comb += [self.vtg.source.connect(self.sc.vtg), self.pix_ready.eq(self.sc.pix.ready & self.ce)]


def rgb(p):  # rgb565 -> the 8-bit channels the scaler emits
    return ((p >> 11) & 31) << 3, ((p >> 5) & 63) << 2, (p & 31) << 3


def run(ce_mode=False, hdouble=True):
    """hdouble=False (TASK-5047): 2*SW x SH frame, only lines doubled (640x240 -> 640x480)."""
    dut = DUT(ce_mode, hdouble)
    sw = SW if hdouble else 2*SW
    random.seed(5040)
    frames_shown = []   # list of dict (X,Y)->(r,g,b)
    errors = []
    underflows = [0]

    @passive
    def feeder():
        f = 0
        while True:
            for y in range(SH):
                for x in range(sw):
                    yield dut.sc.pix.data.eq((f*64 + y*8 + x) & 0xffff)
                    yield dut.sc.pix.last.eq(int(x == sw-1 and y == SH-1))
                    yield dut.sc.pix.valid.eq(1)
                    yield
                    while not (yield dut.pix_ready):
                        yield
                    yield dut.sc.pix.valid.eq(0)
                    # random gap, but never long enough to starve (a pixel is needed every 2nd cycle at most)
                    if random.random() < (0.3 if (hdouble or ce_mode) else 0.0):   # no-hdouble 2 clocks: 1 px/cycle
                        yield
            f += 1

    def monitor():
        X = Y = 0
        cur = {}
        prev_de = 0
        for _ in range(14*9*12*(5 if ce_mode else 1)):
            if not (yield dut.ce):
                yield
                continue
            de = yield dut.sc.source.de
            vs = yield dut.sc.source.vsync
            if (yield dut.sc.underflow) and (yield dut.ce):
                underflows[0] += 1
            if de:
                cur[(X, Y)] = ((yield dut.sc.source.r), (yield dut.sc.source.g), (yield dut.sc.source.b))
                X += 1
            elif prev_de:
                X = 0
                Y += 1
            if vs and cur:
                frames_shown.append(cur)
                cur = {}
                X = Y = 0
            prev_de = de
            yield

    run_simulation(dut, [feeder(), monitor()])

    # Frames with any non-black pixel are "shown" frames; identify the source frame from pixel (0,0).
    shown = [fr for fr in frames_shown if any(v != (0, 0, 0) for v in fr.values())]
    ok = 0
    for fr in shown:
        if len(fr) != 48:
            errors.append("frame with %d pixels" % len(fr))
            continue
        # frame index from pixel (1,0) (pixel (0,0) of frame 0 is black by construction)
        r, g, b = fr[(2, 0)]
        p1 = ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)
        f = (p1 - 1) // 64
        for (X, Y), v in fr.items():
            exp = rgb((f*64 + (Y//2)*8 + (X//2 if hdouble else X)) & 0xffff)
            if v != exp:
                errors.append("frame %d (%d,%d): got %s exp %s" % (f, X, Y, v, exp))
        ok += 1
    print("[%s] frames seen %d, shown %d, checked %d, underflows %d, errors %d" %
          (("ce 1/5" if ce_mode else "2 clocks") + ("" if hdouble else ", 640x240"), len(frames_shown), len(shown), ok, underflows[0], len(errors)))
    for e in errors[:10]:
        print("  ", e)
    passed = ok >= 3 and not errors and underflows[0] == 0
    print("PASS" if passed else "FAIL")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(run(False) | run(True) | run(False, hdouble=False) | run(True, hdouble=False))
