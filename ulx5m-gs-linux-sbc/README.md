# ulx5m-gs-linux-sbc — LiteX Linux computer on the ULX5M-GS

This folder turns the [ULX5M-GS](https://github.com/intergalaktik/ulx5m-gs) board (GateMate CCGM1A1,
KSZ9031 PHY, 64 MB SDRAM) into a small Linux computer:
- a VexRiscv-SMP RISC-V CPU at 20 MHz,
- 64 MB of SDRAM,
- **1000 Mb/s Ethernet**,
- a 640×480 DVI picture,
- a USB 1.1 host for a keyboard and a mouse.

Linux 6.12 boots over TFTP in 266 s, with the console on the DVI screen and the USB keyboard. The images are in
`linux/k612/`. (The older Linux 5.14 setup also runs DOOM.)

**Quick start** (which bitstream to use, how to boot Linux, how to rebuild) is in the
[main README](../README.md). This file describes what is inside the folder.

## One design

`gateware/target_soc.py` is the whole design: CPU, SDRAM, BIOS, 1000 Mb/s Ethernet, DVI, an optional USB
host and SD card. The bitstreams in `bitstreams/` are built from it.

The project started with two designs without a CPU (100 Mb/s and 1000 Mb/s ping in hardware) and many
diagnostic modules. They were removed on 26 September 2026 and are kept in the git tag `pre-cleanup-20260926`.
The review is in `docs/REVIEW_LITEX_DUPLICATES.md`.

## Why these files are local

Most of the design comes from LiteX: the board platform (`litex_boards.platforms.intergalaktik_ulx5m_gs`), the
VexRiscv CPU, the BIOS, the LiteDRAM SDRAM controller, the LiteEth MAC, the video timing generator and the TMDS
encoder. The build uses unmodified upstream LiteX. These files are local because LiteX does not have them, or
has them in a form that does not fit this board:

| File | Why it is not taken from LiteX |
|---|---|
| `gateware/target_soc.py` | The litex-boards target for this board has no Ethernet, DVI or USB. Its clock generator uses a separate PLL output for the SDRAM clock, and 1G Ethernet already takes all 4 global clock nets. The SDRAM chip (IS42VM16320E, 1.8 V, 64 MB) is not in LiteDRAM, so its timings are defined here. |
| `gateware/gbe_phy.py` | LiteEth has no GateMate RGMII PHY. Its other PHYs keep clock-crossing FIFOs at 125 MHz, and on GateMate those paths only reach 52–65 MHz. |
| `gateware/pll_stdy.py` | A small subclass of LiteX `GateMatePLL` that connects the PLL's sticky lock flag. LiteX leaves it unconnected. |
| `gateware/sticky_lock.py` | LiteX resets the clock domains from the raw PLL lock flag. On this board that flag flickers, so it is filtered here. |
| `gateware/video_sbc.py` | LiteX's HDMI PHY needs its own pixel clock net, and there is none left. Here video runs in the 125 MHz Ethernet clock with a 1-in-5 clock enable. LiteX's framebuffer at 640×480 would use 92 % of the SDRAM bandwidth, so a 320×240 frame is scaled up in hardware. |
| `gateware/mdio_core.py` | Sets up the Ethernet PHY for 1000 Mb/s in hardware, before the CPU runs. LiteEth only offers MDIO access from software. (Migen; it replaced an older Verilog file and behaves cycle for cycle the same, see `sim/tb_mdio_core_equiv.py`.) |
| `gateware/usb_pnru.py` (not published yet) | LiteX's USB host (OHCI) needs a 48 MHz global clock net, and there is none left. This is a Migen port of the PNRU USB 1.1 host (full speed, low speed, low speed behind a hub). It runs at 60 MHz from a PLL output on fabric routing. The driver is in Linux user space (`tools/usbhostd/`). The port stays out of this repository until the PNRU author agrees, because the original has no license statement (`docs/USB_HUB_PNRU.md` §2). |
| `gateware/usb_hid.py`, `gateware/verilog/usbhost/` | Older: Emard's small low-speed keyboard host (`…USBHID_rec1.bit`). Replaced by the PNRU host. |

## Gigabit Ethernet: how it works here

**The link runs at 1000 Mb/s.** The PHY is told to advertise only 1000BASE-T full duplex, and the PHY status
register reads 1000 Mb/s full duplex. So the board needs a gigabit switch. It cannot link directly to a
device that only supports 100 Mb/s.

