# Pregled repozitorija chili-chips-ba/openCologne-PCIE: što možemo iskoristiti za GS↔M2 SerDes — TASK-5557, 17.10.2026

**Zahtjev:** Goran, 17.10.2026. 11:09 (Telegram, grupa REGOČ): „istraži taj repo što sve ima na njemu; možda ima još nešto što
možemo iskoristiti, kao to što pišu model, pa ćemo barem znati kako se sve mora ponašati.” **Napisala:** Manda (istraživanje).
**Ploče i Pi nisam dirala.** Sve u ovom dokumentu je čitanje koda i simulacija na poslužitelju.

- **Repo:** https://github.com/chili-chips-ba/openCologne-PCIE, `main` @ `a3cb12f` (17.10.2026. 00:52 PDT). Klon je u
  `~/app/raid/projekti/openCologne-PCIE`, a podmoduli (`colognechip/gatemate-pipe`, grana `dll_test` @ `5d34d20`) su inicijalizirani.
- **Simulator:** Icarus Verilog 14.0 (devel) i Yosys iz `oss-cad-suite-20261016`, što je zadani lanac od 17.10.
- **Naš testbench i svi izlazi:** `docs/data_20261017/t5557/` (popis u §7).

Oznake: **IZMJERENO** (pokrenuto ovdje, izlaz priložen), **IZ KODA** (pročitano u kodu ili README-u repoa), **IZVEDENO**, **PRETPOSTAVKA**.

---

## 0. Kratki odgovor

1. **Repo je PCIe Gen1 x1 EndPoint za GateMate** (NLnet, BSD-3-Clause). Sadrži soft DLL, MAC/LTSSM i PIPE sloj iznad `CC_SERDES`.
   Ima i **otvoreni ponašajni model GateMate SerDesa** (`2.rtl/1.phy/2.serdes-model/ccfpga_serdes.v`, Anes Vrce, 13.10.2026).
   Njihova **M.2 kartica je naša ULX5M-M2** (`1.pcb/README.md` vodi na intergalaktik/ulx5m-m2). Na hardveru **nema objavljenog
   PCIe linka ni BER mjerenja** na GateMateu. Odjeljak „Debug, Bringup” je doslovno preuzet s Artix-7 (openPCIE). EVK PRBS test u
   `1.serdes-tests` je kostur bez rezultata.
2. **Model je protokolni (digitalni), ne analogni.** Vjerno modelira PLL (formula linijske brzine), 8b/10b, poravnanje na
   zarez, elastične spremnike, PRBS, električni idle, detekciju prijemnika, loopback i **RX/TX reset sekvencer s
   `RX_WAIT_CDR_LOCK`**. **Ne modelira** PMA ni analogni dio: TX FFE (`TX_SEL_PRE/POST`), AFE, **DFE/EQA adaptaciju**,
   terminaciju i `RX_CALIB`, eye scan, ADPLL i BISC. Njihovi statusni registri „vraćaju gotovo”. Vjernost je provjerena
   **samo na podatkovnom putu** prema NDA modelu proizvođača (400 riječi, 0 razlika, ista latencija 736 ns, Gen1 2,5 Gb/s).
   Registarska datoteka nije uspoređivana.
3. **Na pitanje iz CALIBRATION_OPTIONS §0 (zašto se readback `CKP_LF/HF/OFFSET` i 0x2B ne slaže s upisom) model ne može
   odgovoriti.** IZMJERENO u našem testbenchu (§4, R1): u modelu je regfile **obični RAM**, pa je readback = upis za 0x03, 0x04 i
   0x2B (5/5). Vrijednosti iz regfilea ne mijenjaju ponašanje (osim PLL/0x5C). Početna vrijednost je 0x0000, a ne parametar
   (0xA3A3). Naš kvar na siliciju (0/6, 0/6, 17/58) je dakle **ponašanje silicija koje model izostavlja**. Rang hipoteza ostaje
   kao kod Kosjenke: polja posjeduje EQA/reset FSM i blokirani upis tiho propada. Jedini put do odgovora bez ploče je da
   **netko s NDA modelom** (Anes Vrce / Cologne Chip) pusti naš R1 test na modelu proizvođača (§5, stavka 3).
