# Zašto GateMate eye scan (`RX_EYE_MEAS_EN`) ne radi — uzrok iz dokumentacije i koda

TASK-5529 · Kosjenka · 15.10.2026. · nastavak na `EYE_SCAN_ISTRAZIVANJE.md` (H1–H8) i `VERIFY_20260926_RATES.md` §17.6–17.7.
Pi ni ploče nisu dirani. Ovo je analiza postojećih izvora i zapisa iz laba. Jelena mjeri u TASK-5527.

---

## 0. Ukratko

1. **Kvar nije specifičan za oko.** Na našim pločama se preko JTAG-a ne izvršava **nijedan w/c strob** koji smo
   provjerili:
   - `RX_CALIB_EN` ostaje 1 (TASK-5483, `data_20261012/t5483/eye20.out` r. 15–18);
   - `RX_EYE_MEAS_EN` ostaje 1 (svi pokusi od lab4 do labeye);
   - upis `RX_RESET_OVR=1, RX_RESET=1` u 0x2B ne ruši CDR (`eye20.out` r. 100–101).

   Brojači oka su 0 zato što **mjerni stroj nikad ne krene ili rezultat nikad ne stigne u regfile**. Kriva postavka
   praga, faze ili DFE-a nije uzrok.
2. **Najvjerojatniji uzrok (H-A):** dio regfilea koji izvršava strob, briše w/c bit i upisuje rezultat nema takta u
   trenutku kad bi to trebao napraviti. `REGFILE_CLK_I` je vezan na 0 u **svim** dizajnima, i našima i Patrickovima.
   DS1001 str. 89 kaže da regfile piše „with the rising edge of CLK_REG_I”.

   Sve što se izvrši **unutar same JTAG transakcije** radi:
   - upis i čitanje polja;
   - hvatanje 0x07 pri čitanju.

   Ne radi ništa što regfile mora napraviti **poslije** transakcije: brisanje w/c bita, start, DONE i upis brojača.
3. **(b) i (c) su odbačeni izvorom.**
   - Adrese i bitovi 0x14–0x1D u `serdestool.py` jednaki su onima u DS-u (t.2.59) i u prjpeppercornu
     (`TileBitDatabase.cpp:488–498`).
   - Toolchain prenosi `RX_EYE_MEAS_*` u bitstream (`pack_serdes.cc:94–96` i `bitstream.cc:474–477`). Dokaz je očitanje
     0x14=0x8000 odmah nakon učitavanja.

   **(d) je odbačen mjerenjem:** EQA, sel_comp_data, LOCK_CFG i PRBS isprobani su u svim kombinacijama. Prozor od 1
   traje 32 ns, a EN stoji 1,5 s, dakle 4,6 · 10⁴ puta dulje od najduljeg prozora.
4. **Patrick tvrdi da njemu radi („pola oka”), a koristi isti `regfile_clk = 1'b0`.** Razlika mora biti izvan
   poslanog `.v`-a. U njegovom `serdes_lb.ccf` (mail UID 85, r. 5–6) ostali su pinovi **`regfile_we` i `regfile_rstn`**,
   kojih u `.v` nema. To je trag da je njegova klupa imala fabric pristup regfileu, a time vjerojatno i takt.
   IDCODE ne razlikuje reviziju čipa: DS str. 142 kaže da IDCODE „only contains a placeholder value”. Zato je
   `0x20000001` na obje ploče **bez dokazne vrijednosti**.
5. **Pokusi za Jelenu (§4):**
   - P1 (2 min, bez novog bitstreama): izvršavaju li se uopće w/c strobovi `TX_PRBS_FORCE_ERR` i `RX_PRBS_CNT_RESET`;
   - P2 (5 min, samo softver): 100 000 TCK u Run-Test/Idle nakon starta;
   - P3 (jedan bitstream): `REGFILE_CLK_I` na slobodni takt, uz `REGFILE_EN_I=0`.

   **Pitanje za Patricka je u §5.**

---

## 1. Izvori (što je pregledano)

