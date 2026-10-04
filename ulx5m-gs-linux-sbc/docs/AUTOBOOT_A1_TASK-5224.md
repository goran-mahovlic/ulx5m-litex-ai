# ULX5M-GS (A1) — last working bitstream and automatic Linux boot (TASK-5224, 04.10.2026.)

Goran's request (04.10. 12:31): find the last bitstream on which everything works, make the board boot Linux on its
own (DVI, USB keyboard, Ethernet), prove it. Raw logs and pictures: `docs/autoboot_T5224/` (`R*`/`D1`/`P*` = single runs 12:36–13:39, `session*.txt/.uart` =
the flash + proof session, `F3b/F3c.txt` = flash writes, `dvi_*.jpg` = grabber). Board session on the Pi:
`~/t5224/` (`autoboot_session.sh`, `session.txt`, `session.uart`).

## 1. Result

| | |
|---|---|
| Chip | **CCGM1A1** (measured, §2) |
| Bitstream | `bitstreams/ETH_GateMateA1_2909_1015_Linux_GbE_DVI_USBPNRU_pll60s2_np1817.bit`, sha256 `dcf82c64a44db1f307feda950e9d8ed991162fdad036b63578af823b345dac75` (TASK-5091, nextpnr `ad8527f8`) — same file as `/home/pi/FPGA/…np1817.bit` |
| SPI flash | AT25QL321 (JEDEC `0x1f4216`, 4 MiB): **np1817 at offset 0, verified** (§5). CFG_MD = 0 → the A1 configures from flash at power-on |
| Linux images | `/srv/tftp` on the Pi: `Image612`, `rv32_k612.dtb`, `rootfs612.cpio`, `opensbi612.bin` (§4) — the set that belongs to np1817 |
| Autoboot chain | power-on → FPGA from flash → BIOS memtest → BIOS netboot from `boot.json` (no input) → OpenSBI → Linux 6.12, `ip=` on the kernel command line brings eth0 up → `buildroot login:` on UART and DVI |
| Proof | reset ×2 (`fpga-jtag gs <bit> -r`, CFGRST): login after **260 s / 262 s** with no input, Pi → board 20/20 × 1400 B both times, DVI login screen; 300/300 pings × 1400 B (0 %); **power-on from flash (P1, no JTAG load): login after 250 s**, 20/20 × 1400 B, DVI login screen (§6) — `session.txt` ends with `SESSION_OK` (14:31:14) |

## 2. Which chip — measured, not taken from a note

| Check | Result | Meaning |
|---|---|---|
| `fpga-jtag gs --detect` | one TAP, `idcode 0x20000001`, `GM1Ax` | an A2 has two TAPs in the chain (`--index-chain 0`, A2_CCGM1A2_TASK-5092.md l. 7) → **A1** |
| A1 bitstream, BIOS | `SDRAM 64.0MiB … Memtest OK` | an A1 bitstream on an A2 does not see the SDRAM → **A1** |

