# Eye scan na GateMate SerDesu — kako se pokreću brojači RX_EYE_MEAS i zamjenski „bathtub”

TASK-5486 (Manda, 12.10.2026.). Ovo je samo istraživanje, bez hardvera; ploče u isto vrijeme koristi Jelena (TASK-5483).
Ulaz: `VERIFY_20260926_RATES.md` §5 i §9.6, `TUNING_5G.md` §5.1/E7, `SOURCES_20260926.md`, `SERDES_KNOWLEDGE.md` §7.

Oznake: **[DS]** DS1001 iz rujna 2026. (`regoc_system/docs/ulx5m-serdes/sources_20260926/DS1001_GateMate1_datasheet_2026-09.pdf`),
**[UG]** UG1001 iz ožujka 2025., **[PU]** pu-cc/gm_serdes_lb @56aa48b (Patrick Urban, Cologne Chip) s git poviješću,
**[PP]** YosysHQ/prjpeppercorn @b1eb52f, **[SIM]** `tb_ccfpga_serdes.v` (Cologne Chipov SerDes testbench u
chili-chips openCologne-PCIE `5.sim/` i pu-cc gatemate-pipe `sim/`), **[NAŠE]** ovaj repo i mjerenja.
**VERIFICIRANO** znači pročitano u izvoru, a **HIPOTEZA** znači da nije izmjereno.

---

## 0. Ukratko

1. **Nijedan javni izvor ne objašnjava kako se brojači pokreću.** DS daje samo imena i širine polja, a upstream `tc_eyemeas`
   je i danas prazan: `main` je @56aa48b (18.09.2026.), provjereno 12.10. preko `git ls-remote` i GitHub API-ja. Za
   „RX_EYE_MEAS”, „gatemate eye scan” i „cc_serdes eye” GitHub pretraga issuea daje 0 rezultata.
2. **Cologne Chip ipak ima akviziciju koja radi.** `eyetools.py` [PU 83d7858] crta stvarne podatke: oko, krivulje „bathtub”
   i CDF po uzorku bita. Klasa `EyeData` uz brojače vodi i **`prbs_err_cnt`**. Potpis
   `tc_eyemeas(window=512, repeats=1, monitor=2, sel_tap=0, phase_step=1, tapw_sweep=False, setup=True)` [PU 2043840]
   ima korak `setup` i parametre `monitor` i `sel_tap`, koje naš `eyescan.py` nigdje ne postavlja.
3. **Naše dvije opservacije su međusobno konzistentne i ne znače „brojači ne rade”.** Moguće je i da se mjerenje
   nikad ne pokrene ili nikad ne završi:
   - u lab4 (`data_20260926/t5066/lab4.out` r. 32) bit 0x14[0] **nije pao na 0 ni nakon 2 s**;
   - u E7 isti bit „odmah čita 1”, pa je protumačen kao DONE i brojači su pročitani **odmah**.

   DS je ovdje sam sa sobom u sukobu: tablica 2.46 kaže da je `RX_EYE_MEAS_EN` **r/w** i opisuje ga kao „Start eye
   measurement”, a tablica 2.59 kaže **w/c** „RX_EYE_MEAS_EN / EYE_MEAS_DONE”. Dakle, „čita 1” može biti obično
   očitanje upisane vrijednosti, a ne DONE.
4. **Najjači kandidat (H1): brojači se uspoređuju s referencom PRBS checkera**, a ne s podatkovnim uzorkivačem. Naš link
   nikad nije mjerio oko s uključenim, zaključanim tvrdim PRBS checkerom (`RX_PRBS_OVR=0`, podaci su 8b10b iz fabrica).
   Jelena to može provjeriti za oko 15 minuta samo na M2, u loopbacku, bez kabela i bez GS-a (§2).
5. **Ako brojači ostanu mrtvi, postoji zamjenski „bathtub” iz fabric BER-a:**
   - horizontalno pomakom faze CDR-a preko `RX_CDR_PHASE_ACC` (0x0F) uz `RX_CDR_SET_ACC_CONFIG` bit0, „Enable overriding
     … phase (bit 0)” [DS t.2.48];
   - vertikalno pomakom praga podatkovnog uzorkivača preko `RX_AFE_OFFSET` (0x06[10:6]) uz njegov override.

   Procjena: oko 15 min po smjeru i brzini (≈1 h za oba smjera na 2,5 i 5 G), uz preduvjet da UART za BER radi (§3).
6. Pitanje za Patricka je u §4, na engleskom, spremno za slanje.

---

## 1. Što izvori stvarno kažu (svaka tvrdnja s izvorom)

