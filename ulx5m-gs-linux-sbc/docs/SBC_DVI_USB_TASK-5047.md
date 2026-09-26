# ULX5M-GS SBC: PLL lock pod SDRAM opterećenjem — timing ili napajanje? (TASK-5047)

Datum: 25. 9. 2026. Autorica: Jelena (REGOČ). Grana `sbc-dvi-usb`, nastavak `docs/SBC_DVI_USB_TASK-5040.md` §7–§9.
Nalog: Goran, 21:15 — sumnja na loše timinge (na rubu), traži reviziju SDRAM dizajna; USB tipkovnica; preglednija konzola.
Pi `192.168.10.14` do ~21:50 CEST nije odgovarao (ssh timeout), pa su prvi sati bili analiza i buildovi. Nakon toga sve je
**izmjereno na ploči** (§2.2, §2.3). U `dmesg` Pija ima 599× `Under-voltage detected`, što je korisno uz Goranovu provjeru napajanja.

## 1. Odgovor na hipotezu o timingu

**Kratko:** gubitak locka ne dolazi od timinga logike ni od SDRAM timinga. Ipak postoji gateware uzrok koji
pojačava učinak šuma: **LiteX ostavlja `LOCK_REQ=1`, a uz to CC_PLL isključuje izlazni takt svaki put kad lock padne.**

### 1a. Je li brojač padova ispravan? (CDC, glitch, usporedba s LOCKED_STDY)

| Pitanje | Nalaz | Dokaz |
|---|---|---|
| Može li brojač izmisliti padove? | Ne. Sirovi `USR_PLL_LOCKED` ide kroz `MultiReg` (2 FF) u `ref` domenu (clk25 s pina, bez PLL-a); broji se padajući brid sinkroniziranog signala. Metastabilnost može pomaknuti brid za jedan takt, ali ne može stvoriti novi. | `gateware/target_soc.py` (brojači), mirovanje +0 kroz 30 s (§7 TASK-5040) |
| Broji li sve padove? | Ne, to je **donja granica**: padovi kraći od 40 ns ne vide se, a nizovi se stapaju u jedan. | isto |
| CDC prema CPU-u | 16-bitni binarni brojač prelazi u sys kroz `MultiReg`; tijekom brojanja čitanje može biti poderano. Čitanja su rađena nakon opterećenja (brojač miruje), pa su vrijednosti 3787/2665 valjane. | `lt_dvild_1/uart.txt`: 0x0632/0x051c |
| LOCKED_STDY | LiteX ga ostavlja nespojenog. **Sada je spojen**: `gateware/pll_stdy.py` (`GateMatePLLStdy`), CSR `pll_stdy` (bit i = PLL i, 1 = lock nijednom nije pao od zadnjeg re-arma) i `pll_stdy_rst`. Po DS1001 sl. 2.33 STDY pada i ostaje 0 na svaki gubitak locka u samom siliciju, neovisno o uzorkovanju. | elaboracija: `.USR_PLL_LOCKED_STDY (…locked_stdy)`, `csr.csv` 0xf0002008/0xf000200c |

### 1b. Zašto padovi ruše sliku: `LOCK_REQ` (DS1001, tablica 2.19)

| CLK_OUT_EN | LOCK_REQ | PLL_LO | izlaz |
|---|---|---|---|
| 1 | 0 | X | ✓ radi |
| 1 | **1** | **0** | ✗ **isključen** |

`litex/soc/cores/clock/colognechip.py` postavlja `p_LOCK_REQ = 1` (default). **Svaki od izmjerenih ~3800 padova locka
zato znači rupu u sys i video taktu**, a ne samo zastavicu koja trepće. TMDS takt stane pa sink izgubi sinkronizaciju.
U sys domeni stane CPU, a nepredvidiv prekid takta objašnjava i povremeni reset SoC-a.

Mogući mehanizam pozitivne povratne veze: padne lock → takt stane → SDRAM promet stane → šum nestane → lock se vrati
→ promet krene → … Tisuće padova po `mem_test`-u odgovaraju takvom titranju.

**Popravak bez lemljenja:** `--pll-lock-req 0`. PLL tada daje takt i dok detektor locka trepće; kratki fazni poremećaj
znači jitter, ali ne i nestanak takta. Buildovi `dvistdy_1` → `dvilr0_1` razlikuju se u **točno 4 bajta** bitstreama
(`cmp -l | wc -l` = 4) uz identičan placement i timing, pa je A/B čist.

