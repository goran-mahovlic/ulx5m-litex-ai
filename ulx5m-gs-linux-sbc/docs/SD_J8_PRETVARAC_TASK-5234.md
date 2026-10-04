# SD na ULX5M-GS preko vanjskog modula s pretvaračem razina (opcija A) — TASK-5234, 4. 10. 2026.

Goranova odluka 4. 10. 2026. 15:27: **opcija A** — vanjski microSD modul s pretvaračem 1,8 V ↔ 3,3 V na slobodnim
1,8 V pinovima FPGA-a, bez seljenja banke. Pozadina: TASK-5039 (`litex-eth-ulx5m-gs-1g`, grana `linux-vexriscv-smp`,
`docs/SPI_SD_TASK-5039.md`): utor na CM5-IO-BASE-A ide izravno na banku NA (1,8 V), kartica traži VIH ≥ 2,06 V,
a GateMate dopušta VIN ≤ VDDIO + 0,4 V = 2,2 V. Autorica: Jelena.

## 1. Pinovi: Raspberry Pi SPI0 na 40-pinskom headeru J8 nosive ploče

Iz netlista (`tools/hardver/kicad_netlist.py`): `docs/sd/ulx5m-gs-hw_61b6709_netlist.json` (ULX5M-GS, ulx5m-gs-hw @ 61b6709)
i `docs/sd/cm5-io-base-a_netlist.json` (CM5-IO-BASE-A). CM4 GPIO2–27 su na ULX5M-GS na bankama **NA/NB**
(`VDD_NA` = `VDD_NB` = `SDRAM_VCC` = **1,8 V**), a nosiva ploča ih vodi **izravno** (bez otpornika) na header J8.
Pi SPI0 (GPIO8–11) je sav na banci NB i nije zauzet u np1817 (np1817 na NA/NB koristi samo serial GPIO4/GPIO5 i
SDRAM A1/A2/A10). Provjera: `python3 sim/test_sd_pins.py` (4 testa, uključujući „nitko drugi na mreži”).

| SD signal (SPI / SD) | FPGA pad | U4 kuglica | CM4 GPIO | J2 (ULX5M-GS) | **J8 (header)** |
|---|---|---|---|---|---|
| CLK / CLK | IO_NB_B3 | C11 | GPIO11 (SCLK) | J2.38 | **J8.23** |
| MOSI / CMD | IO_NB_B1 | C10 | GPIO10 (MOSI) | J2.44 | **J8.19** |
| MISO / DAT0 | IO_NB_A1 | D10 | GPIO9 (MISO) | J2.40 | **J8.21** |
| CS_N / DAT3 | IO_NB_B2 | A11 | GPIO8 (CE0) | J2.39 | **J8.24** |
| — / DAT1 (4-bit) | IO_NB_A2 | B11 | GPIO7 (CE1) | J2.37 | **J8.26** |
| — / DAT2 (4-bit) | IO_NB_A0 | B9 | GPIO25 | J2.41 | **J8.22** |

Napajanje:

| Što | Gdje | Napomena |
|---|---|---|
| **3,3 V** (strana kartice, VB/VCCB) | **J8.1** ili J8.17 | `+3.3v` nosive ploče = ULX5M-GS `+3V3` (J2.84/86) |
| **GND** | J8.6, J8.20, **J8.25** | |
| **1,8 V** (strana FPGA-a, VA/VCCA) | **nije na J8** | jedini 1,8 V na nosivoj ploči je `+1.8v` = CM5 pin 88/90 = ULX5M-GS `+1V8`; na CM5-IO-BASE-A ide samo na R4 (izbor `GPIO_VREF` 1,8 V, kratkospojnik VDD_IO). **Uzmi ga s 1,8 V nožice kratkospojnika VDD_IO (H1)** — prije spajanja **izmjeri 1,8 V prema GND**. Položaj kratkospojnika je svejedno: `GPIO_VREF` (J2.78) na ULX5M-GS nije spojen. Rezerva: mali LDO 1,8 V (XC6206P182MR) iz J8.1. |

VCCA ne mora biti ista tračnica kao `SDRAM_VCC`: pretvarač na A strani daje ≤ VCCA (1,8 V ± 2 % ≤ 2,2 V VIN max FPGA-a),
a prag mu je ~0,65 × VCCA ≈ 1,17 V, što FPGA (VOH ≈ 1,8 V) prelazi s rezervom.

