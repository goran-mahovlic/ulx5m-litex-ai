# USB keyboard behind the CM4 IO board hub: PNRU USB 1.1 host as a VexRiscv peripheral (TASK-5051)

Goal: a USB keyboard (and mouse) behind the USB2514B hub of the Raspberry Pi CM4 IO board, with the ULX5M-GS in
the CM4 socket, and the same on the USB-C connector J5 of the board.

Status (26.09.2026): phase 1 (gateware) and phase 2a (userspace driver) are implemented and verified in
simulation, host tests and P&R (recommended build: §4.3); phase 2b (Buildroot + Linux 6.12) is built (§6.2),
not booted; **phase 3 (board) started** (§7.1): the PNRU build boots Linux on the board, the USB result is not
read yet because the Pi went offline during the run.

## 1. Hardware facts (from the schematics)

| Item | Fact |
|---|---|
| FPGA USB pins | D+ = IO_EA_A0, D- = IO_EA_B0 (27 R series), go to CM4 pins 103/105 (USB2) **in parallel with J5** |
| Pull network | USB_PULL_P/N = IO_EA_A2/B2 (ULX3S style): low = 12k1 pull-downs = host |
| OTG ID | USB_OTG_ID → IO_EA_A3 (not used by this design) |
| Hub reset | nEXTRST (CM4 pin 100) has pull-up R139: the USB2514B on the IO board is always out of reset |
| Power | +3V3 of the hub comes from the ULX5M-GS; VBUS of the downstream ports from the IO board (AP22653, 1.2 A) |
| Mux | the FSUSB42 on the IO board disconnects the hub only while the micro-USB J11 is plugged in |
| Sharing | J5 and the hub share the lines: **do not use both at the same time** |
| Speeds | the hub talks **full speed** to the host; a low-speed keyboard behind it needs FS **PRE** preambles, so the PHY must do FS + PRE. LS alone works only directly on J5. |

### 1.1 Lab baseboard: Waveshare CM5-IO-BASE-A (instructions #80/#81, 26.09.2026)