### 1c. SDRAM timing revizija (IS42VM16320E-75, 1,8 V, sys 20 MHz, CL=2, `--sdram-clk inv`)

| Parametar | Spec (-75) | LiteDRAM @20 MHz | Rezerva |
|---|---|---|---|
| tRCD / tRP | 22,5 ns | 1 ciklus = 50 ns | 27,5 ns |
| tRAS | 45 ns | 1 ciklus = 50 ns | 5 ns |
| tRFC | 80 ns | 2 ciklusa = 100 ns | 20 ns |
| tWR | 15 ns | 1 ciklus = 50 ns | 35 ns |
| **tREFI** | 64 ms/8192 = 7812,5 ns | **157 ciklusa = 7850 ns** (LiteDRAM zaokružuje NAVIŠE) | **−0,5 %, izvan specifikacije** → ispravljeno na 7,6 µs (152 ciklusa) |
| CL | 2 (≤ ~100 MHz) | 2 @ 20 MHz | velika |
| Pisanje (inv takt) | tIS ~1,5–2,5 ns / tIH ~1 ns | FPGA pokreće na sys↑, SDRAM uzorkuje 25 ns kasnije | setup ≈ 25 − tco(3–8) ≥ 17 ns; hold ≈ 25 ns |
| Čitanje | tAC(CL2) ≤ ~8 ns, tOH ≥ 2,5 ns | podatak valjan od +33 do +77,5 ns nakon SDRAM↑, FPGA uzorkuje na sys↑ = +25 ns nakon njega (+1 ciklus) | ~15–25 ns na obje strane |

- Pri 20 MHz SDRAM radi s rezervom od 5 do 35 ns na svakom parametru. Jedina greška je tREFI (+0,5 %), bez utjecaja na PLL.
- SDRAM timing greška pokazala bi se kao **greška podataka**, ne kao pad locka. Izmjereno je suprotno: pri bootu je brojač
  već bio na 0x632 (1586 padova), a boot `Memtest OK`. Linux i DOOM rade (TASK-5040).
- nextpnr timing (sys domena, post-route): kritični put je **unutar CPU-a** (VexRiscv barrel shifter, 47,4 ns = 7,9 ns
  logike + 39,6 ns rutanja, u `glr0_1`), a ne u SDRAM PHY-u.

### 1d. Seed sweep s timing reportom

Post-route Fmax (nextpnr-himbaechel `--freq 125` za sve domene; stvarni zahtjevi: sys 20, hdmi/ref 25, pixel putovi u gtx0 = 25 MHz s CE, grx 125).

| Build | Seed | CPE_LT | sys (≥20) | hdmi5x/gtx0 | grx (≥125) | Napomena |
|---|---|---|---|---|---|---|
| dvistdy_1 (= dvilr0/dvislew/dvipix) | 1 | 24 434 (59,7 %) | 22,20 | hdmi5x 131,98 ✅ | – | 2 takta, BIOS |
| dvis16_1 (sys 16 MHz) | 1 | 24 201 | 22,44 (≥16) | 160,85 ✅ | – | |
| gref_1 (= glr0_1) | 1 | 28 605 (69,8 %) | 21,04 | gtx0 63,3 (CE) | 139,26 ✅ | 1G+DVI, kandidat |
| glr0_3 | 3 | 28 605 | 24,63 | 59,3 | **104,96 ❌** | RX može pasti |
| glr0_5 | 5 | 28 605 | 23,58 | 54,9 | **123,18 ❌** | rub |
| glr0_9 | 9 | 28 605 | 24,98 | 53,3 | **90,04 ❌** | |
| gneg_1 (na ploči) | 1 | 28 037 | 25,84 | 54,0 | **102,55 ❌** | referenca TASK-5040 |

- **sys ima pozitivnu rezervu u svim seedovima** (21,0–25,0 MHz uz zahtjev od 20 MHz), a hdmi5x u 2-taktnom buildu prolazi (132 MHz).
- Seed mijenja `grx` (RGMII RX, 1G), a ne video ni SDRAM. Timing padovi `grx` pogađaju Ethernet, ne PLL lock.
- `hdmi_clk`/`ref_clk`/`gtx0` FAIL u izvještaju je lažan (ograničeni su na 125 MHz, a rade na 25 MHz ili s CE).
- Timing logike nema mehanizam kojim bi srušio analogni lock detektor. PLL vidi samo clk25 na ulazu i napajanje.

