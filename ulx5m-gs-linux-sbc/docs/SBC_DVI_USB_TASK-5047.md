# ULX5M-GS SBC: PLL lock under SDRAM load — timing or power supply? (TASK-5047)

Date: 2026-09-25. Author: Jelena (REGOČ). Branch `sbc-dvi-usb`, continuation of `docs/SBC_DVI_USB_TASK-5040.md` §7–§9.
Request: Goran, 21:15 — suspects bad timing (on the edge), asks for a review of the SDRAM design; USB keyboard; a more readable console.
The Pi `192.168.10.14` did not respond until ~21:50 CEST (ssh timeout), so the first hours were analysis and builds. After that everything was
**measured on the board** (§2.2, §2.3). The Pi's `dmesg` has 599× `Under-voltage detected`, which is useful alongside Goran's power supply check.

## 1. Answer to the timing hypothesis

**Short:** the loss of lock does not come from logic timing or from SDRAM timing. There is, however, a gateware cause that
amplifies the effect of the noise: **LiteX leaves `LOCK_REQ=1`, and with that CC_PLL disables the output clock every time lock drops.**

### 1a. Is the drop counter correct? (CDC, glitch, comparison with LOCKED_STDY)

| Question | Finding | Evidence |
|---|---|---|
| Can the counter invent drops? | No. The raw `USR_PLL_LOCKED` goes through a `MultiReg` (2 FF) into the `ref` domain (clk25 from the pin, no PLL); the falling edge of the synchronised signal is counted. Metastability can shift an edge by one clock, but it cannot create a new one. | `gateware/target_soc.py` (counters), idle +0 over 30 s (§7 TASK-5040) |
| Does it count all drops? | No, it is a **lower bound**: drops shorter than 40 ns are not seen, and bursts merge into one. | same |
| CDC towards the CPU | The 16-bit binary counter crosses into sys through a `MultiReg`; a read during counting can be torn. The reads were done after the load (counter at rest), so the values 3787/2665 are valid. | `lt_dvild_1/uart.txt`: 0x0632/0x051c |
| LOCKED_STDY | LiteX leaves it unconnected. **It is now connected**: `gateware/pll_stdy.py` (`GateMatePLLStdy`), CSR `pll_stdy` (bit i = PLL i, 1 = lock has not dropped once since the last re-arm) and `pll_stdy_rst`. According to DS1001 fig. 2.33, STDY drops and stays 0 on every loss of lock in the silicon itself, independent of sampling. | elaboration: `.USR_PLL_LOCKED_STDY (…locked_stdy)`, `csr.csv` 0xf0002008/0xf000200c |

### 1b. Why the drops kill the image: `LOCK_REQ` (DS1001, table 2.19)

| CLK_OUT_EN | LOCK_REQ | PLL_LO | output |
|---|---|---|---|
| 1 | 0 | X | ✓ runs |
| 1 | **1** | **0** | ✗ **disabled** |

`litex/soc/cores/clock/colognechip.py` sets `p_LOCK_REQ = 1` (default). **Each of the ~3800 measured lock drops
therefore means a hole in the sys and video clocks**, not just a flag that flickers. The TMDS clock stops, so the sink loses sync.
In the sys domain the CPU stops, and an unpredictable clock interruption also explains the occasional SoC reset.

Possible positive feedback mechanism: lock drops → clock stops → SDRAM traffic stops → noise disappears → lock returns
→ traffic resumes → … Thousands of drops per `mem_test` fit such an oscillation.

**Fix without soldering:** `--pll-lock-req 0`. The PLL then keeps giving a clock even while the lock detector flickers; a short phase disturbance
means jitter, but not a missing clock. The builds `dvistdy_1` → `dvilr0_1` differ in **exactly 4 bytes** of the bitstream
(`cmp -l | wc -l` = 4) with identical placement and timing, so the A/B is clean.

