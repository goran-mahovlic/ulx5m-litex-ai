# DOOM on ULX5M-GS: DVI framebuffer in SDRAM, without Linux (TASK-5036)

Date: 2026-09-25. Author: Jelena (REGOČ). Request: Goran via Klaudio ("can we, in some combination, get a DVI/HDMI framebuffer in SDRAM and run DOOM as an application"). This is a separate chapter on DOOM next to Dora's Linux research (TASK-5035).

Tags: **MEASURED** = run here, with a file or log. **SOURCE** = link or file in the repo. **HYPOTHESIS** = an estimate that still has to be measured.

## 0. Summary

**It is feasible, but not in today's netboot SoC and not with LiteX's ready-made framebuffer.** There are three obstacles and each has a solution:

1. **A DVI output exists** (TMDS on `IO_SB_A4…B7`) and has already worked on the board (Goran's README v004+). I measured the video chain with a build: P&R passes. It needs **2 extra global nets** (`hdmi` 25 MHz and `hdmi5x` 125 MHz), and today's 1G SoC already uses **all 4**. So the DOOM build goes **without 1G Ethernet**: WAD from the SD card or 100 Mb/s netboot.
2. **LiteX `VideoFrameBuffer` is not suitable for DOOM.** At 640×480 rgb565 it needs 92% of SDRAM peak (40 MB/s), and it has no palette. We need **our own module: 320×200 8 bpp indexed + 256×24 palette + hardware line doubling**. That is 3.8 MB/s (9.6% of peak), and DOOM's `screens[0]` then goes into the frame directly, with no colour conversion.
3. **Multiplication:** DOOM calls `FixedMul`/`FixedDiv` all the time. Today the netboot SoC only fits with VexRiscv **lite**, which multiplies iteratively (~33 cycles, 0 CC_MULT). With VexRiscv **standard** (4 CC_MULT, I$/D$ 4 KiB) the placer fails at 76% LT (lesson J7). Once 1G, Etherbone and the hardware stack are removed, standard fits (S5s9 with *more* logic: 68% LT, 4 CC_MULT, P&R passes).

**The shortest path to the first frame** (§7) is 4 steps. The first needs no video gateware at all: DOOM `-timedemo` on the existing S5s9 SoC (standard, SD card), with FPS printed on the UART. Only after we measure the speed do we build the framebuffer.

**Feasibility rating: YES, medium risk.** The biggest unknown is FPS. With no L2 cache and a measured CPU SDRAM read speed of 4.5 MiB/s, I expect **~3–10 FPS at 20 MHz** (HYPOTHESIS, §5).

## 1. Does ULX5M-GS have a DVI/HDMI output?

**Yes.**

| Fact | Evidence |
|---|---|
| Connector "DDMI0 (3 diff data lines + diff clock)", "Video output (DVI)" and "DVI - tested and works" since v004 | SOURCE `~/app/ulx5m-gs-hw/README.md` (sections *Interfaces* and *Tested and confirmed working from V004*), image `pic/ULX5M-GS-v002.jpg` |
| TMDS pins: clk `IO_SB_A7/B7`, D0 `IO_SB_A4/B4`, D1 `IO_SB_A5/B5`, D2 `IO_SB_A6/B6` | SOURCE `~/app/GateMate_demos/LiteX_DVI/intergalaktik_ulx5m_gs_platform.py:93-102` |
| No conflict with our SoC: `IO_SB_A0…B3` are status LEDs, `IO_SB_A8` is clk25 | SOURCE `gateware/target_soc.py:40`, `gateware/crg.py:5` |
| GateMate sends TMDS 640×480@60 through `CC_ODDR` (DDR, 2 bits per 125 MHz clock = 250 Mb/s per pair) and `CC_LVDS_OBUF` | SOURCE `LiteX_DVI/gateware/video_colognechip_hdmi_phy.py` (Miodrag Milanović, 2025), 10:2 serializer → DDR |

**MEASURED: video chain on our chip.** The build `LiteX_DVI/intergalaktik_ulx5m_gs.py --cpu-type None --with-video-terminal` (VTG + colorbars + 3× TMDSEncoder + serializers + SDRAM controller with 8 KiB L2) finished with rc=0. Bitstream sha256 `47f8e260…9c819dbd`, log `docs/doom/dvi_colorbars_util_20260925.txt`.

| Resource | Measured | Note |
|---|---|---|
| CPE_LT | 2 777 (6%) | upper bound for video; also includes LiteDRAM + L2 |
| CPE_FF | 679 (1%) | |
| RAM_HALF | 17 | all 17 are the 8 KiB SRAM + L2 tag/data; video uses no BRAM |
| CC_BUFG | **4** | `sys`, `sys_ps`, `hdmi`, `hdmi5x` → **video needs 2 global nets** |
| CC_PLL | 2 | video has its own PLL |
| CC_ODDR / CC_LVDS_OBUF | 4 / 4 | |
| fmax `hdmi5x` | 128.8 MHz (target 125) | PASS, but with a small margin |
| fmax `hdmi` | 59.6 MHz | the real clock is 25 MHz, so this is enough; "FAIL at 125" is a constraint artefact because the clock is derived by `divide_5` logic from 125 MHz |

I did not flash the board: it was not requested, and according to Goran's README DVI already works on v004+.

## 2. Global nets: the main conflict with 1G Ethernet

GateMate A1 has 4 `CC_BUFG`. Today's 1G SoC uses all 4: `sys`, `gtx0` 125 MHz, TXC and `grx` (SOURCE `docs/SOC_PHASE2_20260925_TASK-5033.md` §4). Video needs 2 more (MEASURED, §1).

| Combination | Global nets | Rating |
|---|---|---|
| 1G + DVI | sys, gtx0, TXC, grx, hdmi, hdmi5x = **6 > 4** | ❌ does not fit |
| **No Ethernet, WAD from SD card** | sys, hdmi, hdmi5x (+ 1 free) | ✅ **recommended for the first frame** |
| 100 Mb/s RGMII netboot + DVI | sys, eth_tx 25 MHz = `hdmi` (same PLL, same frequency), hdmi5x, eth_rx = 4 | ✅ HYPOTHESIS; sharing the TX clock and pixel clock must be checked in P&R |
| 1G, pixel logic in the gtx0 125 MHz domain with CE 1/5 | 4 | ⚠️ HYPOTHESIS; a TMDS encoder at 125 MHz with gtx0 fmax 119 MHz (S5s9) is risky |

## 3. LiteX framebuffer and SDRAM bandwidth

LiteX `VideoFrameBuffer` (`litex/soc/cores/video.py:1022`) reads the frame by DMA through a LiteDRAM port. The only supported formats are `rgb888/rgb565/rgb332/mono8/mono1` (`video.py:1008`): **no palette, no line doubling**.

SDRAM peak: 16 bits × 20 MHz = **40.0 MB/s**. Measured by the CPU (BIOS memspeed, S5): write 8.8 MiB/s, read 4.5 MiB/s (SOURCE `SOC_PHASE2` §4). Budget at 60 Hz (MEASURED by calculation, `python3`):

| Mode | Frame | Read @60 Hz | % of peak | Rating |
|---|---|---|---|---|
| 640×480 rgb888 (LiteX default) | 1200 KiB | 73.7 MB/s | 184% | ❌ |
| 640×480 rgb565 | 600 KiB | 36.9 MB/s | 92% | ❌ CPU starves |
| 640×480 rgb332 (LiteX, unmodified) | 300 KiB | 18.4 MB/s | 46% | ⚠️ works, but the DOOM palette looks bad in 3-3-2, and the CPU must scale 2× and write 300 KiB per frame (~33 ms) |
| 320×240 8 bpp indexed + HW 2× | 75 KiB | 4.6 MB/s | 11.5% | ✅ |
| **320×200 8 bpp indexed + HW 2× (+ 40-line black border)** | **62.5 KiB** | **3.8 MB/s** | **9.6%** | ✅ **recommended** (DOOM's native `SCREENWIDTH×SCREENHEIGHT`) |

Note: DMA reads only during active lines (73% of the time at 640×480), so the instantaneous demand is ~1.37× higher than the average. For the recommended mode that is ~5.3 MB/s, still far below peak.

**Recommended gateware (own module, ~150–250 lines of migen, size is a HYPOTHESIS):**

```
LiteDRAM native port ──> DMA (1 line = 320 B, once per 2 output lines)
    ──> line buffer 320×8 (1 RAM_HALF) ──> palette 256×24 (1 RAM_HALF, CSR write)
    ──> VideoTimingGenerator 640×480@60 ──> VideoCologneChipHDMIPHY (GateMate_demos)
CSR: fb_base (double buffer, swap on vsync), vsync status/counter
```

smunaut's DOOM on iCE40 uses the same model: 320×200 8 bpp, palette in hardware (`I_SetPalette` writes 256 words to `VID_PAL_BASE`), `I_FinishUpdate` = `memcpy` of 64 000 B into the framebuffer, and the timer is a vsync counter (SOURCE `smunaut/doom_riscv` `src/riscv/i_video.c`, `i_system.c`; gateware `smunaut/ice40-playground/projects/riscv_doom/rtl/vid_palette.v`, `vid_framebuf.v`). On our side a `memcpy` of 64 000 B at 8.8 MiB/s takes ~6.9 ms. With a double buffer in SDRAM and an `fb_base` CSR the copy goes away.

**Estimate of total DOOM SoC resources (HYPOTHESIS, starting from the measured S5s9):** S5s9 = 27 874 LT (68%), 48 RAM_HALF, 4 CC_MULT, with 1G + hardware ARP/ICMP/Etherbone + SD card. Removing 1G/Etherbone and adding video (≤ 2 777 LT, measured upper bound with duplicated SDRAM) and the palette/line buffer (+2 RAM_HALF), I expect **≤ 70% LT and ~50/64 RAM_HALF**. That is below ~75%, where J7 showed the placer failing.

## 4. Existing DOOM ports for bare-metal RISC-V

| Project | Platform | CPU | Memory | Video | WAD | Source |
|---|---|---|---|---|---|---|
| **smunaut/doom_riscv** + `ice40-playground/projects/riscv_doom` | iCE40UP5K (iCEBreaker), ~23.3 MHz (`0.925 × 25.175`, `data/clocks.py`) | VexRiscv rv32im, **MulPlugin + DivPlugin**, I$ 2 KiB (`ways_0_datas[0:511]`) | 8 MiB QSPI PSRAM, code from SPI flash | 320×200 8 bpp in SPRAM, palette in HW, 640×480@60 (`COMPAT_MODE`) + dithering, HDMI PMOD | in SPI flash at a fixed address (`libc_backend.c`: `{"doomu.wad", 12408292, 0x40200000}`) | https://github.com/smunaut/doom_riscv (commit 02b0d80), https://github.com/smunaut/ice40-playground/tree/master/projects/riscv_doom, Hackaday: https://hackaday.com/2021/02/07/ice40-runs-doom/ |
| Silice port on IceStick | iCE40HX1K (1280 LUT) + Machdyne QQSPI PMOD 32 MB | small RISC-V (Silice) | PSRAM | – | – | "*very* slow (~0.3 FPS)… Uses an IceStick, @machdyne great QQSPI pmod, @tnt fabulous doom-riscv port" — https://twitter.com/sylefeb/status/1648015362456166402 |
| knazarov/doom-riscv | emulator | – | – | – | – | based on smunaut's port: https://git.knazarov.com/knazarov/doom-riscv |
| doomgeneric | any platform (5 functions: `DG_Init`, `DG_DrawFrame`, `DG_GetTicksMs`, …) | – | – | `DG_ScreenBuffer` 32 bpp (ARGB), needs conversion | via `fopen` | https://github.com/ozkl/doomgeneric |

**Recommendation: smunaut/doom_riscv.** It is already bare-metal, for rv32im, with 8 bpp and a hardware palette, the same model as our plan. doomgeneric works with 32 bpp and needs per-pixel colour conversion, which is too expensive at 20 MHz.

**RAM (SOURCE `i_system.c` `I_ZoneBase`):** 6 MiB zone + WAD (shareware `doom1.wad` 4 196 020 B, Ultimate `doomu.wad` 12 408 292 B) + code ~0.5–1 MiB (HYPOTHESIS) + `screens[]` 5 × 64 000 B. Total < 20 MiB, and we have 64 MiB. **RAM is not a problem.**

**Loading the WAD over TFTP:** DOOM does not need a network stack. LiteX BIOS netboot reads `boot.json` with several images at given addresses (SOURCE `litex/soc/software/bios/boot.c:509` `boot_from_json_buffer`; SD boot does the same). Example:

```json
{ "doom.bin": "0x40000000", "doom1.wad": "0x41000000", "addr": "0x40000000" }
```

In `libc_backend.c` the `fs[]` table is pointed at `0x41000000`, so `open/read` read from SDRAM (the same mechanism as his "flash filesystem"). TFTP in our BIOS is slow, because each 512 B block waits for an ACK. HYPOTHESIS: ~0.3–1 MB/s, so 4.2 MB takes ~5–15 s. **The SD card** (LiteSDCard is already in S5s9, `--boot sdcard`) gives the same, and needs neither Ethernet nor global nets.

**Input (keys):** UART as in smunaut's port (`I_GetRemoteEvent`, script `sw/doom_ctrl.py`), or the 3 buttons on the board (SOURCE README: "3 BTNs") for the first frame. Sound is skipped (smunaut has an empty `s_sound.c`).

## 5. Expected FPS and the multiplication conflict

DOOM is written in 16.16 fixed point. `FixedMul` is `(int64)a*b >> 16` (on rv32im that is `mul` + `mulh`), and `FixedDiv` is in `R_ScaleFromGlobalAngle`, `R_PointToDist` and similar functions. They are called thousands of times per frame.

| CPU (LiteX variant) | Multiplication | Cache | CC_MULT | Fits with | Source |
|---|---|---|---|---|---|
| lite | `MulDivIterativePlugin`, counter to 32 (`VexRiscv_Lite.v:3729`) → ~33 cycles per `mul`, 2× for `FixedMul` | I$ 2 KiB, no D$ | 0 | netboot SoC (71% LT) | SOURCE `VexRiscv_Lite.v`, `SOC_PHASE2` §6 |
| **standard** | `MulPlugin` (4 CC_MULT, 1-cycle throughput) + `DivPlugin` | I$ 4 KiB, D$ 4 KiB (`banks_0[0:1023]`) | 4 | S5s9 (68% LT) ✅, netboot (76%) ❌ | SOURCE `VexRiscv.v:5381, 6127`, lesson J7 |

**The CC_MULT conflict is real, but it does not affect the DOOM SoC.** CC_MULT by itself does not cause failure: S5s9 has 4 CC_MULT and passes. The placer fails only when LT is above ~75% (J7: 3 : 0 for the hypothesis). The DOOM build drops 1G, Etherbone and the hardware stack, so it goes back below that limit. **Recommendation: VexRiscv standard.** With the lite variant `FixedMul` is ~30× slower, so DOOM would be unplayable (HYPOTHESIS < 1 FPS).

**FPS (HYPOTHESIS, not measured):** The 486DX2-66 with 8 MB RAM is the usual quoted target for DOOM (Hackaday: "a 486 DX2 running at 66MHz with 8MB of RAM"); the game is capped at 35 FPS. VexRiscv standard at 20 MHz has about 1/3 of the clock, but runs most instructions in one cycle. The main brake is memory: no L2, D$ is 4 KiB, and the CPU reads only 4.5 MiB/s from SDRAM (measured). Textures, flats and the colormap (8 KiB) keep missing the D$. Estimate: **~3–10 FPS at 20 MHz**. Improvements in order of payoff:

1. colormap and the most frequent lookups in SRAM (on-chip);
2. a larger D$ (8–16 KiB; there is BRAM once the 1G buffers are gone);
3. L2 is disabled because yosys maps the tags into FFs (lesson S1). A small L2 with a manual BRAM instance would be a big gain.

The number must be measured (§7, step 1).

## 6. Examples on GateMate and Machdyne boards

| Finding | Source |
|---|---|
| **DOOM on GateMate is not publicly documented.** I only found Synogate (Game Boy cartridge). They moved to the CologneChip GateMate (1.8 V, DDR2), with their own rv32i core at 48 MHz and fixed-point multiply instructions, but the text does not confirm that DOOM actually ran on GateMate | https://www.synogate.com/blog/2024/bfc_doom_soc_intro.html |
| DVI + LiteX on GateMate exists (colorbars / video terminal) for ULX5M-GS, Olimex GateMate A1 EVB and CologneChip EVB | `~/app/GateMate_demos/LiteX_DVI/` (M. Milanović), MEASURED: build passes (§1) |
| Machdyne: DOOM ran on an IceStick with the Machdyne QQSPI PMOD (~0.3 FPS, Silice) | https://twitter.com/sylefeb/status/1648015362456166402 |
| Machdyne Zucker SoC (PicoRV32 + simple GPU) for Riegel; DOOM is not mentioned | https://github.com/machdyne/riegel |
| RISC-V CPU tutorial for GateMate (learn-fpga port) | https://github.com/fm4dd/gatemate-riscv |

**Conclusion:** as far as I found, we would be **the first with DOOM on GateMate with SDRAM**. That is nice for a demo, but there is no ready solution to copy.

## 7. Shortest path to the first frame on screen

| Step | What | Gateware | Proof of done | Risk |
|---|---|---|---|---|
| **1. DOOM without video** | port `doom_riscv/src/riscv` to LiteX (UART from `libbase`, `I_GetTime` from the LiteX timer, `fs[]` → `0x41000000`, linker for `main_ram`), `-timedemo demo1` | **existing S5s9** (standard, SD) with `--boot sdcard`; boot.json: `doom.bin` + `doom1.wad` | UART prints `timed N gametics in M realtics` → **measured FPS** | low |
| **2. DVI colorbars on v005** | `LiteX_DVI` build (already measured: rc=0) loaded onto the board | no changes | image on the monitor | low (README: DVI works on v004+) |
| **3. 8-bpp framebuffer with palette** | own module (§3) + migen sim testbench (pixel at (x,y) → TMDS input, palette, 2× lines) | S5s9 − 1G/Etherbone + video | sim PASS; P&R ≤ 75% LT; fmax sys ≥ 20 MHz, hdmi5x ≥ 125 MHz | medium (P&R, hdmi5x margin 3%) |
| **4. DOOM on screen** | `I_SetPalette` → CSR palette, `I_FinishUpdate` → `memcpy` or `fb_base` swap on vsync | as 3 | **first frame: DOOM title screen** | low once 1–3 pass |
| 5. (optional) netboot | 100 Mb/s RGMII, TX clock = pixel clock 25 MHz | as 3 + LiteEth MAC (no hw stack) | TFTP boot.json | medium |

**Time estimate (HYPOTHESIS):** step 1 ~0.5 day, 2 ~1 h, 3 ~1–2 days, 4 ~0.5 day.

## 8. Risks

| # | Risk | Likelihood | Mitigation |
|---|---|---|---|
| R1 | Low FPS (< 5) due to SDRAM latency and small D$ | medium | step 1 measures **before** video; colormap in SRAM, larger D$ |
| R2 | P&R failure (J7) if not enough logic is removed | low–medium | no 1G/Etherbone/hw stack; measure LT after each addition |
| R3 | hdmi5x fmax 128.8 MHz vs 125 MHz target (3% margin) | medium | seed sweep as for gtx; serializer `v2` (CDC + Converter) as an alternative |
| R4 | Non-standard pixel clock 25.0 instead of 25.175 MHz | low | most monitors accept it; smunaut and LiteX_DVI do the same |
| R5 | Video DMA steals SDRAM bandwidth from the CPU | low | 3.8 MB/s ≈ 10% of peak |
| R6 | 1G ping fails under SDRAM load (finding 3 in `SOC_PHASE2`) | does not affect the DOOM build | the DOOM build has no 1G |
| R7 | Licence: shareware `doom1.wad` may be redistributed, Ultimate/Doom II may not | – | for the demo use only `doom1.wad` or Freedoom |

## 9. Answers to Klaudio's points

1. **DVI on ULX5M-GS:** YES (IO_SB_A4…B7, works since v004). TMDS 640×480@60 through `CC_ODDR` + `CC_LVDS_OBUF` was measured with a build on our chip. It needs 2 global nets, so it cannot go together with 1G.
2. **LiteX VideoOut:** the ready-made `VideoFrameBuffer` at 640×480 does not work (rgb565 = 92% of peak, no palette). We need 320×200 8 bpp + palette + 2× in hardware: 3.8 MB/s (9.6%). See §3.
3. **DOOM without an OS:** `smunaut/doom_riscv`, 6 MiB zone + WAD. Loading: boot.json (TFTP or SD) to a fixed address. FPS: HYPOTHESIS 3–10 at 20 MHz, measured in step 1. CC_MULT conflict: standard (hw mul) is required, and it fits once 1G/Etherbone is removed (S5s9 proves 4 CC_MULT at 68% LT).
4. **Examples:** there is no public DOOM on GateMate. On Machdyne hardware there is only IceStick + QQSPI (~0.3 FPS). DVI on GateMate exists in `GateMate_demos/LiteX_DVI`.
