# ULX5M-GS with a CCGM1A2 (GateMate A2): pinout per die, options, tool problems (TASK-5092)

**29.09.2026.** Board: ULX5M-GS on the `gs` probe with a **CCGM1A2** instead of the CCGM1A1 (same schematic).
Design: the Linux SoC `s_usb5_pll60_s2_np1817` (VexRiscv SMP, SDRAM, 1G RGMII, DVI, USB PNRU), synthesized once
(`build/s_usb5_pll60_s2_np1817/gateware/intergalaktik_ulx5m_gs.json`) and placed for `--device CCGM1A2`.
Tools: Yosys 0.69+154 / gmpack from oss-cad-suite 2026-09-28, nextpnr `ad8527f8` and the branch `t5092-a2`
(`ad8527f8` + the two fixes below). Loading: `fpga-jtag gs <bit> -r --index-chain 0` (two dies in the JTAG
chain, index 0 = die 1A; without it openFPGALoader stops with "more than one FPGA found").

Short version:

- **Keeping everything on die 1A (`--vopt force_die=1A`) is right for the CPU, SDRAM, UART, DVI**: memtest OK
  (22.8 / 10.2 MiB/s), and on Ethernet the TX direction and MDIO work. **RX does not**: the RGMII input registers
  sit in the IOSELs on die 1B and the path to die 1A takes ~12 ns in an 8 ns cycle. nextpnr does not check that path.
- Three tool problems isolated with minimal designs: (A) nextpnr does not time paths between a mirrored clock and
  its copy on the other die (issue draft); (B) the GateMate clock router uses CPE bridges and blocks router2 on
  die 1B (**fixed**, patch + repro); (C) die-to-die connections exist only from X29, the routing box and delay
  estimate did not know it (**fixed**, patch + repro, router2 22x faster on the repro).
- **(D) CPE flip-flops on die 1B do not work** in the bitstreams nextpnr + gmpack produce for the A2 (hardware
  test, §5.4): a LUT path 1A → 1B → 1A works on 32/32 bits in 4 routings, the same path with a CC_DFF on 1B fails
  on 32/32; flip-flops on 1B never follow D (D=1 reads 0, D=0 reads 1 in another build) and a toggle FF never
  toggles, with a global or a fabric clock.
  IOSEL flip-flops on 1B do work (the RGMII TX ODDRs). So nothing that needs registers can live on die 1B yet
  (option d is blocked), and the die-to-die connections themselves are fine.
- Not reached: Linux 6.12 on the A2 (it boots over TFTP, so it needs Ethernet RX). What was tried is in §5.

## 1. Pinout per die

prjpeppercorn `gatemate/chip.py` `CCGM1_DEVICES` (and DS1001 table 5.1): on the CCGM1A2 each package bank goes to
one or two die-internal banks.

| Ball bank | CCGM1A1 | CCGM1A2 | ULX5M-GS use (this SoC) |
|---|---|---|---|
| EA | 1A N1 | **1B N1** | USB host D+/D- (`IO_EA_A0/B0`), pull-ups (`IO_EA_A2/B2`) |
| EB | 1A N2 | **1B N2** | Ethernet RGMII + MDIO + PHY reset (15 pins, `IO_EB_*`) |
| NA | 1A E1 | 1A E1 **and** 1B E1 | SDRAM A0/A1/A10, UART RX `IO_NA_B6` |
| NB | 1A E2 | 1A E2 | UART TX `IO_NB_B5` |
| WA | 1A S3 | 1A S3 + 1B S3 (split by pin) | — |
| WB | 1A **S1** | 1A **N1** and 1B S1 | SDRAM DQ/BA/RAS/CAS/WE/CS/DM |
| WC | 1A S2 | 1A S2 | SDRAM A, CKE, clock, DQ |
| SA | 1A W1 | 1A W1 | — |
| SB | 1A W2 | 1A W2 and 1B W2 | clk25 `IO_SB_A8`, DVI (LVDS `IO_SB_A4..A7`), LEDs `IO_SB_A0..B3` |

Consequences:

- An A1 bitstream on the A2 cannot work: the WB balls are in bank 1A **N1** on the A2 (1A S1 on the A1), so the
  SDRAM data bus is on the wrong IOs (memtest 100 % KO on the board, as seen before this task).
- Everything except Ethernet and USB (clock, SDRAM, UART, DVI, LEDs) is reachable from die 1A.
- **Ethernet (EB) and USB (EA) exist only on die 1B.** nextpnr places the pads there by itself (`Constraining … on die '1B'`).
- NA, WB, SB balls are bonded to both dies; the unused die's pad stays an input (nextpnr chooses 1A, the die with
  most constrained pins).