**Why our own PHY (`gateware/gbe_phy.py`) and not LiteEth's RGMII PHY.** At 1 Gb/s the RGMII clocks run at
125 MHz. LiteEth places its clock-crossing FIFOs in those 125 MHz domains, and on GateMate they only reach
52–65 MHz after routing. Our PHY keeps only the I/O registers and a small shift register at 125 MHz. Each
frame crosses into the 20 MHz system clock through a 4 KiB block RAM in each direction.

**Speed.** The link is 1 Gb/s, but the data rate is limited by the 20 MHz system clock and the CPU:
- The MAC is 8 bits wide at 20 MHz, so at most about 160 Mb/s can pass through it.
- A short burst is received at full line rate, but only as much as fits into the 4 KiB buffer.
- Measured without Linux, on a smaller CPU: 6.3 Mb/s sent from the board. Our test partner (a Raspberry Pi)
  has only a 100 Mb/s port, so the receive direction topped out at 96 Mb/s. Throughput under Linux has not
  been measured yet. Under Linux 6.12 a 30 min ping gave 1800/1800 replies (RTT 6–36 ms).
- nextpnr reaches 19–27 MHz for the system clock, depending on the seed. That is why it stays at 20 MHz.

**The receive clock pin.** The PHY's receive clock arrives on `IO_EB_A7`, which is not a dedicated clock pin.
On GateMate any pin can drive the global clock network through `CC_BUFG`, and this works at 125 MHz.
(An older version of this README said gigabit was impossible because of this pin. That was wrong.)

## Other things worth knowing

- **DVI.** `gateware/video_sbc.py` reads a 320×240 framebuffer and doubles every pixel and line in hardware.
  A full 640×480 framebuffer would use 92 % of the SDRAM bandwidth.
- **PLL lock.** `--pll-lock-req 0` keeps the PLL outputs running when the lock detector flickers.
  `--video-recover` restarts the video path if the picture is lost. Details: `docs/SBC_DVI_USB_TASK-5047.md`.
- **USB host.** `tools/usbhostd/` enumerates the device (and a hub), reads the boot keyboard and mouse reports and
  passes them to Linux through `/dev/uinput`, so they are real input devices with autorepeat. On the board: a
  Logitech wireless receiver, 200 546 transactions in 33 min with 0 errors, login typed on tty1. Low speed and the
  hub path pass in simulation, but are not tested on the board yet. Details: `docs/USB_HUB_PNRU.md`.
- **Linux 6.12.** Built with Buildroot (`tools/linux/buildroot/`), with fbcon on the DVI screen, small fonts,
  uinput and `ip=` on the command line. Ready-made images and checksums: `linux/k612/`.
- **Configuration reset.** Every bitstream starts with `CMD_CFGRST` (`gmpack --reset`). See the main README.

## Folder layout

| Folder | Contents |
|---|---|
| `gateware/` | The FPGA design (Python/migen + some Verilog) |
| `bitstreams/` | Ready-made bitstreams; `bitstreams/README.md` lists what each one does |
| `linux/k612/` | Linux 6.12 images (kernel, OpenSBI, root file system, device tree) for the recommended bitstream |
| `tools/` | Build scripts, Linux/netboot helpers, Buildroot recipe, DOOM and rootfs, USB driver; see `tools/README.md` |
| `sim/` | Simulations of the local modules (PHY, scaler, watchdog, lock filter) and a BIOS boot-option test |
| `docs/` | Measurements, investigations and lessons (`docs/LESSONS_GATEMATE.md`) |
| `build/` | Build output; only `csr.json`/`csr.csv` of the builds behind `bitstreams/` are kept |
| `env.sh` | Sets up the toolchain and LiteX paths (`OSS_CAD_SUITE`, `LXROOT`) |

Loading uses the DirtyJTAG programmer: `openFPGALoader -c dirtyJtag <file.bit> -r`.

## License

BSD-2-Clause. See `LICENSE`. The project started from the CPU-less 100 Mb/s LiteX-Ethernet-ULX5M-GS design
by its contributors (in the tag `pre-cleanup-20260926`). The older USB host is by Emard, GPL
(`gateware/verilog/usbhost/README.md`). The DOOM files in `tools/doom_linux/` are GPL v2+. The Linux images in
`linux/k612/` are GPL-2.0 (kernel) plus the licenses of the Buildroot packages (`linux/k612/README.md`).
