# Drafts for YosysHQ/nextpnr (GateMate CCGM1A2) — TASK-5092, NOT posted (waiting for Goran)

Found while placing the ULX5M-GS Linux SoC for a CCGM1A2. nextpnr `ad8527f8` (main, 29.09.2026), Yosys 0.69+154
(oss-cad-suite 2026-09-28), chipdb from oss-cad-suite 2026-09-28. Patches are on the local branch `t5092-a2`
(`d5bd4b3b`, `0ef67857`; `d7c60c22` and `ffb7650d` are debug-only: GM_CLKDBG/GM_R2DBG/GM_BLOCK_PIP). Full context: `../A2_CCGM1A2_TASK-5092.md`.

---

## 1. Issue: gatemate CCGM1A2 `mirror` strategy: paths between a clock and its `$die1` copy are not timed

**Device:** CCGM1A2, default multi-die strategy `mirror`.

### Summary
`strategy_mirror()` gives every global clock `X` a copy `X$die1` on the second die. A register on die 1B clocked
by `X$die1` that feeds a register on die 1A clocked by `X` is a normal single-clock path in the design, but
nextpnr treats `X` and `X$die1` as unrelated clocks: the path is only listed as "Max delay … -> …" and never compared
with the clock period. The run reports PASS for a path that is ~1.5x the period.

### Reproduction (`mirror_xdie_timing/`)
```verilog
module top(input clk, input d, output q);
  wire gclk, d0, d1;
  CC_BUFG u_bufg (.I(clk), .O(gclk));
  CC_IDDR u_iddr (.D(d), .CLK(gclk), .Q0(d0), .Q1(d1));
  reg r0, r1;
  always @(posedge gclk) begin r0 <= d0 ^ d1; r1 <= r0; end
  assign q = r1;
endmodule
```
```
Net "clk" Loc = "IO_EB_A7";
Net "d"   Loc = "IO_EB_A0";
Net "q"   Loc = "IO_EB_B5";
```
```sh
yosys -q -p "read_verilog top.v; synth_gatemate -top top -luttree -nomx8; write_json top.json"
nextpnr-himbaechel --device CCGM1A2 --vopt force_die=1A --json top.json --vopt ccf=top.ccf --vopt out=top.txt --freq 125
```
Bank EB is bonded to die 1B only, so the IDDR is on 1B (clock `gclk$die1`) and `r0` on 1A (clock `gclk`).

**Actual:**
```
Info: Max frequency for clock 'gclk': 525.21 MHz (PASS at 125.00 MHz)
Info: Max delay posedge gclk$die1 -> posedge gclk     : 11.52 ns
Info: Max delay negedge gclk$die1 -> posedge gclk     : 11.86 ns
```
**Expected:** the 11.5 ns path is checked against 8 ns (FAIL), as the same design on a CCGM1A1 is (one clock).

On a real board (ULX5M-GS with CCGM1A2, RGMII RX through `CC_IDDR` on bank EB, RX logic forced to die 1A) this is
exactly the failing path: link up at 1000 Mb/s, RXC 125 MHz, TX frames arrive at the peer, but every received frame
is garbage (`ARP failed`), while nextpnr reported no problem.

### Cause (from the source)
`TimingAnalyser::identify_related_domains()` relates two clocks only if walking upstream *through combinational
outputs* reaches a single common driver. GLBOUT `GLB0..3` are `TMG_GEN_CLOCK` in `delay.cc`, so the walk stops at
`GLBOUT0.GLBn` and `GLBOUT1.GLBn` and the two nets never meet (for a pad clock they both come from the same
`USR_GLB` source net; for PLL clocks from two PLLs with the same configuration and the same `CLK_REF` pad).

### Possible fixes
- Relate `X` and `X$dieN` explicitly (they are created by the packer, which knows they are copies), with the real
  insertion-delay difference, so paths between them are checked like same-clock paths; or
- in the relation walk, pass through a GLBOUT (a pure buffer, no frequency change) when the arc exists in the
  timing database;
- at least: a warning in `strategy_mirror()` / after placement when a data net connects cells clocked by `X` and
  by `X$dieN`, pointing to `force_die` or to a clock-domain crossing.

---

## 2. PR: gatemate: clock router must not use CPE bridges

**Device:** CCGM1A2 (seen only there; CCGM1A1 output unchanged).

