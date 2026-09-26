# Linux on ULX5M-GS (TASK-5033, branch linux-vexriscv-smp)

**Result (25. 9. 2026): Linux 5.14 (linux-on-litex-vexriscv prebuilt `linux_2022_03_23`) boots to a Buildroot
root shell over BIOS TFTP netboot**, bitstream `bitstreams/ETH_GateMateA1_2509_1250_Linux_SMP.bit`
(sha256 fa026f5f…2fef, tag `linux-boot-ok-2509`):
- login prompt 176 s after `openFPGALoader -r` (TFTP of ~11 MB included);
- eth0 = 192.168.10.213 after `ip addr add`, ping Linux -> Pi 3/3, Pi -> Linux 5/5;
- log: `docs/linux/linux_boot_smp8_9.txt`.

The DTS files kept here are for the two bitstreams in `bitstreams/`: `rv32_grec_3.dts` (recommended) and
`rv32_ghrec_1.dts` (+ USB HID). DTS files of older builds are in the git tag `pre-cleanup-20260926`.

## SoC

VexRiscv-SMP (1 core, I$/D$ 4 KiB, ITLB/DTLB 4, native LiteDRAM 16 bit, l2 0, no FPU) + 1G CPU MAC
(`--eth-mode mac`: 8-bit LiteEthMAC in sys, no hardware ARP/ICMP/Etherbone) + BIOS netboot. No SD card: with
LiteSDCard it does not place (77 % CPE_LT, lesson J7).

| CPE_LT | CPE_FF | RAM_HALF | CC_MULT | seed 9 (nextpnr) |
|---|---|---|---|---|
| 22 644 / 40 960 (55 %) | 7 732 (18 %) | 45 / 64 | 4 | cpu 20.5 MHz PASS, gtx 127.6 PASS, grx 87.2 FAIL (works on the board) |

    tools/soc_build.sh smp8_9 --sdram-clk inv --cpu-type vexriscv_smp --cpu-variant linux \
        --with-gbe --eth-mode mac --boot netboot --seed 9
    # needs pythondata-cpu-vexriscv_smp in ~/app/litex-1g-deps (git clone --depth 1; its default netlist
    # VexRiscvLitexSmpCluster_Cc1_Iw32Is4096Iy1_Dw32Ds4096Dy1_ITs4DTs4_Ldw16_Ood.v is used)

The first attempt with `add_ethernet(data_width=32)` sent ARP requests, but RX never delivered a frame
(BIOS "ARP failed"; tcpdump showed the replies on the wire). The 8-bit MAC is the same as the proven hybrid path.

## Images and TFTP (Pi 192.168.10.14, /srv/tftp, service tftp-litex)

- `Image`, `rootfs.cpio`, `opensbi.bin` come from https://github.com/litex-hub/linux-on-litex-vexriscv/issues/164 (`linux_2022_03_23.zip`).
- `rv32.dtb` is built from this SoC: `mkdts.py` = `litex_json2dts_linux` + a `litex,liteeth` node without MDIO (our GbePHY has no MDIO CSRs, and the Linux driver maps only "mac" and "buffer"). It is compiled on the Pi, because the container has no dtc:

      python3 tools/linux/mkdts.py build/s_smp8_9 > rv32.dts       # soc_build.sh environment
      dtc -O dtb -o /srv/tftp/rv32.dtb rv32.dts                       # on the Pi
      ~/FPGA/netboot_app.sh linux     # boot.json: Image, rv32.dtb, rootfs.cpio, opensbi.bin (OpenSBI last = jump)

## Board scripts (on the Pi)

- `bash tools/linux/linux_boot.sh <bit> 330`:
  1. writes boot.json (linux);
  2. loads the bitstream;
  3. watches the console for the login prompt, logs in as root and pings .213;
  4. switches TFTP back to the demo.
- `bash tools/linux/lx_cmd.sh "<cmd>" [wait]` types one command into the console at 80 ms per character. Typing faster loses or duplicates characters on the DirtyJTAG UART bridge.
- The kernel ignores `ip=` (no IP_PNP) and Buildroot leaves eth0 down, so bring it up with `ip addr add 192.168.10.213/24 dev eth0; ip link set eth0 up`.
- The CPU is 192.168.10.213 (MAC 10:e2:d5:00:00:01). This SoC has no hardware stack, so 192.168.10.212 is not used.

## SPI-SD (TASK-5039)

`--sdcard spi --boot sdnet` (SD first, then TFTP): P&R PASS at 55 % CPE_LT / 50 RAM_HALF, Linux boots and registers
`mmc_spi` host mmc0, 1G ping works. The inserted card does not answer the init (same with LiteSDCard), most likely a
1.8 V bank vs 3.3 V card level/power issue — see `docs/SPI_SD_TASK-5039.md`. Boot with `APP=linuxsd bash linux_boot.sh
<bit>` (uses `rv32sd.dtb`: `mkdts.py` output of the SPI-SD build); `tools/sd/bios_cmds.sh <bit> "<cmd>"...` types BIOS commands.
