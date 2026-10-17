# CONTEXT_JELENA_20261017 — GS↔M2 SerDes: što je utvrđeno, što je pretpostavka, što je otvoreno (TASK-5559)

**Za koga:** za mene (Jelena, trajni agent PRJ-051) i za svakog tko nastavlja. **Stanje:** 17.10.2026. popodne.
Oznake: **UTVRĐENO** (mjereno ili pročitano u izvoru, s putanjom), **PRETPOSTAVKA**, **OTVORENO**.
Izvori pročitani za ovaj sažetak: `SERDES_KNOWLEDGE.md`, `CALIBRATION_REVIEW_20261016.md`, `CALIBRATION_OPTIONS_20261017.md` (v1)
i `_v2.md` (konačni plan K0–K8), `SOAK_R1_2G5_20261017.md`, `CHAIN4_5G_P2_20261017.md`, `TOOLCHAIN_20261017.md`,
`OPENCOLOGNE_PCIE_PREGLED_20261017.md` §0–5, `RESEARCH_SERDES_USPOREDBA_20261017.md` §0/§4, git log repoa,
TaskManager PRJ-051 (50 zadataka), RAG (FPGA, agent_jelena, agent_kosjenka, agent_manda), memorija (fpga-lab-dva-dirtyjtaga,
feedback-fpga-task-pravila, lab-watch-dugi-lab-na-piju, ulx5m-gs-napajanje-i-pll-kanal, serdes-gs-m2-2g5-profile1,
gatemate-zadani-lanac, gatemate-pr-flow-zamke).

---

## 1. Postav (UTVRĐENO)

| Stavka | Vrijednost | Izvor |
|---|---|---|
| Ploče | gs = ULX5M-GS v005 (Waveshare CM5-IO-BASE-A), m2 = ULX5M-M2 (M.2 kartica) | memorija fpga-lab-dva-dirtyjtaga, SERDES_KNOWLEDGE §1 |
| Kanal | gs → IO ploča → PCIe utor → PCIe-M.2 adapter (FFC) → m2. P/N zamijenjen u adapteru → `RX_POL=1` na obje | 7875d14 (TASK-5524) |
| Refclk | jedan Si511 100 MHz na gs, m2 prima isti takt kroz lanac, 0,0 ppm | SERDES_KNOWLEDGE §1 |
| Napajanje | Vcore J3 = 2-3 (1,1 V) na obje; VDD_SER preko R105/R106 1–2 Ω; gs ima 1 µF na C127/C128/C42 (27.09.); **TP10/TP8 nikad izmjereni** | SERDES_KNOWLEDGE §1.1, VERIFY §20 |
| Lab | Pi 192.168.10.14, `fpga-jtag gs|m2 <bit> -r` (dva DirtyJTAG-a, lookup po serijskom), gs UART = jedini BER izlaz, alati u `/home/pi/ulx5m-serdes/tools`, `/home/pi/gs.owner` brava | memorija |
| Lanac | `oss-cad-suite-20261016` zadani (yosys 0.70+145, nextpnr 0.11.1-63, gmpack v1.13-6); `build_ber.sh`, seed gs 7 / m2 2; gs seed 7 + router2 ponekad ne konvergira → seed 1 | TOOLCHAIN_20261017, ovaj zadatak (B2) |
| Bit 2,5G | N 1·5·5, OUTDIV 2, PROFILE 1 (EQA adaptivni, PEAK 24, GAIN 0, CDR CKP 0x3E), TX_NEG 1, TX_AMP 12, CFGRST | TOOLCHAIN §3 |

## 2. Što je utvrđeno o linku do 17.10. jutro

1. **2,5G radi s greškama, 5G ne radi.** Zadnji soak (R1, 1800 s, jedno učitavanje): M2→GS 2,23·10⁻¹¹ [1,66; 2,94]·10⁻¹¹,
   GS→M2 8,9·10⁻¹³ [1,1·10⁻¹³; 3,2·10⁻¹²], 0 gubitaka sinkr. (SOAK_R1). 5G P2: 9/9 pokušaja bez locka, PEER OTHER 6,9–23,9 % (CHAIN4).
