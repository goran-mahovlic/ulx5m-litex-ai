# TOOLCHAIN_20261017 — novi zadani open source lanac za GateMate (TASK-5549)

**Zahtjev (Goran 17.10. 00:19):** „treba preuzeti novi open source toolchain i s njim nastaviti sve buduće poslove".
**Opseg:** preuzimanje, usporedba, offline kvalifikacija i prebacivanje zadanog lanca. **Ploče nisu dirane** (chain4 TASK-5542
radi na Piju). Na Pi su bitovi samo kopirani, nisu učitani.

## 0. Sažetak

- **Zadani lanac od danas: `~/app/raid/tools/oss-cad-suite-20261016`.** Poveznice `~/app/raid/tools/oss-cad-suite` i
  `~/Programs/oss-cad-suite` pokazuju na njega. Sve build skripte u ovom repozitoriju ga koriste bez ikakvih env varijabli.
- **Kvalifikacija na 2,5G gs/m2 je prošla:**
  - CC_SERDES blok je **bajtno isti** kao u Pi bitovima `*_2g5_auto` (0/186 B, 0/252 polja, na gs i na m2);
  - CMD_CFGRST ✓ na sva 4 nova bita;
  - 0 hold kršenja;
  - Fmax je u istom rasponu kao sa starim lancem (6 seedova po lancu, §4).
- **R1 je upečen u bit** (`OV_CALIB 0`, `OV_TX_SEL_PRE 0`, `OV_EQA_CKP_OFFSET 0`). Razlikuje se točno u 4 polja CC_SERDES.
  „DFE/EQA reset nakon učitavanja" nije polje nego strob, pa nije upečen.
- **Za SerDes nema ništa novo.** nextpnr i dalje ne vremenski analizira SerDes portove (`delay.cc`: SERDES = `TMG_IGNORE`).
  gmpack/gmunpack su isti binar kao 23.9. (prjpeppercorn v1.13-6-gb1eb52f = upstream master).
- **Pazi:** nextpnr PR #1849 (timing puta COMBIN→OUT kod L2T5, tj. naših `-luttree` netlista) spojen je 16.10. u 12:19, a to je
  **iza** nightlyja 20261016. Učinak na naš dizajn je izmjeren u §5: Fmax je i dalje iznad potrebnog, ali gs seed 7 se s njim ne ruta.

## 1. Preuzeto

| | |
|---|---|
| izvor | YosysHQ/oss-cad-suite-build, release `2026-10-16` (objavljen 07:03 UTC), `oss-cad-suite-linux-x64-20261016.tgz` |
| veličina, sha256 | 748 221 305 B, `95aead487287adf8fbbe965799e88e2ccb12a544f3d0a27b27f80bfc7c892911` (= GitHub `digest`) |
| mjesto | `~/app/raid/tools/oss-cad-suite-20261016` (2,5 GB), `.trajno` + `README.trajno.md`, katalog `tc-oss-cad-suite-20261016` (kanonski) |

| alat | 20260923 (dosad zadani) | 20260928 | **20261016 (novi zadani)** |
|---|---|---|---|
| yosys | 0.69+136 (0fa1478ce) | 0.69+154 (30d62572e) | **0.70+145 (a31d95ea0)** |
| nextpnr-himbaechel | 0.11.1-31-g3edea68e | 0.11.1-34-gc4fbb55a | **0.11.1-63-g44a6c739** |
| gmpack / gmunpack (prjpeppercorn) | v1.13-6-gb1eb52f | isto (isti binar, sha256 `e8e1f42a…`) | **isto** — upstream master je i dalje `b1eb52f` (16.6.) |
| openFPGALoader | v1.1.1 | v1.1.1 | **v1.1.1** (novi build). Na Piju se i dalje koristi `/usr/local/bin/openFPGALoader` iza `fpga-jtag`, ništa se ne mijenja |

## 2. Što je novo za GateMate (3edea68e → 44a6c739, 32 commita, 7 GateMate)

Popis: `data_20261017/t5549/nextpnr_3edea68e_44a6c739_gatemate.txt`.

