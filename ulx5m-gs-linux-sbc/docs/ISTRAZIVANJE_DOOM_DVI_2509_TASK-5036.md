# DOOM na ULX5M-GS: DVI framebuffer u SDRAM-u, bez Linuxa (TASK-5036)

Datum: 25. 9. 2026. Autorica: Jelena (REGOČ). Zahtjev: Goran preko Klaudija („može li se u nekoj kombinaciji dobiti DVI/HDMI framebuffer u SDRAM-u i pokrenuti DOOM kao aplikacija"). Ovo je zasebno poglavlje o DOOM-u uz Dorino istraživanje Linuxa (TASK-5035).

Oznake: **IZMJERENO** = pokrenuto ovdje, uz datoteku ili log. **IZVOR** = link ili datoteka u repou. **HIPOTEZA** = procjena koju tek treba izmjeriti.

## 0. Sažetak

**Izvedivo je, ali ne u današnjem netboot SoC-u i ne s LiteX-ovim gotovim framebufferom.** Postoje tri prepreke i svaka ima rješenje:

1. **DVI izlaz postoji** (TMDS na `IO_SB_A4…B7`) i već je proradio na ploči (Goranov README v004+). Video lanac izmjerila sam buildom: P&R prolazi. Traži **2 dodatne globalne mreže** (`hdmi` 25 MHz i `hdmi5x` 125 MHz), a današnji 1G SoC već troši **sve 4**. Zato DOOM build ide **bez 1G Etherneta**: WAD sa SD kartice ili 100 Mb/s netboot.
2. **LiteX `VideoFrameBuffer` nije za DOOM.** Na 640×480 rgb565 traži 92 % vrha SDRAM-a (40 MB/s), a paletu nema. Treba **vlastiti modul: 320×200 8 bpp s indeksom + paleta 256×24 + hardversko udvostručenje linija**. To je 3,8 MB/s (9,6 % vrha), a DOOM-ov `screens[0]` tada ide u okvir izravno, bez pretvorbe boja.
3. **Množenje:** DOOM stalno zove `FixedMul`/`FixedDiv`. Netboot SoC danas stane samo s VexRiscv **lite**, koji množi iterativno (~33 takta, 0 CC_MULT). S VexRiscv **standard** (4 CC_MULT, I$/D$ 4 KiB) placer pada pri 76 % LT (lekcija J7). Kad se izbace 1G, Etherbone i hardverski stog, standard stane (S5s9 s *više* logike: 68 % LT, 4 CC_MULT, P&R prolazi).

**Najkraći put do prvog okvira** (§7) je 4 koraka. Prvi je bez ikakvog video gatewarea: DOOM `-timedemo` na postojećem S5s9 SoC-u (standard, SD kartica), a FPS se ispisuje na UART. Tek kad izmjerimo brzinu, gradimo framebuffer.

**Ocjena izvedivosti: DA, srednji rizik.** Najveća nepoznanica je FPS. Bez L2 cachea i uz izmjereno CPU čitanje SDRAM-a od 4,5 MiB/s, očekujem **~3–10 FPS pri 20 MHz** (HIPOTEZA, §5).

## 1. Ima li ULX5M-GS DVI/HDMI izlaz?

**Da.**

| Činjenica | Dokaz |
|---|---|
| Konektor „DDMI0 (3 diff data lines + diff clock)", „Video output (DVI)" i „DVI - tested and works" od v004 | IZVOR `~/app/ulx5m-gs-hw/README.md` (odjeljci *Interfaces* i *Tested and confirmed working from V004*), slika `pic/ULX5M-GS-v002.jpg` |
| Pinovi TMDS: clk `IO_SB_A7/B7`, D0 `IO_SB_A4/B4`, D1 `IO_SB_A5/B5`, D2 `IO_SB_A6/B6` | IZVOR `~/app/GateMate_demos/LiteX_DVI/intergalaktik_ulx5m_gs_platform.py:93-102` |
| Nema sukoba s našim SoC-om: `IO_SB_A0…B3` su statusne LED-ice, `IO_SB_A8` je clk25 | IZVOR `gateware/target_soc.py:40`, `gateware/crg.py:5` |
| GateMate šalje TMDS 640×480@60 preko `CC_ODDR` (DDR, 2 bita po taktu 125 MHz = 250 Mb/s po paru) i `CC_LVDS_OBUF` | IZVOR `LiteX_DVI/gateware/video_colognechip_hdmi_phy.py` (Miodrag Milanović, 2025), serijalizator 10:2 → DDR |

**IZMJERENO: video lanac na našem čipu.** Build `LiteX_DVI/intergalaktik_ulx5m_gs.py --cpu-type None --with-video-terminal` (VTG + colorbars + 3× TMDSEncoder + serijalizatori + SDRAM kontroler s L2 8 KiB) završio je s rc=0. Bitstream sha256 `47f8e260…9c819dbd`, log `docs/doom/dvi_colorbars_util_20260925.txt`.

| Resurs | Izmjereno | Napomena |
|---|---|---|
| CPE_LT | 2 777 (6 %) | gornja granica za video; uključuje i LiteDRAM + L2 |
| CPE_FF | 679 (1 %) | |
| RAM_HALF | 17 | svih 17 su SRAM 8 KiB + L2 tag/data; video ne troši BRAM |
| CC_BUFG | **4** | `sys`, `sys_ps`, `hdmi`, `hdmi5x` → **video treba 2 globalne mreže** |
| CC_PLL | 2 | video ima vlastiti PLL |
| CC_ODDR / CC_LVDS_OBUF | 4 / 4 | |
| fmax `hdmi5x` | 128,8 MHz (cilj 125) | PASS, ali uz malu rezervu |
| fmax `hdmi` | 59,6 MHz | stvarni takt je 25 MHz, pa je dovoljno; „FAIL at 125" je artefakt ograničenja jer je takt izveden logikom `divide_5` iz 125 MHz |

Nisam flashala ploču: to nije bilo traženo, a prema Goranovu README-u DVI na v004+ već radi.

## 2. Globalne mreže: glavni sukob s 1G Ethernetom

GateMate A1 ima 4 `CC_BUFG`. Današnji 1G SoC troši svih 4: `sys`, `gtx0` 125 MHz, TXC i `grx` (IZVOR `docs/SOC_FAZA2_20260925_TASK-5033.md` §4). Video traži još 2 (IZMJERENO, §1).

| Kombinacija | Globalne mreže | Ocjena |
|---|---|---|
| 1G + DVI | sys, gtx0, TXC, grx, hdmi, hdmi5x = **6 > 4** | ❌ ne stane |
| **Bez Etherneta, WAD sa SD kartice** | sys, hdmi, hdmi5x (+ slobodna 1) | ✅ **preporuka za prvi okvir** |
| 100 Mb/s RGMII netboot + DVI | sys, eth_tx 25 MHz = `hdmi` (isti PLL, ista frekvencija), hdmi5x, eth_rx = 4 | ✅ HIPOTEZA; dijeljenje TX takta i piksel-takta treba provjeriti u P&R-u |
| 1G, piksel logika u domeni gtx0 125 MHz s CE 1/5 | 4 | ⚠️ HIPOTEZA; TMDS enkoder na 125 MHz uz gtx0 fmax 119 MHz (S5s9) je rizičan |

## 3. LiteX framebuffer i propusnost SDRAM-a

LiteX `VideoFrameBuffer` (`litex/soc/cores/video.py:1022`) čita okvir DMA-om preko LiteDRAM porta. Podržani formati su samo `rgb888/rgb565/rgb332/mono8/mono1` (`video.py:1008`): **nema palete, nema udvostručenja linija**.

Vrh SDRAM-a: 16 bita × 20 MHz = **40,0 MB/s**. Izmjereno CPU-om (BIOS memspeed, S5): pisanje 8,8 MiB/s, čitanje 4,5 MiB/s (IZVOR `SOC_FAZA2` §4). Budžet pri 60 Hz (IZMJERENO računom, `python3`):

| Način | Okvir | Čitanje @60 Hz | % vrha | Ocjena |
|---|---|---|---|---|
| 640×480 rgb888 (LiteX zadano) | 1200 KiB | 73,7 MB/s | 184 % | ❌ |
| 640×480 rgb565 | 600 KiB | 36,9 MB/s | 92 % | ❌ CPU gladuje |
| 640×480 rgb332 (LiteX, bez izmjena) | 300 KiB | 18,4 MB/s | 46 % | ⚠️ radi, ali DOOM paleta u 3-3-2 izgleda loše, a CPU mora 2× skalirati i pisati 300 KiB po okviru (~33 ms) |
| 320×240 8 bpp indeks + HW 2× | 75 KiB | 4,6 MB/s | 11,5 % | ✅ |
| **320×200 8 bpp indeks + HW 2× (+ crni rub 40 linija)** | **62,5 KiB** | **3,8 MB/s** | **9,6 %** | ✅ **preporuka** (DOOM-ov nativni `SCREENWIDTH×SCREENHEIGHT`) |

Napomena: DMA čita samo tijekom aktivnih linija (73 % vremena kod 640×480), pa je trenutna potražnja ~1,37× veća od prosjeka. Za preporučeni način to je ~5,3 MB/s, i dalje daleko ispod vrha.

**Preporučeni gateware (vlastiti modul, ~150–250 redaka migena, HIPOTEZA za veličinu):**

```
LiteDRAM native port ──> DMA (1 linija = 320 B, jednom po 2 izlazne linije)
    ──> linijski buffer 320×8 (1 RAM_HALF) ──> paleta 256×24 (1 RAM_HALF, CSR upis)
    ──> VideoTimingGenerator 640×480@60 ──> VideoCologneChipHDMIPHY (GateMate_demos)
CSR: fb_base (dvostruki buffer, zamjena na vsync), vsync status/brojač
```

Isti model koristi smunautov DOOM na iCE40: 320×200 8 bpp, paleta u hardveru (`I_SetPalette` piše 256 riječi u `VID_PAL_BASE`), `I_FinishUpdate` = `memcpy` 64 000 B u framebuffer, a timer je brojač vsync-ova (IZVOR `smunaut/doom_riscv` `src/riscv/i_video.c`, `i_system.c`; gateware `smunaut/ice40-playground/projects/riscv_doom/rtl/vid_palette.v`, `vid_framebuf.v`). Kod nas `memcpy` 64 000 B pri 8,8 MiB/s traje ~6,9 ms. S dvostrukim bufferom u SDRAM-u i `fb_base` CSR-om kopija otpada.

**Procjena ukupnih resursa DOOM SoC-a (HIPOTEZA, polazište je izmjereni S5s9):** S5s9 = 27 874 LT (68 %), 48 RAM_HALF, 4 CC_MULT, s 1G + hardverskim ARP/ICMP/Etherboneom + SD karticom. Kad se makne 1G/Etherbone, a doda video (≤ 2 777 LT, izmjerena gornja granica s dupliciranim SDRAM-om) i paleta/linijski buffer (+2 RAM_HALF), očekujem **≤ 70 % LT i ~50/64 RAM_HALF**. To je ispod ~75 %, gdje je J7 pokazao pad placera.

## 4. Postojeće prilagodbe DOOM-a za RISC-V bez OS-a

| Projekt | Platforma | CPU | Memorija | Video | WAD | Izvor |
|---|---|---|---|---|---|---|
| **smunaut/doom_riscv** + `ice40-playground/projects/riscv_doom` | iCE40UP5K (iCEBreaker), ~23,3 MHz (`0.925 × 25.175`, `data/clocks.py`) | VexRiscv rv32im, **MulPlugin + DivPlugin**, I$ 2 KiB (`ways_0_datas[0:511]`) | 8 MiB QSPI PSRAM, kod iz SPI flasha | 320×200 8 bpp u SPRAM-u, paleta u HW, 640×480@60 (`COMPAT_MODE`) + dithering, HDMI PMOD | u SPI flashu na fiksnoj adresi (`libc_backend.c`: `{"doomu.wad", 12408292, 0x40200000}`) | https://github.com/smunaut/doom_riscv (commit 02b0d80), https://github.com/smunaut/ice40-playground/tree/master/projects/riscv_doom, Hackaday: https://hackaday.com/2021/02/07/ice40-runs-doom/ |
| Silice port na IceStick | iCE40HX1K (1280 LUT) + Machdyne QQSPI PMOD 32 MB | mali RISC-V (Silice) | PSRAM | – | – | „*very* slow (~0.3 FPS)… Uses an IceStick, @machdyne great QQSPI pmod, @tnt fabulous doom-riscv port" — https://twitter.com/sylefeb/status/1648015362456166402 |
| knazarov/doom-riscv | emulator | – | – | – | – | temelji se na smunautovu portu: https://git.knazarov.com/knazarov/doom-riscv |
| doomgeneric | bilo koja platforma (5 funkcija: `DG_Init`, `DG_DrawFrame`, `DG_GetTicksMs`, …) | – | – | `DG_ScreenBuffer` 32 bpp (ARGB), treba pretvorba | preko `fopen` | https://github.com/ozkl/doomgeneric |

**Preporuka: smunaut/doom_riscv.** Već je bez OS-a, za rv32im, s 8 bpp i hardverskom paletom, isti model kao naš plan. doomgeneric radi s 32 bpp i traži pretvorbu boja po pikselu, što je pri 20 MHz preskupo.

**RAM (IZVOR `i_system.c` `I_ZoneBase`):** zona 6 MiB + WAD (shareware `doom1.wad` 4 196 020 B, Ultimate `doomu.wad` 12 408 292 B) + kod ~0,5–1 MiB (HIPOTEZA) + `screens[]` 5 × 64 000 B. Ukupno < 20 MiB, a mi imamo 64 MiB. **RAM nije problem.**

**Učitavanje WAD-a preko TFTP-a:** DOOM ne treba mrežni stog. LiteX BIOS netboot čita `boot.json` s više slika na zadanim adresama (IZVOR `litex/soc/software/bios/boot.c:509` `boot_from_json_buffer`; isto radi i SD boot). Primjer:

```json
{ "doom.bin": "0x40000000", "doom1.wad": "0x41000000", "addr": "0x40000000" }
```

U `libc_backend.c` se tablica `fs[]` usmjeri na `0x41000000`, pa `open/read` čitaju iz SDRAM-a (isti mehanizam kao njegov „flash filesystem"). TFTP u našem BIOS-u je spor, jer blok od 512 B čeka potvrdu. HIPOTEZA: ~0,3–1 MB/s, pa 4,2 MB traje ~5–15 s. **SD kartica** (LiteSDCard je već u S5s9, `--boot sdcard`) daje isto, a ne treba Ethernet ni globalne mreže.

**Ulaz (tipke):** UART kao kod smunauta (`I_GetRemoteEvent`, skripta `sw/doom_ctrl.py`), ili 3 tipke na ploči (IZVOR README: „3 BTNs") za prvi okvir. Zvuk se preskače (smunaut ima prazan `s_sound.c`).

## 5. Očekivani FPS i sukob s množenjem

DOOM je pisan u fiksnom zarezu 16.16. `FixedMul` je `(int64)a*b >> 16` (na rv32im to su `mul` + `mulh`), a `FixedDiv` je u `R_ScaleFromGlobalAngle`, `R_PointToDist` i sličnim funkcijama. Poziva ih se tisuće puta po okviru.

| CPU (LiteX varijanta) | Množenje | Cache | CC_MULT | Stane s | Izvor |
|---|---|---|---|---|---|
| lite | `MulDivIterativePlugin`, brojač do 32 (`VexRiscv_Lite.v:3729`) → ~33 takta po `mul`, 2× za `FixedMul` | I$ 2 KiB, D$ nema | 0 | netboot SoC (71 % LT) | IZVOR `VexRiscv_Lite.v`, `SOC_FAZA2` §6 |
| **standard** | `MulPlugin` (4 CC_MULT, 1 takt protoka) + `DivPlugin` | I$ 4 KiB, D$ 4 KiB (`banks_0[0:1023]`) | 4 | S5s9 (68 % LT) ✅, netboot (76 %) ❌ | IZVOR `VexRiscv.v:5381, 6127`, lekcija J7 |

**Sukob s CC_MULT je stvaran, ali se ne tiče DOOM SoC-a.** CC_MULT sam po sebi ne pada: S5s9 ima 4 CC_MULT i prolazi. Placer pada tek kad je LT iznad ~75 % (J7: 3 : 0 uz hipotezu). DOOM build izbacuje 1G, Etherbone i hardverski stog, pa se vraća ispod te granice. **Preporuka: VexRiscv standard.** S lite varijantom `FixedMul` je ~30× sporiji, pa bi DOOM bio neigriv (HIPOTEZA < 1 FPS).

**FPS (HIPOTEZA, nije izmjereno):** Za DOOM je tipično navođen 486DX2-66 s 8 MB RAM-a (Hackaday: „a 486 DX2 running at 66MHz with 8MB of RAM"); igra je ograničena na 35 FPS. VexRiscv standard pri 20 MHz ima otprilike 1/3 takta, ali većinu instrukcija u jednom taktu. Glavna kočnica je memorija: nema L2, D$ je 4 KiB, a CPU iz SDRAM-a čita samo 4,5 MiB/s (izmjereno). Teksture, flatovi i colormap (8 KiB) stalno promašuju D$. Procjena: **~3–10 FPS pri 20 MHz**. Poboljšanja po redu isplativosti:

1. colormap i najčešći lookupovi u SRAM (on-chip);
2. veći D$ (8–16 KiB, ima BRAM-a kad nema 1G bufferâ);
3. L2 isključen zbog yosys mapiranja tagova u FF (lekcija S1). Mali L2 s ručnom BRAM instancom bio bi velik dobitak.

Broj se mora izmjeriti (§7, korak 1).

## 6. Primjeri na GateMateu i Machdyne pločicama

| Nalaz | Izvor |
|---|---|
| **DOOM na GateMateu nije javno dokumentiran.** Našla sam samo Synogate (Game Boy uložak). Oni su prešli na CologneChip GateMate (1,8 V, DDR2), s vlastitim rv32i jezgrom na 48 MHz i instrukcijama za množenje u fiksnom zarezu, ali tekst ne potvrđuje da je DOOM proradio baš na GateMateu | https://www.synogate.com/blog/2024/bfc_doom_soc_intro.html |
| DVI + LiteX na GateMateu postoji (colorbars / video terminal) za ULX5M-GS, Olimex GateMate A1 EVB i CologneChip EVB | `~/app/GateMate_demos/LiteX_DVI/` (M. Milanović), IZMJERENO: build prolazi (§1) |
| Machdyne: DOOM je radio na IceSticku s Machdyne QQSPI PMOD-om (~0,3 FPS, Silice) | https://twitter.com/sylefeb/status/1648015362456166402 |
| Machdyne Zucker SoC (PicoRV32 + jednostavni GPU) za Riegel; DOOM se ne spominje | https://github.com/machdyne/riegel |
| RISC-V CPU tutorial za GateMate (learn-fpga port) | https://github.com/fm4dd/gatemate-riscv |

**Zaključak:** bili bismo, koliko sam našla, **prvi s DOOM-om na GateMateu uz SDRAM**. To je zanimljivo za prikaz, ali nema gotovog rješenja za prepisati.

## 7. Najkraći put do prvog okvira na ekranu

| Korak | Što | Gateware | Dokaz gotovosti | Rizik |
|---|---|---|---|---|
| **1. DOOM bez videa** | port `doom_riscv/src/riscv` za LiteX (UART iz `libbase`, `I_GetTime` iz LiteX timera, `fs[]` → `0x41000000`, linker za `main_ram`), `-timedemo demo1` | **postojeći S5s9** (standard, SD) s `--boot sdcard`; boot.json: `doom.bin` + `doom1.wad` | UART ispiše `timed N gametics in M realtics` → **izmjereni FPS** | nizak |
| **2. DVI colorbars na v005** | `LiteX_DVI` build (već izmjeren: rc=0) učitan na ploču | nema izmjena | slika na monitoru | nizak (README: DVI radi na v004+) |
| **3. 8-bpp framebuffer s paletom** | vlastiti modul (§3) + migen sim testbench (piksel na (x,y) → TMDS ulaz, paleta, 2× linije) | S5s9 − 1G/Etherbone + video | sim PASS; P&R ≤ 75 % LT; fmax sys ≥ 20 MHz, hdmi5x ≥ 125 MHz | srednji (P&R, hdmi5x rezerva 3 %) |
| **4. DOOM na ekranu** | `I_SetPalette` → CSR paleta, `I_FinishUpdate` → `memcpy` ili zamjena `fb_base` na vsync | kao 3 | **prvi okvir: naslovni ekran DOOM-a** | nizak kad 1–3 prođu |
| 5. (opcija) netboot | 100 Mb/s RGMII, TX takt = piksel takt 25 MHz | kao 3 + LiteEth MAC (bez hw stoga) | TFTP boot.json | srednji |

**Procjena vremena (HIPOTEZA):** korak 1 ~0,5 dana, 2 ~1 h, 3 ~1–2 dana, 4 ~0,5 dana.

## 8. Rizici

| # | Rizik | Vjerojatnost | Ublažavanje |
|---|---|---|---|
| R1 | Nizak FPS (< 5) zbog SDRAM latencije i malog D$ | srednja | korak 1 mjeri **prije** videa; colormap u SRAM, veći D$ |
| R2 | P&R pad (J7) ako se ne izbaci dovoljno logike | niska–srednja | bez 1G/Etherbonea/hw stoga; mjeriti LT nakon svakog dodatka |
| R3 | hdmi5x fmax 128,8 MHz uz cilj 125 MHz (3 % rezerve) | srednja | seed sweep kao za gtx; serijalizator `v2` (CDC + Converter) kao alternativa |
| R4 | Nestandardni piksel takt 25,0 umjesto 25,175 MHz | niska | većina monitora prihvaća; smunaut i LiteX_DVI rade isto |
| R5 | DMA videa krade SDRAM CPU-u | niska | 3,8 MB/s ≈ 10 % vrha |
| R6 | 1G ping pada pod SDRAM opterećenjem (nalaz 3 u `SOC_FAZA2`) | ne tiče se DOOM builda | DOOM build nema 1G |
| R7 | Licenca: shareware `doom1.wad` smije se dijeliti, Ultimate/Doom II ne | – | za demo koristiti samo `doom1.wad` ili Freedoom |

## 9. Odgovori na Klaudijeve točke

1. **DVI na ULX5M-GS:** DA (IO_SB_A4…B7, radi od v004). TMDS 640×480@60 preko `CC_ODDR` + `CC_LVDS_OBUF` je izmjeren buildom na našem čipu. Treba 2 globalne mreže, pa ne ide zajedno s 1G.
2. **LiteX VideoOut:** gotovi `VideoFrameBuffer` na 640×480 ne ide (rgb565 = 92 % vrha, nema palete). Treba 320×200 8 bpp + paleta + 2× u hardveru: 3,8 MB/s (9,6 %). Vidi §3.
3. **DOOM bez OS-a:** `smunaut/doom_riscv`, 6 MiB zona + WAD. Učitavanje: boot.json (TFTP ili SD) na fiksnu adresu. FPS: HIPOTEZA 3–10 pri 20 MHz, mjeri se korakom 1. Sukob s CC_MULT: potreban je standard (hw mul), a on stane kad se makne 1G/Etherbone (S5s9 dokazuje 4 CC_MULT pri 68 % LT).
4. **Primjeri:** DOOM na GateMateu javno nema. Na Machdyne hardveru postoji samo IceStick + QQSPI (~0,3 FPS). DVI na GateMateu postoji u `GateMate_demos/LiteX_DVI`.