## 2. Options

| | What | Result / assessment |
|---|---|---|
| (a) | `force_die=1A` (all logic on 1A), RGMII IOs on 1B | Built and tested on the board. CPU/SDRAM/UART OK; Ethernet TX OK (every ARP request reaches the Pi, the Pi answers), MDIO OK (link 1000 Mb/s), **RX fails** (§3). Needs an RX fix (§5.3). |
| (b) | default `mirror` without `force_die` | router2 aborts at once on die 1B = tool bug B (§4.2, fixed). Even when it routes, the placer spreads the CPU over both dies; every clock then exists twice (`X` on 1A, `X$die1` on 1B, the PLLs are **copied**), and paths between the two halves are not timed (bug A). Not usable for the SoC. |
| (c) | Ethernet at 100 Mb/s | RGMII at 25 MHz (40 ns): the ~12 ns die crossing would fit even without timing checks. Needs a 10/100 mode in `gbe_phy.py` (it is 1000-only) and `reg4`/`reg9` advertising only 100BASE-TX. Not done; **recommended next step** (needs no registers on die 1B). |
| (d) | only the 125 MHz PHY domains on 1B (region split), CPU etc. on 1A | Tool `tools/a2_die_split.py --from-io` + a nextpnr with fixes B/C: 6/6 seeds route. On the board: 2 of 3 seeds do not start (no UART), the third starts but MDIO/TX are dead (§5.2). **Blocked by (D)**: CPE flip-flops on die 1B do not work (§5.4). |

**Recommendation.** Stay with **(a)** `force_die=1A` (the CPU never crosses the die; memtest, UART, TX and MDIO
work on the tested build) and fix the RX direction with **(c) 100 Mb/s**: at 25 MHz the ~12 ns crossing from the
IOSEL on 1B to die 1A fits in the cycle even unchecked, and it needs no registers on die 1B. The region split (d),
which is the right answer for 1G, is **blocked by (D)** until the die-1B CPE flip-flops work (gmpack / prjpeppercorn
side, §5.4). The source-synchronous RX variant (§5.3) did not help on the builds tested, and (a) itself is not
stable across builds (§5.3), which has to be understood before a release bitstream for the A2.

## 3. Why ARP fails with `force_die=1A` (board, not guesswork)

Bitstream `t5091_A2_f1A_s4.bit` (on the Pi `/home/pi/FPGA/`), BIOS console (`tools/sd/bios_cmds.sh`,
`DJ_LOAD_ARGS="--index-chain 0"`), a raw-socket sniffer on the Pi (`eth0`):

| Check | Value | Meaning |
|---|---|---|
| `main_phy_status0` (0xf0002804) | `0x796d0348` | KSZ9031 R1 = 0x796D (link up, autoneg done), R1F = 0x0348 (bit 6: 1000 Mb/s) → **MDIO works** |
| `main_phy_status1` (0xf0002808) | `0x38006400` | RXC edges per 2^20 sys cycles >> 8 = 0x6400 → **RXC = 125.0 MHz** |
| sniffer on the Pi during `netboot` | 16/16 ARP requests `192.168.10.213 → .14` from `10:e2:d5:00:00:01`, each answered by the Pi | **TX works** |
| BIOS | `ARP failed` | the answers are not received |
| `ethmac_rx_datapath_preamble_errors` / `crc_errors` | 0 / 0 | |
| `ethmac_sram_writer_length` | `0x7ff` | a "frame" of 2047 bytes = garbage from the RX PHY |

So only RX breaks. The RX path in this build (post-route timing of the same run, `~/.tmp/a2/a2_f1A_s4.log`):

- The IDDRs (`CC_IDDR`) are packed into the IOSELs of `IO_EB_*` on die 1B and clocked by `grx_clk$die1`
  (the mirrored copy of `grx_clk`: pad `IO_EB_A7` → CC_BUFG → GLBOUT of die 1B).
- The RX logic is on die 1A and clocked by `grx_clk` (same pad, routed through the die-to-die connections to the
  GLBOUT of die 1A as `USR_GLB`).
- nextpnr reports only `Max delay posedge grx_clk$die1 -> posedge grx_clk: 12.22 ns` (and 12.89 ns negedge): a
  cross-domain *report*, **not** a check, so the run says nothing about the 8 ns period. Same for TX
  (`gtx0_clk -> gtx0_clk$die1: 11.49 ns`); TX still works because the TX ODDRs are fed from registers whose
  launch/capture relation happens to fit on this seed (it is not checked either).