| commit / PR | što | značenje za nas |
|---|---|---|
| 1aea87ab5 #1810 | FF_OBF/FF_IBF: inverzija takta iz `C_CPE_CLK` umjesto `CLK_INV` | naš `nextpnr-pr1810` je time **upstream** (već u 20260928) |
| 3c42800da #1814 | timing provjere iz/u IOSEL (registri u IO ćeliji, OUT4 kao takt) | više putova je sada vremenski analizirano. Kod nas su IO samo UART i refclk, pa nema učinka na SerDes |
| ad8527f8f #1817 | IOBUF kašnjenja samo gdje postoji veza | već u našem `nextpnr-main-ad8527f` |
| eb4f15c35 #1818 | PLL `REF_CLK` nema gornju granicu 125 MHz | nema učinka (SerDes refclk ne ide kroz CC_PLL) |
| aa8c83b85 #1832 | takt se premošćuje samo kroz **potpuno slobodne** CPE | djelomično isto što i naša A2 zakrpa B (`nextpnr-a2fix` 0001: nikakvi CPE mostovi). CC_BUFG mreže (`rclk`/`tclk`) se usmjeravaju drukčije |
| f7f1c8775 #1836 | rezervira i CPE `EN_INT` pri usmjeravanju takta | popravak za #1835 (rutiranje pada na EN kod FF-a s PLL taktom) |
| 6f71bc280 | router2 preskače `RESERVED_UNAVAILABLE` žice | općenito |

| tema iz zadatka | stanje u 20261016 |
|---|---|
| **SerDes** | `pack_serdes.cc` i `bitstream.cc` nepromijenjeni. CC_SERDES bitovi isti (§3). Otvoren PR **#1846**: SERDES konfiguracija na die na kojem je ćelija (A2, druga SerDes). Za A1 bez učinka |
| **timing SerDes portova** | i dalje nema: `delay.cc` u 44a6c739, `SERDES → TMG_IGNORE`. TX_DATA_I/RX_DATA_O putovi nisu analizirani (isto vrijedi za p_r, PR_BUILD §3.1). `TX_NEG` ostaje |
| **A2 (CCGM1A2)** | naš fix C (prijelaz die samo s X29, `nextpnr-a2fix` 0002) **nije upstream**. Za A2 i dalje `nextpnr-a2fix`. Fix B je djelomično pokriven s #1832 |
| **CC_BUFG** | #1832/#1836 mijenjaju usmjeravanje takta; na našem dizajnu je 0 nerutiranih i 0 hold kršenja (§4) |
| **CFGRST** | gmpack isti binar, `--reset` radi isto. `gm_cfgrst_check` = CFGRST na sva 4 nova bita |
| yosys 0.70 | nema izmjena u `techlibs/gatemate`. ABC ažuriran 6.10. i 12.10.; `opt_dff` „hold feedback → clock enable" (8e11aac4a). Netlista je zato malo drukčija (gs CPE_LT 7047 → 7116, m2 2116 → 2102) |

**Poznate regresije i otvorene stvari (GitHub, od 20.9.):**
- nextpnr #1811: segfault u `pack_cpe.cc` (otvoreno);
- nextpnr #1843: PR za segfault u `move_ram_io` na nespojenim mrežama (otvoreno);
- yosys #6243: segfault u `synth_gatemate` (otvoreno);
- yosys #6319: `iopadmap` i `-noflatten` (otvoreno).
- Na našim dizajnima se ništa od toga nije pojavilo: svih 28 P&R pokretanja (20261016 i 20260923) završilo je normalno.
- **#1849 nije u ovom nightlyju** (§5).

## 3. Kvalifikacija: 2,5G gs/m2

### 3.1 Postupak

```
cd gateware/ber        # isti ber_top.v, ber_link{,_gs}.v, top_{gs,m2}.ccf kao *_2g5_auto (REVIEW_INIT §10)
P="N1 1 N2 5 N3 5 OUTDIV 2 PROFILE 1 TX_NEG 1 OV_TX_AMP 12"
LINK=ber_link_gs.v FREQ=40 ./build_ber.sh gs 2g5_default 7 $P     # novi zadani lanac, bez env
FREQ=40 ./build_ber.sh m2 2g5_default 2 $P
python3 ../../pr_build/tools/serdes_cmp.py build/gs_2g5p1_txneg_amp12_s7.bit build/gs_2g5_default_s7.bit
```

### 3.2 Rezultat