## 2. Izbor dijela (dobavljivost provjerena 4. 10. 2026. preko pcbparts MCP-a: `mouser_get_part`, `jlc_search`)

NE: 74AHC125 / 74LVC125 / CD74HC4050 „Arduino SD” moduli — to su jednosmjerni spuštači 5 V → 3,3 V, ulaz im ne
prepoznaje 1,8 V. NXP **NVT4857UK** (preporuka AN13031) **nema na zalihi**: Mouser `NVT4857UKZ` 0 kom, LCSC ga nema.

| # | Rješenje | Linije | Dobavljivost / cijena | Ocjena |
|---|---|---|---|---|
| **1 (preporuka, odmah)** | **Adafruit 1875** (TXB0104 breakout, VA 1,2–3,6 V, VB 1,65–5,5 V, OE s 10 k pull-upom) + **Adafruit 4682** (microSD breakout „3V only”: bez pretvarača, 47 k pull-upovi na svim linijama — provjereno u Eagle shemi) | 4 (SPI) | Mouser `485-1875` **590 kom, 3,50 USD**; `485-4682` **786 kom, 3,50 USD** | gotovo, samo Dupont žice; SPI-SD odmah. 47 k pull-up je na granici TI-jeve preporuke za TXB (≥ 50 k) — za SPI do nekoliko MHz u redu |
| 2 (4-bit, gotovo) | **Adafruit 395** (TXB0108, 8 kanala) + Adafruit 4682 | 6 (+2 slobodne) | Mouser `485-395` **330 kom, 7,95 USD** | isto kao 1, plus DAT1/DAT2 za nativni LiteSDCard (`--sdcard native --sd-pins j8`); nativni na Linux SoC-u ne stane (TASK-5039: 77 % LT bez DVI/USB) |
| 3 (trajno, po specifikaciji SD 3.0) | vlastita mala pločica: **NVT4858HKZ** (SD pretvarač s auto-smjerom, EMI filtar + ESD, VCCA 1,08–1,95 V, VCCB 1,65–3,6 V) + **TF-01A** utor + XC6206P182MR (1,8 V) + ženski 2×13 konektor koji se natakne izravno na J8.1–26 | 6 | `NVT4858HKZ` LCSC **C3035811, 3 138 kom, 1,11 USD** (Mouser 105 436 kom, 1,09 USD), XQFN-16 0,4 mm → samo JLC PCBA; `TF-01A` **C91145**, 201 364 kom, 0,19 USD; `XC6206P182MR` **C21659** | najčišće, ali treba crtanje + narudžba PCBA |

Alternativni čip za opciju 3 ako se lemi ručno: `TXS0108EPWR` (TSSOP-20, VCCA 1,2–3,6 V, ugrađeni 10 k pull-upovi —
dobro za CMD/DAT) LCSC **C17206, 53 290 kom, 0,44 USD** (Mouser 141 kom); `TXB0106PWR` LCSC C38253 (7 719 kom).
NVT4858HKZ nožice (LCSC pinout): 1 DAT2A, 2 DAT3A, 3 DAT0A, 4 DAT1A, 5 CLKA, 6 CLK_FB, 7 GND, 8 CLKB, 9 DAT1B,
10 DAT0B, 11 DAT3B, 12 DAT2B, 13 CMDB, 14 VCCB, 15 VCCA, 16 CMDA.

**Preporuka: opcija 1** (gotovo, ~7 USD, bez lemljenja SMD-a); ako SPI-SD proradi, a želi se brzina/4-bit ili trajno
rješenje — opcija 3. KiCad shema minimalne pločice **nije rađena**: postoje gotovi moduli (uvjet iz zadatka „ako ništa
gotovo nema” nije ispunjen); na zahtjev crtam opciju 3.

### Spajanje — opcija 1 (Adafruit 1875 + Adafruit 4682)

| Od | Do | Do |
|---|---|---|
| izmjereni 1,8 V (kratkospojnik VDD_IO, nožica 1,8 V) | 1875 **VA** | — |
| J8.1 (3,3 V) | 1875 **VB** | 4682 **3V** |
| J8.25 (GND) | 1875 **GND** | 4682 **GND** |
| J8.23 (GPIO11) | 1875 **A1** → B1 | 4682 **CLK** |
| J8.19 (GPIO10) | 1875 **A2** → B2 | 4682 **SI** (CMD) |
| J8.21 (GPIO9) | 1875 **A3** → B3 | 4682 **SO** (DAT0) |
| J8.24 (GPIO8) | 1875 **A4** → B4 | 4682 **CS** (DAT3) |
| 1875 **OE** | ostaviti (10 k na VA = uključeno) | — |
| 4682 DET | nespojeno | — |