### Problem
`router2` aborts immediately with
```
ERROR: Failed to route arc 0.0 of net '$abc$13731$new_n4557', from X27Y151/CPE.COMBOUT2_int to X28Y151/CPE.D1_03_int.
```
for any design where a clock **without** CC_BUFG (e.g. a `CC_PLL` output used directly) has users on die 1B.
Minimal design `clkrouter_bridge/top.v` (PLL → 64 LFSR lanes, all logic `GATEMATE_DIE=1B`): fails on seeds 1, 2, 3;
works on CCGM1A1 and with `--vopt no-bridges`. The full ULX5M-GS SoC with the default `mirror` strategy fails the
same way on every seed (`usb_clk` is such a PLL clock).

### Cause
`GateMateImpl::route_clock()` binds the clock nets before router2 runs. Its Dijkstra search skips CPE-internal muxes
with a `resource`, but not CPE **bridge** pips (`CPE.IN*_int -> CPE.MUXOUT_int`, flag `MUX_ROUTING`). With
instrumentation: 64 bridge pips on the repro's clock, 44 on the SoC's `usb_clk`, all on die 1B. A bridge takes one
of the CPE's `IN` inputs; the logic already placed in that CPE can then not reach its input, and router2 cannot rip
up the clock.

### Change (`clkrouter_bridge/fix_clkrouter_no_bridges.patch`)
```diff
                 if (extra_data.type == PipExtra::PIP_EXTRA_MUX && extra_data.resource != 0) {
                     if (!(extra_data.resource == PipMask::C_CY2_I && extra_data.value == 0))
                         continue;
                 }
+                // Never use a CPE in bridge mode: the bridge takes one of the CPE's IN inputs, the clock net is
+                // bound before router2 runs, and the logic placed in that CPE can then not reach its input.
+                if (extra_data.type == PipExtra::PIP_EXTRA_MUX && (extra_data.flags & MUX_ROUTING))
+                    continue;
```
### Tests
- repro: ad8527f8 fails on seeds 1/2/3, patched routes 3/3;
- CCGM1A1: the repro and the full SoC (seed 2) give a byte-identical `.txt` with and without the patch (the A1 clock
  router never used a bridge);
- note: such a fabric clock on die 1B then has small hold violations (−0.1 ns); a BUFG is still the better design.

---

## 3. PR: gatemate: die crossing only where die-to-die connections exist

**Device:** CCGM1A2.

### Problem
The CCGM1A2 chipdb (prjpeppercorn `chip.py get_connections()`, `range(27, 163)`) has die-to-die connections only
from nextpnr column X29. The placer does not know that (estimate = Manhattan distance + 2000 for a die change), so
it puts the ends of crossing nets anywhere, e.g. at X3..X13; the routing box (`getRouteBoundingBox`) then contains
no crossing, every such arc fails inside the box and router2 retries it without the box (full-chip search,
~0.5 s each). Repro `d2d_bbox/` (32 registers 1A → 1B → 1A): router2 250–410 s, 41 retries; with 128 nets per
direction it does not finish in 15 min.

### Change (`d2d_bbox/fix_d2d_bbox_estimate.patch`)
- at start-up (multi-die only) find the first column whose `D2D` wires are joined to the other die (a pip on the
  other die drives or is driven by them; every switch box has `D2D`-named wires) → `Die-to-die connections from X29.`;
- `getRouteBoundingBox()`: a net whose ends are on different dies gets its box extended to that column;
- `estimateDelay()` / `predictDelay()`: add the detour `2 * max(0, d2d_x0 - max(sx, dx))` tiles.

### Tests
- repro: router2 250.6 s → 11.4 s (other seeds 409/341 s → 13.1/13.7 s), retries without box 41 → 0;
- CCGM1A1 unchanged (`d2d_x0 = 0`; repro output byte-identical).

---

## 4. Issue (prjpeppercorn / nextpnr): CCGM1A2 — CPE flip-flops on die 1B stop working after some JTAG loads