## 4. Tool problems (minimal designs in `docs/nextpnr_a2_repro/`)

### 4.1 (A) Mirrored clocks are unrelated for timing → cross-die paths are never checked

`docs/nextpnr_a2_repro/mirror_xdie_timing/` (`top.v`: pad clock + `CC_IDDR` on bank EB, two registers;
`force_die=1A`):

| nextpnr ad8527f8 | Output |
|---|---|
| CCGM1A1 | normal same-clock path, checked |
| CCGM1A2 `force_die=1A` | `Max frequency for clock 'gclk': 525 MHz (PASS at 125 MHz)` and only `Max delay posedge gclk$die1 -> posedge gclk: 11.52 ns` |

Cause (reading the source): `strategy_mirror()` (pack_clocking.cc) creates a new net `X$dieN` from the GLBOUT of the
other die. `TimingAnalyser::identify_related_domains()` (common/kernel/timing.cc) relates two clocks only if a walk
*through combinational outputs* reaches a common driver; GLBOUT `GLBn` is `TMG_GEN_CLOCK` (delay.cc), so the walk
stops at the two GLBOUTs and `X`/`X$dieN` are unrelated. The path is then reported as a cross-domain "Max delay"
and never compared with the period. Possible fixes: let the relation walk pass GLBOUT (a buffer: `USR_GLBn`/`CLKn_m`
→ `GLBn` without a frequency change) and, for PLL copies, compare the same-configured PLLs by their common
`CLK_REF`; or, simpler, warn in `strategy_mirror` when a net connects cells clocked by `X` and `X$dieN`. Not patched
(common kernel, needs a maintainer's opinion). Draft issue: `docs/nextpnr_a2_repro/UPSTREAM_DRAFTS.md` §1.

### 4.2 (B) Clock router takes CPE bridges → router2 "Failed to route arc 0.0" on die 1B — FIXED

`docs/nextpnr_a2_repro/clkrouter_bridge/` (`top.v`: a CC_PLL output used as a clock **without** CC_BUFG, 64 LFSR
lanes, all logic on die 1B via `GATEMATE_DIE`):

| | seed 1 | seed 2 | seed 3 |
|---|---|---|---|
| ad8527f8, CCGM1A2 | `ERROR: Failed to route arc 0.0 … CPE.D1_03_int` | same | same |
| ad8527f8, CCGM1A2 `--vopt no-bridges` | OK | | |
| ad8527f8, CCGM1A1 | OK | | |
| **with the fix**, CCGM1A2 | OK | OK | OK |

Instrumented clock router (`GM_CLKDBG`, only on the debug commit): the PLL clock without BUFG has 64 CPE bridge pips
(`CPE.IN*_int → CPE.MUXOUT_int`, `MUX_ROUTING`) on die 1B. In the SoC with default `mirror` it is the same: `usb_clk`
(PLL2 CLK0, no BUFG) has 3402 pips / **44 bridge pips** on die 1; the failing arcs are exactly the CPE inputs of such
tiles. The clock router binds its pips before router2, the bridge uses one of the CPE's `IN` inputs, and the logic
already placed in that CPE can no longer reach it.

Fix (`clkrouter_bridge/fix_clkrouter_no_bridges.patch`, nextpnr branch `t5092-a2` commit `d5bd4b3b`): skip
`MUX_ROUTING` pips in `GateMateImpl::route_clock()`. Checks: the repro routes on 3/3 seeds; **CCGM1A1 output is
byte-identical** (repro, and the full SoC `s_usb5_pll60` seed 2 = the tested `np1817` bitstream's `.txt`, `cmp`
equal; the A1 clock router never used a bridge). Side note: a clock routed through the fabric on die 1B then shows
hold violations (up to −0.1 ns on the repro) — use a CC_BUFG for every clock that reaches die 1B.

### 4.3 (C) Die-to-die connections only from X29 → full-chip router retries, no placement cost — FIXED

prjpeppercorn `chip.py get_connections()` creates the CCGM1A2 die-to-die (D2D) links only for `x in range(27, 163)`
(nextpnr X29 and up). In the routed designs every crossing uses `TES.MDIE2.Pn` (1A → 1B, driven from the top CPE
row's `COUTY2`/`POUTY2` or `TES.SB_Y2`) or `SB_*.Pn.D2_4_D2D` (1B → 1A).

`docs/nextpnr_a2_repro/d2d_bbox/` (32 registers on 1A → 32 on 1B → back): the placer puts the 1B registers at
X3..X13 (no D2D there). Every crossing arc fails inside its routing box and router2 retries it without the box
(full-chip search, 0.5–0.7 s each, instrumented `GM_R2DBG`); with 128 nets per direction it does not finish in 15 min.

Fix (`d2d_bbox/fix_d2d_bbox_estimate.patch`, commit `0ef67857`): at start-up find the first column whose `D2D`
wires are really joined to the other die (a pip on the other die drives them; every SB has `D2D`-named wires) →
`Die-to-die connections from X29.`; extend `getRouteBoundingBox()` of a crossing net to it; add the detour to
`estimateDelay()`/`predictDelay()`. Single-die devices: `d2d_x0 = 0`, no change (A1 repro output identical).

| 32 nets each way, seed 1 | router2 time | retries without box |
|---|---|---|
| ad8527f8 | 250.6 s (other seeds 409 s / 341 s; the saved repro script: 548 s) | 41 |
| with the fix | **11.4 s** (13.1 / 13.7 s; repro script 13.5 s) | **0** |

The same problem made the region-split SoC (§5.2) sit >20 min in the first router2 iteration.

## 5. Attempts on the board

### 5.1 `force_die=1A` (option a, before this task): see §3

### 5.2 Region split (option d)

`tools/a2_die_split.py in.json out.json --from-io --clk grx_clk --clk gtx0_clk --clk gtx90_clk --clk ulx5msoc_gbephy_txc_g`
sets `GATEMATE_DIE` on every cell: registers/BRAMs of the 125 MHz domains that are connected to the Ethernet
IDDR/ODDRs → 1B, combinational cells whose every sink is on 1B → 1B, everything else → 1A (tests
`sim/test_a2_die_split.py`, 9 pass). Without `--from-io` it also pulled the DVI path to 1B (DVI runs in `gtx0`,
1428 crossing nets); with it: 293 FFs + 2 BRAM_40K (the PHY frame buffers) on 1B, 122 crossing nets.

nextpnr `t5092-a2` (fixes B + C), `mirror`, no `force_die`: 6/6 seeds route (router2 338–505 s).

| seed | grx_clk$die1 | gtx0_clk$die1 | usb_clk (60) | sys (20) | hold viol. | board |
|---|---|---|---|---|---|---|
| 1 | 107.5 | 103.9 | 53.5 | 25.4 | 4 | — |
| 2 | 108.2 | 106.2 | 55.0 | 24.8 | 1 | **no UART at all** (3 loads) |
| 3 | 120.3 | 96.3 | 56.8 | 24.8 | 3 | BIOS + memtest OK; `phy_status0 = 0xffffffff` (**MDIO dead**), RXC 125 MHz, 682 preamble errors, **no TX frame on the wire**, ARP failed |
| 4 | **133.4** | 104.0 | 45.9 | 24.6 | 2 | **no UART at all** (3 loads) |
| 5 | 102.7 | 102.6 | 56.8 | 24.6 | 5 | — |
| 6 | 113.7 | 102.9 | 56.7 | 23.2 | 3 | — |

(`pll_sys_unlocks`/`pll_tx_unlocks` are 684/29 on seed 3 and 1021/29 on the working `force_die` s4: static after
start-up on both, not the difference.)

What differs from `force_die=1A` (where MDIO and TX work): MDIO (`mdc`, `mdo`, `moe`) crosses 1A → 1B in both
builds and in the same way (`TES.SB_Y2 → TES.MDIE2 → SB.D2_2_D2D`), but on other D2D planes (P5/P6 in the
working build, P3/P8 in seed 3). The router also sends some 1A → 1A nets through die 1B and back
(`cplines$X85Y130$COUTY2`: `CPE.COUTY2` of the top 1A row → `TES.MDIE2.P5` → 1B → `D2_4_D2D` → 1A); seed 4 has
three such nets, seed 3 one. **First hypothesis (superseded by §5.4):** part of the D2D model (some planes/columns of
`TES.MDIE2` or the top-row `COUTY2/POUTY2` path) does not match the silicon. A split design uses ~120 crossings on
random planes and hits it; `force_die` uses ~34 and happened not to.

The hardware test of §5.4 shows the real reason for the split builds: the PHY's registers are on die 1B, and CPE
flip-flops on die 1B do not work at all.

### 5.3 `force_die=1A` with the RX flip-flops in the fabric

`tools/a2_iddr_to_fabric.py` (tests `sim/test_a2_iddr_to_fabric.py`, 2 pass) replaces the 5 RX `CC_IDDR` by two
`CC_DFF` each (posedge Q0, negedge Q1); the IBUFs have no `FF_IBF`, so they stay in the fabric on die 1A and RXC
and RXD both cross the die. `force_die=1A`, seeds 3–6 (router2 548–1134 s, `grx_clk` 129.7 MHz on s5).

| build | nextpnr | board |
|---|---|---|
| fab s5 | t5092 | BIOS OK; MDIO registers 0, RXC 125 MHz, no frame on the wire, `video_recoveries` 4742 |
| fab s3 | t5092 | BIOS OK; MDIO `0xffff`, RXC 0 (PHY looks held in reset), no frame on the wire |
| fab s4 | t5092 | no UART |
| fab s5 | **ad8527f8** (control) | same as fab s5 with t5092: MDIO dead, no TX |
| original netlist s5 (`t5091_A2_f1A_s5.bit`) | ad8527f8 | MDIO 0, RXC 0, no TX |
| original netlist s4 (`t5091_A2_f1A_s4.bit`) | ad8527f8 | MDIO OK, TX OK, RX garbage (§3) — **3/3 reloads the same** |

So the fix-B/C nextpnr is not the cause (the ad8527f8 control fails the same way), and even the original
`force_die` netlist works on one seed out of two. In these builds die 1B holds only IOSELs, the 3 mirrored PLLs,
GLBOUT/CLKIN and 23 `RAM_O` CPEs that feed the IOSELs — no CPE flip-flop — and no die-1A net detours through die 1B
(checked in the routed JSON). The 1A → 1B crossings of MDIO and TX use the same kind of resources in the working and
the failing builds. **Open:** what differs between s4 and s5 on die 1B (next step: diff the die-1B tile configuration
of the two `.txt` files, starting with the `RAM_O` CPEs and the PLL copies).

### 5.4 Hardware test of die 1B: LUTs and D2D work, CPE flip-flops do not

`docs/nextpnr_a2_repro/die1b_ff/` (`top.v`, `mark_dies.py`, `run.sh`, `pi_uart_rst.sh`): all at 25 MHz from clk25.
Per bit g of a 32-bit LFSR on 1A: (E) 1A register → **CC_DFF on 1B** → 1A register, (K[31:4]) 1A register →
**CC_LUT1 on 1B** → 1A register; probes on 1B: a toggle FF, a FF with D=1, a FF with D=0. Sticky error masks are
printed on the UART and cleared by a byte from the Pi. The test itself had to be made robust first: GateMate
ignores Verilog init values, yosys folds a power-on shift register fed with a constant, and `CC_USR_RSTN` gave no
reset pulse on the A2, so the reset comes from the UART RX line.

| build | E (via 1B FF) | K (LUT path + probes) |
|---|---|---|
| all on 1A (`force_die=1A`, control) | `00000000` | `00000000` |
| 1B FFs on the mirrored global clock, 4 routings (seeds 1–4) | `FFFFFFFF` | `00000000` (no probes yet) → LUT path OK on 32/32 |
| 1B FFs clocked straight from the pad (fabric clock), 2 routings | `FFFFFFFF` | `00000000` |
| with probes | `FFFFFFFF` | `00000008`: toggle FF never toggles, **FF with D=1 reads 0**, FF with D=0 reads 0 |
| saved repro `die1b_ff/run.sh` (29.09., re-run): `top_1a` / `top_x` | `00000000` / `FFFFFFFF` | `0000000B` (1A: toggle, D=1→1, D=0→0, correct) / `0000000C` (1B: no toggle, **D=1 reads 0, D=0 reads 1**) |
| probes, die-1B `CMD_CHG_STATUS` patched from `0x10` to `0x00/0x01/0x03/0x11/0x13` (CRC fixed) | `FFFFFFFF` | `00000008` |

Meaning: the die-to-die connections work in both directions (LUT path), the die-1B LUTs are configured, but no
CPE flip-flop on die 1B ever takes a new value (it keeps whatever it started with), whatever its clock. The CPE configuration written by nextpnr for those tiles is
the same as on die 1A (`C_CPE_CLK/EN/RES/SET`, `C_O1/C_O2` histograms). gmpack (prjpeppercorn `libgm`
`Bitstream.cpp`) writes the dies in the order 1B, 1A and ends die 1B with `CMD_CHG_STATUS cfg = CFG_CPE_RESET`
(0x10) and only die 1A with `CFG_CPE_RESET|CFG_DONE|CFG_STOP` (0x13); changing the die-1B value did not help, so
it is not (only) that byte. The Cologne Chip `p_r` 4.2 in `~/app/raid/tools/cc-toolchain` has no A2 option, so there
is no vendor A2 bitstream to compare with. This is the finding to take to prjpeppercorn/nextpnr (draft §4 in
`nextpnr_a2_repro/UPSTREAM_DRAFTS.md`).

### 5.5 Die-1B flip-flops, continued (TASK-5093, Kosjenka, 29.09. 20:55–21:40) — cause still open

Local toolchain `~/app/raid/tools/nextpnr-a2fix/` (`build.sh`, README with commits and patches): nextpnr `ad8527f8`
+ fixes B and C only (no DEBUG commits), gmpack from prjpeppercorn `b1eb52f`. Regression: CCGM1A1 output equal to
`ad8527f8` (`cmp`, sha1 `58a7a6d1fd43`), CCGM1A2 `top_x` `.txt` and `.bit` equal to the `t5092-a2` build.

Repro re-measured at 21:02: `top_1a` `E00000000 K0000000B`, `top_x` `EFFFFFFFF K0000000C` (same as §5.4).

| Hypothesis | Test | Result |
|---|---|---|
| H1: die 1B needs configuration clocks after its final `CMD_CHG_STATUS` (the stream switches back to 1A at once) | 64 / 1024 / 16384 NOP bytes inserted after the die-1B `CHG_STATUS` fill, also with status 0x11 (`exp/mkvar.py`) | no change on the UART (`EFFFFFFFF K0000000C`), **but see the wedge below — these loads may not have been applied at all** |
| H3: die-1B global clock dead (pad not bonded to 1B) | read the configuration | rejected: `CLKIN1`/`GLBOUT1` on 1B configured, IOSEL of the 1B copy of `IO_SB_A8` (`X0Y237`) has `INPUT_ENABLE`; DS1001 §2.6.2: CLK0..3 and SER_CLK are connected to both dies; TX ODDRs on 1B work from a PLL on 1B |
| earlier status-byte test (§5.4) | re-checked `p1.bit` vs `p1_0x13.bit` | the patch was really applied (byte 7221 0x10 → 0x13, CRC changed); that negative result stands |
| H2: position (every 1B FF so far sat at Y134–140, next to the BES / D2D row) | `exp/pos/`: 8 probe groups placed with CCF place boxes (1A ×2, 1B at Y≈137/153/203/253, X≈7/143) | built, **not measured** (board wedged) |
| H4: global freeze vs clock | `exp/h4/`: 1B FF with async SET driven by a signal, FF with routed EN | built, **not measured** |

**The board wedged (21:05).** After the NOP-variant loads, no load is applied any more: `top_1a.bit`, a 1A-only
stream, `CMD_CFGRST` alone, streams to `--index-chain 1` — each ends in openFPGALoader `Done`, and the UART still
shows the old `top_x` design (its frame counter keeps running). JTAG itself is fine: `--detect` sees 2× `0x20000001`;
a BYPASS loopback (IR = 12 ones, 48 bits through DR) returns the pattern shifted by exactly 2 bits (`a5c3f00f1234` →
`2970fc03c48d`). DirtyJTAG (firmware `DJTAG2`) SRST and TRST held low for 200–300 ms: no effect (the design does
not reset, so SRST is not wired to `RST_N` or does not reset the controller). Most likely cause: the extra bytes in
the die-1B section left the configuration path (1A forwarding to 1B, `CMD_PATH`) in a state that only a power
cycle clears. **Rule: never change the filler between the die sections of an A2 stream.** Goran asked for a power cycle
(21:10); after it: `~/t5092/run_after_powercycle.sh` (top_1a must again give `K0000000B`, then top_x, pos, h4).

**Vendor reference does not exist.** Cologne Chip `p_r` 2025.11 (prints `Version 4.2`) has a hidden option `-A 2`
(help string "GateMate Device number A1..A25"). With it, a counter design is placed and routed on the CCGM1A2
(`not routed: 0`), then `p_r` exits with `ERangeError` before writing a bitstream (also with `-tm 2`, `-om 2`, `-fs`,
`+uCIO`, `-cgb`, `-pr`). The bitstream writer `Fpga_cfg::Fill_cfg_file` (disassembled, symbols present) writes one
`CMD_PATH 0x10`, optional `CMD_SLAVE_MODE`, PLL, RAM, latches, SERDES and one `CMD_CHG_STATUS` (0x11 | 0x02 = 0x13,
+0x04/0x08 with reconfig, +0x40 with SerDes) — a single-die writer, no `CMD_PATH 0x02`. So the vendor tool cannot
produce an A2 bitstream to compare with either.

Upstream: prjpeppercorn-test-cases `127-bufg-a2` (Miodrag Milanović, 25.09., `strategy=full`) places 88 of 176
FFs on die 1B (our nextpnr, checked). If it was verified on an A2 board, die-1B FFs work there — question added to
the issue draft (`UPSTREAM_DRAFTS.md` §4). GitHub search: no issue about die-1B FFs (nextpnr #1501, #1550, #1811;
prjpeppercorn #18 is about JTAG pins bonded through the interposer).

### 5.6 Die-1B flip-flops: pre-registered experiments after the power cycle (TASK-5093, 29.09. 23:40, written BEFORE the board)

Board state: `gs` power-cycled at 22:54:54 (USB re-enumeration in the Pi `dmesg`), UART silent (no design running).

**Re-reading the old result.** `K0000000C` on 1B means: toggle FF never toggles, FF with D=1 reads **0**, FF with
D=0 reads **1**. A FF that simply keeps its start value would have to start at 0 in one CPE and at 1 in the other.
All three observations (and E=`FFFFFFFF`) are explained at once by **an inversion in the 1B FF data path**
(Q = ~D: the toggle loop D=~Q then holds its value). So "the FF does not update" and "the FF is inverted" were never
told apart.

| # | Hypothesis | Bitstream (made by gmpack itself, not patched) | sha256 | Expected if hypothesis true | Otherwise |
|---|---|---|---|---|---|
| P1 | H5: `CMD_CFGRST` (`gmpack --reset`) and/or `openFPGALoader -r` stops the 1B FFs (upstream `127-bufg-a2` flow uses neither) | `top_x_nr.bit` = same `top_x.txt`, `gmpack` **without** `--reset`, loaded `--index-chain 0` **without** `-r` | `b294109d110cfac8…` | `E00000000 K0000000B` | `EFFFFFFFF K0000000C` again |
| P2 | H6: 1B FF works but data is inverted, vs. H0: 1B FF stuck | `inv_nr.bit` (`die1b_ff_t5093/inv/top.v`: K[7:4] = raw {L, 1B FF D=L, 1B FF D=~L, 1A FF D=L}, L = frame bit), no `--reset` | `2bcd50523a23de25…` | H6: K[7:4] alternates `B`/`4` | working: `D`/`2`; stuck: bits 6,5 constant |
| P3 | same as P2 with `--reset` (only if P1 differs from P2's reset-free result) | `inv_r.bit` | `4ea901c11fac2428…` | as P2 | — |

Offline checks done before the board: (1) `top_x.bit` rebuilt with the local toolchain is byte-identical to the one
measured on 21:02 (sha256 `1bab6321…`); (2) the command skeleton of `top_x_nr.bit` equals upstream `127-bufg-a2`
packed by the same gmpack (`exp/gmbit.py`, only the design's GPIO-bank bytes in `CHG_STATUS` differ) — no
hand-made commands; (3) RTL and gate-level (yosys netlist + `cells_sim.v`, iverilog) simulation of `inv/top.v`
print `K…DA`/`K…2A` alternating (working chip; bit 0 is X in simulation because the toggle FF has no init);
(4) `gmunpack` round-trip is **not possible**: gmunpack `b1eb52f` fails on gmpack's own output (A1 too) with
`Unhandled command 0x00` at the 12 zero bytes written after the PLL block — a separate tool bug.

**Measured 29.09. 23:25–23:36 (after the power cycle; each load a gmpack output, script `uart_nr.sh` = no `-r`,
`uart_r.sh` = with `-r`, both `--index-chain 0`):**

| order | bitstream | flow | UART | meaning |
|---|---|---|---|---|
| 1 | `top_x_nr.bit` (P1) | no `--reset`, no `-r` | `E00000000 K0000000B` ×5 | **die-1B FFs work**: toggle, D=1→1, D=0→0, 32/32 registered crossings |
| 2 | `top_x_nr.bit` | same, repeated | `E00000000 K0000000B` | reproducible |
| 3 | `top_x.bit` | `--reset`, no `-r` | `E00000000 K0000000B` | CFGRST is harmless (same design as 2, so this load alone does not prove it was applied) |
| 4 | `inv_r.bit` (P2/P3) | `--reset`, no `-r` | `EF7FFFFFF K000000DB / 69 / B9 / 2B` | different layout → load applied; **1B FFs erratic**: raw nibble D, 6, B, 2 — q1b sometimes keeps the previous frame's value, `one_s` once 0 |
| 5 | `top_x.bit` | `--reset` **with `-r`** (the old flow) | `E00000000 K0000000B` | old flow works too → neither CFGRST nor `-r` is the cause (H5 rejected) |
| 6 | `inv_nr.bit` | no `--reset`, no `-r` | **UART silent** (10 s) | openFPGALoader `Done` |
| 7 | `top_x_nr.bit` | no `--reset`, no `-r` | **UART silent** | — board stopped here (rule 5a: stop, report); `--detect` sees both dies |

Conclusions so far: (1) the tool chain (nextpnr a2fix + gmpack `b1eb52f`) produces working die-1B flip-flops;
H1–H5 and "missing config bit" are not the cause. (2) The `K0000000C` state of 29.09. and the "wedge" at 21:05
were a **chip state** that only a power cycle cleared; the same bitstreams work on a fresh chip. (3) The chip
falls back into a bad state during a session: erratic 1B FFs at load 4, no running design from load 6 on. What
triggers it is open — candidates: a load over a running A2 design (the DirtyJTAG `-r`/pre-load `reset()` does not
reach `RST_N` on gs, so no load starts from a real chip reset), the `inv` placement (1B FFs at X28/X29 next to the
die crossing, `ib.ub` X28Y137, `nb.ub` X29Y137), or the board (see below). No D2D site is used by two nets in either
build (checked in the routed JSON).

Board note (DS1001 §5.3/§5.4, "Combined PCB for A1 or A2"): ULX5M-GS is wired for the A1 — U14/V14 go straight to
GND and U16/V16 to GND through 0 Ω (R7/R8), V15 (`POR_ADJ` on A1) has only C133 100 n. On the A2 these balls are
`SER1_RX_P/N`, `SER1_TX_P/N` and `SER1_RTERM` (die-1B SerDes), which DS1001 says to leave open (case 2). This only
touches `VDD_SER` (own rail on gs, not `VDD_CORE`), so it is not a likely cause of the FF problem, but it is a
known deviation from the datasheet for an A2 on this board.

## 6. Open items

1. **Die-1B CPE flip-flops (D)** (TASK-5093 §5.5: H1/H3 rejected, H2/H4 built but not measured, board waits for a power cycle): find the missing piece (a per-die start/reset command in the bitstream, or a
   CPE/tile configuration bit on die 1B) — ideally with a vendor-generated A2 bitstream (Cologne Chip p_r with A2
   support) as reference. Until then no registers on die 1B.
2. **`force_die=1A` is not stable across builds** (s4 works, s5 and the fabric-RX builds do not): diff the die-1B
   tile configuration of `a2_f1A_s4.txt` and `a2_f1A_s5.txt`.
3. RX at 1G is not possible with everything on 1A (12 ns crossing in an 8 ns cycle); next practical step is the
   100 Mb/s mode (option c) on a build of the s4 kind.
4. Linux 6.12 on the A2 (login, ping, DVI, USB, 30 min stability as in TASK-5091) waits for items 2 and 3; USB
   (EA bank, die 1B) was not tested.
5. Upstream (after Goran's review): issue A (timing of mirrored clocks), PRs B and C, issue D (die-1B flip-flops).
6. `gm_cfgrst_check.py` knows the A2 format now (a run of `d9 01 ed 96` path records before each die's
   `CMD_CFGRST`, offsets 48 and 77979 in `t5091_A2_f1A_s4.bit`); tests `tools/tests/test_gm_cfgrst_check.py` 5 pass.

## 7. Reproduce

```sh
# nextpnr with fixes B + C (local): branch t5092-a2 of the nextpnr repo, build like docs/nextpnr_1814_repro/build_nextpnr_ad8527f.sh
# repros (each prints the difference between ad8527f8 and the fixed binary)
NEXTPNR=.../nextpnr-himbaechel docs/nextpnr_a2_repro/clkrouter_bridge/run.sh
NEXTPNR=.../nextpnr-himbaechel docs/nextpnr_a2_repro/d2d_bbox/run.sh
NEXTPNR=.../nextpnr-himbaechel docs/nextpnr_a2_repro/mirror_xdie_timing/run.sh
# SoC for the A2 from the existing A1 synthesis (no new yosys run)
G=build/s_usb5_pll60_s2_np1817/gateware
nextpnr-himbaechel --json $G/intergalaktik_ulx5m_gs.json --vopt ccf=$G/intergalaktik_ulx5m_gs.ccf --vopt out=a2.txt \
  --vopt fpga_mode=3 --device CCGM1A2 --vopt force_die=1A --router router2 --timing-allow-fail --freq 125 --seed 4
gmpack --reset a2.txt a2.bit && python3 ~/app/regoc_system/tools/gm_cfgrst_check.py a2.bit
# on the Pi
DJ_LOAD_ARGS="--index-chain 0" ./bios_cmds.sh a2.bit "mem_read 0xf0002804 8" "netboot"
```
