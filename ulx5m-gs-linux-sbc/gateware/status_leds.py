#
# Bring-up status LEDs for the ULX5M-GS. Outputs active-HIGH self.led[7:0].
#
# NOTE on polarity and pin order: the ULX5M-GS user LEDs are ACTIVE-HIGH (drive
# the pin to 1 to light the LED). The litex-boards `user_led_n` name implies
# active-low and uses an A/B pin order for bits 4-7 that does not match this
# board; the target here adds its own `status_led` extension with the correct
# ball map and drives it active-high (no inversion). See target_eth.py.
#
#   LED ladder
#   [7] heartbeat  free-running ~1 Hz counter bit (proves sys clock + reset released)
#   [6] rst_seen   sticky, set after reset deasserts
#   [5] tx_active  a frame sent to the PHY (target: any MAC TX frame), stretched ~0.1 s
#   [4] rx_active  a frame received from the PHY (target: any MAC RX frame), stretched
#   [3][2]         RGMII in-band speed status (PHY inter-frame status nibble):
#                  00 = 10M or no RXC, 01 (led2 alone) = 100M <- expected good state,
#                  10 (led3 alone) = 1G. Stays 00 if the RXC never toggles.
#   [1] link_up    RGMII in-band link status. Pass 0 if unavailable.
#   [0] mdio_done  MDIO bring-up sequencer finished (KSZ9031 forced to 100-FD).
#                  Pass 0 if there is no sequencer.
#
# Bring-up glance, all good = LEDs 7(blink) 6 2 1 0 on, 3 off.
#
# All signal inputs must be in the LED clock domain (sys).
#
# SPDX-License-Identifier: BSD-2-Clause

import math
from migen import *
from litex.gen import LiteXModule


class StatusLeds(LiteXModule):
    def __init__(self, sys_clk_freq, rx_active, tx_active, link_up=0, speed=0, mdio_done=0):
        self.led = Signal(8)   # active-high; the target drives the pads directly.

        # Heartbeat: proves the sys clock is running AND reset has released. Pick the
        # counter bit closest to a ~1 Hz toggle for the given clock.
        hb = Signal(32)
        self.sync += hb.eq(hb + 1)
        hb_bit = max(1, int(round(math.log2(sys_clk_freq))) - 1)   # 16 MHz -> bit 23 (~1 Hz)
        heartbeat = hb[hb_bit]

        # Sticky "reset released at least once": 0 while the sys reset is asserted (reg
        # cleared), latches 1 on the first clock after release and stays.
        rst_seen = Signal()
        self.sync += rst_seen.eq(1)

        # Activity stretchers (~0.1 s) so a single-packet blip is visible to the eye.
        stretch = max(2, int(sys_clk_freq // 10))
        rx_cnt = Signal(max=stretch + 1)
        tx_cnt = Signal(max=stretch + 1)
        self.sync += [
            If(rx_active, rx_cnt.eq(stretch)).Elif(rx_cnt != 0, rx_cnt.eq(rx_cnt - 1)),
            If(tx_active, tx_cnt.eq(stretch)).Elif(tx_cnt != 0, tx_cnt.eq(tx_cnt - 1)),
        ]

        speed = Signal(2) if isinstance(speed, int) else speed
        self.comb += [
            self.led[7].eq(heartbeat),
            self.led[6].eq(rst_seen),
            self.led[5].eq(tx_cnt != 0),
            self.led[4].eq(rx_cnt != 0),
            self.led[3].eq(speed[1]),         # in-band speed MSB (1G)
            self.led[2].eq(speed[0]),         # in-band speed LSB (100M when alone)
            self.led[1].eq(link_up),
            self.led[0].eq(mdio_done),
        ]
