# A2 (CCGM1A2) na ULX5M-GS: 1 Gb/s Ethernet, `CC_IDDR` na die 1B i reset (kratki sažetak)

**30.09.2026.** Sažetak dokumenta `A2_CCGM1A2_TASK-5092.md` (§3–§5.10) i nacrta za upstream
`nextpnr_a2_repro/UPSTREAM_DRAFTS.md` (TASK-5092…5097). Detalji i dokazi nalaze se ondje.

## 1. Odgovor ukratko

- **Gotovog rješenja u alatima za 1 Gb/s na A2 još nema.** Za 1 Gb/s nedostaje ulazni DDR (`CC_IDDR`) na die 1B.
  Uzrok nije utvrđen i zakrpe nema.
- **Radi 100 Mb/s:** Linux 6.12, prijava nakon 263 s, ping, USB, DVI, 30 min 1800/1800 pod opterećenjem SDRAM-a.
  Bitstream: `/home/pi/FPGA/A2_CCGM1A2_Linux612_ETH100M_rxos_DVI_USB_selfrst_CFGRST_f1A_s5_T5094.bit`.
- **Reset nije pogreška alata**, nego pogreška postupka učitavanja. Riješen je resetom koji pokreće sam dizajn (`R!` → `RST_N`)
  i koji resetira **oba** die-a (§4).
- Tri pogreške alata su popravljene lokalno, a dvije su prijavljene bez zakrpe (§5). Za 1 Gb/s postoji konkretan
  put koji još nije isproban na ploči (§6).

## 2. Zašto 1 Gb/s ne radi (lanac uzroka)

1. RGMII kuglice (banka EB) na A2 su na **die 1B**, a CPU, SDRAM i UART na die 1A (`--vopt force_die=1A`).
2. `CC_IDDR` se pakira u IOSEL pada na die 1B i **ne vraća ništa** (§3).
3. Bez IDDR-a (`CC_IBUF` → fabric FF na 1A) prijelaz 1B → 1A traje **~12 ns u ciklusu od 8 ns**. Faza uzorkovanja
   ovisi o placementu, a nextpnr taj put ne provjerava jer takt `X` i njegovu kopiju `X$die1` smatra nepovezanima
   (problem A).
4. Na 100 Mb/s (40 ns po nibbleu) to se zaobilazi nadsempliranjem: `Rgmii100OSCore` uzorkuje RXC/RX_CTL/RXD taktom
   od 125 MHz (`--eth-100m --eth-rx-os`). Na 1 Gb/s taj trik ne prolazi.

TX i MDIO rade i na 1 Gb/s (`CC_ODDR` na 1B radi). Link je 1000M, a RXC mjeri 125 MHz. Ne radi samo RX.

## 3. `CC_IDDR` na die 1B: koji je točno problem

Minimalni dizajn `nextpnr_a2_repro/rxprobe/` broji bridove RX_CTL i RXD0 dok Pi šalje okvire:

| varijanta | RX_CTL / RXD0 bridovi |
|---|---|
| `CC_IDDR` u IOSEL-u die 1B (kao u SoC-u) | **0 / 0** (`C0000 F0000 D0000`, 4 puta) |
| `CC_IBUF` → fabric `CC_DFF` | 7 / 194 (rastu) |

- Pinovi dakle nose podatke. Ulazni registri IOSEL-a na 1B ne daju ništa: i Q0 i Q1 su konstantni.
- U istoj banci radi `CC_ODDR` (TXD/TX_CTL/TXC), radi običan ulaz (MDIO, RXC u `CC_BUFG`) i rade CPE FF-ovi na 1B.
- **Konfiguracija IOSEL-a jednaka je A1-ovoj** (`GPIO.IN1_FF 1`, `IN2_FF 1`, `INV_IN2_CLOCK 1`, `IN_CLOCK 00`).
  Razlikuju se samo ulazni muxevi IOES (A1: `IOES1.SB_IN_06`, `IOES2.SB_IN_07`; A2 1B: `IOES1.SB_IN_08`, `IOES1.SB_IN_11`).
- **Sumnja:** takt ulaznih registara ili povratni put Q0/Q1 u IOSEL-u die 1B chipdb (prjpeppercorn) modelira
  drukčije nego što je u siliciju. To nije dokazano.
- Nepregledan trag (usporedba ključeva konfiguracije rxprobe A1 i A2, 30.09.): A1 postavlja `LES2.PINX_SEL` i `LES2.SB_Y3_SEL2`,
  a A2 ih ne postavlja ni na jednom die-u. Nije provjereno odnosi li se to na IDDR. To je prvo što treba provjeriti pri
  usporedbi bit po bit.
- Vendorski p_r 2025.11 (`-A 2`) ruši se prije pisanja bitstreama, pa referentnog A2 bitstreama za usporedbu nema.

## 4. Reset: koji je točno problem

**Simptom:** prvi load nakon power-cyclea uvijek radi. Load **drukčijeg** layouta preko A2 dizajna koji radi nije
uspio u 4 od 5 pokušaja: 1B FF-ovi su bili nestabilni ili je čip ostao tih. Loader pritom javlja `Done`, a JTAG je ispravan
(`--detect` OK). Iz toga je nastao pogrešan zaključak „CPE FF na 1B ne rade” (problem D).

**Uzrok (sve četiri točke zajedno):**

1. `gmpack` najprije do kraja konfigurira die 1B (preko `CMD_PATH`, kroz 1A) **dok 1A još izvodi stari dizajn**.
   `CFGRST` za 1A dolazi tek nakon 1B.
