# GateMate 100 Mbps RGMII clocking

Tags: [HW-VERIFIED] = confirmed on hardware; [INFERRED] = from code/toolchain analysis.

## RGMII clock rates
| Speed | RXC | TXC | data |
|---|---|---|---|
| 10M | 2.5 MHz | 2.5 MHz | nibble, rising edge |
| 100M | 25 MHz | 25 MHz | nibble duplicated both edges |
| 1000M | 125 MHz | 125 MHz | byte/clk DDR |

RXC is PHY-sourced; TXC is MAC/FPGA-sourced (forwarded out). [HW-VERIFIED]

This board runs the link at **100 Mbps** by default: RXC is 25 MHz on `IO_EB_A7`,
a non-clock-capable pin, and the PHY datapath runs in 10/100 nibble-gearing mode
(`fixed_100m=True`).

Gigabit is **not blocked by that pin** (measured 2026-09-21, TASK-4961): it is
blocked by timing. `--gbe` builds, but the 125 MHz PHY domains close at only
52.8-65.5 MHz post-route across seeds -- a ~2x deficit, dominated by *routing* on
LiteEth's async-FIFO gray counters, not by the RGMII pads. Details and the full
measurement table: docs/GBE_FEASIBILITY_20260921_TASK-4961.md.

## The split-clock architecture (proven) [HW-VERIFIED]
A single 25 MHz fabric clock **never closes worst-corner** timing on this board
(measured 16-19 MHz Fmax across seeds). The fix: **two CC_PLLs off the 25 MHz
oscillator**:
- **PLL#1: 25 -> 25 MHz = TX line clock.** Forwarded to the PHY as TXC via
  CC_ODDR. Drives ONLY the thin RGMII TX serdes. Closes with large margin.
- **PLL#2: 25 -> 16 MHz = fabric clock.** Runs the whole packet pipeline (MAC +
  IP/UDP + application logic). The relaxed 62.5 ns budget removes the
  intermittent single-bit corruption a 25 MHz fabric shows. Fabric Fmax
  ~18.5-22.6 MHz worst-corner (passes 16 with margin).
- **RX: RXC (25 MHz) used raw off fabric routing**, feeds the thin RX capture ->
  MAC RX async FIFO -> fabric domain.

## Mapping onto LiteEth
LiteEth `with_sys_datapath=True` puts the MAC buffers + IP/UDP + the sys-domain
application (here, the UDP echo) in `sys`, leaving only thin DDR serdes in
`eth_tx`/`eth_rx`:
- `sys`    = PLL#2 output (16 MHz default). Runs the LiteEth core + application.
  100M line rate = 12.5 MB/s; at dw=8 the sys clock needs >= 12.5 MHz (16 MHz is
  fine). If you add heavier sys-domain logic, re-measure worst-corner Fmax and
  set sys as high as still closes.
- `eth_tx` = PLL#1 output, 25 MHz. Thin RGMII TX serdes; TXC forwarded via CC_ODDR.
- `eth_rx` = RXC (`IO_EB_A7`), raw fabric routing. Thin RGMII RX capture (CC_IDDR).
- CDC sys<->eth_tx and eth_rx<->sys = LiteEth async FIFOs (built in).

## THREE HARD TRAPS (honor these or the build breaks)
1. **CC_BUFG on the RXC pin does NOT crash nextpnr** - corrected 2026-09-21
   (TASK-4961, see docs/GBE_FEASIBILITY_20260921_TASK-4961.md). A build with
   `rxc_global=True` inserts `CC_BUFG on ...eth_rx_clk[0]` (3 CC_BUFG total vs. 2
   with `clkbuf_inhibit`) and completes to a bitstream. The real cost is a third
   *global clock* net: with it, some seeds stop routing
   (`Failed to route arc ... GLBOUT0 -> CPE.CLK_int`). So the default stays
   `clkbuf_inhibit` for routability, NOT because the primitive is forbidden.
2. **LiteX `GateMatePLL` leaves `USR_PLL_LOCKED_STDY` unconnected** and derives
   `locked` from the RAW `USR_PLL_LOCKED`, which can reproduce a seed-dependent
   bring-up hang. [INFERRED, strong] For a hardened cold-boot, instantiate
   `CC_PLL` directly with `o_USR_PLL_LOCKED_STDY` wired and gate reset on the
   STEADY lock of BOTH PLLs, 2-FF synced per domain. This repo uses `GateMatePLL`
   as-is for simplicity (see gateware/crg.py).
3. **No duplicate create_clock on PLL-derived clocks** (crashes nextpnr) and
   **set_clock_groups is unsupported** -> all CDC stays in RTL (LiteEth async
   FIFOs already handle it). Constrain only the RGMII RXC port (40 ns / 25 MHz).
   Judge timing at `time_mode=worst`.

## CC_PLL parameters (if instantiating directly)
```
CC_PLL #(.REF_CLK("25.0"), .OUT_CLK("25.0" | "16.0"), .PERF_MD("SPEED"),
         .LOW_JITTER(1), .CI_FILTER_CONST(2), .CP_FILTER_CONST(4))
  (.CLK_REF(clk25), .USR_CLK_REF(1'b0), .CLK_FEEDBACK(1'b0), .USR_LOCKED_STDY_RST(1'b0),
   .USR_PLL_LOCKED_STDY(locked_stdy), .USR_PLL_LOCKED(locked_raw), .CLK0(out), ...);
```
Use `PERF_MD="SPEED"` for the 1.1 V hardware 100M target.

## Seed reality
Routability is seed-sensitive on this board; a trivial net change can flip which
seeds route. A sequential seed sweep plus on-wire validation is the reliable way
to trust a build. STA-clean does not guarantee correct RXC-domain capture.

```
Clock topology:
  25 MHz osc ─┬─ CC_PLL#1 (25->25) ─ eth_tx ─ CC_ODDR -> TXC + TX serdes
              └─ CC_PLL#2 (25->16) ─ sys ──── LiteEth sys datapath + application
  PHY RXC (IO_EB_A7, raw fabric) ─ eth_rx ─ RX capture ─ async FIFO ─> sys
```
