# SPI-SD na Linux SoC-u (Kölsch stil) — TASK-5039, 25. 9. 2026.

Grana `linux-vexriscv-smp` (od taga `linux-boot-ok-2509`). Autorica: Jelena.

## Sažetak

| Stavka | Ishod |
|---|---|
| P&R SMP 1c 4K/4K + 1G CPU MAC + `add_spi_sdcard()` | **PASS**: CPE_LT **22 729 / 40 960 (55 %)**, RAM_HALF **50 / 64**, CPE_FF 7 884 (19 %) |
| Usporedba s LiteSDCard-om (smpM, J7/J14) | 31 643 LT (77 %), placer pada → SPI-SD košta samo **+85 CPE_LT** i **+5 RAM_HALF** prema osnovici bez SD-a (22 644, 45) |
| Linux 5.14 boot na ploči (s1) | **DA**: login za 131 / 135 s, `mmc_spi spi0.0: SD/MMC host mmc0` |
| 1G mreža na istom bitstreamu | Pi → Linux 10/10 (56 B), 5/5 (1400 B); Linux → Pi 3/3 |
| **Kartica (Goran ju je umetnuo)** | **NE odgovara na inicijalizaciju**: BIOS `FatFs error 3` (FR_NOT_READY), Linux nema `mmc0: new SD card`, `ls /dev/mmc*` prazno. Isto i s nativnim LiteSDCard-om (S5NoBoot): `sdcard_init` ne vrati ništa. |

Koraci 2 i 3 recepta (yosys `setattr -unset ram_style`, ROM 64K→32K) **nisu bili potrebni**: 55 % je daleko ispod granice placera (~71 %).

## Build

    tools/soc_build.sh spisd_1 --sdram-clk inv --cpu-type vexriscv_smp --cpu-variant linux \
        --with-gbe --eth-mode mac --sdcard spi --boot sdnet --seed 1

- `--sdcard {none,native,spi}` (novo; `--with-sdcard` = `native`).
- `--boot sdnet` (novo): BIOS najprije pokuša SD (boot.json na FAT-u), pa TFTP, pa serial. Bez odgovora kartice SPI-SD samo istekne i BIOS nastavi netbootom (izmjereno: ne visi, za razliku od J1 s LiteSDCard-om).
- Bitstream: `bitstreams/ETH_GateMateA1_2509_1529_Linux_SPISD_s1.bit`, sha256 `06681e65f2c49c1c42841cc8819280f5f6baa09657b196b3659ac5bdbc2a45a9`.

| seed | CPE_LT | RAM_HALF | cpu (20 MHz) | gtx (125) | grx/rxc (125) | ishod |
|---|---|---|---|---|---|---|
| 1 | 22 729 | 50 | 23,9 PASS | 106,0 FAIL | 129,7 PASS | bitstream, **radi na ploči** (Linux + 1G) |
| 2 | 22 768 | 50 | — | — | — | bitstream |
| 3 | 22 768 | 50 | 20,8 PASS | 109,2 FAIL | 119,6 FAIL | bitstream |
| 11 | 22 729 | 50 | 21,2 PASS | 111,3 FAIL | 112,2 FAIL | bitstream |
| 7 | — | — | — | — | — | pakiranje: „unbound cell … mult_passthru CPE_L2T4” |
| 5, 9 | — | — | — | — | — | router ne konvergira (overused 1–2 nakon 2 900 / 5 100 iteracija), prekinuto |

Kao i kod taga `linux-boot-ok-2509` (grx 87 MHz FAIL, a radi), nextpnr timing na gtx/grx nije mjerodavan za rad na ploči: s1 prolazi 1G ping uz gtx 106 MHz po nextpnr-u.

## DTS