4. **`RX_WAIT_CDR_LOCK` (Kosjenkin kandidat O-c) model pokazuje jasno.** IZMJERENO, M2 se pali prvi, a GS 20 µs kasnije (naš
   redoslijed): s **0** (naši bitovi) M2 `rx_resetdone` raste **14,4 µs prije CDR locka**, dok na liniji još nema signala. S
   **1** raste 1,1 ns **nakon** locka. To je ponašanje reset-FSM-a po DS1001, a ne ponašanje EQA. Pokazuje da danas PCS
   (i, po DS-u, EQA) pušta iz reseta bez zaključanog CDR-a.
5. **EQA reset u modelu ne radi ništa** (IZMJERENO R4: impuls na `rx_eqa_reset_i` i 0x2B daje 0 padova locka i 0 grešaka;
   `rx_eqa_reset_i` nije spojen ni na što u modelu). CDR reset radi (R5: lock pada 1×, relock, 38 bitnih grešaka). Dakle, „bacanje
   kocke” koje vidimo na siliciju (§1.2 Kosjenke) **ne postoji u modelu** i ne može se ondje proučavati.
6. **Dva ograničenja modela koja smo sami pronašli** (bitno ako ga koristimo): (a) **PRBS31 ruši link u modelu.** Detektor idlea
   ima prozor od 20 UI, a PRBS31 ima nizove do 31 istog bita. Rezultat je 15 lažnih idle događaja, 8 padova CDR locka i desetci
   tisuća grešaka u 100 µs. Model je pisan za 8b/10b (najviše 5 istih bitova). Za BER u modelu treba PRBS7 ili 8b/10b.
   (b) **Pomak takta od +100 ppm između dviju instanci zaglavi simulaciju**: u 60 s stigne do 25 µs, a cijeli test (176 µs) ne završi ni u 10 min. +250 ppm i 0 ppm rade
   normalno (~14 s). Uzrok nisam izolirala (PRETPOSTAVKA: zaokruživanje realnog UI na rešetku 100 fs u CDR/EI petlji).
7. **Najkorisnije za nas (rang u §5):** (1) model kao **brzi „digitalni blizanac” GS↔M2 linka** za naš reset/bring-up slijed,
   `link_gate` logiku, poravnanje i 8b/10b put (14 s po pokretanju, bez ploča). (2) **Test `RX_WAIT_CDR_LOCK=1` na pločama**,
   sada s modelom koji pokazuje što se mijenja. (3) **Kontakt s Anesom Vrceom i Hai Luongom** (RWTH/Cologne Chip, gatemate-pipe)
   radi pokretanja R1 na NDA modelu. (4) **CC PIPE referentni set** (EN_EQA 0, bez FFE, TX_CALIB 0) kao krak „B-static”. On je
   već predložen u `SERDES_UMJERAVANJE_KAKO_DRUGI_20261015.md` §2.5; ovaj repo ga samo potvrđuje na novijem `dll_test` commitu.
   Za 5G repo nema ništa: sve je Gen1, a Gen2 je „best effort”.

---

## 1. Inventura repozitorija (IZ KODA)

