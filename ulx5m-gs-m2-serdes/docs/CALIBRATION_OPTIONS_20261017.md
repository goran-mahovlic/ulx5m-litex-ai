# Preostale opcije kalibracije GS↔M2 SerDes i plan slaganja parametara za stabilan 2,5 G (i put do 5 G) — TASK-5553, 17.10.2026

**Zahtjev:** Goran, 17.10.2026 (Telegram, grupa REGOČ): duboko istraživanje koje još opcije kalibracije CC_SERDES postoje i kako
posložiti sve parametre da vrata kvalitete prolaze iz 1. pokušaja i da soak bude bez grešaka. **Napisala:** Kosjenka (arhitektura).
**Ploče i Pi nisam dirala.** Nema novog mjerenja. Nova je analiza postojećih sirovih podataka TASK-5542/5551/5552 (skripte i izlazi u
`data_20261017/t5553/`) i pregled izvora. Dokument **nadograđuje** `CALIBRATION_REVIEW_20261016.md` (K1–K11) i ne ponavlja ga.
Pregled tuđih postupaka je u `SERDES_UMJERAVANJE_KAKO_DRUGI_20261015.md`. Usporedbu s objavljenim mjerenjima drugih FPGA radi
Manda u TASK-5554 (`RESEARCH_SERDES_USPOREDBA_20261017.md`). Izvedbu plana radi Jelena u zasebnom zadatku.

Oznake su iste kao u reviziji: **UTVRĐENO** (izmjereno, ≥ 3 učitavanja ili izvor), **POJEDINAČNO**, **PRETPOSTAVKA**, **IZVEDENO**.

---

## 0. Kratki odgovor

1. **Dio dosadašnje „kalibracije” nikad nije stvarno upisan, ili to bar ne znamo.** Iz svih JTAG `set` naredbi u TASK-5542/5552
   (`write_readback.out`): polja `RX_EQA_CKP_LF/HF` (0x03) i `RX_EQA_CKP_OFFSET` (0x04[7:0]) imaju readback jednak upisu u **0/6**
   slučajeva, a `RX_EQA_RESET_OVR` / `RX_RESET_OVR` (0x2B) u **17/58**. Svih ostalih 12 polja koja smo upisivali (0x02, 0x04[8], 0x09,
   0x0A, 0x0B, 0x30, 0x3C) ima readback jednak upisu u **100 %** slučajeva (150/150). Posljedice:
   - K8 (brzina petlje adaptacije) **nikad nije ispitan**. Ni R1 nije bio R1, kako je TASK-5552 već utvrdio za CKP_OFFSET.
   - Krakovi L1/L1b iz K3 nemaju dokaz iz readbacka (OVR čita 0, a TH_MON/TAPW/OFFSET i CDR_LOCKED se ne mijenjaju). Dokaz da
     L1 djeluje dolazi tek iz BER-a (točka 2).
2. **Ipak, EQA reset preko 0x2B djeluje funkcionalno (novo, §1.2).** U aba2 je TAPW pin +3 na sva tri učitavanja ostavio
   M2→GS na 1,2·10⁻⁶ … 1,9·10⁻⁵. Prvi korak s `eqarst` vratio je BER za **2–4 dekade** (3/3 učitavanja). Svaki sljedeći `eqarst`
   daje novo „bacanje kocke”: na l1 su ishodi naizmjence 3·10⁻¹⁰ i 10⁻⁷, a na l2/l3 ostaju na podu učitavanja (3·10⁻⁹ odnosno 10⁻⁸).
   Dakle: **readback 0x2B ne govori istinu, a EQA reset postoji i ponovno izvlači adaptaciju, ali samo u granicama koje je postavilo
   učitavanje.** Dio lutrije je u EQA, a dio dublje (CDR, TX, PLL, terminacija ili napajanje).
3. **Greške u soaku R1 su Poissonove, nisu prasci.** 19 loših riječi M2→GS u 177 prozora daje očekivano 18,0 prozora s greškom,
   a izmjereno je 18. GS→M2 ima 2 riječi u 2 prozora, očekivano 1,99. Pod 2·10⁻¹¹ je **stacionarni šumni pod (margina)**. Vrata ga
   ne mogu spustiti, jer samo biraju bolje učitavanje. Za „bez grešaka” (< 10⁻¹² uz 95 %) M2→GS treba bolji za **×20 ili više**.
   To mora doći iz radne točke (TX/RX), preslušavanja ili napajanja, a ne iz ponovnog pokušaja.
4. **Najjače neiskorištene poluge (iz postojećih podataka, §2):**
   (a) `TX_SEL_PRE 0` je bolji na 3/3 učitavanja u oba smjera (medijan ×0,08 M2→GS, ×0,2 GS→M2). Već je u R1, ali je upisan **nakon**
   adaptacije. Upečeni R1 bitovi (`gs 79b07795` / `m2 4a94fc99`) postoje i **nikad nisu učitani**.
   (b) **Asimetrični TX FFE po smjeru:** m2 TX traži više post-cursora (POST 8: M2→GS ×0,45), a gs TX manje (Q0: GS→M2 ×0,05).
   Simetrična promjena kvari onaj drugi smjer, pa je zato dosad izgledala neutralno.
   (c) **`RX_WAIT_CDR_LOCK` = 0 u našim bitovima, a DS1001 zadano je 1.** Nula je prepisana iz loopback primjera pu-cc („turn off if
   loopback enabled”). S nulom reset-FSM pušta EQA/PCS bez čekanja da se CDR zaključa, pa adaptacija smije krenuti na nezaključanom
   taktu. To je **nikad ispitan kandidat za lutriju** i za 5G CDR.
   (d) **Redoslijed:** adaptacija bi trebala krenuti tek kad su obje strane gore i u konačnoj TX postavci. Danas se m2 učita prvi
   i adaptira dok gs još nema signal ili ga konfigurira, a R1 se upisuje preko JTAG-a nakon toga.
   (e) **Test preslušavanja:** gs TX u električni idle dok se mjeri M2→GS (gs RX i dalje prima). Tako se odvaja vlastiti TX
   (NEXT, FFC/adapter) od kanala. Nikad mjereno, a jeftino je.
