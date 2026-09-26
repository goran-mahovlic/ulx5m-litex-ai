# ULX5M-GS as a standalone computer: DVI framebuffer + Linux fbcon + USB host (TASK-5040)

Date: 2026-09-25. Author: Jelena (REGOČ). Branch `sbc-dvi-usb` (worktree `~/app/litex-eth-ulx5m-gs-1g-sbc`).
Request: Goran, 25 Sep 14:33 ("SD, whichever is more logical; does DVI + framebuffer fit; does USB host fit"), order
according to instructions #44, #51, #55–#58 (console on screen → DOOM from Linux → USB).

## 0. Summary

| Goal | Status | Evidence |
|---|---|---|
| DVI test image from the BIOS | ✅ **Goran confirmed the image (17:16), colours OK** | `ETH_GateMateA1_2509_1651_Linux_DVI_s1.bit`, `tools/dvi/testimg_cmds.sh` |
| Linux fbcon on DVI + 1G ETH in **one** SoC | ✅ on the board: `simplefb registered`, `Console: switching to colour frame buffer device 40x30`, ping .213 3/3, `/proc/fb` = `0 simple`. Goran saw the penguin and the console (18:12), and the HDMI capture records the kernel log. ⚠️ The image drops out under load (§7) | `ETH_GateMateA1_2509_1732_Linux_GbE_DVI_s1.bit`, `tools/linux/rv32_gdvi_1.dts` |
| DOOM from Linux on /dev/fb0 | ✅ 5.5 FPS on the title screens, **1.7–1.8 FPS `-timedemo demo1`**; REGOČ saw DOOM through the capture (18:24) | `tools/doom_linux/`, `/usr/bin/doom` in `rootfs_dvi.cpio` |
| USB host | ❌ **OHCI does not fit** (91% LT with DVI); the prebuilt kernel has no USB anyway | §4 |
| SD | ⏸ SPI-SD (TASK-5039) is the logical choice and it fits (+85 LT), but the card does not work on the 1.8 V bank (J16) | §5 |

## 1. Hardware (point 0)

- **DVI:** DDMI0 = TMDS on `IO_SB_A4…B7` (clk A7/B7, D0 A4/B4, D1 A5/B5, D2 A6/B6), board README: "DVI – tested and works" since v004.
- **USB-C J5 (schematic `ethernet.kicad_sch`):** D+ = `USB25_P` → `IO_EA_A0` (and `IO_EA_A1` in parallel), D- = `USB25_N` → `IO_EA_B0` (`IO_EA_B1`), 27 Ω in series.
  - `USB_PULL_P` = `IO_EA_A2`, `USB_PULL_N` = `IO_EA_B2`, through diodes: high level gives a 1k pull-up (device), low level gives a 12k1 pull-down (host). This is the same circuit as ULX3S US2.
  - CC1/CC2 have 5k1 to ground (the board presents itself as a device).
  - **VBUS is not powered by the board** (`J5.VBUS` = connector only), so a keyboard needs external 5 V (powered hub or Y-cable).
- **SPI flash** MX25R3235F = 4 MB: too small for Linux (Image 7.5 MB + rootfs 3.8 MB).

## 2. DVI + framebuffer

**Why not the LiteX `VideoFrameBuffer` 640×480:** rgb565 needs 36.9 MB/s = 92% of the peak of the 16-bit SDRAM (40 MB/s at 20 MHz).
**`FrameBuffer2x` (`gateware/video_sbc.py`)** reads a 320×240 rgb565 frame (9.2 MB/s, 23%) and doubles pixels and lines in hardware:
- even output lines come from DMA and are written into a 320×16 line buffer (1 RAM_HALF);
- odd lines are repeated from the line buffer.

Linux sees a plain `simple-framebuffer` 320×240 r5g6b5 at `0x43f00000` (last MB of RAM, `reserved-memory no-map`).
The testbench `sim/tb_scaler2x.py` checks pixel (X,Y) = frame (X/2, Y/2), frame integrity and underflow, in both modes (two clocks and CE):
**PASS, 11 frames, 0 errors**.

