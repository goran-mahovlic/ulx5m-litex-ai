#
# PLL serial status channel (TASK-4999): internal state -> JTAG, no pins, no UART, no SerDes.
#
# Two spare CC_PLLs are fed from fabric through USR_CLK_REF with a reference of either clk25/2
# (12.5 MHz) or clk25/3 (8.33 MHz). The PLL fine-tune value, which the Pi reads at any time over
# the JTAG TAP (STATUS_PLLx instruction, tools/pll_serial_rx.py), is ~0x096 for /2 and ~0x018 for
# /3 -- one sample decides the level, switching is immediate (measured on the ULX5M-GS 23.9.2026).
#   clock PLL: level alternates every bit period (marks bit boundaries)
#   data  PLL: level = current bit (/2 = 1, /3 = 0)
# Frame: 12 x '1' (sync), '0', then each byte as '0' + 8 bits LSB first (max 9 ones in a row,
# so the sync is unique). Bit period 2**bit_log2 cycles of the 25 MHz oscillator.
#
# SPDX-License-Identifier: BSD-2-Clause

from functools import reduce

from migen import *

from litex.gen import LiteXModule


class PLLSerialOut(LiteXModule):
    """Runs in clock domain `cd` (must be the raw 25 MHz oscillator); `data` is sampled there."""
    def __init__(self, data, cd="mb", bit_log2=23, div1=2, div0=3, perf_md="LOWPOWER"):
        # div1/div0: reference divider for level 1/0. 23.9. (0.9 V) the levels were told apart by
        # fine-tune (/2 ~0x096, /3 ~0x018). At 1.1 V (TASK-5007) LOWPOWER /2../4 all LOCK with the
        # same fine-tune and some PLL slots sit in underflow even at /2. MEASURED 24.9. (fab3, 1.1 V):
        # perf_md="ECONOMY", /2 -> LOCKED ft 0x190..0x290, /8 (and /4) -> LOCK_IN+underflow ft 0x004,
        # switching both ways within one 0.67 s step -> decode ft > 0x40 as 1.
        nbytes = (len(data) + 7) // 8
        latched = Signal(8 * nbytes)
        seq = [C(1, 1)] * 12 + [C(0, 1)]
        for i in range(nbytes):
            seq += [C(0, 1)] + [latched[8*i + b] for b in range(8)]
        n = len(seq)
        self.nbits = n

        sync  = getattr(self.sync, cd)
        tick  = Signal(bit_log2)
        idx   = Signal(max=n)
        clk_level = Signal()
        bit   = Signal()
        # Registered: the 300+-input mux does not close 25 MHz, and a combinational level into the
        # reference divider made the data PLL see irregular periods (ft ~0x0E2 = "/2.5", never 0).
        # MEASURED 24.9. (s5). idx changes once per bit period, so one cycle of latency is harmless.
        sync_ = getattr(self.sync, cd)
        sync_ += bit.eq(Array(seq)[idx])
        sync += [
            tick.eq(tick + 1),
            If(tick == (2**bit_log2 - 1),
                clk_level.eq(~clk_level),
                If(idx == n - 1,
                    idx.eq(0),
                    latched.eq(data),
                ).Else(
                    idx.eq(idx + 1),
                )
            )
        ]
        # Reference generators: level 1 -> /div1, level 0 -> /div0.
        self.loads = []
        for name, level in (("clk", clk_level), ("dat", bit)):
            d = Signal(max=max(div0, div1) + 1)
            g = Signal()
            per = Signal(max=max(div0, div1) + 1)
            self.comb += per.eq(Mux(level, div1, div0))
            sync += [
                If(d >= per - 1, d.eq(0)).Else(d.eq(d + 1)),
                g.eq((d < (per >> 1)) & (fr | (not zero_stop))),
            ]
            out = Signal()
            self.specials += Instance("CC_PLL",
                name = "pllser_" + name,
                attr = {("keep", "true")},
                p_REF_CLK = "12.5", p_OUT_CLK = out_clk, p_PERF_MD = perf_md,
                p_LOW_JITTER = 1, p_CI_FILTER_CONST = 2, p_CP_FILTER_CONST = 4, p_LOCK_REQ = 0,
                i_CLK_REF = 0, i_USR_CLK_REF = g, i_CLK_FEEDBACK = 0, i_USR_LOCKED_STDY_RST = 0,
                o_CLK0 = out,
            )
            # Keep the PLL output loaded (a 1-bit toggle nobody reads is still a used output).
            t = Signal()
            setattr(self, "cd_pllser_" + name, ClockDomain("pllser_" + name, reset_less=True))
            self.comb += getattr(self, "cd_pllser_" + name).clk.eq(out)
            out.attr.add(("clkbuf_inhibit", 1))
            getattr(self.sync, "pllser_" + name).__iadd__(t.eq(~t))
            setattr(self, "toggle_" + name, t)
            self.loads.append(t)


