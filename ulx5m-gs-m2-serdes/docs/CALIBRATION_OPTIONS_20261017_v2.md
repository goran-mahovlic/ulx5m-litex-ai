# Kalibracija GS↔M2 SerDes, v2: revizija zadataka, što mijenjaju nalazi TASK-5554/5557 i konačni plan izvedbe — TASK-5558, 17.10.2026

**Nalog:** Goran, 17.10.2026. 12:16: „treba vidjeti sve zadatke i revidirati ih i onda kalibrirati do kraja sve i testirati”.
**Napisala:** Kosjenka (arhitektura). **Ploče i Pi nisam dirala.** Novog mjerenja nema. Novi su izračun granica plana
(`data_20261017/t5558/plan_v2_stats.py`) i čitanje koda CC PIPE / openCologne-PCIE reset logike.
**Izvršitelj plana:** Jelena, TASK-5559. Plan je u §3 i to je jedini odjeljak koji treba za izvedbu.

Dokument **nadograđuje** `CALIBRATION_OPTIONS_20261017.md` (dalje: **v1**, TASK-5553, opcije O1–O14, faze F0–F5). v1 je napisan
prije Mandinih nalaza `RESEARCH_SERDES_USPOREDBA_20261017.md` (**5554**) i `OPENCOLOGNE_PCIE_PREGLED_20261017.md` (**5557**).
Gdje se v2 i v1 razlikuju, **vrijedi v2**. Oznake: **UTVRĐENO**, **POJEDINAČNO**, **PRETPOSTAVKA**, **IZVEDENO** (kao u v1).

---

## 0. Kratki odgovor

1. **Zadaci (§1):** TASK-5542 → zatvoriti kao nadmašen, **nakon** što Jelena commita njegov necommitani WIP (alat koji danas vrti
   Pi nije u gitu). TASK-5545 (p_r ↔ nextpnr) → zatvoriti kao nadmašen: CC_SERDES blok je bajtno isti (TASK-5546), a greške
   su linijske, ne fabric. TASK-5531 (flash) → spojiti u plan kao zadnji korak K8 (flash **konačnog** bita, ne lab39).
   TASK-5559 (Jelena) i TASK-5560 (Potjeh) → nastaviti, s ovim planom kao ulazom.
2. **Novo i važno za izvedbu: upečeni R1 bitovi nisu „R1 iz mjerenja”.** `gs 79b07795` / `m2 4a94fc99` imaju upečen
   `RX_EQA_CKP_OFFSET = 0`. Na pločama ta vrijednost **nikad nije bila aktivna**, jer JTAG upis ne drži (readback 1, v1 §1.1).
   „Dobitak K8” je bio od EQA reseta, ne od OFFSET 0. Zato ti bitovi ispituju **novu, neprovjerenu** točku. Osnovica plana je
   novi bit **B0′ = CAL0 + TX_SEL_PRE 0, OFFSET 1**. Postojeći R1 bit služi samo kao test „drži li polje iz bita” (K1-d).
3. **Što mijenja 5554 (§2.1): kriterij dokaza.** BER ≤ 10⁻¹² uz 95 % = **3,0·10¹² provjerenih bita bez greške po smjeru**
   (40 min na 2,5G), ili ≤ 1 greška u 63 min, ili **≤ 2 greške u 84 min**. Trajanje se **zadaje unaprijed**. Ne smije se stati
   „kad izgleda dobro”. Da bi takav soak prošao s vjerojatnošću 0,8, stvarni BER mora biti **≤ 2,4·10⁻¹³**. Danas je M2→GS
   2,2·10⁻¹¹, **≈ ×90 iznad toga**, a GS→M2 ≈ ×4. Zaključak: **završni soak ne dolazi prije nego K4 pokaže stvarni pomak poda.**
4. **Što mijenja 5557 (§2.2): reset slijed.** U modelu (i po DS1001) RX reset-FSM ide PMA → EQA → CDR → PCS → BUF.
   S `RX_WAIT_CDR_LOCK=0` (naši bitovi) M2 `rx_resetdone` raste **14,4 µs prije CDR locka**, a s 1 tek nakon locka. Cologne
   Chipov PIPE drži `WAIT_CDR_LOCK 0` i sve fabric RX resete na 0, ali **vozi statički RX (`RX_EN_EQA 0`)**. Mi imamo adaptivni
   EQA, pa njihova praksa za nas ne vrijedi. B1 (`WAIT_CDR_LOCK 1`) ostaje prvi pokus reset slijeda. Model ne modelira EQA, pa
   **učinak mora doći s ploča**. EVK test daje i drugi obrazac: RX + CDR reset nakon trajne greške. To je naš L1b/CDR razina.
5. **Što mijenja 5557 (§2.3): izvor neupisivih polja.** Model ima regfile kao obični RAM (readback = upis 5/5), pa naš kvar
   (0x03 0/6, 0x04[7:0] 0/6, 0x2B 17/58) **nije u modelu**. Ostaje ponašanje silicija. Rang uzroka: (a) zaštita od upisa dok
   je `RX_EN_EQA=1` (presedan u CC `serdestool.py`), (b) polje prepisuje FSM, (c) zaostajanje readbacka 0x2B. Silicij puni
   regfile iz bita (0x03 čita 0xA3 = parametar), pa je **put kroz bit vjerojatno ispravan**. Razrješava se na siliciju za
   ≤ 45 min (K1). Vanjski put je NDA model kod Anesa Vrcea, **ali o kontaktu odlučuje Goran**.