**Measured with memspeed (BIOS, VexRiscv-SMP):** without video 33.2/13.9 MiB/s (write/read); with framebuffer 27.9/10.5; with 1G and framebuffer 22.9/10.1.

### Global networks: how 1G + DVI fit into 4 BUFG

- 1G uses all 4 global networks: `sys`, `gtx0` 125 MHz, TXC (`gtx90`) and `grx`.
- DVI with two clocks (hdmi 25 + hdmi5x 125) needs 2 more.
- **Solution (commit 86a3033):** hdmi5x is the same clock as `gtx0` (125 MHz). The whole video chain (VTG, scaler, TMDS encoders, serialisers) runs in `gtx0` and advances only when `ce` = 1, i.e. one clock in five (25 MHz). The TMDS clock is the 10-bit word `0b0000011111` through the same serialiser.
- **Trap:** memory ports are not under `CEInserter`. The line buffer write enable and read enable must follow `ce` (`Scaler2x.we_ce`), otherwise the write repeats the wrong pixel and `dat_r` runs one pixel ahead. The sim caught this: 132 errors, 0 after the fix.
- nextpnr reports `gtx0` FAIL (48–68 MHz) because it counts pixel paths as single-cycle. The real requirement for them is 25 MHz. The critical path (VTG `hcount`) is multi-cycle.

## 3. Feasibility table (P&R, nextpnr-himbaechel, CCGM1A1; placer limit ≈ 71% LT, J7)

| Build | CPE_LT | RAM_HALF | CC_BUFG | PLL | Clock (fmax) | Fits | On the board |
|---|---|---|---|---|---|---|---|
| Linux SMP + 1G MAC (baseline, smp8_9) | 22 644 (55%) | 45 | 4 | 2 | sys 20.5 | ✅ | Linux 3/3 |
| SMP + DVI fb, no ETH (dvi_1/3/9) | 23 566 (57%) | 32 | 3 | 2 | sys 26.7, hdmi5x 166 | ✅ | ✅ image confirmed (s1) |
| SMP + DVI fb + SPI-SD (dvisd_1/9) | 23 957 (58%) | 37 | 3 | 2 | sys 26.9, hdmi5x 128 | ✅ | not loaded (SD does not work, J16) |
| SMP + VideoTerminal (UART mirror), no ETH (vt_1/9) | 20 471 (50%) | 35 | 3 | 2 | sys 23.5, hdmi5x 144 | ✅ | not loaded (fbcon worked first) |
| **SMP + 1G MAC + DVI fb, CE in gtx0 (gdvi_1)** | **28 037 (68%)** | **48** | **4** | 2 | sys 25.3 | ✅ | **✅ Linux + fbcon + ping (s1); s9 dead** |
| SMP + DVI fb + USB OHCI (Cdma, 48 MHz) | 37 535 (91%) | 35 | 4 | 3 | – | ❌ placer: "Unable to find legal placement" | – |

- 48 MHz from 25 MHz on the GateMate PLL is 47.917 MHz (−0.17%; USB FS allows ±0.25%).
- **gdvi seed 9** passed P&R (rc=0), but there is not a single byte on the UART. Seed 1 works. A seed-dependent fault must be checked on the board, not only by rc=0.

## 4. USB host: assessment