### 1c. SDRAM timing review (IS42VM16320E-75, 1.8 V, sys 20 MHz, CL=2, `--sdram-clk inv`)

| Parameter | Spec (-75) | LiteDRAM @20 MHz | Margin |
|---|---|---|---|
| tRCD / tRP | 22.5 ns | 1 cycle = 50 ns | 27.5 ns |
| tRAS | 45 ns | 1 cycle = 50 ns | 5 ns |
| tRFC | 80 ns | 2 cycles = 100 ns | 20 ns |
| tWR | 15 ns | 1 cycle = 50 ns | 35 ns |
| **tREFI** | 64 ms/8192 = 7812.5 ns | **157 cycles = 7850 ns** (LiteDRAM rounds UP) | **−0.5%, out of spec** → fixed to 7.6 µs (152 cycles) |
| CL | 2 (≤ ~100 MHz) | 2 @ 20 MHz | large |
| Write (inv clock) | tIS ~1.5–2.5 ns / tIH ~1 ns | FPGA drives on sys↑, SDRAM samples 25 ns later | setup ≈ 25 − tco(3–8) ≥ 17 ns; hold ≈ 25 ns |
| Read | tAC(CL2) ≤ ~8 ns, tOH ≥ 2.5 ns | data valid from +33 to +77.5 ns after SDRAM↑, FPGA samples on sys↑ = +25 ns after it (+1 cycle) | ~15–25 ns on both sides |

- At 20 MHz the SDRAM runs with a margin of 5 to 35 ns on every parameter. The only error is tREFI (+0.5%), with no effect on the PLL.
- An SDRAM timing error would show up as a **data error**, not as a lock drop. The opposite was measured: at boot the counter
  was already at 0x632 (1586 drops), and the boot reported `Memtest OK`. Linux and DOOM work (TASK-5040).
- nextpnr timing (sys domain, post-route): the critical path is **inside the CPU** (VexRiscv barrel shifter, 47.4 ns = 7.9 ns
  of logic + 39.6 ns of routing, in `glr0_1`), not in the SDRAM PHY.

### 1d. Seed sweep with timing report

Post-route Fmax (nextpnr-himbaechel `--freq 125` for all domains; real requirements: sys 20, hdmi/ref 25, pixel paths in gtx0 = 25 MHz with CE, grx 125).

| Build | Seed | CPE_LT | sys (≥20) | hdmi5x/gtx0 | grx (≥125) | Note |
|---|---|---|---|---|---|---|
| dvistdy_1 (= dvilr0/dvislew/dvipix) | 1 | 24 434 (59.7%) | 22.20 | hdmi5x 131.98 ✅ | – | 2 clocks, BIOS |
| dvis16_1 (sys 16 MHz) | 1 | 24 201 | 22.44 (≥16) | 160.85 ✅ | – | |
| gref_1 (= glr0_1) | 1 | 28 605 (69.8%) | 21.04 | gtx0 63.3 (CE) | 139.26 ✅ | 1G+DVI, candidate |
| glr0_3 | 3 | 28 605 | 24.63 | 59.3 | **104.96 ❌** | RX may fail |
| glr0_5 | 5 | 28 605 | 23.58 | 54.9 | **123.18 ❌** | edge |
| glr0_9 | 9 | 28 605 | 24.98 | 53.3 | **90.04 ❌** | |
| gneg_1 (on the board) | 1 | 28 037 | 25.84 | 54.0 | **102.55 ❌** | TASK-5040 reference |

- **sys has positive slack in all seeds** (21.0–25.0 MHz against a 20 MHz requirement), and hdmi5x passes in the 2-clock build (132 MHz).
- The seed changes `grx` (RGMII RX, 1G), not video or SDRAM. `grx` timing failures affect Ethernet, not PLL lock.
- The `hdmi_clk`/`ref_clk`/`gtx0` FAIL in the report is false (they are constrained to 125 MHz, but run at 25 MHz or with CE).
- Logic timing has no mechanism to bring down the analogue lock detector. The PLL sees only clk25 at its input and the power supply.

