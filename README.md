# Base folder of AI projects for ULX5M-GS

FPGA projects for the **[ULX5M-GS](https://github.com/intergalaktik/ulx5m-gs)** board, built with LiteX and the open-source toolchain
(Yosys, nextpnr-himbaechel, gmpack).

The board has:
- a CologneChip GateMate CCGM1A1 FPGA,
- 64 MB SDRAM,
- a gigabit Ethernet PHY (KSZ9031),
- a DVI output.

Board hardware (schematics, PCB, production files): https://github.com/intergalaktik/ulx5m-gs

---

## ulx5m-gs-linux-sbc — the board as a small Linux computer

This project turns the FPGA into a small computer. Linux 6.12 boots over the network, with the console on a DVI
monitor and a USB keyboard.

### Features

- **CPU:** VexRiscv-SMP RISC-V (rv32ima, Sv32 MMU), 1 core, 20 MHz.
- **Cache:** 4 KiB instruction, 4 KiB data, no L2.
- **SDRAM:** 64 MB (IS42VM16320E, 16 bit), LiteDRAM controller.
- **Ethernet:** 1000 Mb/s (KSZ9031, RGMII), our own PHY with the LiteEth MAC.
- **Video:** DVI 640×480, from a 320×240 RGB565 framebuffer that is doubled in hardware.
- **USB:** USB 1.1 host (port of the PNRU core): full speed, low speed, and low speed behind a full-speed hub.
- **UART:** serial console at 115200 baud, on the same USB cable as JTAG.
- **Boot:** LiteX BIOS loads Linux over TFTP.
- **Clocks:** `sys` 20 MHz, Ethernet 125 MHz, USB 60 MHz, pixel clock 25 MHz (125 MHz with a 1-in-5 clock enable).

### What works (measured on the board, 26–27 September 2026)

- Linux 6.12 reaches the login prompt 266 s after the FPGA is loaded (Linux 5.14 took 4–15 min).
- Gigabit Ethernet: link, network boot, ping 1800/1800 in 30 min.
- USB: a Logitech wireless receiver (full speed) is found as keyboard + mouse. In 33 min: 200 546 transactions,
  0 time-outs, 0 CRC errors.
- USB keyboard: typed keys reach the console, and `root` logs in on the DVI screen. Autorepeat works
  (250 ms delay, 33 ms period).
- DVI: the Linux console is on the screen, and the DVI watchdog never had to restart the picture.
- Stability: 33 min without a panic or oops.

### What does not work yet

- **SD card.** Linux sees the SD controller, but the card does not answer. The likely cause is voltage:
  the FPGA pins run at 1.8 V and the card at 3.3 V.
- **Not tested on the board:** a wired low-speed keyboard, and a keyboard behind a USB hub. Both pass in simulation.
- **Slow console.** Each typed character takes about 42 ms to show, and every command takes seconds to start.
  The CPU runs at 20 MHz with small caches.
- **DOOM** was shown on Linux 5.14 (bitstream `…lr0_rec3.bit`). It is not in the Linux 6.12 image yet.
- **PLL noise.** Under heavy memory traffic the FPGA clock (PLL) briefly reports "not locked". We changed
  the design so the clocks keep running anyway, which keeps the picture stable. The cause is noise on the
  PLL supply (VDD_PLL), so the real fix is in hardware.

### FPGA resources (recommended bitstream)

| Resource | Used |
|---|---|
| CPE_LT (logic) | 30 818 / 40 960 (75 %) |
| CPE_FF (flip-flops) | 10 689 / 40 960 (26 %) |
| RAM_HALF (block RAM) | 50 / 64 (78 %) |
| PLL | 3 / 4 |
| GPIO | 73 / 162 (45 %) |
| Global clock nets | 4 / 4 |

Timing after routing: `sys` 24.9 MHz (needs 20), USB 64.6 MHz (needs 60).

### Which bitstream to use

The bitstreams are in `ulx5m-gs-linux-sbc/bitstreams/`:

| File | Use |
|---|---|
| `ETH_GateMateA1_2609_1646_Linux_GbE_DVI_USBPNRU_pll60s1.bit` | **Use this one.** Linux 6.12 + Ethernet + DVI + USB keyboard. |
| `ETH_GateMateA1_2509_2330_Linux_GbE_DVI_lr0_rec3.bit` | Older: Linux 5.14 + Ethernet + DVI + DOOM, no USB. |
| `ETH_GateMateA1_2509_2330_Linux_GbE_DVI_USBHID_rec1.bit` | Older USB keyboard host (low speed only). Never tested on the board. |

The checksums and build commands are in `ulx5m-gs-linux-sbc/bitstreams/README.md`. Older bitstreams are not in
this repository.

---

## ulx5m-gs-m2-serdes — SerDes link between two GateMate boards

ULX5M-GS and ULX5M-M2 connected by their SerDes lane, with one JTAG probe per board.

| Rate | Result |
|---|---|
| 0.3 Gb/s | 8b10b link in both directions, bit-exact (360/360 reads). 0 errors in 1.1·10⁹ words per direction (BER < 6.7·10⁻¹¹). |
| 1.25 Gb/s | 0 errors in 1.9·10⁹ words per direction (BER < 4·10⁻¹¹). |
| 2.5 Gb/s | Works, but not error-free: BER about 10⁻⁹ … 10⁻¹¹, and it changes from one load to the next. Needs `TX_NEG=1`. |
| 5 Gb/s | Does not work: BER 10⁻² … 10⁻¹. About 60 register settings did not help; the next step is hardware (supply noise). |

A script proves step by step that the data goes over the external cable (idle tests, error injection, pulling the cable).

Details: `ulx5m-gs-m2-serdes/README.md`.

---

## How to try it on another computer

**You need:**
- the board, connected to a gigabit switch,
- a DVI monitor,
- a USB keyboard on the USB-C connector (it needs 5 V on VBUS; our baseboard, a Waveshare CM5-IO-BASE-A, supplies it),
- a Linux PC with `openFPGALoader`, a TFTP server and Python 3.

**1. Set the PC's IP address.** The addresses are built into the bitstream and the device tree:
- the board is `192.168.10.213`,
- it downloads Linux from `192.168.10.14`.

Give your PC the address `192.168.10.14`, or build the bitstream and the device tree again with other addresses.

**2. Copy Linux into the TFTP folder.** The images are in this repository:

    cd /srv/tftp      # your TFTP folder
    cp /path/to/ulx5m-litex-ai/ulx5m-gs-linux-sbc/linux/k612/*.gz .
    gunzip -f *.gz

This gives `Image612`, `opensbi612.bin`, `rootfs612.cpio` and `rv32_k612.dtb`.
`ulx5m-gs-linux-sbc/linux/k612/README.md` says how they were built.

**3. Tell the board what to load.** In the TFTP folder, create `boot.json`:

    { "Image612": "0x40000000", "rv32_k612.dtb": "0x40ef0000", "rootfs612.cpio": "0x41000000", "opensbi612.bin": "0x40f00000" }

`ulx5m-gs-linux-sbc/tools/linux/netboot_app.sh linux` writes exactly this file (the default since 28.09.2026;
`linux514` selects the old 5.14 images). If the DVI screen shows only coloured noise, the board is still in the
BIOS: Linux was not loaded (usually `boot.json` points to other files). The console appears about 12 s into the kernel.

**4. Load the FPGA and wait.**

    openFPGALoader -c dirtyJtag ulx5m-gs-linux-sbc/bitstreams/ETH_GateMateA1_2609_1646_Linux_GbE_DVI_USBPNRU_pll60s1.bit -r

The serial console is on the same USB cable (`/dev/ttyACM0`, 115200 baud). After about 4.5 minutes you get
a login prompt, on the serial console and on the DVI screen. Log in as `root` (no password).

**Linux 5.14 and DOOM (older).** Use `…lr0_rec3.bit`, the prebuilt `linux_2022_03_23.zip` from
https://github.com/litex-hub/linux-on-litex-vexriscv/issues/164, the device tree from
`ulx5m-gs-linux-sbc/tools/linux/rv32_grec_3.dts`, and `tools/doom_linux/mkrootfs_dvi.py` to add DOOM (you need
your own `doom1.wad`). The steps are in the git history of this README (before 27 September 2026).

---

## Building the bitstream yourself

**You need:**
- oss-cad-suite, 2026-09 or newer,
- a RISC-V GCC (`riscv-none-elf`),
- LiteX, migen, litedram, liteeth, litex-boards, litesdcard and `pythondata-cpu-vexriscv_smp`,
  at the versions linked under [Built on](#built-on).

Set `OSS_CAD_SUITE` and `LXROOT` to point to them. The recommended bitstream was built with:

    cd ulx5m-gs-linux-sbc
    source env.sh
    python3 gateware/target_soc.py --build --output-dir build/s_usb5_pll60_s1 --seed 1 \
      --cpu-type vexriscv_smp --cpu-variant linux --sdram-clk inv \
      --with-gbe --eth-mode mac --boot netboot \
      --with-video --video-ce-rep --video-neg-sync --video-recover --pll-lock-req 0 \
      --with-usb-pnru --usb-pnru-clk pll48 --usb-pnru-freq 60e6
    python3 tools/linux/mkdts.py build/s_usb5_pll60_s1 --font 6x8 \
      --append "consoleblank=0 usbhostd=-v,-s,60 sbcdiag=0xf0002800" > rv32_k612.dts

The USB engine `gateware/usb_pnru.py` is a port of the PNRU USB host. The original has no license statement yet,
so we do not publish the port until its author agrees (see `ulx5m-gs-linux-sbc/docs/USB_HUB_PNRU.md` §2). Without
it, leave out the three `--usb-pnru` options and use seed 3: that builds the older `…lr0_rec3.bit` (no USB).

Linux 6.12 itself is built with `ulx5m-gs-linux-sbc/tools/linux/buildroot/build_buildroot.sh` (1–2 hours, about 15 GB).

Different seeds give different timing, and not every seed produces a working Ethernet receiver. Seed 1 (with USB)
and seed 3 (without) are tested on the board. If you change the design, test the new bitstream on the board.

### Important: every bitstream must start with a configuration reset (`gmpack --reset`)

**The problem.** gmpack writes a "sparse" bitstream. It contains only the parts of the FPGA that the design
uses. The rest of the chip is not touched. When you load a new design into the FPGA's SRAM, parts of the
previous design can therefore stay behind and mix with the new one.

**What we saw:**
- A bitstream that worked a minute earlier stopped working after another design had been loaded.
- The UART showed stuck bits, or went completely silent.
- Ethernet sent no frames at all.

Only a power cycle helped. And on our setup the board's power cannot be switched off from software
(the USB hub does not support it).

**Why `openFPGALoader -r` does not fix it.** With the DirtyJTAG cable, `-r` only sends a very short reset
pulse and does not wait. We could not show that this pulse reaches the FPGA's `RST_N` pin at all.

**The fix.** `gmpack --reset` puts the command `CMD_CFGRST` at the start of the bitstream. This command clears
all configuration latches before the new design is written, so every load starts from a clean chip.

**Proof.** The same design without `--reset` sent 0 frames and 0 bytes on the UART. With `--reset` it
immediately sent 58 frames and a clean UART. Since then, every recommended bitstream works 3 times out of 3,
even when a "dirty" design was loaded just before it.

**In this project.** LiteX does not add `--reset` on its own. `gateware/target_soc.py` adds it to the gmpack
options for every build, so you do not have to do anything. If you build the bitstream in another way (other
scripts, or gmpack by hand), add `--reset` yourself. All bitstreams in `bitstreams/` already contain it.

### LiteX is used without changes

The build uses plain upstream LiteX at the version linked under [Built on](#built-on). An older version of
this folder had a small optional LiteX patch (one line that did not change the logic, and one extra line in the
BIOS start-up screen). It was removed on 26 September 2026; see
`ulx5m-gs-linux-sbc/docs/REVIEW_LITEX_DUPLICATES.md`.

The scripts in `tools/` still contain our local paths and IP addresses. Change them before you use them.

## More information

`ulx5m-gs-linux-sbc/docs/` has the measurements and lessons we learned. Start with these files:
- `USB_HUB_PNRU.md`: the USB host, Linux 6.12 and the board measurements,
- `SBC_DVI_USB_TASK-5047.md`: the clock/PLL problem,
- `LESSONS_GATEMATE.md`: general GateMate lessons.

---

## Built on

This work is built on these open-source projects. Without them it would not exist. Each link points to the
exact version we used. All are plain upstream `master`, without local changes, unless the table says otherwise.

| Project | What we use it for |
|---|---|
| [LiteX](https://github.com/enjoy-digital/litex/tree/b6ae9e0b227354aecffef5339d3e946f2395ac09) | SoC builder, BIOS, CPU integration, build flow |
| [LiteEth](https://github.com/enjoy-digital/liteeth/tree/96547670d9d4776b81edba0c8a82e5f10ed8a1e3) | Ethernet MAC |
| [LiteDRAM](https://github.com/enjoy-digital/litedram/tree/51de2b05e9b8e555cde8ff5508b5996945a2fd22) | SDRAM controller |
| [LiteX-Boards](https://github.com/litex-hub/litex-boards/tree/8741034010bdbd98f2740d7b7345d93a480b7877) | ULX5M-GS platform (pin definitions) |
| [LiteSDCard](https://github.com/enjoy-digital/litesdcard/tree/17718d9258ac2dd62ac23e2eecd7ac613a050986) | SD card support (not working on this board yet) |
| [Migen](https://github.com/m-labs/migen/tree/e19524c963a8342952840983047557707fbe0b6a) | Python hardware description language that LiteX uses |
| [VexRiscv SMP](https://github.com/litex-hub/pythondata-cpu-vexriscv_smp/tree/217d23d7e9ad5556c17a73dc6ffc1971765f3d7c) / [VexRiscv](https://github.com/litex-hub/pythondata-cpu-vexriscv/tree/642ecfed1c84460555d6d803d660cc60cfc1ecb6) | RISC-V CPU (SMP for Linux, the plain one for the smaller test SoCs) |
| [linux-on-litex-vexriscv](https://github.com/litex-hub/linux-on-litex-vexriscv/tree/05fc5e4) | Buildroot recipe for Linux 6.12 on VexRiscv (`litex_vexriscv`), and the older prebuilt Linux 5.14 ([`linux_2022_03_23.zip`](https://github.com/litex-hub/linux-on-litex-vexriscv/issues/164)) |
| [Buildroot 2026.05.3](https://gitlab.com/buildroot.org/buildroot/-/tree/2026.05.3) / [Linux 6.12](https://kernel.org) / [OpenSBI](https://github.com/riscv-software-src/opensbi) | Kernel, root file system and firmware in `linux/k612/`. Not changed; our config fragment and overlay are in `tools/linux/buildroot/`. |
| [PNRU usb_host](https://gitlab.com/pnru/usb_host) via [emard/usb_host @ 47408bb](https://github.com/emard/usb_host/tree/47408bb) | USB 1.1 host (PHY with LS/FS/PRE, SIE, registers). Ported to Migen as `gateware/usb_pnru.py`; the port is not published yet because the original has no license statement. `tools/usbhostd/` is our own Linux driver. |
| [oss-cad-suite](https://github.com/YosysHQ/oss-cad-suite-build/releases/tag/2026-09-23): [Yosys](https://github.com/YosysHQ/yosys), [nextpnr](https://github.com/YosysHQ/nextpnr), [Project Peppercorn](https://github.com/YosysHQ/prjpeppercorn) (`gmpack`), [openFPGALoader](https://github.com/trabucayre/openFPGALoader) | Open-source synthesis, place and route, bitstream packing and loading for GateMate |
| [smunaut/doom_riscv](https://github.com/smunaut/doom_riscv/tree/02b0d80) | DOOM engine for RISC-V. Not changed; our Linux framebuffer layer is in `tools/doom_linux/`. |
| [emard/ulx3s-misc](https://github.com/emard/ulx3s-misc/tree/d0c6f15/examples/usb) | Older low-speed USB HID host (Ultra-Embedded SIE + OpenCores USB PHY), used in `…USBHID_rec1.bit`. Copied into `gateware/verilog/usbhost/`; the VHDL PHY was converted to Verilog with GHDL. |
| [CologneChip gm_serdes_lb](https://github.com/pu-cc/gm_serdes_lb/tree/fbe1966) (via [openCologne @ 27eb53a](https://github.com/chili-chips-ba/openCologne/tree/27eb53ae74cbec76a8066ff108776bce127523bf/7.SerDes/1.serdestool_by_gm)) | `serdes_lb.v` and `serdestool.py` for `ulx5m-gs-m2-serdes` (CC_SERDES instance, regfile access over JTAG). ISC-style permission notice, © Cologne Chip AG, kept in the file headers. Small changes are listed in `ulx5m-gs-m2-serdes/README.md`. |

**We did not change LiteEth.** Gigabit Ethernet works because we use our own PHY (`gateware/gbe_phy.py`)
with the stock LiteEth MAC. The reason is explained in `ulx5m-gs-linux-sbc/README.md`. The same goes for the
other GateMate-specific parts: they live in this repository, not in patched LiteX code.

Our own code is BSD-2-Clause. Files taken from other projects keep their original license: the DOOM files
in `tools/doom_linux/` are GPL v2+, the USB host in `gateware/verilog/usbhost/` is GPL, and the Linux images in
`ulx5m-gs-linux-sbc/linux/k612/` are GPL-2.0 (kernel) and the licenses of the Buildroot packages.

---

## Contact

**Intergalaktik d.o.o.**  
[intergalaktik.eu](https://intergalaktik.eu)  
[warp@intergalaktik.eu](mailto:warp@intergalaktik.eu)