5. **Plan (§3)** ide u 5 faza: F0 alat (bez laba) → F1 put upisa (30–60 min) → F2 preslušavanje i redoslijed (≈ 2 h) →
   F3 upečeni bitovi, matrica B0–B4 kroz vrata (po kraku 20 pokretanja, ≈ 1 h) → F4 rangiranje na stresnoj točki (marginom
   amplitude umjesto mrtvog eye scana) → F5 soak. Statističke granice su iz `plan_stats.out`. **Za tvrdnju „bez grešaka” na
   2,5 G treba 0 grešaka u 2400 s po smjeru (BER < 10⁻¹² uz 95 %).** Za „iz 1. pokušaja” (p ≥ 0,8 uz 95 %) treba 15/15 ili
   28/30 prolaza iz 1. pokušaja.
6. **Od Gorana (§4):** TP10/TP8 DC na obje ploče, s 2,5 G pa 5 G bitom (multimetar, 10 min). Zatim AC šum na TP10/TP8 osciloskopom,
   identifikacija FFC-a i adaptera, refclk na M2 strani. Bez TP10/TP8 nema 5 G posla.
7. **5 G:** redoslijed iz revizije §5 i dalje vrijedi. Novo je da `RX_WAIT_CDR_LOCK 1` i dulji `RX_CDR_RESET_TIME` idu u
   5G bitove **prije** S1–S5, jer 5G pada upravo na CDR locku (gs RX_CDR_LOCKED 0 u 7/9). Pravilo zaustavljanja ostaje.

---

## 1. Novi nalazi iz postojećih podataka

### 1.1 Koji JTAG upisi drže (readback)

Skripta `data_20261017/t5553/write_readback.py`. Za svaku `set F=v` naredbu (calib_aba `aba2`, `eeqa`, `k12a`, link_gate `k3r_2`)
usporedi traženu vrijednost s readbackom iz iste naredbe. `eyescan.py cmd_set` odmah nakon `wr_fields` radi `rd_fields`. W/C
polja (`*_RESET`, `*_CALIB_EN`) su preskočena, jer je njihov readback 0 očekivan.

| Polje | Adresa [bitovi] | readback = upis | readback ≠ upis | Primjer (upis → readback) |
|---|---|---|---|---|
| RX_CALIB_OVR / RX_CALIB_VAL | 0x02[2] / [6:3] | 4 / 22 | 0 / 0 | |
| **RX_EQA_CKP_LF / HF** | **0x03[7:0] / [15:8]** | **0** | **6 / 6** | 0x83 → 163 (= 0xA3, zadano) |
| **RX_EQA_CKP_OFFSET** | **0x04[7:0]** | **0** | **6** | 0 → 1 (plus TASK-5552: 2 → 1) |
| RX_EN_EQA | 0x04[8] | 8 | 0 | ista adresa kao CKP_OFFSET, a drži |
| RX_AFE_PEAK / GAIN | 0x09 | 12 / 6 | 0 | |
| RX_CDR_CKP / TRANS_TH | 0x0A / 0x0B | 12 / 6 | 0 | |
| **RX_EQA_RESET_OVR** | **0x2B[2]** | 16 | **40** | 1 → 0, ali i 0 → 1 (vidi niže) |
| **RX_RESET_OVR** | **0x2B[10]** | 1 | **1** | 1 → 0 |
| TX_SEL_PRE / POST / AMP | 0x30 | 18 / 18 / 24 | 0 | |
| TX_CALIB_OVR / VAL | 0x3C | 4 / 16 | 0 | |

Što iz toga slijedi (IZVEDENO):
- Kvar je **vezan uz polje, ne uz alat**. Isti `wr_fields`/`rd_fields` put radi za 0x04[8], a ne radi za 0x04[7:0] iste riječi.
  Maska u `wr_serdes_regfile` je ispravna za oba (`wr_fields` gradi masku po polju).
- 0x03 i 0x04[7:0] su parametri petlje EQA (DFE) adaptacije. 0x2B su prepisivači reseta. Sva tri su polja koja **posjeduje stroj
  stanja RX-a** (EQA ili reset-FSM). DS1001 (rujan 2026, tabl. 2.44 i 2.59) za CKP_OFFSET kaže samo „r/w, zadano 0x01”
  [S1]. Bit-pozicija je ista u DS-u, prjpeppercorn `TileBitDatabase.cpp:444-446`, nextpnr `pack_serdes.cc` i serdestoolu [S2].
  Krivo mapiranje zato nije vjerojatno.
- **Presedan iz izvora proizvođača:** upstream `serdestool.py` (pu-cc, r. 1354–1397) piše da su dva polja istog bloka
  zaštićena od upisa i da **„blokirani upis tiho propada”**. `RX_EQA_CONFIG` je zaključan dok je `RX_EN_EQA=1`, a `RX_TH_MON2`
  dok je `RX_EN_EQA_EXT_VALUE[3]=1`. Zato `eye_freeze()` prvo piše `RX_EN_EQA=0` [S3]. Naši upisi u 0x03/0x04[7:0] rađeni su
  uz `RX_EN_EQA=1`. **Najvjerojatnije objašnjenje (PRETPOSTAVKA, test F1-b):** i `RX_EQA_CKP_*` su zaključani dok adaptacija radi.
- Mapa 0x2B u našem `serdestool.py` (PMA 0/1, EQA 2/3, CDR 4/5, PCS 6/7, BUF 8/9, RX 10/11) **jednaka je ispravljenoj** mapi
  iz prjpeppercorn PR #20 (Patrick Urban, 16.06.2026, „0x2B was incorrectly documented”) [S4]. Starije kopije
  (pa i komentar u upstream `reset_serdes_rx`, maska 0x0003) imaju stari, krivi raspored. Naš `L1` je dakle stvarno EQA reset,
  a `L1b` stvarno RX reset.
- DS1001 traži ≥ 16 taktova između dva pristupa regfileu sa strane CPE-a [S1 str. 89]. Za JTAG put to nije navedeno. Moguće je
  da je par OVR + W/C puls samobrišući, pa je readback OVR = 0 očekivan (PRETPOSTAVKA). Ne objašnjava slučajeve 0 → 1 u aba2.
- Uzorak za 0x2B u aba2 izgleda kao **zaostajanje za jedan upis**: `eqarst` = [OVR=1 RST=1, OVR=0 RST=0] vraća readback [0, 1].
  U eeqa i link_gate isti par vraća [0, 0]. Readback 0x2B dakle nije pouzdan ni kao dokaz da se upis nije dogodio.
- **`link_gate.py after_load()` ne provjerava ni readback ni izlazni kod `eyescan.py set`** (TASK-5552 §4). Sve mjere sa
  `--r1` i K3 L1/L1b trebaju to imati na umu.

