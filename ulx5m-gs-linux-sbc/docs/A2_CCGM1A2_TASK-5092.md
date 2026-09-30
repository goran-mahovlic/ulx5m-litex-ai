# ULX5M-GS with a CCGM1A2 (GateMate A2): pinout per die, options, tool problems (TASK-5092)

**29.09.2026.** Board: ULX5M-GS on the `gs` probe with a **CCGM1A2** instead of the CCGM1A1 (same schematic).
Design: the Linux SoC `s_usb5_pll60_s2_np1817` (VexRiscv SMP, SDRAM, 1G RGMII, DVI, USB PNRU), synthesized once
(`build/s_usb5_pll60_s2_np1817/gateware/intergalaktik_ulx5m_gs.json`) and placed for `--device CCGM1A2`.
Tools: Yosys 0.69+154 / gmpack from oss-cad-suite 2026-09-28, nextpnr `ad8527f8` and the branch `t5092-a2`
(`ad8527f8` + the two fixes below). Loading: `fpga-jtag gs <bit> -r --index-chain 0` (two dies in the JTAG
chain, index 0 = die 1A; without it openFPGALoader stops with "more than one FPGA found").

**Update 30.09.2026 (TASK-5094, §5.9) — supersedes the short version below where they differ:**

- **Linux 6.12 with Ethernet runs on the A2** at **100 Mb/s**: BIOS memtest, TFTP netboot, login after 263 s, ping
  both ways, USB keyboard/mouse (`input0`), DVI console, 30 min with 1800/1800 pings × 1400 B under SDRAM load.
  Bitstream `/home/pi/FPGA/A2_CCGM1A2_Linux612_ETH100M_rxos_DVI_USB_selfrst_CFGRST_f1A_s5_T5094.bit`.
- Why 1G RX never worked on the A2: the **`CC_IDDR` input registers in the die-1B IOSEL return nothing** (RX pin probe
  `nextpnr_a2_repro/rxprobe/`), and RX flip-flops clocked by RXC across the dies sample at a placement-dependent
  phase. The 100 Mb/s PHY therefore oversamples RXC/RX_CTL/RXD with the 125 MHz TX clock (`Rgmii100OSCore`).
- (D) is not a flip-flop defect: die-1B FFs work; the chip only fails when another layout is loaded over a running A2
  design. **A design-driven reset (`R!` → `IO_SB_B8` = `RST_N`) returns both dies to the power-on state**, so the A2
  can be reloaded without a power cycle.
- New tool bug: nextpnr's heap placer limit overflows `int` from 46 341 cells (all placements of the SoC failed).
- Review §5.10 (TASK-5097): after the test the board still runs (45 min, dmesg 0 errors, `rx_errors` 0); the
  45.8 MHz gtx figure is the DVI scaler path the working A1 has too (46.6 MHz), not the RX front end.

Short version (29.09., TASK-5092):

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

**Next, pre-registered (after the next power cycle, only the bitstreams above, no hand-made streams):**
Q1 `inv_nr.bit` as the **first** load on the fresh chip — if the 1B FFs are erratic, the `inv` build (placement at
X28/X29) is the trigger; if raw alternates `D`/`2`, the chip degrades with loads over a running design. Q2 `top_x_nr.bit`,
Q3 `inv_nr.bit` again, Q4 `top_x_nr.bit` ×3 in a row — the first silent/erratic result stops the series.

### 5.7 Q1/Q2 after the second power cycle, and a design-driven chip reset (TASK-5095, Jelena, 29.09. 23:55–00:40)

`gs` was power-cycled at 23:55:14 (both DirtyJTAG probes re-enumerated in the Pi `dmesg`). Bitstreams on the Pi checked
against §5.6 (sha256 `2bcd5052…` `inv_nr`, `b294109d…` `top_x_nr`). Series Q1–Q4 from §5.6, `uart_nr.sh`
(no `--reset`, no `-r`, `--index-chain 0`):

| order | bitstream | UART | meaning |
|---|---|---|---|
| Q1 | `inv_nr.bit`, **first** load on the fresh chip | `E00000000 K0000002B / K000000DB` alternating, 7 frames | 1B FFs work, not inverted; the `inv` placement (X28/X29) is **not** the trigger |
| Q2 | `top_x_nr.bit` over the running `inv` design | `load: Done`, **UART silent** (4 s, then 8 s more after `0x00`) | series stopped (rule 5a); `--detect`: both dies `0x20000001` |

**Pattern over both sessions (§5.6 + this one):** the first load after a power cycle always works (`top_x_nr`
23:25, `inv_nr` 23:57). Reloading the **same** layout works (§5.6 loads 2, 3). Loading a **different** layout over a
running A2 design went wrong 4 times out of 5: erratic 1B FFs (§5.6 load 4), no running design (§5.6 loads 6–7, Q2);
the exception is §5.6 load 5 (`top_x` over `inv_r`, worked), so it is not deterministic. That fits
H7: **a load over a running A2 design is not applied cleanly, because nothing resets the chip before it.**
openFPGALoader `CologneChip::reset()` for DirtyJTAG sets SRST low and high again with no wait (`colognechip.cpp`
l. 88–105, 676e53e), SRST does not reach `RST_N` on gs (§5.5), and DS1001 §3.4 has no JTAG instruction that
resets the configuration (the only ones are BYPASS, CONFIGURE, SPI_*, SERDES_REGFILE, SET_TESTMODE,
SAMPLE_PRELOAD, EXTEST). `CMD_CFGRST` in the stream (`--reset`) does not replace it (§5.6 load 4 used `--reset`). On the
A1 this never showed because a single-die stream has no 1A→1B forwarding path to leave half-configured.

**A reset the board already has.** `kicad_netlist.py` on `ulx5m-gs-hw` 61b6709: net `RST_N` = `U4.T15` (the RST_N
ball) + **`U4.N15` = `IO_SB_B8`** + R111 (10 k to +1V8) + C138 (100 nF) + J2.72/J2.99 (CM4 connector). A design can
therefore reset its own chip by pulling `IO_SB_B8` low. On the A2, bank SB is 1A W2 (§1), so the pin is on die 1A.
The reset tri-states every IO, so the pin lets go by itself and R111/C138 give a rising edge ~1 ms later: the design
**cannot** hold the chip in reset. What the chip does after the edge is decided by `CFG_MD` (SW1), the same as after
a power cycle.

`die1b_ff_t5095/` (built with `nextpnr-a2fix`, `build.sh`):