> **Update 29.09. 23:40 (TASK-5093) — rewrite before sending.** After a power cycle the same `die1b_ff` bitstream
> works (`E00000000 K0000000B`: toggle, D=1→1, D=0→0, 32/32 registered crossings), with and without `gmpack --reset`
> and with and without `openFPGALoader -r`. So the tools are not (known to be) wrong; the failing state below was a
> chip state that survived JTAG loads and `CMD_CFGRST`. In the same session the chip fell back: a build with the
> probes at X28/X29 next to the crossing showed erratic 1B flip-flops, and two loads later no design ran at all
> (loader `Done`, JTAG `--detect` fine). The question for the maintainers becomes: is there a known way a CCGM1A2
> gets into a state where die-1B CPE flip-flops (or the whole configuration) no longer start, that only `RST_N` /
> power clears, and how should a loader reset an A2 before JTAG configuration? (Our DirtyJTAG does not drive `RST_N`.)
>
> **Update 30.09. 00:26 (TASK-5095/5096).** Narrower now: the first load after a power cycle always works, and
> loading a *different* layout over a running A2 design fails (4/5 before, and again T2.1 below). gmpack writes die
> 1B completely (CFGRST … CHG_STATUS) while die 1A still runs the old design, so we tried a local
> `gmpack --reset-all-first` that sends the existing CFGRST records of both dies before any configuration: the
> fresh load works (`K0000000B`), the reload over it is still silent. So `CMD_CFGRST`, before or after the 1B
> section, does not bring the chip back to its power-on state. Questions to add: (1) what does `CMD_CFGRST` reset
> on a die that is in user mode, and does a multi-die reload need something else (e.g. a `CMD_CHG_STATUS` back to
> configuration mode on 1A before `CMD_PATH` forwards to 1B)? (2) Is `RST_N` bonded to both dies of the CCGM1A2
> (DS1001 §2.6.2 lists only the clock pins as shared)? (3) Is there a minimum `RST_N` low time?

**Device:** CCGM1A2 on ULX5M-GS, loaded over JTAG (`openFPGALoader ... -r --index-chain 0`), bitstream from
nextpnr + `gmpack --reset` (oss-cad-suite 2026-09-28, libgm `b1eb52f`).

### Summary
In a CCGM1A2 bitstream, logic placed on die 1B works as long as it is combinational (LUTs, die-to-die routing,
IOSEL flip-flops), but no **CPE flip-flop** on die 1B ever takes a new value: a CC_DFF with D=1 reads 0 and one
with D=0 reads 1 (in another build), a toggle flip-flop never toggles — with a global (mirrored) clock or with a
fabric clock. The same design with everything on die 1A gives the correct values.

### Reproduction (`die1b_ff/`)
32 bits from an LFSR on die 1A go through (E) a CC_DFF on die 1B and back, and (K) a CC_LUT1 on die 1B and back;
three probe flip-flops on 1B (toggle, D=1, D=0); sticky error masks on the UART (`run.sh` has the details).

| build | E (through 1B CC_DFF) | K (through 1B CC_LUT1 + probes) |
|---|---|---|
| all on die 1A (`force_die=1A`) | 0 | 0 |
| 1B cells marked `GATEMATE_DIE=1B`, 4 seeds | all 32 bits wrong | LUT path correct on 32/32; probes: no toggle, D=1 reads 0 (D=0 reads 1 in another build) |
| same, 1B flip-flops clocked from the pad through the fabric | all 32 bits wrong | LUT path correct |

### What was checked
- nextpnr writes the same kind of CPE configuration on die 1B as on die 1A (`C_CPE_CLK/EN/RES/SET`, `C_O1/C_O2`).
- gmpack writes die 1B first and ends it with `CMD_CHG_STATUS` `cfg = CFG_CPE_RESET` (0x10); only die 0 gets
  `CFG_CPE_RESET|CFG_DONE|CFG_STOP` (0x13) (`libgm/src/Bitstream.cpp`, "Only for die 0"). Patching the die-1B value
  to 0x00/0x01/0x03/0x11/0x13 (CRC16 fixed) changed nothing.
- IOSEL flip-flops on die 1B work (RGMII TX through CC_ODDR on bank EB reaches the link partner).

### Also checked (29.09., TASK-5093)
- 64–16384 NOP bytes after the die-1B `CMD_CHG_STATUS` (start-up clocks): no change; afterwards the chip accepted no
  JTAG configuration any more until a power cycle (JTAG itself working).
- Cologne Chip p_r 2025.11 with `-A 2` places and routes an A2 design but stops with `ERangeError` before writing a
  bitstream; its writer emits a single `CMD_PATH 0x10`, so there is no vendor A2 bitstream to compare with.

### Question
Is there a known difference in how the second die's CPE flip-flops are released from reset / started (a command
in the bitstream, a per-die configuration bit, or the order of the dies)? A vendor-generated CCGM1A2 bitstream of
a trivial design with one flip-flop on die 1B would settle it. Was `127-bufg-a2` (88 flip-flops on die 1B with
`strategy=full`) checked on an A2 board, and with which gmpack / loader?