### 1.2 EQA reset (0x2B) ipak djeluje: ponovno bacanje kocke unutar učitavanja

Skripta `data_20261017/t5553/eqarst_reroll.py` nad `aba2.out` (3 učitavanja, svaki korak 30–60 s, oba smjera):

| Učitavanje | Prije prvog `eqarst` (M2→GS) | Uzastopni koraci s `eqarst`: M2→GS | Oba < 10⁻⁹ |
|---|---|---|---|
| l1_1938 | 1,9·10⁻⁵ (nakon TAPW +3) | 3,1·10⁻¹⁰ → 1,1·10⁻⁷ → 3,9·10⁻¹⁰ → 3,5·10⁻⁸ → 2,6·10⁻¹⁰ → 1,9·10⁻⁷ | 3/6 |
| l2_2032 | 1,2·10⁻⁶ | 5,0·10⁻⁹ → 3,7·10⁻⁹ → 3,2·10⁻⁹ → 3,0·10⁻⁹ → 2,7·10⁻⁹ → 2,4·10⁻⁹ | 0/6 |
| l3_2127 | 1,7·10⁻⁶ | 1,5·10⁻⁸ → 1,5·10⁻⁸ → 8,2·10⁻⁹ → 2,1·10⁻⁸ → 1,6·10⁻⁸ → 3,1·10⁻⁸ | 0/6 |

- Iz oštećenog stanja svaki prvi `eqarst` vraća 2–4 dekade (3/3). **Reset EQA se dakle izvršava**, iako readback OVR kaže 0.
  Pojedinačni L1 u k3r_2 (0/1) pokrenut je iz neoštećenog stanja i ne govori ništa ni za ni protiv.
- l1 izmjenjuje dobro i loše (dvije razine, 3/6), a l2 i l3 se drže svog poda. Hipoteza H1 (lokalni minimumi EQA) objašnjava
  **dio** lutrije: unutar l1 razlika je ×300. Pod l2/l3 (≥ 2·10⁻⁹) ne miče se EQA resetom, pa je drugi dio izvan EQA
  (H2 TX/PLL faza, H3 napajanje, ili CDR, kojeg L1 ne dira). To potvrđuje rang L1 < L2 < L3 i daje mjerljiv cilj za K3.
- **Histereza unutar učitavanja** (isto upozorava Xilinx UG476 str. 195 za adaptaciju na 8b10b podacima [S6]): A koraci istog učitavanja (isti parametri, samo vraćeni) kližu se kroz sweep (l1: A0 1,3·10⁻⁸ →
  A4 3,6·10⁻⁷ → A16 3,1·10⁻⁶). Promjena TX postavke druge strane pomakne adaptaciju RX-a u stanje iz kojeg se sama ne vraća.
  **Svaku promjenu TX/RX postavke mora pratiti EQA reset obje strane prije mjerenja.** Inače A/B mjeri povijest, a ne točku
  (to je i razlog šuma u §14.2–14.3 starih sweepova).

### 1.3 Soak R1: šumni pod, ne prasci

`SOAK_R1_2G5_20261017.md`: M2→GS 19 loših riječi u 177 prozora, 18 prozora s greškom. Uz Poissonov model očekuje se
177·(1 − e^(−19/177)) = **18,0**, za GS→M2 1,99 (izmjereno 2). Greške su neovisni događaji ravnomjerno razasuti po 30 min.
Ni drift ni prasci nisu vidljivi. U tom učitavanju nema „lošeg trenutka” koji bi nadzor u radu mogao uhvatiti i resetirati.
Postoji samo margina koja je premala. **Odluka:** vrata (K1) ostaju za lutriju. Za „bez grešaka” trebaju poluge koje mijenjaju
SNR (§2: O3–O8, O10), a ne poluge koje mijenjaju izvlačenje.

### 1.4 Redoslijed paljenja i adaptacije danas (iz koda i logova)

| Korak | Danas | Problem |
|---|---|---|
| 1 učitaj m2 (`-r`) | m2 RX odmah kreće: PMA → CDR → EQA (reset-FSM, `RX_WAIT_CDR_LOCK 0`) | gs još nije učitan ili se upravo konfigurira: m2 RX adaptira na šum ili na pola konfiguriran signal |
| 2 učitaj gs (`-r`) | gs RX adaptira na m2 TX | m2 TX je još u PROFILE postavci (PRE 5, CAL auto) |
| 3 `after_load` JTAG: CAL0, TX_SEL_PRE 0, (CKP_OFFSET 0 — ne drži) | TX obje strane mijenja se **ispod** već adaptiranih RX-ova | §1.2: adaptacija se ne vraća sama. R1 je mjeren s RX-om adaptiranim na PRE 5 |
| 4 vrata | Q 10 s / C 60 s | mjeri stanje nakon koraka 1–3, koje ovisi o putu |

Preporučeni redoslijed (§3, F2/F3): **sve konačne postavke u bitu** → učitaj obje → čekaj PLL lock i TX gore na obje → **RX reset
(PMA ili EQA) obje strane** kad su oba TX-a gotova → CDR lock → EQA lock → PCS/align → vrata. Tako radi PCIe (adaptacija u
Recovery.Equalization nakon dogovora TX preseta) i Xilinx (DFE adaptacija na stvarnim podacima nakon CDR locka, pa HOLD) —
`SERDES_UMJERAVANJE_KAKO_DRUGI_20261015.md` §3.1, §3.5.

### 1.5 Što krug K4–K12 (aba2) već kaže o svakom parametru

Skripta `data_20261017/t5553/aba2_ratio.py`: omjer BER(B) / geometrijska sredina BER(A prije, A poslije), medijan preko 3 učitavanja.
Vrijednost < 1 znači da je B bolji. Oprez: A drifta (§1.2), pa omjer ×2–3 nije značajan. Ozbiljno uzimam samo smjer koji se
ponavlja na 3/3 ili omjer ≥ ×5.

