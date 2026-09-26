# Base folder of AI projects for ULX5M-GS

LiteX projects for the Radiona **ULX5M-GS** (CologneChip GateMate CCGM1A1, KSZ9031 GbE PHY),
built with the open toolchain (Yosys → nextpnr-himbaechel → gmpack).

## `ulx5m-gs-linux-sbc/` — Linux SBC: 1G Ethernet + DVI + DOOM (+ USB keyboard, untested)

VexRiscv-SMP (1 core) + 32 MiB SDRAM + 1 Gb/s Ethernet (CPU MAC) + DVI 640×480 framebuffer.
BIOS boots Linux 5.14 (Buildroot) over TFTP.

| Works (measured on the board) | Does not work / not tested |
|---|---|
| 1G link and ping; BIOS TFTP netboot | **USB keyboard** (`…USBHID_rec1.bit`): built, never loaded; needs 5 V on J5 VBUS |
| Linux login on UART and on DVI (fbcon) | **SD card**: the SPI-SD host registers, but the card does not answer (probably 1.8 V bank vs 3.3 V card) |
| DOOM (shareware) on DVI, `-timedemo` 30/30 clean frames | Linux boot is slow and varies: 4–10 min to login |
| Picture stable: 80/80 frames during boot, 0 resync in 19 min (`LOCK_REQ=0` + video watchdog) | PLL lock detector still flickers under SDRAM load (analog noise on VDD_PLL); `LOCK_REQ=0` hides it |

Bitstreams (`bitstreams/`, load to SRAM only):
- `ETH_GateMateA1_2509_2330_Linux_GbE_DVI_lr0_rec3.bit` — **recommended**, DTS `tools/linux/rv32_grec_3.dts`
- `ETH_GateMateA1_2509_2330_Linux_GbE_DVI_USBHID_rec1.bit` — same + USB HID, DTS `tools/linux/rv32_ghrec_1.dts`

## Test on another computer

You need: the ULX5M-GS on a 1G switch, DVI monitor, `openFPGALoader`, `dtc`, a TFTP server, and Python 3.

1. **Network.** The IPs are compiled into the bitstream: board = `192.168.10.213`, TFTP server = `192.168.10.14`.
   Give your PC `192.168.10.14/24`, or rebuild with `--local-ip` / `--remote-ip`.
2. **Linux images.** Get `Image`, `rootfs.cpio` and `opensbi.bin` from `linux_2022_03_23.zip`
   (https://github.com/litex-hub/linux-on-litex-vexriscv/issues/164). Put them in the TFTP root.
3. **DTB.** `dtc -O dtb -o rv32dvi.dtb ulx5m-gs-linux-sbc/tools/linux/rv32_grec_3.dts`. Then `boot.json`:
   ```json
   { "Image": "0x40000000", "rv32dvi.dtb": "0x40ef0000", "rootfs.cpio": "0x41000000", "opensbi.bin": "0x40f00000" }
   ```
4. **DOOM (optional).** `python3 tools/doom_linux/mkrootfs_dvi.py rootfs.cpio rootfs_doom.cpio` with
   `WAD=/path/doom1.wad` (shareware, not included). Use it instead of `rootfs.cpio`.
5. **Load:** `openFPGALoader -c dirtyJtag bitstreams/…_lr0_rec3.bit -r`. The UART console is on the same USB
   (115200). Log in as `root`. Then run `doom` (reads `/usr/share/doom/doom1.wad`; `-timedemo demo1` for a benchmark).

**Rebuild** (optional): oss-cad-suite ≥ 2026-09, LiteX `b6ae9e0b2` + `docs/litex-b6ae9e0b2-local.patch`
(CC_IOBUF tristate fix), litedram, liteeth, litesdcard, `pythondata-cpu-vexriscv_smp`, and a riscv-none-elf GCC.
Set `OSS_CAD_SUITE` / `LXROOT`, then run `source env.sh`. Then:

    python3 gateware/target_soc.py --build --output-dir build/s_grec_3 --cpu-type vexriscv_smp --cpu-variant linux \
      --with-gbe --eth-mode mac --boot netboot --with-video --sdram-clk inv \
      --video-ce-rep --video-neg-sync --pll-lock-req 0 --video-recover --seed 3
    python3 tools/linux/mkdts.py build/s_grec_3 > rv32dvi.dts

The helper scripts in `tools/` still contain our local paths and IPs; adjust them before use.
Details, measurements and lessons: `ulx5m-gs-linux-sbc/docs/` (`SBC_DVI_USB_TASK-5047.md`, `LESSONS_GATEMATE.md`).
