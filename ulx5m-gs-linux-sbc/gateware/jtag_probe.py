#
# JTAG snapshot probe for the Ethernet design (TASK-4999).
#
# Publishes internal state through gateware/verilog/jtag_mailbox.v (CC_SERDES regfile), read on the
# Pi with tools/jtag_mailbox.py over the JTAG TAP -- no UART, no extra pins, no extra hardware.
# The mailbox runs in "mb" = the raw 25 MHz oscillator (no PLL), so it reports even when a PLL
# does not lock. Everything else is MultiReg'd into "mb" (counters change slowly: a torn read is
# possible but rare and visible as an odd value).
#
# Snapshot layout (decoded by tools/jtag_mailbox.py --eth):
#   w16[0] flags   b0 pll_tx lock, b1 pll_sys lock, b2 sys rst, b3 eth_tx rst, b4 eth_rx rst,
#                  b5 PHY RESET_N asserted (crg.reset), b6 MDIO done, b7 in-band link,
#                  b9:8 in-band speed, b10 RX_CTL pin (raw), b11 last PHY-RX frame had error
#   w16[1] {PHY RX frames[7:0] (eth_rx), PHY TX frames[7:0] (eth_tx)}
#   w16[2] {MAC preamble errors[7:0], MAC CRC errors[7:0]}
#   w16[3] {ARP RX frames[7:0], ARP TX frames[7:0]}
#   w16[4] last PHY-RX frame bytes 0,1   (byte0 in [15:8])
#   w16[5] last PHY-RX frame bytes 2,3
#   w15[0] last PHY-RX frame bytes 6,7   (byte6 low 7 bits)
#   w15[1] last PHY-RX frame bytes 8,9
#   w15[2] last PHY-RX frame bytes 20,21 (ethertype when an 8-byte preamble is present)
#   w15[3] eth_rx  (RXC) cycles per 2**14 mb cycles (25 MHz -> 16384)
#   w15[4] eth_tx  cycles per 2**14 mb cycles
#   w15[5] sys     cycles per 2**14 mb cycles
#   w15[6] {ICMP RX frames[7:0], ICMP TX frames[6:0]}
#   w15[7] last PHY-RX frame length in bytes
#   w15[8] {MAC TX frames (sys, into the TX datapath)[7:0], MAC RX frames (sys, out of RX datapath)[6:0]}
#
# SPDX-License-Identifier: BSD-2-Clause

import os

from migen import *
from migen.genlib.cdc import MultiReg

from litex.gen import LiteXModule

from mdio_diag import FreqMeter


def _frame_counter(module, cd, ep, width=8):
    """Frames (valid & ready & last) on endpoint `ep` in clock domain `cd`."""
    cnt = Signal(width)
    getattr(module.sync, cd).__iadd__(If(ep.valid & ep.ready & ep.last, cnt.eq(cnt + 1)))
    return cnt