**Conclusion for Goran:** timing is not the cause. The cause is analogue (power supply noise or input clock jitter, §9.1 TASK-5044, P1/P2),
and `LOCK_REQ=1` turns every detector glitch into a missing clock. The first move without soldering is `LOCK_REQ=0`, the second is the P1/P2 discriminator.

## 2. Gateware mitigation: one change per build

All 2-clock BIOS builds have the same seed (1) and the same arguments; only the listed item changes.

| Build | Change | Bitstream vs. reference | Lock drops under `mem_test` | Image dropouts | Status |
|---|---|---|---|---|---|
| `dvistdy_1` | reference (+ STDY CSR, observation only) | sha256 `38353a26…` | ref. ≈ +3787/+2665 (dvipll_1) | ref. 16/30 | waiting for the Pi |
| `dvilr0_1` | `--pll-lock-req 0` | 4 bytes different | ? | ? | **waiting for the Pi, largest expected effect** |
| `dvislew_1` | `--sdram-slew slow` | **bit-identical to the reference** | = ref. | = ref. | **no effect:** SDRAM outputs are already SLOW (nextpnr `.txt`: 42× `GPIO.SLEW 1`, the only `SLEW 0` = `sdram_clock` with explicit `SLEW=fast`), see §2.1 |
| `dvidrv6_1` (TASK-5040) | `--sdram-drive 6` | – | – | 16/16 | measured earlier: does not help |
| `dvis16_1` | sys (= SDRAM) 16 MHz instead of 20 | different placement | ? | ? | waiting for the Pi |
| `dvipix_1` | pixel 25.175 MHz (VESA) instead of 25.000 | `OUT_CLK 125.875` | ? | ? | waiting for the Pi (for the strict monitor) |
| "PLL ref from another source" | – | – | – | – | **not possible**: the only clock on the board is Y1 25 MHz (`IO_SB_A8`); RXC from the PHY (125 MHz) exists only after link-up and is derived from the same Y1 (PHY XI = clk25, `gateware/crg.py`) |
| "smaller burst/refresh peaks" | – | – | – | – | GENSDRPHY is SDR 1:1 without bursts (BL=1). Refresh is one AREF every 7.6 µs and does not create a peak; LiteDRAM refresh postponing (`tREFI`×N) would only **increase** the peaks |

### 2.1 SLEW
`SLEW=slow` in the CCF is accepted without a warning (nextpnr reports `Unknown value … for SLEW` for invalid values), and the configuration is
unchanged. The control build `dvifast_1` (`--sdram-slew fast`) gives **39× `GPIO.SLEW 0`** and 4× `SLEW 1` in the nextpnr `.txt`, while the default
and `slow` give 42× `SLEW 1`. **So the SDRAM outputs are already SLOW (default)** and this measure does not exist.

### 2.2 MEASURED: LOCK_REQ A/B on 1G+DVI (BIOS, same placement, 4-byte difference)

The 2-clock builds of this round (`dvistdy/dvilr0/dvislew/dvipix/dvis16`) **do not start the CPU** (no UART; the old `dvipll_1` on the same board
works). nextpnr reports them with a **hold violation in the sys domain** (clk-skew −3.89 ns, BRAM icache → FF). The old builds and all 1G builds
have 0 hold violations. The A/B was therefore done on the target 1G+DVI core: `gref_1` (LOCK_REQ=1) and `glr0_1` (LOCK_REQ=0), same seed and placement.

Procedure (`~/.tmp/t5047/ab2.sh`): BIOS → test image → re-arm STDY → 20 s idle → 2× `mem_test` 32 MiB with 30 snapshots (4 s) → counters.

