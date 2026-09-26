# Istraživanje: Linux na GateMateu (CCGM1A1) sa SDRAM-om — TASK-5035

Autorica: Dora (REGOČ), 25. 9. 2026. Nalog: Goran 10:45, upute #28, #30, #31. Ovo je samo istraživanje. Nisam dirala ploču ni Jelenin kod.

Dorada i provjera: Jelena (TASK-5038), 25. 9. 2026. Lokalne tvrdnje ponovno sam provjerila, a dvije otvorene točke iz §7 zatvorila mjerenjem (vidi §11).

> **Stanje prije ovog izvještaja.** Dok je nalog nastajao, Jelena je (TASK-5033, grana `linux-vexriscv-smp`, tag `linux-boot-ok-2509`) već podigla Linux 5.14 na ULX5M-GS: VexRiscv-SMP s 1 jezgrom, I$/D$ 4 KiB, MMU, 1G CPU MAC, bez SD-a, **CPE_LT 55 %**, RAM_HALF 45/64 (`docs/SOC_PHASE2_20260925_TASK-5033.md` §9). Zato ovaj dokument ne traži konfiguraciju koja stane, nego:
> (a) dokazuje da je to ista konfiguracija kojom je Linux podignut na Kölschu;
> (b) popisuje što se još može ukloniti da uz Linux stane i SD;
> (c) ocjenjuje zamjenske putove (nommu, SaxonSoc, VexiiRiscv).

Oznake: **[IZVOR]** znači da iza tvrdnje stoji link ili datoteka. **HIPOTEZA** znači da nije provjereno.

---

## 1. Ploča njemačkog proizvođača: Machdyne Kölsch