`python3 tools/linux/mkdts.py build/s_spisd_1 > tools/linux/rv32_spisd_1.dts`. Razlika prema `rv32_smp8_9.dts` je samo novi čvor (ostale adrese iste):

    litespisdcard0: spi@f0003800 { compatible = "litex,litespi"; litespi,sck-frequency = <1500000>;
        mmc-slot@0 { compatible = "mmc-spi-slot"; voltage-ranges = <3300 3300>; spi-max-frequency = <1500000>; }; };

Na Piju: `dtc -O dtb -o /srv/tftp/rv32sd.dtb rv32_spisd_1.dts`, `netboot_app.sh linuxsd` (novi način: boot.json s `rv32sd.dtb`).
Prebuilt kernel 5.14 driver prihvaća: `mmc_spi` host se registrira bez vlastitog Buildroota.

## Zašto kartica ne radi — dijagnoza

1. **Nije do SPI-SD jezgre**: nativni LiteSDCard (drugačiji RTL, drugačiji BIOS driver) ima isti simptom.
2. **Nije do datotečnog sustava**: FatFs error 3 = `FR_NOT_READY` (disk_initialize pao). Bez FAT-a bi bio 13 (`FR_NO_FILESYSTEM`); Linux ne bi ni tada propustio `mmcblk0`.
3. **Pinovi su točni** (`tools/kicad_netlist.py` nad `ulx5m-gs-hw/hardware`): SD_CLK J2.57↔IO_NA_A3, SD_CMD J2.62↔IO_NA_B3, SD_DAT0 J2.63↔IO_NA_A1, SD_DAT3 J2.61↔IO_NA_A2 (DAT1 IO_NB_A5, DAT2 IO_NA_B2) — isto kao `spisdcard`/`sdcard` u litex-boards. Izravno, bez otpornika ili pretvarača razine.
4. **Naponska razina (HIPOTEZA, najvjerojatnija)**: `VDD_NA` i `VDD_NB` su na mreži **`SDRAM_VCC` = 1,8 V** (README ploče: „DEFAULT SDRAM PART is 1.8V”). SD kartica se inicijalizira na 3,3 V signalizaciji (SPI način 1,8 V uopće ne podržava); ulazni prag kartice VIH ≥ 0,625 × 3,3 V ≈ 2,06 V, a FPGA daje 1,8 V. U obrnutom smjeru kartica bi tjerala 3,3 V u 1,8 V banku.
5. **Napajanje kartice (HIPOTEZA)**: na CM4 konektoru J2.75 (`SD_PWR_ON` po CM4 pinoutu) i J2.73 (`SD_VDD_OVERRIDE`) su na ULX5M-GS nespojeni. Ako nosiva ploča (CM4 IO board) tim signalom uključuje VDD kartice, kartica je bez napajanja.

README ploče (v02) kaže „SD – tested and working with LiteX”: to je vjerojatno bila inačica s 3,3 V bankom ili druga nosiva ploča — treba Goranova potvrda.

## Što treba za nastavak (hardver, ne gateware)

- Koja je nosiva ploča i dobiva li utor kartice 3,3 V (izmjeriti VDD na utoru) — uz `SD_PWR_ON` nespojen.
- Ako je VDD 3,3 V: SD na 1,8 V banci traži pretvarač razine (ili ploču s 3,3 V `SDRAM_VCC`, ali tada i 3,3 V SDRAM).
- Gateware (`--sdcard spi --boot sdnet`), DTS i kernel su spremni: čim kartica odgovori, provjera je `dmesg | grep mmc`, `cat /proc/partitions`, pa `mount -o ro /dev/mmcblk0p1 /mnt` (samo čitanje, uputa #49).

## Dnevnici

- `docs/linux/linux_boot_spisd_s1.txt` — BIOS (SD u SPI modu → FatFs 3 → netboot) + Linux boot s `mmc_spi` hostom.
- `docs/linux/bios_s5_sdcard_init_t5039.txt` — nativni LiteSDCard: `sdcard_detect` „inserted”, `sdcard_init` bez odgovora.