| Mapa | Što je | Stanje | Korist za nas |
|---|---|---|---|
| `0.doc/` | PCIe base spec 2.1, CEM 4.0, MindShare PCIe 3.0, Southwell „PCIe primer”, crteži, logotipi, `using-busybox-devmem` | referentna literatura | mala (spec, ako ikad radimo PCIe) |
| `1.pcb/` | README: M.2 kartica = **intergalaktik/ulx5m-m2** (naša), Edge kartica tek skica (ULX4M-PCIe-IO) | RevA M.2 ✔, Edge ✗ | potvrda da projekt cilja **našu** M2 ploču |
| `2.rtl/0.doc/` | DLL nacrti (svibanj–srpanj 2026), `GateMatePCIE--2026-09-04.pdf`, `TL_DPLL`, drawio | dokumentacija dizajna | mala |
| `2.rtl/1.phy/` | README PHY sloja (slike PIPE i SerDes blokova, citati iz razgovora CC↔chili-chips) | opisno | srednja (slika SerDes bloka) |
| `2.rtl/1.phy/1.serdes-tests/PRBS-Loopback-Test-for-GateMate-EVK/` | `serdes_top.v` + `Pins.ccf` za CC EVK (10 MHz): PRBS7 vanjska petlja, PLL preko regfilea (0x51=0x16FA, 0x5C=1, 0x50=0x0C03), auto-oporavak RX/CDR reseta nakon ~300 ms greške, LED-ovi | **kostur**: README „to fill with details”, nema rezultata. `TX_PAT` je zakomentiran, pa ga Yosys implicitno deklarira (1 bit). `25'h20000FF` treba 26 bitova, pa je impuls oporavka 255 taktova umjesto ~33 M | mala. Ideja auto-oporavka (CDR reset nakon trajne greške) već postoji kod nas kao vrata |
| **`2.rtl/1.phy/2.serdes-model/`** | **Otvoreni ponašajni model `ccfpga_serdes`** (1 modul, 1243 retka) + 8b/10b koder i dekoder + `0.doc/equivalence-checking.md` | objavljen 13.10.2026. (f48f026); issue #5 je i dalje otvoren, a 17.10. u njemu je komentar s poveznicom na model | **velika**, vidi §3–4 |
| `2.rtl/2.pipe/pipe_src` (podmodul) | **colognechip/gatemate-pipe** `dll_test`: `ccfpga_pipe_wrapper.v` (**`CC_SERDES` s punim popisom parametara**, PCIe set proizvođača), PIPE FSM, poravnanje riječi, MAC i DLL izvori, `testcase_pipe.v` | aktivno (Hai Luong, 13.10.) | **srednja**: referentni CC parametri i bring-up |
| `2.rtl/3.mac/` | README MAC/LTSSM; izvor je isti podmodul gatemate-pipe | | mala |
| `2.rtl/4.dll/` | DLL (CRC, retry, FC, DLLP) + sim | aktivno | nikakva za SerDes |
| `2.rtl/ip.infra/` | SoC sitnice (UART, FIFO, CSR, fabric) | | mala |
| `3.sw/` | plan TestAppa (RPi, Artix-7, PC) | prazno | nikakva |
| `4.build/formal/` | Yosys SAT dokazi za 8b/10b (5 svojstava) + iscrpna provjera dekodera | radi (IZMJERENO 6/0) | mala (8b/10b imamo u siliciju) |
| `5.sim/` | Tokovi: `serdesflow_dll` (EP↔RC, cijeli stog na modelu), `serdesflow_mod` (PIPE testcase, open ili NDA model), `serdesflow_equiv` (model prema NDA modelu), `phy_pipe_serdes.v` (PIPE + SerDes s bring-up FSM-om), pcieVHost i VProc kosimulacija, RV32 ISS | radi (§2) | **srednja**: gotovi tb obrasci za dvije instance preko serijske veze |
| `6.litex/` | samo poveznice na LitePCIe PHY za Gowin i Lattice | prazno | nikakva |
| `LICENSES/` | Apache-2.0, BSD-3, CC0, GPL-3.0+, MIT. GitHub prijavljuje BSD-3-Clause | datoteke modela nemaju SPDX zaglavlje | model smijemo koristiti uz BSD-3 (PRETPOSTAVKA: licenca repoa vrijedi za sve datoteke bez zaglavlja) |

**GitHub (API, 17.10.):** 100 zvjezdica, 8 forkova, wiki uključen, ali prazan (preusmjerava na repo). 12 otvorenih issuea, svi
o PCIe sloju: #8 PCLK u 64-bitnom PIPE-u je pola brzine riječi SerDesa, #9 K-oznake, #10 scrambler, #12 LTSSM, #14 regresija,
#4 x2/x4 na PCB-u. **Nijedan nije o SerDes analogu, kalibraciji ni BER-u.** PR-ovi su samo dependabot (#15, #16).

**Stanje projekta (IZ KODA, README „Project Status”):** označeno je ✔ za PHY s PIPE x1 Gen1, DLL i TL RTL te M.2 RevA. Ostalo je
otvoreno: Gen2 (best-effort), implementacija u GateMateu i zatvaranje vremena, bring-up, SW i LiteX. **Ploča:** CC EVK (serdes
testovi) i ULX5M-M2 (plan). **Brzina:** 2,5 Gb/s. Nema mjerenja na hardveru.

---

## 2. Upstream tokovi, pokrenuti ovdje (IZMJERENO)

