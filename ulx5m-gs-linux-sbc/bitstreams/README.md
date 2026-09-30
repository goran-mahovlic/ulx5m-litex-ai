# Bitstreams — naming: ETH_GateMateA1|A2_<DDMM>_<HHMM CEST>_<Description>.bit

Loading (SRAM only): `openFPGALoader -c dirtyJtag <bit> -r`. All of them have CMD_CFGRST (`gmpack --reset`).

Older bitstreams and CPU-less designs (100 Mb/s `target_eth.py`, 1 Gb/s `target_gbe.py`) are no longer in this
repository; their descriptions and sources are in git tag `pre-cleanup-20260926` (see `docs/REVIEW_LITEX_DUPLICATES.md`).
The folder holds five bitstreams: `pll60 s2 oss0928` (recommended), `pll60 s2 np1817`, `pll60 s1`, `grec_3` and `ghrec_1`.

| File | sha256 | Use |
|---|---|---|
| **`ETH_GateMateA1_2809_1923_Linux_GbE_DVI_USBPNRU_pll60s2_oss0928.bit`** | `bd3e0251f56bae94456c15dc1f6a2e7230cd87961c9f7f31a9e39f6cb8648496` | **Recommended.** Same design as `pll60 s1`, rebuilt with oss-cad-suite 2026-09-28 (nextpnr c4fbb55a, GateMate FF_OBF/FF_IBF clock-inversion fix #1810), seed 2 |
| `ETH_GateMateA1_2909_1015_Linux_GbE_DVI_USBPNRU_pll60s2_np1817.bit` | `dcf82c64a44db1f307feda950e9d8ed991162fdad036b63578af823b345dac75` | Same design, built with nextpnr main `ad8527f8` (incl. #1814 IOSEL timing + #1817 IOBUF fix for the #1814 crash), seed 2. Board-tested 29.09.2026: 36 min under SDRAM load, ping 1800/1800, DVI, USB |
| `ETH_GateMateA1_2609_1646_Linux_GbE_DVI_USBPNRU_pll60s1.bit` | `9aeda4dc1115f22c731039c6119a8d5d95be1bbbb4c68fc029bb0c11ee7a5f5a` | Previous recommended one (oss-cad-suite 2026-09-23). Linux 6.12 + 1G Ethernet + DVI + USB host |
| `ETH_GateMateA1_2509_2330_Linux_GbE_DVI_lr0_rec3.bit` | `1ee3ba4034d63d215c061368921c19102f51d14accd03bd6be7a5968f1aeb597` | Previous recommended one: Linux 5.14 + 1G + DVI + DOOM, no USB |
| `ETH_GateMateA1_2509_2330_Linux_GbE_DVI_USBHID_rec1.bit` | `f035d9a369c7b9eb52d0254ff11b10bd9c6e7a20d6f7788e467b7bdf707daa16` | Emard's low-speed keyboard host. Never tested on the board; replaced by the PNRU host |

## GateMate A2 (CCGM1A2) — TASK-5094

**`ETH_GateMateA2_3009_0411_Linux_ETH100M_DVI_USBPNRU_rxos_selfrst_f1As5.bit`** —
sha256 `872d54ee51ce7f762e9c91e1c3fa80c2144e0932ab90c66e99034acc852dd941`. **Only for a ULX5M-GS with a CCGM1A2.**
Linux 6.12 + **100 Mb/s** Ethernet (`--eth-100m --eth-rx-os`) + DVI + USB PNRU, `--device CCGM1A2 --vopt force_die=1A`,
seed 5, local A2 toolchain (nextpnr `ad8527f8` + the fixes in `docs/nextpnr_a2_repro/`), selfrst, `gmpack --reset`.
Build: `tools/a2_soc_sr_build.sh` (recipe in `docs/A2_CCGM1A2_TASK-5092.md` §7).

Loading: `openFPGALoader -c dirtyJtag <bit> --index-chain 0`. Before loading another design over it, send `R!` on the
UART (resets both dies through `RST_N`); otherwise the new load may not start until a power cycle.
Board-tested on two A2 boards (30.09.2026): login 263 s, ping, USB, DVI, 30 min 1800/1800 pings under SDRAM load.
Why not 1 Gb/s: `CC_IDDR` on die 1B returns no data (see `docs/A2_1G_ETH_SAZETAK.md`).

## TASK-5091 (nextpnr with the #1814 crash fixed upstream in #1817)

**`ETH_GateMateA1_2909_1015_Linux_GbE_DVI_USBPNRU_pll60s2_np1817.bit`** — the `s_usb5_pll60` design unchanged, built with nextpnr main **`ad8527f8`** (PR #1817 "gatemate: only set
IOBUF delays where connection exists", which fixes the #1814 `dict::at()` crash) and Yosys from oss-cad-suite 2026-09-28.
Seed 2, `gmpack --reset` (CFGRST checked). Build dir `build/s_usb5_pll60_s2_np1817/`. CSR map identical, Linux 6.12 images unchanged.

Post-route Fmax: usb_clk 61.2, grx_clk 118.3 (fail at 125), gtx0_clk 46.6, ref_clk 83.0 MHz. #1814 adds IOSEL timing
checks, so the numbers are not fully comparable with the older builds. Seed 1 did not finish routing.

Board test 29.09.2026: login after 266 s, USB PNRU keyboard/mouse, DVI console on the grabber, 36 min under constant SDRAM
load without reboot, ping 300/300 and 1800/1800 × 1400 B (30 min, 0 % loss, avg 17.6 ms), no video recoveries, clean dmesg.
Cause, minimal repro and fix: `docs/NEXTPNR_1814_IOBUF_CRASH_TASK-5091.md`.

## TASK-5090 (rebuild with the GateMate nextpnr fixes of 25.–28.09.2026)

**`ETH_GateMateA1_2809_1923_Linux_GbE_DVI_USBPNRU_pll60s2_oss0928.bit`** — the `s_usb5_pll60` design unchanged (same `target_soc.py` options, same LiteX b6ae9e0b2, CSR map identical to
`s_usb5_pll60_s1`, so `rv32_k612.dtb` and the Linux 6.12 images stay valid), built with **oss-cad-suite 2026-09-28**
(Yosys 0.69+154, nextpnr 0.11.1-34-gc4fbb55a = upstream incl. #1810 "gatemate: fix clock inversion for FF_OBF/FF_IBF pack").
Seed **2**; `gmpack --reset` (CFGRST checked). Build dir `build/s_usb5_pll60_s2_oss0928/`.

| post-route Fmax [MHz] | 26.09. s1 (oss 0923) | 28.09. s1 (oss 0928) | **28.09. s2 (oss 0928)** |
|---|---|---|---|
| usb_clk (60 MHz) | 64.6 | 59.3 (fail) | **64.2** |
| grx_clk (125 MHz) | 121.4 | 109.8 | **127.8** |
| gtx0_clk | 45.6 | 46.1 | 43.6 |
| ref_clk | 104.9 | 91.9 | 83.2 |

Board test 28.09.2026 (ULX5M-GS on the CM4 baseboard, `lxrun.sh`, Image612 + rv32_k612.dtb + rootfs612.cpio): BIOS memtest OK,
netboot, **login after 261 s**, USB PNRU keyboard/mouse found, ping from the Pi 20/20 and 300/300 × 1400 B (avg 24 ms),
DVI console and login prompt on the grabber. Seed 1 also boots (same result) but misses usb_clk; seed 3 did not finish routing.

**nextpnr 3c42800d (#1814 "gatemate: add missing timing check from and to IOSEL", 28.09.2026) crashes on this design**
right after packing, in timing analysis: `terminate … std::out_of_range: dict::at()`. The commit before it (073bb87e),
built the same way with the same chipdb, gets past that point and places normally, so the crash comes from #1814.
Not used here. Fixed upstream in #1817 (`ad8527f8`), see TASK-5091 above.

## TASK-5051 (USB PNRU host, Linux 6.12)

**`ETH_GateMateA1_2609_1646_Linux_GbE_DVI_USBPNRU_pll60s1.bit`** — build `s_usb5_pll60_s1`
(`build/s_usb5_pll60_s1/csr.json` for `tools/linux/mkdts.py`), seed 1, packed with `gmpack --reset`:

    tools/soc_build.sh usb5_pll60_s1 --seed 1 --sdram-clk inv --cpu-type vexriscv_smp --cpu-variant linux \
        --with-gbe --eth-mode mac --boot netboot --with-video --video-ce-rep --video-neg-sync --video-recover \
        --pll-lock-req 0 --with-usb-pnru --usb-pnru-clk pll48 --usb-pnru-freq 60e6

The PNRU engine (`gateware/usb_pnru.py`) is not in this repository yet (see `docs/USB_HUB_PNRU.md` §2), so this
bitstream cannot be rebuilt from `main` alone.

| Resource | Used |
|---|---|
| CPE_LT | 30 818 / 40 960 (75 %) |
| CPE_FF | 10 689 / 40 960 (26 %) |
| RAM_HALF | 50 / 64 (78 %) |
| PLL | 3 / 4 |
| GPIO | 73 / 162 (45 %) |
| Global clock nets | 4 / 4 (`sys`, `gtx0`, `gtx90`, `grx`) |

Timing (nextpnr, post-route): `sys` 24.89 MHz (needs 20), `usb` 64.61 MHz (needs 60). `grx` 121.36 MHz misses
125 MHz by 3 %; it works on the board. `gtx0` "FAIL" is expected: the DVI path runs in it with a 1-in-5 clock enable.

Works (measured on the board, 26–27.09.2026, `docs/USB_HUB_PNRU.md` §7):
- Linux 6.12 from `linux/k612/` reaches the login prompt 266 s after loading.
- 1G Ethernet: ping 1800/1800 in 30 min.
- 33 min without a panic; USB 200 546 transactions, 0 time-outs, 0 CRC errors.
- USB host (PNRU): full speed and low speed, and low speed behind a full-speed hub (PRE). On the board it is
  tested with a full-speed Logitech wireless receiver (keyboard + mouse); low speed and the hub path are tested in
  simulation only.
- Keyboard: key presses reach the console and login works on tty1; autorepeat works (250 ms / 33 ms).
- DVI: 640×480, from a 320×240 RGB565 framebuffer doubled in hardware; the DVI watchdog never fired.

Does not work / not tested:
- SD card (not in this build).
- On the board: a wired low-speed keyboard, and a keyboard behind a hub.
- The console is slow: about 42 ms per echoed character (20 MHz CPU).

## TASK-5040 (DVI / Linux fbcon / DOOM), branch sbc-dvi-usb

Rows without a file here are only in the git tag `pre-cleanup-20260926`.

| Bitstream | Build | Result |
|---|---|---|
| ETH_GateMateA1_2509_1651_Linux_DVI_s1.bit | dvi_1: SMP + --with-video --boot serial (2 clocks, no ETH) | DVI image confirmed (Goran 17:16); 0/45 dropouts at idle, 16/30 under SDRAM mem_test |
| ETH_GateMateA1_2509_1732_Linux_GbE_DVI_s1.bit | gdvi_1: + --with-gbe --eth-mode mac --boot netboot, video in gtx0 with CE | Linux + fbcon + ping; image drops out (36/40 at boot) |
| ETH_GateMateA1_2509_1859_Linux_GbE_DVI_neg1.bit | gneg_1: like gdvi + --video-ce-rep --video-neg-sync | Linux + fbcon + DOOM; 0/30 at idle, 2/30 with DOOM, 4/60 at boot. Left on the board (netboot linuxdvi) |
Cause of the dropouts: VDD_PLL (R23 1 Ω / C42 100 nF, L5 DNP) — the PLLs lose lock under SDRAM load, docs/SBC_DVI_USB_TASK-5040.md §7.
| ETH_GateMateA1_2509_2330_Linux_GbE_DVI_lr1ref_1.bit | gref_1: gneg + STDY CSR (LOCK_REQ=1 reference, TASK-5047) | BIOS 2x mem_test 32 MiB: 0/30 good captures, resync 17900 |
| ETH_GateMateA1_2509_2330_Linux_GbE_DVI_lr0_1.bit | glr0_1: + --pll-lock-req 0 | BIOS 2x mem_test: 30/30; one of two Linux boots permanently black (resync = frames) -> see rec3 |
| **ETH_GateMateA1_2509_2330_Linux_GbE_DVI_lr0_rec3.bit** | grec_3: + --pll-lock-req 0 --video-recover, seed 3 | Recommended until 27.09.2026 (now `pll60s1`). BIOS 30/30 under load, Linux boot 80/80, 19 min resync 0; on the board, TFTP linux (DTB mkdts.py build/s_grec_3) |
| ETH_GateMateA1_2509_2330_Linux_GbE_DVI_USBHID_rec1.bit | ghrec_1: grec + --with-usb-hid, seed 1 (74.8% LT) | P&R rc=0, 0 hold; NOT loaded; waiting for a test with a keyboard (5 V on VBUS) |
