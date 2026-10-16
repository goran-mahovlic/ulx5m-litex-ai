# Revizija inicijalizacije SerDes bitstreama prije upisa u SPI flash (TASK-5532, 16.10.2026)

**Recenzentica:** Kosjenka (neovisno o autorici TASK-5531). **Zahtjev:** Goran 16.10. 09:12, „neka se dodatno i revidira kod da ne bi u
njemu bilo grešaka koje bi dovodile da se kod inicijalizacije događaju greške".
**Predmet:** bitovi koje TASK-5531 namjerava upisati u flash — `gs_2g5_auto.bit` (sha256 `99d80788…`) i `m2_2g5_auto.bit`
(`3f4857df…`) na Piju u `/home/pi/fpga/`, izvor `gateware/ber/ber_top.v`, `ber_link.v` (m2), `ber_link_gs.v` (gs),
`cc_serdes_params.vh`, `build_ber.sh`, stanje repoa `2b9afc4`.
**Kod nisam mijenjala.** Ispravke idu Jeleni u TASK-5531 (uputa). Na ploče nisam ništa učitavala; s Pija sam samo pročitala sha256.

---

## 0. Verdikt

### ✅ SMIJE u flash — uz četiri preduvjeta (P1–P4, §8)

- U kodu inicijalizacije nema greške koja bi u ispitanim uvjetima srušila podizanje linka. Nema 🔴 nalaza u kodu.
- Bitovi su **deterministični**: moj neovisni rebuild daje bajtno iste datoteke kao one na Piju. Od izmjerenog para
  (`36f09752` / `b1b98a5d`) razlikuju se u **točno jednom retku** od 142 024 (`TX_AMP 11111 → 01100`).
  - Smještaj i routing su isti kao kod bitova koji su prošli 21 + 6 učitavanja.
  - To je bitno jer nextpnr ne mjeri vrijeme na putovima fabric↔SerDes (zamka 2 u SERDES_KNOWLEDGE).
- **SET_ACC sekvencera nema.** TASK-5531 ga nije izgradio (CKI = 0), pa ga nisam imala što revidirati.
  - Odluku sam provjerila na sirovim podacima lab40: na 24/24 čitanja `RX_CDR_LOCKED=1`, `RX_EQA_LOCKED=1` i
    `FREQ_ACC_VAL=0`, a PEER 200/200 na 6/6 učitavanja.
  - Odluka je ispravna (§3).
- Ono što **nije dokazano**, nego se prvi put ispituje upisom u flash:
  - hladno paljenje,
  - istodobni boot obje ploče,
  - ponašanje kad nestane refclk.
- U kodu ne postoji ponovna inicijalizacija (🟡 N1). Ako se link nakon reseta ne digne, lijek je novi reset ili SRAM `-r`.
  Ništa se ne može trajno pokvariti: pri boot-u CRC je u načinu `check`, a stari bitovi ostaju na Piju.

**Ne preporučujem** da se prije flasha mijenja `ber_top.v`. Svaka izmjena logike mijenja smještaj, pa bi se izgubila
kvalifikacija na 27 učitavanja (lutrija TX_NEG/seeda, zamka 2). Popravci 🟡 idu u zasebni build s ponovnom kvalifikacijom
na ≥ 3 učitavanja (§9).

| Težina | Broj | Nalazi |
|---|---|---|
| 🔴 blokira flash | 0 | — |
| 🟡 popraviti / pratiti | 6 | N1 nema ponovne inicijalizacije ni retryja · N2 boot obje ploče istodobno i nakon hladnog paljenja nije ispitan · N3 aux kanal bez zaštite izvršava naredbe · N4 `loss_cnt` 5 bita se preljeva · N5 BER se broji samo dok je link sinkroniziran · N6 zaključavanje PRBS-a na nulu daje lažni PASS |
| 🟢 u redu / sitno | 9 | redoslijed reseta, CDC, init FF-ova, CC_SERDES polja, build vrata, timing, determinizam, flash format, UART nakon reseta |

---

## 1. Redoslijed reseta i inicijalizacije (stavka 1)