**Zaključak za Gorana:** timing nije uzrok. Uzrok je analogni (šum napajanja ili jitter ulaznog takta, §9.1 TASK-5044, P1/P2),
a `LOCK_REQ=1` svaki trzaj detektora pretvara u nestanak takta. Prvi potez bez lemljenja je `LOCK_REQ=0`, drugi je diskriminator P1/P2.

## 2. Gateware ublažavanje: jedna promjena po buildu

Svi 2-taktni BIOS buildovi imaju isti seed (1) i iste argumente; mijenja se samo navedeno.

| Build | Promjena | Bitstream vs. referenca | Padovi locka pod `mem_test` | Ispadi slike | Stanje |
|---|---|---|---|---|---|
| `dvistdy_1` | referenca (+ STDY CSR, samo opažanje) | sha256 `38353a26…` | ref. ≈ +3787/+2665 (dvipll_1) | ref. 16/30 | čeka Pi |
| `dvilr0_1` | `--pll-lock-req 0` | 4 bajta razlike | ? | ? | **čeka Pi, najveći očekivani učinak** |
| `dvislew_1` | `--sdram-slew slow` | **bit-identičan referenci** | = ref. | = ref. | **nema učinka:** SDRAM izlazi su već SLOW (nextpnr `.txt`: 42× `GPIO.SLEW 1`, jedini `SLEW 0` = `sdram_clock` s eksplicitnim `SLEW=fast`), vidi §2.1 |
| `dvidrv6_1` (TASK-5040) | `--sdram-drive 6` | – | – | 16/16 | izmjereno ranije: ne pomaže |
| `dvis16_1` | sys (= SDRAM) 16 MHz umjesto 20 | drugačiji placement | ? | ? | čeka Pi |
| `dvipix_1` | piksel 25,175 MHz (VESA) umjesto 25,000 | `OUT_CLK 125.875` | ? | ? | čeka Pi (za strogi monitor) |
| „PLL ref s drugog izvora" | – | – | – | – | **nije moguće**: jedini takt na ploči je Y1 25 MHz (`IO_SB_A8`); RXC od PHY-a (125 MHz) postoji tek nakon linka i izveden je iz istog Y1 (PHY XI = clk25, `gateware/crg.py`) |
| „manji burst/refresh vrhovi" | – | – | – | – | GENSDRPHY je SDR 1:1 bez burst-a (BL=1). Refresh je jedan AREF svakih 7,6 µs i ne daje vrh; LiteDRAM refresh postponing (`tREFI`×N) bi vrhove samo **povećao** |

### 2.1 SLEW
`SLEW=slow` u CCF-u prihvaćen je bez upozorenja (nextpnr javlja `Unknown value … for SLEW` za neispravne vrijednosti), a konfiguracija je
nepromijenjena. Kontrolni build `dvifast_1` (`--sdram-slew fast`) u nextpnr `.txt` daje **39× `GPIO.SLEW 0`** i 4× `SLEW 1`, a default
i `slow` daju 42× `SLEW 1`. **SDRAM izlazi su dakle već SLOW (default)** i ta mjera ne postoji.

### 2.2 IZMJERENO: LOCK_REQ A/B na 1G+DVI (BIOS, isti placement, razlika 4 bajta)

2-taktni buildovi ovog kruga (`dvistdy/dvilr0/dvislew/dvipix/dvis16`) **ne pokreću CPU** (nema UART-a, stari `dvipll_1` na istoj ploči
radi). nextpnr ih prijavljuje s **hold prekršajem u sys domeni** (clk-skew −3,89 ns, BRAM icache → FF). Stari buildovi i svi 1G buildovi
imaju 0 hold prekršaja. A/B je zato rađen na ciljnoj 1G+DVI jezgri: `gref_1` (LOCK_REQ=1) i `glr0_1` (LOCK_REQ=0), isti seed i placement.

Postupak (`~/.tmp/t5047/ab2.sh`): BIOS → testna slika → re-arm STDY → 20 s mirovanja → 2× `mem_test` 32 MiB uz 30 snimaka (4 s) → brojači.