- `sr/selfrst.v`: 8N1 receiver; after the bytes `R!` (0x52 0x21) a 16-bit key becomes `A55A` and `IO_SB_B8` is driven
  low (open drain, otherwise high-Z). A key instead of one bit because GateMate does not apply FF init values: a
  random start state fires with p = 2⁻¹⁶, a cleared one never. `0x00` (`uart_nr.sh`), a lone `R` or `!` do nothing.
- `sr/top.v` = `die1b_ff/top.v` + selfrst (diff: port `rst_pad` + 4 lines); `inv_sr/top.v` = `die1b_ff_t5093/inv/top.v` + the same.
- Checks before the board: `selfrst_tb.v` 7/7; `top_tb.v` RTL and gate-level (yosys netlist + `cells_sim.v`) for both
  tops: `rst_pad` = 1 (pull-up) at start, after `00 00`, after `R`; 0 after `R!` → `RESULT PASS`; gate-level
  `inv_sr` with the short tick prints `K…2`/`K…D` alternating like the original; nextpnr places `rst_pad` on
  `IO_SB_B8` die 1A (IOSEL `OE_ENABLE=1`, data 0, `OE_SIGNAL` from the key); the same flow rebuilds Kosjenka's
  `inv_nr.bit` byte-identical (sha256 `2bcd50523a23de25`).
- Bitstreams (gmpack without `--reset`): `sr_x_nr.bit` sha256 `fa11676b8ebf7137…`, `inv_sr_nr.bit`
  `c4b8f36839f544c4…`; copied to `fpga-klaudio@pi:~/t5095/` with `sr_reset.sh` and `run_series.sh`, **not loaded**
  (the chip is in the bad state since Q2).

**Pre-registered, after the next power cycle (`~/t5095/run_series.sh`, stops at the first miss):**

| step | action | expected if H7 + self-reset hold | otherwise |
|---|---|---|---|
| S1 | load `sr_x_nr.bit` (fresh chip) | `E00000000 K0000000B` | — (as §5.6 load 1) |
| S2 | `sr_reset.sh`: send `R!` | UART silent (or the flash design, per `CFG_MD`) | frames keep coming → `IO_SB_B8` does not reset the chip |
| S3 | load `inv_sr_nr.bit` | `K000000DB` / `K0000002B` alternating (as Q1 on a fresh chip) | silent/erratic → RST_N does not clear what a power cycle clears |
| S4 | `R!` | silent | — |
| S5/S6 ×3 | `sr_x` → `R!` → `inv_sr` → `R!` | every load as on a fresh chip | first miss stops |

If S1–S6 pass, the load flow for the A2 on gs becomes: **`R!` (or any design-driven pull of `IO_SB_B8`) before
every load**. That is a flow/board fix, not a tool patch: a SoC for the A2 keeps an `IO_SB_B8` reset register, and
`fpga-jtag`/`uart_nr.sh` send the trigger first. A control run (`inv_sr` → `sr_x` **without** `R!`) at the end would
reproduce Q2 and close H7.

### 5.8 Follow-up without the board (TASK-5096, Jelena, 30.09. 00:15–00:40)

The board was **not** loaded: `gs` has not been power-cycled since Q2. Evidence on the Pi (00:15): last DirtyJTAG
enumeration in `dmesg` is 23:55:18 (the power cycle of §5.7), the lease `/home/pi/gs.owner` says
`jelena 1790719839 TASK-5095 gs NEEDS POWER CYCLE (silent since 23:58)`. Only a read-only `fpga-jtag gs --detect
--index-chain 0` was run: both dies answer `0x20000001`, so JTAG is fine and the chip is in the H7 state.

- **Rebuild check:** `OUT=~/.tmp/a2/t5096_rebuild die1b_ff_t5095/build.sh` from scratch (56 s): `selfrst_tb` and both
  gate-level tops `RESULT PASS`, `sr_x_nr.bit` sha256 `fa11676b8ebf7137…`, `inv_sr_nr.bit` `c4b8f36839f544c4…` —
  byte-identical to the copies in `fpga-klaudio@pi:~/t5095/` (checked with `sha256sum` on both sides).
- **What the chip does after the `R!` pulse (S2):** `kicad_netlist.py` on `ulx5m-gs-hw` 61b6709: `CFG_MD0` (R5) and
  `CFG_MD1` (T5) are pulled to GND by R29/R27 10 k (the pull-ups R28/R26 are DNP); `CFG_MD2` (U4) and `CFG_MD3` (V4)
  have 10 k to GND (R25/R24) and go to SW1, whose common pins 1/2 are the `+1V8` power symbol (config sheet at
  17.78/73.66; `kicad_netlist.py` lists that net only as `N$0034` because it does not name power-symbol nets). DS1001 table 3.1: SW1 both on = `0xC` JTAG, both off = `0x0` SPI active
  (loads the flash), only one on = `0x4` SPI passive or `0x8` (not allowed, "malfunction"). The mode is captured on
  the rising edge of `RST_N`, so after `R!` the chip does exactly what it does after power-on — the same starting
  point that §5.6/§5.7 showed works for the first load. The SW1 position is not recorded; if S2 prints output that is
  not ours, it is the flash design (`0x0`), which is expected and not a miss.
- **Guard against loading a wedged chip:** `die1b_ff_t5095/preflight.sh` (sourced first by `run_series.sh`) stops with
  exit 3 while the lease has `NEEDS POWER CYCLE` and the DirtyJTAG probes have not re-enumerated after the note's
  timestamp; it fails closed without a lease file or without a DirtyJTAG line in `dmesg`. `preflight_test.sh`:
  5 pass, 0 fail (fake dmesg/uptime/lease). On the Pi with real data it stops: `last DirtyJTAG enumeration 23:55:19
  is before the note 00:10:39`, exit 3.
- **Control run:** `run_series.sh --control` appends the H7 control after S6 (C1 `inv_sr`, C2 `sr_x` **without**
  `R!`); it leaves the chip in the bad state, so only use it when the next session starts with a power cycle anyway.

**Goran's note #112 (00:20, "maybe both dies need a reset").** Checked before the board:

- *Does `RST_N` reach die 1B?* DS1001 does not say. §2.6.2 lists what is bonded to both dies (SER_CLK/SER_CLK_N,
  CLK0..3); `RST_N` (T15) is not in that list, and §3.2 / the A2 pin list only give one `RST_N` ball. Open; S2/S3
  measure it indirectly (if `R!` only resets 1A, S3 is a load with 1B still running).