Za opciju 2 još: J8.26 (GPIO7) → A5 → B5 → 4682 **D1**; J8.22 (GPIO25) → A6 → B6 → 4682 **DAT2**.
Žice što kraće (< 10 cm), GND žica uz signalne. **Ništa od 3,3 V ne smije doći izravno na J8 GPIO pinove.**
Utor na nosivoj ploči ostaje prazan (kartica samo u vanjskom modulu).

## 3. Gateware (repo `ulx5m-gs-linux-sbc`, isti SoC kao np1817)

`gateware/target_soc.py --sd-pins {slot,j8}` (novo; zadano `slot` = dosadašnje ponašanje). Uz `j8`:

- `--sdcard spi`: `SPIMaster` na J8 pinovima, CSR ime **`spisdcard`** (BIOS driver i Linux `litex,litespi` + `mmc_spi` nepromijenjeni);
- `--sdcard native`: LiteSDCard na resursu `sdcard_j8` (6 linija);
- unutarnji pull-upovi (`PULLUP=true`) na MOSI/CMD, MISO/DAT0, CS_N/DAT3 (i DAT1/DAT2 kod nativnog), CLK bez pull-upa;
- pinovi u `gateware/sd_pins.py` (jedan izvor istine; `slot` i `j8`).

Testovi: `sim/test_sd_pins.py` (pinovi ↔ obje netliste, banka 1,8 V, slobodno u np1817), `sim/test_sd_gen.py`
(generirani `.ccf` i CSR mapa za `spi`/`native` na J8, stari utor nekorišten), regresija `sim/test_boot_option.py`.

Build (np1817 argumenti + SD; `--boot sdnet` = SD pa TFTP, bez kartice SPI-SD samo istekne, TASK-5039):

    OSS_CAD_SUITE=/home/klaudio/app/raid/tools/oss-cad-suite-20260928 \
    NEXTPNR=/home/klaudio/app/raid/tools/nextpnr-main-ad8527f/bin/nextpnr-himbaechel \
    tools/soc_build.sh sdj8_np1817_s1 --seed 1 --cpu-type vexriscv_smp --cpu-variant linux --sdram-clk inv \
        --with-gbe --eth-mode mac --boot sdnet --with-video --video-ce-rep --video-neg-sync --video-recover \
        --pll-lock-req 0 --with-usb-pnru --usb-pnru-clk pll48 --usb-pnru-freq 60e6 --sdcard spi --sd-pins j8

(`tools/sbc_env.sh` sada poštuje `OSS_CAD_SUITE` iz okoline; prije je uvijek postavljao 2026-09-23.)

Rezultati (4. 10. 2026., yosys 0.69+154 iz oss-cad-suite 2026-09-28, nextpnr `ad8527f8`):

| seed | CPE_LT | RAM_HALF | usb_clk (60) | ref_clk (125) | grx (125) | gtx0 | cpu (20) | ishod |
|---|---|---|---|---|---|---|---|---|
| **1** | **31 088 (75 %)** | **55 / 64** | 56,9 | 108,7 | 115,7 | 48,8 | 22,1 PASS | **bitstream** (preporučen) |
| 3 | 31 116 (75 %) | 55 | 52,3 | 114,8 | 113,1 | 46,6 | PASS | bitstream |
| 4 | 31 088 (75 %) | 55 | 46,8 | 90,0 | 123,1 | 47,0 | PASS | bitstream |
| 2 | — | — | — | — | — | — | — | router zapeo (`overused=1` nakon 1 561 iteracija), prekinut — kao np1817 seed 1 |

Usporedba s np1817 (`s_usb5_pll60_s2_np1817`): 30 855 LT / 50 RAM_HALF; SPI-SD na J8 košta **+233 CPE_LT i +5 RAM_HALF**.
post-route usb_clk np1817 = 61,2 MHz; ovdje najbolji 56,9 MHz (−5 %): nextpnr timing za gtx/grx ni ranije nije bio
mjerodavan (np1817 ref_clk 83 MHz FAIL, a radi), ali **USB tipkovnica je na ovom bitstreamu neprovjerena** do testa na ploči.