6. **Konačni plan (§3), redom:** K0 alat i bitovi (bez laba) → **K1 upis CKP_LF/HF/OFFSET i 0x2B** → **K2 reset slijed**
   (B0′/B1/B2 kroz vrata, „readapt” obje strane) → K3 dijagnoza poda (TX idle, 2×2 AMP) → **K4 TX/RX matrica po smjeru**
   (margina na stresnoj točki) → K5 brzina petlje EQA (samo ako je K1 otvorio put) → **K6 završna kvalifikacija** → K7 5G
   (nakon TP10/TP8) → K8 flash.
7. **„Kalibrirano do kraja” na 2,5G (§3.3):** (i) sve postavke u bitu, readback = namjera za svako polje; (ii) vrata iz
   1. pokušaja **≥ 28/30** (donja 95 % granica 0,805); (iii) **3 neovisna prihvaćena učitavanja × 84 min, ≤ 2 bitne greške po
   smjeru na svakom** (oba smjera istodobno, BER < 10⁻¹² uz 95 % na svakom), 0 gubitaka sinkronizacije. Za 5G vrijede
   zasebna vrata 5G-1/2/3.
8. **Goran (§4):** TP10 (VDD_SER) i TP8 (VDD_SER_PLL) DC multimetrom na obje ploče, s 2,5G pa s 5G bitom, i vrijednost
   R105/R106 (10 min). Bez toga nema K7 (5G). Uz to fotografija i tip FFC-a/adaptera, a za 5G refclk na M2 strani i AC šum
   osciloskopom.

---

## 1. Revizija otvorenih SerDes zadataka

Popis: `GET /api/tasks?projectId=PRJ-051`, 17.10. 12:2x. Otvoreno je 5 zadataka (4 blocked + ovaj). Pretraga cijele ploče
(„serdes”, „GS↔M2”) našla je još jedan SerDes zadatak u PRJ-033 (TASK-5531). Statuse ne mijenjam, a na svaki je upisana
bilješka s prijedlogom.