| Oznaka | Izvor | Što daje |
|---|---|---|
| DS | Cologne Chip DS1001, rujan 2026. (tekst: `~/app/tmp/zadaci/TASK-5488_*/ds.txt`) | t.2.44–2.47 (str. 80–81), t.2.58–2.59 regfile (str. 89–98), JTAG 0x25/0x26 (str. 149–150), IDCODE (str. 142) |
| CC | `tools/upstream_cc_20261015/serdestool.py` (Patrick, 15.10.) | mapa polja r. 391–401; `eye_freeze` r. 1354–1427; `eye_measure` r. 1449–1478; `tc_eyemeas` r. 1740–1824 |
| PU | `gateware/upstream_cc_20261015/serdes_lb.v` + `mail_patrick/85_serdes_lb.ccf` | `REGFILE_CLK_I(regfile_clk)` r. 501, `wire regfile_clk = 1'b0` r. 511; CCF r. 5–6 `regfile_we`, `regfile_rstn` |
| NP | nextpnr himbaechel/gatemate (`~/app/raid/archive/toolchain-20261009/nextpnr-gatemate-setuphold/src-vanilla`) | `pack_serdes.cc:93–96` (`RX_SLIDE` 2 b, `RX_EYE_MEAS_EN` 1 b, `RX_EYE_MEAS_CFG` 15 b, `RX_MON_PH_OFFSET` 6 b); `bitstream.cc:474–477` (svi parametri → `serdes.add_word`) |
| PP | prjpeppercorn `libgm/src/TileBitDatabase.cpp:488–498` (`~/app/tmp/zadaci/TASK-5488_*/pp`) | `RX_EYE_MEAS_EN` = (0x14<<4)+0, 1 b; `RX_EYE_MEAS_CFG` = (0x14<<4)+1, 15 b; brojači 0x16–0x1D, 16 b |
| YS | Yosys `oss-cad-suite-20260928/share/yosys/gatemate/cells_bb.v:100–102` | `RX_EYE_MEAS_EN [0:0]`, `RX_EYE_MEAS_CFG [14:0]`, `RX_MON_PH_OFFSET [5:0]` |
| LAB | `docs/data_20261012/t5483/eye20.out`, `docs/data_20261015/t5525/{labeye,probes}.out` | mjerenja na obje ploče |

---

## 2. Rangirane hipoteze

### H-A — w/c strob, DONE i upis brojača trebaju takt regfilea koji naša postava ne daje (hipoteza (a)) · VJEROJATNOST: visoka

**Za:**
- DS str. 89, t.2.58 i tekst ispod slike 2.42: „Data is written to the register file with the rising edge of
  CLK_REG_I. At least 16 clock cycles must elapse between two accesses.” `REGFILE_CLK_I` je u našem `ber_top.v:122`,
  u Patrickovom `serdes_lb.v:511`, u gatemate-pipe i u prjpeppercorn testovima vezan na `1'b0`
  (`EYE_SCAN_ISTRAZIVANJE.md` §1.2).
- **Generalnost kvara** (LAB):
  - `RX_CALIB_EN` (0x02[0], w/c) čita 1 **već prije** upisa (ostatak ranijeg pokusa) i ostaje 1 nakon 0,05 s i 0,5 s
    (`eye20.out` r. 15–18);
  - `RX_EYE_MEAS_EN` ostaje 1 na obje ploče, kroz četiri bitstreama (naš std, naš `EYE_CFG`, Patrickov, E7) i pri
    prozoru 1…2048 (`labeye.out` r. 10–14, `probes.out` r. 5–9 i 15–19);
  - `RX_RESET_OVR=1, RX_RESET=1` (0x2B[11:10], w/c) ne ruši CDR. Po DS-u bi to bio puni RX reset
    (`eye20.out` r. 100–101).