| Korak (oba TX/RX) | M2→GS medijan (po učitavanju) | GS→M2 medijan (po učitavanju) | Čitanje |
|---|---|---|---|
| **pre0** (TX_SEL_PRE 0) | **×0,08** (0,32 / 0,009 / 0,08) | **×0,20** (0,27 / 0,20 / 0,13) | **jasan dobitak, 3/3 oba** → u bit (O2, B0) |
| **ffe_q0** (PRE 0, POST 0) | ×1,9 (3,7 / 1,9 / 1,2) | **×0,05** (0,016 / 0,05 / 1,7) | gs TX bez FFE je bolji za GS→M2, a m2 TX treba FFE → **asimetrija** (O5) |
| **post8** | ×0,45 (0,21 / 0,45 / 2,1) | ×6,1 (18 / 6,1 / 2,8) | m2 TX želi više post-cursora, gs TX manje → ista asimetrija (O5) |
| amp16 | ×0,36 (0,36 / 0,17 / 0,39) | ×5,6 (6,9 / 5,6 / 0,10) | jači m2 TX pomaže M2→GS 3/3, a GS→M2 pati: ili gs TX 16 kvari, ili je to **NEXT m2 TX → m2 RX** (O6, test 2×2) |
| amp8 | ×0,68 | ×0,87 | neutralno |
| peak16 | ×0,88 | **×0,19** (0,33 / 0,09 / 0,19) | više CTLE na m2 RX pomaže GS→M2 (O7) |
| gain1 | ×7,8 | ×30 | **odbaciti** (potvrđeno na AMP 12) |
| tapw −2 / +2 / +3 (pin) | ×18 / ×17 / ×25 | ≈ 1 | adaptirani TAPW je na optimumu → statički DFE (K7) **odbaciti** na 2,5 G |
| ckp1e / ckp7e / trans16 | ×0,75 / ×0,41 / ×2,4 | ×1 / ×1,4 / ×0,9 | CDR na 2,5 G nije poluga (O13) |
| rxval1/2/4, txval2/4 (CAL kodovi) | 0,9–2,6 | 1–2,5 | terminacijski kod nije poluga → K12 **zatvoriti** |
| eqa_off0 / eqa_lfhf83 | — | — | **nevaljano**: polja se nisu upisala (§1.1), a učinak je od `eqarst` (§1.2) |

---

## 2. Rangirani popis opcija

Rang je po (očekivani učinak na cilj „1. pokušaj + soak bez grešaka”) × (pouzdanost dokaza) / trošak. Trošak: **J** = JTAG na
radnom linku (minute), **B** = novi bit + kvalifikacija kroz vrata (≈ 1–2 h Jelena), **H** = Goran na ploči.
K-oznake su iz revizije 16.10.

| Rang | Opcija | Izvor / dokaz | Očekivani učinak | Trošak | Ovisi o |
|---|---|---|---|---|---|
| **O1** | **Mjerni lanac koji ne laže:** `link_gate` i `calib_aba` provjeravaju readback i izlazni kod svakog `set`. Polja 0x03 i 0x04[7:0] se označe „samo bit ili uz `RX_EN_EQA=0`” dok F1 ne pokaže drukčije. Readback 0x2B se ne uzima kao dokaz (OVR + W/C par). Funkcionalni dokaz reseta (§3 F1-c) umjesto readbacka | §1.1 (0/6, 0/6, 17/58) | **preduvjet**: bez toga su K8 i K3 nečitljivi, a „R1” ne znači ono što piše | J/kod, 1 h | — |
| **O2** | **Upečeni R1 bitovi** (`gs 79b07795` / `m2 4a94fc99`, već na Piju `/home/pi/fpga/oss20261016`, nikad učitani): PRE 0 i CAL0 vrijede od paljenja, pa RX adaptira na konačni TX. Ujedno test: čita li se `RX_EQA_CKP_OFFSET` = 0 iz bitstreama | `TOOLCHAIN_20261017.md` (4 polja razlike); §1.4 | udio prolaza iz 1. pokušaja ↑ (hipoteza; danas L3 5/15). BER prihvaćenih ×1–3 | J (bitovi postoje) | O1 |
| **O3** | **Reset-FSM po DS-u:** `RX_WAIT_CDR_LOCK` 0 → **1** (DS1001 zadano). `RX_EQA_RESET_TIME`, `RX_CDR_RESET_TIME`, `RX_PMA_RESET_TIME` 3 → 8 i 16 (0x01, 5 b). `RX_RESET_TIMER_PRESC` ostaje 4 | `TUNING_5G.md` §1.4 (DS def 1, mi 0 iz loopback primjera); nikad mijenjano; 5G CDR lock 0 u 7/9 | **kandidat broj 1 za lutriju** (EQA više ne može krenuti prije CDR locka) i za 5G CDR. Veličina nepoznata | B | O2 kao osnovica |
| **O4** | **Redoslijed „prvo obje strane, onda adaptacija”:** nakon učitavanja obje i nakon svake promjene postavke → EQA reset obje strane (L1 iz §1.2), ili RX PMA reset ako F1 pokaže da radi. U vratima to je korak prije Q | §1.2 (2–4 dekade iz oštećenog stanja, 3/3; histereza); PCIe/Xilinx | uklanja ovisnost o putu. Iz 1. pokušaja ↑. Ne spušta pod učitavanja | J (već postoji `EQARST`) | O1 (funkcionalni dokaz) |
| **O5** | **Asimetrični TX FFE po smjeru:** gs TX `SEL_PRE 0, SEL_POST 0` (GS→M2), m2 TX `SEL_PRE 0, SEL_POST 8` (M2→GS); zatim fino m2 POST 6/8/10/12 | §1.5: ffe_q0 GS→M2 ×0,05; post8 M2→GS ×0,45; obje ponovljene po smjeru 2–3/3 | M2→GS ×2–5, GS→M2 ×5–20 (IZVEDENO iz pojedinačnih koraka; interakcija nepoznata) | J → B | O4 (svaka točka s EQA resetom) |
| **O6** | **2×2 test TX_AMP po ploči** (gs 12/16 × m2 12/16): odvaja „jači daleki TX” od „vlastiti TX prelazi u svoj RX” (NEXT) | §1.5 amp16: M2→GS ×0,36 (3/3), GS→M2 ×5,6; revizija §17.5 (sprega) | ako je NEXT: m2 AMP 16 + gs 12 daje M2→GS ×2–3 bez štete; ako nije, AMP ostaje 12 | J | O4 |
| **O7** | **CTLE po prijamniku:** m2 RX `RX_AFE_PEAK` 24 → 16 (i 12), gs RX ostaje 24 | §1.5 peak16 GS→M2 ×0,19 (2/3) | GS→M2 ×2–5 | J | O5 (FFE i CTLE dijele isti EQ proračun: prvo FFE, pa CTLE) |
| **O8** | **Test preslušavanja i napajanja (gs TX idle):** `TX_ELEC_IDLE_OVR=1, TX_ELEC_IDLE=1` na gs dok gs checker mjeri M2→GS (m2 RX izgubi link, to je u redu). Zatim isto na m2 za GS→M2 | nikad mjereno; §1.3 (stacionarni pod) | **dijagnoza poda**: pad BER-a ≥ ×10 znači da je pod NEXT ili sprega napajanja iz vlastitog TX-a → H5 (FFC/adapter, napajanje) i O6 | J, 3 učitavanja × 60 s A/B/A | O1 (provjeriti readback 0x41) |
| **O9** | **Vrata s ljestvicom** (K1) + L1 EQA reset kao jeftina razina 1–2, L3 od 3. pokušaja. Bilježiti zdravlje svakog pokušaja | K1; §1.2 (L1 = ponovno bacanje unutar učitavanja, p ≈ 0,5 na l1, 0 na l2/l3) | iz 1. pokušaja se ne mijenja, ali vrijeme do prolaza ↓ | J (postoji) | O1, O4 |
| **O10** | **VDD_SER / VDD_SER_PLL** DC i AC (Goran, §4). Ako je < 1,03 V ili je šum > 20 mV pk-pk: R105/R106 2 Ω → 1 Ω ili 0 Ω + ferit + 10 µF | DS1001 1,00–1,10 V [S1 str. 155]; revizija K2; TUNING_5G H2; javno: ulx5m-gs issue #28 (VDD_SER izvan specifikacije na 0,9 V jezgre) i Olimex EVB shema („SerDes ne radi kad je VDD_CORE 0,9 V … min 0,95 V”) [S7] | 2,5 G: nepoznat (moguć dio poda, §1.3, ako O8 pokaže spregu). 5 G: preduvjet | H | — |
| **O11** | **K8 brzina petlje EQA** (`CKP_LF/HF/OFFSET`): preko JTAG-a uz `RX_EN_EQA=0` (ako F1-b prođe), inače kroz bit. Vrijednosti u formatu {pomak 3 b, mantisa 5 b} [S5]: LF/HF 0xA3 = 101_00011 → 0x83 / 0xC3 (pomak ±1), OFFSET 0x01 → 0x02 / 0x21; **ne 0** | §1.1 (uz EN_EQA=1 ne drži); [S3], [S5] | nepoznat, mogući utjecaj na lutriju unutar EQA (l1 ×300) | J ili B | O1, F1 |
| **O12** | **Fabric reset portovi** `RX_EQA_RESET_I`, `RX_PMA_RESET_I`, `RX_CDR_RESET_I` (danas `1'b0`, `ber_top.v:113`) + fabric watchdog (K11): put reseta koji ne ovisi o regfileu i radi bez Pija (flash boot) | UG1001 tabl. 7.x (portovi postoje); §1.1 (regfile put nepouzdan) | neovisan, ponovljiv L1/L1b. Uvjet za rad bez Pija | B, 1 dan | O3/O4 rezultat |
| O13 | CDR na 2,5 G (CKP 0x7E, TRANS_TH) | §1.5: bez ponovljivog učinka | mali | J | — |
| O14 | **G2' — adaptacija na PRBS + pravo zamrzavanje:** treniraj na PRBS-u do `RX_EQA_LOCKED`, zamrzni integratore s `RX_EQA_CONFIG[8:6]=0` (upstream način, uz `RX_EN_EQA=0` prije upisa i provjeru readbacka), pa prebaci na 8b10b okvir. Stari G2 je zamrzavao samo s `RX_EN_EQA=0` | Xilinx UG476 str. 195: ponavljajući 8b10b uzorci „mogu uzrokovati drift” adaptacije, treba PRBS-7 ili bolji [S6]; [S3] r. 1399–1402; revizija §1 (stari G2 3/14) | mali do srednji: cilja upravo histerezu iz §1.2 | J | F1-b |
| — | **Zatvoriti / ne ponavljati:** RX_AFE_GAIN 1 (×8–30 gore, na AMP 12 potvrđeno), statički TAPW (pin ±2/3 ×17–25 gore), CAL kodovi K12 (bez učinka), simetrični FFE Q0 (kvari M2→GS), plus sve s popisa „ne ponavljati” iz revizije §3 | §1.5 | | | |