class PLLStaticBits(LiteXModule):
    """Live static bits over ONE spare PLL, 2 bits per PLL (4 reference levels, MEASURED on the
    ULX5M-GS 23.9.2026, LOWPOWER, REF_CLK 12.5 / OUT 25, fine-tune = STATUS bits 11:2):
        value 3 -> clk25/2   (12.5 MHz)  ft ~0x09A  LOCKED
        value 2 -> clk25/2.5 (10 MHz)    ft ~0x046  LOCKED
        value 1 -> clk25/3   (8.33 MHz)  ft ~0x01A  LOCKED
        value 0 -> clk25/4   (6.25 MHz)  ft ~0x004  LOCK_IN + underflow flag
    value = 2*bits[1] + bits[0]; a level change shows within < 1 s. Decoder: tools/pll_serial_rx.py
    MEASURED: the PLL output must really be used, otherwise its status does not follow the
    reference -> the PLL clocks a toggle that the caller must route to a pin (self.load).
    PLL outputs need a global clock net (GateMate has 4), so a design usually has room for one.
    PLL instance names: pllbit<i> (see routed JSON / NEXTPNR_BEL for the PLLn placement)."""
    def __init__(self, bits, cd="mb"):
        assert len(bits) in (1, 2)
        if len(bits) == 1:
            bits = [bits[0], bits[0]]
        sync = getattr(self.sync, cd)
        d   = Signal(3, name="pllbit0_d")
        g   = Signal(name="pllbit0_g")
        alt = Signal(name="pllbit0_alt")
        per = Signal(3, name="pllbit0_per")
        v   = Cat(bits[0], bits[1])
        self.comb += Case(v, {
            3: per.eq(2),
            2: per.eq(Mux(alt, 3, 2)),
            1: per.eq(3),
            0: per.eq(4),
        })
        sync += [
            If(d >= per - 1, d.eq(0), alt.eq(~alt)).Else(d.eq(d + 1)),
            g.eq(d < (per >> 1)),
        ]
        out = Signal(name="pllbit0_clk")
        self.specials += Instance("CC_PLL",
            name = "pllbit0",
            attr = {("keep", "true")},
            p_REF_CLK = "12.5", p_OUT_CLK = "25.0", p_PERF_MD = "LOWPOWER",
            p_LOW_JITTER = 1, p_CI_FILTER_CONST = 2, p_CP_FILTER_CONST = 4, p_LOCK_REQ = 0,
            i_CLK_REF = 0, i_USR_CLK_REF = g, i_CLK_FEEDBACK = 0, i_USR_LOCKED_STDY_RST = 0,
            o_CLK0 = out,
        )
        self.cd_pllbit0 = ClockDomain("pllbit0", reset_less=True)
        self.comb += self.cd_pllbit0.clk.eq(out)
        out.attr.add(("clkbuf_inhibit", 1))
        t = Signal(4, name="pllbit0_t")
        self.sync.pllbit0 += t.eq(t + 1)
        self.load = t[3]


