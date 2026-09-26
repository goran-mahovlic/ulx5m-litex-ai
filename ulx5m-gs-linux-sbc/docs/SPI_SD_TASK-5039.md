# SPI-SD on the Linux SoC (Kölsch style) — TASK-5039, 2026-09-25

Branch `linux-vexriscv-smp` (from tag `linux-boot-ok-2509`). Author: Jelena.

## Summary

| Item | Result |
|---|---|
| P&R SMP 1c 4K/4K + 1G CPU MAC + `add_spi_sdcard()` | **PASS**: CPE_LT **22 729 / 40 960 (55%)**, RAM_HALF **50 / 64**, CPE_FF 7 884 (19%) |
| Comparison with LiteSDCard (smpM, J7/J14) | 31 643 LT (77%), the placer fails → SPI-SD costs only **+85 CPE_LT** and **+5 RAM_HALF** against the baseline without SD (22 644, 45) |
| Linux 5.14 boot on the board (s1) | **YES**: login in 131 / 135 s, `mmc_spi spi0.0: SD/MMC host mmc0` |
| 1G network on the same bitstream | Pi → Linux 10/10 (56 B), 5/5 (1400 B); Linux → Pi 3/3 |
| **Card (Goran inserted it)** | **Does NOT respond to initialisation**: BIOS `FatFs error 3` (FR_NOT_READY), Linux has no `mmc0: new SD card`, `ls /dev/mmc*` is empty. The same with the native LiteSDCard (S5NoBoot): `sdcard_init` returns nothing. |

Steps 2 and 3 of the recipe (yosys `setattr -unset ram_style`, ROM 64K→32K) **were not needed**: 55% is far below the placer limit (~71%).

## Build

    tools/soc_build.sh spisd_1 --sdram-clk inv --cpu-type vexriscv_smp --cpu-variant linux \
        --with-gbe --eth-mode mac --sdcard spi --boot sdnet --seed 1

- `--sdcard {none,native,spi}` (new; `--with-sdcard` = `native`).
- `--boot sdnet` (new): the BIOS first tries SD (boot.json on FAT), then TFTP, then serial. Without a reply from the card, SPI-SD just times out and the BIOS continues with netboot (measured: it does not hang, unlike J1 with LiteSDCard).
- Bitstream: `bitstreams/ETH_GateMateA1_2509_1529_Linux_SPISD_s1.bit`, sha256 `06681e65f2c49c1c42841cc8819280f5f6baa09657b196b3659ac5bdbc2a45a9`.

| seed | CPE_LT | RAM_HALF | cpu (20 MHz) | gtx (125) | grx/rxc (125) | result |
|---|---|---|---|---|---|---|
| 1 | 22 729 | 50 | 23.9 PASS | 106.0 FAIL | 129.7 PASS | bitstream, **works on the board** (Linux + 1G) |
| 2 | 22 768 | 50 | — | — | — | bitstream |
| 3 | 22 768 | 50 | 20.8 PASS | 109.2 FAIL | 119.6 FAIL | bitstream |
| 11 | 22 729 | 50 | 21.2 PASS | 111.3 FAIL | 112.2 FAIL | bitstream |
| 7 | — | — | — | — | — | packing: "unbound cell … mult_passthru CPE_L2T4" |
| 5, 9 | — | — | — | — | — | router does not converge (overused 1–2 after 2 900 / 5 100 iterations), stopped |

As with tag `linux-boot-ok-2509` (grx 87 MHz FAIL, and it works), nextpnr timing on gtx/grx is not decisive for operation on the board: s1 passes 1G ping with gtx at 106 MHz according to nextpnr.

## DTS

`python3 tools/linux/mkdts.py build/s_spisd_1 > tools/linux/rv32_spisd_1.dts`. The only difference from `rv32_smp8_9.dts` is the new node (the other addresses are the same):

    litespisdcard0: spi@f0003800 { compatible = "litex,litespi"; litespi,sck-frequency = <1500000>;
        mmc-slot@0 { compatible = "mmc-spi-slot"; voltage-ranges = <3300 3300>; spi-max-frequency = <1500000>; }; };

On the Pi: `dtc -O dtb -o /srv/tftp/rv32sd.dtb rv32_spisd_1.dts`, `netboot_app.sh linuxsd` (new mode: boot.json with `rv32sd.dtb`).
The prebuilt kernel 5.14 driver accepts it: the `mmc_spi` host registers without our own Buildroot.

## Why the card does not work — diagnosis

1. **It is not the SPI-SD core**: the native LiteSDCard (different RTL, different BIOS driver) has the same symptom.
2. **It is not the file system**: FatFs error 3 = `FR_NOT_READY` (disk_initialize failed). Without FAT it would be 13 (`FR_NO_FILESYSTEM`); and even then Linux would not miss `mmcblk0`.
3. **The pins are correct** (`tools/kicad_netlist.py` on `ulx5m-gs-hw/hardware`): SD_CLK J2.57↔IO_NA_A3, SD_CMD J2.62↔IO_NA_B3, SD_DAT0 J2.63↔IO_NA_A1, SD_DAT3 J2.61↔IO_NA_A2 (DAT1 IO_NB_A5, DAT2 IO_NA_B2) — the same as `spisdcard`/`sdcard` in litex-boards. Direct, without resistors or level shifters.
4. **Voltage level (HYPOTHESIS, most likely)**: `VDD_NA` and `VDD_NB` are on the **`SDRAM_VCC` = 1.8 V** net (board README: "DEFAULT SDRAM PART is 1.8V"). An SD card initialises with 3.3 V signalling (SPI mode does not support 1.8 V at all); the card input threshold VIH ≥ 0.625 × 3.3 V ≈ 2.06 V, while the FPGA gives 1.8 V. In the other direction the card would drive 3.3 V into a 1.8 V bank.
5. **Card power (HYPOTHESIS)**: on the CM4 connector, J2.75 (`SD_PWR_ON` per the CM4 pinout) and J2.73 (`SD_VDD_OVERRIDE`) are not connected on the ULX5M-GS. If the carrier board (CM4 IO board) uses that signal to switch on the card VDD, the card has no power.

The board README (v02) says "SD – tested and working with LiteX": that was probably a version with a 3.3 V bank or a different carrier board — needs Goran's confirmation.

## What is needed to continue (hardware, not gateware)

- Which carrier board it is, and whether the card slot gets 3.3 V (measure VDD on the slot) — given that `SD_PWR_ON` is not connected.
- If VDD is 3.3 V: SD on a 1.8 V bank needs a level shifter (or a board with 3.3 V `SDRAM_VCC`, but then also a 3.3 V SDRAM).
- Gateware (`--sdcard spi --boot sdnet`), DTS and kernel are ready: as soon as the card responds, the check is `dmesg | grep mmc`, `cat /proc/partitions`, then `mount -o ro /dev/mmcblk0p1 /mnt` (read-only, instruction #49).

## Logs

- `docs/linux/linux_boot_spisd_s1.txt` — BIOS (SD in SPI mode → FatFs 3 → netboot) + Linux boot with the `mmc_spi` host.
- `docs/linux/bios_s5_sdcard_init_t5039.txt` — native LiteSDCard: `sdcard_detect` "inserted", `sdcard_init` with no response.
