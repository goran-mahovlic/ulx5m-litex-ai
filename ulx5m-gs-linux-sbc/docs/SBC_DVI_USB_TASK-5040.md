# ULX5M-GS kao samostalno računalo: DVI framebuffer + Linux fbcon + USB host (TASK-5040)

Datum: 25. 9. 2026. Autorica: Jelena (REGOČ). Grana `sbc-dvi-usb` (worktree `~/app/litex-eth-ulx5m-gs-1g-sbc`).
Nalog: Goran, 25. 9. 14:33 („SD što je logičnije; stane li DVI + framebuffer; stane li USB host"), redoslijed
prema uputama #44, #51, #55–#58 (konzola na ekranu → DOOM iz Linuxa → USB).

## 0. Sažetak

| Cilj | Stanje | Dokaz |
|---|---|---|
| DVI testna slika iz BIOS-a | ✅ **Goran potvrdio sliku (17:16), boje OK** | `ETH_GateMateA1_2509_1651_Linux_DVI_s1.bit`, `tools/dvi/testimg_cmds.sh` |
| Linux fbcon na DVI + 1G ETH u **jednom** SoC-u | ✅ na ploči: `simplefb registered`, `Console: switching to colour frame buffer device 40x30`, ping .213 3/3, `/proc/fb` = `0 simple`. Goran je vidio pingvina i konzolu (18:12), a HDMI capture snima kernel log. ⚠️ Slika ispada pod opterećenjem (§7) | `ETH_GateMateA1_2509_1732_Linux_GbE_DVI_s1.bit`, `tools/linux/rv32_gdvi_1.dts` |
| DOOM iz Linuxa na /dev/fb0 | ✅ 5,5 FPS na naslovnim ekranima, **1,7–1,8 FPS `-timedemo demo1`**; REGOČ je captureom vidio DOOM (18:24) | `tools/doom_linux/`, `/usr/bin/doom` u `rootfs_dvi.cpio` |
| USB host | ❌ **OHCI ne stane** (91 % LT uz DVI); prebuilt kernel ionako nema USB | §4 |
| SD | ⏸ SPI-SD (TASK-5039) je logična odluka i stane (+85 LT), ali kartica ne radi na banci od 1,8 V (J16) | §5 |

## 1. Hardver (točka 0)

- **DVI:** DDMI0 = TMDS na `IO_SB_A4…B7` (clk A7/B7, D0 A4/B4, D1 A5/B5, D2 A6/B6), README ploče: „DVI – tested and works" od v004.
- **USB-C J5 (shema `ethernet.kicad_sch`):** D+ = `USB25_P` → `IO_EA_A0` (i `IO_EA_A1` paralelno), D- = `USB25_N` → `IO_EA_B0` (`IO_EA_B1`), serijski 27 Ω.
  - `USB_PULL_P` = `IO_EA_A2`, `USB_PULL_N` = `IO_EA_B2`, preko dioda: visoka razina daje 1k pull-up (uređaj), niska daje 12k1 pull-down (host). To je isti spoj kao ULX3S US2.
  - CC1/CC2 imaju 5k1 prema masi (ploča se predstavlja kao uređaj).
  - **VBUS nije napajan s ploče** (`J5.VBUS` = samo konektor), pa tipkovnica treba vanjskih 5 V (napajani hub ili Y-kabel).
- **SPI flash** MX25R3235F = 4 MB: premalo za Linux (Image 7,5 MB + rootfs 3,8 MB).

## 2. DVI + framebuffer

**Zašto ne LiteX `VideoFrameBuffer` 640×480:** rgb565 traži 36,9 MB/s = 92 % vrha 16-bitnog SDRAM-a (40 MB/s na 20 MHz).
**`FrameBuffer2x` (`gateware/video_sbc.py`)** čita okvir 320×240 rgb565 (9,2 MB/s, 23 %) i u hardveru udvostručuje piksele i linije:
- parne izlazne linije dolaze iz DMA-a i upisuju se u line buffer 320×16 (1 RAM_HALF);
- neparne linije ponavljaju se iz line buffera.

Linux vidi običan `simple-framebuffer` 320×240 r5g6b5 na `0x43f00000` (zadnji MB RAM-a, `reserved-memory no-map`).
Testbench `sim/tb_scaler2x.py` provjerava piksel (X,Y) = okvir (X/2, Y/2), cjelovitost okvira i underflow, u oba načina (dva takta i CE):
**PASS, 11 okvira, 0 grešaka**.

**Izmjereno memspeedom (BIOS, VexRiscv-SMP):** bez videa 33,2/13,9 MiB/s (pisanje/čitanje); s framebufferom 27,9/10,5; s 1G i framebufferom 22,9/10,1.

### Globalne mreže: kako 1G + DVI stanu u 4 BUFG

- 1G troši sve 4 globalne mreže: `sys`, `gtx0` 125 MHz, TXC (`gtx90`) i `grx`.
- DVI s dva takta (hdmi 25 + hdmi5x 125) traži još 2.
- **Rješenje (commit 86a3033):** hdmi5x je isti takt kao `gtx0` (125 MHz). Cijeli video lanac (VTG, skaler, TMDS koderi, serijalizatori) radi u `gtx0` i napreduje samo kad je `ce` = 1, tj. jedan takt od pet (25 MHz). TMDS takt je 10-bitna riječ `0b0000011111` kroz isti serijalizator.
- **Zamka:** memorijski portovi nisu pod `CEInserter`-om. Write enable i read enable line buffera moraju slijediti `ce` (`Scaler2x.we_ce`), inače upis ponovi krivi piksel, a `dat_r` bježi jedan piksel naprijed. Sim je to uhvatio: 132 greške, nakon popravka 0.
- nextpnr javlja `gtx0` FAIL (48–68 MHz) jer piksel putove broji kao jednotaktne. Stvarni zahtjev za njih je 25 MHz. Kritična putanja (VTG `hcount`) je višetaktna.

## 3. Tablica izvedivosti (P&R, nextpnr-himbaechel, CCGM1A1; granica placera ≈ 71 % LT, J7)

| Build | CPE_LT | RAM_HALF | CC_BUFG | PLL | Takt (fmax) | Stane | Na ploči |
|---|---|---|---|---|---|---|---|
| Linux SMP + 1G MAC (polazište, smp8_9) | 22 644 (55 %) | 45 | 4 | 2 | sys 20,5 | ✅ | Linux 3/3 |
| SMP + DVI fb, bez ETH (dvi_1/3/9) | 23 566 (57 %) | 32 | 3 | 2 | sys 26,7, hdmi5x 166 | ✅ | ✅ slika potvrđena (s1) |
| SMP + DVI fb + SPI-SD (dvisd_1/9) | 23 957 (58 %) | 37 | 3 | 2 | sys 26,9, hdmi5x 128 | ✅ | nije učitano (SD ne radi, J16) |
| SMP + VideoTerminal (UART zrcalo), bez ETH (vt_1/9) | 20 471 (50 %) | 35 | 3 | 2 | sys 23,5, hdmi5x 144 | ✅ | nije učitano (fbcon proradio prvi) |
| **SMP + 1G MAC + DVI fb, CE u gtx0 (gdvi_1)** | **28 037 (68 %)** | **48** | **4** | 2 | sys 25,3 | ✅ | **✅ Linux + fbcon + ping (s1); s9 mrtav** |
| SMP + DVI fb + USB OHCI (Cdma, 48 MHz) | 37 535 (91 %) | 35 | 4 | 3 | – | ❌ placer: „Unable to find legal placement" | – |

- 48 MHz iz 25 MHz na GateMate PLL-u iznosi 47,917 MHz (−0,17 %; USB FS dopušta ±0,25 %).
- **gdvi seed 9** prošao je P&R (rc=0), ali na UART-u nema ni bajta. Seed 1 radi. Kvar ovisan o seedu treba provjeravati na ploči, ne samo po rc=0.

## 4. USB host: procjena

- SpinalHDL OHCI (`--with-usb`, kao linux-on-litex) sam dodaje ~14 000 LT i ~5 900 FF. S DVI-jem to je 91 % LT i placer odustaje. Bez DVI-ja bilo bi ~34 %+55 %, što je također iznad granice.
- Prebuilt kernel 5.14 nema USB podsustav (`strings Image`: nema ohci/usbcore). Za OHCI treba novi Buildroot kernel.
- **Preporuka:** umjesto OHCI-ja mali **hardverski USB HID (low-speed tipkovnica) host** koji pritiske tipki pretvara u ASCII i ubacuje ih u UART RX (npr. `nand2mario/usb_hid_host`, 12 MHz). Tipkovnica tada radi i u BIOS-u i u Linux konzoli bez ijedne promjene kernela. Treba 1 PLL + 1 globalnu mrežu (12 MHz): u buildu bez 1G ima mjesta (3/4 BUFG), a uz 1G+DVI nema (4/4), osim ako se 12 MHz izvede iz `sys` ili radi s CE-om.
- **HW:** 5 V na VBUS izvana (napajani hub). Pull-down ide na `IO_EA_A2/B2` = 0.
- **Emardov USB 1.1 HID host (uputa #61, `emard/ulx3s-misc` `examples/usb/usbhost` + `usb11_phy_vhdl`), samostalna sinteza `synth_gatemate` (GHDL za VHDL PHY, report 8 B):**
  - izmjereno: 590 LUT (201 LUT2 + 156 LUT3 + 229 LUT4 + 4 MX4) + 135 ADDF + 406 DFF, tj. **~725 CPE_LT (~1,8 %)**;
  - log: `~/.tmp/t5040/usbhid_synth.log`;
  - uz 1G+DVI (gtree 28 568 LT = 69,7 %) to je **~71,5 %**, na samoj granici placera; za rezervu treba maknuti dijagnostičke brojače (~3×32 bita) ili smanjiti BIOS ROM.
  - **Takt 6 MHz bez nove globalne mreže:** `gtx0` 125 MHz s CE 1/21 daje 5,952 MHz (−0,79 %, a USB LS dopušta ±1,5 %). CE mora biti stablo (K15).
  - **Most prema Linuxu:** kernel nema USB, pa `usbhidd` u userspaceu čita HID report iz CSR-a preko `/dev/mem` (kao `csrpeek`) i piše znakove u `/dev/tty1` preko ioctl `TIOCSTI`.
  - **Redoslijed (Goran #61):** tek kad je slika stabilna, a to čeka HW popravak VDD_PLL (§7).

## 5. SD: odluka

**Logično je SPI-SD (TASK-5039)**: +85 LT i +5 RAM_HALF, a bez kartice BIOS samo istekne i nastavi (J15). Uz DVI stane (dvisd, 58 %).
Kartica ipak ne odgovara na banci od 1,8 V (J16, Goranov test u 16:56 s nosivom pločom na 1,8 V: `FatFs error 3`, nema `mmcblk`).
Za DVI Linux se zato diže netbootom, što je omogućila kombinacija 1G + DVI (§2).

## 6. Kako ponoviti

```bash
# DVI testna slika (bez ETH):
tools/soc_build.sh dvi_1 --cpu-type vexriscv_smp --cpu-variant linux --with-video --boot serial --sdram-clk inv --seed 1
bash tools/sd/bios_cmds.sh <bit> $(bash tools/dvi/testimg_cmds.sh)            # na Piju kao fpga-klaudio
# Linux + 1G + DVI (fbcon):
tools/soc_build.sh gdvi_1 --cpu-type vexriscv_smp --cpu-variant linux --with-gbe --eth-mode mac --boot netboot \
    --with-video --sdram-clk inv --seed 1
python3 tools/linux/mkdts.py build/s_gdvi_1 > rv32dvi.dts; dtc -O dtb -o /srv/tftp/rv32dvi.dtb rv32dvi.dts   # Pi
~/FPGA/netboot_app.sh linuxdvi; APP=linuxdvi bash tools/linux/linux_boot.sh <bit> 330
# na ploči: setsid getty 38400 tty1 &   (login prompt na DVI-ju)
```

Bootargs: `fbcon=font:VGA8x8 console=tty0 console=liteuart …`, tj. 40×30 znakova. `/dev/console` ostaje UART (nema tipkovnice).
Kernel se diže ~90 s umjesto ~25 s, jer fbcon za svaki redak loga scrolla 150 KB framebuffera kroz SDRAM.

## 7. Stabilnost slike: korijenski uzrok je napajanje PLL-a (mjereno HDMI captureom)

Mjerenje: MS2109 capture na Piju (`http://192.168.10.14:8090/snap.jpg`).
- Niz snimaka (`~/.tmp/t5040/idle_series.sh`): jednolično `070707` znači da capture nema signala, a `000000` je crna slika uz ispravan signal.
- CSR brojači u FrameBuffer2x i u `ref` domeni (brojači padova PLL locka) čitaju se preko `csrpeek` (Linux) i `mem_read` (BIOS).

| Test | Bez signala |
|---|---|
| DVI_s1 (2 takta, bez 1G), BIOS mirovanje | 0/45 |
| DVI_s1, BIOS `mem_test` (puno opterećenje SDRAM-a) | 16/30 |
| 2 takta + SDRAM `DRIVE=6` mA, `mem_test` | 16/16 tijekom testa |
| 2 takta + deterministički load serijalizatora, `mem_test` | 16/16 tijekom testa |
| 2 takta + PLL SPEED, `mem_test` | 13/40 |
| 1G+DVI, jedan CE (gdvi_1), Linux boot | 36/40 |
| 1G+DVI, CE po bloku (gcer_1 / gneg_1 / gtree_3), Linux boot | 5/48, 4/60, 8/60 |
| 1G+DVI (gneg_1), Linux u mirovanju | 0/30 |
| 1G+DVI (gneg_1), DOOM | 2/30 |

**Odlučujuće mjerenje (dvipll_1, brojači padova `USR_PLL_LOCKED`, brojeni u `ref` domeni bez PLL-a):**
- u mirovanju sys PLL +0 i video PLL +0 kroz 30 s;
- nakon `mem_test` od 8 MB sys PLL **+3787**, video PLL **+2665**;
- nakon drugog `mem_test`: +3539 / +2439;
- nakon toga u mirovanju opet +0.

**Pod SDRAM opterećenjem oba PLL-a gube lock tisućama puta.** Video PLL tada daje nestabilan takt pa sink izgubi sinkronizaciju, a sys PLL objašnjava i jedan neobjašnjeni reset SoC-a za vrijeme Linuxa.

**Shema (`power.kicad_sch`):** `VDD_PLL` (U4.P16) dobiva `VDD_CORE` samo preko **R23 = 1 Ω** (0603) i **C42 = 100 nF** (0402); ferit **L5 je DNP**. Filtar VDD_PLL (1 Ω / 100 nF, ~1,6 MHz) ne guši šum jezgre koji nastaje pri SDRAM prometu.
*(Ispravljeno u Kosjenkinoj reviziji, §8: `VDD_SER_PLL` NEMA ferit — L6 i L7 su također DNP, pa SerDes PLL ima isti filtar R105 1 Ω + C127 100 nF.)*

**Preporuka (HW), ispravljena u §8:** L5 **nema footprinta na PCB-u** (ni L6/L7), pa se „zalemiti L5" ne može izvesti. Izvedivo je:
- **korak A (reverzibilan, bez skidanja dijelova):** 10 µF keramički od **TP6** (testna pločica Ø1 mm na mreži VDD_PLL) do najbliže mase. Uz postojeći R23 to daje RC niskopropusni filtar na ~16 kHz, prigušen pa bez LC rezonancije;
- **korak B (samo ako A ne pomogne):** R23 (0603) zamijeniti feritom MPZ1608 (0603, isti otisak), uz zadržani 10 µF;
- provjeriti VDD_CORE pod opterećenjem.

Gateware to ne može popraviti; može samo smanjiti opterećenje, a DRIVE i drugi načini učitavanja u serijalizator ništa ne mijenjaju.

Usput popravljeno u 1G+DVI (CE) načinu, što je potrebno ali nije dovoljno:
- CE stablo (13 CE registara);
- registriran `ready` prema CDC FIFO-u.

nextpnr detaljni timing i dalje pokazuje jednotaktne CE putove od 9,5–11,5 ns, jer `set_false_path -from/-to` u nextpnr-himbaechel „ne radi ništa (još)", pa placer ne vidi koji su putovi stvarno kritični.

## 8. Revizija (Kosjenka, 25. 9. 2026., dorada TASK-5043)

Neovisno provjereno: shema/PCB `~/app/ulx5m-gs-hw/hardware` (commit 61b6709) alatom `kicad_netlist.py`, reset put u `gateware/crg.py` i testbench `sim/tb_scaler2x.py` (oba načina PASS, 11 okvira, 0 grešaka).

**Ispravci §7:**

| Tvrdnja | Nalaz | Dokaz |
|---|---|---|
| „SerDes PLL ima ferit MPZ1608 (L6)" | ❌ L6 i L7 su `dnp yes`, a SerDes PLL ima isti filtar R105 1 Ω + C127 100 nF | `kicad_netlist.py --net VDD_SER_PLL`; `(dnp yes)` u power.kicad_sch |
| „zalemiti L5" | ❌ L5, L6 i L7 nemaju footprint na `ulx5m-gs.kicad_pcb` (na PCB-u su samo L1–L3); R23 je paralelno L5, 0603 | grep `Reference "L5"` u .kicad_pcb = 0 pogodaka |
| VDD_PLL = VDD_CORE preko R23 1 Ω + C42 100 nF | ✅ točno; na istoj mreži je i TP6 (Ø1 mm), što je prirodno mjesto za zakrpu | `--net VDD_PLL`: C42, L5, R23, TP6, U4.P16 |

**Odbačena alternativna hipoteza (gateware):** padovi `USR_PLL_LOCKED` NE resetiraju video i sys domenu. `_pll_reset` ide preko `StickyLock` (1 ms stabilno, zatim zauvijek 1), pa uzrok ispada nije lažni reset iz trzanja lock zastavice, nego sam takt.

**Diskriminacijski eksperiment (jedna promjena, isti test):**
1. ploča kakva jest: `dvipll_1`, BIOS `mem_test` 8 MB → brojači sys/video (referenca: +3787/+2665);
2. korak A (10 µF na TP6) → isti test;
   - brojači padnu za red veličine ili više: potvrđen uzrok VDD_PLL, pa zatim DVI ispadi captureom (cilj 0/30 pod `mem_test`);
   - brojači se ne promijene: uzrok nije lokalni filtar PLL-a, nego VDD_CORE (propad jezgre) ili ulazni takt clk25. Tada se mjeri VDD_CORE osciloskopom na TP-u jezgre, a ferit (korak B) se preskače.

**Proračun za USB tipkovnicu (§4), provjeren:** 28 568 + ~725 = 29 293 CPE_LT od 40 960 = 71,5 %. To je točno na granici placera (J7), a ne ispod nje. Prije ugradnje treba osloboditi ≥ 800 LT, npr. maknuti dijagnostičke brojače iz FrameBuffer2x i `ref` domene kad stabilnost bude potvrđena. `TIOCSTI` most radi na kernelu 5.14 (ograničenje `LEGACY_TIOCSTI` stiglo je tek u 6.2).

**Preporuka redoslijeda:** HW korak A → isti mjerni test → (ako prođe) HID host s oslobođenim LT → `usbhidd` → login na `tty1`. Zadatak pripada projektu ULX5M-GS, ne pretincu PRJ-033.

## 9. Revizija (Dora, 25. 9. 2026., dorada TASK-5044): drugi put šuma i Goranove primjedbe o slici

### 9.1 Šum SDRAM-a ima i drugi put do PLL-a: +1V8 → oscilator i ulaz takta

§7 i §8 gledaju samo put VDD_CORE → VDD_PLL. Netlista pokazuje drugi, jednako izravan put (`kicad_netlist.py`, `~/app/ulx5m-gs-hw/hardware`):

| Čvor | Spoj | Dokaz |
|---|---|---|
| SDRAM_VCC (U10 VDD+VDDQ, FPGA banke **WB, WC, NA, NB** = svi SDRAM pinovi) | **R116 = 0 Ω na +1V8** (R115 DNP) | `--net SDRAM_VCC`, `--ref R116`, vrijednost `0R` u gpio.kicad_sch |
| Oscilator **Y1** 25 MHz (ASE2-25.000MHZ, CLK_25MHz → `IO_SB_A8`) | pinovi 1 i 4 **izravno na +1V8**, bez R/ferita | `--ref Y1` |
| **VDD_CLK** (U4.T14) | +1V8 | `--net '^\+1V8$'` |
| VDD_SB (banka ulaza clk25 i TMDS izlaza) | +1V8 preko **R122 = 4R7** | `--net '^\+1V8_SB$'`, `--ref R122` |
| +1V8 izvor | TLV62569 → L1 → R10 0R | `--net 'N\$0075'` |

**Tri hipoteze s istim simptomom (oba PLL-a gube lock pod `mem_test`):**

| | Put | Što predviđa | Pomaže li korak A (10 µF na TP6)? |
|---|---|---|---|
| P1 | VDD_CORE → VDD_PLL (R23 1 Ω / C42 100 nF) | padovi prate **aktivnost** jezgre i kontrolera, gotovo neovisno o podacima | da |
| P2 | +1V8 (struja SDRAM DQ/VDDQ) → Y1 i VDD_CLK → **jitter ulaznog takta** za sve PLL-ove | padovi prate **promjene podataka na DQ**: slučajni podaci ≫ konstantni | **ne** |
| P3 | propad VDD_CORE na regulatoru | kao P1 | ne |

**Postojeći podaci ne isključuju P2:**
- `DRIVE=6` mA (16/16) mijenja samo FPGA izlaze pri pisanju, ne i SDRAM izlaze pri čitanju ni struju VDDQ čipa.
- Mirovanje daje +0 iako TMDS stalno mijenja stanje na banci SB. To isključuje stalno preklapanje, ali ne i prijelazna opterećenja od SDRAM prometa.
- Oba PLL-a gube lock istodobno i u sličnom omjeru (+3787 / +2665). To se slaže i sa zajedničkim VDD_PLL i sa zajedničkim ulazom clk25, pa ne razlikuje P1 od P2.

**Pokus koji razlikuje P1 i P2 bez lemljenja:** `tools/dvi/pll_discriminator.sh` (bitstream `dvipll_1`, sha256 `b59afe0d…`).
- Na istih 32 MiB i s istim brojem SDRAM naredbi mijenja se samo sadržaj na DQ:
  - `mem_write` s konstantom 0 i s konstantom 1 (DQ statičan);
  - `crc` preko konstantnih podataka;
  - `mem_test` (LFSR podaci);
  - `crc` preko LFSR podataka;
  - ponovljeni `mem_write` s 0 kao provjera ponovljivosti.
- Nakon svakog koraka čitaju se brojači `0xf0002000`/`0xf0002004`, a skripta ispisuje delte po koraku.
- Parser je provjeren na Jeleninom UART zapisu (`lt_dvild_1`: 0x0632 / 0x051c) i na sintetičkom nizu (delta 3787 / 2665 točna).

Tumačenje:
- **WR ≫ W0/W1 i RX ≫ R1:** vrijedi P2. Korak A tada neće pomoći, a HW zakrpa ide na napajanje Y1: presjeći vodove prema +1V8 na pinovima 1 i 4 i umetnuti 10 Ω + 10 µF (RC ~1,6 kHz; pad = 10 Ω × I_DD oscilatora, za nekoliko mA to je desetak do nekoliko desetaka mV, a I_DD treba potvrditi u datasheetu ASE2). Uz to dodati veći kondenzator na +1V8 kod U10.
- **W0 ≈ W1 ≈ WR i R1 ≈ RX:** vrijedi P1 ili P3, pa korak A iz §8 ostaje ispravan prvi potez.
- Pokus traje ~5 min, ne traži Gorana, pa ga treba pokrenuti **prije** lemljenja. Tako se TP6 zakrpa radi samo ako je P1 potvrđen.

### 9.2 Goranove primjedbe o slici (16:13): pingvin, velika slova, strogi monitor

| Primjedba | Uzrok | Rješenje | Cijena |
|---|---|---|---|
| Pingvin u gornjem lijevom kutu | kernel logo | bootarg **`logo.nologo`** (niz postoji u `Image`, `strings`) | 0: samo `boot.json`/bootargs |
| Vrlo velika slova | namjerno: okvir 320×240, font VGA8x8, ×2 skaler → 16×16 px po znaku, 40×30 znakova | (a) **640×240 s udvostručenjem samo po vertikali**: 80×30 znakova, svaki 8×16 px (izgled VGA tekstualnog načina); DMA 640·240·2·60 = **18,4 MB/s (46 % vrha)**. (b) Novi kernel s fontom MINI4x6/6x8 (prebuilt 5.14 ima samo VGA8x8 i VGA8x16, K19). | (a) udvostručuje SDRAM promet framebuffera, a upravo on izaziva padove locka, pa ide **tek nakon** stabilizacije (§9.1). (b) Buildroot rebuild, koji treba i za OHCI. |
| „Monitor strog s 640×480@60" | u 1G+DVI (CE) načinu piksel takt je `gtx0`/5 = **25,000 MHz**; VESA traži 25,175 MHz (**−0,70 %**, izvan tipične ±0,5 %), pa je H = 31,25 kHz i V = 59,52 Hz | nije uzrok ispada: BIOS slika DVI_s1 bila je stabilna (17:16), a ispadi prate SDRAM opterećenje (§7). Točnih 25,175 MHz nema dok je video vezan za 125 MHz `gtx0`. | informativno; ako monitor odbija i u mirovanju, provjeriti na drugom monitoru ili HDMI captureu |

### 9.3 Preporučeni redoslijed (ispravak §8)

1. `tools/dvi/pll_discriminator.sh` (bez Gorana) → P1 ili P2.
2. Ako P1: korak A (10 µF na TP6). Ako P2: RC filtar za Y1 i veći kondenzator na +1V8.
3. Ponoviti isti pokus i niz snimaka HDMI capturea (cilj 0/30 pod `mem_test`).
4. Odmah, neovisno o 1–3: dodati `logo.nologo` u bootargs.
5. Nakon stabilizacije: oslobađanje LT (§8), HID host, a po želji način 640×240.

**Stanje ove dorade:** Pi (`192.168.10.14`) od 20:52 CEST ne odgovara ni na SSH ni na capture (`Connection timed out`), pa pokus 9.1 **nije pokrenut na ploči**. Stanje ploče je nepromijenjeno (Jelenino, TFTP `linux`).