class PLLFreqProbe(LiteXModule):
    """Spare PLL as a frequency meter (TASK-4999): USR_CLK_REF = `ref` (a fabric clock/toggle).
    PLL REF_CLK 12.5 / OUT 25 LOWPOWER; MEASURED fine-tune vs reference on the ULX5M-GS:
    6.25 MHz -> 0x004 (LOCK_IN, underflow), 8.33 -> 0x01A, 10.0 -> 0x046, 12.5 -> 0x09A.
    `load` must be routed to a pin (otherwise the status does not follow the reference)."""
    def __init__(self, ref):
        out = Signal(name="pllbit0_clk")
        self.specials += Instance("CC_PLL",
            name = "pllbit0",
            attr = {("keep", "true")},
            p_REF_CLK = "12.5", p_OUT_CLK = "25.0", p_PERF_MD = "LOWPOWER",
            p_LOW_JITTER = 1, p_CI_FILTER_CONST = 2, p_CP_FILTER_CONST = 4, p_LOCK_REQ = 0,
            i_CLK_REF = 0, i_USR_CLK_REF = ref, i_CLK_FEEDBACK = 0, i_USR_LOCKED_STDY_RST = 0,
            o_CLK0 = out,
        )
        self.cd_pllbit0 = ClockDomain("pllbit0", reset_less=True)
        self.comb += self.cd_pllbit0.clk.eq(out)
        out.attr.add(("clkbuf_inhibit", 1))
        t = Signal(4, name="pllbit0_t")
        self.sync.pllbit0 += t.eq(t + 1)
        self.load = t[3]


class PLLLevelBits(LiteXModule):
    """Static 1-bit flags at 1.1 V (TASK-4999, 24.9.): one ECONOMY CC_PLL per flag, reference
    clk/2 for 1 and clk/8 for 0, from a register in domain `cd` (25 MHz osc). MEASURED (fab3):
    /2 -> LOCKED ft 0x190..0x29x, /8 -> underflow or LOCKED at ft ~0x07E -> read ft > 0x100 as 1.
    A flag change shows after < 1 s (re-acquisition); read with tools/pll_serial_rx.py scan.
    self.loads must be routed to pins (a PLL whose output is unused does not track)."""
    def __init__(self, flags, cd="osc", perf_md="ECONOMY", out_clk="25.0", zero_stop=False):
        # out_clk/zero_stop (TASK-4999, 24.9. pm): at OUT 25 MHz the ECONOMY VCO sits at the bottom of
        # its range and drifts into underflow even for a '1' (PLL1 slot, 14:00). OUT 100 MHz keeps the
        # VCO mid-range; zero_stop=True sends '0' as a STOPPED reference (cannot lock) instead of /8
        # (which sometimes locks). Decode by the LOCKED state (status bits 13:12 == 2), not by ft.
        sync = getattr(self.sync, cd)
        self.loads = []
        for i, f in enumerate(flags):
            fr  = Signal(name="pllflag%d_r" % i)
            d   = Signal(3, name="pllflag%d_d" % i)
            g   = Signal(name="pllflag%d_g" % i)
            per = Signal(4, name="pllflag%d_per" % i)
            sync += fr.eq(f)
            self.comb += per.eq(Mux(fr, 2, 8))
            sync += [
                If(d >= per - 1, d.eq(0)).Else(d.eq(d + 1)),
                g.eq((d < (per >> 1)) & (fr | (not zero_stop))),
            ]
            out = Signal(name="pllflag%d_clk" % i)
            self.specials += Instance("CC_PLL",
                name = "pllflag%d" % i,
                attr = {("keep", "true")},
                p_REF_CLK = "12.5", p_OUT_CLK = out_clk, p_PERF_MD = perf_md,
                p_LOW_JITTER = 1, p_CI_FILTER_CONST = 2, p_CP_FILTER_CONST = 4, p_LOCK_REQ = 0,
                i_CLK_REF = 0, i_USR_CLK_REF = g, i_CLK_FEEDBACK = 0, i_USR_LOCKED_STDY_RST = 0,
                o_CLK0 = out,
            )
            out.attr.add(("clkbuf_inhibit", 1))
            cdn = "pllflag%d" % i
            setattr(self, "cd_" + cdn, ClockDomain(cdn, reset_less=True))
            self.comb += getattr(self, "cd_" + cdn).clk.eq(out)
            t = Signal(name="pllflag%d_t" % i)
            getattr(self.sync, cdn).__iadd__(t.eq(~t))
            self.loads.append(t)