| Tok | Naredba | Ishod | Vrijeme |
|---|---|---|---|
| DLL + MAC + PIPE + open SerDes, EP↔RC preko 2,5 Gb/s | `5.sim/serdesflow_dll` | `SUMMARY: 0 errors, TEST PASSED` (DL_Active, TLP-ovi u oba smjera, NAK/replay, UpdateFC) | 15,6 s |
| PIPE testcase proizvođača, 64 bit, open model | `echo 2 \| SERDES_MODEL=open 5.sim/serdesflow_mod` | **101/101** „Task … completed without Errors” | 15,2 s |
| Formalni dokazi 8b/10b | `4.build/formal/run_formal.sh` | `6 proved, 0 failed` | < 10 s |
| Samoprovjera modela | `5.sim/serdesflow_equiv` | **pada s Icarusom 14**: `bhv_aligned` se koristi prije deklaracije (`tb_serdes_equiv.v:130`). README traži Icarus 12 | 0,15 s |
| Isto, uz zakrpu redoslijeda deklaracija (`fix_equiv.py`, testbench se ne mijenja funkcionalno) | vidi §7 | `400 words checked, 0 mismatches`, latencija **736,0 ns**, `RESULT: PASSED` | 1,1 s |

Usporedbu s NDA modelom (`--ref`, `--cross`) ne možemo pokrenuti jer nemamo izvore proizvođača. Brojke za nju su iz njihovog
README-a: 0 razlika, 0 neslaganja u oba smjera, delta latencije 0,0 ns.

---

## 3. SerDes model: što je, na čemu počiva, koliko je vjeran (IZ KODA)

**Na čemu počiva.** Model je napisan kao zamjena za simulacijski model proizvođača, koji je pod NDA i nije u repou (issue #5,
README modela). Ima isto ime modula (`ccfpga_serdes`), iste portove i iste parametre. Ponašanje je kalibrirano **prema NDA
modelu**, a ne prema siliciju: latencija RX cjevovoda (`BHV_RX_PIPE_STAGES=9`) i vrijeme PLL locka (`35200 ns` = vrijeme
proizvođača) uzeti su iz njega. Mapa adresa (0x00–0x42 RX/TX, 0x50–0x5B PLL, 0x5C SERDES_CFG) je iz DS1001. **Mjerenja na
siliciju nema.** Autor je Anes Vrce (commit f48f026, 13.10.2026). Bilješka o verifikaciji objašnjava zašto LEC ne vrijedi
za cijeli SerDes: model proizvođača nije sintetizabilan, a ova dva modela namjerno nisu isti stroj.

**Što modelira i koliko vjerno:**

| Blok | Modelirano | Ne modelirano / razlika prema siliciju |
|---|---|---|
| Regfile / cfgfile | adrese, maskirani upis, `regfile_rdy_o`, dekodiranje `serdes_en` i `en_adpll_ctrl`, PLL_CFG0/1 zaključani dok radi ADPLL | **obični RAM**: početna vrijednost 0 (a ne parametar), nema zaključavanja polja, nema W/C bitova, nema statusa iz FSM-a. Upis u 0x00–0x42 **ne utječe na ponašanje** (ponašanje dolazi samo iz parametara) |
| PLL | `f_line = f_ref·N1·N2·N3·2/M3`, jezgreni takt = f_line/80, f_ref mjeri iz `clk_ref_i` | `PLL_FCNTRL`, CI/CP, BISC i SAR se ignoriraju; lock nakon fiksnog `BHV_PLL_LOCK_TIME_NS` |
| TX | 8b/10b s RD, prisilni disparitet, bypass, elastični spremnik, serijalizator, EI, polaritet, PRBS7/15/23/31 + ubacivanje greške | **`TX_SEL_PRE/POST`, `TX_AMP`, grane, `TX_CALIB` nemaju učinak** (idealan digitalni izlaz) |
| Kanal | po jedan događaj po UI na P/N | idealan: bez gubitaka, ISI, šuma i jittera (tb može dodati kašnjenje) |
| RX CDR | bang-bang fazni detektor, pojačanje `BHV_CDR_KP=0,125`, lock nakon 32 ruba u prozoru ±UI/4 | **`RX_CDR_CKP/CKI/LOCK_CFG/TRANS_TH` se ignoriraju**; lock pada kad uzorkivač stane (EI ili reset) |
| RX EQA/AFE/DFE | — | **ne postoji**: `RX_EN_EQA`, `CKP_LF/HF/OFFSET`, `TH_MON`, `TAPW`, `AFE_*` nemaju učinak. **`rx_eqa_reset_i` nije spojen** ni na što, a `RX_EQA_RESET_TIME` samo produljuje brojač reset-FSM-a |
| RX PCS | zarez (poravnanje kao zahtjev za hvatanje, prvi zarez nakon brida), klizanje bitova, polaritet, 8b/10b dekodiranje s `not_in_table` i `disp_err`, elastični spremnik, PRBS provjera | — |
| Reset FSM | TX: brojač `(PMA+PCS+2)·2^PRESC`. RX: `(PMA+EQA+CDR+PCS+BUF+5)·2^PRESC`, a zatim **čeka CDR lock ako je `RX_WAIT_CDR_LOCK=1`** | silicij (DS1001) ima stvarne faze (PMA → EQA → CDR → PCS → BUF). Model ih sažima u jedan brojač |
| EI detektor | prozor 20 UI | silicij ima analogni detektor ovojnice (`RX_EI_BIAS/BW_SEL` se ignoriraju) |
| Ostalo | detekcija prijemnika (fiksni ishod), PCS i PMA loopback, kašnjenje izlaza 100 ps | eye scan, scan lanac i SRAM debug ne postoje |