- **Što radi, a što ne**, i to je ključno razgraničenje:
  - radi sve što se zbiva **unutar** JTAG transakcije:
    - upis r/w polja vidi se odmah pri čitanju (0x14=0x0010 → 0x0011, `probes.out` r. 15–19; 0x08 svih 16 vrijednosti, r. 21);
    - čitanje 0x07 okida hvatanje radne točke (`eye_capture_op` daje smislene i promjenjive `th_mon`/`tapw`/`offset`);
    - statusi koje hardver drži (`CDR_LOCKED`, `PRBS_ERR_CNT`) čitaju se ispravno, jer su to vjerojatno
      kombinacijski putevi;
  - ne radi ništa što regfile mora napraviti **asinkrono nakon** transakcije: obrisati w/c bit, poslati start u
    domenu PMA-takta i vratiti DONE i brojače natrag.
- Brojači su 0 u **svim** klasama i svim točkama (`VERIFY_20260926_RATES.md` §9.6, 176 točaka). Kriv prag ili kriva
  faza dali bi mnogo „wrong”, a ne nulu. Nula znači da stroj nijednom nije inkrementirao.

**Protiv / otvoreno:**
- Patrick tvrdi da njegov alat crta oko, a njegov `.v` također ima `regfile_clk = 0`. Ako mu stvarno radi s tim
  `.v`-om, onda regfile ipak ima interni takt, a razlika je u:
  - klupi ili JTAG adapteru (FTDI/pyftdi koji drugačije prolazi kroz Run-Test/Idle, vidi P2);
  - ili u reviziji silicija (H-B).
- Trag da njegova klupa nije bila ista kao poslani `.v`: `85_serdes_lb.ccf` r. 5–6 pinira `regfile_we` i
  `regfile_rstn`, kojih u `.v` nema. Ostatak je to verzije s fabric regfile sučeljem.

**Test:** P1 → P2 → P3 (§4).

### H-B — revizija silicija: mjerni blok ili w/c logika na našim čipovima ne radi, a na Patrickovom radi (dio (a)) · VJEROJATNOST: srednja

- DS str. 142: IDCODE „only contains a placeholder value”. Zato `0x20000001` na m2 i gs (`probes.out` r. 30) ne
  isključuje razliku u reviziji.
- DS ne navodi errata ni reviziju.
- Ne može se provjeriti iz koda. Treba oznaka kućišta ili date code s obje naše ploče i Patrickov podatak (§5).

### H-C — start traži uvjet izvan regfilea, npr. fabric `RX_CLK_I` ili `CLK_CORE_RX` kao takt stroja (dio (a)) · VJEROJATNOST: niska

- `eye_run_time` u CC r. 1440–1447 računa trajanje u „PMA clocks”, dakle stroj radi na PMA ili jezgrenom RX taktu.
- Isključeno je da tog takta nema: PRBS checker radi i broji, a resetni brojači DS-a rade na `CLK_CORE_RX_I`.
- Isprobano je i `RX_CLK_I` izravno iz `RX_CLK_O` (Patrickov `serdes_lb.v:478`) i preko `CC_BUFG` (naš `ber_top`).
  Rezultat je isti (labeye).

### Odbačeno