| | gs stari (`99d80788`, Pi `gs_2g5_auto`) | **gs novi** | m2 stari (`3f4857df`, Pi `m2_2g5_auto`) | **m2 novi** |
|---|---|---|---|---|
| bit sha256 | `99d80788…` (277 269 B) | **`ed04be04…`** (277 971 B) | `3f4857df…` (93 618 B) | **`ec045992…`** (86 315 B) |
| CMD_CFGRST | ✓ | ✓ | ✓ | ✓ |
| CC_SERDES prema starom | — | **0/186 B, 0/252 polja** | — | **0/186 B, 0/252 polja** |
| `rclk` Fmax | 50,92 | 44,98 | 77,46 | 63,08 |
| `tclk` Fmax | 85,77 | 71,31 | 79,65 | 80,70 |
| `clk_i` Fmax | 34,85 | 38,21 | 123,03 | 125,63 |
| hold kršenja | 0 | 0 | 0 | 0 |

- Potrebno: `rclk`/`tclk` ≥ 31,25 MHz, `clk_i` ≥ 25 MHz. Sve je iznad.
- Na `clk_i` gs ostaje „FAIL at 40" kao i prije. To je dopušteno (`--timing-allow-fail`, UART takt je 25 MHz).
- Tablice svih 252 polja: `data_20261017/t5549/{gs,m2}_serdes_oss1016.md`.

### 3.3 Kontrole

- **Izmjena `ber_top.v` (R1 parametri) ne mijenja stare bitove.** Stari lanac s novim `ber_top.v` daje bajtno iste Pi bitove:
  `gs_2g5_oss0923chk_s7.bit` = `99d80788…`, `m2_2g5_oss0923chk_s2.bit` = `3f4857df…`.
- **Zadani put bez env varijabli = eksplicitni novi lanac:** `*_2g5_default` = `*_2g5_oss1016`, bajtno (ed04be04 / ec045992).
  Build je i deterministički.
- Svaki build sada zapisuje i `build/<ime>.toolchain` (stvarna mapa lanca, `yosys -V`, `nextpnr --version`).

## 4. Fmax: 6 seedova po lancu (seed ref + 11…15, FREQ 40)

| | stari 20260923 min / medijan / max | novi 20261016 min / medijan / max |
|---|---|---|
| gs `rclk` | 42,8 / **45,3** / 50,9 | 41,0 / **45,9** / 48,0 |
| gs `tclk` | 66,1 / 74,4 / 85,8 | 69,7 / 72,3 / 83,8 |
| gs `clk_i` | 34,3 / 36,6 / 38,7 | 34,9 / 36,9 / 39,0 |
| m2 `rclk` | 67,3 / 73,1 / 78,7 | 63,1 / 72,1 / 81,8 |
| m2 `tclk` | 77,4 / 81,4 / 91,5 | 67,9 / 81,5 / 84,4 |
| m2 `clk_i` | 119,9 / 128,9 / 145,3 | 125,6 / 133,3 / 154,5 |
| hold kršenja (zbroj) | 0 | 0 |

- **Razlika među lancima je unutar raspršenja po seedovima.** Pi bit gs (seed 7) je slučajno bio najbolji `rclk` starog lanca.
  Novi lanac na istom seedu nije „gori alat", nego drugi smještaj.
- Sirovi podaci: `data_20261017/t5549/fmax_seeds.txt`, `builds.out`, skripta `sweep.sh`.
- Kod 8 gs seed buildova nije pokrenut gmpack, jer je `build_ber.sh` mijenjan dok su radili (bash čita skriptu u hodu).
  Njihov nextpnr log je potpun (`Program finished normally`), a Fmax je čitan iz loga, pa bit ovdje ne treba.

## 5. nextpnr PR #1849 (nije u nightlyju 20261016)

#1849 (7ba06cae8, 16.10. 12:19): dodaje vremenski luk COMBIN→OUT (gornja → donja polovica L2T4 u L2T5) i CP ulaze
(CINX/PINX/CINY/PINY) tretira kao ulaze LUT-a. Prije toga nextpnr za L2T5 put **nije javljao put ni frekvenciju**. Naše
netliste su `-luttree`, pa to izravno vrijedi za nas. Mijenja samo `delay.cc`, chipdb je isti.

Izgrađen je lokalno u radnoj mapi (pokus, nije zadani). Isti JSON i seedovi kao §4, `NEXTPNR=<7ba06cae8>`:

| (MHz) | 44a6c739 (nightly) min / medijan / max | 7ba06cae8 (+#1849) min / medijan / max |
|---|---|---|
| gs `rclk` | 41,0 / 45,9 / 48,0 (n=6) | 41,6 / 45,2 / 46,9 (n=5) |
| gs `tclk` | 69,7 / 72,3 / 83,8 | 69,4 / 77,8 / 83,0 |
| gs `clk_i` | 34,9 / 36,9 / 39,0 | 31,7 / 34,6 / 35,4 |
| m2 `rclk` | 63,1 / 72,1 / 81,8 | 61,3 / 67,1 / 72,4 |
| m2 `tclk` | 67,9 / 81,5 / 84,4 | 76,8 / 80,1 / 85,7 |
| m2 `clk_i` | 125,6 / 133,3 / 154,5 | 120,8 / 135,2 / 156,3 |
| hold kršenja | 0 | 0 |

- **Putovi preko COMBIN sada su u izvješćima** (7 od 11 logova ima `…COMBIN` u kritičnom putu; prije #1849 nijedan).
  Medijani `m2 rclk` (−5 MHz) i `gs clk_i` (−2,3 MHz) su nešto niži, jer je dosad dio putova bio neizmjeren.
- **I dalje je sve iznad potrebnog** (`rclk`/`tclk` ≥ 31,25, najmanje izmjereno 41,6 MHz). Bitovi iz nightlyja 20261016 dakle nisu
  bili „lažno zatvoreni" na SerDes taktovima.
- **Nalaz – router2 ne konvergira: gs seed 7 sa 7ba06cae8.**
  - Nakon 11 668 iteracija (19 min) stalno ostaje `overused=1`, pa je proces prekinut (`gs_np7ba_s7_router2_tail.txt`).
  - Između 44a6c739 i 7ba06cae8 je samo #1849. Drugo kašnjenje u placeru daje drugi smještaj, a na njemu router2 zapne.
  - Isti seed s 44a6c739 i s 3edea68e ruta se normalno.
  - Kad dođe nightly s #1849: ako gs build visi, uzmi drugi seed (11–15 su prošli) ili `ROUTER=router1`. Ne čekaj beskonačno.
- Podaci: `data_20261017/t5549/fmax_7ba06cae8.txt`, `sweep7ba.sh`, `build_nextpnr_7ba06cae8.sh`. Binar je pokus u radnoj mapi
  zadatka, nije trajan i nije zadani.

## 6. R1 upečen u bit

**Novi parametri u `ber_top.v`** (zadano -1 = staro ponašanje, provjereno u §3.3):
- `OV_CALIB`: ≥ 0 → `RX_CALIB_OVR = TX_CALIB_OVR = 1`, `RX_CALIB_VAL = TX_CALIB_VAL = OV_CALIB`;
- `OV_EQA_CKP_OFFSET`: ≥ 0 → `RX_EQA_CKP_OFFSET`, inače 1 kao dosad.
- `TX_SEL_PRE` ide kroz postojeći `OV_TX_SEL_PRE`.
- Test `tools/tests/test_r1_bake.py` (3 testa, yosys elaboracija): zadano ostaje CAL/OFFSET/PRE = 0/0/1/5; R1 pomiče točno
  `RX_CALIB_OVR`, `RX_EQA_CKP_OFFSET`, `TX_CALIB_OVR`, `TX_SEL_PRE`; kod ide u oba smjera.

```
LINK=ber_link_gs.v FREQ=40 ./build_ber.sh gs 2g5r1_oss1016 7 $P OV_CALIB 0 OV_TX_SEL_PRE 0 OV_EQA_CKP_OFFSET 0
FREQ=40 ./build_ber.sh m2 2g5r1_oss1016 2 $P OV_CALIB 0 OV_TX_SEL_PRE 0 OV_EQA_CKP_OFFSET 0
```

| | gs R1 | m2 R1 |
|---|---|---|
| bit | **`79b07795…`** | **`4a94fc99…`** |
| CMD_CFGRST | ✓ | ✓ |
| CC_SERDES prema `*_2g5_oss1016` | 4 B / **4 polja**: `RX_CALIB_OVR` 0→1, `TX_CALIB_OVR` 0→1, `TX_SEL_PRE` 5→0, `RX_EQA_CKP_OFFSET` 1→0 (`*_CALIB_VAL` = 0) | isto |
| Fmax rclk / tclk / clk_i | 43,42 / 74,08 / 33,72 (drugi smještaj nego bez R1) | 63,08 / 80,70 / 125,63 (isti kao bez R1) |

**Razlike prema JTAG receptu R1 (`link_gate.py --r1`):**
1. U labu se CAL0 piše **nakon** učitavanja, dakle nakon što je kalibracija već odradila svoje. Ovdje je OVR=1 od prvog
   takta. Krajnje stanje registra je isto. Je li isto i analogno stanje, nije provjereno: to je prvi kandidat za A/B na ploči.
2. „DFE/EQA reset nakon učitavanja" je strob (0x2B), ne polje bitstreama. Prema TASK-5542 E-EQA strob ionako ništa ne mijenja.
   Učinak K8 dolazi od `RX_EQA_CKP_OFFSET=0`.

## 7. Kopija na Piju (bez učitavanja)

```
ssh pi@192.168.10.14 mkdir -p /home/pi/fpga/oss20261016; scp 4×.bit README.txt SHA256SUMS
/home/pi/fpga/oss20261016$ sha256sum -c SHA256SUMS → gs_2g5_oss1016.bit: OK  gs_2g5r1_oss1016.bit: OK
                                                     m2_2g5_oss1016.bit: OK  m2_2g5r1_oss1016.bit: OK
```

Ništa drugo na Piju nije dirano. Isti bitovi su u repozitoriju: `bitstreams/oss20261016/`.

## 8. Što je postavljeno kao zadano

| gdje | izmjena |
|---|---|
| `~/app/raid/tools/oss-cad-suite`, `~/Programs/oss-cad-suite` | poveznica → `oss-cad-suite-20261016` (prije → 20260923) |
| `gateware/ber/build_ber.sh` | zadano `OSS_CAD_SUITE=~/app/raid/tools/oss-cad-suite` (prije: što god je na PATH-u), zapis `<ime>.toolchain` |
| `gateware/eye_cc/build_eye.sh`, `gateware/baseline/build.sh`, `pr_build/build_pr.sh`, `tools/tests/test_cdr_cki_param.py` | zadano `oss-cad-suite` (poveznica) umjesto `-20260923` |
| `~/.claude/skills/ULX5M-GS-ETH/SKILL.md` | odjeljak Toolchain: zadani lanac, zamjenski lanci, napomene |
| `regoc_system/docs/FPGA_LAB_ARHITEKTURA.md` | §7 Zadani lanac alata (commit `ce175ab`) |
| katalog | `tc-oss-cad-suite-20261016` kanonski. **Zamjenski** (status `zastario`, oznaka `zamjenski`, `zamijenio` = novi): `tc-oss-cad-suite-20260923`, `-20260928`, `tc-nextpnr-a2fix`, `tc-nextpnr-main-ad8527f`, `tc-nextpnr-gatemate-setuphold`, `tc-nextpnr-pr1810`. Ništa nije obrisano (P4=B). `katalog provjeri`: 11 grešaka prije i poslije, sve postojeće, nijedna nova |

**Povratak na stari lanac** (npr. za ponavljanje starog bita): `OSS_CAD_SUITE=~/app/raid/tools/oss-cad-suite-20260923 ./build_ber.sh …`
daje bajtno iste bitove kao prije (§3.3).

## 9. Što nije provjereno / sljedeće

- **Hardver:** nijedan novi bit nije učitan. Novi lanac znači novi smještaj, pa vrijedi REVIEW_INIT §9: ≥ 3 učitavanja po bitu
  prije dugog laba. Prijedlog za A/B kad se Pi oslobodi:
  - `*_2g5_oss1016` prema `*_2g5_auto`;
  - `*_2g5r1_oss1016` (R1 u bitu) prema `*_2g5_auto` + `link_gate.py --r1`.
- **Nightly 20261017** bi trebao sadržavati #1849. Kad izađe, preuzeti ga i ponoviti §3–§5 (`build_ber.sh` + `serdes_cmp.py`).
  Isto vrijedi za pravilo za sljedeće nadogradnje: nova inačica u `tools/oss-cad-suite-<datum>`, kvalifikacija iz §3, tek onda
  prebaciti poveznicu.
- `tools/tests/test_si.py`: 2 testa padaju zbog nedostatka `scipy` u sustavnom pythonu. To nije vezano uz ovaj zadatak.
  Ostalih 197 testova + 6 `pr_build` testova prolazi.