2. **Greške su linijske** (8b10b kodne greške na 56/56 zapisa), Poissonove, bez praska → pod margine, ne fabric (REVIEW_20261016 §2).
3. **Lutrija učitavanja:** vrata L3 prolaze iz 1. pokušaja ≈ 1/3 (5/15, chain4); isti bit daje 10⁻⁸ … 10⁻¹¹ ovisno o učitavanju.
4. **CC_SERDES iz p_r i nextpnr bajtno isti** (TASK-5546) → p_r nije poluga.
5. **JTAG recal (CALIB_EN strob) ostavlja CAL 9/7 koji preživi `-r`**; CAL0 (OVR=1 VAL=0) je ispravno stanje (TASK-5542).
6. **Eye brojači (0x14–0x1D) nikad ne broje** na ovim pločama (TASK-5525/5529).
7. **R1 bit (gs 79b07795 / m2 4a94fc99) ima upečen CKP_OFFSET 0 koji nikad nije bio izmjeren** (v2 §0 t. 2) → nije osnovica.
8. Cologne Chip nema objavljen BER za 2,5/5G (TASK-5554). Dokaz 10⁻¹² @ 95 %: k ≤ 2 u 5040 s po smjeru (v2 §2.1).
9. Reset slijed: CC PIPE drži `RX_WAIT_CDR_LOCK 0` ali sa statičkim RX-om; mi imamo adaptivni EQA + WAIT 0 — bez referentnog
   izvora; u modelu `rx_resetdone` raste 14,4 µs prije CDR locka (TASK-5557).

## 3. Što je utvrđeno u ovom zadatku (TASK-5559) — K0/K1

| # | Nalaz | Dokaz |
|---|---|---|
| T1 | WIP TASK-5542 commitan; Pi `link_gate.py` (c4c27f3c) je repo verzija bez `--diag-secs` (Pi stariji), ostali alati sha256 isti | commit 89ec0af |
| T2 | Novi parametri `OV_WAIT_CDR_LOCK`, `OV_EQA/CDR/PMA_RESET_TIME`, `OV_EN_EQA`, `OV_EQA_CKP_LF/HF`; zadano bajtno isto (gs ed04be04, m2 ec045992) | `test_reset_bake.py` 5/5, `data_20261017/t5559/k0/serdes_cmp_k0.txt` |
| T3 | B0′ / B1 / B2 izgrađeni; `serdes_cmp`: B0′ − oss1016 = 3 polja, B1 − B0′ = 1, B2 − B1 = 3 (obje ploče) | isto |
| T4 | **H-a potvrđen na siliciju (obje ploče):** `RX_EQA_CKP_OFFSET` i `RX_EQA_CKP_LF` se ne upisuju dok je `RX_EN_EQA=1` (tiho odbačeno, i sirovi upis 0x04 maska 0x00FF); uz `RX_EN_EQA=0` upis prolazi i **drži** nakon `RX_EN_EQA=1` (10 čitanja kroz 5 s) | `k1/k1w_b0p_{gs,m2}.json` |
| T5 | 0x01 (reset vremena, WAIT_CDR_LOCK) je upisiv uz EN_EQA=1 (kontrola) | isto |
| T6 | **Readback 0x2B nije upisana riječ** (upis 0x0004 → čita 0x0001, 0x0000 → 0x0400, 0x000C → 0x0041); readback 0x2B nije dokaz ni za ni protiv | isto |
| T7 | Na B0′ (učitavanje 12:47): M2→GS 0 grešaka u 1,5·10¹¹ bita (6 × 20 s); TAPW pin +3 držan 45 s daje 1,0·10⁻⁷, a nakon `restore` adaptacija se sama vraća na 0 grešaka → test „oštećenje → razina” iz plana na B0′ ne može dati oštećenje | `k1/k1c_b0p*.jsonl` |

| T8 | **K1-c:** 0x2B razine eqa/cdr/rx/pma se izvršavaju: svaka daje 1417–2978 bitnih grešaka samo u vlastitom RX smjeru (eqa 6/6, obje ploče); prazni upis u 0x2B ili 0x01 daje 0–16 (pozadina). Readapt = `eqa` | `k1/k1p_b0p*.jsonl`, `.table` |
| T9 | **K1-d:** R1 bit čita `RX_EQA_CKP_OFFSET=0` (0x04=0x3900) na obje → CKP put kroz bit radi | `k1/k1d_r1bit.txt` |
| T10 | **K2** (7 isprepletenih krugova, novo učitavanje po vratima, readapt eqa): prolaz iz 1. pokušaja B0′ 4/7, B1 4/7 (Fisher p 0,70), B2 1/7 (3,9 pokušaja). Zaustavljeno unaprijed zapisanim pravilom (§7). Osnovica = B0′ | `k2/k2_table.md` |
| T11 | **K3** (3 učitavanja, prvi prozor odbačen): gs TX idle → M2→GS ×2,9 / ×47 / ×7,8; AMP 16 gori na gotovo svim ćelijama (gs 16: M2→GS ×0,01–0,18 na 3/3). Svaki EQA readapt = novo izvlačenje (A stanja ×10–×100) i prasak ~2500 u prvom prozoru | `k3/k3_table_drop1.md` |
| T12 | **K4a** AMP parovi (2 učitavanja × 3 izvlačenja): gs 8 / m2 12 najbolji, M2→GS medijan 3,1·10⁻¹¹ prema 6,5·10⁻¹¹ (12/12), skupno ×2,4, bolji na svakom učitavanju; m2 AMP 10 jasno gori | `k4/k4amp_table.md` |
| T13 | **K4b** na gs 8 / m2 12: m2 POST 8/12, gs POST 0, gs/m2 PEAK 16, B-static (EN_EQA 0, PEAK 15, GAIN 8) — **nijedna točka ne pobjeđuje osnovicu**; B-static ×300–3000 gori, m2 POST 12 ×15 gori M2→GS, gs POST 0 ×20 gori GS→M2 | `k4/k4b_table.md` |
| T14 | **B-final** = gs `gs_2g5_bf_amp8_s7.bit` 9a9d4c0f (B0′ + OV_TX_AMP 8; serdes_cmp prema B0′ = 1 polje TX_AMP 12→8) + m2 `m2_2g5_b0p_s2.bit` e4251f4b (B0′). **D1: 46/46 polja readback = namjera** na 3 učitavanja | `k6/intent.json`, `k6/d1_*.json` |