### 1.1 Registri (VERIFICIRANO)

| Adresa | Polje | Izvor | Napomena |
|---|---|---|---|
| 0x14[0] | `RX_EYE_MEAS_EN` | DS t.2.46: **r/w**, „Start eye measurement”; DS t.2.59: **w/c**, „RX_EYE_MEAS_EN / EYE_MEAS_DONE”; PU: `W/C` | sukob r/w ↔ w/c, vidi H2 |
| 0x14[3:1] | — | DS t.2.59: `r`, *Unused* | **ali** UG t.7.13 kaže da je `RX_EYE_MEAS_CFG` širok **15** bita, PP ga mapira od bita 1 (`(0x14<<4)+1, 15`), a i SIM ima `[14:0]`. PU je granicu pomaknuo s lsb 1 na lsb 4 u `9c3b391` (01.12.2025.). Vidi H3 |
| 0x14[15:4] | `RX_EYE_MEAS_CFG` | DS t.2.46: 12 b, „Eye measurement window count” | jedinica prozora nije navedena nigdje |
| 0x15[5:0] | `RX_MON_PH_OFFSET` | DS t.2.44: „Define phase offset of monitor 2”, 6 b | `eyetools` računa 64 koda po UI (`codes_per_ui=64.0`), dakle ±0,5 UI |
| 0x16–0x1D | `RX_EYE_MEAS_{CORRECT,WRONG}_{11S,00S,001S,110S}` | DS t.2.47: „Number of correct/wrong detected 0bX11 … sequences”, 16 b, r | DS ne kaže što je referenca za „wrong” |
| 0x04[12:9] | `RX_EQA_LOCK_CFG` | DS t.2.44: bit1 „select monitor output for capturing”, bit2 „divider by 2 for tap weight”, bit3 „0=LF/1=HF amplitude” | „capturing” možda znači debug SRAM (0x2D–0x2F), vidi §3.3 |
| 0x05[5], 0x05[11], 0x06[5], 0x06[11] | `RX_EN_EQA_EXT_VALUE[0..3]` | DS t.2.59: [0]=TH_MON1_OVR, [1]=TH_MON2_OVR, [2]=TAPW_OVR, [3]=AFE_OFFSET_OVR (redom po adresama) | PU 56aa48b: 0x05[5] i 0x05[11] su „unused”, 0x06[5] je TH_MON1+TAPW, 0x06[11] je TH_MON2+AFE_OFFSET. SIM ima **4 zasebna** parametra `RX_TH_MON1_OVR`, `RX_TH_MON2_OVR`, `RX_TAPW_OVR`, `RX_AFE_OFFSET_OVR` |
| 0x07[9:5] | `RX_TH_MON` (r) | DS t.2.45: „Threshold applied to monitor 2” | **jedino mjesto gdje se vidi djeluje li override praga** (H4) |
| 0x08 | `RX_EQA_CONFIG` = 0x01C0 | DS t.2.44: samo „Configuration of DFE adaption” | bitovi nisu dokumentirani (H5) |
| 0x0D / 0x0F / 0x10 | `RX_CDR_PHASE_ACC_VAL` (r), `RX_CDR_PHASE_ACC` (r/w, 16 b), `RX_CDR_SET_ACC_CONFIG` (2 b) | DS t.2.48: „Enable overriding frequency (bit 1) and phase (bit 0) values”; „Phase accu value to be set” | osnova za horizontalni bathtub (§3.1) |
| 0x10[2] | `RX_CDR_FORCE_LOCK` | DS t.2.48 | drži `CDR_LOCKED` dok fazu namjerno pomičemo |
| 0x2D–0x2F | `RX_DBG_EN` (w/c), `RX_DBG_SEL[3:0]`, `RX_DBG_MODE`, `RX_DBG_SRAM_DELAY`, `RX_DBG_ADDR[9:0]`, `RX_DBG_RE/WE` (w/c), `RX_DBG_DATA[19:0]` | DS t.2.59 str. 94; UG t.7.13 | SRAM za hvatanje 1024 × 20 b. U PU karti su ta polja **zakomentirana**, pa ih `eyescan.py set/get` ne zna po imenu (§3.3) |
| 0x5C[2] | SerDes Testmode | DS t.2.59 str. 98; PU `tc_eyemeas` traži 0x5C[0]=1 i 0x5C[2]=1 | **naš bitstream već ima `SERDES_TESTMODE=1h1`** (`gateware/ber/cc_serdes_params.vh:202`), a `eyescan.py scan` to provjerava → isključeno |

### 1.2 Što imaju vendorski dizajni (VERIFICIRANO)

