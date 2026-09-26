# Review: LiteX duplicates and unneeded files (2026-09-26)

Question: LiteX projects usually have few files, because most of the code is already in LiteX. What in `ulx5m-gs-linux-sbc/`
is duplicated or surplus?

The comparison was made against the LiteX tree `~/app/litex-1g-deps` (LiteX `b6ae9e0b2`, LiteEth `9654767`, LiteDRAM
`51de2b0`, LiteX-Boards `8741034`, LiteSDCard `17718d9`, Migen `e19524c`). Criterion "is used" = the recommended build
`grec_3` (command in the root README.md) and the build `ghrec_1` (same + `--with-usb-hid`), because these are the only two
bitstreams in `bitstreams/`.

The state before the cleanup is kept in the tag **`pre-cleanup-20260926`** (it also has the CPU-less designs `target_eth.py`
/ `target_gbe.py` and all diagnostics). Old logs in `docs/` still mention these files. That is history and
is not changed; the files can be found in the tag.

## Summary

| | before | after |
|---|---|---|
| files in `ulx5m-gs-linux-sbc/` (git) | 261 | 113 |
| `gateware/` | 29 (Python 4,248 lines + 2 Verilog modules) | 14 (Python 1,368 lines, Verilog only Emard's USB) |
| `sim/` | 27 | 6 |
| `tools/` | 153 | 47 |
| `test_script/` | 3 | 0 |
| local LiteX changes | 2 (patch) | **0** (clean upstream `b6ae9e0b2`) |

(113 = 109 after deletion + this document + `tools/README.md` + `sim/tb_mdio_core_equiv.py` + `tools/dj_probe.sh`; `mdio_core.v` replaced by `mdio_core.py`.)

## How we checked that the design did not change

1. Elaboration without P&R (`target_soc.py` without `--build`, i.e. LiteX generates Verilog and compiles the BIOS) with the command from
   the root README, with `SOURCE_DATE_EPOCH` and `--no-ident-version`, so the date does not end up in the output. Two consecutive
   runs give byte-identical output, so the comparison is meaningful.
2. Comparison of all files in `build/<x>/gateware/` without comments (`/* … */` contains the hierarchy tree, whose
   order changes from run to run) and without the absolute build path.
3. Result, step A (deletion and code cleanup, LiteX patch still active):

   | build | `.v` (13,524 / 13,755 lines) | `.ccf` | `.sdc` | `rom.init` | `mem.init` | VexRiscv `.v` | `csr.json` |
   |---|---|---|---|---|---|---|---|
   | grec_3 | same | same | same | same | same | same | same |
   | ghrec_1 (`--with-usb-hid`) | same | same | same | same | same | same | — |

   The only difference is in `.ys`: `read_verilog …/tools/uhello/mdio_core.v` → `…/gateware/verilog/mdio_core.v`
   (the file was moved with `git mv`, the content is the same).
4. Step B (without the LiteX patch, without `CONFIG_BIOS_PRINT_IDENT`): the logic is the same, and the BIOS is 96 B smaller (36,500 → 36,404 B),
   so the ROM has 9,101 instead of 9,125 words. The only difference in `.v` is `reg [31:0] rom[0:9124]` → `rom[0:9100]`.
   The BIOS lacks one output line ("Ident: …"). The bitstreams in `bitstreams/` were built before this and
   still print that line.
5. Simulations that remain: `tb_gbe_phy` ALL TESTS PASSED, `tb_scaler2x` PASS, `tb_sticky_lock` ALL PASS,
   `tb_watchdog` PASS. `sim/test_boot_option.py` 5/5 PASS (none, serial, sdcard, netboot, sdnet).
6. A full P&R was not run: the generated Verilog, `.ccf` and `.sdc` are the same, so with the same seed and tools it would give the same
   bitstream. Nothing was flashed.

## Table: `gateware/`

"In LiteX?" means whether the LiteX tree has something that does the same job.

| File | In LiteX? | Decision | Reason |
|---|---|---|---|
| `target_soc.py` | partly: `litex_boards/targets/intergalaktik_ulx5m_gs.py` | **kept, cleaned** (521 → 420 lines) | The upstream target has only CPU, SDRAM and LED. It has no Ethernet, DVI or USB, and its CRG uses a global net for `sys_ps` (`targets/intergalaktik_ulx5m_gs.py:48-50`), which is not available with 1G Ethernet (4 nets: sys, gtx, TXC, grx). Upstream uses `IS42S16160` (32 MB, `:79`), but the board has IS42VM16320E (64 MB). The platform is not copied: the upstream `intergalaktik_ulx5m_gs.Platform` is used, and the ETH, DVI and USB pins are added with `add_extension`, because the upstream platform does not have them (`platforms/intergalaktik_ulx5m_gs.py:14-86`). Removed options: hwstack (hardware ARP/ICMP/Etherbone), two-clock DVI, `--video-terminal`, `--video-det-load`, `--video-pix-freq`, `--with-usb` (OHCI), `--sdram-drive`, `--sdram-slew`, `--sdram-clk ps90`, `--ip`. `--sdram-clk inv` and `--eth-mode mac` stay as the only value, so the command from the README still works. |
| `target_soc.py: IS42VM16320` | no (`litedram/modules.py:448,457` only have `IS42S16160`, `IS42S16320`) | kept | `IS42S16320` has the same geometry, but it is a 3.3 V part with different timings (tRP/tRCD 20 ns, tREFI 64 ms/8192). IS42VM16320E-75 is a 1.8 V mobile SDR: tRP/tRCD 22.5 ns, tRAS 45 ns, and tREFI is reduced to 7.6 µs because LiteDRAM rounds up (TASK-5047). Replacing it would change the controller. |
| `target_soc.py: add_cpu_mac_regions()` | yes, part of `SoC.add_ethernet()` (`litex/soc/integration/soc.py:2618`) | kept | `add_ethernet(data_width=8)` builds a MAC with `dw=32` in the `eth_tx`/`eth_rx` domains (`soc.py:2656-2672`). It enables `with_sys_datapath` only for `data_width=32`, and that was tried: RX never hands a frame to the CPU (TASK-5033). Our PHY has no `eth_tx`/`eth_rx` domains, it runs in sys. The combination `dw=8` + `with_sys_datapath=True` does not exist through `add_ethernet`, so the regions, IRQ and constants are added by hand, with the same calls as in LiteX. |
| `target_soc.py: _eth` (pins) | no (the platform has no `eth`) | kept (moved from `target_gbe.eth_io()`) | Without it, `target_soc.py` would depend on the CPU-less design. |
| `gbe_phy.py` | no (`liteeth/phy/` only has PHYs for ECP5, 7-series, US, Gowin, Efinix, Agilex; none for GateMate) | kept | The LiteEth RGMII PHYs keep asynchronous CDC FIFOs in 125 MHz domains. On GateMate these paths only reach 52–65 MHz after routing (`docs/GBE_FEASIBILITY_20260921_TASK-4961.md`). `gbe_phy.py` keeps only the IO registers and a shift register at 125 MHz, and the frame crosses into sys through BRAM. |
| `pll_stdy.py` | partly: `GateMatePLL` (`litex/soc/cores/clock/colognechip.py`) | kept (32 lines, subclass) | Upstream `GateMatePLL` ties `USR_LOCKED_STDY_RST = 0` and `USR_PLL_LOCKED_STDY = Open()` (`colognechip.py:154,156`). We need a sticky flag for the CSR `pll_stdy` (PLL noise diagnostics, TASK-5047). `lock_req` is already upstream (`colognechip.py:37,148`) and is used. |
| `sticky_lock.py` | no | kept | The upstream PLL resets the domains from the raw `USR_PLL_LOCKED` (`colognechip.py:104,157,162`). On this board the flag glitches (24/29 JTAG samples), so every glitch would reset sys. |
| `video_sbc.py` | partly: `VideoHDMIPHY`, `VideoFrameBuffer`, `VideoTimingGenerator` (`litex/soc/cores/video.py:1237, 1022, 194`) | **kept, cleaned** (267 → 223 lines) | `VideoTimingGenerator` and `TMDSEncoder` are used from LiteX. `VideoHDMIPHY` needs a separate pixel-clock domain; here all 4 global nets are taken, so video runs in `gtx0` (125 MHz) with a 1/5 clock enable (`DVIPHY`, `_Serializer10to2`). `VideoFrameBuffer` reads 640x480 rgb565: that is 92% of the bandwidth of a 16-bit SDRAM at 20 MHz. `FrameBuffer2x` reads 320x240 and doubles the pixels in hardware. The two-clock path (`Divide5`, branches without CE) was removed, because without Ethernet it is not in the recommended build. |
| `usb_hid.py` + `verilog/usbhost/*` (7) | partly: `USBOHCI` (`litex/soc/cores/usb_ohci.py:29`) | kept | Used by `ghrec_1` (bitstream in `bitstreams/`). OHCI needs a 48 MHz PLL (a 5th global net next to 1G) and a kernel with `CONFIG_USB_OHCI_HCD_PLATFORM`, which the prebuilt 5.14 does not have. Emard's low-speed HID host runs at 125 MHz/21 over local routing. License GPL (`verilog/usbhost/README.md`). |
| `verilog/mdio_core.v` → `mdio_core.py` | partly: `LiteEthPHYMDIO` (`liteeth/phy/common.py:34`) | **rewritten in Migen** (instruction #69), Verilog removed | LiteEth only has bit-bang MDIO over CSR, so software would configure the PHY. KSZ9031 must advertise only 1000FD before the BIOS starts netboot, without the CPU. `MDIOCore` does this in hardware and provides the registers for CSR `phy_status0/1`. Equivalence proof and board test: section "MDIO: Verilog → Migen" below. |
| `__init__.py` | — | **removed** | Package marker for `from gateware.eth_stack import …`. Nobody imports `gateware` as a package. |
| `eth_stack.py` | yes: `LiteEthUDPIPCore` (liteeth) + `TXLastBE8` | **removed** | Used only in hwstack mode (`--eth-mode hwstack`), which the recommended build does not use. `TXLastBE8` was already disabled (`tx_last_be_fix=False`), because LiteX ≥ 7fca6dba sets `last_be` itself. |
| `target_eth.py` | — | **removed** | CPU-less 100 Mb/s design (TASK-4999). Not part of the SBC. Its bitstreams are not in the repository. In tag `pre-cleanup-20260926`. |
| `target_gbe.py` | — | **removed** | CPU-less 1 Gb/s design (ping without a CPU, TASK-5032). Only the pin list was moved from it into `target_soc.py`. In the tag. |
| `phy_rgmii_gatemate.py` | yes: copy of the LiteEth RGMII PHY with GateMate primitives | **removed** | 100M PHY for `target_eth.py`. 1G uses `gbe_phy.py`. |
| `ulx5m_eth_platform.py` | no | **removed** | Pins for `target_eth.py`. |
| `crg.py` | yes: CRG from `targets/intergalaktik_ulx5m_gs.py` | **removed** | CRG for `target_eth.py`. `target_soc.py` has its own `SoCCRG`. |
| `mdio_sequencer.py` | yes: `LiteEthPHYMDIO` + software | **removed** | 100M writes (TASK-4963). In the 1G SoC this is done by `mdio_core.v`. |
| `mdio_diag.py`, `jtag_probe.py`, `verilog/jtag_mailbox.v`, `pll_serial.py`, `status_leds.py`, `beacon.py`, `l2_beacon.py`, `raw_tx.py` | — | **removed** | Diagnostics from the fault-finding phase (UART dump of MDIO registers, JTAG mailbox, serial PLL bits, LEDs, UDP/L2 beacon, raw TX frames). Used only by `target_eth.py` or `target_gbe.py`. |
| `pll_stdy.py`, `sticky_lock.py`, `gbe_phy.py`, `video_sbc.py`, `usb_hid.py` | see above | kept | |

The board platform is not copied anywhere: all designs use `litex_boards.platforms.intergalaktik_ulx5m_gs`.

`_status_leds` in `target_soc.py` is kept. Upstream has the same pins as `user_led_n` (active low, different order of
LED 4/5), while our design drives them directly (no inversion) with `DRIVE=3`. Replacing it would change the polarity and order of the LEDs.

## Table: other

| File / folder | Decision | Reason |
|---|---|---|
| `docs/litex-b6ae9e0b2-local.patch` | **removed** | The tristate part (`common.py`) is a NO-OP. The Python expression `~a if c else ~b` is the same as `~(a if c else b)`. EVIDENCE: a build with the upstream `common.py` restored gives an identical `.v` (13,524 lines; `CC_IOBUF` is used 64 times, so the code really was executed). The BIOS part only prints one line ("Ident: …"). Instruction #32 added it because the banners showed two addresses (.212 hardware, .213 CPU). The hardware stack is now removed, and on netboot the BIOS itself prints "Local IP: 192.168.10.213" (`bios/boot.c:848`) and has an `ident` command. So the patch is no longer needed, and LiteX is clean upstream. |
| `docs/litex-bios-print-ident.patch` | **removed** | Duplicate of the second part of the patch above. |
| `ter-u16b.bdf` | **removed** | Terminus font (OFL license). No file uses it (`grep -r ter-u16b` = 0 hits). |
| `build/Makefile` | **removed** | Builds and flashes `target_eth.py` (`build/eth/…`), i.e. the 100M design. |
| `build/s_grec_3/`, `build/s_ghrec_1/` (`csr.json`, `csr.csv`) | kept | `tools/linux/mkdts.py` uses them to make the DTS for the two bitstreams in `bitstreams/`. |
| `test_script/` (3) | **removed** | UDP echo and UART test for the CPU-less designs. |
| `sim/tb_gbe_phy.py`, `tb_scaler2x.py`, `tb_watchdog.py`, `tb_sticky_lock.py`, `test_boot_option.py` | kept | They test modules that remain. The `mdio_sequencer` part was removed from `tb_sticky_lock.py`. `test_boot_option.py` was adapted: no hwstack, `sdnet` added. |
| `sim/tb_beacon, tb_l2_beacon, tb_io50, tb_lastbe, tb_mdio_diag, tb_mdio_sequencer, tb_rgmii_tx_sf, tb_stack, tb_txc_phase`, `lastbe_env.sh`, `test_refclk_oe.sh`, `io50rtl/`, `postsynth/` | **removed** | They test removed modules or are one-off checks (TASK-4999 100M, LiteX `last_be` regression). |
| `tools/soc_build.sh`, `tools/sbc_env.sh` | kept | `soc_build.sh` now sources `sbc_env.sh` (before, both had the same paths). The line for `pythondata-misc-usb_ohci` was removed: OHCI is removed, and `env.sh` adds all `pythondata-*` anyway. |
| `tools/linux/` (`mkdts.py`, `netboot_app.sh`, `linux_boot.sh`, `lx_cmd.sh`, `README.md`) | kept | Linux: DTS, TFTP, boot on the board. |
| `tools/linux/rv32_grec_3.dts`, `rv32_ghrec_1.dts` | kept | DTS for the two bitstreams in the repository. The root README uses `rv32_grec_3.dts`. |
| `tools/linux/rv32_dvi_1, gcer_1, gdvi_1, gdvi_9, smp8_9, spisd_1.dts` | **removed** | DTS files for builds whose bitstreams are not in the repository. `mkdts.py` generates them from any build. |
| `tools/doom_linux/`, `tools/rootfs/`, `tools/usbhidd/` | kept (`.empty` removed) | DOOM, rootfs and USB keyboard for Linux. |
| `tools/speedtest/` | kept (duplicate `netboot_app.sh` removed) | Throughput measurement (open question "throughput under Linux"). `eth_speedtest.sh` no longer has a default bitstream that is not in the repository (`BIT=` is required), and it uses `tools/linux/netboot_app.sh`. |
| `tools/dvi/testimg_cmds.sh`, `tools/sd/bios_cmds.sh` | kept | Test image in the framebuffer and entry of BIOS commands. |
| `tools/dvi/{idle_series,loadtest,lx_session,mitigation_sweep,pll_discriminator,vtest}.sh` | **removed** | One-off measurements of image dropouts (TASK-5040/5044/5047) with HDMI capture on the Pi. Results are in `docs/SBC_DVI_USB_TASK-5040.md` and `…5047.md`. |
| `tools/t5007/`, `fabtest/`, `pnr_probe/`, `uhello/`, `uloop/`, `gbe/`, `pll_*.py` (6), `jtag_bert.py`, `jtag_mailbox.py`, `mbprobe_top.*`, `nt_all.sh`, `rxstart.sh`, `gbe_build.sh` | **removed** | One-off tests from fault finding (PLL, JTAG, MDIO, fabric, nextpnr bug repro) and build/acceptance of the CPU-less designs. The findings are in `docs/HW_DIAG_20260923_TASK-4999.md` and `docs/LESSONS_GATEMATE.md`, and the scripts are in the tag. |

## What was not touched

- `docs/` (except the two patches and this document): measurement and research logs. They mention removed files, and
  those are in the tag `pre-cleanup-20260926`.
- The inside of `gbe_phy.py`: the `txc_bufg=False` branch and `txc_sel` stay. It is a small, tested PHY (`tb_gbe_phy.py`).
- `--with-sdcard` / `--sdcard spi` / `--boot sdnet`: the SD card is work in progress (root README: "What does not work
  yet"), so these options stay.
- `--video-640x240`: a working option (80x30 text) and it is covered by `tb_scaler2x.py`.

## MDIO: Verilog → Migen (instruction #69, #70)

`gateware/verilog/mdio_core.v` was rewritten as `gateware/mdio_core.py` (`MDIOCore`, LiteXModule): same parameters
(`write_after`, `reg9`, `reg4`, `reg0`), same `snap` (256 bits), same PHY `rst_n`, all registers without reset as in
the Verilog. The UART output and the `dbg` input were removed, because the SoC did not connect them (the pins belong to the BIOS serial).

### 1. Simulation (before integration)

`sim/tb_mdio_core_equiv.py`: the old Verilog (from git, commit `251bcb7`) and the Migen module converted to Verilog run
side by side in Icarus Verilog, each with its own model of a KSZ9031 MDIO slave (ID 0x0022/0x1622, registers are
reset by RESET_N, writes are stored). Every sys clock compares MDC, the resolved MDIO line, `moe`, `mdo`,
RESET_N and the whole `snap`. RXC is asynchronous, and RX_CTL is pseudo-random.

| case | cycles | difference | at the end (snap) |
|---|---|---|---|
| SoC: WRITE_AFTER=0, REG9=0200, REG4=0001, REG0=1200, PHYAD 3 | 10 598 097 | **0** | 3456 MDC edges, idm=08, r4=0001, r9=0200 (write read back) |
| WRITE_AFTER=2, REG9=0000, REG4=0101, PHYAD 0 | 14 823 601 | **0** | 4416 MDC edges, idm=01, r4=0101, r9=0000 |
| negative control (`--mutate`: the new module gets REG4^0x0400) | 10 598 097 | 4 234 113 | the comparison really catches the difference (rc=1) |

### 2. Board (ULX5M-GS, only `fpga-jtag gs … -r`, console `/dev/serial/by-id/…E660583883501E2C-if01`)

First a small SoC (VexRiscv standard + BIOS + 1G, `--boot none`, `--phy-snap-csr`), and only then the Linux SoC.
Cable → board mapping confirmed on 2026-09-26 at 10:53: a BIOS loaded with `fpga-jtag gs` prints to the by-id console.
All bitstreams have `gmpack --reset` (checked in `build_*.sh`).

| step | bitstream | read through the new module | conclusion |
|---|---|---|---|
| control | old Verilog (`mdo_1`, same small SoC) | R1=796D, R1F=0348, RXC 125 MHz | reference link 1000FD |
| (a) ID | `mdt_3` (REG4=0001) | idm=0x08 → reg2 = 0x0022 at PHYAD 3 (addr=3) | MDIO read works |
| (b) write ≠ current | `mdt_2` (REG4=0C01, write in the 255th pass) after a design that writes 0001 | r4=0C01, r9=0200, wrote=1 | write by the new module, read back |
| (c) hardware reset | `mdt_2` then `mdt_4` (never writes) | after `mdt_2`: r4=0C01; in `mdt_4`: r0=1140, r4=01E1, r9=0300, wrote=0 | RESET_N of the new module returned the PHY to factory values |
| link | `mdt_3` (production parameters) | R1=796D, R1F=0348, RA=3800, RXC 125 MHz | same as the old Verilog |

Side note: with REG4=0x0C01 (pause bits) AN does not complete on this switch (R1=7949, RXC 25 MHz); with 0x0001 and with the factory
0x01E1 it completes. This is a property of the test value, not of the module (A/B with the same SoC).

The first two attempts (10:37, 10:45) were discarded: a second DirtyJTAG is connected to the Pi, and `openFPGALoader -c dirtyJtag`
opens the first probe and ignores `--busdev-num`. That is why the Pi scripts in `tools/` load through `fpga-jtag` (`tools/dj_probe.sh`).

### 3. Timing and seed

Every netlist change changes the placement, so a seed is not portable. Criterion: 0 hold violations and grx (RXC) PASS at
125 MHz. Builds with hold violations in the VexRiscv D-cache BRAM path run the BIOS in a reset loop at memtest (mg_1:
8 violations, mdt_4 seed 1: 3); all good ones have 0. Linux SoC with the new module (command from the README, only the seed):

| seed | hold | grx | CPU | P&R |
|---|---|---|---|---|
| 1 | 8 | 127.8 PASS | 22.7 | reset loop on the board |
| 2 | 0 | 123.4 FAIL | 21.7 | |
| **3** | **0** | **138.7 PASS** | **25.4** | **on the board: Linux login after 707 s, ping .213 5/5 and 10/10, from Linux `csrpeek 0xf0002804 2` = `796d0348 38006400` (R1F=0348 = 1000FD, RXC 125 MHz)** |
| 4 | 0 | 111.0 FAIL | 23.2 | |
| 6 | 0 | 125.3 PASS | 21.3 | Linux boots (init), timing edge |
| 7 / 8 / 12 | 0 | 121.5 / 123.2 / 124.0 FAIL | | |
| 10 | 0 | 131.6 PASS | 21.5 | |

Seed 3 is still the right choice for the command from the root README, so the command does not change. The bitstreams in
`bitstreams/` stay the ones built before this review (old Verilog MDIO, LiteX with the patch). A build from the current code
with seed 3 was checked on the board (above), but was not added to `bitstreams/`.