class EthJTAGProbe(LiteXModule):
    def flag(self, name):
        """A sticky/static yes-no flag in the "mb" domain (for PLLStaticBits)."""
        return self.flags_mb[name]

    def __init__(self, platform, soc, clk25, rx_ctl_pad=None, with_mailbox=True, mb_clk=None):
        # mb_clk: default the raw 25 MHz oscillator (PLL-free). With PLL static bits there are no
        # global clock nets left for clk25 (GateMate: 4, PLL outputs must use them), so the caller
        # passes the eth_tx PLL clock (25 MHz, measured locked in LOWPOWER builds) instead.
        mb_clk = clk25 if mb_clk is None else mb_clk
        self.cd_mb = ClockDomain()
        self.comb += self.cd_mb.clk.eq(mb_clk)
        por = Signal(4)
        self.sync.mbpor += If(~por[3], por.eq(por + 1))
        self.cd_mbpor = ClockDomain(reset_less=True)
        self.comb += [self.cd_mbpor.clk.eq(mb_clk), self.cd_mb.rst.eq(~por[3])]

        ethphy = soc.ethphy
        core   = soc.stack.core

        def to_mb(sig):
            s = Signal(len(sig))
            self.specials += MultiReg(sig, s, "mb")
            return s

        # ---- flags -------------------------------------------------------------------------------
        pll_tx = soc.crg.pll_tx.locked if hasattr(soc.crg, "pll_tx") else C(1, 1)
        pll_sys = soc.crg.pll_sys.locked
        rx_ctl_raw = Signal()
        if rx_ctl_pad is not None:
            self.comb += rx_ctl_raw.eq(rx_ctl_pad)
        last_err = Signal()
        flags = Cat(
            pll_tx, pll_sys,
            ResetSignal("sys"), ResetSignal("eth_tx"), ResetSignal("eth_rx"),
            ethphy.crg.reset,
            soc.probe_mdio_done, soc.probe_link_up, soc.probe_speed,
            rx_ctl_raw, last_err,
        )

        # ---- PHY-level frame capture (eth_rx) ----------------------------------------------------
        src = ethphy.source
        idx      = Signal(15)
        cur      = {i: Signal(8) for i in (0, 1, 2, 3, 6, 7, 8, 9, 20, 21)}
        last     = {i: Signal(8) for i in cur}
        last_len = Signal(15)
        cur_err  = Signal()
        rx_sync = self.sync.eth_rx
        rx_sync += If(src.valid & src.ready,
            idx.eq(idx + 1),
            *[If(idx == i, cur[i].eq(src.data[:8])) for i in cur],
            If(src.error != 0, cur_err.eq(1)),
            If(src.last,
                idx.eq(0), cur_err.eq(0),
                last_len.eq(idx + 1),
                last_err.eq(cur_err | (src.error != 0)),
                *[last[i].eq(cur[i]) for i in cur],
            )
        )
        phy_rxf = _frame_counter(self, "eth_rx", ethphy.source)
        phy_txf = _frame_counter(self, "eth_tx", ethphy.sink)
        # Sticky yes/no flags (for PLLStaticBits), all synchronised into "mb".
        self._flags = {}
        def sticky(name, cd, cond):
            f = Signal(name="flag_" + name)
            getattr(self.sync, cd).__iadd__(If(cond, f.eq(1)))
            self._flags[name] = f
        sticky("phy_tx_any", "eth_tx", ethphy.sink.valid & ethphy.sink.ready & ethphy.sink.last)
        sticky("phy_rx_any", "eth_rx", ethphy.source.valid & ethphy.source.ready & ethphy.source.last)
        sticky("phy_tx_valid", "eth_tx", ethphy.sink.valid)
        sticky("phy_rx_valid", "eth_rx", ethphy.source.valid)
        sticky("phy_tx_vr", "eth_tx", ethphy.sink.valid & ethphy.sink.ready)
        sticky("phy_tx_vl", "eth_tx", ethphy.sink.valid & ethphy.sink.last)

        # ---- MAC / ARP / ICMP counters (sys) -----------------------------------------------------
        sticky("mac_tx_any", "sys", core.mac.core.sink.valid & core.mac.core.sink.ready & core.mac.core.sink.last)
        sticky("mac_rx_any", "sys", core.mac.core.source.valid & core.mac.core.source.ready & core.mac.core.source.last)
        sticky("mac_tx_valid", "sys", core.mac.core.sink.valid)
        sticky("mac_tx_vr", "sys", core.mac.core.sink.valid & core.mac.core.sink.ready)
        # Per-stage TX pipeline flags: txs<i>_vl = a whole frame left stage i (valid&ready&last).
        # Stages (with_sys_datapath): 1 padding, 2 crc, 3 preamble (sys), 4 cdc, 5 gap (eth_tx).
        for i, stage in enumerate(core.mac.core.tx_datapath.pipeline[1:-1], start=1):
            if not hasattr(stage, "source"):
                continue
            cd = "eth_tx" if i >= 4 else "sys"
            src_ = stage.source
            sticky("txs%d_vl" % i, cd, src_.valid & src_.ready & src_.last)
            sticky("txs%d_v" % i, cd, src_.valid)
        sticky("arp_rx_any", "sys", core.arp.rx.sink.valid & core.arp.rx.sink.ready & core.arp.rx.sink.last)
        rxdp = core.mac.core.rx_datapath
        pre_err = rxdp.preamble_errors.status[:8] if hasattr(rxdp, "preamble_errors") else C(0, 8)
        crc_err = rxdp.crc_errors.status[:8]      if hasattr(rxdp, "crc_errors")      else C(0, 8)
        arp_rx  = _frame_counter(self, "sys", core.arp.rx.sink)
        arp_tx  = _frame_counter(self, "sys", core.arp.tx.source)
        icmp_rx = _frame_counter(self, "sys", core.icmp.rx.sink)
        icmp_tx = _frame_counter(self, "sys", core.icmp.tx.source)
        mac_tx  = _frame_counter(self, "sys", core.mac.core.sink)
        mac_rx  = _frame_counter(self, "sys", core.mac.core.source)

        # ---- frequency meters (gate 2**14 mb cycles) ---------------------------------------------
        to_mbd = ClockDomainsRenamer({"sys": "mb"})
        self.fm_rx  = to_mbd(FreqMeter("eth_rx", gate_bits=14, width=15))
        self.fm_tx  = to_mbd(FreqMeter("eth_tx", gate_bits=14, width=15))
        self.cd_sysm = ClockDomain(reset_less=True)
        self.comb += self.cd_sysm.clk.eq(ClockSignal("sys"))
        self.fm_sys = to_mbd(FreqMeter("sysm", gate_bits=14, width=15))

        b = lambda hi, lo: Cat(to_mb(lo), to_mb(hi))   # {hi, lo}
        w16 = Cat(
            to_mb(flags)[:16] if len(flags) >= 16 else Cat(to_mb(flags), C(0, 16 - len(flags))),
            b(phy_rxf, phy_txf),
            b(pre_err, crc_err),
            b(arp_rx, arp_tx),
            b(last[0], last[1]),
            b(last[2], last[3]),
        )
        w15 = Cat(
            Cat(to_mb(last[7]), to_mb(last[6])[:7]),
            Cat(to_mb(last[9]), to_mb(last[8])[:7]),
            Cat(to_mb(last[21]), to_mb(last[20])[:7]),
            self.fm_rx.value, self.fm_tx.value, self.fm_sys.value,
            Cat(to_mb(icmp_tx)[:7], to_mb(icmp_rx)),
            to_mb(last_len),
            Cat(to_mb(mac_rx)[:7], to_mb(mac_tx)),
        )
        assert len(w16) == 96 and len(w15) == 135, (len(w16), len(w15))
        self.flags_mb = {n: to_mb(f) for n, f in self._flags.items()}
        self.flags_mb["pll_sys_locked"] = to_mb(pll_sys)
        self.flags_mb["mdio_done"] = to_mb(soc.probe_mdio_done)
        self.flags_mb["phy_out_of_reset"] = to_mb(~ethphy.crg.reset)
        # sys clock health: 12.5 MHz vs mb (25 MHz eth_tx) -> 8192 per 2**14, accept +-10 %;
        # generic: expected = 16384 * f_sys / 25e6.
        exp = int(16384 * soc.sys_clk_freq / 25e6)
        sys_ok = Signal()
        self.sync.mb += sys_ok.eq((self.fm_sys.value > int(exp * 0.9)) & (self.fm_sys.value < int(exp * 1.1)))
        self.flags_mb["sys_freq_ok"] = sys_ok
        # eth_tx vs mb: meaningful only when mb = clk25 (raw oscillator).
        tx_ok, sys_hi, sys_mid = Signal(), Signal(), Signal()
        self.sync.mb += [
            tx_ok.eq((self.fm_tx.value > 14745) & (self.fm_tx.value < 18022)),
            sys_hi.eq(self.fm_sys.value > 12288),    # sys > 18.75 MHz (vs 25 MHz mb)
            sys_mid.eq(self.fm_sys.value > 6144),    # sys >  9.4 MHz
        ]
        self.flags_mb["eth_tx_freq_ok"] = tx_ok
        tx_hi, tx_lo, tx_2x = Signal(), Signal(), Signal()
        self.sync.mb += [
            tx_hi.eq(self.fm_tx.value > 18022),     # eth_tx > 27.5 MHz
            tx_lo.eq(self.fm_tx.value < 14745),     # eth_tx < 22.5 MHz
            tx_2x.eq(self.fm_tx.value > 29491),     # eth_tx > 45 MHz
        ]
        self.flags_mb["tx_gt_27m5"], self.flags_mb["tx_lt_22m5"], self.flags_mb["tx_gt_45m"] = tx_hi, tx_lo, tx_2x
        self.flags_mb["sys_gt_18m75"] = sys_hi
        self.flags_mb["sys_gt_9m4"] = sys_mid
        self.flags_mb["one"] = C(1, 1)
        self.flags_mb["zero"] = C(0, 1)
        # Snapshot for other consumers (L2 beacon): 231 bits, "mb" domain.
        self.snapshot = Cat(w16, w15)
        if not with_mailbox:
            return
        self.specials += Instance("jtag_mailbox",
            p_GAP_LOG2 = 18,   # one pass per ~0.08 s (fewer accesses -> less chance of a port stall)
            i_clk = ClockSignal("mb"), i_rst = ResetSignal("mb"),
            i_w16 = w16, i_w15 = w15,
        )
        platform.add_source(os.path.join(os.path.dirname(__file__), "verilog", "jtag_mailbox.v"))
