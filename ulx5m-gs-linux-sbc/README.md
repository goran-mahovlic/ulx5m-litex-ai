# LiteX Ethernet for the Radiona ULX5M-GS (GateMate)

A minimal, CPU-less 100 Mbps Ethernet design for the **Radiona ULX5M-GS**
(CologneChip **GateMate CCGM1A1** + Microchip **KSZ9031** RGMII PHY), built
entirely with the **open toolchain** (Yosys -> nextpnr-himbaechel -> gmpack).

The design is a UDP/IP endpoint with no soft CPU:

```
KSZ9031 RGMII PHY (100M) -> LiteEth MAC/ARP/IP/ICMP/UDP core -> UDP echo engine
```

- **ICMP ping** is answered automatically, in hardware.
- **UDP echo**: any datagram sent to `<ip>:<port>` is echoed back to its sender.
- No CPU, no BIOS, no vendor tools.

It is meant as a clean starting point: swap the `UDPEcho` engine for your own
sys-domain application on a UDP port and you have a bare-metal networked FPGA.

## Hardware

| Item | Value |
|---|---|
| Board | Radiona ULX5M-GS (v0.4) |
| FPGA | CologneChip GateMate CCGM1A1 |
| PHY | Microchip KSZ9031 (RGMII) |
| Link | 100 Mbps, full duplex (fixed; no MDIO negotiation driven) |
| Default IP | 10.10.10.50 |
| Default UDP echo port | 7000 |
| Programmer | on-board FT232 (`openFPGALoader -c ft232`) |

## Repository layout

```
gateware/
  target_eth.py           # top-level SoC (SoCMini): PHY + stack + UDP echo + LEDs
  crg.py                  # split-clock CRG (two GateMate PLLs off the 25 MHz osc)
  phy_rgmii_gatemate.py   # GateMate RGMII PHY (100M fixed; no DELAYG primitive)
  eth_stack.py            # LiteEth stack wrapper (EthUDPStack) + UDPEcho engine
  ulx5m_eth_platform.py   # RGMII/MDIO pin extension (installed platform untouched)
  status_leds.py          # 8-LED bring-up ladder (heartbeat, link, RX/TX, build-id)
sim/
  tb_stack.py             # migen sim: ICMP ping + ARP resolve + UDP echo
build/
  Makefile                # build + JTAG/flash/DFU helpers
test_script/
  udp_echo_test.py        # host-side UDP echo smoke test
docs/
  GATEMATE_CLOCKING.md    # the split-clock architecture and its three hard traps
  PINMAP.md               # RGMII/MDIO ball map
  LITEETH_INTEGRATION.md  # how the CPU-less core is assembled + the UDP port API
env.sh                    # toolchain + LiteX environment (override paths via env)
```

## Prerequisites

- An **oss-cad-suite** install (Yosys, nextpnr-himbaechel, gmpack, openFPGALoader).
- A **LiteX** checkout tree containing `migen`, `litex`, `liteeth`, `litedram`
  and `litex-boards`.

`env.sh` points at both. Override the locations if yours differ:

```bash
OSS_CAD_SUITE=/opt/oss-cad-suite LXROOT=/opt/litex source ./env.sh
```

> Note: `env.sh` puts the LiteX fork's `migen` ahead of any oss-cad bundled
> `migen`. The migen simulator's memory transform crashes if the order is wrong.

## Build

```bash
source ./env.sh
python3 gateware/target_eth.py --build
# -> build/eth/gateware/intergalaktik_ulx5m_gs.bit
```

Or via the Makefile (also stages the bitstream into `build/`):

```bash
cd build
make bit
```

Useful options on `target_eth.py`: `--ip`, `--udp-port`, `--sys-clk-freq`,
`--build-id`, `--seed`.

## Full LiteX SoC (phase 2, TASK-5032/5033, branch `soc-sdram-sd`)