| Hipoteza iz zadatka | Presuda | Dokaz |
|---|---|---|
| **(b)** kriva adresa ili bit `RX_EYE_MEAS_EN`/`CFG`/brojača, širina, read-to-clear | **ODBAČENO** | DS t.2.59 str. 91–92: 0x14[0] „RX_EYE_MEAS_EN / EYE_MEAS_DONE” w/c, [3:1] unused, [15:4] CFG (t.2.46: 12 b); 0x15[5:0] `RX_MON_PH_OFFSET`; 0x16–0x1D brojači, 16 b. Isto je u CC r. 391–401 i u PP r. 488–498. Očitanje se slaže s upisom (0x0010/0x0011). Read-to-clear nije bitan jer i **prvo** čitanje daje 0. Jedina nesuglasica je širina: YS/NP/PP imaju 15 b od bita 1, DS 12 b od bita 4. Razlika su tri bita 0x14[3:1], a svih 8 vrijednosti isprobano je bez učinka (`probes.out` r. 26–29, `eye20.out` H3) |
| **(c)** toolchain ne prenosi `RX_EYE_MEAS_*` u bitstream | **ODBAČENO** | NP `pack_serdes.cc:94–96` postavlja sva tri parametra s pravom širinom. `bitstream.cc:474–477` piše **svaki** parametar SERDES ćelije kao riječ. PP ih mapira izravno u sliku regfilea. Nakon učitavanja 0x14 čita **0x8000** (`labeye.out` r. 7): to je `{12'h800,3'b0}` na bitu 1, dakle CFG 2048, točno kako je napisano u `.v`. Uz to, JTAG upis u regfile je runtime i ne ovisi o toolchainu. `EYE_EN=1` u bitstreamu je već isproban (TASK-5063), bez učinka |
| **(d)** EQA ili PRBS u krivom stanju | **ODBAČENO** | `probe_cfg.py`: `sel_comp_data` 0…7 × `sel_tap` 0/1 zamrznuto (16 kombinacija) te adaptacija s rutiranim monitorom i `LOCK_CFG` 12 i 14, sve s EN=1 i brojačima 0 (`probes.out` r. 20–24). Tvrdi PRBS checker zaključan (`RX_PRBS_SEL=2`, ERR 0–10, `probes.out` r. 12 i 26–28), PRBS-7 u TASK-5483. `RX_EN_EQA` 0 i 1. Kad bi stroj radio, prozor 1 bi završio za 32 ns, a 2048 za 33 µs (CC r. 1440–1447: 40·(N+1)/f). EN stoji ≥ 1,5 s, dakle ≥ 4,6 · 10⁴ × najdulji prozor. Nijedno podatkovno stanje ne objašnjava stroj koji nikad ne završi |
| `REGFILE_CLK_I=0` „nije uzrok jer ga i vendor ima” (`EYE_SCAN_ISTRAZIVANJE.md` §1.2) | **PREOCJENJENO** | Ta je presuda vrijedila dok se mislilo da je kvar specifičan za oko. TASK-5483 H7 je pokazao da ni `RX_CALIB_EN` ne briše, pa je takt regfilea opet glavni kandidat (H-A) |
| Testmode | ODBAČENO | `SERDES_TESTMODE=1` na obje ploče (`labeye.out` r. 4–5), a `tc_eyemeas` ga traži (CC r. 1743–1746) |

### (e) „Pola oka” — zaseban problem, bitan tek kad brojači prorade

Iz koda, bez mjerenja (brojači su 0, pa se ništa ne može potvrditi):

1. **Mjerilo faze je tvrdo kodirano.** `tc_eyemeas` crta s `codes_per_ui=64.0` (CC r. 1822). Funkcija
   `eye_calibrate_ui` (CC r. 1518–1545) postoji upravo zato što **nije poznato** pokriva li 64 kodova 1 ili 2 UI, a
   `eye_codes_per_ui` vraća 64 ili 32 (CC r. 124–152). Ako je ishodište faze (kod 0) rubni, a ne podatkovni uzorkivač,
   pretraga −32…+31 prikazuje rub u sredini, pa se na grafu vide dvije polovice oka.
   **Provjera:** gdje je zatvoreno područje kod praga 0, na kodu 0 ili na ±32 (`eye_diagnose` korak 4 već ispisuje
   `best phase`).
2. **Vertikalno je DAC na rubu.** Adaptirani `th_mon1/2 = +15` (`labeye.out` DIAG, „RAILED”) znači da je razina
   signala izvan raspona DAC-a ±15. Pretraga −15…+15 tada nikad ne dosegne gornji ili donji rub oka. Oko je „otvoreno
   bez vrha”, a uz pomak AFE-a jedna polovica izgleda odrezano. Patrickov `eye_diagnose` nudi lijek: smanjiti
   `RX_AFE_GAIN` ili `TX_AMP`.
3. **Nesuglasje o bitovima override-a (DS vs CC).**
   - DS t.2.44: `RX_EN_EQA_EXT_VALUE` bit0 = TH_MON1_OVR, bit1 = TH_MON2_OVR, bit2 = TAPW_OVR, bit3 = AFE_OFFSET_OVR.
   - CC r. 353–359 kaže da su [0] i [1] „unused”, [2] = TH_MON1+TAPW, a [3] = TH_MON2+AFE_OFFSET.

   Za nulu u brojačima to nije uzrok (H4, `EYE_SCAN_ISTRAZIVANJE.md`). Za ispravan vertikalni položaj kasnije jest.
   Provjera je u 0x07[9:5] (`RX_TH_MON`): prati li upisani `RX_TH_MON2`?