- Vendorski `serdes_lb.v` [PU] i naš `ber_top.v` vežu `REGFILE_CLK_I` na 0. Isto rade gatemate-pipe
  (`ccfpga_pipe_wrapper.v:480`) i prjpeppercorn-test-cases (`084-serdes-loopback/serdes_lb.v:381`). Taj **takt
  regfilea zato nije uzrok** kod nas: Patrickov dizajn je isti, a regfile koristi JTAG.
- Razlike između vendorskog `serdes_lb.v` (ab7ce94 + 22bbe50) i našeg `cc_serdes_params.vh` u RX poljima vezanima uz
  mjerenje (strojna usporedba svih `.PARAM(...)`):
  - vendor ima sve `RX_*_RESET_OVR=1`, RESET, PMA, EQA, CDR, PCS i BUF, dakle resete vodi regfile; mi imamo 0;
  - vendor ima `RX_COMMA_DETECT_EN_OVR=1` i `RX_MCOMMA/PCOMMA_ALIGN_OVR=1`, uz `RX_SLIDE=2'b01`;
  - `RX_EQA_CONFIG`, `RX_MON_PH_OFFSET`, `RX_DBG_*` i `RX_DATA_SEL` su **isti** kod oba;
  - vendor ima `RX_EYE_MEAS_EN=0`, a mi parametar `EYE_EN`.
- U SIM parametrima hard makroa **`RX_EYE_MEAS_EN` uopće ne postoji**: ima samo `RX_EYE_MEAS_CFG[14:0]` i
  `RX_MON_PH_OFFSET`, kao ni `RX_DBG_EN`. Pokretanje je dakle **čisto runtime strob** u regfileu, pa je `EYE_EN=1` u
  bitstreamu u najboljem slučaju beskoristan. Može i štetiti: bit je 1 od konfiguracije, pa kasniji upis 1 nije novi
  brid (H2).
- Svi vendorski testni slučajevi (`tc_prbs`, `tc_loopback`, `tc_uipattern`) rade **na jednoj ploči u loopbacku s tvrdim
  PRBS-om**, a `EyeData.prbs_err_cnt` pokazuje da se PRBS bilježi uz oko (H1).

### 1.3 Naša mjerenja koja ograničavaju hipoteze (VERIFICIRANO, [NAŠE])

- Brojači su 0 u **svih 176 točaka** na obje ploče, na 2,5 G (PROFILE 1) i na 5 G (PROFILE 2), uz
  `RX_EQA_LOCKED=1` i `RX_CDR_LOCKED=1` (`VERIFY_20260926_RATES.md` §9.6, `data_20260926/t5066/e7_eye_*.json`).
- Prije E7 (`lab4.out` r. 32–44) petlja je čekala da 0x14[0] padne na 0 i **istekla je nakon 2 s** na obje ploče.
  Stanje tada: `RX_EN_EQA=1`, `RX_EQA_LOCK_CFG=12`, `RX_EQA_LOCKED=1`, `RX_CDR_LOCKED=1`.
- U E7 `measure()` upisuje `(window<<4)|1` maskom 0xFFF1, odmah čita 0x14[0]=1 i **u istoj milisekundi** čita
  brojače (`tools/eyescan.py` r. 143–151). Bit 0x14[0] se nijednom ne upisuje kao 0, osim u `finally` na kraju.
- `RX_TH_MON` (0x07[9:5]) je **15, na rubu raspona**, na obje ploče i na svim brzinama (`VERIFY_20260926_RATES.md` r.
  204 i 219). Adaptacija DFE-a dakle drži monitor 2 na samom pragu, a nitko nije provjerio prati li `RX_TH_MON`
  upisani override.
- U E7 su brojači 0 **u svim klasama**. Krivi prag ili kriva faza dali bi mnogo „wrong”, ne nulu. Nula znači da
  **brojač nije ni jednom inkrementirao**: mjerenje nije pokrenuto, nema reference ili se rezultat ne zapisuje.
  To ruši H4 kao primarni uzrok, ali H4 ostaje bitan kad brojači prorade.

---

## 2. Hipoteze što nedostaje, po vjerojatnosti, s testom od ≤ 15 min

Zajedničko za sve testove:
- Jedna ploča je dovoljna. **M2 je zdrav**; GS PLL je od 12.10. 17:20 nestabilan (`675dba9`, `d8e1b1a`).
- Bitstream mora imati `SERDES_TESTMODE=1` i `EYE_EN=0`, tj. svaki `ber_*` bit osim E7 eksperimenta.
- `eyescan.py set/get` radi samo s poljima iz PU karte. Za sirovi pristup koristi se isti objekt kroz kratki Python
  (`serdes_jtag.Serdes().s.wr_regfile(addr, data, mask)` / `.rd_regfile(addr)`, kao `eyescan.py measure`). U nastavku je
  to `R(a)` / `W(a, d, m)`:

```python
# fpga-jtag m2 run python3 - <<'EOF'   (u tools/ na Piju)
import time; from serdes_jtag import Serdes
sd = Serdes(); s = sd.s
R = lambda a: int(s.rd_regfile(a)); W = lambda a, d, m: s.wr_regfile(a, d, m)
cnt = lambda: [R(0x16 + i) for i in range(8)]
# ... test ...
sd.close()
EOF
```

### H1 — referenca za „correct/wrong” je tvrdi PRBS checker (VJEROJATNOST: visoka)

**Zašto:**
- „Wrong detected 0b001 sequence” traži poznat očekivani uzorak. PRBS checker ga ima, a podatkovni uzorkivač nema
  neovisnu referencu.
- Vendorska akvizicija vodi `prbs_err_cnt` uz oko [PU eyetools], svi vendorski testovi rade s PRBS-om [PU], a `setup=True`
  u potpisu `tc_eyemeas` upućuje na pripremni korak.
- Mi smo uvijek mjerili s `RX_PRBS_OVR=0` (fabric 8b10b, `ber_top.v:114` `RX_PRBS_SEL_I(3'b000)`).

**Test (M2, ~10 min):**
1. Uključi near-end PMA loopback i PRBS-7 na TX i RX. Za loopback upiši polja kako `tools/loopback.py` opisuje
   (`TX_LOOPBACK_OVR=1 TX_PMA_LOOPBACK=1`, ili far/near prema DS str. 62). PRBS-7 je `TX_PRBS_OVR=1 TX_PRBS_SEL=1`
   i `RX_PRBS_OVR=1 RX_PRBS_SEL=1`.
   ```
   fpga-jtag m2 run python3 eyescan.py set TX_PRBS_OVR=1 TX_PRBS_SEL=1 RX_PRBS_OVR=1 RX_PRBS_SEL=1
   fpga-jtag m2 run python3 eyescan.py set RX_PRBS_CNT_RESET=1      # w/c: exit 1 jer se čita 0 — to je očekivano
   fpga-jtag m2 run python3 eyescan.py get RX_PRBS_LOCKED RX_PRBS_ERR_CNT RX_CDR_LOCKED RX_EQA_LOCKED
   ```
   Očekuje se `RX_PRBS_LOCKED=1`. Ako kabel ide na GS, može i bez loopbacka: M2 TX PRBS → GS RX checker, kad GS PLL radi.
2. Pokreni mjerenje **s pauzom**: `fpga-jtag m2 run python3 eyescan.py scan --ph=0:0 --th=0:0 --window 512 --out h1.json`.
   Bolje je ručno: `W(0x14,0,1)`, zatim `W(0x14,(512<<4)|1,0xFFF1)`, `time.sleep(1)`, `print(cnt())`.
3. Ponovi s `RX_PRBS_OVR=0` kao kontrolom.

**Ishod:**
- Brojači ≠ 0 samo uz PRBS → **H1 potvrđen**. Oko se onda mjeri samo s PRBS uzorkom, što znači PRBS na TX strani
  partnera ili loopback, a ne pod živim 8b10b prometom.
- I dalje 0 → prijeđi na H2.

### H2 — EN je brid ili razina, a ne „start → DONE”; čitamo prerano i nikad ne ponovimo start (VJEROJATNOST: visoka)

**Zašto:**
- DS t.2.46 kaže r/w, a t.2.59 w/c.
- Bit nikad ne padne (lab4), a E7 pročita brojače odmah. U petlji bit nikad ne ide na 0, pa nakon prve točke više
  nema brida 0→1.
- Uz `EYE_EN=1` u bitstreamu brida nema ni u prvoj točki: mjerenje se „pokrene” za vrijeme reseta RX-a, a reset
  vjerojatno obriše brojače.

**Test (M2, bez PRBS-a i s njim, ~5 min):**
```python
print('0x14 prije', hex(R(0x14)))
W(0x14, 0, 0xFFFF);  print('nakon upisa 0:', hex(R(0x14)))      # čita li se 0? ako ne -> 0x14[0] je čisti status
W(0x14, 512 << 4, 0xFFF0)                                      # prozor, EN=0
for t in (0, 0.01, 0.1, 1, 5):
    W(0x14, 0, 1); W(0x14, 1, 1); time.sleep(t)                # svježi brid 0->1
    print(t, hex(R(0x14)), cnt())
W(0x14, 0, 1); time.sleep(0.5); print('nakon EN=0', cnt())     # latchaju li se brojači tek na silazni brid / stop?
```