2. `CMD_CFGRST` ne vraća die koji je u korisničkom načinu u stanje nakon uključenja. Isprobano je i lokalno
   `gmpack --reset-all-first` (CFGRST oba die-a prije svega ostalog): svježi load radi, a reload i dalje ne radi.
3. `openFPGALoader -r` na DirtyJTAG-u samo spusti i digne SRST, bez čekanja (`colognechip.cpp` 88–105).
   **SRST na `gs` nije spojen na `RST_N`.**
4. DS1001 §3.4 nema JTAG instrukcije koja resetira konfiguraciju.

Na A1 se problem ne vidi jer jednodijelni tok nema prosljeđivanja 1A → 1B koje bi ostalo napola konfigurirano.

**Rješenje (provjereno na ploči):** reset koji pokreće sam dizajn, `selfrst.v`. Nakon bajtova `R!` na UART-u
dizajn povuče `IO_SB_B8` (kuglica N15 = mreža `RST_N`, open-drain) nisko, a to **resetira oba die-a**. Tvoja sumnja je
bila točna: reset mora obuhvatiti obje jezgre. Ploča je izdržala S1 i još 10 loadova bez power-cyclea.

- Puls sam sebe ograničava na ~0,3 ms: čip u resetu prebaci IO u stanje visoke impedancije, a R111/C138 vrate liniju gore.
- Postupak: `~/t5095/sr_reset.sh 2` prije **svakog** loada. Svaki A2 dizajn mora sadržavati selfrst
  (`tools/a2_soc_sr_build.sh` ga ugrađuje).
- Ograničenje: radi samo ako dizajn koji se trenutačno izvodi ima selfrst. Trajno rješenje je sklopovsko: GPIO
  DirtyJTAG-a (ili `PI_GLOBAL_EN` / J2.99 na nosivoj ploči) na `RST_N`, a zatim u openFPGALoaderu
  `CologneChip::reset()` koji tu liniju drži nisko nekoliko ms prije konfiguracije.

## 5. Popravci alata (stanje)

Lokalni toolchain: `~/app/raid/tools/nextpnr-a2fix/` (`build.sh`, `README.md`, `patches/`), nextpnr `ad8527f8` +
grana `t5092-a2`, gmpack `b1eb52f`.

| # | Problem | Stanje | Zakrpa / zaobilaženje |
|---|---|---|---|
| B | clock router koristi CPE bridgeove → router2 „Failed to route arc” na 1B | **popravljeno**; A1 izlaz je bajt-identičan | `patches/0001-gatemate-clock-router-must-not-use-CPE-bridges.patch` |
| C | D2D veze postoje tek od X29; bbox i procjena kašnjenja to nisu znali | **popravljeno**; router2 548 s → 13,5 s | `patches/0002-gatemate-die-crossing-only-where-die-to-die-connecti.patch` |
| E | `placer_heap.cc:2180`: `int` overflow od 46 341 ćelije → placer pada (12/12) | zaobiđeno | `--placer-heap-cell-placement-timeout 0`; ispravak u jednom retku niže (nije u `patches/`) |
| A | `X` i `X$die1` su nepovezani za timing → prijelazi među die-ovima se ne provjeravaju | **nema zakrpe** (common kernel) | nacrt issuea §1; ne vjerovati „PASS” na putovima među die-ovima |
| IDDR | `CC_IDDR` na 1B ne vraća podatke | **nema zakrpe** | nacrt issuea §7; zaobilaženje: fabric FF |
| — | `gm_cfgrst_check.py` je A2 bitstreamove lažno označavao kao `NO_CFGRST` | popravljeno | 5/5 testova |

Ispravak za E (nije primijenjen, dosad se koristila zastavica):

```cpp
// common/place/placer_heap.cc:2180
int64_t n = ctx->cells.size();
cell_placement_timeout = int(std::min<int64_t>(INT_MAX, std::max<int64_t>(10000, n * n / timeout_divisor)));
```

## 6. Put do 1 Gb/s (prijedlog redoslijeda)

1. **RX DDR u fabricu NA die 1B** (bez novog popravka alata): `CC_IBUF` → dva `CC_DFF` (posedge/negedge) **na
   die 1B**, s taktom `grx_clk$die1`, pa CDC (async FIFO) prema 1A. Tako se zaobilaze i neispravan `CC_IDDR` i
   prijelaz od 12 ns u 8 ns. Uzorkovanje ostaje unutar jedne domene na jednom die-u, pa ga nextpnr provjerava.
   Alati postoje: `tools/a2_iddr_to_fabric.py` + `tools/a2_die_split.py --from-io`.
   Raniji split buildovi (s4/s5) koristili su IDDR i učitani su bez resetiranja, pa **nisu mjerodavni**. Ovo još nije
   isprobano na ploči. Rizik je vremenski usklad pad → CPE na 1B unutar poluperiode od 4 ns.
2. **Popravak `CC_IDDR` na 1B:** usporedba IOSEL/IOES konfiguracije A1 i A2 bit po bit (počevši od `LES2.*`), zatim
   issue §7 upstreamu s pitanjem je li ulazni DDR na 1B igdje ispitan.
3. **Problem A:** zakrpa u `timing.cc` (relacija takta kroz GLBOUT) da nextpnr stvarno provjerava prijelaze među die-ovima.

Nacrti za upstream (§1 A, §2 B, §3 C, §4 D/reset, §6 E, §7 IDDR) i lokalni commiti u `ulx5m-litex-ai`
**nisu pushani** i čekaju tvoju provjeru.