| | `gref_1` LOCK_REQ=1 | `glr0_1` LOCK_REQ=0 |
|---|---|---|
| mirovanje 20 s: sys / tx padovi, STDY | +0 / +0, STDY 0x3 | +0 / +0, STDY 0x3 |
| 2× `mem_test` 32 MiB: sys / tx padovi | **+10 288 / +55 694** | **+1942 / +49 909** |
| STDY nakon opterećenja | 0x0 (oba PLL-a izgubila lock u siliciju) | 0x0 (isto) |
| snimke pod opterećenjem | **0/30 ispravnih** (13 bez signala, ostale crne) | **30/30 ispravnih** (testna slika) |
| FB underflow / resync | 0 / **17 900** (crno i nakon opterećenja) | **0 / 0** |
| `Memtest` | OK | OK |
| 1. kraće mjerenje (16 MiB, 6 snimaka) | sys +5398, tx +45 327, 4/6 bez signala, underflow 236k | sys +387, tx +42 105, **6/6**, underflow 0 |

**Zaključci:**
1. Lock detektor pod SDRAM prometom trepće u oba slučaja (tisuće padova, a STDY u siliciju pada), pa **šum/jitter stvarno postoji**. Timing logike tu ne igra ulogu.
2. Uz `LOCK_REQ=1` svaki pad je rupa u taktu → slika nestaje. **Uz `LOCK_REQ=0` slika ostaje stabilna pod punim opterećenjem.**
3. `mem_test` prolazi u oba slučaja: SDRAM podaci su ispravni (1c).

### 2.3 Drugi kvar: video put u CE načinu nema reset (trajna crna slika)

- `cd_gtx0` u `SoCCRG` nastaje s `with_reset=False` i bez `AsyncResetSynchronizer`-a. CE brojači (13), VTG i video strana CDC FIFO-a
  zato se **nikad ne resetiraju** nakon konfiguracije.
- Kad se nakon poremećaja takta razmaknu, stanje ostaje trajno: **resync na svakom okviru, underflow 0, crna slika uz ispravan sync**.
  Restart DMA (`dma_enable` 0→1, resetira i scaler) to ne popravlja (izmjereno).
- Viđeno u `gref_1` nakon opterećenja (17 900 resyncova) i u **jednom od dva Linux boota `glr0_1`** (14 697 resyncova na 14 706 okvira,
  60/60 crnih snimaka). Drugi boot bio je 0/60 bez signala, s konzolom vidljivom cijelo vrijeme.
- **Popravak (`--video-recover`):** domena `vid` (isti gtx0 takt, bez nove BUFG) s resetom `~lock_tx | vrst` i `vsys` (sys takt) za CDC
  write stranu. `ResyncWatchdog` u FrameBuffer2x: 4 uzastopna resynca bez dobrog okvira → 128 sys ciklusa reseta cijelog video puta.
  CSR `main_video_recoveries` broji oporavke. Test `sim/tb_watchdog.py`: 4/4 PASS.

### 2.4 IZMJERENO: `grec_3` = LOCK_REQ=0 + `--video-recover` (preporučeni build)

`ETH_GateMateA1_2509_2330_Linux_GbE_DVI_lr0_rec3.bit` (seed 3: 0 hold, sys post-route 22,39 MHz, grx 143 MHz PASS, 29 124 LT = 71,1 %).

| Test | Rezultat |
|---|---|
| BIOS, 2× `mem_test` 32 MiB, 30 snimaka | **30/30 ispravnih**, underflow 0, resync 0, oporavaka 0; sys +8930 / tx +43 333 padova detektora; Memtest OK |
| Linux netboot, 80 snimaka tijekom boota (240 s) | **80/80 ispravnih** (bez crnih i bez ispada); fbcon bez pingvina (`logo.nologo`) |
| Linux, 19 min rada | okvira 72 805, **underflow 0, resync 0**, oporavaka 0 |
| DOOM `-timedemo demo1`, 25 snimaka | 21 slika + 4 crne na prijelazu konzola → DOOM (DOOM pri startu briše ekran; sljedeće snimke prikazuju igru); tijekom samog DOOM-a (drugi niz) **30/30 ispravnih** (`gneg_1`: 2/30 ispada) |

Usporedba s dosadašnjim stanjem (TASK-5040, isti monitor/capture): `gdvi_1` 36/40 ispada pri bootu, `gneg_1` 4/60 pri bootu i 2/30 uz DOOM,
DVI_s1 16/30 pod `mem_test`.

