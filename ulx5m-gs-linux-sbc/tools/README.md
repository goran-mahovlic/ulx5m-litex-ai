# tools/

Helper scripts for building the SoC, booting Linux and running things on the board.

Many of them run on our test setup: a Raspberry Pi at `192.168.10.14` holds the DirtyJTAG programmer
(`/dev/ttyACM0` = board serial), the TFTP server (`/srv/tftp`) and a copy of these scripts in `~/FPGA/`.
The board's CPU uses `192.168.10.213`. Scripts marked **Pi** expect that setup; scripts marked **local paths**
contain paths from our build machine. Change them before use.

## Build

| File | What it does |
|---|---|
| `soc_build.sh <name> [args]` | Builds the SoC (`gateware/target_soc.py --build`) into `build/s_<name>/`, log in `~/.tmp/t5032/soc_<name>.log`. **Local paths** (via `sbc_env.sh`). |
| `sbc_env.sh` | `source` it to get our toolchain paths (oss-cad-suite, LiteX tree, RISC-V GCC) and then `../env.sh`. **Local paths.** On another machine, use `env.sh` with `OSS_CAD_SUITE` and `LXROOT` instead. |

## Linux and netboot (`linux/`)

| File | What it does |
|---|---|
| `linux/mkdts.py <build dir>` | Writes the Linux device tree for a build (from its `csr.json`): LiteX's `litex_json2dts_linux` plus our Ethernet node and, with DVI, the framebuffer node. |
| `linux/rv32_grec_3.dts`, `linux/rv32_ghrec_1.dts` | Device trees for the two bitstreams in `bitstreams/` (output of `mkdts.py`). |
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
| `doom_linux/doom`, `csrpeek`, `usbhidd` | Prebuilt rv32 binaries of the above and of `usbhidd`, so `mkrootfs_dvi.py` works without a RISC-V compiler. |

## USB keyboard (`usbhidd/`)

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
