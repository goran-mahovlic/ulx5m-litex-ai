# Revizija kalibracije GS↔M2 SerDes (2,5 G i 5 G) — što još podesiti za bolji i stabilniji signal (TASK-5541, 16.10.2026)

**Zahtjev:** Goran 16.10. 16:53: „Treba ponovno provjeriti kalibraciju je li ispravna … što bi se još moglo podesiti i kako da
dobijemo bolji i stabilniji signal … nakon kalibracije imamo li 5G signal.” **Napisala:** Kosjenka (arhitektura), iz rada
Jelene, Mande, Dore i svojih ranijih revizija. **Ploče i Pi nisam dirala.** Novo mjerenje nije rađeno; nova je samo analiza
postojećih sirovih podataka (§2.2, skripte u `data_20261016/t5541/`). Nastavak (mjerenja i alat) radi Jelena u TASK-5542.

Oznake: **UTVRĐENO** = izmjereno na pločama, ponovljeno na ≥ 3 učitavanja ili na izvoru (DS1001, kod). **POJEDINAČNO** = izmjereno,
ali na 1–2 učitavanja ili prije neke promjene hardvera. **PRETPOSTAVKA** = preuzeto (pu-cc, DS) ili izvedeno, nije izmjereno kod nas.

---

## 0. Kratki odgovor

1. **Kalibracija je ispravna u smislu „ništa nije krivo postavljeno”.** Svaki parametar u bitovima (`gs 99d80788` / `m2 3f4857df`,
   PROFILE 1 + TX_AMP 12) ima ili mjerenje iza sebe ili je bez mjerljivog učinka (§1). Nisam našla polje koje je pogrešno ni
   zamku koja bi se ponovila (TRANS_TH 0, TH_MON2 zaključan, TAPW zaštićen, RTERM isključen — sve riješeno).
2. **Kalibracija nije završena.** Na 2,5 G ostaje jedan veliki problem: **lutrija po učitavanju**. Isti bitovi daju 10⁻¹¹ ili
   5·10⁻⁸, ovisno o učitavanju. Prag < 1e-9 u 60 s prolazi otprilike svako drugo do treće učitavanje (lab39 7/21 iz prve,
   10/21 s G2, lab40 0/6, lab41 1/4). Unutar jednog učitavanja BER je stabilan satima (§15, lab39 soak 4,8 h).
3. **Novo iz ove revizije (§2.2):** u svih 56 zapisa (učitavanje ili G2 korak × smjer, lab39/lab41/b900) s ≥ 10 loših riječi greške su **linijske**. Na svaku lošu
   riječ dolazi 1,2–4,3 kodne 8b10b greške (medijan 2,8 za M2→GS i 2,3 za GS→M2), i nema nijednog slučaja s lošim riječima bez
   kodnih grešaka. Dakle lutrija **nije** u neusklađenom putu fabric↔SerDes (zamka 2, TX_NEG/RX_NEG). Ona je u analognom stanju koje
   se postavi pri resetu: adaptacija DFE/offseta, CDR ili TX/PLL. Time `RX_NEG` i rebuild sa seedovima padaju s popisa.
4. **Najveći dobitak nije novi parametar nego postupak:** vrata kvalitete s automatskim ponovnim učitavanjem (§4). Uz p ≈ 0,33–0,48
   po učitavanju očekuju se 2–3 pokušaja. Vjerojatnost da 10 pokušaja ne prođe je 0,1–2 %. Prag i trajanje izvela sam iz
   Poissonove statistike (§4.2).
5. **Napajanje treba izmjeriti prije bilo kakvog 5G posla.** S R105/R106 = 2 Ω izlazi VDD_SER ≈ 1,02–1,03 V, a na donjem kutu
   VDD_CORE −50 mV i 0,97 V. To je ispod DS1001 minimuma od 1,00 V. 2,5 G je očito tolerantan (najbolji medijan 28.09. bio je s
   5,1 Ω, procjena ≈ 0,9 V), ali za 5 G treba ≥ 1,05 V, a to s 2 Ω nije moguće (§3, K2; §5).
6. **5 G:** zasad nema dokaza da će raditi. U rujnu 5 G nije radio ni s VDD_SER ≈ 1,05 V (1 Ω), BER je bio ~10⁻². Od tada su
   promijenjeni TX_AMP (pragovi više nisu na rubu), C143/C144 i napajanje HAT-a. Plan u §5 ima stroga vrata (5G-1/2/3) i pravilo
   zaustavljanja: ako 5G-1 ne prođe ni nakon popravka napajanja i S1–S5, sljedeći korak je hardver (kanal, refclk), a ne registri.

---

## 1. Je li sadašnja kalibracija ispravna — parametar po parametar

Bitovi u pogonu: `ber_{gs,m2}_2g5_p1_txneg_amp12_*` (PROFILE 1, TX_NEG 1, OV_TX_AMP 12, CKI 0), `.serdes` je provjeren polje po polje
u REVIEW_INIT §3. Izvori u stupcu „dokaz” su odjeljci `VERIFY_20260926_RATES.md` (§) ako nije drukčije navedeno.