The ULX5M-GS in the lab sits on a **Waveshare CM5-IO-BASE-A** ("Mini Base Board (A)",
[schematic](https://files.waveshare.com/wiki/CM5-IO-BASE-A/CM5-IO-BASE-A_Sch.pdf)), not on the official CM4 IO board:

| Item | Fact (Waveshare schematic) | Consequence |
|---|---|---|
| USB-C connector | DP1/DP2, DN1/DN2 = USB0_P/N = module pins 105/103 = the FPGA USB lines IO_EA_A0/B0 directly (parallel to J5), **no hub** | a keyboard on the USB-C is on the root port of the FPGA host |
| USB-C VBUS | = CM4_5V, the 5 V rail of the baseboard (fed through the 40-pin header) | the keyboard has 5 V whenever the board is powered |
| CC1/CC2 | R4/R9 not fitted, go only to module pins 94/96 (not connected on the ULX5M-GS) | — |
| USB0_ID (module pin 101) | tied to GND through R17 (0 R) | **IO_EA_A3 (USB_OTG_ID) must never be driven high** (short to GND); it stays an input |
| Hub CH334F | upstream on USB3-1-D (module pins 163/165), not connected on the ULX5M-GS | hub and USB-A ports are not reachable from the FPGA; USB-A VBUS switch is VBUS_EN (pin 111), floating on the ULX5M-GS (R140) |

So on this board no hub is involved: the PNRU host (LS + FS) or Emard's LS host sees the device on the USB-C
directly. The hub path (PRE) remains for the CM4 IO board and later boards.

## 2. Why the PNRU core, and what was done with it

Source: [emard/usb_host](https://github.com/emard/usb_host) (fork of [gitlab.com/pnru/usb_host](https://gitlab.com/pnru/usb_host)),
commit `47408bb`: `usb11/phy.v` (UTMI level 3 PHY: LS, FS, PRE), `usb11/sie.v` (serial interface engine),
`usb11/regs.v` (register block, register set of ultraembedded/core_usb_host) and an rv32i microcontroller with
firmware `ucmem/*.c` (enum, hub, hid). It is the only small open core found that does **PRE** (LS behind a FS hub);
Emard's `usbh_host_hid` (TASK-5047, `gateware/usb_hid.py`) is LS-only and has no hub support.

> **License:** the PNRU code has no license statement (no LICENSE file, checked 26.09.2026). The Verilog is not
> copied into this repository — `sim/tb_usb_pnru.py` fetches it at the pinned commit for the comparison tests.
> `gateware/usb_pnru.py` is a port (derived work) and `tools/usbhostd/usbh.c` follows the structure of the
> firmware: **ask the author before offering either upstream.** Because this repository is public,
> `gateware/usb_pnru.py` is **not pushed yet**: it is committed on the local branch `usb-pnru-port` (on the build
> machine) and goes to `main` after the author agrees. Until then `--with-usb-pnru`, `sim/tb_usb_pnru.py` and
> `tools/usb_pnru_pnr.py` need that file. `tools/usbhostd/usbh.c` is written independently (only the task
> structure root port → enum → hub → hid is the same) and is published.

Goran's decision: no second SoC in the FPGA; the protocol work (enumeration, hub, HID) runs on the VexRiscv under
Linux, the gateware only moves packets. Following instruction #68 the three Verilog files were **rewritten in
Migen/LiteX** (not wrapped as a black box).

### 2.1 `gateware/usb_pnru.py`

| Class | Original | Notes |
|---|---|---|
| `USBPHY` | `phy.v` | bit clock is a phase accumulator (NCO) instead of a divide-by-4/32 counter, so the same code runs at any clock ≥ 48 MHz; at 48 MHz the NCO steps are exactly 1/4 and 1/32 (= PNRU timing), at 125 MHz 10.42 clocks per FS bit. NCO width is chosen automatically (5 bits at 48 MHz, 20 at 125 MHz, rate error < 10 ppm). |
| `USBSIE` | `sie.v` | same state machine; byte counters 8 bit (packets ≤ 64 bytes) |
| `USBHostEngine` | clocked part of `regs.v` | SOF timer/guard band, scheduler, PHY error latch, optional connect detect; time constants scale with the clock |
| `USBHostPNRU` | register part of `regs.v` | LiteX CSRs in `sys`, engine in its own clock domain `usb`; CDC with MultiReg/PulseSynchronizer; 64-byte OUT/IN buffers are dual-clock memories (2 RAM_HALF); optional EventManager (`with_events`) |

CSRs (`csr.csv`, prefix `usb_pnru_`, one 32-bit word each; with `with_events=False` as in the SoC):

| Word | CSR | Bits |
|---|---|---|
| 0 | `ctrl` | sof_en[0], opmode[2:1], xcvrsel[4:3] (1 FS, 2 LS, 3 LS behind a FS hub = PRE), termsel[5], dp_pulld[6], dn_pulld[7], tx_flush[8] (pulse) |
| 1 | `stat` | dp[0], dn[1], phy_err[2], detect[3] (0 without `with_detect`) |
| 2 | `frame` | frame number of the last SOF |
| 3 | `tx_len` | OUT length 0..64 |
| 4 | `token` | ep[8:5], addr[15:9], pid[23:16], data1[28], hs[29], in[30], start[31] |
| 5 | `rx_stat` | rx_len[7:0], resp[23:16], idle[28], timeout[29], crc_err[30], queued[31] |
| 6 | `tx_data` | write: append a byte to the OUT buffer |
| 7 | `rx_data` | read: next byte of the IN buffer (first-word-fall-through) |

A transaction: write the OUT bytes, `tx_len`, `token` (start = 1); wait for `queued = 0` and `idle = 1`; read
`rx_stat` and `rx_len` bytes. `ctrl` opmode 2 + xcvrsel 0 + both pull-downs drives SE0 (bus reset).

Differences to the PNRU Verilog (intentional; the wire protocol is the same, see §3):

- NCO bit clock (above); the RX sample point is the same (2 clocks after the edge at FS/48 MHz).
- Timing (GateMate routing is ~2 ns per logic level): a register slice on the UTMI interface in both directions,
  the NCO carry (`bit_tick`) is registered, the token CRC5 is registered, and both state machines carry
  `fsm_encoding = "one-hot"`. The last one matters: Migen writes an init value on every register and yosys then
  refuses to re-encode an FSM (log: "Register has an initialization value") unless the register is marked.
- The line state (`stat.dp/dn`) comes from a 2-FF synchronizer, not from the raw pins.
- RX reads are first-word-fall-through (PNRU's CPU reads the byte of the previous pop); the transaction start
  rewinds the buffers instead of a FIFO flush (no flush across clock domains needed).
- The connect debounce counter and the EventManager are optional; the SoC leaves them out (−~150 LT) and the
  driver debounces `stat.dp/dn` in software.

## 3. Verification: the same tests on PNRU and on the port

`sim/tb_usb_pnru.py` runs `sim/usb_pnru/test_usb_pnru.py` (cocotb 2.0 + Icarus) against five DUTs. The USB side is a
Python device model on the resolved D+/D- lines: every line transition is recorded and decoded offline
(edge intervals → bits, NRZI, de-stuffing, CRC check), device responses are driven with exact bit times. Only the
register access differs (PNRU bus vs. LiteX CSR bus); the tests and vectors are identical.

    source tools/sbc_env.sh && python3 sim/tb_usb_pnru.py            # ref48 mig48 mig125 mig48s mig125s

| Test | What is checked |
|---|---|
| t01 | reference CRCs: SETUP addr 0 ep 0 = `2D 00 10`; GET_DESCRIPTOR data CRC16 = `E0 F4`; CRC5 residual 01100 |
| t02 | FS SETUP + DATA0 (8 bytes) → ACK; token and data bytes, CRC5/CRC16 on the wire; TX bit rate and jitter |
| t03 | FS IN → DATA1 (8 bytes) → host ACK, CPU reads the 8 bytes |
| t04 | FS IN with a corrupted CRC16 → crc_err, no ACK |
| t05 | FS IN without response → timeout; NAK → resp = NAK |
| t06 | FS SOF every 1 ms, frame number +1, CRC5 valid |
| t07 | LS device on the port: IN → DATA0 at 1.5 Mb/s, LS polarity; LS keep-alive (EOP only) every ms |
| t08 | LS device behind a FS hub (xcvrsel 3): FS SYNC+PRE, LS token in FS polarity, LS data back, PRE before the ACK |
| t09 | bus reset drives SE0; line state / connect detect |

Results (all configurations 9/9 PASS; `mig48s/mig125s` are the SoC configuration without detect/events):

| DUT | clock | tests | FS TX: mean bit period (fit) | FS TX: max edge deviation (TDJ) | LS TX: period / TDJ | SOF period |
|---|---|---|---|---|---|---|
| ref48 (PNRU Verilog) | 48 MHz | 9/9 | +32 ppm (sim clock 20.834 ns) | 0.00 ns | +32 ppm / 0.00 ns | 1000.09 / 1000.01 µs |
| mig48 (port) | 48 MHz | 9/9 | +32 ppm | 0.00 ns | +32 ppm / 0.00 ns | 1000.09 / 1000.01 µs |
| mig125 (port) | 125 MHz | 9/9 | −8.5 ppm | 3.82 ns | +570 ppm / 3.67 ns (16-bit NCO; 20-bit now: < 10 ppm) | 999.98 / 999.99 µs |
| mig48s, mig125s | 48 / 125 MHz | 9/9 each | — | — | — | — |

At 48 MHz the port reproduces the PNRU wire timing exactly. At 125 MHz every edge falls on the 8 ns grid: the
largest edge deviation is 3.8 ns, against USB 2.0 table 7-9 FS source jitter ±3.5 ns (next transition) / ±4 ns
(paired) — at the limit, while the receiver tolerance is ±18.5 ns; the mean rate is far inside ±0.25 %.

## 4. Clock options (instruction #68)

The 1G + DVI SoC (`grec_3`) uses all four global nets (sys, gtx0, TXC = CLK90 through a BUFG, grx). Three ways to
clock the engine were built:

- **(a) `pll48`** — 48 MHz from a third PLL on fabric routing (`clkbuf_inhibit`), no global net.
- **(b) `gtx125`** — the engine runs in gtx0 (125 MHz), PHY oversampling 10.42× with the NCO, no new clock.
- **(c) `bufg48`** — 48 MHz on a global net, freed by moving TXC from CLK90-over-BUFG to CLK270 over fabric
  routing (the ~5.8 ns fabric route plus 270° ≈ the 90° of the BUFG path, lesson I6).

`python3 gateware/target_soc.py ... --with-usb-pnru --usb-pnru-clk pll48|gtx125|bufg48`

### 4.1 The engine alone (`tools/usb_pnru_pnr.py`, SoCMini + UART bridge, seeds 1–4, post-route)

| Version | pll48 (a) | gtx125 (b), needs 125 MHz | bufg48 (c) |
|---|---|---|---|
| first port | 36.3 – 43.7 MHz, 0/4 pass | 37.4 – 43.0 MHz | 37.0 – 46.5 MHz, 0/4 |
| + UTMI slice | 47.2 – 54.4 MHz, 3/4 | — | 43.1 – 60.8 MHz, 3/4 |
| + registered bit_tick | 49.5 – 56.1 MHz, 4/4 | 51.7 – 53.5 MHz, 0/4 | 51.6 – 56.4 MHz, 4/4 |
| + one-hot FSMs (final) | **58.4 – 63.6 MHz, 4/4** | (≈ 55–60, not rebuilt) | **53.8 – 65.2 MHz, 4/4** |

Engine size: 1 480 CPE_LT + 2 RAM_HALF (SoCMini with the engine 2 413 LT, without it 933 LT).

**Option (b) is not feasible with this architecture:** the engine closes at about 52 MHz, the 125 MHz domain
would need 2.4× that. It would need a different PHY (oversampling front end at 125 MHz feeding a slower back end),
i.e. a new design, not a port.

### 4.2 Full SoC (`grec_3` + USB, seed sweep, post-route)

grec_3 without USB: CPE_LT 29 124 (71 %), RAM_HALF 48/64, sys 22.39 MHz, grx 143.04 MHz (seed 3).

First version (before the one-hot FSMs):

| Build | CPE_LT | RAM_HALF | usb | sys (20) | grx (125) | gtx0* |
|---|---|---|---|---|---|---|
| pll48 s1 | 30 761 (75 %) | 50 | 47.21 FAIL | 25.74 | 137.78 | 45.91 |
| bufg48 s1 | 30 759 (75 %) | 50 | 50.94 | 22.52 | 125.98 | 47.19 |
| bufg48 s3 | 30 759 (75 %) | 50 | 49.91 | 24.62 | **111.94 FAIL** | 47.40 |
| gtx125 s3 | 30 712 (74 %) | 50 | (in gtx0) | 24.08 | 135.67 | 44.68 |
| gtx125 s1 | 31 306 (76 %) | 50 | placer failed (lesson J7) | | | |

\* gtx0 "FAIL at 125 MHz" is expected in every grec build: the DVI path runs in gtx0 with a 1-in-5 clock enable,
nextpnr checks the 5-cycle paths as 1-cycle paths.

Final version (one-hot FSMs), seeds 1–3, all placed at **30 975–30 977 CPE_LT (75.6 %)**, RAM_HALF 50/64
(`ref_clk` is shown against 125 MHz but runs at 25 MHz, it also "fails" in grec_3; gtx0 see above):

| Build | usb (48) | sys (20) | grx (125) | gtx0* | all real clocks |
|---|---|---|---|---|---|
| **pll48 s1** | **63.54** | **24.80** | **140.19** | 43.21 | **PASS** |
| pll48 s2 | 55.78 | 16.89 FAIL | 112.69 FAIL | 44.52 | fail |
| pll48 s3 | 62.04 | 23.28 | 94.43 FAIL | 43.93 | fail |
| bufg48 s1 | 58.76 | 22.31 | 135.80 | 42.72 | PASS |
| bufg48 s2 | 56.25 | 23.33 | 128.60 | 44.50 | PASS |
| bufg48 s3 | — | — | — | — | router did not converge (overuse 1 after ~20 min), stopped |
| gtx125 | — | — | — | — | not rebuilt: the engine alone reaches ~52 of 125 MHz (§4.1) |

With the one-hot FSMs the USB domain has 16–32 % margin on every routed seed; what decides a seed is, as in
every grec build, sys and grx.

### 4.2.1 60 MHz engine clock (after the board test, §7.1)

`--usb-pnru-clk pll48 --usb-pnru-freq 60e6` (same local PLL output, no global net), RX buffer in `sys`, TX RAM
output registered. Seeds 1–8, post-route, all at **30 796–30 818 CPE_LT (75 %)**, RAM_HALF 50/64:

| Seed | usb (60) | sys (20) | grx (125) |
|---|---|---|---|
| **1** | **64.61** | **24.89** | 121.36 FAIL |
| 2 | 64.35 | 21.25 | 122.47 FAIL |
| 3 | 52.75 FAIL | 25.25 | 124.16 FAIL |
| 4 | 61.77 | 22.91 | 114.04 FAIL |
| 5 | 55.42 FAIL | 24.26 | 128.35 |
| 6 | 61.28 | 22.07 | 112.70 FAIL |
| 7 | 64.28 | 24.42 | 105.98 FAIL |
| 8 | 66.14 | 24.66 | 110.99 FAIL |

The TX RAM → usb path went from 56.75 MHz (FAIL, first 60 MHz build) to 243 MHz with the output register. No seed
passes all three; grx misses by 2.5–19 %. On the board seed 1 (sha256 `9aeda4dc…`) receives over 1G (BIOS TFTP of
Image, DTB, rootfs; Linux to the login prompt). Seed 4 of the first 60 MHz build (grx 113.4) stopped at "ARP failed", but in the same
hour the proven pll48 s1 bitstream also failed ARP at the first attempts (the Pi's network was unstable that
evening), so that result is not conclusive. As with the earlier grec builds, a grx FAIL of a few percent can work
on the board; it is checked per bitstream.

### 4.3 Recommendation

| Option | Timing | Risk | Verdict |
|---|---|---|---|
| (a) pll48 | usb 56–64 MHz on all seeds; seed 1 passes every real clock | no change to Ethernet; a fabric-routed clock (skew ~1 ns, included in the analysis) | **recommended** — `build/s_usb2_pll48_s1` (DTS `tools/linux/rv32_usb2_pll48_s1.dts`) |
| (b) gtx125 | engine ~52 MHz vs 125 needed | would need a new PHY architecture | **not feasible** |
| (c) bufg48 | 2 of 2 routed seeds pass | TXC moves from CLK90+BUFG to CLK270 over fabric: 1G TX timing now depends on a placement-dependent fabric route (lesson I6); must be proven with ping 1G on the board, per seed | fallback if (a) misbehaves on the board |

The first board bitstream is therefore **pll48 seed 1** (sha256 `1d62ac96a02bce38…`, packed with
`gmpack --reset`, checked in its build script). It has not been on the board.

## 5. PNRU with its rv32i (for comparison)

PNRU's own `soc.v` (rv32i + usb11 + UART, 16 KB firmware BRAM) on GateMate, stand-alone, 48 MHz clock (PLL 96 MHz
/ 2 as on the ULX3S), seeds 1–4: **6 826 CPE_LT (16.7 %), 1 859 FF, 16 RAM_HALF, 22.4 – 24.3 MHz post-route (needs
48 MHz)**. Added to grec_3 this would be ~88 % CPE_LT and 64/64 RAM_HALF, above the placer limit (lesson J7) and
without timing: it does not fit "bez muke". The Migen engine without a CPU is 4.6× smaller and needs no BRAM for
firmware.

## 6. Software

### 6.1 Phase 2a: userspace driver `tools/usbhostd` (works with the prebuilt 5.14 kernel)

| File | Content |
|---|---|
| `usbh.c`, `usbh.h` | portable host stack: transactions on the CSRs, control transfers (NAK/timeout retries, data toggles), root port (connect debounce 100 ms, bus reset 50 ms, LS/FS detection, disconnect = SE0 on 3 polls), enumeration, hub driver (port power, reset, LS detection → PRE mode, unplug/replug), HID boot keyboard and mouse (SET_PROTOCOL boot, SET_IDLE 0, interrupt IN polling every 10 ms) |
| `usbhostd.c` | Linux main: CSRs through `/dev/mem` (base from the device tree node `usbhost@<csr>`), keys into `/dev/uinput` if it exists, else TIOCSTI into `/dev/tty1` with typematic repeat (as `usbhidd`); `-t` forces TIOCSTI |
| `hidinput.h` | HID boot reports → Linux input events (key codes of `input-event-codes.h`) |
| `S90usbhostd` | init script (starts the daemon only if the DT node exists) |
| `test_usbh.c` | host test: register model + USB2514B hub model (4 ports) + LS boot keyboard model |

    cc -O1 -Wall -I../usbhidd -o test_usbh test_usbh.c && ./test_usbh          # in tools/usbhostd
    make -C tools/doom_linux usbhostd                                          # rv32 static binary

`test_usbh`: 18/18 PASS (14 + FS composite receiver, §7.1) — hub enumerated (addr 1, VID 0424 PID 2514), LS keyboard behind hub port 2 enumerated
(addr 2); hub transactions in FS mode (xcvrsel 1), keyboard in PRE mode (xcvrsel 3), none in a wrong mode; "hi⏎"
typed through the hub; unplug frees the device, replug re-enumerates (addr 3) and types again; an LS keyboard
directly on the root port (J5) works in LS mode (xcvrsel 2); root disconnect detected; HID → input events.

`tools/linux/mkdts.py` adds `usbhost@<csr>` when the build has `usb_pnru`; `tools/doom_linux/mkrootfs_dvi.py`
puts `usbhostd` + `S90usbhostd` into the rootfs.

### 6.2 Phase 2b: Buildroot + Linux 6.12

`tools/linux/buildroot/build_buildroot.sh`: Buildroot 2026.05.3 + linux-on-litex-vexriscv (`05fc5e4`, Linux 6.12,
OpenSBI 1.3.1, VexRiscv-SMP rv32ima ilp32) + `linux_sbc.fragment`:

- fbcon on simplefb with fonts VGA8x8, VGA8x16, **6x8, 6x10, MINI4x6** (lesson K19), no logo;
- **input: evdev + uinput** (keyboard/mouse from `usbhostd` as real input devices; the VT keyboard handler types
  into the console, no TIOCSTI);
- `IP_PNP` (`ip=` on the command line), `/dev/mem` without STRICT_DEVMEM, LiteSPI + mmc_spi (SPI-SD);
- rootfs overlay with `usbhostd` and `S90usbhostd`.

The build container has no root: `file`, `rsync`, `bc`, `cpio` come from Debian packages unpacked with `dpkg -x`
(`BR_HOSTTOOLS`), and Buildroot's check for exactly `/usr/bin/file` is relaxed to `file`.

**Build result (26.09.2026, 13:38):** `Image` (Linux 6.12.0, SMP, gcc 13.4.0, 8.99 MB), `fw_jump.bin` (OpenSBI,
264 KB), `rootfs.cpio` (11.2 MB, contains `usr/bin/usbhostd` and `etc/init.d/S90usbhostd`) in
`~/app/raid/t5051/buildroot/output/images/` on the build machine. Checked in the kernel `.config`: INPUT_UINPUT,
INPUT_EVDEV, FONT_MINI_4x6, FONT_6x8, FRAMEBUFFER_CONSOLE, FB_SIMPLE, IP_PNP, DEVMEM, MMC_SPI, SPI_LITESPI,
LITEX_LITEETH, SERIAL_LITEUART = y, STRICT_DEVMEM off. The first run stopped only in upstream's SD-image
post-image script (it needs `boot.json`/`rv32.dtb` from its `make.py`); the recipe now disables it. The rootfs
(11.2 MB) needs the 12 MB initrd window of the DVI DTS (`mkdts.py` sets `linux,initrd-end = <0x41c00000>`). Not
booted on the board yet.

A kernel HCD driver for the engine is not part of this step (not needed: `usbhostd` + uinput give real input
devices).

## 7. Phase 3: board test

### 7.1 First run on the Waveshare board (26.09.2026, instructions #80–#85)

Device on the USB-C: Goran's **2.4 GHz wireless keyboard + mouse receiver** (dongle). Such receivers are usually
**full speed** and **composite** (keyboard and mouse interfaces), so Emard's LS-only host (`…USBHID_rec1.bit`,
6 MHz, one interface) most likely cannot enumerate it; the PNRU host handles LS and FS and every boot interface.
The first run therefore used the PNRU build, which answers both questions in one boot:

- `usbhostd` now logs the idle line state at start (`usbh: line state D+ 1 D- 0 (FS device)` / `D+ 0 D- 1 (LS
  device)`) and hex-dumps the device and configuration descriptors of every device (`usbh: dev …`, `usbh: cfg …`).
- Host test `test_usbh` case 3: an FS composite receiver on the root port (boot keyboard on EP1, boot mouse on EP2)
  enumerates in FS mode, types "hi⏎" and delivers a mouse report: **18/18 PASS**.
- Boot: `tools/linux/lxrun.sh <bit> rv32_usb2.dtb rootfs_usb.cpio 720 "cat /var/log/usbhostd.log" …` on the Pi
  (rootfs: the REGOČ rootfs + `usbhostd`, padded to 12 MiB for the initrd window).

Result of the first build (`pll48 s1`, sha256 `1d62ac96…`), three boots (Linux 5.14, TFTP netboot):

| Observation | Measured |
|---|---|
| SoC | Linux boots, DVI console, 1G ping: the grec_3 SoC with the PNRU engine works |
| Device speed | `usbh: line state D+ 1 D- 0 (FS device)`: the wireless receiver is **full speed** (Emard's LS host cannot talk to it) |
| Host → device | SETUP, SET_ADDRESS accepted (the device answers on its new address): TX path works |
| Device → host | `usbdiag` (raw register trace): IN with a **valid CRC** returns `01 00 02 00 00 00 08 00`; the device descriptor starts `12 01 00 02 00 00 00 08` — every byte at an even buffer address is lost, odd addresses read 0 |
| Intermittent | some IN packets arrive with `crc_err` (e.g. PID 4b, 8 bytes, CRC flag) |
| Pi outage 16:27–16:41 | a network outage, not a crash (Pi uptime 5 h); the Pi logs under-voltage all day (158× in 5 h, before the test too) |

Two faults, both fixed in the gateware (§7.1.1):

1. **RX buffer:** in the first build the RX RAM was written in the `usb` domain, whose clock is fabric-routed (pll48,
   no global net) and enters the RAM through a CPE; nextpnr merged that RAM into a shared block
   (`$ram$merged$id21`, write enable on `WEA[1]`), and the write address bit 0 was lost: bytes 0 and 1 go to
   location 0 (1 overwrites 0), odd locations stay 0 — exactly `b1 0 b3 0 …`. The TX RAM (written in `sys`) was
   fine. The RTL and the simulation are correct; the fault is in the mapping.
2. **Receiver margin at 48 MHz:** the ULX5M-GS has no differential receiver on the USB lines; like on the ULX3S
   without `usb_fpga_dp`, D+ alone is the data input. New cocotb test `t10` drives the device with a skewed D-
   (SE0/SE1 transients at every edge) and with duty-cycle distortion on D+ (late rising edge):

   | engine clock (samples/bit) | none | D- skew 10/20/30 ns | D+ DCD 8 / 16 ns | skew 20 + DCD 8 |
   |---|---|---|---|---|
   | 48 MHz (4, PNRU) | ok | ok / ok / FAIL | **FAIL / FAIL** (PID 4b → 9b, extra bits) | FAIL |
   | 60 MHz (5) | ok | ok / ok / ok | ok / ok | ok |
   | 96, 125 MHz | ok | ok | ok | ok |

   A few ns of D+ distortion is normal for a single-ended input, so at 48 MHz the receiver has no margin; this
   matches the intermittent CRC errors. From 60 MHz every case passes.

The serial console was the practical obstacle: under load the Linux console drops typed
characters; commands were typed at 0.1 s/char and long-running ones interrupted with Ctrl-C.

#### 7.1.1 Fix: RX buffer in `sys`, engine at 60 MHz

- `gateware/usb_pnru.py`: both RX RAM ports in `sys`; each received byte is handed from `usb` to `sys` with a
  toggle (2-FF synchronizer) and a byte register that holds still until the next push (one byte per 8 bit times
  = 0.67 µs at FS = 13 sys clocks). The simulation results of §3 are unchanged.
- `gateware/target_soc.py --usb-pnru-freq 60e6`: the same third PLL on fabric routing (no global net), 60 MHz.
  The PHY's NCO makes any clock ≥ 48 MHz work (§2.1).
- A line-capture block (1024 samples) was tried for the diagnosis but does not place in the full SoC (placer
  limit, 75 % CPE_LT, lesson J7); it is not in the source.

### 7.2 Remaining order

Order (FPGA rules: do not power-cycle the board, only `openFPGALoader -r`; every bitstream is packed with
`gmpack --reset` — the build script of these builds runs `gmpack --reset`, target_soc.py adds it; on instability
suspect first a missing `--reset`, then timing, never the Pi's supply):

1. LS keyboard directly on J5 (external 5 V: J5.VBUS is not powered by the board): bitstream with
   `--with-usb-pnru`, DTB from `mkdts.py`, `usbhostd` in the rootfs; expect in `/var/log/usbhostd.log`:
   `root port: LS device`, `boot keyboard`, then typing on tty1.
2. ULX5M-GS in the CM4 IO board, keyboard on a hub port: `root port: FS device`, `hub with 4 ports`,
   `hub port N: LS device`, `boot keyboard` (PRE mode).
3. Then the Buildroot kernel with uinput.

## 8. Files

| File | |
|---|---|
| `gateware/usb_pnru.py` | the Migen engine and LiteX peripheral |
| `gateware/target_soc.py` | `--with-usb-pnru`, `--usb-pnru-clk pll48/gtx125/bufg48` |
| `sim/tb_usb_pnru.py`, `sim/usb_pnru/` | cocotb comparison tests (PNRU reference fetched at run time) |
| `tools/usb_pnru_pnr.py` | stand-alone P&R of the engine (Fmax/size per clock option) |
| `tools/usbhostd/` | userspace USB host driver + host test |
| `tools/linux/buildroot/` | Buildroot + Linux 6.12 recipe for the SBC |