Goran confirmed A1 at 12:51 (instruction #155). The A2 bitstream T5094 is not a candidate on this board.

## 3. What happened on the way (12:36–13:39) — read before blaming hardware

| Time | Step | Result |
|---|---|---|
| 12:36 / 12:40 | np1817, then oss0928 from SRAM | Memtest OK, BIOS starts netboot by itself, **`ARP failed`**; `main_phy_status0 = 0xffffffff`, RXC counter 0, tcpdump on the Pi: 0 frames from 10:e2:d5:00:00:01 |
| 12:44 / 12:47 | `ETH_GateMateA1_2509_1250_Linux_SMP.bit` (25.09.), `t4999_diag6_CFGRST.bit` (drives XI from IO_EB_A3) | the same: MDIO `0xFFFF` at every PHYAD 0–7, RXC 0 |
| 12:59:20 | DirtyJTAG disconnect/reconnect (21 s), Pi under-voltage | board state changed (cables touched at the board) |
| 13:17 | **`phy_probe`** (new, §7) | XI = 25 MHz (X1 runs), **RXC = 125 MHz (PHY alive, 1G link)**, RESET_N pulled high on the board |
| 13:17–13:22 | np1817 again (R5) | netboot OK, **login 261 s**, ping 5/5, Pi → board 20/20 × 1400 B, `input0` = `usb_pnru boot keyboard/mouse` (kbd event0), `/dev/fb0`, dmesg error/fail/oops = 0 |

So the PHY was in a bad state until the board was touched/power-cycled — **not broken**. The 13:05 interim message
"PHY dead" was wrong and was corrected on Telegram at 13:3x. Rule: when Ethernet stops on a bitstream that worked,
ask for a power cycle before any hardware conclusion.

**Own mistake (13:3x):** the third probe build read CFG_MD0..3 (IO_WA_A0/B0/A1/B1) as inputs. The JTAG pins are in
the same bank (TCK/TDI/TMS/TDO = IO_WA_A5/A4/B4/B3); taking any WA pin as user IO made the JTAG chain disappear
(`found 0 devices`, also at 100 kHz) until RST_N. DirtyJTAG SRST does not reach RST_N on gs, so Goran had to power
cycle the board (13:39). It measured `MD=0` once before that. `phy_probe.py` no longer touches bank WA.

## 4. Boot files (Pi 192.168.10.14)

TFTP: `tftp-litex.service` (dnsmasq TFTP-only, root `/srv/tftp`, interface eth0), **enabled + active**, survives a Pi
reboot. Alias `tftpd-hpa.service` added 04.10. (backup `/etc/systemd/system/tftp-litex.service.bak_T5224`), so
`systemctl is-enabled tftpd-hpa` → `enabled`.

`/srv/tftp/boot.json` (written by `/home/pi/FPGA/netboot_app.sh linux`; OpenSBI last = jump address):

| File | Address | sha256 |
|---|---|---|
| `Image612` | 0x40000000 | `79a1e9d2768cd7ae761c2c4de3f8552f0c14337928cb9c0803117d36c75fc3f0` |
| `rv32_k612.dtb` | 0x40ef0000 | `5d8d4ee267282073fb8a770e3835753564b6386c314ef8f405dd64eb499b19bc` |
| `rootfs612.cpio` | 0x41000000 | `75b8eab5aa7110ea276459a8302e061fe4e1186c2a8a66433588c0022ba92f15` |
| `opensbi612.bin` | 0x40f00000 | `f2603c09e584a38bdcd663e98eb26bd46f2c61abc4816e7b98e6eba1216f628d` |

**Which set goes with which bitstream (instruction #157):** this set (built 26.09. for `s_usb5_pll60`, CSR map of
`build/s_usb5_pll60_s1/csr.json`) is valid for every A1 `…USBPNRU_pll60*` bitstream — pll60s1, oss0928 and np1817
have an identical CSR map (bitstreams/README.md). Proven on np1817 today (R5, S1, S2). The A2 bitstream T5094 uses
the same images. `linux514`/`linuxdvi` sets in `netboot_app.sh` belong to the 25.09. bitstreams only.

**Trap:** `tools/linux/linux_boot.sh` switches TFTP back to the demo at its end (`netboot_app.sh demo` deletes
`boot.json`). After that, autoboot loads `boot.bin` (LiteX demo) instead of Linux → `netboot_app.sh linux` again.

## 5. SPI flash

| Step | Command (on the Pi) | Result |
|---|---|---|
| Backup | `sudo fpga-jtag gs --dump-flash --file-size 4194304 flash_before_T5224.bin` | 4 MiB, sha256 `cd3517473707d59c3d915b52a3e16213cadce80d9ffb2b4371958fb7acb51a08`, **all 0xFF** (the flash was empty); file `~/t5224/flash_before_T5224.bin` on the Pi |
| Write ×2 at 6 MHz | `sudo fpga-jtag gs -f --verify <np1817.bit>` | `Verification failed at 418802`, then `at 1052084` — different places, Pi under-voltage in the same seconds → transient |
| Write at 1 MHz | `sudo fpga-jtag gs -f --verify --freq 1000000 <np1817.bit>` | `Verifying write … Done` (83 s) |
| Independent check | `--dump-flash --freq 1000000 --file-size 1286336 flash_after_T5224.bin`; `cmp` with the bit | identical, sha256 `dcf82c64a44db1f307feda950e9d8ed991162fdad036b63578af823b345dac75` = np1817 (`F3c.txt`: `Verifying write … Done`) |

**Undo:** `sudo fpga-jtag gs -f --verify --freq 1000000 ~/t5224/flash_before_T5224.bin` (empty flash) or write
another bitstream the same way. CFG_MD: MD0/MD1 10 k to GND, MD2/MD3 10 k to GND or high through SW1 (SW1 open
= SPI active = boot from flash; closed = JTAG only).

## 6. Proof runs (`~/t5224/autoboot_session.sh`, one UART reader, no typing at any step)

| Run | Trigger | Login | Ping Pi → board | DVI |
|---|---|---|---|---|
| S1 13:46 | `fpga-jtag gs <np1817> -r` | 260 s | 20/20 × 1400 B, avg 25.5 ms | `dvi_S1.jpg`: login prompt, luma 0–251 |
| S2 13:51 | same | 262 s | 20/20 × 1400 B, avg 25.4 ms | `dvi_S2.jpg`: `input: usb_pnru boot keyboard/mouse … input0`, `buildroot login:` |
| ST 13:56 | — | — | **300/300 × 1400 B, 1/s, 0 % loss** | — |
| KB 14:0x | Goran types `root` on the board's USB keyboard | — | — | `dvi_usb_keyboard_root_login.jpg`: `buildroot login: root` + Linux banner on tty1; UART: `login[105]: root login on 'tty1'`, diag `event0 0 → 320` |
| P1 14:26→14:30 | board power cycle by Goran (board stopped answering 14:26:28), **no JTAG load** — FPGA configured from SPI flash | **250 s** (14:30:44) | 20/20 × 1400 B, avg 25.5 ms | `dvi_P1.jpg`: `[174.314686] input: usb_pnru boot keyboard/mouse … input0`, `Welcome to Buildroot`, `buildroot login: _`, luma 0–251 |

P1 UART (`session.uart` from l. 735): BIOS init → `Local IP: 192.168.10.213` → Memtest → `Copying … rv32_k612.dtb / rootfs612.cpio / opensbi612.bin` → `Liftoff!` → OpenSBI v1.3 → `Linux version 6.12.0 … Sat Sep 26` → `fb0: simplefb registered` (12.9 s) → `IP-Config: Complete` (34.5 s) → `usb_pnru … input0` (174.3 s) → `buildroot login:`. The first BIOS lines after power-on are partly garbled (the DirtyJTAG UART re-enumerates while the board powers up); the reader recovers before Memtest. `grep -ci 'oops|panic' session.uart` = 0 over S1, S2, ST and P1. Session ended `== 14:31:14 SESSION_OK`.

## 7. Probe (`litex-eth-ulx5m-gs/gateware/phy_probe.py`)

CPU-less, no MDIO, no XI drive, UART 115200 on IO_NB_B5 (+ IO_NA_A4), one line per second:
`P5224 PH XI RXC C125 EA EB RF RD LV ACT` — frequencies of IO_EB_A3 (XI), IO_EB_A7 (RXC), IO_EB_B8 (CLK125_NDO) in
cycles per 2^20 × 80 ns (0x200000 = 25 MHz), pad-loop match on IO_EA_B7 (bank EA = +3V3, also X1 and the PHY
AVDDH) and IO_EB_B2 (1V8 control), RESET_N level floating (RF) and driven high (RD). Build:
`source …/tools/sbc_env.sh; python3 gateware/phy_probe.py --build` (2 min). 13:17 reading on gs:
`XI=1FFFFA RXC=A0012E C125=000000 EA=77FF EB=77FF RF=1 RD=1` — EA = EB = 0x77FF of 0x8000 (15/16: the one-cycle
mismatch at each edge, same on both banks) → bank EA (+3V3) is powered.

## 8. Open

- JTAG flash writes need `--freq 1000000` while the Pi reports under-voltage (`vcgencmd get_throttled` 0xd0005).
- Power-on from flash is proven (P1). Reset without a power cycle reloads from SRAM only: np1817 (A1) has no `selfrst` (R! is in the A2 builds), and
  DirtyJTAG SRST does not reach RST_N.