- *Minimum `RST_N` low time:* DS1001 table 4.8 gives only POR thresholds, no pulse width. `selfrst.v` holds `IO_SB_B8`
  low until the reset tri-states the pad; then R111/C138 (10 k, 100 nF, τ = 1 ms) make the rising edge. `CFG_DONE`
  (V3) goes only to U6 (LED) on gs, and DS1001 §3.4 has no JTAG status instruction, so the Pi cannot see CFG_DONE.
- *Reset 1B over JTAG index 1 (1B's own TAP) with a single-die stream:* not built. Kosjenka's loads to
  `--index-chain 1` in the wedged state had no effect (README of nextpnr-a2fix), and a stream written into 1B
  directly bypasses the 1A→1B path the A2 flow uses; kept as a fallback.
- **gmpack order (candidate b) — this is a tool problem, and it is fixed locally.** `Bitstream::serialise_chip`
  (b1eb52f l. 862–901) writes, per die in the order 1B, 1A: path select, `CMD_PATH 0x10`, `CMD_CFGRST` (only with
  `--reset`), configuration, `CMD_CHG_STATUS`. So during a reload **die 1A keeps running the previous design while
  die 1B is reset and written** — 1A is reset only after 1B is done. On a fresh chip 1A runs nothing, which is why
  the first load always works; on a reload the old 1A logic drives the die-to-die connections into the new 1B
  configuration. That fits every observation of §5.6/§5.7, including §5.6 load 4 (`--reset` did not help: its 1A
  CFGRST came after 1B). Call it **H8**.
  Local patch `nextpnr-a2fix/patches/prjpeppercorn/0001-gmpack-reset-all-first-resets-every-die-before-any-d.patch` (branch `a2fix-reset-first`):
  new option `gmpack --reset-all-first` (implies `--reset`) writes, before the first die's configuration, the reset
  records of every die: 1B `PATH 01, PATH 02, PATH 10, CFGRST 00` then 1A `PATH 01, PATH 10, CFGRST 00` (94 bytes).
  Offline checks, `nextpnr-a2fix/tests/gmpack_reset_first_test.py`: 15 ok, 0 fail — without the option the output
  is byte-identical to b1eb52f for A1 and A2 (with and without `--reset`); on the A1 the option equals `--reset`;
  on the A2 the output is `prefix + (b1eb52f --reset stream)`, and both prefix blocks are byte copies of records that
  stream already contains (1B block at offset 0, 1A block at offset 6450 in `sr`, 7028 in `inv_sr`) — no new
  command, no changed filler (the §5.5 wedge came from changed filler). `gm_cfgrst_check.py`: CFGRST present.
  Bitstreams: `sr_x_raf.bit` sha256 `bb2e1afb0234a40c…`, `inv_sr_raf.bit` `4049745c95212735…` (same `.txt` as
  `sr_x_nr`/`inv_sr_nr`), on the Pi in `~/t5095/`.

**Pre-registered series T (tool fix, run first after the power cycle of 00:23:14; `~/t5095/run_series_t.sh`, no
`R!` anywhere, stops at the first miss):**

| step | action | expected if H8 holds and the patch fixes it | otherwise |
|---|---|---|---|
| T1 | `sr_x_raf.bit` on the fresh chip | `E00000000 K0000000B` | CFGRST-first breaks a fresh load → patch wrong |
| T2.1 | `inv_sr_raf.bit` over running `sr_x` | `K000000DB` / `K0000002B` alternating | silent/erratic → H8 is not (the whole) cause; recover with `R!`? no design runs → power cycle, then series S |
| T3.1 | `sr_x_raf.bit` over running `inv_sr` (the Q2 case) | `E00000000 K0000000B` | as above |
| T2/T3 ×2 more | | every load as on a fresh chip | first miss stops |

If T passes, the tool fix is `gmpack --reset-all-first` for every A2 load (and an upstream PR: make it the default
for multi-die streams when `--reset` is given). If T1 passes and a reload fails, H8 is rejected and series S (§5.7)
runs after the next power cycle.

**Result of series T (00:24–00:26, after the power cycle of 00:23:14; preflight passed, board otherwise untouched):**

| step | bitstream | UART | meaning |
|---|---|---|---|
| T1 | `sr_x_raf.bit` (sha256 `bb2e1afb…`), fresh chip | `load: Done`, `E00000000 K0000000B N0001..N0004` | 1B FFs work; the reset-first prefix does no harm on a fresh load |
| T2.1 | `inv_sr_raf.bit` (`4049745c…`) over running `sr_x` | `load: Done`, **silent** (4 s, then 8 s more after `0x00`, 00:25:57) | series stopped; `--detect` both dies `0x20000001` |

**H8 is rejected as the (whole) cause:** resetting both dies with `CMD_CFGRST` before either is configured does not
make a reload of another layout work. So the in-stream `CMD_CFGRST` does not return the chip to the state a power
cycle gives, whether it comes before or after 1B's configuration. The gmpack patch stays in the local tree (harmless:
byte-identical without the option, T1 fine) but it is **not** a fix and is not proposed upstream. What remains is a
real reset of the chip: series S (`R!` = `IO_SB_B8` → `RST_N`, §5.7) after the next power cycle.
The series scripts now write `~/t5095/NEEDS_POWER_CYCLE` when a step misses (agents cannot write `/home/pi/gs.owner`);
`preflight.sh` takes the newer of that marker and the lease note (`preflight_test.sh` 8 pass, 0 fail). On the Pi
after T2.1: both `run_series_t.sh` and `run_series.sh` stop with `last DirtyJTAG enumeration 00:23:18 is before the
note 00:25:30`, exit 3.

**Goran's note #114 (00:26: other ways to reset, a longer reset, gmpack reset of both dies).** Offline, the board
was already silent after T2.1:

- *Documentation.* DS1001 §3.2 (RST_N, POR), §3.3 (CFG_MD table 3.1, CFG_DONE/CFG_FAILED_N table 3.3), §3.4 (JTAG
  instructions) say nothing about resetting one die of the A2 or about a minimum `RST_N` low time; UG1001 (primitives)
  has nothing on configuration. No A2/multi-die application note was found locally or in §5.5's search. prjpeppercorn
  `serialise_chip` and openFPGALoader `CologneChip::reset()` are covered above and in §5.7.
- *JTAG TLR/TRST.* Test-Logic-Reset (5× TMS=1) resets the TAP only, not the configuration (IEEE 1149.1); DirtyJTAG
  SRST/TRST pulses of 200–300 ms did nothing on gs (TASK-5093). Not a candidate.