**Ishod:**
- Brojači ≠ 0 nakon dovoljne pauze ili nakon EN=0 → ispravi `eyescan.measure()`: dodaj `EN=0` → `EN=1` → čekaj
  prozor → (`EN=0`) → čitaj.
- 0x14[0] čita 0 nakon upisa 0, a 1 nakon upisa 1 → to je **razina** (r/w), nije DONE.

### H3 — 0x14[3:1] su tri donja bita 15-bitnog `RX_EYE_MEAS_CFG`, npr. odabir monitora ili načina (VJEROJATNOST: srednja)

**Zašto:**
- Tri izvora kažu da je polje široko 15 b (UG t.7.13, PP, SIM), a DS kaže 12 b plus „unused”.
- PU je svjesno pomaknuo lsb s 1 na 4 [9c3b391].
- `tc_eyemeas` ima argumente `monitor=2` i `sel_tap=0`, koji moraju negdje u registar, a jedina neobjašnjena mjesta
  su 0x14[3:1] i 0x08.
- `eyescan.start_write` maskom 0xFFF1 uvijek upisuje 0 u [3:1]. Ako je 0 „monitor isključen”, mjerenje ne broji ništa.

**Test (~5 min):**
1. `W(0x14, 0b1110, 0x000E); print(hex(R(0x14)))`. Ako se [3:1] ne mogu upisati, H3 otpada.
2. Ako se mogu, za `m` u 1..7 ponovi H2 sekvencu s `W(0x14, (512<<4)|(m<<1), 0xFFFE)` prije brida.
   Prema potpisu je najvjerojatnije `m=2` („monitor=2”).

### H4 — override praga monitora 2 nije na bitu koji koristimo (VJEROJATNOST: srednja za *ispravnost* oka, niska za *nulu*)

**Zašto:**
- DS kaže 0x05[11], a PU kaže 0x06[11]. SIM pokazuje četiri zasebna overridea, što više odgovara DS-u.
- `RX_TH_MON` stoji na 15 (rub) i nitko nije provjerio prati li ga upisana vrijednost.

**Test (~5 min, `eyescan.py set/get`):**
```
fpga-jtag m2 run python3 eyescan.py get RX_TH_MON RX_TH_MON2 RX_EN_EQA_EXT_VALUE[1] RX_EN_EQA_EXT_VALUE[3]
fpga-jtag m2 run python3 eyescan.py set RX_TH_MON2=3 RX_EN_EQA_EXT_VALUE[3]=1 ; ... get RX_TH_MON   # prati li 3?
fpga-jtag m2 run python3 eyescan.py set RX_EN_EQA_EXT_VALUE[3]=0 RX_EN_EQA_EXT_VALUE[1]=1 ; ... get RX_TH_MON
```
Pazi: 0x06[11] uključuje i `RX_AFE_OFFSET_OVR`. Prije upisa pročitaj `RX_OFFSET` (0x07[13:10]) i isti iznos upiši u
`RX_AFE_OFFSET`, kako ne bi pomaknuo podatkovni prag (`TUNING_5G.md` §5.1).

**Ishod:** onaj bit uz koji `RX_TH_MON` prati upisanu vrijednost je pravi. Ispravi `eyescan.th2_ovr_write`.

### H5 — monitor ili mjerni stroj je uključen nedokumentiranim bitom u `RX_EQA_CONFIG` (0x08 = 0x01C0) (VJEROJATNOST: niska do srednja)

**Zašto:** 16 bita s opisom od jedne rečenice [DS]. Parametar `sel_tap` iz potpisa nema drugog vidljivog mjesta.
**Test:** samo ako H1–H3 padnu. Za svaki bit `b` od 0 do 15, jedan po jedan:
`W(0x08, 0x01C0 ^ (1<<b), 0xFFFF)`, pa H2 sekvenca, pa vraćanje 0x01C0 i `eyescan.py recal`.
**Rizik:** DFE se može razdesiti, ali `recal` i ponovno učitavanje bitstreama to vraćaju. To je 16 × ~40 s, dakle oko
**12 min**. Bolje je prvo pitati Patricka (§4).

### H6 — mjerni stroj živi u domeni reseta koju vendor drži regfileom (`RX_*_RESET_OVR=1`) (VJEROJATNOST: niska)