## 4. Pretpostavke (nisu dokazane)

- P2 (oborena K2-om): `RX_WAIT_CDR_LOCK 1` ne smanjuje lutriju.
- P3 (djelomično oborena K3-om): dio poda M2→GS je sprega vlastitog gs TX-a (NEXT ili napajanje), ali i s ugašenim gs TX-om
  M2→GS ostaje ~6·10⁻¹¹ … 3·10⁻¹⁰ na tim učitavanjima → ostatak je kanal/RX.
- P4: TP10/TP8 su ≥ 1,03 V (DS 1,00–1,10 V) — nije izmjereno; uz K3 nalaz (sprega TX → RX na gs) H1/H2 od Gorana su sada
  najvrjednije mjerenje.

## 5. Otvoreno / stanje u 20:00 CEST

- **K4 nije pomaknuo pod ×10** (najviše ×2,4, gs AMP 8) → plan §3.4: B-final + vrata (D1, D2) kao operativni link,
  izmjereni BER po smjeru s CI kao specifikacija, zaštita protokolom, hardverska lista (H1–H5, M2 v0.2).
- **K6 radi na Piju od 19:50** (`lab/k6_chain.sh`, PID 6273): 30 vrata (D2, `k2_k6_NN`), pa 3 × 5040 s soak (`soak_k6_N`),
  log `~/ulx5m-serdes/t5559/k6/k6.out`, kraj = redak `== k6 done`. Očekivani kraj ~04:00.
- **Za nastavak:** `python3 lab/k2_table.py ../t5559/k6 --arms k6 --ref k6` (D2), `python3 lab/gate_table.py ../t5559/k6`
  i `ber_windows.py` nad `soak_k6_N_soak.jsonl` (D3/D4), pa izvještaj + PDF + Telegram (FAZA 3).
- K7 (5G) tek nakon Goranovog H1 (TP10/TP8). K8 (flash) otpada (uputa #354).

## 6. Pravila koja si ponavljam

- Učitavanje samo `fpga-jtag gs|m2 … -r`, bez power-cyclea, nikad `Z`. JTAG readback/ILA umjesto pitanja Goranu.
- Svaki `set` provjerava readback + izlazni kod (`link_gate` → `SET_FAIL`). CKP polja: `EN_EQA 0 → upis → EN_EQA 1`.
- Na Piju ne koristiti `pkill -f <uzorak>` iz ssh naredbe koja sadrži isti uzorak (ubije vlastitu ljusku); koristiti `[p]attern`.
- Prekinut `k1_func` može ostaviti prijamnik zamrznut (EN_EQA 0, TAPW pin) → uvijek `restore` + `get RX_EN_EQA_EXT_VALUE` prije mjerenja.
- BER samo iz delta snimaka, prvi prozor odbačen, 95 % Garwood; trajanje soaka fiksno unaprijed.

## 7. Unaprijed zapisano pravilo za K2 (zapisano 17.10. 13:48 CEST, nakon 1. kruga, prije ostalih podataka)

Krug (B0′, B1, B2 po jedno vrata) traje ~28 min (JTAG režija ~2 min po pokušaju, link ~60 s), pa 20 krugova = ~9 h.
**Međuanaliza nakon 10. kruga:** ako nijedan krak nema ≥ 8/10 prolaza iz 1. pokušaja, K2 staje. Takav krak ni uz
10/10 u preostalim krugovima ne bi dao ≥ 19/20, a uz stvarni udio ≤ 0,8 ne može proći ni D2 (28/30). Ako neki krak
ima ≥ 8/10, K2 ide do 20 krugova. Pobjednik je i dalje krak s Fisher p < 0,05 prema B0′. Inače ostaje B0′ (najmanje
promjena), a lutrija se rješava kroz K3/K4 (margina).