- *Longer reset.* A design cannot make the pulse longer: when `IO_SB_B8` pulls `RST_N` below the threshold the chip
  goes into reset and tri-states its IOs (DS1001 fig. 3.2 `/ResetIO`), so it lets go of the net itself. With an
  8 mA driver C138 (100 nF) falls from 1.8 V to ~1.0 V in ~10 µs; from there R111 (10 k, τ = 1 ms) brings it back
  over the rising threshold (~1.2 V, table 4.8 VIO,TH+ as a proxy; the pin threshold itself is not specified) in
  τ·ln(0.8/0.6) ≈ 0.3 ms. So `R!` gives a reset of the order of **0.3 ms** and nothing longer. A longer reset needs
  an external pull on the `RST_N` net: on gs that net is also at the module connector **J2.99** = CM5 `PMIC_Enable`,
  on Waveshare CM5-IO-BASE-A the net `PI_GLOBAL_EN` (schematic `CM5-IO-BASE-A_Sch.pdf`, p. 1), and **J2.72** = CM5
  `SD_DAT6` (unused by the 4-bit TF slot). Grounding `PI_GLOBAL_EN` (a pad/header on the baseboard, or a wire to a
  Pi GPIO in open-drain) for 1 / 10 / 100 ms is the only way to measure a longer reset; it needs Goran at the board.
  (U7/U8 74LVC2G00 only read `RST_N`, they do not drive it.)
- *gmpack reset of both dies:* done — `--reset-all-first` (T, rejected). The order 1A-first is the same idea with
  the same `CMD_CFGRST`; after T2.1 it is not worth a power cycle.
- *Empty "reset" stream between two designs* (series E) and *1B through its own TAP* (series J) — built:
  `die1b_ff_t5095/empty/` (`empty.v`: no logic, UART TX idle-high on `IO_NB_B5`; `build.sh` rebuilds the same
  sha256), `empty_a2_r.bit` (255 B, `983fec22ac4a4d82…`) and `empty_a1_r.bit` (106 B, `af8884403a9771e9…`); their
  command lists (`exp/gmbit.py`) have the same skeleton as the real streams (PATH/fill/CFGRST/D2D/PLL/CHG_STATUS, 1B
  status `10 1f…`, 1A `13 1f 20…`), no hand-made records. Scripts `run_series_e.sh` (E1 `sr_x` fresh, then ×3:
  empty → `inv_sr` → empty → `sr_x`, judged on the real designs) and `run_series_j.sh` (J1 `sr_x`, then ×3:
  `empty_a1_r` to `--index-chain 1` (observed only) → `inv_sr` → again → `sr_x`). Both on the Pi, both stop in the
  preflight now (exit 3).

**Order for the next power cycles (one series per power cycle while they fail; each stops at the first miss):**

1. **S** `~/t5095/run_series.sh --control` — `R!` (design-driven ~0.3 ms `RST_N`). If S passes, it is the flow fix.
2. **E** `~/t5095/run_series_e.sh` — empty stream between designs (pure JTAG, no board change).
3. **J** `~/t5095/run_series_j.sh` — 1B through its own TAP.
4. **L** (needs Goran): with `sr_x` running, ground `PI_GLOBAL_EN` for 100 ms, then 10 ms, then 1 ms, each followed
   by `inv_sr` / `sr_x`; records the shortest external reset that works. If even 100 ms fails, the state survives
   `RST_N` and only a power cycle clears it.

After the next power cycle: clear the note in `/home/pi/gs.owner` or leave it (the probes' re-enumeration lets the
preflight pass either way), then `fpga-klaudio@pi:~/t5095/run_series.sh --control`.

### 5.9 Linux + Ethernet again with the local toolchain, one load per power cycle (TASK-5094, Jelena, 30.09. from 00:33, written BEFORE the board)

**State at the start (00:35):** `gs` silent since T2.1 (§5.8); `~/t5095/preflight.sh` on the Pi: `last DirtyJTAG
enumeration 00:23:18 is before the note 00:25:30`, exit 3. Nothing was loaded. Goran's notes #113/#115 (reset both
dies, longer reset, gmpack reset of both dies, alternatives) are answered in §5.8 as far as possible without the
board; the remaining measurements (S, E, J, L) are folded into the session below.

**Why a new attempt makes sense.** The SoC results of §5.2/§5.3 (split s2/s4 "no UART", s3 "MDIO dead", fab builds,
`force_die` s5) were loads of *different layouts one after another in the same session* — exactly H7 (§5.7): only the
first load after a power cycle is known to be applied cleanly. So those results say nothing reliable about the
builds; each of them has to be judged again as the **first** load after a power cycle. The die-1B FFs themselves work
on a fresh chip with this toolchain (§5.6, §5.7 Q1, §5.8 T1), so the region split of Goran's #108 (PHY + MAC-side
up to the frame buffers on 1B, CDC on the sys side, `gtx` from the PLL copy on 1B fed by CLK0 = clk25 on both dies)
is no longer blocked by (D).

**Build (`tools/a2_soc_sr_build.sh`, local toolchain `~/app/raid/tools/nextpnr-a2fix`):**

- Source: the TASK-5091 SoC (`build/s_usb5_pll60_s2_np1817`: VexRiscv-SMP, 1G MAC, DVI, USB PNRU, Linux 6.12 on
  the A1) — same gateware, same `rv32_k612.dtb` (no CSR change).
- **Self-reset added** (`selfrst.v` from §5.7, instance `a2_selfrst`, pad `a2_rst_pad` = `IO_SB_B8` = `RST_N` net,
  `CC_IOBUF`, open drain). It is clocked by the 20 MHz `sys_clk` (`-DSR_HALF=87 -DSR_FULL=174`): clocked by clk25 it
  would need a third global clock per die (GLBOUT is 2/2) — first attempt failed. `selfrst.v` got macros instead of
  parameters because a parameter changed the §5.7 bitstreams; with macros `die1b_ff_t5095/build.sh` still rebuilds
  `sr_x_nr.bit` `fa11676b…` and `inv_sr_nr.bit` `c4b8f368…` byte-identically. `selfrst_tb.v`: 25 MHz PASS, 20 MHz
  with `-DSYS20 -DSR_HALF=87 -DSR_FULL=174` PASS, 20 MHz with the 25 MHz divider FAIL 2 (negative control).
- Synthesis once (yosys 0.69+154, oss-cad-suite 2026-09-28, 48 s): 37 selfrst cells (25 DFF, 12 ADDF), `a2_rst_pad` on
  a `CC_IOBUF`.
- Variants: **split** = `a2_die_split.py --from-io --clk grx_clk --clk gtx0_clk --clk gtx90_clk --clk
  ulx5msoc_gbephy_txc_g` (1B = 474 cells: 293 DFF + 2 BRAM_40K + their combinational cone; the rest 1A), `mirror`,
  no `force_die`; **f1A** = `--vopt force_die=1A` (control, the §3 build type). Seeds 1–6 each, `--freq 125
  --vopt fpga_mode=3 --router router2 --timing-allow-fail`, `gmpack --reset`, `gm_cfgrst_check.py`.