**Zašto:** to je jedina veća razlika u RX konfiguraciji između vendorskog `serdes_lb.v` i našeg dizajna (§1.2).
**Test bez rebuilda (~5 min):** upiši `RX_EQA_RESET_OVR=1` (s `RX_EQA_RESET=0`) i `RX_PCS_RESET_OVR=1` (s `RX_PCS_RESET=0`)
preko `eyescan.py set`, pa ponovi H2. Raspored bitova u 0x2B je provjeren u PP `b1eb52f`; upstream
`reset_serdes_rx` ga piše krivo (`SOURCES_20260926.md` S3), pa se ne kopira.

### H7 — w/c strobovi se uopće ne izvršavaju preko JTAG-a jer nema takta (VJEROJATNOST: niska, ali 1 min za isključiti)

**Test:** `eyescan.py set RX_CALIB_EN=1`, pa `get RX_CALIB_EN RX_CALIB_DONE`. Ako `RX_CALIB_EN` padne na 0, w/c strobovi rade
i problem je specifičan za mjerenje oka. Isto vrijedi za `RX_PRBS_CNT_RESET` iz H1.

### Isključeno (s dokazom)

- **Testmode:** 0x5C[2]=1 u našem bitstreamu (`cc_serdes_params.vh:202`); `eyescan.py scan` ga provjerava.
- **`REGFILE_CLK_I=0`:** isto je i kod vendora (§1.2).
- **DFE isključen ili nezaključan:** E7 je imao `RX_EN_EQA=1` i `RX_EQA_LOCKED=1`.
- **`EQA_LOCK_CFG` 0/2/0xE:** isprobano (§9.6).
- **lsb za CFG:** 4 je ispravno prema DS-u i PU-u. Ostaje samo pitanje iz H3, ali to je drugo pitanje.

**Redoslijed za Jelenu:** H7 (1 min) → H2 (5 min) → H1 (10 min) → H3 (5 min) → H4 (5 min). Ukupno ≈ 25–30 min na M2, a
H5/H6 dolaze tek ako sve prethodno padne. Bilo koji test s brojačima ≠ 0 je dovoljan da se `eyescan.py measure`
ispravi i E7 ponovi.

---

## 3. Zamjenski put kad brojači ostanu mrtvi: „bathtub” iz fabric BER-a

Načelo je da se pomiče **podatkovni** uzorkivač, ne monitor, a BER mjeri postojeći fabric checker (`ber_link.v`) kroz
`ber_mon.py`. `RX_MON_PH_OFFSET` i `RX_TH_MON2` ovdje **ne pomažu** jer pomiču samo monitor 2, koji ne odlučuje o podacima.

### 3.1 Horizontalno: fazu CDR-a drži override phase accumulatora

- Polja [DS t.2.48]:
  - `RX_CDR_PHASE_ACC` (0x0F, 16 b, „Phase accu value to be set”);
  - `RX_CDR_SET_ACC_CONFIG` bit0 (0x10[0], „Enable overriding … phase”);
  - očitanje `RX_CDR_PHASE_ACC_VAL` (0x0D);
  - `RX_CDR_FORCE_LOCK` (0x10[2]), da reset FSM (`RX_WAIT_CDR_LOCK`) ne krene ispočetka kad zbog pomaka padne lock.
- Zašto smije biti otvorena petlja: obje ploče rade na **zajedničkom refclku** (0 ppm, `SERDES_KNOWLEDGE.md` §6), pa
  zamrznuta faza ne bježi frekvencijski. Bježi samo jitter i wander PLL-a, što je u prozoru od nekoliko sekundi zanemarivo.
- **Provjera izvedivosti, ~10 min, prije svega ostalog:**
  1. `get RX_CDR_PHASE_ACC_VAL` 5 puta, da se vidi kako šeta zaključana petlja.
  2. `set RX_CDR_PHASE_ACC=<val+Δ> RX_CDR_SET_ACC_CONFIG=1 RX_CDR_FORCE_LOCK=1`, pa 5 puta `get RX_CDR_PHASE_ACC_VAL`.
     Ako ostaje na `val+Δ`, override **drži** fazu. Ako se vrati, override samo jednom upiše vrijednost i petlja je
     povuče natrag. Tada treba i `RX_CDR_CKP=0` i `RX_CDR_CKI=0` (petlja zamrznuta), pa ponoviti.
  3. Upozorenje iz `SERDES_KNOWLEDGE.md` §6: upis u 0x0E (FREQ_ACC) se **čita kao 0**. Zato se učinak gleda na 0x0D (VAL),
     ne na 0x0F.
  4. Vraćanje: `SET_ACC_CONFIG=0 FORCE_LOCK=0`, izvorni CKP i CKI, pa `eyescan.py recal`.