---

## 3. Što je novo u odnosu na `EYE_SCAN_ISTRAZIVANJE.md`

- H7 je **izmjeren** (TASK-5483) i dao je „W/C STUCK”. U starom dokumentu ima vjerojatnost „niska”, a stvarno je
  najjači trag. Zato je H1–H6 (podatkovni uzorak, način rada, monitor, EQA) **podređen** H-A: dokle god nijedan w/c
  strob ne radi, nijedan od njih ne može dati brojače ≠ 0.
- (c) je zatvoren izvorom: NP + PP + očitanje 0x8000.
- Patrickov `.ccf` sadrži pinove fabric regfile sučelja kojih u `.v` nema.
- IDCODE ne može dokazati istu reviziju (DS str. 142).
- Labeye s Patrickovim bitom (`labeye.out` r. 4–5) **nije bio ispravan link**: `RX_PRBS_ERR_CNT=32767`,
  `RX_EQA_LOCKED=0`. Za (d) to nije važno, jer i naš ispravan link (`probes.out`, ERR 0–10) daje isti zaglavljeni EN.

---

## 4. Pokusi za Jelenu (M2, najjeftiniji prvi; samo kad TASK-5527 pusti ploče)

Postava za sve pokuse: standardni par `m2_2g5.bit` / `gs_2g5.bit` s PRBS-om kao u `probes.out`
(gs `TX_PRBS_OVR=1 SEL=2` → m2 `RX_PRBS_OVR=1 SEL=2`), CDR zaključan.

### P1 — izvršavaju li se w/c strobovi uopće (2 min, bez novog bitstreama)

Ovaj pokus razdvaja „mrtav je samo mjerni stroj oka” od „mrtvi su svi w/c strobovi” (H-A).

```python
# m2 RX broji PRBS s gs TX-a
a = rd('RX_PRBS_ERR_CNT')                       # na m2
for _ in range(10): gs.wr_field('TX_PRBS_FORCE_ERR', 1)   # 0x40[9], w/c, na gs
b = rd('RX_PRBS_ERR_CNT'); f = gs.rd_field('TX_PRBS_FORCE_ERR')
m2.wr_field('RX_PRBS_CNT_RESET', 1)             # 0x2A[9], w/c (radi samo uz RX_PRBS_OVR=1, SOURCES_20260926.md r. 25)
c = rd('RX_PRBS_ERR_CNT'); r = m2.rd_field('RX_PRBS_CNT_RESET')
print(a, b, f, c, r)
```

Kako čitati rezultat:
- **b − a ≈ 10, f = 0, c = 0, r = 0:** w/c strobovi rade. H-A pada, a kvar je specifičan za mjerni stroj oka
  (prema H-B, i ide pitanje Patricku).
- **b = a, f = 1, r = 1:** ništa se ne izvršava i H-A je potvrđen. Slijedi P2.

### P2 — je li takt regfilea JTAG TCK u Run-Test/Idle (5 min, samo softver)

Naš `dirtyjtag_engine.py` nakon Update-DR daje točno **jedan** TCK u RTI (`_shift`, r. 220: `_tms_seq([1, 0])`) i
odmah kreće na sljedeću operaciju. Pokus:
- nakon `wr_field('RX_EYE_MEAS_EN', 1)`, s IR još na 0x25, dati `sd.s._tool._engine._clock(tms=0, tdi=0, n=100000)`,
  tj. 100 000 TCK u RTI, oko 17 ms na 6 MHz;
- zatim pročitati 0x14 i brojače;
- isto ponoviti za `RX_CALIB_EN`.

Ako EN padne na 0 ili brojači ≠ 0, lijek je softverski: u `serdes_jtag.py` dodati `runtest N` nakon w/c upisa. To bi
objasnilo i zašto Patricku radi: pyftdi/FTDI drugačije prolazi kroz RTI.