Stvarni tok u kodu: konfiguracija završi → FF-ovi na svojim init vrijednostima → POR brojač na `clk_i` (25 MHz) drži
`rst = 1` 511 taktova (20,4 µs) → `rst` pada **istodobno** na `PLL_RESET_I`, `TX_RESET_I` i `RX_RESET_I`
(`ber_top.v:43-44`, `:107`). Ostali reseti SerDesa vezani su na 0 (`:108-109`), a sekvenciranje PLL → TX → RX → CDR
radi unutarnji reset-FSM SerDesa (`*_RESET_TIME 3`, `RX_RESET_TIMER_PRESC 4`, `RX_WAIT_CDR_LOCK 0`,
`SERDES_AUTO_INIT 0`, `cc_serdes_params.vh:3-10,200-201`). Fabric **ne čeka ništa**: PRBS checker se sinkronizira sam
iz primljenih podataka (16 dobrih riječi u nizu, `ber_link.v:142-147`).

| Pitanje iz zadatka | Nalaz |
|---|---|
| Polaritet reseta | 🟢 `rst` je aktivan u 1, kao u Cologne Chipovu `serdes_lb.v` i u svim dosadašnjim bitovima. Izvor je izravno registar (`rst_cnt`), pa nema glitcha. |
| Sinkronizator reseta | 🟢 POR je generiran u `clk_i` domeni iz FF-ova s init 0, a SerDes ga uzorkuje sam. Domene `tclk`/`rclk` nemaju reset nego init vrijednosti iz bitstreama (provjereno u §6, init je stigao u bit). |
| Čeka li se PLL lock / TX_RESET_DONE / RX_RESET_DONE? | **Ne.** `TX_RESET_DONE_O`/`RX_RESET_DONE_O` spojeni su na žice `txrd`/`rxrd` koje se nigdje ne koriste (`ber_top.v:110`). Primitiv nema izlaz za PLL lock ni CDR lock, a regfile port je ugašen (`REGFILE_CLK_I=0`, `:122-123`). Fabric zato **ne može** vidjeti `PLL_LOCKED`/`RX_CDR_LOCKED` → 🟡 N1. |
| CDC refclk/fabric/rx/tx | 🟢 Jednobitni prijelazi su toggle + 3 FF (`:133-134`, `:172`). Snimke `us_*`/`ut_*` čitaju se u `clk_i` domeni 200 taktova (8 µs) nakon zahtjeva, a sinkronizacija traje oko 0,1 µs. `snap_tx` ima 31 takt rezerve. `cmd_out` (8 bita) prelazi kroz 2 FF i filtar jednakosti (`:173`); mijenja se samo na naredbu s UART-a, pa je u redu. Kad `rclk` ne radi (nema linka), snimka može biti napola stara. To je kozmetika: izvještaj dok link ne radi ionako nije mjerenje. |
| Glitch/metastabilnost pri stjecanju CDR-a | 🟢/🟡 `rclk` je oporavljeni takt kroz `CC_BUFG`. Dok CDR stječe lock, takt može imati kratke impulse. Stanje u `rclk` domeni se samo oporavlja (sync, one-hot `a_we` se računa svaki takt). Brojači mogu dobiti smeće, a briše ih `z`/`Z` ili ih filtrira baseline u `ber_long.py`. Jedino trajno stanje je TX LFSR u `tclk` domeni: ako bi ga glitch PLL takta ikad stavio na 0, ostaje 0 zauvijek (N6). |
| PLL lock padne pa se vrati | 🟡 **Nema ponovne inicijalizacije** (N1). Hoće li unutarnji ADPLL/BISC i reset-FSM sami ponovno uhvatiti lock, nije dokumentirano (DS1001) ni izmjereno. Gubitak **podataka** od partnera je pokriven: u svakom ciklusu lab39/lab40 m2 se ponovno učitava dok gs radi, i obrnuto, a checker se ponovno sinkronizira (+ testbench „cable pulled → synced again"). Gubitak **refclka** nije ispitan. Refclk dolazi s GS X2 (OE preko R143 100 k na VDD_CLK, slobodno titra), pa nestaje samo ako GS ostane bez napajanja. |

---

## 2. SET_ACC sekvencer (stavka 2)

**U bitovima ga nema** (`git show 2b9afc4`, `e40c197`: „no ber_top.v change, no SET_ACC sequencer"). Pitanja iz zadatka o
trajanju pulsa, čekanju `RX_CDR_LOCKED`, retryju i zaglavljenom FSM-u zato se ne odnose na isporučeni kod. Provjerila sam
**odluku** da ga ne treba:

| Provjera | Rezultat |
|---|---|
| `RX_CDR_CKI` u oba `.txt` | `00000000` (integrator frekvencije isključen) |
| `RX_CDR_SET_ACC_CONFIG` / `RX_CDR_FREQ_ACC` u bitu | `00` / `0` = vrijednost kojom puls lab39 i završava |
| Zamka §4C (`LOCAL_REFCLK_M2.md`) | viđena **samo** na cki1/cki2 bitovima (integrator na rubu raspona); s CKI = 0 integrator ne radi, pa nema što zaglaviti |
| lab40 sirovi `lab40.out` (6 svježih `-r`, skripta `lab40.sh` nema nijedan `set`/`recal`) | S0 odmah nakon učitavanja: `RX_CDR_LOCKED=1 RX_EQA_LOCKED=1 SET_ACC=0 FREQ_ACC_VAL=0` na **24/24** čitanja; `polls=1` na 6/6 (link je gore već kod prve provjere); PEER 200/200 oba smjera na 6/6 |

- Napomena uz VERIFY §19.2: „t_link 31,8–39,3 s" nije vrijeme podizanja linka. To je trajanje JTAG upita (`polls=1`
  znači da je link bio gore kod prvog pogleda). Stvarno vrijeme je ispod toga. 🟢, ispraviti formulaciju.
- **Ako se sekvencer ikad bude gradio** (npr. za M2 s vlastitim X2 i CKI ≠ 0), treba mu:
  - regfile port s pravim taktom (danas je `REGFILE_CLK_I=0`, vidi `EYE_MEAS_UZROK` H-A);
  - kriterij zaključavanja `synced` iz fabric checkera, a ne `RX_CDR_LOCKED`, jer taj „laže" (zamka 4);
  - ograničen broj pokušaja s izlazom iz svakog stanja.

---

## 3. Parametri CC_SERDES (stavka 3)

- **TX_AMP 12 je stvarno u bitu.** Usporedba sekcije `.serdes` polje po polje (215 polja) između amp12 i kontrolnog bita:
  - gs `{'TX_AMP': ('11111', '01100')}`, m2 identično;
  - nijedno drugo polje se ne mijenja;
  - `diff` cijelog `.txt` daje 2 retka (`<`/`>`) od 142 024.
- `OV_*` mapiranje (`ber_top.v:59-73`):
  - integer parametar puni lokalni parametar fiksne širine; `OV_TX_AMP=12` → `5'h0C` ✓;
  - **nema provjere raspona**: `OV_TX_AMP=40` bi se tiho skratio na 8, a `OV_CDR_TRANS_TH=200` na `7'h48`;
  - 🟢 prijedlog: provjera u `build_ber.sh` ili `initial if (...) $error` u generate bloku;
  - ne utječe na ove bitove.
- `CDR_TRANS_TH`:
  - lokalni parametar je 9-bitan, polje primitiva 7-bitno (`:66`, `cc_serdes_params.vh:32`);
  - PROFILE 1 daje `9'h08` → `.txt` `RX_CDR_TRANS_TH 0001000` = 8 ✓;
  - PROFILE 0 (`9'h80`) bi dao **0**, što je poznata zamka 8 i ne tiče se ovih bitova;
  - 🟢 prijedlog: lokalni parametar suziti na `[6:0]` da se zamka ne ponovi.
- P1/P2/P3 grananje:
  - za PROFILE 1 vrijedi P1 = 1, P2 = P3 = 0;
  - vrijednosti u `.txt` odgovaraju grani P1: CKP `0x3E`, AFE PEAK 24 / GAIN 0, SEL_PRE/POST 5, BR_PRE/POST 12,
    DC_ENABLE 43, EQA on, LOCK_CFG `0xD5`;
  - neispravan PROFILE (> 3) tiho pada na postavke PROFILE 0, a `VER` ga i dalje prijavljuje (🟢, prijedlog provjere).
- `PLL_MAIN_DIVSEL 011011` (N1 1, N2 5, N3 5), `PLL_OUT_DIVSEL 01`, `PLL_REF_SEL lvds`, `RX_POLARITY_I=1` (port; registar
  čita 0, što je zamka 5, očekivano). `RX_WAIT_CDR_LOCK 0` je vrijednost iz pu-cc („turn off if loopback enabled"). PCS se
  pušta prije locka CDR-a, ali `RX_BUF_ERR` je na svim dosadašnjim čitanjima 0 (VERIFY §5), a comma aligner se sam
  poravnava. 🟢, ostaviti.

---

## 4. PRBS/BER logika (stavka 4)

Regresija: postojeći `sim/tb_ber_link.v` prolazi na **oba** checkera (11 PASS, `fails=0` svaki). Uz to sam napisala vlastiti
testbench rubnih slučajeva (`gateware/ber/sim/tb_review_init.v`; samo test, dizajn netaknut). Sva tri nalaza ispod su **potvrđena simulacijom** na
`ber_link.v` i `ber_link_gs.v`.

- 🟢 **Init LFSR-a:**
  - TX LFSR počinje od `40'h00DEADBEEF` (`ber_link.v:32`);
  - u netlisti je 24 FF-ova s INIT=1 točno na bitovima LFSR-a (na obje ploče);
  - nextpnr te bitove prenosi u `FF_INIT 11`, a FF-ovi s različitim init ne mogu dijeliti CPE (`get_dff_config`);
  - polinom x⁴⁰+x³⁸+x²¹+x¹⁹+1 je maksimalne duljine, a LFSR se nikad ne resetira ni ne dira injekcijom (inject XOR-a samo izlaz);
  - simulacija T0: nakon starta `lfsr ≠ 0`.
- 🟡 **N6 — zaključavanje na nulu daje lažni PASS:**
  - checker se dok nije sinkroniziran sam zasijava iz primljenog payloada (`ber_link.v:143`);
  - ako payload bude 0, sinkronizira se na `expv = 0` i broji 0 grešaka (T1: `synced=1 expv=0000000000`);
  - TX LFSR u radu ne može postati 0, osim kroz SEU ili glitch `tclk` dok PLL hvata lock, pa je vjerojatnost zanemariva;
  - ali posljedica bi bila tiha: BER = 0 uz mrtvi PRBS;
  - prijedlog (sljedeći build): u `ber_tx` `if (lfsr == 0) lfsr <= SEED`, a u `ber_rx` ne prihvaćati sinkronizaciju na `pay == 0`.
- 🟡 **N4 — `loss_cnt` je 5-bitni i tiho se preljeva** (`ber_link.v:64,154`):
  - T2: 40 gubitaka sinkronizacije čita se kao `loss_cnt=8`;
  - `ber_long.py` „restarts" broji vraćanje brojača riječi (ponovno učitavanje ili brisanje), **ne** gubitke sinkronizacije;
  - zato „0 restarta" ne znači „0 gubitaka sinkronizacije";
  - prijedlog: proširiti na 16 bita (u izvještaju je još jedno slobodno polje, `flg[5]=0`) ili gledati udio sinkroniziranog vremena (N5).
- 🟡 **N5 — BER se broji samo dok je link sinkroniziran** (`ber_link.v:148-157`):
  - dok je `synced=0`, ne broje se ni riječi ni greške;
  - nakon 64 loše riječi u nizu checker izlazi iz sinkronizacije, pa rafal grešaka ulazi u BER samo s prvih ~64 riječi;
  - za kratko mjerenje nakon flash boot-a treba uz BER prijaviti i **udio sinkroniziranog vremena**
    (Δwords/Δtcnt, oba su već u izvještaju) i Δloss.
- 🟡 **N3 — aux kanal bez zaštite izvršava naredbe** (`ber_link.v:120,160`; `ber_top.v:144-153`):
  - riječ se prihvaća za okvir ako PRBS payload odgovara;
  - **aux bajt (byte7) i 8b10b greške nisu u uvjetu** (`match` ne uključuje `wce`);
  - T3: pokvaren aux bajt uz ispravan PRBS prihvaćen je u 7 okvira (`peer_frame[7:0]=01`);
  - kad se pokvari bajt naredbe, `pcmd != pcmd_prev` izvrši naredbu: niski nibble 1 briše brojače partnera,
    nibble 2 ubacuje grešku na partnerov TX;
  - isto vrijedi za povratak na ispravnu vrijednost (već poznato, komentar u `ber_long.py`);
  - ne utječe na podizanje linka, ali utječe na vjerodostojnost brojeva;
  - prijedlog: u `match` za aux uključiti `!wce`, a naredbu izvršiti tek kad je ista u 2 uzastopna okvira.
- 🟢 **Ostali brojači:**
  - `word_cnt` je 48-bitni;
  - `err_words`/`err_bits`/`code_err`/`pframes` su 32-bitni; preljev bi tražio oko 98 % loših riječi uz očuvanu sinkronizaciju, što je nerealno;
  - `tcnt`/`rcnt`/`t25` se preljevaju svakih 137–171 s, ali parseri rade s maskom `& 0xFFFFFFFF` (`ber_parse.py:40-41`, `ber_long.py:63`).
- 🟢 **UART nakon reseta:**
  - `idx = LINE_LEN`, pa ne ide smeće prije prve snimke;
  - prvi zahtjev za snimku je u prvom taktu (`sec=0`); ako `rclk` još ne radi, rub se uhvati kad krene, pa je prvi redak star (kozmetika);
  - `DIV=217` → 115 207 Bd (+0,006 %);
  - `uart_rx` ima PULLUP, pa nespojena linija ne šalje naredbe.

---

## 5. Build (stavka 5)

| Provjera | Rezultat |
|---|---|
| `gmpack --reset` + vrata | `build_ber.sh:276-277`: `gmpack --reset` pa `gm_cfgrst_check.py` (exit 1 prekida zbog `set -e`). Oba bita: `CFGRST`. |
| Hold | `hold_viol=0` na oba (moj rebuild i Jelenin log) |
| Fmax nakon routinga | gs: tclk 85,77 / rclk 50,92 / clk_i 34,85 MHz; m2: 79,65 / 77,46 / 123,03 MHz. Potrebno: 31,25 MHz (riječ na 2,5 G) i 25 MHz (`clk_i`). „FAIL at 40 MHz" za gs `clk_i` je očekivan, cilj FREQ=40 je samo za SerDes takte. 🟢 |
| SerDes portovi | nisu vremenski analizirani (TMG_IGNORE). Zato je ključan determinizam: amp12 ima **isti** smještaj kao izmjereni par, razlika je samo u konfiguracijskom retku `TX_AMP`. 🟢 |
| Determinizam | **neovisni rebuild** (moja kopija izvora, `oss-cad-suite-20260923`, isti seedovi 7/2): gs `99d80788ef4d…`, m2 `3f4857df4ef1…` = bajtno isto kao `build/` i kao Pi `*_auto.bit`. Kontrolni rebuild starog para (Jelena) također je bajtno isti. 🟢 |

---

## 6. Put iz flasha (stavka 6)

- 🟢 **Format bitstreama** (izvor gmpack v1.13-6, `libgm/src/Bitstream.cpp:81-85,899-928`):
  - bez `--spimode` nema `CMD_CFGMODE`, pa vrijedi zadani način **single SPI** (READ 0x03), koji svaki flash podržava,
    uključujući AT25QL321 na 1,8 V;
  - CRC je u načinu `check`: djelomično ili pokvareno upisana slika **ne** ide u pogon, nego FPGA ostaje nekonfigurirana i
    oporavlja se SRAM-om preko JTAG-a, pa je ploča i dalje oporavljiva;
  - `CMD_CFGRST` na početku je za hladni boot suvišan (latchevi su već 0), ali je bezopasan i ostaje kao zaštita za `-r`.
- **Razlike flash boot-a prema SRAM `-r`** koje kod ne pokriva i koje nisu izmjerene (🟡 N2):
  1. *Hladni analogni start.* PLL (BISC, SCAP auto-cal), RX/TX kalibracija terminacije i EQA kreću od hladnog stanja.
     Kod `-r` je SerDes prije toga radio. Za razliku od JTAG upisa postavki, ove kalibracije se izvode iz reseta i u
     bitovima (zamka 1), pa nema razloga za kvar. Ipak, izmjereno nije.
  2. *Redoslijed.* Svi dosadašnji podaci imaju redoslijed „m2 pa gs" (SERDES_KNOWLEDGE zamka 12). Kod reseta i paljenja
     redoslijed nije pod kontrolom. Slučaj „partner kasni" je ispitan za RX na m2 (gs se učita nekoliko sekundi kasnije).
     Istodobni start i slučaj „gs prvi" nisu ispitani.
  3. *Refclk pri paljenju.* POR drži reset samo 20,4 µs nakon konfiguracije. Si511 se pokreće u nekoliko ms, a
     konfiguracija iz SPI flasha (277 KB gs / 94 KB m2, single SPI) traje dulje od toga. Refclk bi zato trebao biti stabilan,
     ali bez provjere u fabricu (N1). M2 dobiva refclk s GS-a kroz lanac (CM4 IO → PCIe → M.2), pa ako GS kasni s
     napajanjem, M2-ov PLL kreće bez refclka.
  4. *Napajanje.* Pi javlja `Under-voltage` pri učitavanjima (zamka 16), a ploče se napajaju preko Pi USB-a (`uhubctl`).
     Istodobni boot obje ploče je najveći strujni udar.
  5. *M2 strapping.* GS se već dizao iz flasha (povijest `-f` pa `uhubctl`). Za **M2** nisam našla zapis da se ikad dizala
     iz flasha (CFG_MODE strap) → preduvjet P3.

---

## 7. Popis nalaza 🟡 (datoteka:redak, scenarij, prijedlog)

| # | Gdje | Scenarij kvara | Prijedlog (sljedeći build, NE prije ovog flasha) |
|---|---|---|---|
| N1 | `ber_top.v:43-44,110,122-123` | Ako PLL ne uhvati lock (refclk kasni ili trepne) ili CDR ostane bez locka, nitko to ne vidi i nitko ne pokuša ponovno. Iz flasha, bez JTAG-a, link ostaje dolje do sljedećeg reseta. | Fabric watchdog: `!synced` dulje od ~5 s → ponovni puls `rst` (PLL/TX/RX), brojač pokušaja u izvještaju (`flg[5]`, slobodan). POR produljiti na ~2²² taktova (~170 ms). `txrd`/`rxrd`/`rxbe` staviti u izvještaj radi dijagnostike bez JTAG-a. |
| N2 | (proces, ne redak) | Hladni ili istodobni boot ni jednom nije izmjeren; svi podaci su SRAM `-r`, „m2 pa gs". | Prvo mjerenje nakon Goranova reseta je ujedno test ovog scenarija. Zabilježiti točno koji reset je bio (gumb ili napajanje, jedna ploča ili obje). |
| N3 | `ber_link.v:120,160`; `ber_link_gs.v:142`; `ber_top.v:144-153` | Bitna greška u aux bajtu uz ispravan PRBS izvrši naredbu partneru (brisanje brojača ili injekcija). | `!wce` u uvjet za aux; naredba vrijedi tek kad je ista u 2 okvira. |
| N4 | `ber_link.v:64,154` (`_gs:66,136`) | Više od 31 gubitka sinkronizacije čita se kao mali broj. | `loss_cnt` 16 bita. |
| N5 | `ber_link.v:148-157` | Vrijeme izvan sinkronizacije ne ulazi u BER; rafali su podcijenjeni. | U izvještaju mjerenja navesti udio sinkroniziranog vremena i Δloss. |
| N6 | `ber_link.v:32,143` | TX LFSR = 0 (SEU ili glitch) daje tihi BER 0. | Zaštita od nule u TX-u i RX-u. |

🟢 sitno (bez utjecaja na ove bitove): nema provjere raspona `OV_*` i `PROFILE`; `A_CDR_TRANS_TH` je 9-bitan za 7-bitno
polje; formulacija „t_link" u VERIFY §19.2.

---

## 8. Preduvjeti za upis u flash (za TASK-5531)

- **P1 — slika za povratak.** Read ID ne radi, pa sigurnosna kopija trenutnog sadržaja flasha nije moguća.
  - Prije upisa utvrditi i spremiti koji je bitstream zadnji upisan na GS (vjerojatno LiteX/Ethernet build, povijest na Piju).
  - Zabilježiti ga u README kao sliku za povratak.
  - Prvo riješiti pristup flashu (Read ID); bez ispravnog čitanja nema ni provjere upisa.
- **P2 — provjera nakon upisa.** Read-back ili verify alata. Ako to nije moguće, CRC `check` pri boot-u ostaje jedina
  zaštita (nekonfiguriran FPGA = vidljiv kvar, oporavak SRAM-om).
- **P3 — M2 boot iz flasha.** Prije upisa provjeriti na shemi ili u povijesti da je CFG_MODE na M2 postavljen na SPI.
  Inače upis na M2 nema učinka.
- **P4 — mjerenje nakon reseta, bez JTAG pisanja:**
  - PEER 200/200 oba smjera;
  - BER oba smjera 300 s;
  - **uz Δloss i udio sinkroniziranog vremena** (N4/N5);
  - zapisati vrstu reseta (N2).
  - Očekivanje je „slučajno učitavanje": lošiji smjer 10⁻⁹…10⁻⁸. Brojevi 8,3·10⁻¹⁰ / 4,2·10⁻¹⁰ pripadaju odabranom
    lab39 soaku i nisu realno očekivanje (VERIFY §19.2).
  - Ako link ne dođe gore: drugi reset, pa SRAM `-r` istih bitova kao kontrola (razdvaja „flash put" od „init").

---

## 9. Što NE raditi prije ovog flasha

- Ne mijenjati `ber_top.v`/`ber_link*.v` zbog N1–N6. Novi build znači novi smještaj, dakle novu lutriju na SerDes putovima
  koji nisu vremenski analizirani, i nova kvalifikacija mora imati ≥ 3 učitavanja.
- Ne graditi SET_ACC sekvencer za CKI = 0 par (§2).

---

## 10. Dokazi (ponovljivo)

```
# neovisni rebuild (kopija izvora u /home/klaudio/app/tmp/zadaci/TASK-5532_neovisna-revizija-koda/rb/)
LINK=ber_link_gs.v FREQ=40 ./build_ber.sh gs 2g5p1_txneg_amp12 7 N1 1 N2 5 N3 5 OUTDIV 2 PROFILE 1 TX_NEG 1 OV_TX_AMP 12
FREQ=40 ./build_ber.sh m2 2g5p1_txneg_amp12 2 N1 1 N2 5 N3 5 OUTDIV 2 PROFILE 1 TX_NEG 1 OV_TX_AMP 12
→ build/gs_2g5p1_txneg_amp12_s7.bit CFGRST hold_viol=0  'u.tclk': 85.77 MHz 'u.rclk': 50.92 MHz
→ build/m2_2g5p1_txneg_amp12_s2.bit CFGRST hold_viol=0  'u.clk_i': 123.03 MHz 'u.tclk': 79.65 MHz 'u.rclk': 77.46 MHz
sha256: 99d80788ef4ddce5…  (gs)   3f4857df4ef1a2b1…  (m2)   = Pi /home/pi/fpga/{gs,m2}_2g5_auto.bit

# .serdes polje po polje (215 polja) amp12 vs kontrolni bit
gs {'TX_AMP': ('11111', '01100')}   m2 {'TX_AMP': ('11111', '01100')}

# iverilog: postojeci testbench na oba checkera
ber_link.v RESULT fails=0 (11 PASS)    ber_link_gs.v RESULT fails=0 (11 PASS)
# vlastiti rubni testbench (sim/tb_review_init.v), oba checkera isto:
T0 init: tx lfsr=f4b96052bd (!=0: 1)
T2 40 prekida sinkronizacije -> loss_cnt=8
T1 payload=0: synced=1 expv=0000000000
T3 aux bajt pokvaren: prihvaceno okvira=7, peer_frame[7:0]=01

# lab40 sirovi podaci (docs/data_20261016/t5531/lab40.out)
24x RX_CDR_LOCKED=1, 24x RX_EQA_LOCKED=1, 24x FREQ_ACC_VAL=0, 24x SET_ACC_CONFIG=0; polls=1 na 6/6; PEER 200/200 na 6/6
```
