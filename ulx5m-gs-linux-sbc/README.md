# ulx5m-gs-linux-sbc — LiteX Linux computer on the ULX5M-GS

This folder turns the [ULX5M-GS](https://github.com/intergalaktik/ulx5m-gs) board (GateMate CCGM1A1,
KSZ9031 PHY, 64 MB SDRAM) into a small Linux computer:
- a VexRiscv-SMP RISC-V CPU at 20 MHz,
- 64 MB of SDRAM,
- **1000 Mb/s Ethernet**,
- a 640×480 DVI picture.

Linux 5.14 boots over TFTP, and DOOM runs on the screen.

**Quick start** (which bitstream to use, how to boot Linux, how to rebuild) is in the
[main README](../README.md). This file describes what is inside the folder.

## Three designs in one folder

The project grew in three steps. All three top-level files still build:

| Top file | What it is | Ethernet |
|---|---|---|
| `gateware/target_eth.py` | No CPU. LiteEth answers ping and UDP echo in hardware. | 100 Mb/s |
| `gateware/target_gbe.py` | No CPU. Same idea, using our own gigabit PHY. | 1000 Mb/s |
| `gateware/target_soc.py` | **The Linux computer.** CPU, SDRAM, BIOS, Ethernet, DVI, optional USB keyboard and SD card. | 1000 Mb/s |

The bitstreams in `bitstreams/` are built from `target_soc.py`.

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
  been measured yet.
- nextpnr reaches 19–27 MHz for the system clock, depending on the seed. That is why it stays at 20 MHz.

**The receive clock pin.** The PHY's receive clock arrives on `IO_EB_A7`, which is not a dedicated clock pin.
On GateMate any pin can drive the global clock network through `CC_BUFG`, and this works at 125 MHz.
(An older version of this README said gigabit was impossible because of this pin. That was wrong.)

## Other things worth knowing

- **DVI.** `gateware/video_sbc.py` reads a 320×240 framebuffer and doubles every pixel and line in hardware.
  A full 640×480 framebuffer would use 92 % of the SDRAM bandwidth.
- **PLL lock.** `--pll-lock-req 0` keeps the PLL outputs running when the lock detector flickers.
  `--video-recover` restarts the video path if the picture is lost. Details: `docs/SBC_DVI_USB_TASK-5047.md`.
- **USB keyboard.** `gateware/usb_hid.py` wraps Emard's low-speed USB HID host (`gateware/verilog/usbhost/`).
  `tools/usbhidd/` passes the key presses to the Linux console. Not tested on the board yet.
- **Configuration reset.** Every bitstream starts with `CMD_CFGRST` (`gmpack --reset`). See the main README.

## Folder layout

| Folder | Contents |
|---|---|
| `gateware/` | The FPGA design (Python/migen + some Verilog) |
| `bitstreams/` | Ready-made bitstreams; `bitstreams/README.md` lists what each one does |
| `tools/` | Build scripts, Linux/netboot helpers, DOOM and rootfs, USB daemon, board diagnostics |
| `sim/` | Simulations and test benches |
| `test_script/` | Host-side tests (UDP echo, UART) |
| `docs/` | Measurements, investigations and lessons (`docs/LESSONS_GATEMATE.md`) |
| `build/` | Build output; only `csr.json`/`csr.csv` of the two recommended builds are kept |
| `env.sh` | Sets up the toolchain and LiteX paths (`OSS_CAD_SUITE`, `LXROOT`) |

Loading uses the DirtyJTAG programmer: `openFPGALoader -c dirtyJtag <file.bit> -r`.

## License

BSD-2-Clause. See `LICENSE`. The first, CPU-less 100 Mb/s design comes from the LiteX-Ethernet-ULX5M-GS
contributors. The USB host is by Emard (`gateware/verilog/usbhost/README.md`).