- **Kalibracija koraka:** koliko kodova `PHASE_ACC` čini 1 UI nije dokumentirano. Grubi prolaz kroz cijeli 16-bitni
  raspon u 32–64 koraka pokazuje periodu: BER skoči na ~0,5 (gubitak synca) i opet padne, a razmak dviju „rupa” je 1 UI.
- **Mjera:** za svaku točku `ber_mon.py run` s izračunom **udjela vremena u syncu** (`ab_table.py run_sync`, lekcija
  TASK-5070). Kad link gubi sync, BER iz checkera je uvjetan i sam za sebe laže.

### 3.2 Vertikalno: prag podatkovnog uzorkivača preko `RX_AFE_OFFSET`

- `RX_AFE_OFFSET` (0x06[10:6], „Set AFE offset”) postaje aktivan uz `RX_EN_EQA_EXT_VALUE[3]` (0x06[11]) [DS t.2.44 i t.2.59].
  Kalibrirana vrijednost čita se kao `RX_OFFSET` (0x07[13:10]); u E7 je bila 7 na gs.
- Za svaki korak od `RX_OFFSET` do oba ruba (5 b, ~±15 kodova) mjeri se BER. Rubovi na kojima BER prijeđe 10⁻⁶ ili
  10⁻⁹ daju visinu oka u kodovima. Bez mV/LSB podatka iz DS-a to je samo relativna mjera, dobra za usporedbu postavki i
  smjerova.
- **Druga mogućnost bez RX overridea:** smanjivati `TX_AMP` na predajniku dok BER ne prijeđe prag. To je vertikalna
  margina s TX strane, a polje je već u `eyescan.py`.

### 3.3 Ako se pokaže da „capturing” znači debug SRAM: statističko oko iz sirovih uzoraka

- `RX_EQA_LOCK_CFG` bit1, „select monitor output for capturing” [DS], najvjerojatnije bira **što ide u debug SRAM**
  (`RX_DBG_*`, 0x2D–0x2F, 1024 × 20 b) [DS str. 94, UG t.7.13].
- Ako `RX_DBG_SEL` može dati izlaz monitora 2 uz podatke, oko se računa offline: za svaku (fazu, prag) usporedi
  odluku monitora s odlukom podatkovnog uzorkivača. To je isto što bi radili brojači, samo u softveru.
- **Test (~15 min, sirovo, jer PU ta polja ima zakomentirana):**
  ```python
  for sel in range(16):
      W(0x2D, (sel << 1) | 1, 0x001F)                      # RX_DBG_SEL=sel, RX_DBG_EN=1 (w/c)
      time.sleep(0.05)
      words = []
      for a in range(8):
          W(0x2E, a | (1 << 10), 0x07FF)                   # RX_DBG_ADDR=a, RX_DBG_RE=1
          words.append((R(0x2F) << 4) | (R(0x2E) >> 12))  # DATA[19:4] i DATA[3:0]
      print(sel, hex(R(0x2D)), [hex(w) for w in words])
  ```
  Traži se `sel` za koji se sadržaj mijenja od hvatanja do hvatanja, a mijenja se i kad se `RX_EQA_LOCK_CFG` bit1
  prebaci 0↔1.
- `RX_DBG_MODE` i `RX_DBG_SRAM_DELAY` (zadano 5) nisu opisani; ostaju zadani.

### 3.4 Procjena trajanja (2,5 Gb/s; na 5 G je vrijeme po bitu upola kraće)

| Korak | Broj točaka | Po točki | Ukupno |
|---|---|---|---|
| Provjera izvedivosti overridea faze (§3.1) | — | — | 10 min |
| Kalibracija UI u kodovima `PHASE_ACC` | 32–64 | ~3 s JTAG + 1 s BER | 3–5 min |
| Horizontalni bathtub do 10⁻⁹ (3·10⁹ bita ≈ 1,2 s) | ~30 | ~5 s | 3 min |
| Pokušaj rubova do 10⁻¹¹ (≈ 120 s po točki) | 2 × 4 | ~2 min | 16 min |
| Vertikalni bathtub preko `AFE_OFFSET`, do 10⁻⁹ | ~30 | ~5 s | 3 min |
| **Jedan smjer, jedna brzina** | | | **≈ 15 min (10⁻⁹) do 35 min (10⁻¹¹)** |
| Oba smjera × 2,5 G i 5 G | | | **≈ 1 h do 2,5 h** |

- **Preduvjet** je BER očitanje s ploče koja prima. M2 UART radi, a GS UART je isprekidan (`0a54f7d`; `675dba9` dodaje
  `ber_mon` sparse način).
