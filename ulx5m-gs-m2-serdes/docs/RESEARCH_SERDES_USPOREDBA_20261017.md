# Objavljena mjerenja SerDes linka: Cologne Chip GateMate i usporedni FPGA čipovi (TASK-5554)

Nalog: Goran, 17.10.2026. (Telegram, grupa REGOČ), dopuna uputa #351 (11:07, openCologne-PCIE).
Izradila: Manda, 17.10.2026. Svi izvori pregledani **17.10.2026.** (to je „pregledano" uz svaki URL u §7).
Oznake: **PRONAĐENO** (piše u izvoru), **NIJE PRONAĐENO** (tražila sam, nema), **IZVEDENO** (moj zaključak iz izvora ili naših podataka).
Ništa nije mjereno na pločama. Pi i ploče nisu dirani.

---

## 0. Kratki odgovor

1. **Cologne Chip nije nigdje objavio BER, eye ni trajanje mjerenja za SerDes link na 2,5 ili 5 Gb/s.** NIJE PRONAĐENO u DS1001 (rujan 2026), UG1001 (ožujak 2025), DS1003 (EVB, siječanj 2024), tri prezentacije (GSI 2024, FPGA Conference 2025, CERN FDF 2025), na stranicama proizvoda i eval ploče, u vijestima ni u repozitorijima `pu-cc/gm_serdes_lb`, `colognechip/gatemate-pipe` i `chili-chips-ba/openCologne-PCIE`.
   Jedino objavljeno hardversko mjerenje proizvođača je **PRBS-7 i PRBS-15 na 1,25 Gb/s**, s `RX_PRBS_ERR_CNT = 0`. Test je trajao **10 s po uzorku** (`tc_prbs`, petlja `n = 10 × sleep(1)`), na **EVB-u sa SMA kabelima u petlji TX→RX na istom čipu**, uz analogne postavke iz `serdes_lb.v` te verzije (= naš PROFILE 0: PEAK 15, GAIN 8, bez EQA [L3]) [C6][C7]. To je 1,25·10¹⁰ bitova, pa 95 % gornja granica iznosi **BER < 2,4·10⁻¹⁰**. Ni eye ni postavke kanala nisu objavljeni.
2. **openCologne-PCIE (uputa #351):** „x1 Gen1 ✔" odnosi se na PIPE RTL i simulaciju. Na pločici nema nijednog objavljenog mjerenja: `1.serdes-tests/README.md` je prazan predložak („to fill with details… oscillograms") [O3]. Open-source SerDes model **namjerno ne modelira** analogni dio (TX tapove, AFE, DFE, eye) [O1]. Cologne Chipove PCIe postavke (§2.3) koriste **isključenu EQA/DFE adaptaciju i fiksni CTLE**. To je gotovo točno naš PROFILE 0, koji je na našem kanalu 26.09. dao BER 5,9·10⁻⁴ [L3]. To je mjereno prije TX_NEG popravka, pa A/B na današnjim bitovima ima smisla (§2.5, predano Kosjenki).
3. **Drugi proizvođači** objavljuju uglavnom specifikacije „uz BER 10⁻¹²" (DS181, ECP5 DS) i alate (IBERT, Transceiver Toolkit, Efinix debugger, CertusPro eye monitor). Brojevi bitova i trajanje gotovo se nigdje ne objavljuju. Najbliže onome što tražimo:
   - Xilinx WP428 (GTP, 6,25 Gb/s, PRBS31, 30" FR4 ≈ 12 dB): eye scan do 10⁻⁸, zatim ekstrapolacija na 10⁻¹⁵ [X1].
   - Gowin WP1157 (GW5AT): cilj 10⁻¹², PRBS15, kriterij „kolaps internog oka", trajanje nije navedeno [G1].
   - CESYS WP-101 (Artix-7 GTP, 6,25 Gb/s, HDMI kabel): status „0E0 errors" i oko > 75 %, trajanje nije navedeno [X3].
   - **Broj pokušaja do linka ne objavljuje nitko** (NIJE PRONAĐENO).
4. **Industrijski cilj je BER ≤ 10⁻¹²** (PCIe nakon izjednačavanja [T1], GTP specifikacije [X2], Gowin [G1], CPRI [L1]). Dokaz je test bez grešaka od **N = −ln(1−0,95)/BER ≈ 3,0·10¹² bitova** [K1]: 20 min na 2,5 Gb/s linije, 10 min na 5 Gb/s.
   Naš checker broji 40 od 80 bitova riječi, pa mu na 2,5G treba **40 min** bez greške (s 1 greškom 63 min, s 2 greške 84 min) (§4).
5. **Gdje smo (IZVEDENO iz [L4]):**
   - GS→M2 (2 greške u 2,24·10¹²) ima 95 % gornju granicu 2,8·10⁻¹² (jednostrano). Taj smjer je **na korak od dokaza 10⁻¹²**: isti link, ≈ 84 min ukupno bez novih grešaka.
   - M2→GS (2,2·10⁻¹¹) je **≈ 22× iznad cilja**. Nikakvo trajanje to ne dokazuje, treba bolji link.
   - Naše R1 mjerenje je jedino mjerenje BER-a GateMate SerDesa preko dvije ploče na 2,5G koje sam našla (javnih drugih nema, §1). Usporedivo je po metodi (PRBS + Poisson CI) s onim što objavljuju Xilinx i Keysight.

---

## 1. Pitanje 1: što je Cologne Chip objavio o SerDes linku

### 1.1 Pregled po izvoru

| izvor (datum izdanja) | brzina | kanal | postavke CC_SERDES | BER | eye | trajanje | oznaka |
|---|---|---|---|---|---|---|---|
| **DS1001** datasheet, rujan 2026 (197 str.) [C1] | 0,3–5 Gb/s (tabl. 4.3, str. 155); f_DCO 1250–2500 MHz; **SER_CLK jitter max 1 ps**; VDD_SER 1,00–1,10 V; snaga 2,5G 36–42 mA, 5G 40–48 mA (tabl. 4.4) | — | opis registara (pogl. 2) | **nema** BER specifikacije ni rezultata (pretraga „BER/bit error/eye/1e-12" u svih 197 str.) | opis eye-meas brojača (str. 77, 81), bez rezultata | — | PRONAĐENO (spec.) / NIJE PRONAĐENO (mjerenja) |
| **UG1001** Primitives Library, ožujak 2025 [C2] | — | — | popis parametara CC_SERDES (tabl. 7.12–7.14, str. 122–124) | nema | nema | — | PRONAĐENO (samo parametri) |
| **DS1003** EVB datasheet, siječanj 2024 [C3] | — | SMA J13–J16 (TX/RX P/N) i J11/J12 (LVDS refclk) **nisu montirani u isporuci**, korisnik ih lemi (§3.9, str. 39); opcijski LVDS oscilator (§3.5, str. 32) | — | nema | nema | — | PRONAĐENO (kanal) |
| Stranica eval ploče [C4] | „up to 2x 5 Gbit/s SerDes", SMA | SMA | — | nema | nema | — | NIJE PRONAĐENO |
| Stranica GateMate (popis dokumenata) [C5] | 5 Gbit/s | — | — | „no BER measurements, eye diagrams" | — | — | NIJE PRONAĐENO; app noteova za SerDes nema (UG1002–UG1005 su toolchain, A2 GPIO, ILA, 3,3 V) |
| **Prezentacija „GateMate FPGA High-Speed Transceiver (SerDes)"**, P. Urban, FPGA Conference Europe, 3.7.2025 (21 slajd) [C8] | tablica ADPLL brzina (sl. 11: 0,3–5 Gb/s „In spec", 6–10 Gb/s „Not in spec"); sl. 12 TX driver (125 grana, FFE); sl. 13 RX „3-tap DFE, eye measurement, CDR" | — | — | **nema** | samo shema FFE valnog oblika (DS sl. 2.37), bez mjerenog oka | — | sl. 20 „GateMate SerDes Demo" je **prazan slajd** (demo uživo, rezultati nisu objavljeni). NIJE PRONAĐENO |
| Prezentacija CERN FPGA Developers Forum, rujan 2025 [C9] | „5 Gbit/s SerDes Controller"; EVB „one high-speed SerDes RX, TX + CLK via SMA"; ULX5M-GS s PCIe sučeljem (sl. 14) | — | — | nema | „Eye Scan" samo kao blok | — | NIJE PRONAĐENO |
| Prezentacija GSI seminar, 23.7.2024 [C10] | „31.25 MHz @ 2.5 Gbit/s, 62.50 MHz @ 5.0 Gbit/s" (takt putanje) | — | — | nema | nema | — | NIJE PRONAĐENO |
| **pu-cc/gm_serdes_lb** (Patrick Urban, CC) @56aa48b, 18.9.2026 [C6] | `serdes_lb.v` 2,5G (N 1·5·5, OUT /2); commit ab7ce94 (2.9.2026) „prepare 5G tests": DFE on, AFE PEAK 24 GAIN 0 VCM 3, CDR CKP 0x3E TRANS_TH 8, TX pre/post 5/5, AMP 31 | — | **jedini objavljeni CC skup za 5G** (= naš PROFILE 1) | `tc_prbs`: 10 × 1 s, čita `RX_PRBS_ERR_CNT` (15 b) | `eyetools.py` (analiza), `tc_eyemeas` je prazan stub (već utvrđeno [L2]) | 10 s | PRONAĐENO (alat, postavke) / NIJE PRONAĐENO (rezultat na 5G). README na 56aa48b je prazan (0 redaka) |
| **openCologne `7.SerDes/1.serdestool_by_gm`** README (kopija fbe1966) [C7] | **1,25 Gb/s** (`tc_prbs` u toj verziji) | **EVB, 4 montirana SMA, dva kratka SMA kabela u petlji TX_P→RX_P, TX_N→RX_N** (fotografija `0.doc/SerDes-Loopback.jpg`) | `serdes_lb.v` (fbe1966) = naš PROFILE 0 (PEAK 15, GAIN 8, EN_EQA 0) [L3] | PRBS-7 i PRBS-15: `RX_PRBS_LOCKED 1, ERR_CNT 0`; s ubačenim greškama 6 i 7 | nema | 10 s po uzorku | **PRONAĐENO, jedino hardversko mjerenje proizvođača.** IZVEDENO: 1,25·10¹⁰ bitova, 0 grešaka, BER < 2,4·10⁻¹⁰ (95 %) [§4] |
| colognechip/gatemate-pipe main @63ba8b1, 10.11.2025 i dll_test @5d34d20, 13.10.2026 [C11] | main 2,5G; **dll_test i dalje 300 Mb/s** (r. 112–114 aktivno, 2,5G zakomentirano r. 108–110) | — | potpuni PCIe skup (§2.3) | testbench u simulaciji; „SERDES simulation model … can not be disclosed" | — | — | PRONAĐENO (postavke) / NIJE PRONAĐENO (hardver) |
| prjpeppercorn-test-cases `084-serdes-loopback`, `109-blinky-serdes` [L2 S15] | 300 Mb/s (DCO izvan specifikacije) | — | — | — | — | — | samo build-testovi |
| nextpnr / prjpeppercorn issues (pretraga „serdes") [C12] | — | — | #1476 (početna podrška), #1596 i #13 (CDR parametri, 28.10.2025), #20 (RX redoslijed, 16.6.2026), **#1846 (13.10.2026, otvoren): SERDES konfiguracija se piše u die 0 bez obzira na smještaj, pa A2 drugi SerDes nije konfiguriran** | — | — | — | nijedan issue ne objavljuje BER. IZVEDENO: #1846 ne utječe na A1 (jedan die) |
| Cologne Chip vijesti; FPGA Conference Europe 2026 program (oba dana) [C13][C14] | — | — | — | — | — | — | jedini CC govor 2026 je TDC (M. Gude, 30.6.2026); o SerDesu NIJE PRONAĐENO |
| „Forum Cologne Chip", „FPGA Ignite" [C15] | — | — | — | — | — | — | **NIJE PRONAĐENO**: javni CC forum ne postoji (u tražilici samo EEVblog i blogovi), događaj „FPGA Ignite" uz GateMate ne postoji |

### 1.2 Zaključak

- Proizvođač je javno pokazao **samo dvije stvari**: 1,25 Gb/s PRBS u petlji na istom čipu (10 s, 0 grešaka) i 1000BASE-X (1,25 Gb/s, LiteEth, sl. 17–19 [C8]) bez BER brojke. 2,5G i 5G postoje kao parametri i kao „demo" bez rezultata. **Cross-board link, BER ≤ 10⁻¹², eye i trajanje NISU PRONAĐENI.**
- IZVEDENO: CC test i naš link se razlikuju u tri ključne točke. Kod njih je **isti refclk i isti čip za TX i RX**, kanal su **SMA kabeli od nekoliko cm** i **brzina je 1,25G**. Kod nas su dvije ploče, FFC/konektor i 2,5G. Njihov rezultat zato ne predviđa naš.
- Pitanja koja ostaju za P. Urbana (patrick.urban@colognechip.com [C8] sl. 21) nadovezuju se na Kosjenkin §6 i ne ponavljaju ga:
  (a) postoji li interno BER ≤ 10⁻¹² mjerenje na 2,5 i 5G i s kojim kanalom;
  (b) što je bilo na demu sa sl. 20;
  (c) zašto PIPE radi bez EQA adaptacije (§2.3).

---

## 2. openCologne-PCIE (uputa #351): SerDes model, PHY, postavke, mjerenja

Repo `chili-chips-ba/openCologne-PCIE` @a3cb12f (17.10.2026) [O0]. PHY podmoduli `2.rtl/2.pipe/pipe_src` i `3.mac/mac_src` pokazuju na `colognechip/gatemate-pipe` @5d34d20 (dependabot PR #16, 16.10.2026).

### 2.1 Što je `2.rtl/1.phy/2.serdes-model` [O1]

- Open-source **bihevioralni model** CC_SERDES: isti naziv modula, portovi, imena parametara i **zadane vrijednosti kao vendorski model** (koji je pod NDA i nije u repu). Služi samo za simulaciju; za hardver se instancira `CC_SERDES`.
- Modelirano: regfile (0x00–0x5C), PLL (`f_line = f_ref·N1·N2·N3·2/M3`), 8b/10b, elastični bufferi, bang-bang CDR (`BHV_CDR_KP`, `BHV_CDR_LOCK_EDGES` = 32), poravnanje comma, PRBS7/15/23/31 i reset sekvenceri (PMA/PCS/CDR/EQA/BUF timeri, `RX_WAIT_CDR_LOCK`).
- **Nije modelirano**, doslovno: „driver taps and pre/post emphasis, termination calibration, AFE gain and peaking, DFE adaptation, eye measurement … ADPLL internals … Their status registers report done / locked". Dalje piše: „Signal integrity, jitter tolerance and equalisation are outside the scope … covered by hardware measurements on the GateMate EVK, see `../1.serdes-tests/`".
- Verifikacija samo u simulaciji: „formal 6 proved; equivalence 400 words, 0 divergences; cross-linked 400 words, 0 mismatches; testcase_pipe PASSED, 101 check tasks".
- **IZVEDENO: model nam ne pomaže za analogni problem.** Naš problem (lutrija pri učitavanju, pod BER-a, 5G CDR) je upravo u dijelovima koje model proglašava „done/locked".

### 2.2 `1.serdes-tests` i ostatak repoa: je li išta mjereno na pločici

| stavka | sadržaj | mjerenje na hardveru |
|---|---|---|
| `1.serdes-tests/README.md` [O3] | „Mujo Sejdic and @KemalLikic workspace, **to fill with details, explanations, diagrams and oscillograms**." | **NIJE PRONAĐENO** (prazan predložak) |
| `PRBS-Loopback-Test-for-GateMate-EVK/serdes_top.v` [O2] | EVK, 10 MHz takt. FSM upisuje u regfile `0x51=0x16FA` (2,5G), `0x5C=0x0001`, `0x50=0x0C03`. Hard PRBS-7 TX i RX, 8b10b isključen, comma detect isključen, `LOOPBACK_I=000` (vanjska petlja), **analogni parametri nisu postavljeni (zadani)**. Status: LED `loopback_ok` nakon 65 535 uzastopnih taktova bez `RX_PRBS_ERR_O`. **Automatski oporavak:** nakon ≈ 2²⁵ taktova neprekidne greške (komentar: „~300 ms") diže `RX_RESET_I` i `RX_CDR_RESET_I` i resetira PRBS brojač | **NIJE PRONAĐENO**: nema brojača grešaka, BER-a ni zapisa rezultata. U repou je samo kod i PDF „Reviewed-By-Claude-Code". (Naša ranija bilješka [L2 S7] da se ne prevodi zbog `TX_PAT` vrijedi i dalje: `TX_PAT` je zakomentiran u r. 91, a koristi se u r. 138) |
| `2.rtl/1.phy/README.md` [O4] | linkovi na gatemate-pipe, DS1001, Mithro slajdove, Yumewatari; „DLL TestBench" (pcieVHost); tablica sim rezultata | samo simulacija |
| README glavni, stanje [O0] | „Develop opensource PHY with PIPE interface: [x] ✔ x1, Gen1; [ ] Gen2 (best-effort)". „Debug and bringup": neoznačeno. „Implement it all in GateMate, PNR and timing closure": neoznačeno. M.2 RevA ✔ (PCB) | IZVEDENO: ✔ Gen1 znači PIPE RTL i simulaciju. Bringup na hardveru je otvoren |
| Issues (16, stanje 17.10.2026) [O5] | #5 otvoren (4.9.2026): behavioral model; #8 otvoren (13.10.2026): „64-bit PIPE: PCLK is half the SerDes word rate"; #9–#14 MAC/DLL/sim | **nijedan issue ne izvještava o hardverskom linku ni BER-u** |
| LinkedIn chili-chips 17.10.2026 (poveznica iz README-a) [O6] | WaveCrux dekoderi za PCIe | nema hardverskog rezultata |

### 2.3 CC_SERDES postavke za PCIe Gen1 2,5G: Cologne Chip naspram nas

Izvori: `gatemate-pipe` main @63ba8b1 `src/ccfpga_pipe_wrapper.v` [C11]. Dll_test @5d34d20 ima **iste analogne vrijednosti**, razlikuje se samo brzina (r. 4–5 diff, 300 Mb/s). Naši: `gateware/ber/ber_top.v` r. 60–79 (PROFILE 1 + `OV_TX_AMP 12` + R1) [L5], Kosjenka [L6] §1.4/O3.

| polje | CC PIPE (Gen1 2,5G) [C11] r. | EVK `serdes_top.v` [O2] | zadano CC_SERDES (model = vendor) [O1] | **naš 2,5G** (PROFILE 1, AMP 12, R1) |
|---|---|---|---|---|
| brzina | MAIN_DIVSEL 0x1B (1·5·5), OUT 01 (2,5G), r. 108–110 | 0x51=0x16FA (2,5G) | — | 1·5·5, OUT 2 (2,5G) |
| **RX_EN_EQA** (DFE/EQA adaptacija) | **0** (r. 141) | zadano (0) | 0 | **1** |
| RX_EQA_LOCK_CFG | 0 (r. 142) | — | 0 | 0xC |
| RX_EQA_CKP_LF / HF / OFFSET | 0xA3 / 0xA3 / **0x01** (r. 137–140) | — | 0xA3 / 0xA3 / 0x01 | 0xA3 / 0xA3 / **0x01** (R1 je tražio 0, ne upiše se [L4b]) |
| RX_EQA_CONFIG | 0x01C0 (r. 139) | — | — | zadano |
| **RX_AFE_PEAK** (CTLE; 0 = max) | **15** (r. 149, „old: 16") | 16 | 16 | **24** |
| **RX_AFE_GAIN** | **8** (r. 148) | 8 | 8 | **0** |
| RX_AFE_VCMSEL / RTERM_VCMSEL | 4 / 4 | 4 / 4 | 4 | 3 / 3 |
| **RX_CDR_CKP** | **0xF8** (r. 150, „old: 101_01111") | 0xAF | 0xAF | **0x3E** |
| RX_CDR_CKI | 0 | 0 | 0 | 0 |
| RX_CDR_TRANS_TH | 8 (r. 248, komentar „h15? // ?") | — | — | 8 |
| RX_CDR_LOCK_CFG | 0xD5 | — | — | 0xD5 |
| RX_CALIB_EN / OVR / VAL | 1 / 0 / 0 (r. 227–229: auto) | — | — | **OVR 1, VAL 0 (CAL0, R1)** |
| **TX_CALIB_EN** | **0** (r. 345) | — | — | **1** |
| **TX_AMP** | **30** (r. 172) | 15 | 15 | **12** |
| TX_SEL_PRE / SEL_POST | **0 / 0** (r. 309–310), BRANCH_EN_PRE/POST 0xF | 0 / 0 | 0 / 0 | PRE **0** (R1) / POST **5**, BRANCH 12/12 |
| RX_WAIT_CDR_LOCK | **0** (r. 127) | — | — | 0 (Kosjenka O3: DS zadano je 1) |
| RX_RESET_TIMER_PRESC; *_RESET_TIME | 0; 3 (r. 129–134) | — | — | 4; 3 |
| PLL_FAST_LOCK / LOCK_WINDOW | 1 / 1 (r. 187–188) | — | — | — |
| reset portovi iz fabrica | samo `PLL_RESET = s_reset`; **TX/RX, PMA, PCS, CDR i EQA reset vezani na 0** (`ccfpga_pipe_logic.v` r. 204–212, 247); `s_reset_done` gleda samo TX (r. 355, 401) | `RX_RESET_I` + `RX_CDR_RESET_I` na auto-oporavak | — | TX/RX/PLL reset = `rst`; PMA/EQA/CDR/PCS = 0 (`ber_top.v` r. 112–113); EQA reset preko JTAG 0x2B |
| mjerenje na pločici | **NIJE PRONAĐENO** | **NIJE PRONAĐENO** | — | soak 1800 s [L4] |

### 2.4 Razlikuje li se redoslijed kalibracije i reseta od našeg

- **CC PIPE:** jedan globalni reset → ADPLL. Zatim interni sekvenceri (timeri 3, PRESC 0, bez čekanja CDR locka). **Nema DFE/EQA adaptacije** (EN_EQA 0) **ni TX kalibracije** (TX_CALIB_EN 0), RX terminacija je na auto kalibraciji. Ponovni pokušaj ne postoji. U PCIe-u ga daje LTSSM (Detect/Polling ponavlja), koji je u MAC sloju [C11].
- **EVK test openCologne-PCIE:** isto, plus **automatski RX + CDR reset nakon neprekidnih grešaka**. To je jedini objavljeni „retry" mehanizam za GateMate [O2]. IZVEDENO: odgovara našoj ljestvici vrata (L1/L3) i Kosjenkinoj O12 (fabric reset portovi + watchdog). Potvrđuje da je i drugima jednostavni RX/CDR reset prvi lijek.
- **Mi:** EQA adaptacija **uključena**, TX kalibracija uključena, CAL0 forsiran, nakon učitavanja ljestvica vrata. Razlika je stvarna: **CC svoj PCIe recept vozi sa statičkim RX-om.** Nama EQA reset unutar učitavanja „ponovno baca kocku" [L6 §1.2]. IZVEDENO: to je u skladu s hipotezom da je dio naše lutrije u samoj adaptaciji.

### 2.5 Pomaže li nam (IZVEDENO; predano Kosjenki, ne dupliciram njezin plan)

1. **Statički RX po CC receptu je već jednom probao naš kanal, ali nečisto.** PROFILE 0 (PEAK 15, GAIN 8, EN_EQA 0, CKP 0xF8, AMP 15, TX_CALIB 0) je na 2,5G 26.09. dao 5,9·10⁻⁴ / 2,1·10⁻⁴ [L3 RATES §1]. To je bilo **prije TX_NEG popravka** fabric↔SerDes vremena (nextpnr ne mjeri te putove [L2 S21]), pa je rezultat pomiješan s tim kvarom.
   Prijedlog za Kosjenkin F3: krak **„B-static" = trenutni bit (TX_NEG 1, AMP 12) + `RX_EN_EQA=0`, `RX_AFE_PEAK 15`, `RX_AFE_GAIN 8`**. To je CC PIPE RX set na našem TX-u. Mjeri se udio prolaza iz 1. pokušaja (20 učitavanja). To je ujedno K7/O14 („Static_DFE") s vrijednostima koje proizvođač koristi.
   **Rizik:** na 5G CDR se zaključava samo s DFE-om [L3 TUNING_5G], pa ovo vrijedi samo za 2,5G.
2. `RX_EQA_CKP_OFFSET`: CC drži **0x01** (kao mi). Nitko upstream ne koristi 0. Kosjenkin zaključak „ne pisati 0" (O11) se potvrđuje.
3. `RX_WAIT_CDR_LOCK = 0` kod CC-a i kod nas. Kosjenkina O3 (=1) je dakle odstupanje od CC prakse, ne povratak na nju. Ostaje hipoteza, CC je nije testirao javno.
4. `TX_AMP 30` kod CC-a je za PCIe kanal s kondenzatorima i konektorom slota. Za naš kratki kanal nije dokaz (naš optimum je 12–24 [L3]).
5. **Model ne pomaže** (§2.1). Ono što pomaže su **postavke i struktura reseta**. Mjerenja ne postoje.

---

## 3. Pitanje 2: objavljena mjerenja drugih FPGA SerDesa

| čip (izvor, datum) | brzina | kanal | postavke | BER / kriterij | trajanje / bitovi | broj pokušaja do linka | oznaka |
|---|---|---|---|---|---|---|---|
| **Xilinx Artix-7 GTP**, WP428 v1.0.1, 7.12.2017 [X1] | 6,25 Gb/s | AC722 karakterizacijska ploča + **30" FR4 (≈ 12 dB na 3,125 GHz)** | TX swing 850 mV, **TX emfaza OFF**, RX EQ auto-adaptacija, PRBS31 | eye scan do **10⁻⁸**: oko ~200 mV, 0,56 UI; ekstrapolacija na **10⁻¹⁵** (≥ 95 kodova, 0,51 UI); maska 50 kodova / 0,35 UI → margina 90 % / 45,7 % | WP428: „at 6 Gb/s it takes about 3 minutes to reach raw BER of 10⁻¹², 2,780 minutes for 10⁻¹⁵, 193 days for 10⁻¹⁷" (= 1/BER bitova, **bez faktora 3 za 95 %**, IZVEDENO §4) | nije navedeno | PRONAĐENO |
| Xilinx Artix-7 GTP, DS181 v1.25, 18.6.2018 [X2] | 0,5–6,6 Gb/s | — | — | TX TJ 0,20 UI na 2,5G, 0,30 UI na 5G; RX SJ tolerancija 0,5 UI (2,5G), 0,44 UI (5G); **„All jitter values are based on a bit-error ratio of 1e-12"** (str. 53–54) | — | — | PRONAĐENO (spec.) |
| Artix-7 GTP (CESYS EFM-03), WP-101 v1.0, siječanj 2018 [X3] | 6,25 Gb/s | **HDMI kabel** u fizičkoj petlji, breakout ploča, 125 MHz refclk iz LMK61PDEVM preko SMA | IBERT zadano, **Slow-clock uzorak** (ne PRBS) | „Errors 0E0", eye scan oko > 75 % | **nije navedeno** | nije navedeno | PRONAĐENO (slabo: nije PRBS) |
| **Gowin GW5AT**, WP1157-1.0E, 1.8.2025 [G1] | do 12 Gb/s (ISI FR4 0,3 m), 9G (0,635 m), DP 2 m 11G, HDMI 2 m 10G, HSD 3 m 8G / 8 m 6G, fiber 10 m 12G | EVAL_GW5AT_60KUG225_V1 + kabeli; IL: PKG+PCB 2 dB po strani, kabel A/C 0,5 dB | **BER cilj 1e-12, PRBS15, TX de-emfaza −1,94 do −6 dB, RX EQ AUTO** | kriterij granice: „**total collapse of the eye diagram**" (interno oko); Keysight UXR0254A, E5071C | **nije navedeno** (bez broja bitova) | nije navedeno | PRONAĐENO (cilj, kanali) / NIJE PRONAĐENO (dokaz 1e-12) |
| **Lattice ECP5 / ECP5-5G**, DS FPGA-DS-02012-3.3 [L1] | 5G (PCIe-like tabl.), CPRI E.48 (4,9 Gb/s) | — | „Full Rx Equalization enabled" za toleranciju jittera | specifikacija: RX TJ tolerancija 0,6–0,65 UI, oko 0,35 UI; „Data is measured with PRBS7, not PRBS-31"; 5G tablica: „Not in compliance with PCI Express standard" | — | — | PRONAĐENO (spec.) |
| Lattice ECP5, TN-02206 v1.7 [L1b] | — | — | PRBS checker `prbs_error_cnt[7:0]` | CPRI: „BER requirement of 1×10⁻¹²" (str. 45) | — | — | PRONAĐENO (zahtjev) |
| Lattice ECP5 SERDES Eye Demo UG93 v1.3 (siječanj 2017) i UG111 (5G) [L1c] | 3,125 Gb/s (UG93); 5G (UG111) | Versa ploča, SMA, **vanjski DCA/DSO** | PRBS ili brojač | samo oko na instrumentu | — | — | URL Lattice vraća HTML (blokirano 17.10.); sadržaj iz sažetka tražilice. **BER broj NIJE PRONAĐEN** |
| **Lattice CertusPro-NX**, SerDes/PCS UG FPGA-TN-02245-1.4 [L7] | do 10,3 Gb/s | — | PRBS7/11/23/31 (reg64), eye monitor → BER mapa (sl. 9.9, str. 100–101); CTLE bez adaptacije na minimum (str. 88–92, već u [L2b]) | alat, ne rezultat | — | — | NIJE PRONAĐENO (mjerenja) |
| **Efinix Titanium Ti375**, Transceiver Debugger tutorial v1.0, srpanj 2025 [E1] | do 12,5 Gb/s PMA Direct, PCIe Gen4 | Ti375 N1156 dev kit, opcijski SFP+ loopback modul | BIST, inject error, eye: horizontalni korak 1/64 UI, vertikalni ≈ 3 mV, BER piksela = greške/(uzorci·accum) | alat, primjer slike; **nema BER broja** | — | — | NIJE PRONAĐENO (mjerenja) |
| **Intel Cyclone 10 GX**, XCVR Toolkit Reference Design UG v17.1.1 [I1] | (dev kit) | interna serijska petlja ili **FMC loopback kartica** | PRBS7/15/23/31 | kriterij prolaza: „**CDR locked and BER result is zero**"; pad = „CDR loose lock and BER increment" | **nije navedeno** | nije navedeno | URL je 17.10.2026. 404 (Intel redirect); sadržaj iz sažetka tražilice. Djelomično |
| open-source ECP5 (LiteICLink bench, ECP5-PCIe, litex-acorn #4) [L8] | 1,25–5G (bench skripte) | Versa/Acorn | — | LiteICLink README: ECP5 i Artix-7 GTP „support"; acorn #4 (2021) „Validate Acorn <> ECP5 link" **otvoren bez rezultata**; ECP5-PCIe pokazuje vrijeme u L0 (slika), bez BER-a | — | — | NIJE PRONAĐENO |

**Zaključak §3 (IZVEDENO):**

- **Nijedan proizvođač iz istog razreda ne objavljuje „BER ≤ 10⁻¹² dokazan s N bitova" za konkretan link.** Objavljuju specifikaciju (jitter „pri 10⁻¹²"), alat ili kriterij („0 errors", „oko > 75 %", „kolaps oka").
- Metodološki najjači je Xilinx WP428. Njegov postupak:
  1. eye scan na 10⁻⁸ za svaku postavku;
  2. izbor najbolje postavke po margini;
  3. ekstrapolacija na niski BER;
  4. **jedan dugi BER test** s odabranom postavkom.
  To je točno redoslijed koji Kosjenkin F4 („margina amplitude") nadomješta dok nam eye brojači ne rade.
- **Broj pokušaja do linka ne objavljuje nitko.** U praksi to rješavaju protokol (PCIe LTSSM ponavlja Detect/Polling/Recovery [T1]) ili automatski reset (openCologne-PCIE [O2]). Naš podatak „vrata 2,5G 5/15" [L4b] **nema javnu usporednicu**. Nije ga moguće rangirati prema drugima, samo prema vlastitom cilju.

---

## 4. Pitanje 3: industrijski cilj i dokaz

### 4.1 Cilj

- **BER ≤ 10⁻¹²** je de facto standard:
  - PCIe nakon izjednačavanja: „link should have BER less than 10⁻¹²"; faza 1 traži < 10⁻⁴ [T1];
  - Xilinx GTP specifikacije [X2] i WP428 („usually 10⁻¹² or below") [X1];
  - Gowin [G1];
  - CPRI [L1b].
- Stroži ciljevi postoje: WP428 simulira 10⁻¹⁵; Xilinx za produkciju navodi 10⁻¹⁶ [X4].

### 4.2 Dokaz: koliko bitova i koliko vremena

- Formula (Keysight [K1]; Poisson, jednostrano): **N = χ²(CL; 2(k+1)) / (2·BER)**. Za k = 0 to je N = −ln(1−CL)/BER.
- Keysight: „95 % confidence with target BER 1E-6 requires 3 million bits". Dakle za 10⁻¹² treba **3·10¹² bitova bez greške**.
- Izračun: `docs/data_20261017/t5554/ber_cl.py` → `ber_cl.out`.

| cilj | CL | dopušteno grešaka k | potrebno bitova N | 2,5 Gb/s linije | **naš checker na 2,5G (1,25·10⁹ b/s)** | 5 Gb/s linije | naš checker na 5G (2,5·10⁹ b/s) |
|---|---|---|---|---|---|---|---|
| 10⁻¹² | 95 % | 0 | 3,00·10¹² | 20,0 min | **40 min** | 10,0 min | 20 min |
| 10⁻¹² | 95 % | 1 | 4,74·10¹² | 31,6 min | **63 min** | 15,8 min | 32 min |
| 10⁻¹² | 95 % | 2 | 6,30·10¹² | 42,0 min | **84 min** | 21,0 min | 42 min |
| 10⁻¹² | 99 % | 0 | 4,61·10¹² | 30,7 min | 61 min | 15,4 min | 31 min |
| 10⁻¹⁵ | 95 % | 0 | 3,00·10¹⁵ | 13,9 dana | 27,7 dana | 6,9 dana | 13,9 dana |

Napomene:

- Naš checker na 2,5G broji 40 bitova po riječi (31,25 M riječi/s), tj. 1,25·10⁹ provjerenih bitova/s. Soak: 2,239·10¹² bitova u 1791 s [L4]. Zato trajanje treba računati iz **provjerenih**, a ne linijskih bitova.
  IZVEDENO: preostalih 40 bitova riječi (K28.5 + ID) također prolazi kanal. Greška u njima bi se vidjela kao loša riječ ili gubitak sinkronizacije, ali ne ulazi u N.
- WP428-ova rečenica „3 minutes to 10⁻¹² at 6 Gb/s" odgovara 1,08·10¹² bitova, tj. **≈ 1/BER (63 % CL)**. Za 95 % treba 8,3 min. Kad netko kaže „izmjerili smo 10⁻¹²", treba pitati koliko je bitova bilo.
- CC `tc_prbs` (10 s, 1,25G, 0 grešaka) = 1,25·10¹⁰ bitova → **BER < 2,4·10⁻¹⁰ (95 %)**. Dakle 250× slabije od cilja 10⁻¹².

### 4.3 Naše stanje prema cilju (za kontekst, bez novog mjerenja)

| smjer (soak R1, 1800 s [L4]) | k | N | BER | 95 % jednostrano gore | 95 % dvostrano (kao u SOAK) | prema 10⁻¹² @ 95 % |
|---|---|---|---|---|---|---|
| GS→M2 | 2 | 2,239·10¹² | 8,9·10⁻¹³ | 2,8·10⁻¹² | [1,08·10⁻¹³, 3,23·10⁻¹²] | **još nije dokazano.** Uz k = 2 treba N = 6,30·10¹² (≈ 84 min ukupno, ≈ 54 min više od danas) bez nove greške |
| M2→GS | 50 | 2,239·10¹² | 2,2·10⁻¹¹ | 2,8·10⁻¹¹ | [1,66·10⁻¹¹, 2,94·10⁻¹¹] | **ne može se dokazati trajanjem**: stvarni BER je ≈ 22× iznad cilja, treba bolji link (Kosjenka O5–O8) |

Unakrsna provjera: `ber_cl.py` daje točno CI iz `SOAK_R1_2G5_20261017.md` za oba smjera, pa je statistika u oba dokumenta ista.

Prijedlog kriterija „2,5G radi bez greške" (IZVEDENO, odluka je Goranova): **≥ 3,0·10¹² provjerenih bitova po smjeru s 0 grešaka**, 40 min na 2,5G, oba smjera istodobno, 0 gubitaka sinkronizacije. To daje BER < 10⁻¹² uz 95 %, po istoj formuli koju koriste Keysight i PCIe praksa. Uz to treba bilježiti **udio prolaza iz 1. pokušaja**, jer za njega javne usporednice nema (§3).

---

## 5. Predaja Kosjenki (TASK-5553) i što ne dupliciram

Kosjenkin `CALIBRATION_OPTIONS_20261017.md` (16a5137) već ima opcije O1–O14 i plan F0–F5. Ovaj dokument joj predaje **samo izvore i tri konkretne točke**:

1. [C11] r. 127–188, 227–229, 309–310, 345 i [O2] kao **CC referentni PCIe set**: EN_EQA 0, PEAK 15, GAIN 8, CKP 0xF8, AMP 30, bez FFE, TX_CALIB 0, WAIT_CDR_LOCK 0. Prijedlog kraka „B-static" za F3 (§2.5 t. 1).
2. [O2] auto RX+CDR reset kao javni primjer za O12 (fabric reset + watchdog).
3. [X1] WP428 postupak (margina na 10⁻⁸ → jedan dugi test) kao vanjsku potvrdu njezinog F4, i §4.2 tablicu trajanja za F5/soak kriterij.

---

## 6. Nesigurnosti

- Lattice UG93/UG111/TN1261/UG98 i Intel C10GX RD vodič nisu se dali preuzeti 17.10.2026. (Lattice vraća HTML, Intel 404). Za njih se oslanjam na sažetke tražilice: naslovi, 3,125 Gb/s, kriterij „CDR locked + BER zero". Moguće je da sadrže tablicu s trajanjem koju nisam vidjela.
- Interni dokumenti proizvođača (Xilinx karakterizacijski izvještaji, CC NDA SerDes model, CC interna mjerenja) **nisu javni**. „NIJE PRONAĐENO" znači da nije javno objavljeno, ne da ne postoji.
- Jedini hardverski rezultat CC-a je iz kopije README-a u openCologne (fbe1966, 2025-10-23 upstream). Upstream README na 56aa48b je prazan, pa se ne vidi je li isti test ponovljen na 2,5G nakon ab7ce94.
- Usporedba §2.3 za „naš 2,5G" uzima vrijednosti iz `ber_top.v` i Kosjenkinog §1.4. Što je stvarno u silikonu nakon JTAG upisa ovisi o readbacku (Kosjenka O1).
- „Gen1 ✔" u openCologne-PCIE tumačim kao RTL i simulaciju (IZVEDENO iz praznog `1.serdes-tests` i neoznačenog „Debug and bringup"). Autori to nisu izričito napisali.

---

## 7. Izvori (svi pregledani 17.10.2026.)

**Cologne Chip / GateMate**

- [C1] DS1001 GateMate Datasheet, **rujan 2026** (PDF modDate 2026-09-11), str. 50–98, 155: https://colognechip.com/docs/ds1001-gatemate1-datasheet-latest.pdf ; izvadak `data_20261017/t5554/DS1001_2026-09_p155_serdes_table.txt`
- [C2] UG1001 Primitives Library, **ožujak 2025**, str. 117–124: https://www.colognechip.com/docs/ug1001-gatemate1-primitives-library-latest.pdf
- [C3] DS1003 Evaluation Board Datasheet, **siječanj 2024**, str. 32, 39: https://colognechip.com/docs/ds1003-gatemate1-evalboard-latest.pdf
- [C4] Stranica eval ploče: https://colognechip.com/programmable-logic/gatemate-evaluation-board/
- [C5] Stranica GateMate (popis dokumenata, UG1002–UG1005, product brief 27.3.2025): https://colognechip.com/programmable-logic/gatemate/
- [C6] pu-cc/gm_serdes_lb @56aa48b (18.9.2026), commit ab7ce94 (2.9.2026): https://github.com/pu-cc/gm_serdes_lb/tree/56aa48ba9f9f7dbf7ea8e0664ea8a8bdf247e0df ; https://github.com/pu-cc/gm_serdes_lb/commit/ab7ce94
- [C7] openCologne `7.SerDes/1.serdestool_by_gm` README (log PRBS-7/15) i fotografija petlje: https://github.com/chili-chips-ba/openCologne/tree/27eb53ae74cbec76a8066ff108776bce127523bf/7.SerDes/1.serdestool_by_gm ; https://raw.githubusercontent.com/chili-chips-ba/openCologne/27eb53a/7.SerDes/0.doc/SerDes-Loopback.jpg
- [C8] P. Urban, „GateMate FPGA High-Speed Transceiver (SerDes)", **3.7.2025** (FPGA Conference Europe): https://www.colognechip.com/docs/presentations/gatemate-serdes-fpgaconf2025.pdf ; tekst `data_20261017/t5554/cc_serdes_fpgaconf2025_text.txt`
- [C9] „GateMate FPGA, A European 28nm FPGA…", CERN FPGA Developers Forum, **rujan 2025**: https://indico.cern.ch/event/1587509/contributions/6690211/attachments/3140818/5574499/gatemate-fdf2025.pdf
- [C10] „GateMate FPGA Overview", GSI seminar, **23.7.2024**: https://indico.gsi.de/event/20202/attachments/47959/69739/gatemate-gsi-seminar_2024_07.pdf
- [C11] colognechip/gatemate-pipe main @63ba8b1 (**10.11.2025**) `src/ccfpga_pipe_wrapper.v`, `src/ccfpga_pipe_logic.v`; dll_test @5d34d20 (**13.10.2026**): https://github.com/colognechip/gatemate-pipe/tree/63ba8b197a97ac8360945f7db0f00469baa7e5db ; https://github.com/colognechip/gatemate-pipe/tree/5d34d20ee1317bb609b9072113caca28c517a07a ; izvadak `data_20261017/t5554/gatemate-pipe_63ba8b1_wrapper_params.txt`, `…_pipe_logic_resets.txt`
- [C12] nextpnr PR #1846 (13.10.2026): https://github.com/YosysHQ/nextpnr/pull/1846 ; #1596: https://github.com/YosysHQ/nextpnr/pull/1596 ; prjpeppercorn #20: https://github.com/YosysHQ/prjpeppercorn/pull/20 ; #13: https://github.com/YosysHQ/prjpeppercorn/pull/13
- [C13] Cologne Chip vijesti: https://www.colognechip.com/about-the-company/news/
- [C14] FPGA Conference Europe 2026, program: https://www.fpga-conference.eu/program-2026-day-one ; https://www.fpga-conference.eu/program-2026-day-two
- [C15] awesome-gatemate (popis zajednice): https://github.com/PythonLinks/awesome-gatemate

**openCologne-PCIE (uputa #351)**

- [O0] chili-chips-ba/openCologne-PCIE @a3cb12f (**17.10.2026**) README: https://github.com/chili-chips-ba/openCologne-PCIE/tree/a3cb12f
- [O1] `2.rtl/1.phy/2.serdes-model/README.md`, `ccfpga_serdes.v`, `0.doc/equivalence-checking.md`: https://github.com/chili-chips-ba/openCologne-PCIE/tree/main/2.rtl/1.phy/2.serdes-model ; kopija `data_20261017/t5554/openCologne-PCIE_a3cb12f_serdes-model_README.md`
- [O2] `2.rtl/1.phy/1.serdes-tests/PRBS-Loopback-Test-for-GateMate-EVK/serdes_top.v`: https://github.com/chili-chips-ba/openCologne-PCIE/tree/main/2.rtl/1.phy/1.serdes-tests ; kopija `data_20261017/t5554/openCologne-PCIE_a3cb12f_serdes_top.v`
- [O3] `2.rtl/1.phy/1.serdes-tests/README.md` (isti URL kao [O2])
- [O4] `2.rtl/1.phy/README.md`: https://github.com/chili-chips-ba/openCologne-PCIE/tree/main/2.rtl/1.phy
- [O5] Issues: https://github.com/chili-chips-ba/openCologne-PCIE/issues?q=is%3Aissue (#5, #8 otvoreni)
- [O6] chili-chips LinkedIn 17.10.2026: https://www.linkedin.com/posts/chili-chips_having-too-much-fun-cracking-ones-and-zeros-activity-7517129808020074496-Rmev

**Drugi proizvođači i statistika**

- [X1] Xilinx WP428 v1.0.1, **7.12.2017**, H. Fu, R. Mayder, str. 2–10: https://docs.amd.com/api/khub/documents/iJbdiZXYuXW71XvJ4yKG8A/content
- [X2] Xilinx DS181 Artix-7 Data Sheet v1.25, **18.6.2018**, str. 53–54: https://0x04.net/~mwk/xidocs/ds/ds181_Artix_7_Data_Sheet.pdf
- [X3] CESYS WP-101 v1.0, **siječanj 2018**: https://www.cesys.com/fileadmin/user_upload/service/FPGA/fpga%20boards%20&%20modules/EFM-03/wp-101-EFM-03_-_Bit_Error_Rate_Tests_for_GTP.pdf
- [X4] AMD Adaptive Support, „How to use PRBS checker for link testing (Virtex 5 GTP)" (produkcijski cilj 1e-16, iz sažetka tražilice): https://adaptivesupport.amd.com/s/question/0D52E00006hpT8WSAU/how-to-use-prbs-checker-for-link-testing-virtex-5-gtp?language=en_US
- [G1] Gowin WP1157-1.0E, „Evaluating GW5AT SerDes Channel Performance Across Various Transmission Media", **1.8.2025**, str. 5, 10, 14, 21: https://www.gowinsemi.com/upload/database_doc/3235/document/688c0e65443ac.pdf
- [L1] Lattice ECP5/ECP5-5G Family Data Sheet FPGA-DS-02012-3.3, str. 80–83: https://0x04.net/~mwk/doc/lattice/ecp5/FPGA-DS-02012-3-3-ECP5-ECP5G-Family-Data-Sheet.pdf
- [L1b] Lattice FPGA-TN-02206-1.7 ECP5 SerDes/PCS UG, str. 45, 95, 106: https://0x04.net/~mwk/doc/lattice/ecp5/FPGA-TN-02206-1-7-ECP5-and-ECP5-5G-SerDes-PCS-User-Guide.pdf
- [L1c] Lattice UG93 v1.3 (siječanj 2017) SERDES Eye Demo: https://www.latticesemi.com/-/media/LatticeSemi/Documents/UserManuals/RZ/SERDESEyeDemoECP5VersaDevKitUG93.ashx?document_id=50998 (preuzimanje blokirano 17.10.2026.)
- [L7] Lattice FPGA-TN-02245-1.4 CertusPro-NX SerDes/PCS UG, str. 43, 60, 88–101, 127: https://www.frontgrade.com/sites/default/files/documents/fpga-tn-02245-1_4-certuspro-nx-serdes-pcs-user-guide.pdf
- [L8] LiteICLink: https://github.com/enjoy-digital/liteiclink ; litex-acorn-baseboard #4 (11.10.2021): https://github.com/enjoy-digital/litex-acorn-baseboard/issues/4 ; ECP5-PCIe (zadnji commit 16.5.2023): https://github.com/ECP5-PCIe/ECP5-PCIe
- [E1] Efinix Efinity Transceiver Debugger Tutorial v1.0, **srpanj 2025**: https://www.efinixinc.com/docs/efinity-transceiver-debugger-tutorial-v1.0.pdf
- [I1] Intel Cyclone 10 GX XCVR Toolkit Reference Design v17.1.1 UG (17.10.2026. vraća 404): https://www.intel.com/content/dam/support/us/en/programmable/support-resources/fpga-wiki/asset03/cyclone-10-gx-xcvr-toolkit-reference-design-user-guide.pdf ; stranica primjera: https://www.intel.com/content/www/us/en/design-example/715173/intel-cyclone-10-gx-fpga-transceiver-toolkit-reference-design.html
- [T1] TI SNLA415 „PCIe Link Training Overview", **kolovoz 2022**, str. 8–9: https://www.ti.com/lit/pdf/snla415
- [K1] Keysight 5992-2676 „BER Measurement" (PDF 19.3.2021), str. 14, 24–26: https://keysight.zinfi.net/concierge/OEMs/keysight/wwwcontent/Attachments/pdf/5992-2676.pdf ; Keysight KB (formula, 17.10. vraća 403): https://docs.keysight.com/kkbopen/how-do-i-measure-the-bit-error-rate-ber-to-a-given-confidence-level-on-the-j-bert-m8020a-and-the-m8040a-high-performance-bert-588276182.html

**Naši dokumenti**

- [L2] `SOURCES_20260926.md` (S3, S7, S8, S15, S21); [L2b] `SERDES_UMJERAVANJE_KAKO_DRUGI_20261015.md`
- [L3] `VERIFY_20260926_RATES.md` §1 (PROFILE 0 na 2,5G: 5,9·10⁻⁴ / 2,1·10⁻⁴), `TUNING_5G.md` (RX_EN_EQA, TX_AMP)
- [L4] `SOAK_R1_2G5_20261017.md`; [L4b] `CHAIN4_5G_P2_20261017.md` §2, §4
- [L5] `gateware/ber/ber_top.v` r. 18–79, 112–113
- [L6] `CALIBRATION_OPTIONS_20261017.md` (Kosjenka, TASK-5553)

## 8. Ponovljivost

```sh
cd ulx5m-gs-m2-serdes/docs/data_20261017/t5554
python3 ber_cl.py | diff - ber_cl.out          # tablica §4.2 i CI §4.3 (bez scipy)
sha256sum -c <(sed 's#  #  /put/do/preuzetih/#' source_pdfs.sha256)   # hashevi 18 preuzetih PDF-ova (17.10.2026.)
```
