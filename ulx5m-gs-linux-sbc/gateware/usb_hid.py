#
# USB 1.1 low-speed HID host (TASK-5047): Emard's usbh_host_hid (gateware/verilog/usbhost) on USB-C J5, as a
# LiteX CSR peripheral. A userspace daemon (tools/usbhidd) reads the 8-byte boot keyboard report and types into
# /dev/tty1 (TIOCSTI) - the prebuilt 5.14 kernel has no USB stack.
#
# Clock: low speed needs 6 MHz. There is no free global net in the 1G+DVI SoC (sys, gtx0, TXC, grx), so the usb
# clock is <src>/21 from a fabric counter (125 MHz / 21 = 5.952 MHz, -0.79 %, USB LS allows +-1.5 %) on local
# routing (clkbuf_inhibit, like the ref domain). The PHY's RX uses a phase accumulator, the report path is slow.
#
# CSRs: report (64 bit, byte 0 = modifiers, 2..7 = key codes), seq (hid_valid count, 16 bit; read seq, report,
# seq again - a changed seq means a torn read), led (usbh_host_hid debug), ctrl bit 0 = bus reset.
#
# SPDX-License-Identifier: BSD-2-Clause

import os

from migen import *
from migen.genlib.cdc import MultiReg
from migen.genlib.resetsync import AsyncResetSynchronizer

from litex.gen import LiteXModule
from litex.soc.interconnect.csr import CSRStatus, CSRStorage

VDIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "verilog", "usbhost")


class USBHIDHost(LiteXModule):
    def __init__(self, platform, pads, pull, src_domain="gtx0", div=21, rst=0, report_length=8):
        self.cd_usb = ClockDomain()
        self.report = CSRStatus(8*report_length, description="last HID report (byte 0 in bits 7:0)")
        self.seq    = CSRStatus(16, description="HID reports received")
        self.led    = CSRStatus(8,  description="usbh_host_hid debug state")
        self.ctrl   = CSRStorage(1, description="bit 0: USB bus reset")

        # # #

        # 6 MHz on local routing: counter mod div in the 125 MHz source domain, registered output (~50 % duty).
        cnt, clk = Signal(max=div), Signal(name="usb_clk_div")
        clk.attr.add(("clkbuf_inhibit", 1))            # on the FF itself: yosys clkbufmap looks at the driver net
        sd = getattr(self.sync, src_domain)
        sd += [If(cnt == div - 1, cnt.eq(0)).Else(cnt.eq(cnt + 1)), clk.eq(cnt < div//2)]
        self.comb += self.cd_usb.clk.eq(clk)
        self.cd_usb.clk.attr.add(("clkbuf_inhibit", 1))
        self.specials += AsyncResetSynchronizer(self.cd_usb, rst)
        platform.add_period_constraint(self.cd_usb.clk, 1e9*div/125e6)

        self.comb += [pull.p.eq(0), pull.n.eq(0)]      # host: 12k1 pull-downs on D+ and D-

        bus_reset, hid_report, hid_valid, led = Signal(), Signal(8*report_length), Signal(), Signal(8)
        self.specials += MultiReg(self.ctrl.storage[0], bus_reset, "usb")
        self.specials += Instance("usbh_host_hid",
            p_C_usb_speed        = 0,
            p_C_report_length    = report_length,
            p_C_setup_rom_file   = os.path.join(VDIR, "usbh_setup_rom.mem"),
            i_clk                = ClockSignal("usb"),
            i_bus_reset          = bus_reset | ResetSignal("usb"),
            i_usb_dif            = pads.dp,
            io_usb_dp            = pads.dp,
            io_usb_dn            = pads.dm,
            o_led                = led,
            o_hid_report         = hid_report,
            o_hid_valid          = hid_valid,
        )
        for f in ["usbh_host_hid.v", "usbh_sie.v", "usbh_crc5.v", "usbh_crc16.v", "usb_phy_ghdl.v"]:
            platform.add_source(os.path.join(VDIR, f))

        # Capture in the usb domain, cross to sys with MultiReg (the report is static for >= 1 ms between polls).
        rep, seq, valid_d = Signal(8*report_length), Signal(16), Signal()
        self.sync.usb += [valid_d.eq(hid_valid), If(hid_valid & ~valid_d, rep.eq(hid_report), seq.eq(seq + 1))]
        self.specials += [MultiReg(rep, self.report.status), MultiReg(seq, self.seq.status),
                          MultiReg(led, self.led.status)]