| Zadatak | Stanje | Prijedlog | Razlog | Što prelazi u plan |
|---|---|---|---|---|
| **TASK-5542** Jelena: vrata kvalitete, auto ponovno spajanje, mjerenje, 5G | blocked od 16.10. 22:07 („spawn izašao bez izvještaja”). Rezultati su ipak isporučeni kroz 5551 (soak R1) i 5552 (chain4, 5G P2, vrata) | **Zatvoriti kao nadmašen**, ali tek **nakon K0-a**: commit WIP-a | Točke 1–3 naloga su ispunjene (vrata postoje i rade: L3 5/15, soak 1800 s s CI). Točka 4 (5G) je pokušana: 9/9 bez locka, čeka TP10/TP8. **WIP u repou nije commitan:** `tools/lab/link_gate.py` (+64: `--r1`, `--eqarst`, `--diag-secs`, `rx_err`/PEER odabir lošeg RX-a), `calib_aba.py`, testovi i `data_20261016/t5542/calib/aba2.*`, `eeqa.*`. To je **verzija koja je vozila chain4 na Piju**. Bez commita je mjerni lanac neponovljiv | K0-a (commit WIP), K2 (vrata), K7 (5G) |
| **TASK-5545** Jelena: A/B p_r ↔ nextpnr bit na pločama | blocked (čeka 5542) | **Zatvoriti kao nadmašen** | TASK-5546: CC_SERDES blok p_r i nextpnr bita je **bajtno isti** (0/186 B, 0/252 polja). Revizija 16.10. §2.2: greške su linijske na 56/56 zapisa, a lutrija je analogna ili stanje reseta, ne fabric port. Razlika p_r/nextpnr je samo u smještaju fabrica i vremenu, a to K-krug već isključuje. A/B ≥ 5 + 5 učitavanja kroz vrata košta ≈ 2–3 h laba za malu očekivanu korist. **Iznimka:** ako K2 pokaže da lutrija ovisi o bitu, a ne o reset slijedu (npr. B0′ s različitim seedom daje drukčiji udio prolaza), oživjeti kao jedan krak u K2 | ništa obvezno; p_r bitovi ostaju na Piju (`/home/pi/fpga/pr`) kao rezerva |
| **TASK-5531** (PRJ-033) Jelena: lab39 recept → SPI flash, samostalno dizanje | blocked od 16.10. (čeka Goranov upis u flash, uputa #344) | **Spojiti u plan kao K8** (flash **konačnog** bita) | Bit koji je trebao u flash (`*_2g5_auto`, lab39: AMP 12) **nadmašen je** svim kasnijim nalazima (CAL0, PRE 0, reset slijed). Flash sada nema smisla. Kad K6 prođe, konačni bit ide u flash po istom postupku (Goran upisuje, P4 `p4_flash_boot.sh` mjeri bez JTAG-a). Napomena: zadatak je u PRJ-033 (pretinac), a pripada PRJ-051 | K8 |
| **TASK-5559** Jelena: kalibracija do kraja po konačnom planu + test | blocked (čekao je ovaj plan). Po uputi #352 Jelena radi paralelno | **Nastaviti** | Izvršitelj §3. Uputa s putanjom i ključnim točkama poslana je preko `/uputa` | cijeli §3 |
| **TASK-5560** Potjeh: neovisna provjera (readback, BER iz sirovih) | blocked (čeka 5559) | **Nastaviti**, uz kriterije iz §3.3 | Provjera „kalibrirano do kraja” mora imati unaprijed zapisane kriterije. §3.3 ih daje u obliku koji se provjerava iz JSONL-a (readback po polju, 28/30, k po smjeru u 5040 s) | §3.3, §3.5 |

Zatvoreni zadaci PRJ-051 (42 completed, 2 cancelled) nisu predmet revizije. Njihovi nalazi ulaze kroz v1 i dokumente 5541–5557.

---

## 2. Što mijenjaju nalazi TASK-5554 i TASK-5557

### 2.1 Kriterij dokaza BER ≤ 10⁻¹² (iz 5554 §4)

Izračun `data_20261017/t5558/plan_v2_stats.out` (isti brojevi kao Mandin `t5554/ber_cl.out`: 2397 / 3795 / 5037 s).

| Pravilo (po smjeru, provjereni bitovi 1,25·10⁹/s) | Bita | 2,5G | 5G | Stvarni BER za P(prolaz) ≥ 0,8 |
|---|---|---|---|---|
| 0 grešaka | 3,00·10¹² | **2400 s (40 min)** | 1200 s | ≤ 7,4·10⁻¹⁴ |
| ≤ 1 greška | 4,74·10¹² | 3795 s (63 min) | 1898 s | — |
| **≤ 2 greške** | 6,30·10¹² | **5040 s (84 min)** | 2520 s | **≤ 2,4·10⁻¹³** |

Što to mijenja u v1:
1. **F5 u v1 je imao „3 × 2400 s, 0 grešaka”.** Za isti dokaz (BER < 10⁻¹² uz 95 %) pravilo **≤ 2 u 5040 s** traži ×3 manje
   dobar link (2,4·10⁻¹³ umjesto 7,4·10⁻¹⁴ za P = 0,8) i manje je osjetljivo na jednu zalutalu grešku. Uzimam **84 min, k ≤ 2**
   kao glavno pravilo. 40 min, k = 0 ostaje kao brza varijanta: ako prođe, dokaz je isti. Ako ima ijednu grešku, ne
   produljuje se, nego se pokreće novi soak od 84 min.
2. **Trajanje je fiksno unaprijed.** Produljivanje dok se ne „skupi” dovoljno bitova (optional stopping) ruši razinu
   pouzdanosti. Soak se ne prekida ni zbog jedne greške. Završava se na zadanom vremenu i tek onda se presuđuje.
3. **Ne zbrajati učitavanja.** Svako učitavanje je drukčije izvlačenje (lutrija), pa je tvrdnja „po prihvaćenom učitavanju”.
   Zato su tri neovisna soaka, svaki sa svojim k (§3.3). Stari soak R1 (1800 s) **ne produljuje se** novim mjerenjem.
4. **Gdje smo (IZVEDENO):** uz R1 soak M2→GS bi u 84 min imao očekivano 140 grešaka, pa P(prolaz) ≈ 10⁻⁵⁷. Treba
   **≈ ×90** bolji M2→GS i ≈ ×4 bolji GS→M2. To ne mogu dati vrata ni retry (v1 §1.3: greške su Poissonove, stacionarni pod).
   Mogu dati samo poluge koje mijenjaju SNR (K3/K4) ili hardver (§4). **Ako K4 ne pomakne pod barem ×10 u M2→GS,
   2,5G „bez grešaka” na ovom hardveru nije dostižno registrima**, i to je legitiman ishod plana (§3.4).
5. **Vrata iz 1. pokušaja:** za tvrdnju p ≥ 0,8 (95 %, jednostrano) treba **15/15** (0,819) ili **28/30** (0,805). v1 F3 je
   pisao „≥ 16/20 = 0,8”, što je **netočno**: 16/20 daje donju granicu 0,60. Ispravak je u §3. Napomena: da bi stvarni link
   prošao 28/30 s vjerojatnošću 0,8, njegov stvarni udio mora biti ≈ **0,95** (0,9 prolazi samo u 41 %).

### 2.2 Reset slijed (iz 5557 §3–4, CC PIPE kod i EVK testa)

| Izvor | RX reset slijed | Čeka CDR lock? | EQA | Fabric reset portovi | Retry |
|---|---|---|---|---|---|
| DS1001 / model `ccfpga_serdes` | interni FSM: PMA → EQA → CDR → PCS → BUF (model sve sažima u brojač `(PMA+EQA+CDR+PCS+BUF+5)·2^PRESC`) | samo ako `RX_WAIT_CDR_LOCK=1` (model zadano 1) | model: ne postoji; `rx_eqa_reset_i` nije spojen | — | — |
| CC PIPE (`gatemate-pipe`, `ccfpga_pipe_logic.v` r. 204–212, 247, 355) | samo `PLL_RESET` iz fabrica, interni FSM radi ostalo; `s_reset_done` gleda samo TX | **0** | **isključen** (`RX_EN_EQA 0`, PEAK 15, GAIN 8) | TX/RX/PMA/PCS/CDR/EQA = 0 | LTSSM (Detect/Polling) u MAC-u |
| openCologne EVK test (`serdes_top.v` r. 91–110) | zadano | zadano | zadano | `RX_RESET_I` + `RX_CDR_RESET_I` | **da: nakon trajne greške RX + CDR reset** |
| **mi** (`ber_top.v` r. 112–114, `cc_serdes_params.vh` r. 1–10) | interni FSM, `PRESC 4`, vremena 3 | **0** (prepisano iz loopback primjera) | **uključen** (adaptivni, `LOCK_CFG 0xC`) | TX/RX/PLL = `rst` (512 taktova), ostali 0 | vrata: L3 (oba `-r`), L1 EQA reset preko 0x2B |

Zaključci (IZVEDENO):
1. **Kombinacija „WAIT_CDR_LOCK 0 + adaptivni EQA” nema nijedan referentni izvor.** CC je uz 0 vozi samo sa statičkim RX-om,
   kad nema adaptacije koja bi krenula na nezaključanom taktu. Model (R2) pokazuje da uz 0 PCS izlazi iz reseta 14,4 µs prije
   CDR locka, i to u našem redoslijedu paljenja (m2 prvi). → **B1 (`WAIT_CDR_LOCK 1`) ostaje prvi pokus K2.** Je li i EQA na
   siliciju vezan uz to čekanje, ne zna nitko: DS opisuje redoslijed, a model EQA nema. Zato se mjeri.
2. **„Readapt” = EQA reset obje strane nakon što su oba TX-a gotova** ostaje glavni slijed (v1 §1.4, O4). Novo iz 5557: CDR
   reset u modelu stvarno radi (R5: pad locka, relock), a EQA reset ne radi ništa. Na siliciju je EQA reset funkcionalan (v1 §1.2,
   2–4 dekade iz oštećenog stanja, 3/3). → K1-c mjeri **sve tri razine** (EQA, CDR, RX) funkcionalno, a ne readbackom.
3. **Krak „B-static” (CC PIPE RX set na našem TX-u)** dolazi iz 5554 §2.5 i 5557 §5 t. 4 i ulazi u K4 kao jedna točka:
   `RX_EN_EQA 0, PEAK 15, GAIN 8`. To je jedini proizvođačev 2,5G RX recept. Na 26.09. je mjeren prije TX_NEG popravka, pa
   taj rezultat (5,9·10⁻⁴) ne vrijedi. Rizik: na 5G CDR treba DFE, pa krak vrijedi samo za 2,5G.
4. **Fabric sekvencer (O12) nije potreban za kalibraciju**, nego za rad bez Pija (flash, K8). Ako K1/K2 pokažu da readapt
   ili CDR reset djeluje, prenosi se u fabric po EVK obrascu (watchdog: trajna greška → RX/CDR/EQA reset). Prije ploča se
   testira na modelu kao digitalnom blizancu (5557 §5 t. 2: omotač `CC_SERDES→ccfpga_serdes` oko 150 redaka, 14 s po
   pokretanju). To je izvan kritičnog puta 2,5G kalibracije.
5. **Nitko ne koristi `RX_EQA_CKP_OFFSET = 0`** (CC PIPE 0x01, model 0x01, pu-cc 0x01). Uz v1 (format {pomak 3 b, mantisa 5 b},
   0 vjerojatno gasi petlju offseta) zato upečeni R1 bit s OFFSET 0 **nije osnovica** (§0 t. 2).

### 2.3 Izvor neupisivih polja CKP (0x03, 0x04[7:0]) i 0x2B

| Hipoteza | Za | Protiv / što fali | Test (K1) |
|---|---|---|---|
| **H-a zaštita od upisa dok je `RX_EN_EQA=1`** (blokirani upis tiho propada) | CC `serdestool.py` r. 1354–1397: dva polja istog bloka su tako zaštićena (`RX_EQA_CONFIG` dok je `EN_EQA=1`). Sva tri polja pripadaju EQA/reset FSM-u. 0x04[8] (`EN_EQA`) iste riječi drži | nije dokumentirano za CKP | K1-b: `EN_EQA=0` → upis → readback → `EN_EQA=1` → readback |
| **H-b polje prepisuje FSM ili parametar iz bita** | silicij čita 0xA3 = parametar iz bita, a model 0x0000 (5557 §4). Polje dakle dolazi iz bita | ne objašnjava zašto `EN_EQA` iste riječi drži | K1-a (10 × `get` kroz 5 s), K1-d (bit s OFFSET 0 → čita li 0) |
| **H-c readback 0x2B zaostaje za jedan upis ili je par OVR + W/C samobrišući** | aba2: [OVR=1 RST=1, OVR=0 RST=0] → readback [0, 1]; drugdje [0, 0] | — | K1-c: funkcionalni test (BER), readback 0x2B se ne koristi kao dokaz |
| H-d JTAG put krši ≥ 16 taktova između pristupa regfileu (DS1001 str. 89, za CPE) | — | isti put radi za 12 drugih polja (150/150) | samo ako H-a i H-b padnu |
| **Model (5557)** | — | regfile = RAM, nema zaključavanja. **Ne može ni potvrditi ni oboriti** | — |

Vanjski put: pokretanje našeg R1 dijela `tb_gsm2_model.v` na NDA modelu (Anes Vrce, chili-chips; Hai Luong, RWTH) ili pitanje
Patricku Urbanu (CC). To je slanje sadržaja izvan kuće, pa **odluku i poruku šalje Goran**. Plan **ne ovisi** o odgovoru, jer
K1 odlučuje na siliciju, a put kroz bit postoji neovisno o JTAG-u.

---

## 3. Konačni plan izvedbe (Jelena, TASK-5559)

### 3.0 Pravila koja vrijede u svakom koraku

- Lanac `oss-cad-suite-20261016`, CFGRST, hold 0, isti `ber_top.v`, seed gs 7 / m2 2. Svaki novi bit se provjerava
  `serdes_cmp.py`: od osnovice se smije razlikovati **samo** navedeno polje.
- FPGA lab: samo `fpga-jtag gs|m2 … -r`, bez power-cyclea, nikad `Z` (brisanje brojača). BER samo iz delta snimaka, prvi prozor
  se odbacuje (`ber_windows.py`), 95 % Garwood.
- **Svaki JTAG `set` provjerava readback i izlazni kod** (K0). Polje kojem readback ≠ upis znači da je **pokus nevaljan**, a ne
  da se ne može izmjeriti.
- **Svaka točka se mjeri nakon readapta obje strane** (razina iz K1-c). Usporedba ide A/B/A unutar istog učitavanja i potvrđuje
  se na ≥ 3 učitavanja (v1 §3.1).
- Učitavanje: m2 `-r`, gs `-r`, čekati `PLL_LOCKED` i `TX_RESET_DONE` na obje, **zatim** readapt obje (§2.2 t. 2). Bilježe se
  `t_load`, `t_readapt` i zdravlje (v1 §3.4: sirove riječi 0x01, 0x03, 0x04, 0x2B, `RX_CDR_LOCKED`, `RX_EQA_LOCKED`, `FREQ_ACC`).
- Vrata (revizija §4): Q 10 s ≤ 8, C 60 s ≤ 60, prasak > 20 / 10 s, do 10 pokušaja. Na 5G Q ≤ 16, C ≤ 120.

### 3.1 Koraci, redoslijed, kriteriji

| Korak | Što | Trajanje | Kriterij prolaza | Ako ne prođe |
|---|---|---|---|---|
| **K0 alat i bitovi** (bez laba) | (a) **commit necommitanog WIP-a TASK-5542** (`link_gate.py`, `calib_aba.py`, 2 testa, `aba2.*`, `eeqa.*`) + sha256 Pi verzije = repo verzija. (b) v1 F0: `set` s readbackom i izlaznim kodom → `set_fail` u JSONL i stop; zdravlje bilježi sirove 0x01/0x03/0x04/0x2B; zastavica `--readapt <razina>` prije Q; testovi na lažnim izlazima. (c) **izgraditi bitove** (paralelno): **B0′** = PROFILE 1 + AMP 12 + `OV_CALIB 0` + `OV_TX_SEL_PRE 0` (OFFSET 1); **B1** = B0′ + `RX_WAIT_CDR_LOCK 1`; **B2** = B1 + `RX_EQA/CDR_RESET_TIME 16`, `RX_PMA_RESET_TIME 8`. Za B1/B2 treba novi `OV_` parametar u `ber_top.v` (danas je `WAIT_CDR_LOCK` tvrdo 0 u `cc_serdes_params.vh` r. 10). Zadano mora ostati bajtno isto (test kao `test_r1_bake.py`) | 2–4 h | testovi prolaze; `set_fail` se vidi u JSONL-u na lažnom izlazu; `serdes_cmp`: B0′ prema `*_2g5_oss1016` = 3 polja (RX/TX_CALIB_OVR, TX_SEL_PRE), B1 prema B0′ = 1 polje, B2 prema B1 = 3 polja; WIP commit pushan | ne ići u lab |
| **K1 put upisa** (JTAG, 1 učitavanje B0′, pa 1 učitavanje R1 bita `79b07795`/`4a94fc99`) | v1 F1: (a) `set RX_EQA_CKP_OFFSET=2` → 10 × `get` kroz 5 s; (b) **H-a:** `RX_EN_EQA=0` → `CKP_OFFSET=2`, `CKP_LF=0x83` → readback → `RX_EN_EQA=1` → readback (ne pisati 0); (b′) sirova riječ 0x04, maska 0x00FF, podatak 0x55; (c) **funkcionalni test razina:** TAPW pin +3 → `restore` → 30 s (očekivano ≥ 10⁻⁶) → razina → 30 s; razine **EQA (0x2B[2])**, **CDR (0x2B[4])**, **RX (0x2B[10])**, svaka 3×; (d) učitaj R1 bit, pročitaj `RX_EQA_CKP_OFFSET` | ≈ 1 h | (a/b) readback = upis i drži nakon `EN_EQA=1` → **put = „EN_EQA 0 → upis → EN_EQA 1 → readapt”**, ugraditi u `eyescan.py set` za 0x03/0x04[7:0]; (c) razina **djeluje** ako vrati ≥ 2 dekade na 3/3, a najjeftinija takva postaje `--readapt`; (d) čita 0 → put kroz bit radi | (a/b) ne drži → CKP polja su „samo bit”, K5 ide kroz bitove; (c) nijedna razina ne djeluje → readapt = L2 (`-r` ploče), a fabric reset port (O12) postaje uvjet za K8; (d) čita 1 → polje drži hardver, **K5 se zatvara** |
| **K2 reset slijed** (bitovi kroz vrata) | B0′ → B1 → B2, svaki **20 pokretanja vrata** (svako s novim učitavanjem, `--max-attempts 10`, `--readapt` iz K1). Bilježi se prolaz iz 1. pokušaja, pokušaji do prolaza, BER prihvaćenog (C 60 s), `RX_CDR_LOCKED` u trenutku vrata | 3 × (30–60 min) | krak pobjeđuje ako je prolaz iz 1. pokušaja bolji od prethodnog uz Fisher p < 0,05 (za 0,33 → 0,8 dovoljno je 20 po kraku). **Cilj je ≥ 19/20.** Pobjednik je osnovica za K3/K4 | B1 i B2 ne pomiču prolaz (≤ 9/20) → lutrija nije u reset FSM-u; osnovica ostaje B0′ + readapt; dalje K3/K4 (lutrija se tada rješava podizanjem margine) |
| **K3 dijagnoza poda** (JTAG, pobjednik K2) | v1 F2: (a) **gs TX idle** (`TX_ELEC_IDLE_OVR/IDLE`, 0x41, readback!) dok gs mjeri M2→GS: A/B/A 60 s, 3 učitavanja; isto za m2; (b) **2×2 TX_AMP** (gs 12/16 × m2 12/16), 60 s po ćeliji nakon readapta, 3 učitavanja | ≈ 1,5 h | (a) B/A ≤ 0,1 na 3/3 → pod je NEXT/sprega napajanja → H2/H4/H5 (Goran) i AMP po ploči; (b) ćelija bolja od (12, 12) ≥ ×2 u lošijem smjeru bez štete drugom → AMP po ploči u bit | (a) B/A ≈ 1 → pod je kanal ili RX → K4 nosi sav teret |
| **K4 TX/RX matrica po smjeru** (JTAG, margina na stresnoj točki) | metoda v1 F4: margina = najmanji TX_AMP druge strane uz koji je smjer < 10⁻⁹ u 30 s (12, 10, 8, 6, 4; readapt prije svake). Točke **M2→GS:** m2 `TX_SEL_POST` 5/6/8/10/12; gs `RX_AFE_PEAK` 24/16. Točke **GS→M2:** gs `TX_SEL_POST` 5/0; m2 `RX_AFE_PEAK` 24/16/12. Krak **B-static** (`RX_EN_EQA 0, PEAK 15, GAIN 8` na oba RX-a). Prvo FFE, pa CTLE (isti EQ proračun). Zatim pobjednike upeći u **B-final** (samo ta polja, `serdes_cmp`) | 3 učitavanja × ≈ 20 min po smjeru + bit | točka s ≥ 1 korakom amplitude više margine na 3/3 ulazi u B-final. **Pragmatični cilj:** na B-final C 60 s oba smjera 0 grešaka na ≥ 3/3 prihvaćena učitavanja (C 60 s = 7,5·10¹⁰ bita, pa 0 grešaka znači < 4·10⁻¹¹; to je preduvjet za K6, ne dokaz) | nijedna točka ne daje ni 1 korak → registri su iscrpljeni na 2,5G → §3.4 (hardver) |
| **K5 brzina petlje EQA** (samo ako je K1 a/b ili d otvorio put) | `CKP_LF/HF` 0xA3 → 0x83 / 0xC3, `CKP_OFFSET` 0x01 → 0x02 / 0x21, istom metodom margine na B-final | ≈ 1 h | ≥ 1 korak margine na 3/3 → u bit | preskočiti |
| **K6 završna kvalifikacija 2,5G** (B-final, bez JTAG upisa osim readapta) | (a) **30 pokretanja vrata** (nova učitavanja); (b) **3 neovisna prihvaćena učitavanja × 5040 s soak** (`ber_long`, oba smjera istodobno). Trajanje je fiksno, bez prekida i bez produljenja | (a) ≈ 1 h, (b) ≈ 4,5 h | **§3.3** | §3.4 |
| **K7 5G** (tek nakon H1 od Gorana) | P2 + iz K2 pobjednički reset (WAIT 1, CDR_RESET_TIME 16) + iz K4 asimetrični FFE/CTLE, pa revizija §5.2 S1–S5 (S1 kao 2×2 po ploči). Vrata 5G-1 / 5G-2 / 5G-3 (revizija §5.3) | dan | 5G-1 → 5G-2 → 5G-3; 5G dokaz 10⁻¹²: k ≤ 2 u 2520 s po smjeru (tek ako 5G-3 prođe; za M2→GS treba P5-3 mjerilo) | pravilo zaustavljanja revizije §5.3 → hardver (H3, H4/H5, M2 v0.2 Zdiff 85 Ω) |
| **K8 flash** (TASK-5531) | B-final (+ fabric readapt/watchdog ako ga K1 traži) → Goran upisuje flash → `p4_flash_boot.sh` (bez JTAG pisanja) | Goran + 30 min | link gore nakon reseta bez Pija, vrata prolaze | ostaje SRAM postupak |

**Paralelno:** K0-c bitovi grade se dok traje K0-b. Goranov H1/H4 (§4) može ići bilo kad prije K3. K7 ne kreće bez H1.
**Ukupno do K6:** ≈ 1,5–2 radna dana laba, ako svaki korak prođe iz prve.

### 3.2 Zašto baš ovim redom

1. **K1 prije svega:** dok ne znamo koji upis drži i koja razina reseta djeluje, svaki A/B mjeri povijest ili nepostojeću
   postavku (tako je „R1 s OFFSET 0” ušao u bitove, a nikad nije bio izmjeren).
2. **K2 prije K4:** reset slijed mijenja izvlačenje (lutriju), a K4 mijenja pod. K4 mjeri na prihvaćenom učitavanju nakon
   readapta. Bez stabilnog slijeda (K2) margina u K4 skače između učitavanja.
3. **K3 prije K4:** ako je pod preslušavanje vlastitog TX-a, FFE/CTLE sweep (K4) traži krivu polugu, a pravi lijek je AMP
   po ploči ili hardver.
4. **K6 tek kad K4 pokaže pomak:** prema §2.1 t. 4 soak na današnjem podu ima P(prolaz) ≈ 0. Pokretati ga ranije troši
   4,5 h i ne daje informaciju.

### 3.3 Kriterij završetka „kalibrirano do kraja” (2,5G) — sve četiri stavke

| # | Kriterij | Kako se provjerava (TASK-5560) |
|---|---|---|
| D1 | **Sve postavke su u bitu** (B-final, CFGRST). Nakon učitavanja nema JTAG upisa osim readapta (koji se ionako prenosi u fabric za K8). Za svako polje iz tablice konačnih postavki je **readback = namjera** (0 razlika) na obje ploče | `eyescan.py get` svih polja nakon učitavanja (sirovi izlaz u repou) + `serdes_cmp.py` B-final prema osnovici |
| D2 | **Vrata iz 1. pokušaja ≥ 28/30** na B-final (svako pokretanje novo učitavanje). Donja 95 % granica je 0,805. Alternativa je 15/15 (0,819) ako je vrijeme kratko | JSONL vrata: broj zapisa s `attempt == 1 && verdict == PASS` |
| D3 | **Soak: 3 neovisna prihvaćena učitavanja × 5040 s, oba smjera istodobno, na svakom ≤ 2 bitne greške po smjeru** (≥ 6,30·10¹² provjerenih bita po smjeru i učitavanju). Na svakom tada vrijedi BER < 10⁻¹² uz 95 %. Brza varijanta: 2400 s s 0 grešaka vrijedi isto, a ako ima grešku, ponavlja se kao 5040 s, ne produljuje se | `ber_windows.py` nad soak JSONL-om, prvi prozor odbačen; bitovi = riječi × 40 |
| D4 | **0 gubitaka sinkronizacije**, udio synced ≥ 0,999999. Prozori s greškom su Poissonovi (nema praska > 20 / 10 s) | isto |

Izvještaj Goranu (njegov format iz TASK-5559): samo rezultati ovih mjerenja, tablica po smjeru (bitovi, bitne greške, loše
riječi, BER + 95 % CI, gubitci sinkr., najgori prozor, pokušaji vrata) i konačne postavke svih parametara.

**5G „kalibrirano”** je zaseban cilj: 5G-3 (oba smjera < 10⁻⁹ u 300 s na ≥ 3/5 učitavanja, pa 5G vrata). Dokaz 10⁻¹² na
5G (k ≤ 2 u 2520 s) dolazi tek nakon toga. Iskreno očekivanje iz revizije §5.3 vrijedi i dalje: na ovom FFC/adapterskom
lancu 5G-3 ne očekujem bez promjene hardvera.

### 3.4 Pošten ishod ako registri nisu dovoljni

Ako K4 ne spusti pod M2→GS barem ×10, D3 se na 2,5G ne može postići registrima. Tada je ispravan završetak:
(1) B-final + vrata (D1, D2) kao **operativni** link, (2) izmjereni BER po smjeru s CI kao specifikacija linka, (3) protokolna
zaštita (CRC + retransmisija, revizija §6) za uporabu, (4) hardverska lista §4 (H2–H5) i M2 v0.2 kao put do 10⁻¹².
To se javlja Goranu kao **nalaz**, ne kao neuspjeh plana.

### 3.5 Konačne postavke: tablica koju K6 mora ispuniti

| Polje | gs | m2 | Izvor (korak) | Readback = namjera |
|---|---|---|---|---|
| RX/TX_CALIB_OVR, VAL | 1, 0 | 1, 0 | K0 (CAL0) | |
| TX_SEL_PRE / POST / AMP | 0 / K4 / K3 | 0 / K4 / K3 | K3, K4 | |
| RX_AFE_PEAK / GAIN | K4 / 0 | K4 / 0 | K4 (ili B-static 15/8) | |
| RX_EN_EQA | 1 (ili 0 ako B-static) | isto | K4 | |
| RX_EQA_CKP_LF / HF / OFFSET | 0xA3 / 0xA3 / 0x01 (ili K5) | isto | K1, K5 | |
| RX_WAIT_CDR_LOCK, *_RESET_TIME | K2 | K2 | K2 | |
| RX_CDR_CKP / TRANS_TH | 0x3E / 8 | 0x3E / 8 | nepromijenjeno (v1 O13) | |
| readapt razina i trenutak | K1-c | K1-c | K1, K2 | — |
| bit sha256 | | | K6 | — |

---

## 4. Što treba izmjeriti Goran

| # | Mjerenje | Kako | Kad | Odluka |
|---|---|---|---|---|
| **H1** | **TP10 (VDD_SER) i TP8 (VDD_SER_PLL), DC**, obje ploče; uz to vrijednost R105/R106 na svakoj | multimetar; prvo dok radi 2,5G bit, zatim 5G bit (P2). Jelena učitava bit kad Goran kaže da je spreman | **prije K7, poželjno prije K3** (10 min) | < 1,00 V je tvrdo izvan DS-a; < 1,03 V → R105/R106 2 Ω → 1 Ω (ili 0 Ω + ferit + 10 µF). **Bez H1 nema 5G (K7)** |
| H2 | AC šum na TP10/TP8 | osciloskop, kratka masa, AC, puni pojas i 20 MHz; link u radu, zatim uz K3-a (gs TX idle) | uz K3 | > 20 mV pk-pk ili komponenta na 31,25/62,5 MHz → sprega napajanja |
| H3 | refclk na M2 strani (nakon FFC/adaptera) | osciloskop, diferencijalno | prije K7 | swing < 250 mV ili zvonjenje → fan-out ili RTERM samo na jednoj strani |
| H4 | identifikacija FFC-a i adaptera (duljina, tip, fotografija) | bez instrumenta | odmah | ulaz za H5 i M2 v0.2 |
| H5 | zamjena FFC-a, A/B (5 pokretanja vrata svaki) | — | samo ako K3-a pokaže preslušavanje | izravna provjera kanala |

Goran **ne treba** ništa dirati za K0–K2. Sve je JTAG i `-r`.

---

## 5. Nesigurnosti

- H-a…H-d (§2.3) su hipoteze. K1 ih razdvaja na siliciju, a model ne može.
- Učinak `RX_WAIT_CDR_LOCK 1` na EQA nije poznat ni iz DS-a ni iz modela. Poznat je samo njegov učinak na PCS (model R2).
- Faktor „≈ ×90” u §2.1 počiva na jednom soaku (1800 s, jedno učitavanje). Prihvaćena učitavanja se razlikuju, pa je to red
  veličine, ne točan broj.
- Trajanja koraka su procjene iz dosadašnjih labova (učitavanje + vrata 1–3 min). Pi je u chainu 4 bio na mekom temperaturnom
  limitu (0xd0008), što može usporiti.
- Ne znam je li `0x2B[4]` (CDR reset preko OVR) na siliciju funkcionalan. To je dio K1-c.

## 6. Dokazi i ponovljivost

```
cd ulx5m-gs-m2-serdes/docs/data_20261017/t5558
python3 plan_v2_stats.py > plan_v2_stats.out    # §2.1, §3.3 (granice, P(prolaz), CP 28/30, faktori)
diff <(python3 plan_v2_stats.py) plan_v2_stats.out && echo SAME
```

Pročitano: v1 (`CALIBRATION_OPTIONS_20261017.md`), `RESEARCH_SERDES_USPOREDBA_20261017.md` §0, §2.3–2.5, §4,
`OPENCOLOGNE_PCIE_PREGLED_20261017.md` (cijeli), `CALIBRATION_REVIEW_20261016.md` §4–5, `SOAK_R1_2G5_20261017.md`,
`CHAIN4_5G_P2_20261017.md`, `TOOLCHAIN_20261017.md` §6 (R1 bit: `RX_EQA_CKP_OFFSET` 1→0), `slides/SERDES_SLIDE_20261017.pdf`,
`gateware/ber/ber_top.v` r. 45–46, 112–115 i `cc_serdes_params.vh` r. 1–10, openCologne-PCIE @a3cb12f:
`2.rtl/1.phy/2.serdes-model/ccfpga_serdes.v` (reset FSM r. 513–570), `2.rtl/2.pipe/pipe_src/src/pipe_src/ccfpga_pipe_logic.v`
r. 195–247, 355, 401 i `ccfpga_pipe_wrapper.v` r. 127–141, `5.sim/phy_pipe_serdes.v` (cfg FSM). TaskManager:
TASK-5531/5542/5545/5559/5560 (opis, bilješke, blockedReason). `git status` repoa: 7 izmijenjenih i 2 nepraćene datoteke
iz TASK-5542 (§1).