**Linux boot je spor i varira** (raspakiravanje initramfsa 63–156 s, login za 226 s do ~10 min). Uzrok nije mjeren. Poznato je (TASK-5040)
da fbcon za svaki redak scrolla 150 KB kroz SDRAM. Zamka u testu: `mem_test` na 0x41000000 ostavlja LFSR podatke u initrd prozoru, pa je
kernel iza 8,4 MB cpio-a nailazio na smeće (`Initramfs unpacking failed: invalid magic`) i zapeo. Zato je rootfs nadopunjen nulama do 12 MiB
(`rootfs_hid.cpio` na TFTP-u).

## 3. Mjerenje (skripte)

```bash
tools/dvi/mitigation_sweep.sh dvistdy_1 dvilr0_1 dvis16_1 dvipix_1     # ~6 min po buildu
cat ~/.tmp/t5047/sweep_table.txt
```
Po buildu: testna slika → brojači + STDY → re-arm STDY → 2× `mem_test` 32 MiB (paralelno 40 snimaka capturea) → brojači + STDY.
Redak: `sys_unl +N  2nd_unl +N  stdy re-armed=0x3 after_load=0x?  no-signal n/40`. Parser je provjeren sintetičkim zapisom (delta 3787/2665 točna).

**Tumačenje:**
- `dvilr0_1`: brojači ostaju visoki (detektor i dalje trepće), a no-signal ≈ 0/40 → potvrđen mehanizam LOCK_REQ; ide `glr0_1` na Linux.
- `dvilr0_1`: brojači visoki i slika i dalje ispada → takt je stvarno loš (fazni skokovi), pa ostaje HW (§9.1 P1/P2, `pll_discriminator.sh`).
- STDY `after_load` = 0 uz visok sirovi brojač potvrđuje da silicij sam vidi pad; STDY = 1 bi značilo da je sirovi signal lažno trepće.

## 4. Konzola (Goranove primjedbe)

| Stavka | Stanje | Dokaz |
|---|---|---|
| `logo.nologo` | ✅ u `tools/linux/mkdts.py` (bootargs) | `grep nologo tools/linux/mkdts.py` |
| 640×240 (80×30 znakova 8×16 px) | ✅ gateware: `Scaler2x(sw, hdouble=False)`, `--video-640x240`, `VIDEO_FB_WIDTH` = 640 → mkdts stride 1280 | `sim/tb_scaler2x.py`: **4/4 PASS** (2 takta, CE, 2 takta 640×240, CE 640×240; 11 okvira, 0 grešaka) |
| Build 1G+DVI+LOCK_REQ0+640×240 (`g640_1`) | P&R rc=0, 28 666 LT (70 %), 0 hold; **sys post-route 20,16 MHz (0,8 % rezerve)**; nije učitan na ploču | `soc_g640_1.log` |
| SDRAM propusnost | 640 riječi po paru linija (64 µs) = 10 Mriječi/s = **50 % vrha** SDR-a na 20 MHz (320×240: 25 %). CPU memspeed će pasti. **Uključiti tek kad `dvilr0`/`glr0` pokaže stabilnu sliku**, jer dvostruki DMA promet pojačava upravo onaj šum koji ruši lock. | |

## 5. USB tipkovnica (Emardov HID host)

