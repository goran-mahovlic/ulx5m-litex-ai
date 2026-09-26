# HW MDIO sequencer + toolchain 20260920 + ping test — TASK-4963, 2026-09-21

## What was done

1. **`gateware/mdio_sequencer.py`** — a pure hardware clause-22 MDIO write engine
   (`MDIOWriteSequencer`). `LiteEthPHYMDIO` is a CSR bit-bang, and in a design without a CPU
   it is dead weight; after the PHY reset + 10 ms settle, this module writes by itself:
   - reg 9 = 0x0000 (no 1000BASE-T advertisement)
   - reg 4 = 0x0101 (100BASE-TX FD only)
   - reg 0 = 0x1200 (AN enable + restart)

   The KSZ9031 PHYAD strap is not documented for this board revision → the sequence is
   repeated on all 8 possible addresses (PHYAD[2:0]); the KSZ9031 is the only device on the bus,
   and a write to a non-existent address is ignored. MDC 1 MHz, MDIO changes in the
   low half of MDC, Hi-Z between frames and after completion.
   **The MMD2 pad-skew registers are NOT touched** (they kill TX, see LITEETH_INTEGRATION.md).

2. **`gateware/phy_rgmii_gatemate.py`** — new parameter `mdio_sequencer_clk_freq`:
   when it is set, the sequencer is instantiated instead of `LiteEthPHYMDIO` (only one
   may drive the mdc/mdio pads). `target_eth.py` enables it for the 100M build.

3. **`sim/tb_mdio_sequencer.py`** — testbench: samples on the rising edge of MDC
   (exactly like the PHY), reassembles frames, checks the count, the fields, the order
   reg9→reg4→reg0 per address, Hi-Z between frames, and that nothing goes out while
   the PHY reset is active. **PASS 9/9.**

4. **LED diagnostics** (`status_leds.py`): the build ID was replaced with something more useful:

   | LED | Meaning |
   |-----|----------|
   | 7 | heartbeat ~1 Hz |
   | 6 | reset released (sticky) |
   | 5 | TX activity |
   | 4 | RX activity |
   | 3 | in-band speed MSB (on = 1G) |
   | 2 | in-band speed LSB (alone = **100M — the expected good state**) |
   | 1 | link up (in-band status) |
   | 0 | **MDIO sequencer done** |

   All good = 7 (blinking), 6, 2, 1, 0 on; 3 off.

5. **Toolchain** — `~/Programs/oss-cad-suite-20260920/` (Yosys 0.69+75,
   nextpnr-himbaechel 0.11.1-30 with the gatemate uarch, gmpack). Build clean,
   exit 0, timing without negative slack (eth_rx max delay 15.3 ns @ 40 ns).

## Hardware test result (2026-09-21 ~19:35)

- Flash into SRAM via dirtyJtag from the Pi (192.168.10.14): **OK** (100%, Done), 2×.
- `ping -c 5 192.168.10.212` from the Pi after 30 s: **FAIL** — 100% loss,
  `ip neigh` = INCOMPLETE/FAILED. The board replies neither to ARP nor to UDP echo
  (port 7000, also tried from the dell-home container).
- Switch port speed: cannot be read remotely (the switch is not manageable from the network;
  the Pi is on the switch, not directly on the board).
- tcpdump on the Pi is impossible (sudo NOPASSWD only for openFPGALoader/uhubctl).

## How the LEDs bisect the fault (needs a physical look)

| Seen | Conclusion |
|--------|-----------|
| LED0 off | the sequencer did not finish → bug in the FSM / reset hangs |
| LED0+, LED1 off | AN did not finish: MDIO does not reach the PHY (electrical problem, MDC/MDIO swapped?) or the link partner does not cooperate |
| LED0+, LED1+, LED3 on | the PHY is still at 1G → the MDIO writes did not take effect |
| LED0+, LED1+, LED2 alone | **AN = 100M succeeded**; the fault is in the RGMII datapath — first suspect is RX capture on the fabric-routed RXC (IO_EB_A7, skew), then TX |

If it is the last row: the next step is RXC skew (try `rxc_global=True` with a
seed sweep, or CC_IBUF DELAY taps on the rx pads), not MDIO.

## Branches / commits

Branch `mdio-100m-autoneg` in this repo.