| | `gref_1` LOCK_REQ=1 | `glr0_1` LOCK_REQ=0 |
|---|---|---|
| idle 20 s: sys / tx drops, STDY | +0 / +0, STDY 0x3 | +0 / +0, STDY 0x3 |
| 2× `mem_test` 32 MiB: sys / tx drops | **+10 288 / +55 694** | **+1942 / +49 909** |
| STDY after load | 0x0 (both PLLs lost lock in silicon) | 0x0 (same) |
| snapshots under load | **0/30 valid** (13 no signal, the rest black) | **30/30 valid** (test image) |
| FB underflow / resync | 0 / **17 900** (black even after the load) | **0 / 0** |
| `Memtest` | OK | OK |
| 1st shorter measurement (16 MiB, 6 snapshots) | sys +5398, tx +45 327, 4/6 no signal, underflow 236k | sys +387, tx +42 105, **6/6**, underflow 0 |

**Conclusions:**
1. The lock detector flickers under SDRAM traffic in both cases (thousands of drops, and STDY in silicon drops), so **the noise/jitter is real**. Logic timing plays no role here.
2. With `LOCK_REQ=1` every drop is a hole in the clock → the image disappears. **With `LOCK_REQ=0` the image stays stable under full load.**
3. `mem_test` passes in both cases: SDRAM data is correct (1c).

### 2.3 Second fault: the video path in CE mode has no reset (permanent black image)

- `cd_gtx0` in `SoCCRG` is created with `with_reset=False` and without an `AsyncResetSynchronizer`. The CE counters (13), VTG and the video side of the CDC FIFO
  are therefore **never reset** after configuration.
- When they drift apart after a clock disturbance, the state stays permanently: **resync on every frame, underflow 0, black image with valid sync**.
  Restarting the DMA (`dma_enable` 0→1, also resets the scaler) does not fix it (measured).
- Seen in `gref_1` after the load (17 900 resyncs) and in **one of two Linux boots of `glr0_1`** (14 697 resyncs in 14 706 frames,
  60/60 black snapshots). The other boot was 0/60 no signal, with the console visible the whole time.
- **Fix (`--video-recover`):** a `vid` domain (same gtx0 clock, no new BUFG) with reset `~lock_tx | vrst`, and `vsys` (sys clock) for the CDC
  write side. `ResyncWatchdog` in FrameBuffer2x: 4 consecutive resyncs without a good frame → 128 sys cycles of reset for the whole video path.
  CSR `main_video_recoveries` counts recoveries. Test `sim/tb_watchdog.py`: 4/4 PASS.

### 2.4 MEASURED: `grec_3` = LOCK_REQ=0 + `--video-recover` (recommended build)

`ETH_GateMateA1_2509_2330_Linux_GbE_DVI_lr0_rec3.bit` (seed 3: 0 hold, sys post-route 22.39 MHz, grx 143 MHz PASS, 29 124 LT = 71.1%).

| Test | Result |
|---|---|
| BIOS, 2× `mem_test` 32 MiB, 30 snapshots | **30/30 valid**, underflow 0, resync 0, recoveries 0; sys +8930 / tx +43 333 detector drops; Memtest OK |
| Linux netboot, 80 snapshots during boot (240 s) | **80/80 valid** (no black frames and no dropouts); fbcon without the penguin (`logo.nologo`) |
| Linux, 19 min of running | frames 72 805, **underflow 0, resync 0**, recoveries 0 |
| DOOM `-timedemo demo1`, 25 snapshots | 21 images + 4 black at the console → DOOM transition (DOOM clears the screen at start; the following snapshots show the game); during DOOM itself (second series) **30/30 valid** (`gneg_1`: 2/30 dropouts) |

Comparison with the previous state (TASK-5040, same monitor/capture): `gdvi_1` 36/40 dropouts during boot, `gneg_1` 4/60 during boot and 2/30 with DOOM,
DVI_s1 16/30 under `mem_test`.