## 5. Issue (prjpeppercorn): gmunpack cannot read gmpack output (`Unhandled command 0x00`)

gmunpack `b1eb52f` stops on bitstreams written by gmpack `b1eb52f` itself, for CCGM1A1 and CCGM1A2 alike:
`Bitstream Parse Error: Unhandled command 0x00 [at 0x0000003d]` (A1) / `[at 0x00000064]` (A2 without `--reset`).
In the A2 stream the offset falls inside the 12 zero bytes gmpack writes right after the (empty) PLL block
(`exp/gmbit.py`: `PLL 24` at 62, zero fill at 92–103); the reader apparently does not accept them there (not traced
further in the reader code). Found while trying a gmunpack → gmpack round-trip
as an offline check (TASK-5093). Reproduce: any design without a PLL, `gmpack top.txt top.bit; gmunpack top.bit x.txt`.


---

## 6. Issue/PR (nextpnr, common): placer_heap cell-placement timeout overflows `int` from 46 341 cells on

Found in TASK-5094 (30.09.2026), nextpnr `ad8527f8` and upstream HEAD `eb4f15c3` (29.09.2026) — same line.

`common/place/placer_heap.cc:2180`:

```cpp
cell_placement_timeout = std::max(10000, (int(ctx->cells.size()) * int(ctx->cells.size()) / timeout_divisor));
```

The product is computed in `int`. From 46 341 cells on it exceeds 2^31−1 (signed overflow, UB; in practice it wraps
negative), `std::max` then returns 10000, and a large design fails in the analytical placer with
`Unable to find legal placement for cell '...' of type 'CPE_FF' after 10001 attempts` although utilisation is low
(CCGM1A2: CPE_LT 37 %, CPE_FF 13 %).

Observed: the ULX5M-GS Linux SoC (VexRiscv-SMP + LiteDRAM + 1G MAC + DVI + USB) for CCGM1A2 printed
`max placement attempts per cell = 267833940` (≈ 46 289 cells, just below the limit) and placed; the same SoC with
a 37-cell UART reset sniffer added (and a different ABC result, +400 LUT2) printed `... = 10000` and failed on 12 of 12
runs (6 seeds × 2 die strategies). `--placer-heap-cell-placement-timeout 0` (no limit) places it.

Fix (one line): compute in 64 bit and clamp, e.g.
`int64_t n = ctx->cells.size(); cell_placement_timeout = int(std::min<int64_t>(INT_MAX, std::max<int64_t>(10000, n * n / timeout_divisor)));`

---

## 7. Issue (nextpnr gatemate / prjpeppercorn): CCGM1A2 — `CC_IDDR` on die 1B never returns data, `CC_ODDR` does work

Found in TASK-5094 (30.09.2026) on a ULX5M-GS with a CCGM1A2 (KSZ9031 RGMII on bank EB = die 1B N2), nextpnr
`ad8527f8` + fixes B/C, gmpack `b1eb52f`, oss-cad-suite 2026-09-28. Minimal design `rxprobe/` (`top.v`, `build.sh`):
RXC (`IO_EB_A7`) → `CC_BUFG`; RX_CTL (`IO_EB_A8`) and RXD0 (`IO_EB_A0`) sampled on RXC; gray-coded edge counters on
the UART; logic `--vopt force_die=1A`, the pads are on die 1B.

| variant | RX_CTL / RXD0 edges while the Pi sends frames to the PHY |
|---|---|
| `CC_IDDR` (packed into the die-1B IOSEL: `GPIO.IN1_FF 1`, `IN2_FF 1`, `INV_IN2_CLOCK 1`, `IN_CLOCK 00`) | 0 / 0 |
| `CC_IBUF` → fabric `CC_DFF` (die 1A) | 7 / 194 |

In the same bank, `CC_ODDR` (TXD/TX_CTL/TXC of the same PHY) works, and so do plain inputs (MDIO read-back, RXC into
`CC_BUFG`). The IOSEL configuration words of the IDDR pad are the same as in the CCGM1A1 build of the same design; only
the IOES input muxes differ (A1 `IOES1.SB_IN_06`, `IOES2.SB_IN_07`; A2 die 1B `IOES1.SB_IN_08`, `IOES1.SB_IN_11`).
Suspect: the clock (or Q0/Q1 return path) of the input registers on die 1B is routed through a resource the chip
database models differently from the silicon. Question: is input DDR on die 1B of the A2 tested anywhere?
