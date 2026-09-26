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

This project turns the FPGA into a small computer:
- a RISC-V CPU (VexRiscv),
- 64 MB of RAM,
- gigabit Ethernet,
- a 640×480 picture on a DVI monitor.

Linux 5.14 boots over the network, and you can play DOOM on the screen.

### What works

- Gigabit Ethernet: link, ping, network boot.
- Linux boots to a login prompt, on the serial console and on the DVI screen.
- DOOM (shareware) runs on the DVI screen.
- The picture is stable. There were no dropouts in 80 frames captured during boot, or in 19 minutes of running.

### What does not work yet

- **USB keyboard.** The bitstream is built, but it has never been tried on the board. The keyboard needs
  5 V on the J5 VBUS pin, and the board does not supply it.
- **SD card.** Linux sees the SD controller, but the card does not answer. The likely cause is voltage:
  the FPGA pins run at 1.8 V and the card at 3.3 V.
- **Slow boot.** Linux takes 4 to 10 minutes to reach the login prompt.
- **PLL noise.** Under heavy memory traffic the FPGA clock (PLL) briefly reports "not locked". We changed
  the design so the clocks keep running anyway, which keeps the picture stable. The cause is noise on the
  PLL supply (VDD_PLL), so the real fix is in hardware.

### Which bitstream to use

The bitstreams are in `ulx5m-gs-linux-sbc/bitstreams/`:

| File | Use |
|---|---|
| `ETH_GateMateA1_2509_2330_Linux_GbE_DVI_lr0_rec3.bit` | **Use this one.** Linux + Ethernet + DVI + DOOM. |
| `ETH_GateMateA1_2509_2330_Linux_GbE_DVI_USBHID_rec1.bit` | Same, plus the USB keyboard. Not tested yet. |

Older bitstreams are not in this repository.

---

## ulx5m-gs-m2-serdes — SerDes link between two GateMate boards

ULX5M-GS and ULX5M-M2 connected by their SerDes lane, with one JTAG probe per board.
- An 8b10b link works in both directions, bit-exact, at 0.3 Gb/s (360/360 reads).
- A fabric BER checker measured 1.1·10⁹ words per direction with 0 errors (BER < 6.7·10⁻¹¹).
- A script proves step by step that the data goes over the external cable (idle tests, error injection, pulling the cable).
- Higher rates (up to 2.5 Gb/s) are built but not yet measured.

Details: `ulx5m-gs-m2-serdes/README.md`.

---

## How to try it on another computer

**You need:**
- the board, connected to a gigabit switch,
- a DVI monitor,
- a Linux PC with `openFPGALoader`, `dtc` (device-tree compiler), a TFTP server and Python 3.

**1. Set the PC's IP address.** The addresses are built into the bitstream:
- the board is `192.168.10.213`,
- it downloads Linux from `192.168.10.14`.

Give your PC the address `192.168.10.14`, or build the bitstream again with other addresses.

**2. Download Linux.** Get `linux_2022_03_23.zip` from
https://github.com/litex-hub/linux-on-litex-vexriscv/issues/164.
Copy `Image`, `rootfs.cpio` and `opensbi.bin` from it into the TFTP folder.

**3. Make the device tree.** The device tree tells Linux what hardware the board has:

    dtc -O dtb -o rv32dvi.dtb ulx5m-gs-linux-sbc/tools/linux/rv32_grec_3.dts

Copy `rv32dvi.dtb` into the TFTP folder as well.

**4. Tell the board what to load.** In the TFTP folder, create `boot.json`:

    { "Image": "0x40000000", "rv32dvi.dtb": "0x40ef0000", "rootfs.cpio": "0x41000000", "opensbi.bin": "0x40f00000" }

**5. Add DOOM (optional).** DOOM needs `doom1.wad`. The shareware version is free, but it is not included here.
Build a new root file system that contains DOOM:

    WAD=/path/to/doom1.wad python3 ulx5m-gs-linux-sbc/tools/doom_linux/mkrootfs_dvi.py rootfs.cpio rootfs_doom.cpio

Copy the result into the TFTP folder under the name `rootfs.cpio`.

**6. Load the FPGA and wait.**

    openFPGALoader -c dirtyJtag ulx5m-gs-linux-sbc/bitstreams/ETH_GateMateA1_2509_2330_Linux_GbE_DVI_lr0_rec3.bit -r