**Linux boot is slow and varies** (initramfs unpacking 63–156 s, login after 226 s up to ~10 min). The cause was not measured. It is known (TASK-5040)
that fbcon scrolls 150 KB through SDRAM for every line. A trap in the test: `mem_test` at 0x41000000 leaves LFSR data in the initrd window, so
the kernel hit garbage behind the 8.4 MB cpio (`Initramfs unpacking failed: invalid magic`) and got stuck. That is why the rootfs was padded with zeros to 12 MiB
(`rootfs_hid.cpio` on TFTP).

## 3. Measurement (scripts)

```bash
tools/dvi/mitigation_sweep.sh dvistdy_1 dvilr0_1 dvis16_1 dvipix_1     # ~6 min per build
cat ~/.tmp/t5047/sweep_table.txt
```
Per build: test image → counters + STDY → re-arm STDY → 2× `mem_test` 32 MiB (40 capture snapshots in parallel) → counters + STDY.
Line: `sys_unl +N  2nd_unl +N  stdy re-armed=0x3 after_load=0x?  no-signal n/40`. The parser was checked with a synthetic log (delta 3787/2665 correct).

**Interpretation:**
- `dvilr0_1`: counters stay high (the detector still flickers), and no-signal ≈ 0/40 → LOCK_REQ mechanism confirmed; `glr0_1` goes to Linux.
- `dvilr0_1`: counters high and the image still drops out → the clock is really bad (phase jumps), so it remains a HW issue (§9.1 P1/P2, `pll_discriminator.sh`).
- STDY `after_load` = 0 with a high raw counter confirms that the silicon itself sees the drop; STDY = 1 would mean the raw signal flickers falsely.

## 4. Console (Goran's remarks)

| Item | Status | Evidence |
|---|---|---|
| `logo.nologo` | ✅ in `tools/linux/mkdts.py` (bootargs) | `grep nologo tools/linux/mkdts.py` |
| 640×240 (80×30 characters of 8×16 px) | ✅ gateware: `Scaler2x(sw, hdouble=False)`, `--video-640x240`, `VIDEO_FB_WIDTH` = 640 → mkdts stride 1280 | `sim/tb_scaler2x.py`: **4/4 PASS** (2 clocks, CE, 2 clocks 640×240, CE 640×240; 11 frames, 0 errors) |
| Build 1G+DVI+LOCK_REQ0+640×240 (`g640_1`) | P&R rc=0, 28 666 LT (70%), 0 hold; **sys post-route 20.16 MHz (0.8% margin)**; not loaded on the board | `soc_g640_1.log` |
| SDRAM bandwidth | 640 words per line pair (64 µs) = 10 Mwords/s = **50% of the peak** of the SDR at 20 MHz (320×240: 25%). CPU memspeed will drop. **Enable only once `dvilr0`/`glr0` shows a stable image**, because the doubled DMA traffic amplifies exactly the noise that breaks lock. | |

## 5. USB keyboard (Emard's HID host)