- **New tool bug on the way (E):** all 12 runs first failed in the placer (`Unable to find legal placement for cell
  … CPE_FF after 10001 attempts`, CPE_LT 37 %). `placer_heap.cc:2180` computes `int(cells)*int(cells)/8` in `int`;
  from 46 341 cells on it overflows and the limit falls to 10000 (the TASK-5091 netlist printed 267833940 ≈ 46 289
  cells, just under it). Same line in upstream HEAD `eb4f15c3`. Workaround `--placer-heap-cell-placement-timeout 0`;
  draft §6 in `nextpnr_a2_repro/UPSTREAM_DRAFTS.md` (not posted).

| build | sha256 | sys (20) | grx_clk$die1 | gtx0_clk$die1 | usb_clk (60) | grx_clk / gtx0_clk (1A) | CFGRST |
|---|---|---|---|---|---|---|---|
| split s3 | `bbe3ae2e7d428e13…` | 23.7 | **126.8 PASS** | 106.3 | 56.2 | 256.3 / 41.9 | yes |
| split s4 | `32eb557c2cb68baa…` | 25.4 | 120.5 | 107.0 | 56.1 | 206.8 / 47.1 | yes |
| split s5 | `9f1fca691c04b00c…` | 23.9 | 124.0 | 96.4 | 51.9 | 205.6 / 45.5 | yes |
| split s6 | — | killed by the OOM killer (12 parallel runs, 62 GB) | | | | | |
| f1A s4 | `934c2faaeb538807…` | 24.9 | — | — | 50.4 | 82.4 / 42.3 | yes |

(f1A s1–s3, s6 were stopped to free memory; split s1/s2 still routing when the board session started.) No hold
violations in split s3/s5 after routing. `a2_rst_pad` is on `IO_SB_B8` on die 1A in every run.

**Pre-registered session after the next power cycle** (`~/t5094/a2_session.sh`, stops at the first miss; every
load is a direct gmpack output, CFGRST present; board IP 192.168.10.213; boot.json `linux` = Image612 +
`rv32_k612.dtb` + `rootfs612.cpio` + `opensbi612.bin`):

| step | action | expected if it works | otherwise |
|---|---|---|---|
| P1 | first load: best split seed (`a2_board_once.sh`, `STAB=1800`) | BIOS memtest OK → netboot TFTP (= 1G RX + TX) → Linux 6.12 login → `ping` Pi 5/5, Pi → board 20/20 × 1400 B, `input0` (USB), `/dev/fb0` (DVI), dmesg 0 error → 30 min: SDRAM loop + 1800 pings, 0 % loss | BIOS but `litex>` (netboot failed): `mem_read 0xf0002804 8` = PHY status (MDIO), RXC counter → 1G RX still broken → 100 Mb/s variant (item 4); silent → marker, stop |
| R1 | `R!` on the console | board stops answering ping (SoC reset through `RST_N`) | still answers → R! does not reach `RST_N` in the SoC, stop |
| S1 | `sr_x_nr.bit` (another layout) after R1 | `E00000000 K0000000B` → **R! returns the chip to the power-on state: the H7 flow fix** | silent → R! resets only part of the chip (only 1A? #113) or is too short (#115) → marker; next power cycle: series E/J (§5.8), then L (Goran, longer external reset) |
| P2… | after `R!`: next split seed / the f1A control | as P1 (without the 30 min) | first miss stops |

If P1 already gives Linux with working Ethernet, the result of the task does not depend on R1/S1; those only decide
whether later loads need a power cycle.

**Result of the session (power cycle by Goran at 00:51:34; all loads direct gmpack output with CFGRST; scripts
`~/t5094/a2_board_once.sh`, `~/t5095/sr_reset.sh`, `~/t5095/uart_nr.sh`):**

| step | time | bitstream | load onto | console | meaning |
|---|---|---|---|---|---|
| P1 | 01:08:39 | split s3 (`bbe3ae2e…`) | **fresh chip** | BIOS banner, `Ethernet init`, `Memtest at 0x40000000`, `Write: 0x40000000` — then nothing (90 s) | SoC starts; the CPU hangs on the first SDRAM write of the memtest: a problem of this routing, not of the chip state (fresh load) |
| R1 | 01:09:56 | — | P1 | `R!` sent | (no Linux, so the ping proof does not apply; S1 is the proof) |
| **S1** | 01:09:59 | `sr_x_nr.bit` (`fa11676b…`, other layout) | SoC after R1 | **`E00000000 K0000000B` ×5** | **R! returns the chip to the power-on state**: a different layout, loaded over an A2 design after the design-driven `RST_N` pulse, works exactly as on a fresh chip; die-1B FFs work (item 1 of the task: die1b_ff repro OK with the local toolchain) |
| R2 | 01:11:14 | — | `sr_x` | `R!` | |
| P2 | 01:11:16 | f1A s4 (`934c2faa…`) | after R2 | BIOS, **Memtest OK**, 22.8/10.2 MiB/s, netboot `ARP failed` ×2 → `litex>`; `phy_status0 = 0x796d0348` (link up, 1000 Mb/s, MDIO OK), `phy_status1 = 0x38006400` (RXC 125 MHz), `ethmac_sram_writer_length = 0x7ff`, pending 1 | same as §3: TX and MDIO work, 1G RX delivers garbage; the load after R! behaves like the §3 loads |
| R3 | 01:14:54 | — | P2 (BIOS prompt) | `R!` | |
| P3 | 01:14:56 | split s5 (`9f1fca69…`) | after R3 | Memtest OK, `ARP failed` ×2, `0x796d0348`, writer length `0x7ff` | **1G RX broken with the PHY registers on die 1B as well** |
| R4 | 01:16:07 | — | P3 | `R!` | |
| P4 | 01:16:09 | split s4 | after R4 | Memtest OK, `ARP failed` ×2, `0x796d0348` | as P3 |

So: (1) **the reset question of #113/#115 has a working answer**: `R!` (design pulls `IO_SB_B8` = `RST_N`, pulse
~0.3 ms, §5.8) resets both dies — four loads of three different layouts after it all came up as on a fresh chip,
none needed a power cycle. `RST_N` does reach die 1B (S1: the 1B FFs of `sr_x` work after the SoC). (2) 1G RX on the
A2 does not work in any variant, including Goran's #108 cut (PHY + frame buffers on 1B, timing met for `grx_clk$die1`
on s3); MDIO, TX and the RX clock do. (3) → item 4 of the task: 100 Mb/s on a `force_die=1A` build (below).

