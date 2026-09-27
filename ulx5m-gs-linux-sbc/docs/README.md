# Documents in `docs/`

Engineering notes, measurements and logs from building the ULX5M-GS Linux SBC.
Most files are dated reports tied to one task (`TASK-NNNN`). They describe the state at that date;
the current state of the project is in the [project README](../README.md).

## Ethernet 100M / 1G

| Document | What it is |
|---|---|
| [PINMAP.md](PINMAP.md) | RGMII and MDIO pin map of the KSZ9031 PHY on the ULX5M-GS, checked against the schematic. |
| [GATEMATE_CLOCKING.md](GATEMATE_CLOCKING.md) | How RGMII clocks (RXC/TXC) are handled on the GateMate for 100 Mbps. |
| [LITEETH_INTEGRATION.md](LITEETH_INTEGRATION.md) | How the LiteEth core is put together without a CPU, and how to attach your own logic to a UDP port. |
| [FLASH_TEST_20260921_TASK-4959.md](FLASH_TEST_20260921_TASK-4959.md) | First flash and network test of a clean 100M build, where ping and ARP failed, with the list of possible causes. |
| [MDIO_SEQUENCER_20260921_TASK-4963.md](MDIO_SEQUENCER_20260921_TASK-4963.md) | A hardware MDIO sequencer that forces the PHY to 100 Mbps without a CPU, with its testbench and ping test. |
| [GBE_FEASIBILITY_20260921_TASK-4961.md](GBE_FEASIBILITY_20260921_TASK-4961.md) | Study of whether 1 Gbps Ethernet can close timing on the GateMate, with measured Fmax and the bottlenecks. |
| [GBE_FORKS_20260921_TASK-4962.md](GBE_FORKS_20260921_TASK-4962.md) | What the LiteEth/LiteX forks of pu-cc, mmicko and trabucayre do for 1 Gbps on the GateMate. |
| [UPSTREAM_ISSUES_draft.md](UPSTREAM_ISSUES_draft.md) | Draft upstream bug report: nextpnr drops the clock inversion when a negedge flip-flop is merged into the GateMate IO cell. |
| [seed_sweep_io50_20260924.txt](seed_sweep_io50_20260924.txt) | Raw results of a placer seed sweep: ping at 100M and 1000M for each seed. |

## Hardware diagnostics

| Document | What it is |
|---|---|
| [HW_DIAG_20260923_TASK-4999.md](HW_DIAG_20260923_TASK-4999.md) | Full hardware diagnosis of the KSZ9031 and its IO_EB_A3 reference clock, measured from inside the FPGA over UART. |
| [DRIVE_FIX_20260923_TASK-4999.md](DRIVE_FIX_20260923_TASK-4999.md) | The root cause found in that diagnosis: the PHY reference clock pin had too weak a drive (DRIVE=3), and the fix. |

## Linux SoC

| Document | What it is |
|---|---|
| [SOC_PHASE2_20260925_TASK-5033.md](SOC_PHASE2_20260925_TASK-5033.md) | Final report on the full LiteX SoC with SDRAM and 1G netboot: bitstreams, resource use, measurements and open findings. |
| [RESEARCH_LINUX_GATEMATE_2509_TASK-5035.md](RESEARCH_LINUX_GATEMATE_2509_TASK-5035.md) | Research on running Linux on the GateMate with SDRAM: what fits, and alternatives (nommu, SaxonSoc, VexiiRiscv). |
| [SPI_SD_TASK-5039.md](SPI_SD_TASK-5039.md) | Adding an SPI SD card controller to the Linux SoC: resource cost, Linux boot and why the card does not answer yet. |
| [REVIEW_LITEX_DUPLICATES.md](REVIEW_LITEX_DUPLICATES.md) | Review of which files in this project duplicated LiteX code, what was removed, and why the remaining local files are needed. |
| [linux/](linux/) | Console logs of Linux boots and of the BIOS SD card init (raw output, not edited). |
| [soc_s5/](soc_s5/) | Raw acceptance-test logs of the SoC bitstreams: memory tests, netboot, ping flood and speed tests. |

## DVI, DOOM and USB

| Document | What it is |
|---|---|
| [RESEARCH_DOOM_DVI_2509_TASK-5036.md](RESEARCH_DOOM_DVI_2509_TASK-5036.md) | Research on running DOOM with a DVI framebuffer in SDRAM: bandwidth, resources and the proposed video module. |
| [SBC_DVI_USB_TASK-5040.md](SBC_DVI_USB_TASK-5040.md) | Building the standalone computer: DVI test image, Linux console on DVI, DOOM from Linux and the USB host. |
| [SBC_DVI_USB_TASK-5047.md](SBC_DVI_USB_TASK-5047.md) | Why the PLL loses lock under SDRAM load (timing or power supply), with board measurements and the gateware fix. |
| [doom/](doom/) | Raw nextpnr resource report of the DVI colour-bar build. |
| [USB_HUB_PNRU.md](USB_HUB_PNRU.md) | The PNRU USB 1.1 host (full speed, low speed, hub): port, simulation, clock options, the `usbhostd` driver, Linux 6.12 and the board tests (keyboard, autorepeat, 33 min run). **Current state of USB and Linux 6.12.** |
| [linux/k612_20260926/](linux/k612_20260926/) | Raw logs of the Linux 6.12 boot and the 30 min run (ping, USB statistics). |
| [linux/t5075_20260927/](linux/t5075_20260927/) | DVI grabber pictures of tty1 before and after the autorepeat fix. |
| [linux/dvi_grabber_20260927/](linux/dvi_grabber_20260927/README.md) | Why the HDMI grabber showed a black frame: the grabber chain, not the design. |

## Lessons

| Document | What it is |
|---|---|
| [LESSONS_GATEMATE.md](LESSONS_GATEMATE.md) | Lessons learned on GateMate + KSZ9031, each tagged VERIFIED or HYPOTHESIS, with the evidence. |