**Bitstream:** `bitstreams/ETH_GateMateA1_0410_Linux_GbE_DVI_USBPNRU_SDJ8_np1817s1.bit` (CFGRST, `gmpack --reset`),
sha256 `71004652c950fd5d41416411fa0483788829ef333f99858d58dbb685f2353cd5`; kopija na Piju `~/FPGA/` (sha provjeren),
DTB na Piju `/srv/tftp/rv32sdj8.dtb` (`dtc` rc 0, `fdtget /soc/spi@f0003800 compatible` = `litex,litespi`).
`.ccf`: `spisdcard_j8_clk` IO_NB_B3; `_mosi` IO_NB_B1, `_cs_n` IO_NB_B2, `_miso` IO_NB_A1 — sva tri `PULLUP=true`.
**Na ploču nije učitan** (čeka spajanje modula); ploča i dalje vrti np1817 iz flasha (ping Pi → 192.168.10.213 3/3).

### DTS i OpenSBI iz istog builda

    python3 tools/linux/mkdts.py build/s_sdj8_np1817_s2 --font 6x8 \
        --append "consoleblank=0 usbhostd=-v,-s,60 sbcdiag=0xf0002800" > tools/linux/rv32_sdj8_np1817_k612.dts

CSR mapa se pomaknula: `spisdcard` je na **0xf0003800**, a `usb_pnru` 0xf0003800 → **0xf0004000**, `video_fb2x` → 0xf0004800,
`video_vtg` → 0xf0005000. Zato **`rv32_k612.dtb` od np1817 NE vrijedi** za ovaj bitstream — treba `rv32_sdj8_np1817_k612.dts`
(razlika prema `rv32_usb5_pll60_s1_k612.dts`: samo `usbhost@f0004000` i novi čvor `litespisdcard0: spi@f0003800` s `mmc-slot@0`).
`usbhostd` adresu čita iz DT čvora; `sbcdiag` (`main_video_recoveries`) ostao je na 0xf0002800; UART 0xf0001000 isti.
OpenSBI: `opensbi612.bin` (Buildroot `fw_jump.bin`, sha256 `f2603c09…`) — isti skup kao np1817 (ovisi samo o UART-u i DT-u).
Kernel 6.12 (`linux-6.12/.config`): `SPI_LITESPI=y`, `MMC_SPI=y`, `MMC_BLOCK=y`, `MMC_LITEX=y`, `VFAT_FS=y`, `MSDOS_PARTITION=y`.

**SPI flash se ne dira**: u flashu ostaje np1817 (sha256 `dcf82c64…`, TASK-5224); test ide samo u SRAM (`fpga-jtag gs <bit> -r`).

## 4. HW test — tek kad Goran spoji modul

1. Goran: spoji po tablici iz §2, izmjeri VA = 1,8 V i VB = 3,3 V, umetne FAT32 karticu u modul.
2. Jelena (Pi): `dtc -O dtb -o /srv/tftp/rv32sdj8.dtb rv32_sdj8_np1817_k612.dts`; pa
   `IMAGE=Image612 SBI=opensbi612.bin bash lxrun.sh ~/FPGA/<SDJ8 bit> rv32sdj8.dtb rootfs612.cpio 900 "dmesg | grep -i mmc; cat /proc/partitions"`
   (lxrun.sh piše i vraća boot.json; `fpga-jtag gs <bit> -r`, bez gašenja ploče/huba, jedan čitač UART-a, dugi dio preko lab_watch).
3. BIOS: `--boot sdnet` sam pokuša SD (`sdcardboot`): očekivano bez `FatFs error 3`; bez boot.json na kartici prelazi na TFTP.
4. Linux: `mmc0: new SD card on SPI`, `mmcblk0`/`mmcblk0p1` u `/proc/partitions`, pa `mount -o ro /dev/mmcblk0p1 /mnt` (samo čitanje).
5. Ako kartica ne odgovara: ILA na J8 linijama — `SDPadProbe` (`gateware/sd_probe.py` iz TASK-5039) prebacuje se na `sd_pins["j8"]`
   u manjem SoC-u (bez DVI/USB) i broji bridove jezgra/pad za CLK/MOSI/CS_N/MISO. Bez tog dokaza se hardver ne proglašava pokvarenim.
6. Nakon testa ploča se vraća na np1817 (reset iz flasha ili `fpga-jtag gs …np1817.bit -r`), boot.json na Piju vraća lxrun.sh.