**Sažetak vjernosti (IZVEDENO):** za sve što vidi PIPE ili fabric (takt, reset-done, poravnanje, 8b/10b, latencija) model je
dovoljno vjeran da prođe testcase proizvođača i da križno radi s NDA modelom. Za sve što nas zanima u kalibraciji (FFE, EQA,
CDR petlja, terminacija, readback analognih polja) **nije vjeran ni po zamisli**. U njemu će svaka naša postavka „raditi”,
jer kanal nema gubitaka i analognog dijela nema.

**Kako ga spojiti na naš kod.** Naš `ber_top.v` instancira `CC_SERDES` (portovi velikim slovima, `REGFILE_CLK_I`, bez
`clk_ref_i`/`cfg*`). Model je `ccfpga_serdes` s portovima malim slovima. Uz to, u modelu nema parametara `RX_CALIB_EN`,
`RX_EN_EQA_EXT_VALUE`, `RX_CDR_TRANS_TH`, `TX_CALIB_EN` ni `SERDES_*`, koje mi postavljamo. Za puni `ber_top` treba **omotač
`CC_SERDES → ccfpga_serdes`** od oko 150 redaka: preimenuje portove, odbaci parametre kojih nema, a `SERDES_ENABLE` pretvori u
upis cfgfilea 0x5C. Upstream to izbjegava tako da u simulaciji izostavi `ccfpga_pipe_wrapper.v` i instancira `ccfpga_serdes`
izravno (`5.sim/phy_pipe_serdes.v` r. 266). Za ovaj zadatak omotač nije bio potreban.
Napisala sam samostalni testbench s dvije instance (§4).

---

## 4. Model s našim postavkama: GS↔M2 u simulaciji (IZMJERENO)

**Testbench:** `docs/data_20261017/t5557/tb_gsm2_model.v`. Ima dvije instance modela (GS, M2) križno spojene preko kanala od 5 ns,
na 2,5 Gb/s, uz +250 ppm na referentnom taktu M2. Postavke su naše gdje ih model prima: PROFILE 1 + R1, `RX_RESET_TIMER_PRESC 4`,
reset vremena 3, **R1/CAL0** (`RX/TX_CALIB_OVR 1, VAL 0`), `RX_EN_EQA 1`, `CKP_LF/HF 0xA3`, **`CKP_OFFSET 0`**, `EQA_LOCK_CFG 0xC`,
`AFE_PEAK 0x18`, `GAIN 0`, `CDR_CKP 0x3E`, **`TX_SEL_PRE 0`**, `POST 5`, `AMP 31`, datapath 64 bit, `ALIGN_COMMA_WORD 3`.
Redoslijed je naš: M2 se pali prvi, GS 20 µs kasnije. Bring-up je po DS1001 (0x5C=1, 0x50=2, pa 3). Napomena: većina ovih
analognih parametara u modelu nema učinka (§3). Upisani su da tb odgovara našem bitu, a ne zato što ih model koristi.

