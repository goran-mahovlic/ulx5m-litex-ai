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
- LiteX at commit `b6ae9e0b2`, together with migen, litedram, liteeth, litesdcard and
  `pythondata-cpu-vexriscv_smp`.

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

### About the LiteX patch (`docs/litex-b6ae9e0b2-local.patch`)

**You do not need this patch to build.** It records two small changes in our local LiteX copy:

1. **`litex/build/colognechip/common.py`** (tristate buffer). This change only rewrites one line and adds a
   comment. The logic is the same as in upstream LiteX (we checked: both give the same expression). It is left
   over from our search for a tristate problem. That problem turned out to be a nextpnr bug, which shows up
   when the tristate control is a constant. This patch will be removed.
2. **`litex/soc/software/bios/main.c`**. This change adds one line to the BIOS start-up screen, showing the
   board's IP and MAC address. Without it, the line is simply not printed.

The scripts in `tools/` still contain our local paths and IP addresses. Change them before you use them.

## More information

`ulx5m-gs-linux-sbc/docs/` has the measurements and lessons we learned. Start with these two files:
- `SBC_DVI_USB_TASK-5047.md`: the clock/PLL problem and the USB keyboard,
- `LESSONS_GATEMATE.md`: general GateMate lessons.

Some documents in that folder are in Croatian.