**Zašto ovaj redoslijed, a ne „još jedan sweep”:** od svih poluga samo O3–O8 i O10 mogu spustiti stacionarni pod (§1.3). O1, O2 i O4
su jeftini i uklanjaju šum mjerenja (put upisa, histereza). Bez njih bi svaki sweep O5–O7 opet mjerio povijest učitavanja,
kao u §14.2–14.3 starih sweepova.

---

## 3. Plan pokusa

### 3.1 Statističke granice (iz `data_20261017/t5553/plan_stats.out`)

2,5 G = 1,25·10⁹ **provjerenih** bita/s po smjeru (31,25 M riječi/s × 40 bita koje checker uspoređuje). 5 G = 2,5·10⁹. Linijska
brzina je dvostruka, pa izvori koji računaju po linijskim bitovima [S8] dobivaju upola kraće vrijeme. Za našu tvrdnju vrijede
samo provjereni bitovi. Pravilo nula grešaka: 3,00/BER bita za 95 %, 4,61/BER za 99 % [S8].

| Tvrdnja | Što treba | Na 2,5 G | Na 5 G |
|---|---|---|---|
| BER < 10⁻¹¹ uz 95 % (0 grešaka) | 3,0·10¹¹ bita | 240 s | 120 s |
| **BER < 10⁻¹² uz 95 % („bez grešaka”)** | 3,0·10¹² bita | **2400 s (40 min)** | 1200 s |
| BER < 10⁻¹³ uz 95 % | 3,0·10¹³ bita | 6,7 h | 3,3 h |
| A/B razlika ×2 (95 %, snaga 80 %) | ≈ 33 greške po kraku | 1300 s/krak na 2·10⁻¹¹; **52 s na 5·10⁻¹⁰** | |
| A/B razlika ×3 / ×5 | 13 / 6 grešaka po kraku | 520 / 240 s na 2·10⁻¹¹; 21 / 10 s na 5·10⁻¹⁰ | |
| udio dobrih učitavanja 0,33 → 0,66 / 0,80 / 0,90 | Fisher, 95 %/80 % | **35 / 17 / 11 učitavanja po kraku** | |
| „vrata iz 1. pokušaja” p ≥ 0,8 (donja 95 % CP granica) | | **15/15 ili 28/30** | |
| soak 1800 s bez greške, ako je stvarni BER 10⁻¹³ / 10⁻¹² / 2,2·10⁻¹¹ | P(0 grešaka) | 0,80 / 0,11 / 0 | |