**100 Mb/s (item 4 of the task).** `gateware/gbe_phy.py` `Rgmii100Core`/`Rgmii100PHY`, `target_soc.py --eth-100m`:
the unchanged `GbePHYCore` under migen clock enables — RX: RXC = 25 MHz, the falling-edge IDDR sample (mid-nibble)
is the nibble, the core advances every 2nd RXC cycle and its enable is re-aligned on every SFD (5 → D) so the core's
A/B pairing never has to change; TX: gtx stays 125 MHz (DVI/USB need it), the core advances every 10th cycle, the
output stage holds each nibble 5 cycles and makes TXC itself (register, 2 of 5 cycles high = 25 MHz, 40 % duty,
rising edge 16 ns after the nibble change). MDIOCore advertises only 100BASE-TX FD (REG9 = 0, REG4 = 0x0101). The
CSR map is identical to the 1G SoC (same `rv32_k612.dtb`). `sim/tb_rgmii100.py`: TX nibbles at the rising TXC →
25 MHz RX loop, both enable phases × both nibble offsets + an RX_ER frame: **4/4 PASS**; the 1G `sim/tb_gbe_phy.py`
still passes (A, B). The first version (free-running RX enable) failed 2 of 4 cases (a frame whose SFD falls on the
other phase is lost while the pairing re-trains) — fixed by the SFD re-alignment.

Build `SRC=build/s_a2_e100 OUT=~/.tmp/a2/t5094e100 tools/a2_soc_sr_build.sh f1A`, seed 1: sys 23.4 PASS, grx_clk
72.7 MHz (needs 25), CFGRST yes, sha256 `12242bc2e6f7a324…` (Pi `~/t5094/A2_f1A_eth100M_selfrst_s1.bit`).

| step | time | bitstream | console / registers | meaning |
|---|---|---|---|---|
| R5 + P5 | 01:34 | 100M f1A s1 | Memtest OK; `phy_status0 = 0x796d0328` (R1F bit 5: **100 Mb/s FD**, link up), `phy_status1 = 0x40001400` (**RXC 25 MHz**); `ARP failed` ×2, `netboot` again by hand after the link was surely up: `ARP failed` ×2; `ethmac_sram_writer_length 0x7ff`, pending 1 | same signature as 1G |
| | 01:36 | (same) | RX slots `0x80000000`/`0x80000800`: **all zero**; TX slot `0x80001000`: a correct ARP request (`ff…ff 10e2d5000001 0806 … c0a80ad5 … c0a80a0e`) | the MAC got a 2047-byte stream of zeros, i.e. the PHY core's sys side emitted words that were never written (not corrupted real frames) |
| R6 + P6 | 01:55 | 100M f1A s1 + CSR `zdiag` (`--phy-diag-csr`, sha256 `b1905c636d4ab0d3…`) | `zdiag`: rx_frames 0, **tx_frames 16**, drops 0, flips 0 (the RX_CTL edge field was 0 by construction: the SoC never passed `rx_ctl` to MDIOCore — fixed for the next diag build) | the core accepted 16 ARP requests; RX delivered no frame |
| R7 + P7 | 02:34 | 100M diag2 (`6c453a8b9c11ace5…`, RX_CTL edges of the IDDR sample now counted) | `zdiag`: tx_emit 16, tx_frames 16, **RX_CTL rising edges 1**, rx_frames 0; after 10 pings from the Pi to .213 (unicast to `10:e2:d5:00:00:01`): still 1 | the RX_CTL the core sees never toggles |

The Pi's neighbour entry for .213 was not refreshed by any load of this session (`updated` 11 h ago), which weakly
suggests the Pi did not receive our ARP requests (Linux does not always refresh a STALE entry with the same lladdr,
so this is not proof). The Pi agent account has no packet capture (tcpdump needs root).

**RX pin probe (`docs/nextpnr_a2_repro/rxprobe/`, `build.sh`, sim `top_tb.v` prints `C0003 F0003 D0096`).**
RX_CTL (`IO_EB_A8`) and RXD0 (`IO_EB_A0`) sampled on RXC, UART prints gray-coded edge counters; RESET_N held high,
MDIO untouched (the PHY keeps the 100 Mb/s link of the SoC before). Both loaded after `R!`, while the Pi pinged .213:

| variant | sha256 | UART (0.67 s apart) |
|---|---|---|
| `CC_IDDR` in the die-1B IOSEL (as the SoC) | `174ea69a84724eee…` | `C0000 F0000 D0000` ×4 |
| `CC_IBUF` → fabric FF on die 1A (`-DFAB`) | `bc7cd8177f6657c8…` | `C0002 → C0005 → C0007`, `D003A → D008E → D00C2` |

**This is the cause of "ARP failed" on the A2 at 1G and at 100 Mb/s:** the KSZ9031 does deliver the frames on the
RX pins, but the `CC_IDDR` input registers in the die-1B IOSEL never return data (both Q0 and Q1 stay constant),
while the `CC_ODDR` output registers of the same bank work (TX, TXC) and so does a plain input (`CC_IBUF` → fabric,
also the MDIO input and RXC → `CC_BUFG`). Whether that is the silicon, the chip database or the bitstream writer for
input DDR on die 1B is open (next: diff the IOSEL configuration words of `IO_EB_A8` in `rxp_iddr.txt` against an
A1 build of the same design; candidate issue for prjpeppercorn/nextpnr, not posted). The `R` field of the probe
does not match RXC = 25 MHz (it advances by 2 per line in both variants); not needed for the verdict, not chased.

Consequence for the SoC: `Rgmii100PHY(rx_fabric=True)` / `--eth-rx-fabric` samples RX_CTL/RXD with a negedge
`CC_DFF` behind the `CC_IBUF` (no `CC_IDDR`; 40 ns per nibble, the pad → die-1A path of ~12 ns fits). 1G cannot
use that (8 ns cycle, 12 ns crossing) — at 1G the A2 needs working input DDR on die 1B.

| step | time | bitstream | result |
|---|---|---|---|
| R8 + P8 | 02:59 | 100M, `--eth-rx-fabric --phy-diag-csr`, f1A s2 (`d4b03a6ecaa2785d…`; sys 25.1 PASS, usb 64.4 PASS) | Memtest OK, `ARP failed` ×2; `zdiag` at the prompt: RX_CTL edges 27, **drops 27**, rx_frames 0; after 10 pings from the Pi 38 / 38 |
| | 03:05 | (same), `netboot` by hand | tx_frames 16 → 32, **RX_CTL edges +16, drops +16**, rx_frames 0 |