- Za smjer m2→gs, dok je GS UART nepouzdan, ostaje JTAG: `ber_jtag_check.py` daje samo grubi udio „PEER” uzoraka
  (~10⁻¹), a tvrdi PRBS brojač `RX_PRBS_ERR_CNT` (0x1F) ima pod od ~1400–2200 grešaka/s pod 8b10b i comma alignom
  (`VERIFY_20260926_RATES.md` §5). JTAG-only bathtub zato ima smisla tek uz PRBS bez 8b10b s obje strane, kao vendorski
  `tc_prbs`.

---

## 4. Nacrt pitanja za Patricka Urbana / Cologne Chip (Goran šalje sam)

> **Subject:** GateMate CC_SERDES on-chip eye measurement (regfile 0x14–0x1D): how is it started?
>
> Hi Patrick,
>
> we run a 2.5/5 Gb/s GateMate-to-GateMate SerDes link (ULX5M-GS ↔ M2, shared refclk, 8b10b, DFE on,
> `RX_EQA_LOCKED=1`, `RX_CDR_LOCKED=1`, `SERDES_TESTMODE=1`) and use your `eyetools.py` (83d7858) with our own
> acquisition over JTAG, since `tc_eyemeas` in gm_serdes_lb is still a stub. The eye counters 0x16–0x1D stay 0 in every
> configuration we tried. Could you tell us the exact sequence your acquisition uses? Specifically:
>
> 1. **Reference:** are CORRECT/WRONG_* counted against the PRBS checker (so TX/RX PRBS must be on and
>    `RX_PRBS_LOCKED=1`), or against the data sampler (works with normal 8b10b traffic)? `EyeData.prbs_err_cnt` suggests PRBS.
> 2. **Start/done:** is 0x14[0] a w/c start strobe that reads back as DONE (DS1001 Table 2.59), or a r/w level enable
>    (Table 2.46)? It reads 1 immediately after the write and never returns to 0. Do we need a 0→1 edge per point, and how
>    long is one window of `RX_EYE_MEAS_CFG` (unit: UI, words, or EQA update cycles)?
> 3. **Bits 0x14[3:1]:** UG1001 lists `RX_EYE_MEAS_CFG` as 15 bits (prjpeppercorn maps it from bit 1), while the DS and
>    serdestool (9c3b391) use [15:4]. What are the three low bits — the `monitor` / `sel_tap` arguments of `tc_eyemeas`?
> 4. **Overrides:** is the `RX_TH_MON2` override at 0x05[11] (DS1001 Table 2.59) or at 0x06[11] together with
>    `RX_AFE_OFFSET` (serdestool map)? Must `RX_EN_EQA=1` and/or `RX_EQA_LOCK_CFG[1]=1` be set, and does `RX_EQA_CONFIG`
>    (0x08, default 0x01C0) need a change?
> 5. **Optional:** is `RX_CDR_SET_ACC_CONFIG[0]` + `RX_CDR_PHASE_ACC` a supported way to hold the data-sampler phase at an
>    offset (for a BER bathtub), and how many `PHASE_ACC` codes are one UI?
>
> Our scan: monitor 2, `RX_MON_PH_OFFSET` −32..+28 step 4, `RX_TH_MON2` −15..+15 step 3, window 512; tried with DFE
> on/off, `EQA_LOCK_CFG` 0/2/0xE, `RX_EYE_MEAS_EN=1` in the bitstream; all eight counters 0 at every point.
> Even a five-line pseudo-sequence of `tc_eyemeas` would help us a lot. Thank you!
>
> Goran Mahovlić (ULX5M)

---

## 5. Što s ovim napraviti

1. Jelena, kad ploče budu slobodne: redoslijed testova iz §2 (H7 → H2 → H1 → H3 → H4), ≈ 30 min na M2, bez rebuilda.
2. Ako neki test pokaže brojače ≠ 0: ispraviti `eyescan.measure()`, uz test u `tools/tests/test_eyescan.py`, i
   ponoviti E7 na 2,5 G i 5 G.
3. Ako ništa ne proradi: Goran šalje §4. Do odgovora ide bathtub iz §3.1/§3.2 na m2→gs i gs→m2 s BER-om preko UART-a,
   ≈ 1 h za obje brzine.
4. Nepoznanice koje ovaj dokument ne može riješiti bez hardvera ili odgovora vendora:
   - jedinica prozora `RX_EYE_MEAS_CFG`;
   - značenje `RX_EQA_CONFIG` i `RX_DBG_SEL`;
   - broj kodova `PHASE_ACC` po UI;
   - mV po kodu za `RX_AFE_OFFSET` i `RX_TH_MON2`.
