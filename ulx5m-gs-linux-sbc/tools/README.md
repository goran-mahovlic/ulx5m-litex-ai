# tools/

Helper scripts for building the SoC, booting Linux and running things on the board.

Many of them run on our test setup: a Raspberry Pi at `192.168.10.14` holds the DirtyJTAG programmers, the TFTP
server (`/srv/tftp`) and a copy of these scripts in `~/FPGA/`. There are two DirtyJTAG probes with the same USB ID
(ULX5M-GS and a second board), so the scripts load bitstreams through the Pi's `fpga-jtag gs` wrapper (it picks the
probe by serial number) and use the probe's `/dev/serial/by-id/...` console, never `/dev/ttyACMn` (`dj_probe.sh`).
The board's CPU uses `192.168.10.213`. Scripts marked **Pi** expect that setup; scripts marked **local paths**
contain paths from our build machine. Change them before use.

## Build

| File | What it does |
|---|---|
| `soc_build.sh <name> [args]` | Builds the SoC (`gateware/target_soc.py --build`) into `build/s_<name>/`, log in `~/.tmp/t5032/soc_<name>.log`. **Local paths** (via `sbc_env.sh`). |
| `dj_probe.sh` | Sourced by the **Pi** scripts: console path and `dj_load <bit>` for the board `DJ_BOARD` (default `gs`) through `fpga-jtag`. |
| `sbc_env.sh` | `source` it to get our toolchain paths (oss-cad-suite, LiteX tree, RISC-V GCC) and then `../env.sh`. **Local paths.** On another machine, use `env.sh` with `OSS_CAD_SUITE` and `LXROOT` instead. |

## Linux and netboot (`linux/`)

| File | What it does |
|---|---|
| `linux/mkdts.py <build dir>` | Writes the Linux device tree for a build (from its `csr.json`): LiteX's `litex_json2dts_linux` plus our Ethernet node and, with DVI, the framebuffer node. |
| `linux/mkdts.py … --font 6x8 --append "…"` | Same, with a small fbcon font and extra kernel arguments (used for Linux 6.12). |
| `linux/rv32_usb5_pll60_s1_k612.dts` | Device tree for the recommended bitstream and Linux 6.12 (compiled: `../linux/k612/rv32_k612.dtb.gz`). |
| `linux/rv32_grec_3.dts`, `linux/rv32_ghrec_1.dts`, `linux/rv32_usb2_pll48_s1.dts` | Device trees of older builds (output of `mkdts.py`). |
| `linux/buildroot/build_buildroot.sh [dir]` | Builds Linux 6.12, OpenSBI and the root file system with Buildroot (1–2 h, ~15 GB). **Local paths** (default work dir). |
| `linux/buildroot/linux_sbc.fragment` | Our kernel config additions: fbcon on DVI, small fonts, uinput/evdev, `ip=`, `/dev/mem`, SPI-SD. |
| `linux/buildroot/rootfs/etc/init.d/` | Init scripts for the root file system: `S20console` (no blinking cursor), `S89fbperf` and `S92sbcdiag` (diagnostics, only with `sbcdiag=` on the kernel command line). |
| `linux/lxrun.sh <bit> <dtb> <rootfs> [secs] "<cmd>"…` | Netboots Linux with the given files (`IMAGE=Image612 SBI=opensbi612.bin` for 6.12), logs in and types commands. **Pi.** |
| `linux/cap.sh <out> <secs>` | Records the serial console without typing. **Pi.** |
| `linux/cpio_append.py <in.cpio> <out.cpio> <path>=<file>…` | Replaces files in a padded initramfs without unpacking it (keeps root ownership). |
| `linux/netboot_app.sh <app>` | Chooses what the BIOS loads over TFTP on the next boot (`linux`, `linuxdvi`, `linuxsd`, `speedtest`, `demo`) by writing `/srv/tftp/boot.json`. **Pi.** |
| `linux/linux_boot.sh <bit> [secs]` | Loads a bitstream, netboots Linux, waits for the login prompt, logs in and pings the board. **Pi.** |
| `linux/lx_cmd.sh "<cmd>" [wait]` | Types one command into the Linux serial console (slowly, so no characters are lost) and prints the output. **Pi.** |
| `linux/README.md` | Notes on the Linux images, the device tree and the boot steps. |

## DOOM and root file system

| File | What it does |
|---|---|
| `rootfs/mkrootfs.py <in.cpio> <out.cpio>` | Adds our files to the Linux `rootfs.cpio`: static IP `192.168.10.213` on eth0 and the `banner` programs. |
| `rootfs/interfaces`, `rootfs/banner`, `rootfs/banner_ascii` | The files that `mkrootfs.py` adds (the banners are static rv32 binaries). |
| `doom_linux/mkrootfs_dvi.py <in.cpio> <out.cpio>` | Same as `mkrootfs.py`, plus DOOM, `csrpeek` and `doom1.wad` (set `WAD=`; the WAD is not included). |
| `doom_linux/*.c`, `*.h`, `Makefile` | DOOM for Linux on the framebuffer (from smunaut/doom_riscv, GPL v2+), plus `csrpeek.c` (reads CSRs from Linux). |
| `doom_linux/doom`, `csrpeek`, `usbhidd`, `usbhostd`, `usbdiag` | Prebuilt rv32 binaries (static, raw Linux syscalls in `sys_linux.c`), so the rootfs scripts work without a RISC-V compiler. |

## USB host driver (`usbhostd/`)

| File | What it does |
|---|---|
| `usbhostd/usbhostd.c`, `usbh.c`, `usbh.h`, `hidinput.h` | Linux user-space driver for the PNRU USB host: enumeration, hub, boot keyboard and mouse, passed to Linux through `/dev/uinput` (with autorepeat). Build: `make -C doom_linux usbhostd`. |
| `usbhostd/S90usbhostd` | Init script: starts `usbhostd` (options from `usbhostd=` on the kernel command line) and a login on tty1. |
| `usbhostd/test_usbh.c` | Host-side test of the driver against a simulated device, with descriptors read on the board. |
| `usbhostd/usbdiag.c`, `S91usbdiag` | Board test without typing: raw GET_DESCRIPTOR and a timed `usbhostd` run. |
| `usbhostd/reptest.c` | Checks the autorepeat of the input device on the board. |

## Older USB keyboard (`usbhidd/`)

| File | What it does |
|---|---|
| `usbhidd/usbhidd.c`, `hidkey.h` | Linux daemon: reads key reports from the `usb_hid` CSRs and types them into the console. Needs the `ghrec_1` bitstream. |
| `usbhidd/S90usbhidd` | Init script: starts the daemon at boot and a login shell on the DVI console. |
| `usbhidd/test_hidkey.c` | Host-side unit test of the key-code table. |

## Diagnostics

| File | What it does |
|---|---|
| `sd/bios_cmds.sh <bit> "<cmd>"...` | Loads a bitstream, stops netboot and types BIOS commands (e.g. `mem_test`, `sdcard_init`). **Pi.** |
| `dvi/testimg_cmds.sh` | Prints BIOS commands that paint 8 colour bands into the framebuffer (use with `sd/bios_cmds.sh`). |
| `speedtest/` | Bare-metal Ethernet speed test: `main.c` is a TFTP-booted app, `eth_speedtest.py` measures from a host, `eth_speedtest.sh` runs both (`BIT=<bitstream>`). See `speedtest/README_speedtest.md`. **Pi.** |