With fabric sampling the frames reach the PHY core: for every one of our 16 ARP requests one frame came back (the
Pi's replies — so **100 Mb/s TX works**), and the core dropped each of them (`drop = (commit & bad) | (ofirst &
~space_ok)`). Which of the two is being measured with separate counters (`GbePHYCore(diag=True)`, zdiag bits
[119:80]: drops with RX_ER, drops without space, `ra`, `wc_s`, `space`, FSM idle, source valid/ready).

| R9 + P9 | 03:20 | 100M fabric RX + core diag, f1A s2 (`144f32b261180a8e…`) | at the prompt: RX_CTL edges 27, **drops 0**, **rx_frames 11**, `ra = wc_s = 743`, idle, space; `netboot`: 16 requests out, RX_CTL edges +17, rx_frames **+1**, drops 0, `ra` +105 words (≈ 420 bytes, i.e. the replies were written and read) → still `ARP failed` |

The same RX logic behaved differently in two routings (P8: every frame dropped with a clean pointer state; P9: no
drops, but the replies came out without their frame ends — merged into one long frame). In simulation a one-nibble
skew between RX_CTL and RXD drops every frame (`tb_rgmii100.py --skew`: 0/7). So the RX flip-flops clocked by RXC
sample at a **placement-dependent phase**: RXC reaches die 1A through `CC_BUFG` on 1B and the die-to-die clock,
RXD/RX_CTL through ordinary die-to-die routes, and nothing times the two against each other.

**RX by oversampling (`Rgmii100OSCore`, `--eth-rx-os`).** RXC, RX_CTL and RXD are all sampled as levels by gtx
(125 MHz, 2 synchronizer stages, fabric on 1A): a rising RXC between two samples marks the nibble change, the sample
2 gtx cycles later (16–24 ns after the edge) is the middle of the 40 ns nibble; the core runs in gtx with a nibble
strobe (`rx_valid`) instead of the RXC domain. Skews between the pads of up to ~12 ns and a drifting RXC do not
matter. RXC no longer needs a `CC_BUFG` (the MDIO controller's RXC counter then counts gtx — diagnostics only).
`sim/tb_rgmii100_os.py`: RXC periods 5, 5/5/6/5/4, 5/6/5/5/4/5 with RX_CTL one sample late, 5/4/5/6 with RX_CTL one
sample early, plus an RX_ER frame: **4/4 PASS**; `tb_rgmii100.py` (nibble strobe added) still 4/4.

**Linux 6.12 + Ethernet on the A2 (item 3 of the task).** Build `--eth-100m --eth-rx-os --phy-diag-csr`
(`build/s_a2_e100os`, selfrst, `force_die=1A`, `tools/a2_soc_sr_build.sh`), seeds 1/2 stuck in router2 (2–4 overused
wires after >1000 iterations, stopped), seed 5 routed: sys 24.9 MHz PASS, usb 59.2 (60), gtx0 45.8 MHz reported
against 125 (the video/USB/PHY CE paths are multi-cycle by design; see the concern below), CFGRST yes, sha256
`872d54ee51ce7f762e9c91e1c3fa80c2144e0932ab90c66e99034acc852dd941`. On the Pi:
`/home/pi/FPGA/A2_CCGM1A2_Linux612_ETH100M_rxos_DVI_USB_selfrst_CFGRST_f1A_s5_T5094.bit`.

| step | time | result |
|---|---|---|
| R10 + P10 | 04:01 | Memtest OK, **netboot TFTP works** (7.5 MB `Image` in one go) — but the agent's `~/FPGA/netboot_app.sh` is the old one and had written the 5.14 `boot.json`; run stopped, `boot.json` restored to Goran's 6.12 default with `/home/pi/FPGA/netboot_app.sh linux`, `a2_board_once.sh` now calls that one |
| R11 + P11 | 04:04 | BIOS memtest OK → TFTP `Image612`, `rv32_k612.dtb`, `rootfs612.cpio`, `opensbi612.bin` → OpenSBI v1.3 → **Linux 6.12.0, `buildroot login:` after 263 s** (A1 TASK-5091: 266 s); `liteeth f0000800.mac eth0`, kernel IP 192.168.10.213 |
| | | board → Pi `ping -c 5`: **5/5**, 0 % loss; Pi → board `ping -c 20 -s 1400`: **20/20**, avg 24.0 ms |
| | | USB: `/proc/bus/input/devices`: `usb_pnru boot keyboard/mouse`, `event0`; `/dev/input/event0` |
| | | DVI: `/dev/fb0`; grabber `:8090/snap.jpg` at 04:11: fbcon with `input: usb_pnru boot keyboard/mouse …` and `buildroot login:` (`docs/linux/a2_t5094/dvi_a2_100M_start.jpg`) |

**30 min stability (as TASK-5091), 04:07–04:40:** SDRAM load loop on the board (`cat` + `md5sum` of an 8 MB file,
load average 3.1–3.5, 3.73 at the end) and `ping -c 1800 -s 1400 -i 1` from the Pi: **1800/1800, 0 % loss**,
rtt 13.8 / 18.3 / 36.0 ms (min/avg/max); `uptime` 35 min at the end, no reboot; the sbcdiag line every ~60 s shows
`vrec 0x00000000` throughout; `dmesg | grep -ciE 'error|fail|oops'` = 0 at the start (the repeat at the end was cut
off by the capture); DVI grabber after 36 min still the fbcon console (`docs/linux/a2_t5094/dvi_a2_100M_after36min.jpg`).
Logs: `docs/linux/a2_t5094/P11_linux612_100M_session.log` (Pi side), `P11_linux612_100M_console.txt` (console).

**Concerns (DONE_WITH_CONCERNS):**
- Ethernet on the A2 runs at **100 Mb/s**, not 1G: the die-1B `CC_IDDR` returns nothing (issue draft §7), and a 1G RX
  without input DDR does not fit (8 ns cycle, ~12 ns die crossing).
- The oversampling front end and the nibble enable are single-cycle paths in gtx and their slack is **not known**:
  the 45.8 MHz nextpnr prints for seed 5 (clock net `grx_clk` = `gtx_clk` = `gtx0_clk`) is the DVI scaler path
  (`framebuffer2x_scaler2x` line buffer → adder, `vid_clk` = `gtx0_clk`), which the working A1 build of TASK-5091 has
  as well (46.57 MHz) — see §5.10. It works on the board and over 30 min; to be sure, latch the nibble one cycle after
  the RXC edge, give the enable 3 cycles (and duplicate its fan-out), then re-seed. Seeds 1/2 did not route (router2
  stuck at 2–4 overused wires).
- yosys reduces `selfrst`'s 16-bit key to one flip-flop (the key only takes 0 or A55A), so the "random start state"
  protection of §5.7 is not what the netlist has; on the board the FFs start cleared and R! never fired by itself.
- Nothing is pushed; the upstream drafts §6 (placer overflow) and §7 (IDDR on die 1B) wait for Goran.


### 5.10 Review of §5.9 (TASK-5097, Kosjenka, 30.09. 04:45–05:15) — no load, board only read

Independent checks of the TASK-5094 result; nothing was loaded onto `gs`, the running Linux was only read over the
console (`~/t5094/k5097_q.sh`, logs `~/t5094/K5097_*.uart` on the Pi).

| check | result |
|---|---|
| bitstream on the Pi | `sha256sum` = `872d54ee51ce7f76…` = local `~/.tmp/a2/t5094e100os/t5094_A2_sr_f1A_s5.bit`; `gm_cfgrst_check.py` → `CFGRST` |
| board after the test | Pi → .213 `ping -c 3`: 3/3; `/proc/uptime` 2693 s (45 min, same boot as P11), SDRAM loop still running (load 4.45), `vrec 0` |
| dmesg (the count §5.9 lost at the end) | `dmesg \| grep -ciE 'error\|fail\|oops'` = **0**, the listing is empty |
| eth0 counters | `rx_errors 0`, `rx_dropped 51` (49 → 51 in 4 min, no traffic of ours), `rx_packets 2624`, `tx_packets 1957` |
| sims (`. tools/sbc_env.sh`) | `tb_rgmii100_os.py`, `tb_rgmii100.py`, `tb_gbe_phy.py` (1G): ALL TESTS PASSED; `tools/tests/a2_board_once_test.sh`: 8 ok, 0 fail |

- **`rx_dropped` is not a PHY/MAC fault.** `litex_liteeth.c` (6.12) drops a frame with bad length or without an skb
  at `rx_drop:`, which increments `rx_dropped` **and** `rx_errors`; `rx_errors` is 0, so all 51 are counted by the
  network core after the driver delivered a good frame (frames with a protocol the buildroot kernel does not handle,
  e.g. IPv6/LLDP multicast from the LAN). Not verified per frame (no capture on the Pi: tcpdump is not installed).
- **The 45.8 MHz in §5.9 is not the RX front end.** In the `--eth-rx-os` netlist `grx_clk` = `gtx_clk` = `gtx0_clk`
  (`soc_sr.v:6445/6450`), and the reported critical path (21.8 ns) starts at the DVI scaler line buffer
  (`mem_1` = `framebuffer2x_scaler2x`, `vid_clk` = `gtx0_clk`, `soc_sr.v:4018/13979`) and goes through an adder.
  The same clock limits every build: A2 100M s1 44.1 MHz, A2 1G f1A s4 39.6 MHz, and the **working A1 build of
  TASK-5091 46.57 MHz** (`build/s_usb5_pll60_s2_np1817/litex.log`). So the concern is "RX front end slack unknown"
  (masked by the scaler path), not "RX front end fails timing". Same for `ref_clk` 89.8 MHz (a `multiregimpl`
  synchronizer path, A1: 83.0 MHz).
- **Lab state left behind:** `/home/pi/gs.owner` still says `jelena … TASK-5095 gs NEEDS POWER CYCLE (silent since
  23:58)` (written 00:10), and `~/t5095/NEEDS_POWER_CYCLE` (01:02) is still there. `preflight.sh` passes because the
  DirtyJTAG enumeration after Goran's power cycle (00:51) is newer, but a human reading the lease note gets the wrong
  state: the chip runs the §5.9 Linux design and needs no power cycle (`R!` resets both dies). The agent account
  cannot write `gs.owner` (owned by `pi`) — Goran/pi should update it.

## 6. Open items

1. **Linux 6.12 + Ethernet on the A2 work at 100 Mb/s** (§5.9: login 263 s, ping, USB, DVI, 30 min 1800/1800 under
   SDRAM load) with `--eth-100m --eth-rx-os` on a `force_die=1A` build with selfrst; bitstream
   `/home/pi/FPGA/A2_CCGM1A2_Linux612_ETH100M_rxos_DVI_USB_selfrst_CFGRST_f1A_s5_T5094.bit`.
2. **Reload without a power cycle:** `R!` (selfrst, `IO_SB_B8` = `RST_N`) resets both dies (§5.9 S1 + 10 further
   loads). Every A2 design should contain selfrst; before each load run `~/t5095/sr_reset.sh 2`.
3. **1G on the A2 needs the die-1B input DDR:** `CC_IDDR` in the die-1B IOSEL returns nothing (`rxprobe/`, draft §7).
   Next: diff the IOSEL/IOES configuration against a working A1 IDDR bit by bit, or ask upstream.
4. Timing of the 100 Mb/s RX front end in gtx: slack unknown, hidden behind the DVI scaler path that limits gtx0 in
   every build incl. the A1 (§5.10) — make it multi-cycle, re-seed, and read its own path with a timing report.
5. `force_die=1A` s4/s5 differences and the split s3 memtest hang (§5.9 P1) are not chased further: all earlier SoC
   board results before §5.9 were reloads without a reset (H7) and are not reliable.
6. Upstream (after Goran's review): issue A, PRs B and C, issue D (§4, now: FFs work, reload needs a reset), E/§6
   (placer int overflow), §7 (IDDR on die 1B).
7. `gm_cfgrst_check.py` knows the A2 format (tests `tools/tests/test_gm_cfgrst_check.py` 5 pass).

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
# A2 Linux 6.12 + 100 Mb/s Ethernet (§5.9): LiteX build with the target_soc.py line from build/s_a2_e100os/litex.log
# (... --with-gbe --eth-mode mac --boot netboot --phy-diag-csr --eth-100m --eth-rx-os), then selfrst + local A2 toolchain:
SRC=build/s_a2_e100os OUT=~/.tmp/a2/t5094e100os SEEDS=5 tools/a2_soc_sr_build.sh f1A    # -> t5094_A2_sr_f1A_s5.bit
# on the Pi (preflight, one load, login, ping, USB/DVI, STAB = stability seconds); before a reload: ~/t5095/sr_reset.sh 2
STAB=1800 ~/t5094/a2_board_once.sh A2_f1A_eth100M_rxos_diag_selfrst_s5.bit P11_e100os_s5
```