The serial console is on the same USB cable (`/dev/ttyACM0`, 115200 baud). After 4 to 10 minutes you get
a login prompt, on the serial console and on the DVI screen. Log in as `root` and type `doom`.

---

## Building the bitstream yourself

**You need:**
- oss-cad-suite, 2026-09 or newer,
- a RISC-V GCC (`riscv-none-elf`),
- LiteX, migen, litedram, liteeth, litex-boards, litesdcard and `pythondata-cpu-vexriscv_smp`,
  at the versions linked under [Built on](#built-on).

Set `OSS_CAD_SUITE` and `LXROOT` to point to them. Then run:

    cd ulx5m-gs-linux-sbc
    source env.sh
    python3 gateware/target_soc.py --build --output-dir build/s_grec_3 --seed 3 \
      --cpu-type vexriscv_smp --cpu-variant linux --sdram-clk inv \
      --with-gbe --eth-mode mac --boot netboot \
      --with-video --video-ce-rep --video-neg-sync --video-recover --pll-lock-req 0
    python3 tools/linux/mkdts.py build/s_grec_3 > rv32dvi.dts

Different seeds give different timing, and not every seed produces a working Ethernet receiver. Seed 3 is
tested on the board. If you change the design, test the new bitstream on the board.

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

`ulx5m-gs-linux-sbc/docs/` has the measurements and lessons we learned. Start with these two files:
- `SBC_DVI_USB_TASK-5047.md`: the clock/PLL problem and the USB keyboard,
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
| [linux-on-litex-vexriscv](https://github.com/litex-hub/linux-on-litex-vexriscv/issues/164) | Prebuilt Linux 5.14, Buildroot root file system and OpenSBI (`linux_2022_03_23.zip`) |
| [oss-cad-suite](https://github.com/YosysHQ/oss-cad-suite-build/releases/tag/2026-09-23): [Yosys](https://github.com/YosysHQ/yosys), [nextpnr](https://github.com/YosysHQ/nextpnr), [Project Peppercorn](https://github.com/YosysHQ/prjpeppercorn) (`gmpack`), [openFPGALoader](https://github.com/trabucayre/openFPGALoader) | Open-source synthesis, place and route, bitstream packing and loading for GateMate |
| [smunaut/doom_riscv](https://github.com/smunaut/doom_riscv/tree/02b0d80) | DOOM engine for RISC-V. Not changed; our Linux framebuffer layer is in `tools/doom_linux/`. |
| [emard/ulx3s-misc](https://github.com/emard/ulx3s-misc/tree/d0c6f15/examples/usb) | USB 1.1 HID host (Ultra-Embedded SIE + OpenCores USB PHY). Copied into `gateware/verilog/usbhost/`; the VHDL PHY was converted to Verilog with GHDL. |
| [CologneChip gm_serdes_lb](https://github.com/pu-cc/gm_serdes_lb/tree/fbe1966) (via [openCologne @ 27eb53a](https://github.com/chili-chips-ba/openCologne/tree/27eb53ae74cbec76a8066ff108776bce127523bf/7.SerDes/1.serdestool_by_gm)) | `serdes_lb.v` and `serdestool.py` for `ulx5m-gs-m2-serdes` (CC_SERDES instance, regfile access over JTAG). ISC-style permission notice, © Cologne Chip AG, kept in the file headers. Small changes are listed in `ulx5m-gs-m2-serdes/README.md`. |

**We did not change LiteEth.** Gigabit Ethernet works because we use our own PHY (`gateware/gbe_phy.py`)
with the stock LiteEth MAC. The reason is explained in `ulx5m-gs-linux-sbc/README.md`. The same goes for the
other GateMate-specific parts: they live in this repository, not in patched LiteX code.

Our own code is BSD-2-Clause. Files taken from other projects keep their original license: the DOOM files
in `tools/doom_linux/` are GPL v2+, and the USB host in `gateware/verilog/usbhost/` is GPL.

---

## Contact

**Intergalaktik d.o.o.**  
[intergalaktik.eu](https://intergalaktik.eu)  
[warp@intergalaktik.eu](mailto:warp@intergalaktik.eu)