| # | Provjera | `RX_WAIT_CDR_LOCK=0` (naši bitovi) | `RX_WAIT_CDR_LOCK=1` (DS1001 zadano) |
|---|---|---|---|
| R1 | 0x03 prije upisa | 0x0000 (parametar je 0xA3A3) | isto |
| R1 | 0x03 ← 0x8383 → readback | **0x8383 = upis** | isto |
| R1 | 0x04 ← [8]=1, [7:0]=0x00 → readback | **0x0100 = upis** | isto |
| R1 | 0x2B ← [3:2]=11, pa 00 → readback | **0x000C, pa 0x0000 = upis** | isto |
| R2 | M2 `rx_resetdone` prema M2 CDR locku | **14 370,7 ns PRIJE locka** (12 890,7 / 27 261,4 ns) | **1,1 ns NAKON locka** (27 262,5 / 27 261,4 ns) |
| R2 | GS `rx_resetdone` prema GS CDR locku | 10 227,8 ns nakon (signal M2 već postoji) | isto |
| R3 | PRBS7 100 µs (250 kbit po smjeru), M2→GS / GS→M2 | **0 / 0 grešaka**, 0 idle događaja, 0 padova locka | 0 / 0 |
| R4 | GS EQA reset: pin 8 taktova + 0x2B impuls | 0 padova locka, 0 padova reset-done, **0 grešaka** (nema učinka) | isto |
| R5 | GS CDR reset: pin 8 taktova | lock pada 1×, reset-done pada 1×, relock, **38 grešaka** | isto |
| R3' | **PRBS31** (isti tb, `-Ptb.PRBS=4`) | M2→GS 29 457 / GS→M2 59 151 grešaka, **15 idle događaja, 8 padova locka** | — |

Trajanje: oko 14,5 s po pokretanju (176 µs simuliranog vremena).

**Što iz toga slijedi:**
- **Readback (§0 Kosjenke):** model ne reproducira kvar ni po kojem polju (5/5 readback = upis). Model zato ne može ni
  potvrditi ni oboriti hipotezu o zaključanim poljima. Kosjenkin test F1-b (upis CKP uz `RX_EN_EQA=0`) i dalje je jedini put
  na siliciju. Jedna sitna, ali korisna razlika: silicij za 0x03 vraća 0xA3 (= vrijednost parametra iz bita), a model 0x0000.
  Silicij dakle **puni regfile iz bitstreama**, a model ne. Ako na siliciju upis u 0x03 uz `RX_EN_EQA=0` vrati upisanu
  vrijednost, zaključavanje je potvrđeno. Ako i dalje vraća 0xA3, polje je nadjačano iz bita ili iz FSM-a (PRETPOSTAVKA za F1).
- **`RX_WAIT_CDR_LOCK`:** u modelu s 0 PCS izlazi iz reseta dok kanal još šuti, i to je stanje u kojem danas palimo M2.
  S 1 izlaz iz reseta čeka lock. Učinak na **EQA** model ne može pokazati (EQA ne postoji). DS1001 ga opisuje istim redoslijedom
  faza, pa je to razlog više da se O-c (`RX_WAIT_CDR_LOCK 1` u bitu) ispita na pločama. Uz 1 vrijedi i upozorenje iz
  koda: komentar „turn off if loopback enabled” odnosi se na PMA loopback, koji mi ne koristimo u GS↔M2 linku.