- The SpinalHDL OHCI (`--with-usb`, as in linux-on-litex) alone adds ~14 000 LT and ~5 900 FF. With DVI that is 91% LT and the placer gives up. Without DVI it would be ~34%+55%, which is also above the limit.
- The prebuilt kernel 5.14 has no USB subsystem (`strings Image`: no ohci/usbcore). OHCI needs a new Buildroot kernel.
- **Recommendation:** instead of OHCI, a small **hardware USB HID (low-speed keyboard) host** that converts key presses into ASCII and injects them into UART RX (e.g. `nand2mario/usb_hid_host`, 12 MHz). The keyboard then works both in the BIOS and in the Linux console without any kernel change. It needs 1 PLL + 1 global network (12 MHz): the build without 1G has room (3/4 BUFG), but with 1G+DVI there is none (4/4), unless 12 MHz is derived from `sys` or runs with CE.
- **HW:** 5 V on VBUS from outside (powered hub). The pull-down goes to `IO_EA_A2/B2` = 0.
- **Emard's USB 1.1 HID host (instruction #61, `emard/ulx3s-misc` `examples/usb/usbhost` + `usb11_phy_vhdl`), standalone synthesis `synth_gatemate` (GHDL for the VHDL PHY, 8 B report):**
  - measured: 590 LUT (201 LUT2 + 156 LUT3 + 229 LUT4 + 4 MX4) + 135 ADDF + 406 DFF, i.e. **~725 CPE_LT (~1.8%)**;
  - log: `~/.tmp/t5040/usbhid_synth.log`;
  - with 1G+DVI (gtree 28 568 LT = 69.7%) this is **~71.5%**, right at the placer limit; for margin, remove the diagnostic counters (~3×32 bits) or shrink the BIOS ROM.
  - **6 MHz clock without a new global network:** `gtx0` 125 MHz with CE 1/21 gives 5.952 MHz (−0.79%, and USB LS allows ±1.5%). The CE must be a tree (K15).
  - **Bridge to Linux:** the kernel has no USB, so `usbhidd` in userspace reads the HID report from the CSR via `/dev/mem` (like `csrpeek`) and writes characters to `/dev/tty1` via the `TIOCSTI` ioctl.
  - **Order (Goran #61):** only once the image is stable, and that waits for the VDD_PLL HW fix (§7).

## 5. SD: decision

**SPI-SD (TASK-5039) is the logical choice**: +85 LT and +5 RAM_HALF, and without a card the BIOS just times out and continues (J15). It fits with DVI (dvisd, 58%).
The card still does not respond on the 1.8 V bank (J16, Goran's test at 16:56 with the carrier board at 1.8 V: `FatFs error 3`, no `mmcblk`).
So for DVI, Linux boots via netboot, which the 1G + DVI combination made possible (§2).

## 6. How to reproduce

```bash
# DVI test image (no ETH):
tools/soc_build.sh dvi_1 --cpu-type vexriscv_smp --cpu-variant linux --with-video --boot serial --sdram-clk inv --seed 1
bash tools/sd/bios_cmds.sh <bit> $(bash tools/dvi/testimg_cmds.sh)            # on the Pi as fpga-klaudio
# Linux + 1G + DVI (fbcon):
tools/soc_build.sh gdvi_1 --cpu-type vexriscv_smp --cpu-variant linux --with-gbe --eth-mode mac --boot netboot \
    --with-video --sdram-clk inv --seed 1
python3 tools/linux/mkdts.py build/s_gdvi_1 > rv32dvi.dts; dtc -O dtb -o /srv/tftp/rv32dvi.dtb rv32dvi.dts   # Pi
~/FPGA/netboot_app.sh linuxdvi; APP=linuxdvi bash tools/linux/linux_boot.sh <bit> 330
# on the board: setsid getty 38400 tty1 &   (login prompt on DVI)
```

Bootargs: `fbcon=font:VGA8x8 console=tty0 console=liteuart …`, i.e. 40×30 characters. `/dev/console` stays on the UART (no keyboard).
The kernel boots in ~90 s instead of ~25 s, because for every log line fbcon scrolls 150 KB of framebuffer through SDRAM.

## 7. Image stability: the root cause is the PLL power supply (measured with HDMI capture)

Measurement: MS2109 capture on the Pi (`http://192.168.10.14:8090/snap.jpg`).
- Snapshot series (`~/.tmp/t5040/idle_series.sh`): a uniform `070707` means the capture has no signal, and `000000` is a black image with a valid signal.
- CSR counters in FrameBuffer2x and in the `ref` domain (PLL lock drop counters) are read via `csrpeek` (Linux) and `mem_read` (BIOS).

| Test | No signal |
|---|---|
| DVI_s1 (2 clocks, no 1G), BIOS idle | 0/45 |
| DVI_s1, BIOS `mem_test` (full SDRAM load) | 16/30 |
| 2 clocks + SDRAM `DRIVE=6` mA, `mem_test` | 16/16 during the test |
| 2 clocks + deterministic serialiser load, `mem_test` | 16/16 during the test |
| 2 clocks + PLL SPEED, `mem_test` | 13/40 |
| 1G+DVI, single CE (gdvi_1), Linux boot | 36/40 |
| 1G+DVI, CE per block (gcer_1 / gneg_1 / gtree_3), Linux boot | 5/48, 4/60, 8/60 |
| 1G+DVI (gneg_1), Linux idle | 0/30 |
| 1G+DVI (gneg_1), DOOM | 2/30 |

**Decisive measurement (dvipll_1, `USR_PLL_LOCKED` drop counters, counted in the `ref` domain without a PLL):**
- idle: sys PLL +0 and video PLL +0 over 30 s;
- after an 8 MB `mem_test`: sys PLL **+3787**, video PLL **+2665**;
- after a second `mem_test`: +3539 / +2439;
- idle again after that: +0.

**Under SDRAM load both PLLs lose lock thousands of times.** The video PLL then gives an unstable clock so the sink loses sync, and the sys PLL also explains one unexplained SoC reset during Linux.

**Schematic (`power.kicad_sch`):** `VDD_PLL` (U4.P16) gets `VDD_CORE` only through **R23 = 1 Ω** (0603) and **C42 = 100 nF** (0402); ferrite **L5 is DNP**. The VDD_PLL filter (1 Ω / 100 nF, ~1.6 MHz) does not suppress core noise that appears during SDRAM traffic.
*(Corrected in Kosjenka's review, §8: `VDD_SER_PLL` has NO ferrite — L6 and L7 are also DNP, so the SerDes PLL has the same filter R105 1 Ω + C127 100 nF.)*

**Recommendation (HW), corrected in §8:** L5 **has no footprint on the PCB** (neither do L6/L7), so "solder L5" cannot be done. What can be done:
- **step A (reversible, no parts removed):** 10 µF ceramic from **TP6** (Ø1 mm test pad on the VDD_PLL net) to the nearest ground. With the existing R23 this gives an RC low-pass filter at ~16 kHz, damped, so no LC resonance;
- **step B (only if A does not help):** replace R23 (0603) with an MPZ1608 ferrite (0603, same footprint), keeping the 10 µF;
- check VDD_CORE under load.

Gateware cannot fix this; it can only reduce the load, and DRIVE and other ways of loading the serialiser change nothing.

Fixed along the way in the 1G+DVI (CE) mode, which is necessary but not sufficient:
- CE tree (13 CE registers);
- registered `ready` towards the CDC FIFO.

nextpnr detailed timing still shows single-cycle CE paths of 9.5–11.5 ns, because `set_false_path -from/-to` in nextpnr-himbaechel "does nothing (yet)", so the placer does not see which paths are really critical.

## 8. Review (Kosjenka, 2026-09-25, follow-up TASK-5043)

Independently checked: schematic/PCB `~/app/ulx5m-gs-hw/hardware` (commit 61b6709) with the `kicad_netlist.py` tool, the reset path in `gateware/crg.py` and the testbench `sim/tb_scaler2x.py` (both modes PASS, 11 frames, 0 errors).

**Corrections to §7:**

| Claim | Finding | Evidence |
|---|---|---|
| "SerDes PLL has an MPZ1608 ferrite (L6)" | ❌ L6 and L7 are `dnp yes`, and the SerDes PLL has the same filter R105 1 Ω + C127 100 nF | `kicad_netlist.py --net VDD_SER_PLL`; `(dnp yes)` in power.kicad_sch |
| "solder L5" | ❌ L5, L6 and L7 have no footprint on `ulx5m-gs.kicad_pcb` (only L1–L3 are on the PCB); R23 is in parallel with L5, 0603 | grep `Reference "L5"` in .kicad_pcb = 0 hits |
| VDD_PLL = VDD_CORE through R23 1 Ω + C42 100 nF | ✅ correct; TP6 (Ø1 mm) is on the same net, which is the natural place for the patch | `--net VDD_PLL`: C42, L5, R23, TP6, U4.P16 |

**Rejected alternative hypothesis (gateware):** `USR_PLL_LOCKED` drops do NOT reset the video and sys domains. `_pll_reset` goes through `StickyLock` (1 ms stable, then 1 forever), so the cause of the dropouts is not a false reset from a jittery lock flag, but the clock itself.

**Discriminating experiment (one change, same test):**
1. board as it is: `dvipll_1`, BIOS `mem_test` 8 MB → sys/video counters (reference: +3787/+2665);
2. step A (10 µF on TP6) → same test;
   - counters drop by an order of magnitude or more: VDD_PLL cause confirmed, then DVI dropouts via capture (target 0/30 under `mem_test`);
   - counters do not change: the cause is not the local PLL filter but VDD_CORE (core droop) or the clk25 input clock. Then measure VDD_CORE with an oscilloscope on the core TP, and skip the ferrite (step B).

**Budget for the USB keyboard (§4), checked:** 28 568 + ~725 = 29 293 CPE_LT of 40 960 = 71.5%. This is exactly at the placer limit (J7), not below it. Before integration, free ≥ 800 LT, e.g. remove the diagnostic counters from FrameBuffer2x and the `ref` domain once stability is confirmed. The `TIOCSTI` bridge works on kernel 5.14 (the `LEGACY_TIOCSTI` restriction only arrived in 6.2).

**Recommended order:** HW step A → same measurement test → (if it passes) HID host with freed LT → `usbhidd` → login on `tty1`. The task belongs to the ULX5M-GS project, not to the PRJ-033 bucket.

## 9. Review (Dora, 2026-09-25, follow-up TASK-5044): a second noise path and Goran's remarks about the image

### 9.1 SDRAM noise has a second path to the PLL: +1V8 → oscillator and clock input

§7 and §8 look only at the VDD_CORE → VDD_PLL path. The netlist shows a second, equally direct path (`kicad_netlist.py`, `~/app/ulx5m-gs-hw/hardware`):

| Node | Connection | Evidence |
|---|---|---|
| SDRAM_VCC (U10 VDD+VDDQ, FPGA banks **WB, WC, NA, NB** = all SDRAM pins) | **R116 = 0 Ω to +1V8** (R115 DNP) | `--net SDRAM_VCC`, `--ref R116`, value `0R` in gpio.kicad_sch |
| Oscillator **Y1** 25 MHz (ASE2-25.000MHZ, CLK_25MHz → `IO_SB_A8`) | pins 1 and 4 **directly on +1V8**, no R/ferrite | `--ref Y1` |
| **VDD_CLK** (U4.T14) | +1V8 | `--net '^\+1V8$'` |
| VDD_SB (bank of the clk25 input and TMDS outputs) | +1V8 through **R122 = 4R7** | `--net '^\+1V8_SB$'`, `--ref R122` |
| +1V8 source | TLV62569 → L1 → R10 0R | `--net 'N\$0075'` |

**Three hypotheses with the same symptom (both PLLs lose lock under `mem_test`):**

| | Path | What it predicts | Does step A (10 µF on TP6) help? |
|---|---|---|---|
| P1 | VDD_CORE → VDD_PLL (R23 1 Ω / C42 100 nF) | drops follow core and controller **activity**, almost independent of data | yes |
| P2 | +1V8 (SDRAM DQ/VDDQ current) → Y1 and VDD_CLK → **input clock jitter** for all PLLs | drops follow **data changes on DQ**: random data ≫ constant | **no** |
| P3 | VDD_CORE droop at the regulator | like P1 | no |

**Existing data do not rule out P2:**
- `DRIVE=6` mA (16/16) changes only the FPGA outputs when writing, not the SDRAM outputs when reading, nor the chip's VDDQ current.
- Idle gives +0 even though TMDS constantly toggles on bank SB. This rules out constant switching, but not transient loads from SDRAM traffic.
- Both PLLs lose lock at the same time and in a similar ratio (+3787 / +2665). This fits both a shared VDD_PLL and a shared clk25 input, so it does not separate P1 from P2.

**Experiment that separates P1 and P2 without soldering:** `tools/dvi/pll_discriminator.sh` (bitstream `dvipll_1`, sha256 `b59afe0d…`).
- On the same 32 MiB and with the same number of SDRAM commands, only the content on DQ changes:
  - `mem_write` with constant 0 and with constant 1 (DQ static);
  - `crc` over constant data;
  - `mem_test` (LFSR data);
  - `crc` over LFSR data;
  - a repeated `mem_write` with 0 as a repeatability check.
- After each step the counters `0xf0002000`/`0xf0002004` are read, and the script prints the per-step deltas.
- The parser was checked on Jelena's UART log (`lt_dvild_1`: 0x0632 / 0x051c) and on a synthetic sequence (delta 3787 / 2665 correct).

Interpretation:
- **WR ≫ W0/W1 and RX ≫ R1:** P2 holds. Step A will then not help, and the HW patch goes to the Y1 supply: cut the traces to +1V8 on pins 1 and 4 and insert 10 Ω + 10 µF (RC ~1.6 kHz; drop = 10 Ω × oscillator I_DD, for a few mA that is ten to a few tens of mV, and I_DD must be confirmed in the ASE2 datasheet). Also add a larger capacitor on +1V8 near U10.
- **W0 ≈ W1 ≈ WR and R1 ≈ RX:** P1 or P3 holds, so step A from §8 remains the right first move.
- The experiment takes ~5 min and does not need Goran, so it should be run **before** soldering. That way the TP6 patch is done only if P1 is confirmed.

### 9.2 Goran's remarks about the image (16:13): penguin, large letters, strict monitor

| Remark | Cause | Solution | Cost |
|---|---|---|---|
| Penguin in the top left corner | kernel logo | bootarg **`logo.nologo`** (the string exists in `Image`, `strings`) | 0: only `boot.json`/bootargs |
| Very large letters | intentional: 320×240 frame, VGA8x8 font, ×2 scaler → 16×16 px per character, 40×30 characters | (a) **640×240 with vertical-only doubling**: 80×30 characters, each 8×16 px (looks like VGA text mode); DMA 640·240·2·60 = **18.4 MB/s (46% of peak)**. (b) New kernel with a MINI4x6/6x8 font (prebuilt 5.14 has only VGA8x8 and VGA8x16, K19). | (a) doubles the framebuffer SDRAM traffic, which is exactly what causes the lock drops, so it comes **only after** stabilisation (§9.1). (b) Buildroot rebuild, which is also needed for OHCI. |
| "Monitor is strict about 640×480@60" | in the 1G+DVI (CE) mode the pixel clock is `gtx0`/5 = **25.000 MHz**; VESA asks for 25.175 MHz (**−0.70%**, outside the typical ±0.5%), so H = 31.25 kHz and V = 59.52 Hz | not the cause of the dropouts: the BIOS image DVI_s1 was stable (17:16), and the dropouts follow SDRAM load (§7). An exact 25.175 MHz is not possible while video is tied to the 125 MHz `gtx0`. | informational; if the monitor also refuses when idle, check on another monitor or the HDMI capture |

### 9.3 Recommended order (correction to §8)

1. `tools/dvi/pll_discriminator.sh` (without Goran) → P1 or P2.
2. If P1: step A (10 µF on TP6). If P2: RC filter for Y1 and a larger capacitor on +1V8.
3. Repeat the same experiment and the HDMI capture snapshot series (target 0/30 under `mem_test`).
4. Immediately, independent of 1–3: add `logo.nologo` to the bootargs.
5. After stabilisation: free LT (§8), HID host, and optionally the 640×240 mode.

**Status of this follow-up:** since 20:52 CEST the Pi (`192.168.10.14`) responds neither to SSH nor to the capture (`Connection timed out`), so experiment 9.1 **was not run on the board**. The board state is unchanged (Jelena's, TFTP `linux`).