`gateware/target_soc.py`: VexRiscv @ 20 MHz, 64 MiB SDRAM (IS42VM16320E, GENSDRPHY), BIOS serial on
GPIO5 (TX, IO_NB_B5) / GPIO4 (RX, IO_NA_B6), 1000 Mb/s Ethernet (hardware ARP/ICMP on 192.168.10.212 +
Etherbone UDP 1234), LiteSDCard. Build (environment: `tools/soc_build.sh`, LiteX tree `~/app/litex-1g-deps`):

```bash
tools/soc_build.sh <name> --sdram-clk inv --cpu-variant standard --with-gbe --with-sdcard --seed 9          # --boot none
tools/soc_build.sh <name> --sdram-clk inv --cpu-variant lite --with-gbe --with-sdcard --boot netboot --seed 9
```

`--boot` selects the BIOS boot source:

| `--boot` | BIOS | notes |
|---|---|---|
| `none` (default) | console only (`BIOS_NO_BOOT`) | without it the BIOS hangs in the SD boot when no card is inserted |
| `serial` | serialboot (`litex_term --kernel`), then console | `SDCARD_BOOT_DISABLE`, `NET_BOOT_DISABLE` |
| `sdcard` | SD card (boot.json / boot.bin) first, then serial | `SDCARD_BOOT_PRIORITY=-1`, `NET_BOOT_DISABLE` |
| `netboot` | TFTP boot.json / boot.bin from `--remote-ip` (default 192.168.10.14), then serial | adds a CPU port to the MAC (hybrid, MAC 10:e2:d5:00:00:01, `--local-ip` 192.168.10.213); needs `--with-gbe`; with `standard` the SoC no longer places (77 % LT, 4 CC_MULT) -> use `--cpu-variant lite` |

`sim/test_boot_option.py` checks the generated BIOS defines of every mode. The TFTP server is the Pi
(service `tftp-litex`, root `/srv/tftp`), see `docs/SOC_FAZA2_20260925_TASK-5033.md`. Board tests on the Pi:
`tools/gbe/soc_accept.sh` (BIOS + 64 MiB mem_test + ping sweep + Etherbone) and `tools/gbe/nb_accept.sh` (netboot).

## Load and test

```bash
cd build
make jtag        # load into SRAM over JTAG (volatile, non-destructive)
# or: make flash # write to SPI flash@0 (persistent)
```

Put a host NIC on the same subnet and test:

```bash
sudo ip addr add 10.10.10.1/24 dev <iface>
ping 10.10.10.50
python3 ../test_script/udp_echo_test.py --ip 10.10.10.50 --port 7000
```

## Status LEDs

Active-high; left-to-right on the board silk (LED0..LED7):

| LED | Meaning |
|---|---|
| 7 | heartbeat (~1 Hz) - sys clock alive, reset released |
| 6 | reset released (sticky) |
| 5 | UDP TX activity (stretched) |
| 4 | UDP RX activity (stretched) |
| 1 | link up (RGMII in-band status) |
| 3, 2, 0 | 3-bit build-id tag (`--build-id`), MSB->LSB |

## Simulation

```bash
source ./env.sh
python3 sim/tb_stack.py     # -> ALL TESTS PASSED
```

Runs the LiteEth core against LiteEth's pure-migen model PHY: ICMP ping, ARP
resolution, and UDP echo, independent of RGMII I/O timing.

## Design notes

The two things that make Ethernet work on this specific board are documented in
`docs/`:

1. **100 Mbps datapath, not gigabit.** RXC (25 MHz) lands on a non-clock-capable
   pin (`IO_EB_A7`); gigabit's 125 MHz RXC cannot be clocked. The PHY runs the
   RGMII datapath in fixed 10/100 nibble-gearing mode (`fixed_100m=True`) and
   forwards a 25 MHz TXC. See `docs/LITEETH_INTEGRATION.md`.
2. **Split-clock CRG.** A single 25 MHz fabric clock does not close timing on
   this board. Two PLLs are used: 25 MHz for the thin TX serdes, 16 MHz for the
   fabric/packet pipeline. See `docs/GATEMATE_CLOCKING.md`, including the three
   toolchain traps (no CC_BUFG on RXC, the GateMatePLL lock caveat, no duplicate
   create_clock on PLL-derived clocks).

## License

BSD-2-Clause. See `LICENSE`.