- **EQA „bacanje kocke”** (CALIBRATION_OPTIONS §1.2) u modelu ne postoji. Model je zato bezvrijedan za lutriju i za BER-pod.
- **Za BER i soak u modelu koristiti PRBS7 ili 8b/10b.** PRBS31 ruši model (R3'). Na siliciju to ne vrijedi: ondje PRBS31 nije
  problem, osim ako je uključen `RX_EN_EI_DETECTOR`.

---

## 5. Popis iskoristivog, rangirano po koristi za GS↔M2 2,5G/5G

Trud: S = sati, D = dani. „Korist” znači koliko pomiče prolaz iz 1. pokušaja, BER-pod ili 5G.

| Rang | Što | Odakle | Korist | Trud | Napomena |
|---|---|---|---|---|---|
| 1 | **`RX_WAIT_CDR_LOCK 1` (+ dulji `RX_CDR_RESET_TIME`) u upečenim bitovima, A/B kroz vrata, 20 učitavanja po kraku** | model §4 R2, DS1001, Kosjenka O-c | srednja do velika za lutriju i 5G CDR (gs 5G CDR_LOCKED 0 u 7/9) | 0,5 D (build + Jelenin lab) | model pokazuje mehanizam, a dokaz učinka mora doći s ploča |
| 2 | **Model kao digitalni blizanac našeg linka**: omotač `CC_SERDES→ccfpga_serdes`, pa naš `ber_top`/`ber_link` (GS i M2) preko modela umjesto stuba `gateware/ber/sim/stubs.v` | `2.serdes-model` + naš tb | srednja: regresija reset/bring-up slijeda, poravnanja, `link_gate` logike i brojila grešaka bez ploča, u ~15 s | 1 D | današnji stub je kratka petlja bez CDR-a, reset-FSM-a i 8b/10b |
| 3 | **R1 readback test na NDA modelu proizvođača**: pošaljemo `tb_gsm2_model.v` (R1 dio) Anesu Vrceu ili Haiu Luongu i pitamo vraća li vendor model 0xA3 i štiti li 0x03/0x04[7:0]/0x2B | autori (§6) | velika za O1/F1 ako NDA model modelira zaključavanje | 1 S (poruka) + čekanje | njihov `serdesflow_equiv --ref` već ima sve; R1 su 4 upisa i čitanja. Vanjska poruka, **Goran odlučuje** |
| 4 | **CC PIPE referentni RX set kao krak „B-static”**: `RX_EN_EQA 0`, `PEAK 15`, `GAIN 8`, `CDR_CKP 0xF8`, `TX_SEL_PRE/POST 0`, `AMP 30`, `TX_CALIB_EN 0`, `WAIT_CDR_LOCK 0` | `ccfpga_pipe_wrapper.v` parametri r. 4–215, instanca `CC_SERDES` r. 218–418 (`dll_test` 5d34d20) | srednja: drugi izvor istog seta | 0,5 D | već predloženo u SERDES_UMJERAVANJE §2.5 t. 1. Ovdje samo potvrđeno na commitu od 13.10. |
| 5 | **Obrazac auto-oporavka iz EVK testa**: trajna PRBS greška → `RX_CDR_RESET` + `RX_RESET` + reset brojila | `serdes_top.v` r. 91–110 | mala: naša vrata to već rade (ponovno učitavanje ili EQA reset) | 1 S | ima dvije greške (§1). Uzeti ideju, ne kod |
| 6 | **Formalni 8b/10b dokazi i iscrpna provjera dekodera** | `4.build/formal` | mala: korisno samo ako pišemo vlastiti fabric 8b/10b (npr. za 5G bez PCS-a) | 1 S | |
| 7 | **PIPE/MAC/DLL stog i pcieVHost VIP** | `2.rtl/2.pipe`, `4.dll`, `5.sim` | nikakva za GS↔M2. Velika ako M2 jednom ide u PCIe utor (Gen1) | D–tjedni | issue #8 (PCLK na pola brzine): stog još nije trenirao link sa stvarnim partnerom |
| 8 | **Literatura** (PCIe 2.1 spec, CEM 4.0, Southwell primer) | `0.doc` | mala | — | |
| — | **5G** | — | **ništa**: sve je Gen1 2,5 Gb/s, a Gen2 je „best effort” bez koda | — | za 5G ostaje naš plan (CALIBRATION_OPTIONS §5) |

---

## 6. Ljudi i kontakti (IZ KODA, git shortlog i GitHub)

| Tko | Uloga u repou | Zašto nam treba |
|---|---|---|
| **Anes Vrce** (AnesVrce, anes.vrce@chili-chips.xyz) | autor otvorenog SerDes modela, `serdesflow_*`, issuei #8–#13 | ima pristup NDA modelu i alat za usporedbu, pa je idealan za stavku 3 |
| **Vinh Hai Luong** (RWTH Aachen, hai.luong@rwth-aachen.de) | gatemate-pipe (Cologne Chip), PIPE/MAC, `ccfpga_pipe_wrapper.v` | izvor CC PCIe postavki i bring-upa |
| **Chili.CHIPS** (ask@chili-chips.xyz) | vlasnik projekta (104 commita) | koordinacija; projekt cilja našu ULX5M-M2 |
| Simon Southwell (wyvernSemi) | pcieVHost VIP, kosimulacija | samo ako idemo u PCIe |
| Mujo Sejdić, Kemal Likić | EVK SerDes loopback testovi (README) | jedini u projektu koji rade na SerDes hardveru; rezultata još nema |
| Minela Sultanović | sim tokovi (64-bitni PIPE testcase) | — |

Patrick Urban (Cologne Chip, pu-cc/gm_serdes_lb) u ovom repou ne sudjeluje. On ostaje naš izvor za silicij (PR #20 mape 0x2B).

---

## 7. Ponovljivost

Svi izlazi su u `docs/data_20261017/t5557/`: `tb_gsm2_model.v`, `fix_equiv.py`, `run_wait0_prbs7.out`, `run_wait1_prbs7.out`,
`run_wait0_prbs31.out`, `upstream_equiv_patched.out`, `upstream_equiv_unpatched_iverilog14.out`, `upstream_formal.out`,
`upstream_dll_tail.out`, `upstream_pipe64_summary.out`.

```sh
export PATH=~/app/raid/tools/oss-cad-suite/bin:$PATH
R=~/app/raid/projekti/openCologne-PCIE; M=$R/2.rtl/1.phy/2.serdes-model
D=~/app/raid/projekti/ulx5m-litex-ai/ulx5m-gs-m2-serdes/docs/data_20261017/t5557
# naš GS<->M2 tb (WAIT_CDR 0/1, PRBS 1=PRBS7 / 4=PRBS31, PPM, GS_DELAY_NS su parametri)
iverilog -g2012 -I $M -Ptb.WAIT_CDR=0 -o w0.vvp $M/ccfpga_serdes.v $D/tb_gsm2_model.v && vvp -N w0.vvp
iverilog -g2012 -I $M -Ptb.WAIT_CDR=1 -o w1.vvp $M/ccfpga_serdes.v $D/tb_gsm2_model.v && vvp -N w1.vvp
# upstream
(cd $R && git submodule update --init)
SERDES_BUILD_DIR=$PWD/sim bash $R/5.sim/serdesflow_dll                 # TEST PASSED, 0 errors
(cd $R/5.sim && echo 2 | SERDES_BUILD_DIR=$PWD/sim SERDES_MODEL=open bash serdesflow_mod)   # 101 x completed without Errors
(cd $R/4.build/formal && bash run_formal.sh)                              # 6 proved, 0 failed
python3 $D/fix_equiv.py $R/5.sim/tb_serdes_equiv.v tb_equiv_fixed.v       # Icarus 14: deklaracija prije upotrebe
iverilog -g2012 -gspecify -Ttyp -DPIPE -I $M -o eq.vvp $M/ccfpga_serdes.v tb_equiv_fixed.v && vvp -N eq.vvp  # PASSED
```

Pazi: s `-Ptb.PPM=100` simulacija zapne (§0 t. 6b). Koristi 0 ili 250.

---

## 8. Izvori

- [R1] github.com/chili-chips-ba/openCologne-PCIE @ a3cb12f: `README.md`, `2.rtl/1.phy/README.md`,
  `2.rtl/1.phy/2.serdes-model/{README.md, ccfpga_serdes.v, 0.doc/equivalence-checking.md}`, `5.sim/{serdesflow_*, tb_serdes_equiv.v}`,
  `1.pcb/README.md`, `2.rtl/1.phy/1.serdes-tests/PRBS-Loopback-Test-for-GateMate-EVK/serdes_top.v`.
- [R2] github.com/colognechip/gatemate-pipe, grana `dll_test` @ 5d34d20: `src/pipe_src/ccfpga_pipe_wrapper.v`, `ccfpga_pipe_logic.v` r. 208–212.
- [R3] GitHub API, 17.10.2026: repo, issues #1–#14, PR #15–#16 (issue #5 „Create behavioral model”, #8 PCLK).
- [L1] `CALIBRATION_OPTIONS_20261017.md` §0, §1.1–1.2 (Kosjenka, TASK-5553).
- [L2] `SERDES_UMJERAVANJE_KAKO_DRUGI_20261015.md` §2.5 i [C11] (CC PIPE set).
- [L3] `gateware/ber/cc_serdes_params.vh`, `gateware/ber/ber_top.v` (naši parametri, PROFILE 1, R1).