| Stavka | Kölsch | Izvor |
|---|---|---|
| Proizvođač | Machdyne UG (njemački oblik društva) | [X/Twitter Machdyne](https://x.com/machdyne/status/1651920765619511297), [Cologne Chip vijest](https://colognechip.com/news/machdyne-announced-board-with-a1/) |
| FPGA | **CCGM1A1** („Cologne Chip GateMate CCGM1A1 FPGA (20K LUTs, 4 PLLs)”), dakle isti čip kao naš, a ne A2/A4 | [machdyne.com/product/kolsch-computer](https://machdyne.com/product/kolsch-computer/) |
| RAM | „64MB 16-bit LPSDR SDRAM (166MHz)”, u LiteX-u modul `W989D6DBGX6` na `GENSDRPHY`, 1:1 | produktna stranica; `litex_boards/targets/machdyne_kolsch.py` r. 26, 103–107 |
| Takt SDRAM-a | `DDROutput(1, 0, sdram_clock, ClockSignal("sys_ps"))`, PLL `sys_ps` s fazom 90° | `machdyne_kolsch.py` r. 37, 51–53 |
| Ostalo | VGA (4096 boja), kompozitni video, microSD (SPI), RP2040 konfigurira FPGA | produktna stranica; [github.com/machdyne/kolsch](https://github.com/machdyne/kolsch) |

### 1.1 Linux na Kölschu: što je javno dokazano

- **linux-on-litex-vexriscv `--board=kolsch`**: [PR #428](https://github.com/litex-hub/linux-on-litex-vexriscv/pull/428), autor Miodrag Milanović (mmicko, YosysHQ), primljen 2. 7. 2025. Commit `b988251` „Added support for Machdyne Kolsch”:
  ```python
  class Kolsch(Board):
      soc_kwargs = {"sys_clk_freq": int(24e6)}
      ... soc_capabilities={"serial", "spisdcard"}
  ```
  PR ovisi o tri upstream zakrpe, koje su sve primljene:
  - [litex-boards #679](https://github.com/litex-hub/litex-boards/pull/679) (ploča);
  - [litedram #366](https://github.com/enjoy-digital/litedram/pull/366) („Added W989D6DBGX6”);
  - [litex #2274](https://github.com/enjoy-digital/litex/pull/2274) („colognechip: DDR should not be inverted”).

  **Naš lokalni LiteX (`~/app/litex-1g-deps/litex`, 2026.08) već sadrži #2274** (`git log`: `dbca01b0e`), a litedram sadrži `W989D6DBGX6` (`modules.py:574`).
- **Točna CPU konfiguracija** je u YosysHQ testnom slučaju [`prjpeppercorn-test-cases/112-litex-linux-kolsch`](https://github.com/YosysHQ/prjpeppercorn-test-cases/tree/main/112-litex-linux-kolsch), commit `6d11041` „Added Linux on Kolsch with SDRAM” (27. 6. 2025, Milanović). Netlist je `VexRiscvLitexSmpCluster_Cc1_Iw32Is4096Iy1_Dw32Ds4096Dy1_ITs4DTs4_Ldw16_Ood_Hb1.v`:
  - **1 jezgra, I$ 4 KiB/1 put, D$ 4 KiB/1 put, ITLB/DTLB 4, MMU (Sv32), bez FPU-a;**
  - nativni LiteDRAM 16 bit, out-of-order dekoder, 1 hardverska prijelomna točka;
  - `kolsch.sdc`: `sys_clk` period 41,666 ns = **24 MHz**;
  - yosys: `-nomx8` i `setattr -unset ram_style a:ram_style=distributed`;
  - od commita `8ed68d7` (18. 8. 2025) množila su uključena (maknut je `-nomult`).
- **Iskorištenost Kölscha nije objavljena.** Testni slučaj nema izvještaj P&R-a, a toolchain nije u ovom kontejneru, pa ga nisam mogla ponoviti. **HIPOTEZA:** oko 60 % CPE_LT, jer je sastav (SMP + SDRAM + serial + SPI-SD) najbliži Jeleninom `smp_1` (61 %, SMP + serial + LiteSDCard).
- **Zapis boota s Kölscha nisam našla javno**: nema ga ni u PR-u #428, ni u prjpeppercorn, ni na Machdyneovim stranicama. Dokaz da Linux radi posredan je:
  1. ploča je u glavnoj grani linux-on-litex-vexriscv;
  2. autor je kasnije dodavao samo popravke;
  3. naslov commita kaže „Linux on Kolsch with SDRAM”.

  **Najjači dokaz boota na CCGM1A1 + SDRAM danas je naš vlastiti:** `docs/linux/linux_boot_smp8_9.txt` na grani `linux-vexriscv-smp` i Kosjenkina neovisna provjera 3/3 (TASK-5034, commit `47985a8`).

**Zaključak §1.** Jelenina konfiguracija (`…Cc1_Iw32Is4096Iy1_Dw32Ds4096Dy1_ITs4DTs4_Ldw16_Ood.v`) i Kölscheva razlikuju se samo po `Hb1`. Ista je jezgra, na istom čipu i s istom širinom SDRAM-a. Mi radimo na 20 MHz, Kölsch na 24 MHz. **Put je potvrđen i nema potrebe tražiti drugi CPU.**

## 2. Ostale GateMate ploče

| Ploča | Čip | RAM | Linux profil | Dokaz / stanje |
|---|---|---|---|---|
| Cologne Chip GateMate EVB | CCGM1A1 (`device="A1"`, a A2 se može zadati) | **HyperRAM 8 MB** (W958D6NW) | `colognechip_gatemate_evb`, 24 MHz, serial + SD | [PR #422](https://github.com/litex-hub/linux-on-litex-vexriscv/pull/422): „note it does have 8MB of RAM”. prjpeppercorn [108-litex-linux-evb](https://github.com/YosysHQ/prjpeppercorn-test-cases/tree/main/108-litex-linux-evb) README: „**Still in progress, working on Linux image**”. Netlist `…_Ood_Wm_Hb1` (Wishbone memorija, jer HyperRAM nema nativni port). |
| Olimex GateMateA1-EVB | CCGM1A1 | QSPI PSRAM | nema u linux-on-litex-vexriscv | prjpeppercorn [119](https://github.com/YosysHQ/prjpeppercorn-test-cases/tree/main/119-litex-vexriscv_smp_dual): **2 jezgre SMP, I$/D$ 8 KiB, 20 MHz na A1** (samo P&R test). [120](https://github.com/YosysHQ/prjpeppercorn-test-cases/tree/main/120-litex-vexriscv_smp_quad) (4 jezgre): „**This test is for A2 only, does not fit in A1**”. [121](https://github.com/YosysHQ/prjpeppercorn-test-cases/tree/main/121-litex-vexiiriscv-linux): VexiiRiscv `--cpu-variant linux`. |
| Trenz (TEG2000 i sl.) | — | — | — | nisam našla Linux profil ni zapis (pretraga GitHub/web, 25. 9.) |
| **ULX5M-GS (naša)** | CCGM1A1 | SDRAM 64 MB IS42VM16320 | vlastiti `target_soc.py` | **Linux 5.14 root shell, 3/3** (TASK-5033/5034) |

**Pouka iz testova 119 i 120:** Olimex testovi nemaju SDRAM ni MAC, a na A1 stanu čak dvije SMP jezgre s cacheom od 8 KiB. Na A1 dakle ne skuči CPU, nego periferija oko njega (MAC + LiteSDCard + Etherbone + FIFO). Isto kaže i Jelenina lekcija J7: placer pada iznad ~71–76 % CPE_LT, a CC_MULT nije uzrok.

## 3. Issue #164 (linux-on-litex-vexriscv)

[Issue #164](https://github.com/litex-hub/linux-on-litex-vexriscv/issues/164) „Prebuilt Bitstreams and Linux/OpenSBI images” otvorio je enjoy-digital 15. 12. 2020. Nije problem, nego trajno otvoreno mjesto za preuzimanje:
- `linux_2022_03_23.zip` (Image + rootfs.cpio + opensbi.bin), `arty_…zip`, `orangecrab_…zip`;
- „The .dts/.dtb are included in the archives and can be regenerated with `./make.py --board=xy`.”

Ništa drugo ne predlaže. **Jelena već koristi upravo te slike** (`tools/linux/README.md`). Posljedice koje ona već navodi:
- kernel 5.14 nema `IP_PNP`, pa `ip=` ne radi;
- `rootfs.cpio` javlja „invalid magic”.

Rješenje je vlastiti Buildroot (`./make.py` → `buildroot/configs/litex_vexriscv_defconfig`) uz fragment s `CONFIG_IP_PNP=y`. To je sljedeći korak, a ne nova gateware opcija.

## 4. VexRiscv-SMP: minimalna konfiguracija

Ovo je naš radni sastav i sastav Kölscha (1 jezgra, 4K/4K, TLB 4, bez FPU-a, Ldw16):

| Build (Jelena, TASK-5033) | CPE_LT | RAM_HALF | Ishod |
|---|---|---|---|
| SMP + 1G CPU MAC + netboot, bez SD-a | 22 644 (55 %) | 45/64 | **Linux 3/3 na ploči** |
| SMP + serial + SD | 25 356 (61 %) | 38 | P&R PASS, nije dizan |
| SMP + MAC + SD | 31 643 (77 %) | 54 | placer pada |

Daljnje smanjenje jezgre. Sve su to opcije `litex/soc/cores/cpu/vexriscv_smp/core.py`, r. 71–95:

| Poluga | Učinak | Uvjet / rizik |
|---|---|---|
| `--without-out-of-order-decoder` | manje logike u dekoderu (help: „Reduce area at cost of peripheral access speed”) | **treba regenerirati netlist** (SBT + Java). U `pythondata-cpu-vexriscv_smp` postoje samo gotove `…_Ood` inačice. Ušteda nije izmjerena (HIPOTEZA: nekoliko stotina CPE-ova). |
| `--icache-size 2048 --dcache-size 2048` | štedi BRAM (oko 2–3 RAM_HALF), a CPE manje | isto (regeneracija). Sporiji Linux. |
| `--itlb-size 2 --dtlb-size 2` | malo CPE-ova | isto. Više TLB promašaja. |
| `--hardware-breakpoints 0` | već je tako (naš netlist nema `Hb1`) | — |
| `-nomult` / CC_MULT | **ne pomaže**: lekcija J7 to pokusom opovrgava | — |

**Zaključak §4.** Jezgru ne treba dalje rezati. Kad bismo morali, jedina vrijedna poluga je regeneracija bez OoO dekodera, uz SBT/Javu kojih u ovom kontejneru nema. Veći dobitak je u periferiji (§6).

## 5. Linux bez MMU-a (nommu, uClinux) — uputa #28 (7)

| Pitanje | Odgovor | Izvor |
|---|---|---|
| Podržava li kernel rv32 nommu? | Da. `CONFIG_MMU=n` ostaje. Prijedlog da se ukine (2024.) povučen je nakon Lohrova prigovora: „NOMMU Linux on RISC-V is the avenue used by many FPGA soft cores for Linux”. | [LKML 2403.3/07337](https://lkml.iu.edu/hypermail/linux/kernel/2403.3/07337.html) |
| Buildroot + elf2flt za rv32 | Patchset „Add RISC-V 32 NOMMU support” (12/2022): elf2flt rv32, uClibc rv32, `-fPIC` | [buildroot patchwork](https://patchwork.ozlabs.org/project/buildroot/cover/20221217051337.3778405-1-Mr.Bossman075@gmail.com/), [elf2flt patch](https://lists.buildroot.org/pipermail/buildroot/2022-December/720522.html) |
| Minimalni zahtjevi CPU-a | **rv32ima + Zicsr, M-mode, CLINT (mtime/mtimecmp)**. Kernel treba atomike (A). Referentni emulator mini-rv32ima implementira upravo to. | [cnlohr/mini-rv32ima](https://github.com/cnlohr/mini-rv32ima) |
| Userspace | bFLT (`CONFIG_BINFMT_FLAT=y`), `vfork` umjesto `fork`, `-Wl,-elf2flt=-r` | [popovicu.com: 789 KB Linux without MMU](https://popovicu.com/posts/789-kb-linux-without-mmu-riscv/) (6.5.5, rv64, QEMU) |
| RAM | tinyconfig kernel 789 KB nekomprimiran. Buildroot sustav stane u nekoliko MB, a mi imamo 64 MB, pa to nije ograničenje. | isto |
| Radni primjer na LiteX/VexRiscv? | **Nisam ga našla.** Svi LiteX Linux primjeri koriste MMU (VexRiscv-SMP/linux). Poznati rv32 nommu primjeri su emulatori (mini-rv32ima, uc-rv32ima na ESP32-C3) i KianV (vlastiti SoC; ima i Sv32 inačicu). | [xhackerustc/uc-rv32ima](https://github.com/xhackerustc/uc-rv32ima), [splinedrive/kianRiscV](https://github.com/splinedrive/kianRiscV) |
| Može li na našem **Lite** SoC-u? | **Ne izravno.** `lite` je `rv32im` (GCC_FLAGS: `-march=rv32i2p0_m`), dakle ima M (iterativno, 0 CC_MULT), **ali nema A**. Ispravak §9 u SOC_PHASE2, gdje piše „lite nema A/M”: M ima. Kandidat bez MMU-a je varijanta **`imac`**: `GenCoreDefault --csrPluginConfig all --atomics true --compressedGen true`, s istim 4K cacheom kao `standard`, ali s MMU-om. Emulirati A u trap handleru nije moguće jer kernel radi u M-modu (HIPOTEZA). | `litex/soc/cores/cpu/vexriscv/core.py` r. 34–80; `pythondata-cpu-vexriscv/verilog/Makefile` r. 15–25 |
| Isplati li se? | **Ne.** `standard` (izveden iz iste jezgre kao `imac`) s netbootom ne stane (76 %, J7), a SMP s MMU-om stane na 55 %. Razlika dolazi od toga što SMP spaja LiteDRAM nativno (Ldw16) i sporije pristupa periferiji. nommu bi uz to tražio vlastiti kernel i uClibc + elf2flt userspace, a to je puno softverskog posla bez hardverskog dobitka. | Jelenina tablica §9 + J7 |

## 6. SaxonSoc — uputa #28 (6)

- [SpinalHDL/SaxonSoc](https://github.com/SpinalHDL/SaxonSoc) (grana dev-0.3) ima BSP-ove za **ULX3S (ECP5), Arty-A7 i Efinix Xyloni**. **GateMate BSP nema.**
- Na ULX3S postoji bitstream `saxonsoc-ulx3s-linux-12f.bit`, dakle Linux s MMU-om na ECP5 12F (oko 12k LUT4) i SDRAM-u od 32 MB ([dok3r/ulx3s-saxonsoc wiki](https://github.com/dok3r/ulx3s-saxonsoc/wiki/SaxonSoc-on-ULX3s), [LinuxGizmos](https://linuxgizmos.com/lattice-fpga-sbcs-can-run-linux-on-risc-v-softcore/)). Točna konfiguracija (cache, takt) i iskorištenost nisu na tim stranicama.
- **HIPOTEZA:** SaxonSoc na ECP5 12F dokazuje da je VexRiscv s MMU-om dovoljno malen i za ~20k LUT-a GateMatea. To isto već dokazuje i naš SMP na 55 %.
- **Ocjena:** port na GateMate traži novi BSP u SpinalHDL-u, SBT/Javu, vlastiti U-Boot i DTS, i nema LiteEth/1G MAC-a. Nema prednosti pred LiteX SMP-om koji već radi. **Ne preporučujem.**

## 7. Smanjenje ostatka LiteX SoC-a (da uz Linux i ETH stane SD)

Cilj je spustiti `SMP + MAC + SD` sa 77 % ispod ~71 %, što je granica placera iz J7. Treba uštedjeti oko 2 500–3 000 CPE_LT.

| # | Poluga | Očekivani učinak | Dokaz / izvor | Rizik |
|---|---|---|---|---|
| R1 | **SPI-SD umjesto LiteSDCard** (`add_spi_sdcard()`, kao na Kölschu: `"spisdcard"`) | LiteSDCard (native, DMA, FIFO-i) je razlika 55 % → 77 %, oko 9 000 CPE. SPI-SD je jednostavni SPI master s nekoliko stotina CPE-ova (HIPOTEZA). Linux ga vidi preko `mmc_spi`: DTS `compatible = "litex,litespi"`, `litespi,sck-frequency = <1500000>`. | `make.py` r. 350–353; Kölsch `soc_capabilities={"serial","spisdcard"}`; `litex_json2dts_linux.py` r. 998–1021 | sporo: SCK 1,5 MHz daje oko 0,18 MB/s, dovoljno za trajni rootfs, ne za velike prijenose. Kernel mora imati LiteSPI i `mmc_spi`: **prebuilt 5.14 ih ima** (provjereno, §11.2). Pinovi `spisdcard` za ULX5M-GS već postoje u litex-boards (§11.3). |
| R2 | ROM 64 KiB → 32 KiB (BIOS lite) | −16 RAM_HALF, CPE malo | Jelena §9: ROM je najveći potrošač BRAM-a, a J13 kaže da ROM 48K ne štedi | BIOS mora zadržati netboot |
| R3 | SRAM 8 KiB → 6 KiB | −1 RAM_HALF | zadana vrijednost linux-on-litex-vexriscv je `integrated_sram_size 0x1800` (`boards.py` r. 13–16) | nizak |
| R4 | bez hardverskog stoga (ICMP FIFO, Etherbone, ARP) | već napravljeno (`--eth-mode mac`) | Jelena smpMn | — |
| R5 | ethmac 2 RX + 2 TX slota → 1 + 1 | −2 do −4 RAM_HALF | Jelena §9 | manja RX propusnost |
| R6 | yosys `setattr -unset ram_style a:ram_style=distributed` | premješta LUT-RAM (regfile, TLB i sl.) u BRAM, pa štedi CPE. Tako grade i YosysHQ testovi 108/112. | prjpeppercorn 112 Makefile | više RAM_HALF, a BRAM-a je malo ako se ne napravi R2. Nije izmjereno na našem SoC-u. |
| R7 | `--without-out-of-order-decoder` | vidi §4 | — | treba SBT |

**Preporučeni redoslijed:** R1 → izmjeriti; ako je iznad 71 %, dodati R6; ako BRAM ponestane, dodati R2.

## 8. Tablica opcija (sažetak)

| Opcija | Resursi | Dokaz | Rizik | Preporuka |
|---|---|---|---|---|
| **A. VexRiscv-SMP 1c 4K/4K MMU + 1G MAC, bez SD** (sadašnje) | 55 % LT, 45/64 RAM_HALF, 4 MULT, 4/4 BUFG | **Linux 5.14 na ploči 3/3** (TASK-5033/5034); ista jezgra kao Kölsch | nizak | **ZADRŽATI kao osnovicu** |
| **B. A + SPI-SD** (Kölsch stil) | HIPOTEZA oko 57–60 % LT | Kölsch profil (`spisdcard`) | srednji: treba P&R; upravljački programi u kernelu i pinovi već postoje (§11.2, §11.3), a DTS čvor `litex,litespi` + `mmc-slot` generira `litex_json2dts_linux` | **SLJEDEĆI KORAK** za trajni rootfs |
| C. A + LiteSDCard | 77 % LT | placer pada (smpM) | visok | ne |
| D. Vlastiti Buildroot (`IP_PNP`, ispravan cpio) | 0 gatewarea | #164 + `make.py` | nizak, samo vrijeme builda | **DA**, paralelno s B |
| E. VexRiscv `linux` (ne-SMP) | 83 % / 79 % (no-dsp) | placer pada | visok | ne |
| F. nommu na `imac` | HIPOTEZA oko 70–76 % (standard 76 % pada) | nema LiteX primjera | visok, veliki softverski posao | ne |
| G. nommu na `lite` | — | lite nema A | blokirano | ne |
| H. SaxonSoc | nepoznato na GateMateu | ULX3S 12F Linux | visok (port BSP-a) | ne |
| I. VexiiRiscv `linux` | nepoznato (samo P&R test 121 na Olimex A1) | prjpeppercorn 121 | srednji: noviji LiteX, nije dizano na GateMateu | samo za eksperiment |
| J. A2/A4 (veći čip) | — | test 120 (4 jezgre) samo A2 | treba nova ploča | nije primjenjivo na ULX5M-GS |

## 9. DOOM (uputa #30)

Po uputi #31 ovo poglavlje ne dupliciram. Vidi Jelenin dokument **`docs/RESEARCH_DOOM_DVI_2509_TASK-5036.md`** na grani `doom-dvi-2509` (commit `3684e8e`) i moju reviziju (§10, ispravci D1–D8, commit `5337c88`, TASK-5037).

Veza s Linuxom:
- DVI treba 2 globalne mreže, a 1G SoC troši 4/4 CC_BUFG. Zato **Linux + 1G + DVI ne ide istodobno**.
- DOOM kao aplikacija ide na SoC-u bez 1G.
- Za brzinu DOOM-a presudan je D-cache (SMP ga ima), a ne CC_MULT.

## 10. Izvori

- https://github.com/litex-hub/linux-on-litex-vexriscv (`boards.py` r. 871–908, `make.py` r. 240–353; commit `05fc5e4`, 14. 9. 2026.)
- https://github.com/litex-hub/linux-on-litex-vexriscv/pull/428 , /pull/422 , /issues/164
- https://github.com/litex-hub/litex-boards/pull/679 , /pull/673 ; https://github.com/enjoy-digital/litedram/pull/366 ; https://github.com/enjoy-digital/litex/pull/2274
- https://github.com/YosysHQ/prjpeppercorn-test-cases (108, 112, 119, 120, 121; commitovi `6d11041`, `7aa28ed`, `8ed68d7`)
- https://machdyne.com/product/kolsch-computer/ ; https://github.com/machdyne/kolsch
- https://github.com/SpinalHDL/SaxonSoc ; https://github.com/dok3r/ulx3s-saxonsoc/wiki/SaxonSoc-on-ULX3s
- https://lkml.iu.edu/hypermail/linux/kernel/2403.3/07337.html ; https://github.com/cnlohr/mini-rv32ima ; https://popovicu.com/posts/789-kb-linux-without-mmu-riscv/
- lokalno: `~/app/litex-1g-deps/{litex,litedram,pythondata-cpu-vexriscv,pythondata-cpu-vexriscv_smp}`; `docs/SOC_PHASE2_20260925_TASK-5033.md`; `docs/LESSONS_GATEMATE.md` (J7)

## 11. Dorada i provjera (Jelena, TASK-5038)

### 11.1 Ponovljena provjera lokalnih tvrdnji

| Tvrdnja (§) | Naredba | Izlaz | Ishod |
|---|---|---|---|
| Lokalni LiteX sadrži #2274 (§1.1) | `git -C ~/app/litex-1g-deps/litex log --oneline \| grep invert` | `dbca01b0e colognechip: DDR should not be inverted` | ✅ |
| litedram ima `W989D6DBGX6` (§1.1) | `grep -n W989D6DBGX6 litedram/modules.py` | `574:class W989D6DBGX6(SDRModule):` | ✅ |
| Opcije smanjenja SMP jezgre (§4) | `sed -n 60,100p litex/soc/cores/cpu/vexriscv_smp/core.py` | postoje `--without-out-of-order-decoder`, `--icache/dcache-size`, `--itlb/dtlb-size`, `--hardware-breakpoints` (zadano 1) | ✅ |
| `lite` = rv32im, `imac` = rv32imac (§5) | `grep -n 'lite\|imac' litex/soc/cores/cpu/vexriscv/core.py` | r. 65: `-march=rv32i2p0_m`, r. 70: `-march=rv32i2p0_mac` | ✅ Dorin ispravak stoji: `lite` ima M, nema A. U SOC_PHASE2 (grana `linux-vexriscv-smp`, r. 195) i dalje piše „lite nema A/M”, pa taj redak treba ispraviti pri sljedećem commitu na toj grani. |

### 11.2 Ima li prebuilt kernel 5.14 upravljački program za SPI-SD? — DA

Dora je to ostavila kao HIPOTEZU (§7 R1). Provjerila sam `Image` iz `linux_2022_03_23.zip`, isti koji se diže na ploči (`~/.tmp/t5033/linux/Image`, 7 531 468 B):

```
$ strings Image | grep -m1 "Linux version"
Linux version 5.14.0 (florent@panda) (riscv32-buildroot-linux-gnu-gcc.br_real (Buildroot 2021.08-381-g279167ee8d) 10.3.0, ...) #1 SMP Tue Sep 21 12:57:31 CEST 2021
$ strings -n4 Image | grep -E "mmc_spi|litespi|litex,mmc"
litex,litespi
litex,mmc
litespi,max-bpw
litespi,sck-frequency
litespi,num-cs
litespi
mmc_spi
```

- `litex,litespi` i `litespi,*` su nizovi upravljačkog programa za LiteX SPI master, a `mmc_spi` je MMC-preko-SPI. Točno te ključeve piše `litex_json2dts_linux.py` r. 998–1021 kad SoC ima `spisdcard`.
- `litex,mmc` (LiteSDCard) je također u kernelu, pa softver nije razlog zašto opcija C otpada. Otpada zbog P&R-a (77 %).
- Brojanje: `ext4` 315 pojava, `vfat` 3, a to znači da kernel može montirati trajni rootfs s kartice.
- `IP-Config` 0 pojava: potvrđuje Jelenin nalaz da ovaj kernel nema `IP_PNP` (§3), pa `ip=` doista ne radi.

**Posljedica:** opcija B ne treba vlastiti Buildroot (D). Dovoljan je gateware s `add_spi_sdcard()` i DTS iz `mkdts.py`. D ostaje potreban samo za `ip=` i ispravan `rootfs.cpio`.

Ograničenje provjere: nizovi dokazuju da je kod ugrađen (`=y`), ali ne i da radi na našoj ploči. To dokazuje tek boot s karticom.

### 11.3 Pinovi SPI-SD na ULX5M-GS već postoje

`gateware/target_soc.py` r. 103 koristi `intergalaktik_ulx5m_gs.Platform`, a ta platforma (`litex-boards/.../intergalaktik_ulx5m_gs.py` r. 73–84) ima oba resursa na istom utoru:

```
("spisdcard", 0, clk IO_NA_A3, mosi IO_NA_B3, cs_n IO_NA_A2, miso IO_NA_A1)
("sdcard",    0, data IO_NA_A1 IO_NB_A5 IO_NA_B2 IO_NA_A2, cmd IO_NA_B3, clk IO_NA_A3)
```

SPI-SD koristi podskup pinova nativnog SD-a (CLK, CMD→MOSI, DAT3→CS, DAT0→MISO). Za opciju B dakle ne treba mijenjati platformu. Treba samo `self.add_spi_sdcard()` umjesto `self.add_sdcard()` u `target_soc.py` r. 188 (novi izbor, npr. `--sdcard spi|native`).

### 11.4 Što se mijenja u preporuci

| Opcija | Prije (Dora) | Nakon dorade |
|---|---|---|
| B. A + SPI-SD | srednji rizik: kernel i DTS neprovjereni | **niži rizik:** kernel ima `mmc_spi` + `litex,litespi`, pinovi postoje; ostaje samo P&R (HIPOTEZA 57–60 % CPE_LT) i boot s karticom |
| D. vlastiti Buildroot | „paralelno s B” | više nije preduvjet za B, nego samo za `ip=` i ispravan cpio |

**Najbolja opcija ostaje A + B** (VexRiscv-SMP 1c 4K/4K MMU + 1G MAC + SPI-SD, Kölsch stil). Prvi korak na ploči: build `smp8_9 … --sdcard spi` i mjerenje CPE_LT. Ako je ispod ~71 %, slijedi boot s `root=/dev/mmcblk0p2`.

Status predaje: uputa na TASK-5033 vraća HTTP 409 (zadatak zatvoren), pa je Dora nalaze predala kao TASK-5039 (čeka Goranovu odluku). Ovaj dokument pripada projektu GATEMATE_ETH, a ne pretincu PRJ-033.
