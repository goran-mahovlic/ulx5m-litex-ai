#
# GateMatePLLStdy (TASK-5047): LiteX GateMatePLL with the CC_PLL USR_PLL_LOCKED_STDY output wired out.
#
# DS1001 Fig. 2.33: USR_PLL_LOCKED_STDY rises with the first lock and falls, and STAYS low, on any loss of lock
# until USR_LOCKED_STDY_RST is held high for >= 2 CLK_REF cycles. It is the silicon's own "lock was never lost"
# flag, independent of how (and at what rate) fabric logic samples the raw USR_PLL_LOCKED.
# DS1001 Table 2.19: with LOCK_REQ=1 (LiteX default) the clock OUTPUTS ARE DISABLED while USR_PLL_LOCKED is 0,
# so every raw lock drop also gates the PLL output clock. lock_req=0 keeps the outputs running.
#
# SPDX-License-Identifier: BSD-2-Clause

from migen import *
from migen.fhdl.specials import Instance

from litex.soc.cores.clock.colognechip import GateMatePLL


class GateMatePLLStdy(GateMatePLL):
    def __init__(self, *args, **kwargs):
        GateMatePLL.__init__(self, *args, **kwargs)
        self.locked_stdy = Signal()
        self.stdy_rst    = Signal()     # hold >= 2 clk25 cycles to re-arm locked_stdy

    def do_finalize(self):
        GateMatePLL.do_finalize(self)
        insts = [s for s in self._fragment.specials if isinstance(s, Instance) and s.of == "CC_PLL"]
        assert len(insts) == 1
        for it in insts[0].items:
            if isinstance(it, Instance.Output) and it.name == "USR_PLL_LOCKED_STDY":
                it.expr = self.locked_stdy
            if isinstance(it, Instance.Input) and it.name == "USR_LOCKED_STDY_RST":
                it.expr = self.stdy_rst