Iz tablice slijede tri pravila plana:
1. **Na prihvaćenom učitavanju (≈ 2·10⁻¹¹) A/B nije izvediv** u razumnom vremenu (≥ 20 min po kraku za ×2). Točke se zato
   rangiraju **na stresnoj točki** (§3.3 F4), gdje je BER 10⁻⁹–10⁻⁸ i ×2 se vidi za 1 min. Na prihvaćenom učitavanju radi se
   samo završna potvrda (soak).
2. **Udio dobrih učitavanja** (lutrija) ocjenjuje se brojem pokretanja vrata: ≈ 20 po kraku, ako je očekivani pomak 0,33 → ≥ 0,8.
   Za manji pomak (→ 0,66) treba 35 po kraku, a to je pola dana po kraku. Zato se manji pomaci ne love.
3. **Svaka točka se mjeri nakon EQA reseta obje strane** (§1.2). Svaka usporedba ide **unutar istog učitavanja (A/B/A)** i
   potvrđuje se na ≥ 3 učitavanja.

### 3.2 Matrica bitova (za F3)

Svi bitovi su CFGRST, hold 0, isti `ber_top.v`, isti seedovi (gs 7 / m2 2) i isti lanac (`oss-cad-suite-20261016`). Razlike se
provjeravaju sa `serdes_cmp.py` (smije se razlikovati **samo** navedeno polje).

| Krak | Sadržaj | Razlika prema prethodnom | Pitanje |
|---|---|---|---|
| **B0** | R1 upečen (postoji: gs `79b07795`, m2 `4a94fc99`) | — | osnovica: konačni TX od paljenja |
| **B1** | B0 + `RX_WAIT_CDR_LOCK 1` | 1 polje × 2 ploče | čeka li EQA CDR i smanjuje li to lutriju |
| **B2** | B1 + `RX_EQA_RESET_TIME`, `RX_CDR_RESET_TIME` 3 → 16 (i `RX_PMA_RESET_TIME` 3 → 8) | 3 polja | dulji reset koraci |
| **B3** | B2 (ili B0/B1, što pobijedi) + asimetrični FFE: gs `TX_SEL_POST 0`, m2 `TX_SEL_POST 8` | po 1 polje na ploči | O5 u bitu |
| **B4** | B3 + m2 `RX_AFE_PEAK 16` (+ m2 TX_AMP 16 ako O6 to pokaže) | 1–2 polja na m2 | O6/O7 u bitu |

B1/B2 i B3/B4 se mogu graditi paralelno (Jelena). Učitava se samo ono što je prošlo prethodni korak.

### 3.3 Faze, redoslijed, trajanje, kriteriji