| Dio | Stanje | Dokaz |
|---|---|---|
| Izvori | `gateware/verilog/usbhost/` (emard/ulx3s-misc d0c6f15: usbh_host_hid, usbh_sie, crc5/16, setup ROM); VHDL PHY → Verilog preko `ghdl --synth` (LiteX flow nema VHDL) | `gateware/verilog/usbhost/README.md` |
| Wrapper | `gateware/usb_hid.py` `USBHIDHost`: 6 MHz = gtx0/21 (5,952 MHz, −0,79 %, LS ±1,5 %) iz brojača na lokalnom routingu (`clkbuf_inhibit` na samom FF-u, **bez nove BUFG**), pull-downi za host, CSR `usb_hid_report` (64 b), `usb_hid_seq`, `usb_hid_led`, `usb_hid_ctrl` (bus reset) | `csr.csv` 0xf0003800… |
| Zamka | Prvi pokušaj (`ghid_1`): `clkbuf_inhibit` samo na `cd.clk` → yosys je umetnuo 5. `CC_BUFG` na FF izlaz, a nextpnr (`More than 4 BUFG`) pao je s `dict::at()`. Atribut mora biti na **registru** koji tjera mrežu takta. | `soc_ghid_1.log` |
| P&R 1G+DVI+USB (`ghid2_1`) | rc=0, **30 232 CPE_LT (73,8 %)**, iznad dosadašnje „granice placera" od 71 %, ali placer je uspio; 0 hold; sys 23,66 MHz; `usb_clk` 50,9 MHz (treba 5,95); grx 100 MHz (kao `gneg_1` na ploči) | `soc_ghid2_1.log` |
| Most prema Linuxu | `tools/usbhidd/usbhidd.c` (statički rv32im ELF, isti runtime kao doom/csrpeek): čita CSR preko `/dev/mem` svakih 8 ms (`clock_nanosleep`), provjerava poderano čitanje preko seq, a nove tipke piše u `/dev/tty1` s `TIOCSTI` (US raspored, Shift/Ctrl, strelice, typematic 500 ms / 30 Hz) | `tools/usbhidd/hidkey.h` + `test_hidkey.c`: **11/11 PASS** (gcc na hostu) |
| Boot | `etc/init.d/S90usbhidd`: `usbhidd &` i `getty 38400 tty1` u petlji → login na DVI ekranu | `~/.tmp/t5047/rootfs_dvi_hid.cpio` (8,4 MB, u initrd prozoru 12 MB) |
| Na ploči (`ghid2_1`, bez watchdoga) | bitstream radi: Linux se diže, mreža radi (ping), slika stabilna; `usbhidd` i USB CSR-ovi nisu provjereni do kraja (boot ~10 min, konzola zauzeta) | `~/.tmp/t5047/lx_ghid2_1/uart.txt` |
| Build s watchdogom (`ghrec_1`) | P&R rc=0, 30 635 LT (74,8 %), 0 hold, sys 22,24 MHz, grx 97 MHz (FAIL kao na `gneg_1`, koji ipak radi) → `ETH_GateMateA1_2509_2330_Linux_GbE_DVI_USBHID_rec1.bit`, **nije učitan** | `soc_ghrec_1.log` |
| Zaštita | `usbhidd` se pokreće samo ako DT ima `usbhid@<csr>` (`mkdts.py`); fiksna 0xf0003800 bi na buildu bez USB-a pisala u `video_fb2x_dma_loop`. `sleep_ms` pada na `ppoll_time64` ako `clock_nanosleep_time64` ne radi (nikad ne vrti petlju) | `tools/usbhidd/` |
| Test s tipkovnicom | ❌ **nije napravljen**: traži Gorana (tipkovnica na J5 + **vanjskih 5 V na VBUS**, J5.VBUS nije napajan s ploče) | – |

## 6. Stanje ploče (kraj TASK-5047)
Na ploči je `grec_3` (Linux + 1G + DVI, LOCK_REQ=0, watchdog), a login i DOOM rade. **TFTP je vraćen u `linux` mod.**
Dodatne datoteke na Piju: `/srv/tftp/rootfs_hid.cpio` (12 MiB: doom, csrpeek, usbhidd, S90usbhidd), `rv32_{glr0_1,ghid2_1,g640_1,grec_3}.dtb`.
Za ponovni boot preporučenog builda: `bash /tmp/lxrun.sh <bit> rv32_grec_3.dtb 600` (na Piju; skripta u `~/.tmp/t5047/lxrun.sh`).

## 7. Sljedeći koraci
1. Goran: USB tipkovnica na J5 + 5 V na VBUS, učitati `…USBHID_rec1.bit` (DTB `mkdts.py build/s_ghrec_1`, rootfs `rootfs_hid.cpio`) i
   tipkati na DVI ekranu. `usbhidd` piše `/var/log/usbhidd.log`, a `csrpeek <usb_hid> 5` prikazuje report/seq/led.
2. 640×240 s watchdogom (`--video-640x240 --video-recover`) pa mjeriti; `g640_1` ima samo 0,8 % rezerve sys takta.
3. Goranova mjerenja napona (VDD_PLL / +1V8 pod opterećenjem): detektor locka i dalje trepće (STDY=0). LOCK_REQ=0 skriva simptom, a šum
   ostaje (P1/P2 iz §9.1 TASK-5044, `tools/dvi/pll_discriminator.sh`).