### P3 — slobodni takt na `REGFILE_CLK_I` (jedan bitstream po ploči)

U `gateware/ber/ber_top.v:122` treba promijeniti samo `.REGFILE_CLK_I(1'b0)` u slobodni takt:
- `clk_i` (25 MHz) preko postojećeg `CC_BUFG`;
- ili `rclk`.

`REGFILE_EN_I` i `REGFILE_WE_I` ostaju 0, pa fabric ne pristupa regfileu, a JTAG ima prednost (DS str. 89 i 149).
Novi parametar `REGCLK=1` po uzoru na `EYE_CFG`; s `REGCLK=0` gradnja mora ostati bajtno ista (kao `36f09752`).

Postupak:
1. JTAG čitanje i upis 0x14 i 0x08 moraju i dalje raditi. Ako ne rade, prekinuti pokus.
2. `probe_meas.py` (t5525), pa P1.

Kako čitati rezultat:
- **EN se briše i brojači ≠ 0:** uzrok je nađen. Vrijedi i za naše buduće dizajne, jer w/c resete (0x2B) i kalibraciju
  zato nikad nismo stvarno izvršili.
- **Ništa:** H-B (silicij). Šalje se pitanje iz §5 s rezultatima P1–P3.

### P4 — samo ako P3 pokaže da je takt potreban, a JTAG uz takt smeta

Mali fabric master regfilea, kakav Patrickov `.ccf` sugerira:
- piše 0x14 = `(N<<4)|1`;
- čeka `REGFILE_RDY_O` i 0x14[0] = 0;
- čita 0x16–0x1D u BRAM ili UART.

---

## 5. Precizno pitanje za Patricka (Goran šalje sam; engleski)

> Hi Patrick, thanks for serdes_lb.v (mail of 15.10.). On both of our GateMate A1 boards (IDCODE 0x20000001, which
> DS1001 p.142 says is a placeholder, so it doesn't tell us the silicon revision), your bitstream and your
> serdestool eye path give the same result. `RX_EYE_MEAS_EN` (0x14[0]) is never cleared (we waited 1.5 s at window
> 1…2048), and all eight counters 0x16–0x1D read 0. The `eye_diagnose` setup checks all pass: RX_EN_EQA=0 before
> RX_EQA_CONFIG, sel_comp_data=2, en_acc=0, EXT_VALUE=0b0111, and RX_TH_MON2 is writable.
>
> The failure is not specific to the eye unit. `RX_CALIB_EN` (0x02[0]) also stays at 1, and writing
> RX_RESET_OVR/RX_RESET in 0x2B does not reset the CDR. Plain r/w fields and the read-triggered capture at 0x07 work
> fine over JTAG. So it looks as if no write-and-clear strobe is ever executed.
>
> 1. Does the regfile need a running clock on `REGFILE_CLK_I` (DS p.89 "written with the rising edge of
>    CLK_REG_I") for w/c strobes, EYE_MEAS_DONE and the counter update, even when it is accessed only over JTAG?
>    Your serdes_lb.v ties `regfile_clk = 1'b0`, but your .ccf still pins `regfile_we`/`regfile_rstn`. Did the
>    setup where you saw the eye drive the regfile from the fabric with a clock?
> 2. If not: does the JTAG access need TCK cycles in Run-Test/Idle after the 0x25 update for a w/c bit to take
>    effect? We give one. How many does your pyftdi flow give?
> 3. Which silicon revision or date code is on your board, and is there an erratum for the eye measurement or for
>    the regfile w/c bits on early A1 parts?
> 4. Once it counts: is RX_MON_PH_OFFSET code 0 the data sampler phase or the edge sampler phase, and do 64 codes
>    span 1 UI or 2 UI? Your tc_eyemeas plots with codes_per_ui=64. Could that be the "half eye" you mentioned?

---

## 6. Popis prihvatnih stavki zadatka

Vidi izvještaj TASK-5529 u TaskManageru. Ovaj dokument je izvor za sve stavke.