| Parametar | U bitu (oba) | Status | Dokaz / što nedostaje |
|---|---|---|---|
| **TX_AMP** | 12 (od 31) | UTVRĐENO da je bolji od 31; **nije utvrđeno da je optimum** | §18.8 lab38: simetrično 12 → lošiji smjer ×4–36 bolji na 3/3, TH_MON silazi s +15 (12–14). §18.11 lab39 21 učitavanje + soak 4,8 h. Ispod 12 simetrično nije mjereno (r1 je imao optimum na 16, r2/r3 na 12), pa „pad iza vrha” (Intel/Dora G3) nije pokazan → kandidat K4 |
| TX FFE: BR_PRE/POST 12/12, SEL_PRE/POST 5/5 (−2,3 dB), DC_ENABLE 43 | pu-cc 5G set | POJEDINAČNO | FFE isključen je ×40–40 000 gori za M2→GS (lab38, 3 učitavanja, na AMP 31/20). Tablica preseta (Dora G4) **nikad nije pokrenuta na AMP 12**. m2 POST 10–15 „pobjednici” iz §14.2 nisu preživjeli ponavljanje (§14.3, na AMP 31, prije C143/C144) → K5 |
| TX_DETECT_RX_I 0, TX_CALIB_EN 1 | kao upstream | UTVRĐENO (bez učinka / nužno) | §9.2, Mann–Whitney null (§9.9) |
| RX_AFE_GAIN 0 | min | UTVRĐENO | §2: GAIN 0 → 6·10⁻⁷, GAIN 4/8 → 2·10⁻². §14.2: GAIN 1/2 gori (pojedinačno). **Na AMP 12 nije ponovljeno**: signal je sada manji, pa GAIN 1 treba jedan A/B → K6 |
| RX_AFE_PEAK 24 | pu-cc | POJEDINAČNO (ravno) | §2: 20–31 skoro isto; §14.2 16/8/31 pojedinačno, bez pobjednika. Za 2,5 G PEAK nije poluga. Na AMP 12 nije mjereno → K6 (jeftino, isti krug) |
| RX_AFE_VCMSEL / RX_RTERM_VCMSEL 3 | pu-cc | POJEDINAČNO | §14.2: VCMSEL 4 je ×100–2500 gori (1 učitavanje). Kod 2 nije mjeren. Apsolutni CM ide s VDD_SER (tabl. 2.42): 3 → 21/29·VDD = 0,74 V na 1,02 V → K10, nizak prioritet |
| RX_EN_EQA 1, EQA_LOCK_CFG 0xC | pu-cc | UTVRĐENO da treba (5 G CDR lock samo s DFE). LOCK_CFG varijante bez dobitka | §3, lab29/30 (LOCK_CFG 0/2/0xE bez pomaka). `RX_EQA_CKP_LF/HF/OFFSET` (brzina petlje adaptacije) **nikad nisu dirani** → K8 |
| Adaptirana točka (TH_MON, TAPW, OFFSET) | adaptira se | UTVRĐENO da se na AMP 12 adaptacija ponaša zdravo | lab39 soak: TH_MON gs 12–13 / m2 14 (s ruba), TAPW gs 0–1 / m2 1, OFFSET gs 1–2 / m2 2–3. Na AMP 31 su bili na +15 (§17.2), pa DFE nije imao gradijent |
| TAPW pin +2 (gs) | **nije u bitu** | UTVRĐENO kao *uvjetno* pravilo | Pomaže samo prijemniku koji je loš na tom učitavanju, a dobrog kvari (§18.4–18.5). Mjereno na AMP 31. Na AMP 12 kada TAPW nije ponovljena → K7 |
| G2 (PRBS-15 adaptacija + freeze) | nije u bitu | UTVRĐENO kao uvjetno, slabo | §18.7/§18.11: od 14 loših popravio 3. M2→GS je bio bolji 7 puta i gori 7 puta. Može pokvariti dobro učitavanje (r1). Ponovno učitavanje radi bolje |
| RX_OFFSET (offset petlja) | adaptira se | UTVRĐENO **negativno** | Pin offseta daje najviše ×4 (§18.3). Početni offset ne predviđa dobro učitavanje (§18.9, §18.11). Preslikavanje AFE↔OFFSET je izmjereno (§18.9) |
| CDR: CKP 0x3E, TRANS_TH 8, CKI 0, LOCK_CFG 0xD5 | pu-cc + popravak | UTVRĐENO za CKI 0 i TRANS_TH 8 | CKI 0: lab40 24/24 lock bez SET_ACC (§19.2), uz dijeljeni refclk 0,0 ppm. CKP 30/126/248 i TRANS_TH 16 su gori na AMP 31 (§14.2–14.3). Na AMP 12 nije mjereno → K9, nizak prioritet |
| RX_RESET_TIMER_PRESC 4, RX_WAIT_CDR_LOCK 0 | pu-cc | PRETPOSTAVKA (radi) | RX_BUF_ERR je 0 na svim čitanjima. Nije mijenjano |
| RX terminacija | interna 100 Ω, kalibrirana prema R109 200R | UTVRĐENO (shema) | `RX/TX_CALIB_CAL` 0/0 u dobrim razdobljima, 9/7 u lošim (12.–13.10.) — korelacija u 3 razdoblja, uzrok nepoznat (§16). 15.10. je 0/0 na obje ploče (log33, q30). Treba ga bilježiti pri svakom učitavanju (§4.4) |
| PLL: N 1·5·5, OUTDIV 2, FCNTRL 58, BISC mode 5 | upstream / pu-cc | UTVRĐENO | Lock na svakom učitavanju, FT_OF/UF 0. CAP_FT gs 496–499 / m2 508–511 (15.10.). DCO 2500 MHz je **gornji rub** raspona DS1001 (i za 2,5 G i za 5 G) |
| Refclk: dijeljeni GS X2 (Si511), PLL_REF_RTERM 1 na obje | | UTVRĐENO | Odvojeni refclk je 20–1000× gori (§11.2–11.5). RTERM 0 na M2 je ×25 gori (§11.3). Jitter nije mjeren (DS ≤ 1 ps). Jedan LVDS izvor vidi **dvije** terminacije (polovični swing, TUNING_5G §2.4, PRETPOSTAVKA) → važno tek za 5 G |
| TX_NEG 1, RX_NEG 0, seedovi gs 7 / m2 2 | | UTVRĐENO | Determinističan rebuild (REVIEW_INIT §5). Vidi §2.2: sadašnje greške nisu na fabric sučelju |
| **VDD_SER / VDD_SER_PLL** | R105/R106 = 2 Ω (16.10., uputa #345) | **NIJE IZMJERENO** | Izračun §3 K2: 1,02–1,03 V nazivno, 0,97–0,98 V na kutu −50 mV. Kada je točno ugrađeno 2 Ω (12.10. ili 16.10.) nije zapisano |

**Zaključak §1:** nema pogrešne postavke. Sva otvorena pitanja su „nije pokazano da je optimum na AMP 12”. TX_AMP 12 je promijenio
radnu točku RX-a (pragovi više nisu na rubu), a sve ostale TX/RX/CDR mjere rađene su na AMP 31. Zato je jeftin krug ponovne
provjere (K4–K7) opravdan, ali od njega ne očekujem više od ×2–5. Jedino lutrija po učitavanju vrijedi 2–3 dekade.

---

## 2. Što se zna o lutriji po učitavanju

### 2.1 Činjenice (sve UTVRĐENO)

| Činjenica | Izvor |
|---|---|
| Isti bitovi, isti postupak: raspon između učitavanja 3–5 dekada | §14.5, §16, §18.5 |
| Unutar učitavanja BER je konstantan (pola sata prema pola sata unutar ×1,4; soak 4,8 h bez drifta većeg od ×2 po satu) | §15, §18.11 |
| Lošiji smjer se mijenja po učitavanju (M2→GS u 12/14 loših u lab39, ali i obrnuto u lab30/33) | §18.4, §18.11 |
| Ništa u regfileu ne predviđa dobro učitavanje (OFFSET, CAP_FT, CALIB, TH_MON). Jedini trag ρ = −0,74 nije se ponovio | §14.5, §16, §18.9 |
| Ponovno učitavanje je jedina poluga koja ponovno izvlači stanje: 9/10 pokušaja prihvaćeno unutar ≤ 3 učitavanja | §18.11 |
| Promjene na ploči (12.10. filtar, 15.10. C143/C144) mijenjaju razinu cijele raspodjele za 1–3 dekade | §14.7, §16, §18.1 |

### 2.2 Novo: greške su linijske, ne fabric (analiza ove revizije)

Skripta `docs/data_20261016/t5541/code_ratio.py` za svaki ber_long zapis (lab39 21 učitavanje + G2 koraci, lab41, b900) uzima razliku od prvog do
zadnjeg snimka i dijeli 8b10b kodne greške s brojem loših riječi.

| Smjer | Zapisa s ≥ 10 loših riječi | Kodnih grešaka po lošoj riječi: min / medijan / max | Učitavanja s lošim riječima i 0 kodnih |
|---|---|---|---|
| M2→GS (gs checker) | 35 | 1,21 / 2,83 / 14,5 | 0 |
| GS→M2 (m2 checker) | 21 | 1,83 / 2,25 / 4,29 | 0 |

Kako to čitam (IZVEDENO):
- Bitna greška na liniji u 8b10b kodu daje nevaljan simbol i/ili grešku dispariteta, dakle ≥ 1 kodnu grešku po pogođenoj riječi.
  Greška u neusklađenom paralelnom prijenosu fabric↔SerDes (zamka 2 iz §2) nastaje prije kodera ili poslije dekodera i ne daje kodnu
  grešku. U rujnu je upravo tako izgledala: 1,9·10⁸ loših riječi prema ~10⁴ kodnih grešaka, prije TX_NEG.
- Danas je omjer ≈ 2–3 i na dobrim i na lošim učitavanjima. Loše učitavanje ima **više linijskih grešaka**, a ne drugu vrstu greške.
  Lutrija je dakle u analognom ili taktnom stanju (adaptacija RX-a, CDR, TX driver, PLL faza), ne u sučelju koje nextpnr ne mjeri.
- Posljedice: (a) RX_NEG / novi seed nisu kandidati; (b) RX reset bez ponovnog učitavanja **može** ponovno izvući stanje, ako je
  lutrija u RX-u — to treba izmjeriti (K3), jer je jeftiniji od ponovnog učitavanja i može ići u fabric (flash boot).

### 2.3 Hipoteze o mjestu lutrije (rangirane, za K3)

| # | Hipoteza | Za | Protiv / otvoreno | Test (K3) |
|---|---|---|---|---|
| H1 | RX adaptacija (DFE/offset/pragovi) završi u jednom od više lokalnih minimuma | TAPW pin popravlja loše učitavanje ×34–700 (§18.3, §18.5); G2 ponekad popravi | Na AMP 12 pragovi nisu na rubu, a lutrija je ostala (lab39–41) | RX EQA reset / RX PMA reset samo na lošem prijemniku |
| H2 | Stanje TX drivera ili TX PLL faze druge ploče | m2 TX_AMP utječe na gs RX i na m2 RX suprotnog smjera (§17.5: fizička sprega) | Nije izravno testirano | ponovno učitavanje samo ploče **odašiljača** lošeg smjera |
| H3 | Sprega preko napajanja (TX struja na VDD_SER druge strane), raspodjela ovisi o radnoj točki napajanja | promjene filtra mijenjaju cijelu raspodjelu; VDD_SER je na rubu | uzrok i mehanizam nepoznati | TP10/TP8 + CAP_FT po učitavanju (K2) |

---

## 3. Kandidati za podešavanje — rangirano po očekivanom učinku i trošku

Trošak: **J** = JTAG upis u radni link, bez rebuilda (minute); **B** = rebuild i kvalifikacija ≥ 3–5 učitavanja; **H** = Goran, ruka na
ploči. Svako mjerenje: A/B/A unutar učitavanja, zatim potvrda na ≥ 3 svježa učitavanja, oba smjera zajedno, `ber_windows.py`
(delte, prvi prozor odbačen, Poisson 95 %), PEER 200/200 prije i poslije.

| Rang | Kandidat | Očekivani učinak | Trošak | Mjerljivi kriterij (prolaz) |
|---|---|---|---|---|
| **K1** | **Vrata kvalitete + automatsko ponovno učitavanje** (§4) | **velik i siguran**: svaki prihvaćeni link je u boljoj polovici raspodjele (lab39 soak 8,3·10⁻¹⁰ / 4,2·10⁻¹⁰ prema medijanu prvog pokušaja 9,3·10⁻⁹) | J (Pi skripta), 1 dan | ≥ 9/10 pokretanja vrata završi s PROLAZ u ≤ 10 pokušaja; prihvaćena učitavanja u 300 s: lošiji smjer < 1e-9 na ≥ 90 % |
| **K2** | **Izmjeriti VDD_SER (TP10) i VDD_SER_PLL (TP8)** na obje ploče, s 2,5 G pa 5 G bitom u radu; ako < 1,03 V → **2 Ω → 1 Ω** (GS: ili 0 Ω + feritna perla MPZ1608 na L6/L7 + 4,7–10 µF; M2 nema footprint perle: 1 Ω + 4,7 µF) | 2,5 G: mali ili nikakav (2,5 G je radio i na ≈ 0,9 V). 5 G: preduvjet | H, 10 min mjerenje; zamjena 30 min | izmjereno ≥ 1,00 V (tvrdo), cilj 1,05 V pod 5 G opterećenjem. Uz mjerenje zapisati CAP_FT obje ploče, da CAP_FT postane neizravni monitor napajanja |
| **K3** | **Gdje je lutrija** (§2.3): na lošim učitavanjima isprobati krakove L1 RX EQA reset, L1b RX PMA reset, L2s „meki puni reset” jedne ploče (ADPLL off/on + TX/RX reset preko regfilea), L2 `-r` ploče prijemnika, L2' `-r` ploče odašiljača | određuje koju razinu vrata koriste i može li se ponovni pokušaj izvesti u fabricu bez Pija | J, ~2 h | po kraku ≥ 5 loših učitavanja. Krak ulazi u vrata ako je udio prolaza nakon njega ≥ 0,3 (= svježe učitavanje) i ako je brži od `-r`. **Dokaz da se reset izvršio:** RX_CDR_LOCKED 1→0→1 ili skok PHASE_ACC, novo čitanje TH_MON/OFFSET (H8 iz §14.6 ostao je neodlučan) |
| K4 | **Simetrični TX_AMP fino oko 12**: 8, 10, 12, 14 (16 kao kontrola) | ×1–3 na lošijem smjeru (lab38: r1 optimum 16, r2/r3 12 → vrh još nije omeđen) | J | medijan zbroja BER oba smjera po 3 učitavanja niži za ≥ ×2, TH_MON na obje strane < 15 i > 8 |
| K5 | **Tablica TX FFE preseta na AMP 12**, svaka TX sudi suprotni RX: Q0 0/0, P1 5/5 (sadašnji), SEL_POST 3, 8; pre-shoot 0 / 3 (BR_PRE 12) | ×1–3; FFE je bitan (isključen ×40+ gore), ali je njegov optimum mjeren samo na AMP 31 | J | BER smjera tog TX-a, medijan 3 učitavanja ≥ ×2 bolji od P1 bez pogoršanja suprotnog smjera |
| K6 | AFE na AMP 12: GAIN 0 / 1; PEAK 16 / 24 / 31 | mali (≤ ×2) | J, isti krug kao K4 | kao K4 |
| K7 | TAPW kada (−2…+3) na **lošem** učitavanju na AMP 12; ako je dno stalno ≠ adaptiranog, statički DFE u bit (`RX_EN_EQA=0`, `RX_TAPW`, `EXT_VALUE`, = PolarFire Static_DFE) | na AMP 31 ×34–700 na lošem, a dobrog kvari; na AMP 12 nepoznato | J, pa B | dno kade na ≥ 3/3 lošim učitavanjima isto **i** ne kvari dobro učitavanje (A/B na 2 dobra) |
| K8 | Sporija petlja adaptacije: `RX_EQA_CKP_OFFSET` 0x01 → 0x00, `RX_EQA_CKP_LF/HF` 0xA3 → niže | nepoznat (manje „dithera” na granici koda) — **jedina poluga lutrije koja nikad nije probana** | J | pomak udjela dobrih učitavanja (≥ 10 učitavanja po točki, Fisher) — skupo za statistiku, zato nakon K1 (vrata daju tu statistiku besplatno) |
| K9 | CDR na AMP 12: CKP 0x3E / 0x1E / 0x7E × TRANS_TH 8 / 16 | mali | J | kao K4 |
| K10 | VCMSEL 2 (AFE + RTERM) uz niži VDD_SER | mali | J | kao K4 |
| K11 | Fabric ponovna inicijalizacija za flash boot (REVIEW_INIT N1 + N3 + N4 + N6 u **jednom** buildu) | nužno za rad bez Pija; za BER neutralno | B, 1 dan + kvalifikacija ≥ 5 učitavanja | vrata u fabricu (§4.5) prolaze kao Pi vrata; bitovi i dalje CFGRST i hold 0 |
| — | **Ne ponavljati:** RX_NEG/seed, offset pin/retry, asimetrični TX_AMP, FFE isključen, TRANS_TH 16 na 2,5 G, VCMSEL 4, odvojeni refclk, RTERM 0, CKI ≠ 0, eye counteri (mrtvi, §18.6) | | | |

**Redoslijed izvedbe (prijedlog za TASK-5542):** K2 mjerenje (Goran, 10 min) → K1 vrata (Pi skripta) → K3 (unutar vrata, krakovi) →
K4–K6 u jednom krugu kroz vrata (svaka točka na prihvaćenim učitavanjima, tako lutrija ne prikriva učinak) → K7 → odluka o novom
buildu (K7 statički DFE + K11 u istom buildu, jer svaki build znači novu kvalifikaciju).

Važno za mjerenje K4–K9: točku uspoređivati **na prihvaćenom učitavanju** (A/B/A) i na učitavanju koje je palo na vratima. Inače
raspodjela 3–5 dekada pojede svaki učinak ×2 (to se dogodilo u §14.2–14.3).

---

## 4. Vrata kvalitete linka (Goranova ideja) — dizajn

### 4.1 Tijek

```
POČETAK (bitovi sha256 provjereni, gs lease, UART otvoren)
  pokušaj n = 1..10:
    [RAZINA_n]  izvedi ponovni pokušaj (n=1: učitavanje m2 pa gs, -r)
    [ZDRAVLJE]  obje ploče: PLL_LOCKED, FT_OF/UF=0, RX_CDR_LOCKED, RX_EQA_LOCKED; PEER 200/200 oba smjera
                -> ne prolazi: zapiši razlog, sljedeći pokušaj
    [SMIRI]     5 s, prvi prozor nakon dizanja odbaci (ber_windows)
    [Q, 10 s]   oba smjera: greške <= 8, Δloss = 0, synced = 1; rani izlaz čim greške > 8
                -> ne prolazi: sljedeći pokušaj (razina prema §4.3)
    [C, 60 s]   6 prozora po 10 s: ukupno <= 60 grešaka po smjeru, nijedan prozor > 20, Δloss = 0, udio synced >= 0,999999
                -> ne prolazi: sljedeći pokušaj
    PROLAZ -> zapiši, prijeđi na DUGO MJERENJE (soak, ber_long, ista vrata kao nadzor: prozor > 20 = PRASAK zapisati, ne prekidati)
  10 neuspjeha -> VRATA_PALA: zapiši sve, javi u chat (to je znak promjene hardvera, kao 12.10. ili 15.10.)
```

### 4.2 Prag i trajanje (iz Poissona, `data_20261016/t5541/gate_poisson.out`)

2,5 G: 31,25 M riječi/s × 40 provjerenih bita = **1,25·10⁹ bita/s po smjeru**.

| Stupanj | Bita po smjeru | Prag | P(prolaz) ako je stvarni BER 3·10⁻¹⁰ / 5·10⁻¹⁰ / 1·10⁻⁹ / 2·10⁻⁹ |
|---|---|---|---|
| Q, 10 s | 1,25·10¹⁰ | ≤ 8 grešaka (≈ 6,4·10⁻¹⁰) | 0,985 / 0,82 / 0,125 / 0,000 |
| C, 60 s | 7,5·10¹⁰ | ≤ 60 grešaka (≈ 8·10⁻¹⁰) | 1,000 / 1,000 / 0,043 / 0,000 |
| Q pa C | | | ≈ 0,985 / 0,82 / **0,005** / 0 |
| praskovi | 10 s prozor | > 20 grešaka u prozoru = pad | lažni pad pri 5·10⁻¹⁰: 2,7·10⁻⁶ |

- Zašto 10 s pa 60 s: Q za 10 s odbaci gotovo svako loše učitavanje (≥ 2·10⁻⁹). Lab39 je imao lošija učitavanja 10⁻⁹…3·10⁻⁷,
  pa najčešće pada već nakon 1–3 s (rani izlaz). C od 60 s je mjera Goranovog „5–10 s”, produljena jer lab41 l3 pokazuje
  praskove od 35 s na inače dobrom učitavanju. Kratki Q ih ne bi uhvatio.
- Ukupno vrijeme pokušaja: učitavanje obje ploče + link ≤ 20 s + 5 s + Q 10 s ≈ 40–60 s. Deset pokušaja ≈ 10 min. Očekivano
  (p = 0,33–0,48) 2–3 pokušaja, P(10 neuspjeha) = 0,14–1,8 % (p = 0,25: 5,6 %).
- Za 5 G iste vrijednosti BER-a daju dvostruko više bita: Q ≤ 16, C ≤ 120 (tablica u `gate_poisson.out`).
- **UART ispadi (NOUART)** nisu pad: prozor se produlji do sljedećeg čitanja (kumulativni brojači, `ber_long`). Ako UART šuti > 60 s,
  pokušaj se proglasi NEODLUČEN i ne broji se u 10 pokušaja (najviše 3 takva, zatim stop s razlogom UART).
- **Nikad `Z`** (brisanje brojača preko UART-a) — N3 iz REVIEW_INIT. Sve se računa iz delta.

### 4.3 Što se resetira — ljestvica razina

| Razina | Što | Kako (bez power-cyclea) | Što ponovno izvlači | Status |
|---|---|---|---|---|
| L0 | ništa, samo ponovno izmjeri | — | — | za NEODLUČEN (UART) |
| L1 | RX EQA reset **lošeg prijemnika** | regfile 0x2B: `RX_EQA_RESET_OVR=1`, `RX_EQA_RESET=1`, pa oba 0 | DFE tap, pragovi | **nepoznato** → K3 |
| L1b | RX PMA (+CDR) reset lošeg prijemnika | 0x2B `RX_PMA_RESET_OVR/RESET` (i `RX_CDR_RESET_OVR/RESET`), pa otpustiti; ne kopirati upstream `reset_serdes_rx` (otpušta na 0x3F, bug) | offset kalibracija, CDR, EQA | **nepoznato** → K3 |
| L2s | meki puni reset jedne ploče | `PLL_EN_ADPLL_CTRL` 1→0→1 (radilo u §13), zatim 0x3F `TX_RESET_OVR/RESET` i 0x2B `RX_RESET_OVR/RESET` | PLL + TX + RX te ploče, bez ponovne konfiguracije | **nepoznato** → K3; to je ono što bi fabric watchdog radio |
| L2 | `fpga-jtag <ploča> <bit> -r` ploče lošeg prijemnika | postojeći alat | sve na toj ploči | djelomično (lab40 l1–l6 je učitavao obje) |
| L3 | `-r` obje, m2 pa gs | postojeći postupak lab39/40 | sve | **UTVRĐENO**: 9/10 pokušaja prihvaćeno u ≤ 3 |

**Zadana ljestvica do rezultata K3:** svaki pokušaj je L3. To je jedini dokazani mehanizam. Kad K3 pokaže da L1/L1b/L2s rade
(udio prolaza ≥ 0,3), ljestvica postaje: pokušaji 1–3 jeftina razina koja radi, 4–10 L3. Ploča „lošeg prijemnika” je ona čiji RX
ima veći BER. Ako su oba smjera loša, ide L3.

G2 (PRBS adapt + freeze) **nije** u ljestvici: popravio je 3/14 i može pokvariti, a ponovno učitavanje je bolje (§18.11).

### 4.4 Bilježenje (svaki pokušaj, JSONL)

Datoteka `docs/data_<datum>/gate/<run>.jsonl` u repou i kopija `/home/pi/fpga/gate.log` (jedan redak po vratima). Jedan zapis po pokušaju:

```json
{"run":"gate_20261017_0900","attempt":3,"level":"L3","t":"2026-10-17T09:04:12+02:00",
 "bits":{"gs":"99d80788","m2":"3f4857df"},"t_link_s":17.5,
 "health":{"gs":{"PLL_LOCKED":1,"FT_OF":0,"FT_UF":0,"PLL_CAP_FT":498,"RX_CALIB_CAL":0,"TX_CALIB_CAL":0,
                 "RX_CDR_LOCKED":1,"RX_EQA_LOCKED":1,"RX_TH_MON":13,"RX_EQA_TAPW":1,"RX_OFFSET":2},"m2":{"...":"..."}},
 "peer":{"gs":"200/200","m2":"200/200"},
 "q":{"m2_to_gs":{"err":3,"bits":1.25e10},"gs_to_m2":{"err":0,"bits":1.25e10},"dloss":[0,0],"verdict":"PASS"},
 "c":{"windows_m2_to_gs":[1,0,2,0,1,0],"windows_gs_to_m2":[0,0,1,0,0,0],"sync_frac":[1.0,1.0],"verdict":"PASS"},
 "pi":{"throttled":"0xd0000","temp_c":55.2},"verdict":"PASS","reason":null}
```

- Zdravlje se bilježi **i kad pokušaj pada**. Nakon ~50 pokušaja to je prvi skup podataka iz kojeg se može vidjeti predviđa li
  ikoja veličina (CAP_FT, CALIB_CAL, TH_MON, TAPW, OFFSET) dobro učitavanje, bez ijednog dodatnog sata u labu.
- Sažetak po vratima: broj pokušaja, razina koja je prošla, BER prihvaćenog. Postojeći `proof_table.py` treba proširiti za `gate/*.jsonl`.
- Dnevni udio prolaza iz prve je **detektor promjene hardvera**: pad s ~0,4 na ~0 znači da se nešto na ploči promijenilo.

### 4.5 Gdje vrata žive

| Faza | Gdje | Zašto |
|---|---|---|
| 1 (odmah) | Pi: `tools/lab/link_gate.py` (Jelena, TASK-5542), na postojećim alatima `fpga-jtag`, `eyescan.py get`, `ber_jtag_check`, `ber_long`/`ber_windows`. Testovi na lažnim snimkama (prolaz, rani pad, prasak, NOUART, 10 neuspjeha) | nema rebuilda, nema nove lutrije smještaja, ljestvica se mijenja konfiguracijom |
| 2 (flash boot, nakon K3) | fabric, u istom buildu s K11: svaka ploča sudi **svoj** RX (gs svoj checker, m2 svoj). Ako synced = 0 dulje od 5 s, ili > 8 grešaka u 10 s → puls `RX_EQA/PMA_RESET_I` (portovi postoje, sada su vezani na 0, `ber_top.v:108`). Ako to ne pomogne, pa je razina L2s, ponovni puls `rst`. Brojač pokušaja ide u UART izvještaj (`flg[5]` je slobodan) | radi bez Pija i bez JTAG-a. Ali gs nema „učitavanje” — L3 iz fabrica ne postoji, pa ima smisla samo ako K3 pokaže da L1/L2s ponovno izvlače stanje |

---

## 5. Plan za 5 G nakon kalibracije

### 5.1 Što mora vrijediti prije prvog 5G mjerenja

| # | Preduvjet | Kriterij | Zašto |
|---|---|---|---|
| P5-1 | VDD_SER (TP10) i VDD_SER_PLL (TP8) izmjereni na obje ploče **s 5 G bitom u radu** | tvrdo ≥ 1,00 V (DS1001 str. 155), cilj ≥ 1,05 V | s 2 Ω: 1,10 − 2 Ω × 40–51 mA = 1,00–1,02 V nazivno, 0,95–0,97 V na kutu −50 mV. Za ≥ 1,05 V treba ≤ 1 Ω (1,05–1,06 V nazivno) |
| P5-2 | 2,5 G vrata rade | ≥ 4/5 pokretanja PROLAZ | inače ne razlikujemo „5 G ne radi” od „ova ploča danas ne radi” |
| P5-3 | Mjerilo za M2→GS na 5 G | gs checker radi na 51 MHz < 62,5 MHz (amp12 build) → bez toga je M2→GS samo PEER/1000 (grubo, ≥ 10⁻³) | izbor: (a) samo GS→M2 iz m2 checkera + PEER za drugi smjer; (b) far-end PMA loopback na gs (M2→GS→M2 mjeri m2 checker); (c) lakši gs checker. Za 5G-1/5G-2 dovoljno je (a) |
| P5-4 | Zdravlje na 5 G | PLL lock, FT_OF/UF 0 na obje (DCO 2500 MHz je gornji rub), CAP_FT zapisan | ako FT_OF dođe s nižim VDD_SER_PLL, to je nalaz o napajanju, a ne o SerDesu |

### 5.2 Recept (redom, Dorin G-redoslijed; svaki korak A/B/A na jednom učitavanju, pobjednik na 3 svježa)

| Korak | Što | Polazna točka |
|---|---|---|
| S0 | osnovica nakon P5-1: P2 i P3 bitovi kakvi jesu, 3 učitavanja × 60 s | §16: P2 1,7·10⁻² / 5,1·10⁻², PEER 88–93 %, CDR m2 0 |
| S1 | **simetrični TX_AMP 31 → 24 → 20 → 16 → 12** na P2 | na 5 G m2 TH_MON = +15 (rub), gs 13–14 (§17.2) → ista priča kao 2,5 G prije lab38; nikad mjereno na 5 G |
| S2 | TX FFE na najboljem AMP: BR_POST 31, BR_PRE 0, DC_ENABLE = N_BRA/2 = 47, SEL_POST 0 / 6 / 12 / 17; pa pre-shoot 0 / 3 | §9.9: SEL_POST 0/6 je imao ~200× dulje vrijeme u sinkronizaciji |
| S3 | CTLE: PEAK 24 / 16 / 12 / 8 × GAIN 0 / 1 | PEAK 12 manje grešaka dok je link sinkroniziran, PEAK 24 dulje sinkronizirano (§9.10) |
| S4 | DFE: LOCK_CFG 0xC / 0x4 / 0x8; G2 (PRBS adaptacija + freeze) kao zaseban krak — na 5 G je adaptacija na slučajnom uzorku važnija (Xilinx, Dora §3.1) | |
| S5 | CDR: CKP 0x3E / 0x1E / 0x7E × TRANS_TH 8 / 16 | P3 (CKP 0x1E, TH 16) je dulje sinkroniziran od P2 |
| S6 | najbolju točku u PROFILE 4 bitove (CFGRST, hold 0), 3–5 svježih učitavanja × 300 s, zatim 5G vrata | samo bit vrijedi (zamka 1) |

Rangirati po **udjelu sinkroniziranog vremena pa po BER-u** (`ab_table.py --runs --rank`), jer na 5 G BER računat samo dok je link sinkroniziran vara (§9.9).

### 5.3 Kriterij uspjeha i zaustavljanja

| Vrata | Kriterij (na ≥ 2/3 učitavanja, ako nije drukčije) | Značenje |
|---|---|---|
| **5G-1 „ima signala”** | RX_CDR_LOCKED = 1 na obje ploče na početku i na kraju; PEER ≥ 990/1000 oba smjera; udio synced m2 checkera ≥ 0,99 | danas pada (CDR m2 0, PEER 83–93 %) |
| **5G-2 „upotrebljiv”** | GS→M2 BER < 10⁻⁶ u 60 s; M2→GS po P5-3 < 10⁻⁶ (ili PEER 1000/1000) | link za protokol s retransmisijom |
| **5G-3 „dobar”** | oba smjera < 10⁻⁹ u 300 s na ≥ 3/5 učitavanja → 5G vrata (Q ≤ 16, C ≤ 120) | razina današnjeg 2,5 G |
| **Stop** | ako nakon P5-1 (≥ 1,05 V) i S1–S5 nijedna točka ne prođe 5G-1 na 3 učitavanja | registri su iscrpljeni. Sljedeće je hardver: H3 identifikacija i skraćenje FFC/adapterskog lanca, H4 refclk na M2 osciloskopom (dvostruka terminacija, jitter ≤ 1 ps), fan-out buffer za refclk; na M2 v0.2 ispraviti Zdiff 122 → 85 Ω (TASK-5540) prije narudžbe |

**Iskreno očekivanje:** 5G-1 je moguć ako je u rujnu glavni problem bio prejak signal (pragovi na rubu, kao na 2,5 G). 5G-3 na ovom
lancu (FFC + adapteri, refclk kroz isti lanac) ne očekujem bez promjene hardvera. U rujnu 5 G nije radio ni na ≈ 1,05 V, pa sam
popravak napajanja nije rješenje, nego samo preduvjet.

---

## 6. Dugoročno (arhitektura)

- **Na 2,5 G nije pokazan link bez grešaka:** najbolje prihvaćeno učitavanje je ~4–8·10⁻¹⁰, dakle oko jedne greške u sekundi. Za
  stvarnu uporabu (Ethernet ili PCIe preko SerDesa) treba CRC + retransmisija ili FEC, bez obzira na kalibraciju. 1,25 Gb/s (1000BASE-X)
  je čist (< 4·10⁻¹¹, `VERIFY_20260926_RATES.md` §1). Ako je cilj GbE, ta brzina je već spremna.
- Sljedeća verzija ploče (H5 iz TUNING_5G, TASK-5535 P1): zaseban LDO 1,05 V za VDD_SER/VDD_SER_PLL ili feritna perla + 10 µF umjesto
  serijskog otpornika; refclk fan-out (jedan driver po prijemniku); SerDes put bez FFC-a; Zdiff 85 Ω na M2 v0.2.
- Vrata kvalitete s bilježenjem su ujedno instrument: zamjenjuju mrtvi eye scan kao izvor statistike o radnoj točki.

---

## 7. Nesigurnosti (što nisam mogla provjeriti)

- VDD_SER/VDD_SER_PLL nisu izmjereni ni na jednoj ploči, nikad. Svi naponi u ovom dokumentu su izračun (struja iz DS1001 tabl. 4.4 i
  TASK-5535). Kada je ugrađeno 2 Ω, nije zapisano, pa ne znam s kojim su otpornikom mjereni lab39/lab40.
- Da RX reset preko regfilea (0x2B) stvarno resetira RX nije dokazano (H8 neodlučan, §14.6). Za W/C strobove PRBS-a jest (§18.6).
- Analiza §2.2 isključuje fabric sučelje za **sadašnji** par bitova. Za novi build (K7/K11) treba je ponoviti na kvalifikacijskim učitavanjima.
- Ne znam je li Goran već upisao `*_auto.bit` u flash. To ne mijenja ovaj plan, jer vrata faze 1 učitavaju u SRAM.

---

## 8. Dokazi (ponovljivo)

```
cd ulx5m-gs-m2-serdes/docs
python3 data_20261016/t5541/code_ratio.py   > data_20261016/t5541/code_ratio.out    # §2.2
python3 data_20261016/t5541/gate_poisson.py > data_20261016/t5541/gate_poisson.out  # §4.2
```
Izlaz (skraćeno):
```
m2_to_gs: ucitavanja s >=10 losih rijeci = 35, kodnih/lose rijeci min 1.21 medijan 2.83 max 14.48
gs_to_m2: ucitavanja s >=10 losih rijeci = 21, kodnih/lose rijeci min 1.83 medijan 2.25 max 4.29
ucitavanja s >=10 losih rijeci i 0 kodnih gresaka: 0
2,5G T=10s bita=1.25e+10 prag k<=8   (BER<=6.4e-10)  P(prolaz|BER) 1e-10:1.000  3e-10:0.985  5e-10:0.820  1e-09:0.125  2e-09:0.000
2,5G T=60s bita=7.50e+10 prag k<=60  (BER<=8.0e-10)  P(prolaz|BER) 1e-10:1.000  3e-10:1.000  5e-10:1.000  1e-09:0.043  2e-09:0.000
p(dobro ucitavanje)=0.33: ocekivano pokusaja 3.0, P(nijedan od 10) = 0.0182
```
Pročitani izvori: `VERIFY_20260926_RATES.md` §1–20, `TUNING_5G.md`, `REVIEW_INIT_20261016.md`, `SERDES_UMJERAVANJE_KAKO_DRUGI_20261015.md`,
`EYE_MEAS_UZROK.md` (zaključak u §18.6), `gateware/ber/ber_top.v`, `tools/serdestool.py` (polja 0x2B/0x3F), sažeci TASK-5522/5523/5525/
5527/5528/5529/5531/5532/5535/5538/5540, RAG `agent_jelena`. Sirovi podaci: `data_20261015/t5527/log39/`, `data_20261015/t5527/log33/`, `data_20261016/t5538/`.