| Part | Status | Evidence |
|---|---|---|
| Sources | `gateware/verilog/usbhost/` (emard/ulx3s-misc d0c6f15: usbh_host_hid, usbh_sie, crc5/16, setup ROM); VHDL PHY → Verilog via `ghdl --synth` (the LiteX flow has no VHDL) | `gateware/verilog/usbhost/README.md` |
| Wrapper | `gateware/usb_hid.py` `USBHIDHost`: 6 MHz = gtx0/21 (5.952 MHz, −0.79%, LS ±1.5%) from a counter on local routing (`clkbuf_inhibit` on the FF itself, **no new BUFG**), host pull-downs, CSR `usb_hid_report` (64 b), `usb_hid_seq`, `usb_hid_led`, `usb_hid_ctrl` (bus reset) | `csr.csv` 0xf0003800… |
| Trap | First attempt (`ghid_1`): `clkbuf_inhibit` only on `cd.clk` → yosys inserted a 5th `CC_BUFG` on the FF output, and nextpnr (`More than 4 BUFG`) crashed with `dict::at()`. The attribute must be on the **register** that drives the clock net. | `soc_ghid_1.log` |
| P&R 1G+DVI+USB (`ghid2_1`) | rc=0, **30 232 CPE_LT (73.8%)**, above the previous "placer limit" of 71%, but the placer succeeded; 0 hold; sys 23.66 MHz; `usb_clk` 50.9 MHz (needs 5.95); grx 100 MHz (like `gneg_1` on the board) | `soc_ghid2_1.log` |
| Bridge to Linux | `tools/usbhidd/usbhidd.c` (static rv32im ELF, same runtime as doom/csrpeek): reads the CSR via `/dev/mem` every 8 ms (`clock_nanosleep`), checks for torn reads via seq, and writes new keys to `/dev/tty1` with `TIOCSTI` (US layout, Shift/Ctrl, arrows, typematic 500 ms / 30 Hz) | `tools/usbhidd/hidkey.h` + `test_hidkey.c`: **11/11 PASS** (gcc on the host) |
| Boot | `etc/init.d/S90usbhidd`: `usbhidd &` and `getty 38400 tty1` in a loop → login on the DVI screen | `~/.tmp/t5047/rootfs_dvi_hid.cpio` (8.4 MB, in the 12 MB initrd window) |
| On the board (`ghid2_1`, no watchdog) | the bitstream works: Linux boots, network works (ping), image stable; `usbhidd` and the USB CSRs were not fully checked (boot ~10 min, console busy) | `~/.tmp/t5047/lx_ghid2_1/uart.txt` |
| Build with watchdog (`ghrec_1`) | P&R rc=0, 30 635 LT (74.8%), 0 hold, sys 22.24 MHz, grx 97 MHz (FAIL as on `gneg_1`, which still works) → `ETH_GateMateA1_2509_2330_Linux_GbE_DVI_USBHID_rec1.bit`, **not loaded** | `soc_ghrec_1.log` |
| Protection | `usbhidd` starts only if the DT has `usbhid@<csr>` (`mkdts.py`); a fixed 0xf0003800 would write into `video_fb2x_dma_loop` on a build without USB. `sleep_ms` falls back to `ppoll_time64` if `clock_nanosleep_time64` does not work (never busy-loops) | `tools/usbhidd/` |
| Test with a keyboard | ❌ **not done**: needs Goran (keyboard on J5 + **external 5 V on VBUS**, J5.VBUS is not powered by the board) | – |

## 6. Board state (end of TASK-5047)
The board runs `grec_3` (Linux + 1G + DVI, LOCK_REQ=0, watchdog), and login and DOOM work. **TFTP is back in `linux` mode.**
Additional files on the Pi: `/srv/tftp/rootfs_hid.cpio` (12 MiB: doom, csrpeek, usbhidd, S90usbhidd), `rv32_{glr0_1,ghid2_1,g640_1,grec_3}.dtb`.
To reboot the recommended build: `bash /tmp/lxrun.sh <bit> rv32_grec_3.dtb 600` (on the Pi; script in `~/.tmp/t5047/lxrun.sh`).

## 7. Next steps
1. Goran: USB keyboard on J5 + 5 V on VBUS, load `…USBHID_rec1.bit` (DTB `mkdts.py build/s_ghrec_1`, rootfs `rootfs_hid.cpio`) and
   type on the DVI screen. `usbhidd` writes `/var/log/usbhidd.log`, and `csrpeek <usb_hid> 5` shows report/seq/led.
2. 640×240 with the watchdog (`--video-640x240 --video-recover`), then measure; `g640_1` has only 0.8% sys clock margin.
3. Goran's voltage measurements (VDD_PLL / +1V8 under load): the lock detector still flickers (STDY=0). LOCK_REQ=0 hides the symptom, but the noise
   remains (P1/P2 from §9.1 TASK-5044, `tools/dvi/pll_discriminator.sh`).