| Faza | Što | Pokušaja × trajanje | Kriterij prolaza | Kriterij zaustavljanja |
|---|---|---|---|---|
| **F0** alat (bez laba) | (a) `after_load`/`calib_aba`: `set` vraća ≠ 0 → zapis `set_fail` i stop; (b) zdravlje bilježi sirove riječi 0x03, 0x04, 0x2B; (c) vrata imaju korak `readapt` (EQA reset obje strane) prije Q, uključiv zastavicom; (d) testovi na lažnim izlazima | — | testovi prolaze; `set_fail` se vidi u JSONL | — |
| **F1** put upisa | (a) jedno učitavanje, `set RX_EQA_CKP_OFFSET=2`, zatim 10 × `get` kroz 5 s (je li upis samo kasni?); (b) **zaštita od upisa [S3]:** `RX_EN_EQA=0` → `RX_EQA_CKP_OFFSET=2` i `RX_EQA_CKP_LF=0x83` → readback → `RX_EN_EQA=1` → readback. Ne pisati 0: u formatu {3 b pomak, 5 b mantisa} [S5] 0 vjerojatno gasi petlju offseta; (b') sirova riječ 0x04 prije i poslije, maska 0x00FF, podatak 0x55 (provjera bit-pozicije); (c) **funkcionalni test reseta:** TAPW pin +3 → `restore` → izmjeri 30 s (očekivano ≥ 10⁻⁶) → jedna razina (L1 EQA, L1b RX, PMA) → 30 s. Svaka razina 3× na istom učitavanju; (d) učitati B0 i pročitati `RX_EQA_CKP_OFFSET` | ≈ 45 min | (c) razina **djeluje** ako vrati ≥ 2 dekade u 3/3; (d) readback 0 → bit postavlja polje, JTAG ga ne može | ako (a)–(b) ne prolaze: 0x03/0x04[7:0] su „samo bit” (O11 ide kroz B); ako (d) vrati 1: polje drži hardver, O11 se zatvara |
| **F2** dijagnoza poda i redoslijeda | (a) **O8** gs TX idle: A (normalno) / B (gs TX idle, mjeri M2→GS) / A, 60 s svaki, 3 učitavanja; isto za m2 TX idle; (b) **O6** 2×2 TX_AMP po ploči, svaka ćelija 60 s nakon `readapt`, 3 učitavanja | ≈ 1,5 h | (a) B/A ≤ 0,1 na 3/3 → pod je preslušavanje ili napajanje vlastitog TX-a; (b) ćelija bolja od (12,12) za ≥ ×2 u lošijem smjeru bez pogoršanja drugog | ako (a) B/A ≈ 1 → pod je kanal ili RX: dalje O5/O7 i hardver (H4/H5) |
| **F3** bitovi kroz vrata | za svaki krak B0…B4: **20 pokretanja vrata** (svako novo učitavanje, `--max-attempts 10`), bilježi se prolaz iz 1. pokušaja i BER prihvaćenog (C 60 s). Redom B0 → B1 → B2 → B3 → B4 | po kraku ≈ 20 × (1–3 min) = 30–60 min | krak pobjeđuje ako je prolaz iz 1. ≥ 0,8 (≥ 16/20), ili ako je bolji od prethodnog uz Fisher p < 0,05 | ako B1 i B2 ne pomaknu prolaz iz 1. (≤ 0,45), lutrija nije u reset-FSM → ostaje O9 (vrata). Ne graditi daljnje reset varijante |
| **F4** rangiranje na stresnoj točki | na pobjedničkom bitu i prihvaćenom učitavanju: **margina amplitude** = najmanji TX_AMP druge strane uz koji je smjer < 10⁻⁹ u 30 s (koraci 12, 10, 8, 6, 4; nakon svakog `readapt`). Uspoređuju se točke O5 (m2 POST 6/8/10/12) i O7 (PEAK 24/16/12) po margini, ne po BER-u na radnoj točki | 3 učitavanja × ≈ 15 min | točka s ≥ 1 korakom amplitude više margine na 3/3 ulazi u bit | ako nijedna točka ne daje ni 1 korak, registri su iscrpljeni na 2,5 G → hardver (§4) |
| **F5** soak | pobjednički bit, 3 neovisna prihvaćena učitavanja × 2400 s (ili 1 × 6,7 h) | 2–7 h | **„bez grešaka”: 0 grešaka po smjeru u 2400 s na 3/3** (svaki < 10⁻¹² uz 95 %). „Stabilno”: 0 gubitaka sinkronizacije, prozori Poissonovi | ako je BER > 10⁻¹² na 2/3: tvrdnja „bez grešaka” na 2,5 G nije postignuta. Za uporabu CRC + retransmisija (revizija §6) |

**Ukupni prolaz iz 1. pokušaja kao cilj:** nakon F3 izmjeriti 30 pokretanja na konačnom bitu. Prihvatiti ≥ 28/30
(donja 95 % granica 0,805). Između faza nema rebuilda bez potrebe: F1, F2 i F4 su JTAG, F3 je jedini krug bitova.

### 3.4 Što se bilježi (dopuna revizije §4.4)

Uz postojeći JSONL po pokušaju: `set_ok` (svaki `set` s readbackom), sirove riječi 0x01, 0x03, 0x04, 0x2B, `RX_CDR_FREQ_ACC_VAL` i
`PHASE_ACC_VAL` (10 čitanja kroz 1 s), sha bita, krak (B0…B4) i, kad postoji, `readapt`: da/ne. Nakon F3 to je ≈ 100+ pokušaja s
punim zdravljem: dovoljno da se provjeri predviđa li ikoja veličina dobro učitavanje (revizija §4.4).

---

## 4. Što treba izmjeriti Goran (hardver)

| # | Mjerenje | Kako | Kad | Zašto / odluka |
|---|---|---|---|---|
| **H1** | **VDD_SER (TP10) i VDD_SER_PLL (TP8), DC**, obje ploče, + VDD_CORE na bilo kojem kondenzatoru jezgre | multimetar; 2,5 G bit u radu, zatim 5 G bit (P2) u radu; zapisati i vrijednost R105/R106 na svakoj ploči | prije F3 (10 min) | < 1,00 V tvrdo izvan DS-a; < 1,03 V → zamjena 2 Ω → 1 Ω (ili 0 Ω + ferit MPZ1608 + 10 µF na GS). Bez ovoga nema 5 G (revizija P5-1) |
| **H2** | **AC šum na TP10/TP8** | osciloskop, kratka masa (opruga), AC, puni pojas i 20 MHz; link u radu, zatim gs TX idle (F2 a) | uz F2 | vidi li se skok šuma s TX opterećenjem → H3 (sprega napajanja). Prag za odluku: > 20 mV pk-pk ili vidljiva komponenta na 62,5/31,25 MHz |
| **H3** | **Refclk na M2 strani** (SER_CK nakon FFC/adaptera) | osciloskop diferencijalno ili dvije sonde; amplituda, zvonjenje, oblik | prije 5 G | dvostruka terminacija (PLL_REF_RTERM 1 na obje) = pola amplitude (TUNING_5G §2.4). Ako je swing < 250 mV ili brid zvoni → refclk fan-out ili RTERM 0 samo na jednoj strani (uz novi A/B) |
| **H4** | **Identifikacija FFC-a i adaptera** | duljina, tip/proizvođač, oklop ili mase između parova; fotografija | odmah (bez instrumenta) | najveća nepoznanica kanala (`SI_SERDES_GS_v004.md`). Ako F2 a pokaže preslušavanje: kraći ili oklopljeni FFC kao A/B |
| **H5** | **Zamjena FFC-a** (kraći ili drugi) kao A/B | jedan kabel ↔ drugi, isti bit, 5 pokretanja vrata svaki | samo ako F2 a pokaže preslušavanje | izravna provjera kanala bez rebuilda |
| H6 | temperatura ploča (dodir ili IR) za vrijeme 30-min soaka | — | uz F5 | Pi je bio na mekom temperaturnom limitu (0xd0008). Ploče nikad nisu mjerene |

---

## 5. Put do 5 G (dopuna revizije §5)

1. Preduvjeti ostaju P5-1…P5-4 (revizija §5.1). H1 je obavezan.
2. **Novo:** prije S1–S5 izgraditi P2 uz `RX_WAIT_CDR_LOCK 1` i `RX_CDR_RESET_TIME 16` (iz O3). Na 5 G pada upravo CDR
   (gs RX_CDR_LOCKED 0 u 7/9, PLL čist). Ako reset-FSM pusti EQA prije CDR-a, DFE adaptira na nezaključan takt. Na 5 G je to
   vjerojatnije nego na 2,5 G.
3. **Novo:** isti redoslijed kao §1.4: obje ploče gore, pa RX reset obje (ili fabric reset port, O12).
4. S1 (simetrični TX_AMP) zamijeniti 2×2 testom po ploči (O6). FFE na 5 G odmah asimetrično (O5): kanal M2→GS traži više
   ekvalizacije već na 2,5 G.
5. 5G vrata (Q ≤ 16, C ≤ 120), 5G-1/2/3 i pravilo zaustavljanja ostaju. Ako 5G-1 ne prođe nakon H1 (≥ 1,05 V), B1/B2 na 5 G i
   S2–S5, sljedeći korak je hardver: refclk (H3), FFC/adapter (H4/H5), M2 v0.2 Zdiff 85 Ω.

---

## 6. Nesigurnosti

- **Zašto 0x03, 0x04[7:0] i 0x2B ne pokazuju upis**, ne znam. Ni DS1001 ni UG1001 ne opisuju semantiku čitanja regfilea.
  Moje čitanje („stroj stanja posjeduje polje”) je PRETPOSTAVKA. F1 je napravljen da je odbaci ili potvrdi.
- §1.2 počiva na 3 učitavanja aba2 i na koracima od 30–60 s. „Dvije razine na l1” mogu biti i slučajnost (3 dobra / 3 loša).
- Omjeri u §1.5 su pojedinačni koraci uz drift A. Smjer za pre0 (3/3 oba) je pouzdan. ffe_q0, post8, amp16 i peak16 su
  2–3/3 po smjeru, pa su to kandidati, ne nalazi.
- O3 (`RX_WAIT_CDR_LOCK`) je hipoteza iz DS zadane vrijednosti i iz komentara pu-cc. Nema mjerenja da je danas problem.
- O8 pretpostavlja da `TX_ELEC_IDLE_OVR`/`TX_ELEC_IDLE` (0x41) drže preko JTAG-a. To F1 provjerava prije F2.
- Napajanje nikad nije izmjereno (H1).
- Format {pomak, mantisa} za CKP koeficijente izveden je iz testbencha Cologne Chipa [S5], nije dokumentiran. Prije K8 vrijedi
  pitati Cologne Chip (Patrick Urban, support@colognechip.com) za zaštitu upisa dok je `RX_EN_EQA=1` i za format koeficijenata.

---

## 7. Dokazi (ponovljivo)

```
cd ulx5m-gs-m2-serdes/docs/data_20261017/t5553
python3 write_readback.py  > write_readback.out   # §1.1
python3 eqarst_reroll.py   > eqarst_reroll.out    # §1.2
python3 aba2_ratio.py      > aba2_ratio.out       # §1.5
python3 plan_stats.py      > plan_stats.out       # §3.1
```

Ulazi: `data_20261016/t5542/calib/k12a.jsonl`, `data_20261017/t5542_chain4/gate/k3r_2.jsonl`, `SOAK_R1_2G5_20261017.md` i
**snimke** `t5553/aba2.out`, `t5553/aba2.jsonl`, `t5553/eeqa.jsonl`. Original ovih triju u `data_20261016/t5542/calib/` u repou je
bio prazan ili nepraćen (Jelenin rad u tijeku), pa su kopirani 17.10. sha256 snimke = original:
aba2.out `1430d9fa…`, aba2.jsonl `e81119a3…`, eeqa.jsonl `a2463bef…`.
Pročitano: `CALIBRATION_REVIEW_20261016.md`, `SOAK_R1_2G5_20261017.md`, `CHAIN4_5G_P2_20261017.md`, `TOOLCHAIN_20261017.md`,
`TUNING_5G.md` §1.3–1.4, `SERDES_KNOWLEDGE.md`, `SERDES_UMJERAVANJE_KAKO_DRUGI_20261015.md`, `SI_SERDES_GS_v004.md`,
`tools/serdestool.py` (regfile mapa, `wr_serdes_regfile`), `tools/eyescan.py` (`cmd_set`), `tools/lab/link_gate.py`
(`after_load`, `reconnect`), `tools/lab/calib_aba.py` (`PLAN`, `EQARST`), `gateware/ber/ber_top.v` (reset i regfile portovi),
`gateware/upstream_cc_20261015/serdes_lb.v` i UG1001 tabl. 7.10 (regfile port).

## 8. Izvori

| # | Izvor | Što iz njega |
|---|---|---|
| S1 | Cologne Chip DS1001, rujan 2026 (lokalna kopija `~/app/raid/work/tmp-arhiva/serdes_research/ds26.txt`): str. 58, 60–61, 70–72, 80, 89–90, 155 | CKP_OFFSET r/w, zadano 0x01; lanac reseta ADPLL → TX_RESET_DONE → RX_RESET_DONE; ADPLL isključiti prije promjene postavki u radu; ≥ 16 taktova između pristupa regfileu (CPE); TX FFE 125 grana, SEL ≤ BRANCH_EN; VDD_SER 1,00–1,10 V; DCO ≤ 2500 MHz |
| S2 | prjpeppercorn `libgm/src/TileBitDatabase.cpp:434-449` (YosysHQ), nextpnr-himbaechel `gatemate/pack_serdes.cc` | bit-pozicije 0x01, 0x03, 0x04; `RX_WAIT_CDR_LOCK` 0x01[15] |
| S3 | pu-cc/gm_serdes_lb `serdestool.py` (HEAD 56aa48b, 18.09.2026), r. 1354–1402, 1633 — https://github.com/pu-cc/gm_serdes_lb | tiho blokirani upisi (`RX_EQA_CONFIG` dok je `RX_EN_EQA=1`, `RX_TH_MON2` dok je `EXT_VALUE[3]=1`); zamrzavanje s `RX_EQA_CONFIG[8:6]=0` |
| S4 | prjpeppercorn PR #20, commit b1eb52f (16.06.2026) — https://github.com/YosysHQ/prjpeppercorn/pull/20 | ispravljena mapa 0x2B; `CMD_CHG_STATUS` bit 6 = pristup SERDES regfileu iz CPE-a (potrebno za O12 preko `REGFILE_*` porta) |
| S5 | openCologne-PCIE `5.sim/tb_ccfpga_serdes.v:302-305` | koeficijenti petlje pisani kao 3 + 5 bita (`CKP_LF/HF = 8'b101_00011`, `CKP_OFFSET = 8'b000_00001`) |
| S6 | Xilinx UG476 (7 Series GTX/GTH), str. 195 — https://0x04.net/~mwk/xidocs/ug/ug476_7Series_Transceivers.pdf | adaptacija na 8b10b uzorcima može driftati; PRBS-7+ za trening; HOLD nakon treninga |
| S7 | https://github.com/intergalaktik/ulx5m-gs/issues/28; Olimex GateMate EVB shema | SerDes i niski VDD_CORE / VDD_SER |
| S8 | Maxim HFTA-010.0 (BER confidence) — https://optiwave.com/wp-content/uploads/2014/11/3419.pdf ; Agilent 5989-3206EN (dual-Dirac) | 3,00/BER (95 %), 4,61/BER (99 %); Q = 7,03 na 10⁻¹² |
| S9 | `SERDES_UMJERAVANJE_KAKO_DRUGI_20261015.md` (Xilinx, Intel, PolarFire, TI, PCIe) | redoslijed treniranja i zamrzavanja, sweep po grupama |

Javnog izvještaja o 5 G na GateMate SerDesu nisam našla. pu-cc/gm_serdes_lb je jedini dizajn „za 5G testove” i nema objavljen
rezultat. gatemate-pipe (PCIe Gen1, 2,5 G) i liteeth 1000BASE-X (1,25 G) koriste zadane vrijednosti. Detaljan zapis web pretrage je
u `data_20261017/t5553/web_research.md`.
