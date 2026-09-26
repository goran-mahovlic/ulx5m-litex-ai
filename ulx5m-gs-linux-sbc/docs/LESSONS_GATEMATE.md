# GateMate (CCGM1A1) + KSZ9031 na ULX5M-GS: lekcije iz TASK-4999

Izvor: TASK-4999 i TASK-5007, 23. i 24. 9. 2026. Detalji i sirova mjerenja nalaze se u `docs/HW_DIAG_20260923_TASK-4999.md`.
Sesije su popisane u `/home/klaudio/app/raid/archive/fpga-sessions/TASK-4999/README.md`.
Svaka stavka ima jednu od dvije oznake:
- **PROVJERENO**: izmjereno na ploči, dokazano simulacijom ili pročitano u datasheetu ili shemi. Dokaz je naveden uz stavku.
- **HIPOTEZA**: vjerojatno, ali nije dokazano. Ne smije se navoditi kao činjenica.

Oznake ploča: **stara pločica** nema X1, pa takt za XI daje FPGA s IO_EB_A3. **Nova pločica** (od 24. 9. u 15:39) ima zalemljen X1,
a vod prema E16 (IO_EB_A3) je prerezan.

## A. Takt i napajanje PHY-ja

| # | Lekcija | Status | Dokaz |
|---|---|---|---|
| A1 | KSZ9031 XI s vanjskim taktom traži najmanje **2,5 Vpp** uz DC-spregu, odnosno 1,5 Vpp uz serijski kondenzator. Banka EB je na +1V8, pa IO_EB_A3 daje najviše 1,8 Vpp, što je **izvan specifikacije**. | PROVJERENO | DS00002117F str. 66, pogl. 10; `tools/kicad_netlist.py` nad ulx5m-gs-hw 61b6709 (ETH_CLK = U4.E16 ↔ U14.46, VDD_EB = +1V8) |
| A2 | Rubni XI (1,8 Vpp) je uzrok flapanja linka i nalaza „isti bitstream, drukčiji ishod” na staroj pločici. | HIPOTEZA | u skladu s opažanjima: DRIVE=3 bez PHY-ja, DRIVE=6 s PHY-jem, flap reg1 0x796F↔0x794B, link 0 uz ispravan ID. Mjerenje amplitude na XI nije napravljeno |
| A3 | DRIVE=3 na IO_EB_A3 ne dostaje: PHY ne odgovara na MDIO. S DRIVE=6 PHY ID je čitljiv (0x0022/0x1622). | PROVJERENO | diag6, 23. 9. u 17:56 (UART ispis), commit 53e9ba9 |
| A4 | GateMate GPIO **ne podnosi 3,3 V**: VIN max = VDDIO + 0,4 V, a apsolutni maksimum VDDIO je 2,75 V. X1 od 3,3 V ne smije biti spojen na E16 dok je E16 na banci od 1,8 V. | PROVJERENO | DS1001, tabl. 4.1 i 4.3 (str. 110) |
| A5 | Na novoj pločici (X1, E16 prerezan) IO_EB_A3 se ne definira ni kao ulaz ni kao izlaz (`--no-phy-refclk`). | PROVJERENO | `grep -c EB_A3 *.ccf` = 0 u svim buildovima od 16:00 |
| A6 | KSZ9031 traži PHY reset ≥ 10 ms nakon stabilnog takta. LiteEth je zadano davao 16 µs (256 ciklusa), a ispravno je 20 ms (`--phy-reset-ms 20`). | PROVJERENO | DS tabl. 7-4 (tSR); kod `LiteEthPHYHWReset` |

## B. PLL-ovi (CC_PLL) i napon jezgre

| # | Lekcija | Status | Dokaz |
|---|---|---|---|
| B1 | VDD_CORE se bira kratkospojnikom J3 (open = 0,9 V, 1-2 = 1,0 V, 2-3 = 1,1 V). PERF_MD u buildu mora odgovarati stvarnom naponu. | PROVJERENO | power.kicad_sch (MPM3833) |
| B2 | Na staroj pločici prije prebacivanja na 1,1 V (23. 9.) SPEED PLL-ovi nikad nisu zaključali (LOCK_IN + fine-tune overflow), a LOWPOWER jest. | PROVJERENO | JTAG STATUS_PLLx (`tools/jtag_mailbox.py pll`) nad diag6/b2/b1/b4 |
| B3 | Na 1,1 V jedino **ECONOMY** zaključava 4/4 (oba slota, dvije vremenske točke). SPEED je rubni, a LOWPOWER pada u underflow. | PROVJERENO | TASK-5007, HW_DIAG „1,1 V” §2, commit 4648d6b |
| B4 | Isti bitstream mijenja stanje PLL-a u roku od 30 min (ft se pomiče: 0x0A3 → 0x27B). | PROVJERENO | TASK-5007 §2 |
| B5 | LiteX `GateMatePLL` uzima `locked` iz sirovog `USR_PLL_LOCKED` (LOCKED_STDY nije spojen), pa svaki trzaj locka resetira sys i sve u njemu (PHY reset, MDIO sekvencer). | PROVJERENO | kod; sys PLL ECONOMY LOCKED samo u 24/29 JTAG uzoraka (t5007_sys_ec, nova pločica); klijentov GATEMATE_CLOCKING.md, zamka 2 |
| B6 | Popravak za B5 je `gateware/sticky_lock.py`: lock mora biti stabilan 1 ms, a zatim ostaje ljepljiv. PHY reset i MDIO idu u domenu `ref` (sirovi clk25, reset samo CC_USR_RSTN). | PROVJERENO (sim) | `sim/tb_sticky_lock.py` 6/6 PASS, commit d2b9a9f. Učinak na ploči nije dokazan |
| B7 | `refclk_oe` u sys domeni: XI ostaje bez takta kad sys PLL ne zaključa. To je uzrok nalaza „diag6 jučer radi, danas ne”. | PROVJERENO | `sim/test_refclk_oe.sh` (RED → GREEN), commit 48207cb |
| B8 | CC_PLL: ft (fine-tune) se određuje samo pri zahvatu. Informaciju nosi gubitak zaključavanja, a ponovni zahvat traje 0,2–0,5 s. | PROVJERENO | fab4 (/2↔/3 svakih 168 ms → ft stalno 0x064) |
| B9 | Zaustavljena referenca zamrzne stanje PLL-a (ostaje LOCKED). PLL kao zastavica vrijedi samo uz kontrole `one` i `zero` u ISTOM slotu i ISTOM buildu. | PROVJERENO | `tools/pll_state.py`, y1/y3 proglašeni nevažećima |
| B10 | Izlaz rezervnog PLL-a mora se koristiti, inače status stoji. PLL izlazi troše globalne mreže (4), a uz više PLL-ova nextpnr pada na `CC_BUFG unsupported`. | PROVJERENO | buildovi b18–b34 i diag (`--single-pll`) |

## C. RGMII / MAC / MDIO

| # | Lekcija | Status | Dokaz |
|---|---|---|---|
| C1 | KSZ9031 **ne dodaje kašnjenje na TX**. MAC mora dati TXC pomaknut prema TXD/TX_CTL. | PROVJERENO | DS00002117F str. 22 |
| C2 | Na 100M TXC mora biti pomaknut za 90° (PLL CLK90). U simulaciji isti brid i 180° padaju (TX_CTL se uzorkuje na oba brida). | PROVJERENO (sim) | `sim/tb_txc_phase.py`. Na ploči nije dokazano |
| C3 | GateMate dopušta samo jedan DDR takt po IO banci („DDR port use signal different than already occupied DDR source”), pa CLK90 za TXC ide na pin izravno, bez CC_ODDR. | PROVJERENO | poruka nextpnr-a |
| C4 | MDIO okvir mora imati **64 uzlazna brida MDC-a**. Sa 63 brida PHY odbacuje svaki upis. | PROVJERENO | `tools/uhello/tb_writes3.v`; na novoj pločici nakon popravka R4 = 0101 pročitan natrag (mp2, 18:50) |
| C5 | AN samo za 100FD (reg9 = 0x0000, reg4 = 0x0101, reg0 = 0x1200) daje na switchu **100 Mb/s FD**. | PROVJERENO | nova pločica, mp2 preko UART-a (18:50): PHYAD = 3, R1 = 796D, R5 = C5E1, R1F = 0328, RXC ≈ 25,0 MHz |
| C6 | PHYAD je 3, iako LED1 i LED2 imaju 4k7 na GND: razinu dižu FET-ovi Q1/Q2 prema CM4 konektoru. | PROVJERENO | MDIO skeniranje 0–7 (samo A3 odgovara); shema |
| C7 | U `fixed_100m` načinu stanje linka iz RGMII in-band statusa se ne smije koristiti (S = 2/3 → gigabitno uokvirivanje). | PROVJERENO (kod) | commit f7a4498 |
| C8 | Nova pločica, n1 (ECONOMY, pll90, store-and-forward): ARP i ping s okvirom ≤ 60 B prolaze, a s okvirom ≥ 62 B ne. Jednom, nakon boota iz flasha. | PROVJERENO (jednom) | tcpdump, 24. 9. u 15:01 BST; nije ponovljeno |
| C9 | Prag 60/62 B objašnjava 10M link uz TXC od 25 MHz (TX FIFO PHY-ja se prelije). | **OBOREN** | 24. 9. u 20:50: isti prag uz dokazan 100FD (RF = 0328); sirovi TX okvira od 100 i 200 B radi (vidi H6) |
| C10 | Sirovi RGMII beacon bez LiteX-a (eb3), uz dokazan 100FD link i RXC 25 MHz, daje **0 okvira** na tcpdumpu. | PROVJERENO | eb3, 24. 9. oko 18:00 BST: UART R1F = 0328, JTAG PLL0 LOCKED 32/32, tcpdump 0 |

## D. Alat (yosys / nextpnr / p_r) i fabric

| # | Lekcija | Status | Dokaz |
|---|---|---|---|
| D1 | nextpnr-himbaechel (GateMate): široke clock-enable mreže (≥ 150) ne prolaze routing. Pomaže `dffunmap -ce-only`. Routing je osjetljiv na seed. | PROVJERENO | `tools/uhello/build_beacon.sh` |
| D2 | Vendorski p_r pada na DDR inačicama („Double Position Occupation” s PLL-ovima, „IDDR input pin … could not be routed”). SDR inačica prolazi. | PROVJERENO | b63 |
| D3 | Post-synth simulacija (yosys `cells_sim.v`) pokazuje ispravne okvire i ispravnu logiku, a na ploči nema ničega. Post-synth simulacija ne jamči ispravan rad na ploči. | PROVJERENO | `sim/postsynth/` (2 okvira, FCS OK); fab5b err=0 u sim, ERR = 1 na ploči |
| D4 | Na novoj pločici UART iz fabrica ima u SVAKOM znaku isti zaglavljeni bit: bit 2 u vendorskom buildu (P→T, 0→4), bit 3 u nextpnr buildu (A→I). Greška ovisi o rasporedu (placementu), statična je i ponavlja se 5/5. | PROVJERENO | ebv (p_r 2025.11 `-cCP -om 3`) i uhr0 (nextpnr), 24. 9. u 19:20 CEST |
| D5 | Uzrok D4 su ostaci konfiguracije prethodnog dizajna (bitstream bez CMD_CFGRST), a ne alat ni silicij. | PROVJERENO (H1) | 18:50–19:25 i poznato dobra LiteX referenca daje 0–2 B (REGOČ 3/3). Post-P&R simulacija vendorskog netlista je u tijeku (`~/.tmp/t4999_psim`) |

## E. Dijagnostički kanali bez dodatnog hardvera

| # | Lekcija | Status | Dokaz |
|---|---|---|---|
| E1 | JTAG preko DirtyJTAG-a je pouzdan: `tools/jtag_bert.py` (BYPASS) daje 0 grešaka na 131 039 bita pri 6 MHz i 1 MHz. | PROVJERENO | 24. 9. |
| E2 | JTAG STATUS_PLLx (serdestool TAP) pouzdano pokazuje stanje PLL-a dizajna. | PROVJERENO | TASK-5007 |
| E3 | CC_SERDES regfile kao sandučić fabric → JTAG je **nepouzdan**: radio je jednom, isti bitstream kasnije ne upisuje ništa. | PROVJERENO | mb3, e5 („SNAP INCONSISTENT”) |
| E4 | DirtyJTAG UART (ttyACM0) čuva stari međuspremnik. Prije čitanja ga isprazni (`timeout 2 cat >/dev/null`), inače čitaš ispis prethodnog bitstreama. | PROVJERENO | diag6 je vratio predložak b3 |
| E5 | UART most radi kad se čita SAMO u prozoru oko jednog `-r` učitavanja (`stty` 9600 → 115200, `timeout cat`, zatim zatvori port). | PROVJERENO | 18:40 CEST: LiteX ref 2004 B čitljivo, `ub_115200` „HELLO” čisto |
| E6 | Stalni čitač na ttyACM0 „ruši” most. | HIPOTEZA (vjerojatno ne; pravi uzrok je H1) | u 18:40 je radilo uz čitanje samo u prozoru, ali od 18:50 most opet daje smeće ili 0 B **bez** stalnog čitača, a i Goranova LiteX referenca daje 2 B u 3/3 (REGOČ). Čitač nije jedini uzrok |
| E7 | Nakon više SRAM učitavanja ttyACM prestane davati podatke, a vraća ga samo power-cycle. | OBJAŠNJENO (H1): nije most, nego ostaci konfiguracije; gmpack --reset vraća UART bez power-cyclea | skill ULX5M-GS-ETH; opaženo 23. 9. od 18:05 i 24. 9. od 18:50 |
| E8 | USB hub 05e3:0610 (Genesys) ima skupno (ganged) prekidanje: uhubctl ne gasi napajanje ni po portu ni za sve portove. Softverski power-cycle ploče nije moguć. | PROVJERENO | REGOČ, 24. 9. u 19:22 CEST (uhubctl 2.6.0 `-f`, DirtyJTAG ostaje u `lsusb`) |
| E9 | ILA (gatemate_ila, `CON_DEVICE='oli'`) koristi IO_WA_A5/A4/B3/B4, a to su na ULX5M-GS JTAG TCK/TDI/TDO/TMS (`+uCIO`). | PROVJERENO | netlist sheme |
| E10 | Nakon ILA učitavanja JTAG ostaje bez TAP-a do reseta (SRST ↔ RST_N nije potvrđen). | HIPOTEZA | kontrolirani pokus još nije napravljen |
| E11 | Nakon power-cyclea DirtyJTAG je 24 min javljao „TDO stuck at 0”. Tada `STATUS_PLL` vraća 0x00000 IDLE, a to NIJE mjerenje. Watcher zato traži IDCODE dvaput zaredom. | PROVJERENO | TASK-5007 §0 |
| E12 | tcpdump na Piju radi bez sudo-a (`/usr/sbin/tcpdump`, setcap, grupa pcap). Vidi SVE okvire, pa je neovisan kanal za TX ploče. | PROVJERENO | REGOČ, 24. 9. |

## F. Metodologija (pogreške koje su koštale vremena)

| # | Lekcija | Status | Dokaz |
|---|---|---|---|
| F1 | Nakon zadnjeg poznato dobrog stanja (diag6, 23. 9. u 17:56) promijenjeno je 10 stvari odjednom (refclk DDR, PERF_MD, sys takt, TX takt, CLK90, PHY reset, SF, beacon, single-PLL, BUFG). Pet buildova nije radilo, a nije se znalo zašto. Pravilo: od baseline-a **jedna promjena po buildu**. | PROVJERENO | REGOČ revizija 23. 9., RAG `ulx5m-gs-ethernet/debugging-lessons-2026-04-22` |
| F2 | Beacon koji ide kroz isti (pokvareni) TX put nije neovisan kanal. Neovisni kanali su tcpdump, JTAG i ILA. | PROVJERENO | b1–b17 beacon = 0 bez nove informacije |
| F3 | Dijagnostički kanal (PLL zastavice, sandučić) mora imati kontrolu u istom buildu, inače mjeri sam sebe. | PROVJERENO | df_s5/df_s6 (sve-1 = sve-0) poništili df_s0–s4 |
| F4 | Kad i **poznato dobra referenca** (Goranov LiteX bitstream) prestane raditi, ploča je u lošem stanju i daljnji buildovi naslijepo ne donose informaciju. Prvo vrati referencu (power-cycle), pa tek onda testiraj dizajn. | PROVJERENO | 24. 9.: ref 2004 B u 18:40, 0–2 B od 18:50 |
| F5 | Pi javlja podnapon (383× 24. 9.), a DirtyJTAG se u 10:48 sam odspojio 4× u 25 s, nakon čega je FPGA vrtio dizajn iz flasha. Goran je napajanje ploče proglasio dovoljnim. Utjecaj na neponovljivost nije dokazan. | PROVJERENO (događaj) / HIPOTEZA (uzrok) | dmesg Pija, JTAG PLL stanje |

## H. Proboj 24. 9. navečer (20:20–21:10 CEST)

| # | Lekcija | Status | Dokaz |
|---|---|---|---|
| H1 | **Bitstream mora početi s CMD_CFGRST (`gmpack --reset`).** Bez toga se rijetki bitstream (samo korišteni okviri) upisuje preko konfiguracije prethodnog dizajna. `openFPGALoader -r` s DirtyJTAG-om ne resetira FPGA: SRST je impuls bez čekanja, a spoj do RST_N nije dokazan. Posljedice: „poznato dobar” bitstream prestane raditi, UART ima zaglavljene bitove, nema okvira. | PROVJERENO | eb50 bez `--reset` (20:48) daje 0 okvira i 0 B UART-a. Isti .txt s `--reset` (ETH_GateMateA1_2409_2050_TXC_CFGRST.bit) odmah zatim daje 58 okvira i čist UART. `gmpack --help`: „--reset: reset all configuration latches with CMD_CFGRST”. Commit 7d874f5 (zadano u target_eth.py) |
| H2 | **TXC s PLL CLK90 ide kroz fabric** do pina (CPE X42/X46 → X113, 6,1–6,9 ns), a TXD/TX_CTL izlaze iz IOSEL FF-ova na globalnom taktu (0,29 ns). Stvarna faza je 90° + kašnjenje ovisno o seedu i naponu. | PROVJERENO | post-route skripta nad eb3 (seed 1) i n1 (seed 7), `getNetinfoRouteDelay`. Simulacija (tb_eb50.v): +7 ns → hold 3 ns, +9 ns → < 1 ns, ≥ 10 ns → TX_ER |
| H3 | **io50 TX:** eth_tx = 50 MHz, svi TX pinovi IOSEL FF (`FF_OBF=true`), TXC = IOSEL FF na PLL CLK180, datapath svaki 2. ciklus (tx_enable = ph) → 90° po konstrukciji, margina 10/10 ns. | PROVJERENO | eb50: prvi okviri s FPGA-a preko switcha (20:21). LiteEth: ETH_GateMateA1_2409_2050_LiteEth_CFGRST.bit → PING radi (-s 0/18). sim/tb_io50.py PASS (±8 ns) |
| H4 | **nextpnr bug:** negedge CC_DFF spojen u IOSEL (`FF_OBF`) gubi CLK_INV. `cleanup()`/`dff_to_cpe()` briše CLK_INV prije `pack_io_sel()`, pa IO FF tiho radi na rastući brid. Isto u masteru. Zaobilaznica: IO FF na posedge PLL izlaza CLK180. | PROVJERENO | tools/uhello/negff_repro/run.sh → „BUG PRESENT” (nextpnr-0.11.1-31-g3edea68e) |
| H5 | LiteX peppercorn **ne predaje .sdc** nextpnr-u (`#pnr_opts += " --sdc"` je zakomentiran), a RGMII IO nema constrainta. Kašnjenja RAMIO→IOSEL (DDR select, CLK90 do pina) nextpnr prijavljuje kao 0,000 ns. „Timing PASS” ne pokriva RGMII. | PROVJERENO | litex/build/colognechip/peppercorn.py r. ~73; delays2.json |
| H6 | Sirovi TX dugih okvira radi: beacon od 100 i 200 B → 44 okvira svaki. RX dugih okvira radi: ARP upiti 62–1400 B → odgovori. LiteEth odgovor na okvir > 60 B (ping -s ≥ 19) ne izlazi, neovisno o uzorku podataka. | PROVJERENO | ETH_GateMateA1_2409_2102_Beacon_100B/200B.bit; arp_len.py; ping -p 00/ff/55/aa/0f |
| H7 | Store-and-forward PacketFIFO (BRAM) na 50 MHz ne prolazi timing: `ph → ready → rd ptr → ADDRB` je 27 ns i stvarno je jednociklični put. Za io50 SF isključiti. | PROVJERENO | io50a: eth_tx 36,98 MHz; io50b bez SF: 51,11 MHz |
| H8 | CC_PLL CLK180/CLK270 s `*_DOUB=1` daju dvostruku frekvenciju. CLK270×2 ima rastuće bridove na 90° i 270° takta CLK0. To je alternativa za TXC uz datapath na 25 MHz. | PROVJERENO (datasheet) | UG1001 sl. 7.4, str. 109 |
| H9 | openFPGALoader `reset()` za dirtyJtag šalje SETSIG SRST (bit 6) nisko pa odmah visoko, bez čekanja (FTDI grana drži 500 µs). pico-dirtyJtag: SRST je emulirani open-drain (zadano GPIO20, aktivno nisko, interni pull-up). ULX5M-GS nema RP2040. RST_N (U4.T15) ide na R111 (10k na +1V8), C138 (100 nF, τ ≈ 1 ms), IO_SB_B8 i J2.72/J2.99 (CM4 konektor). Koji RP2040 GPIO (ako ijedan) vodi na RST_N, odlučuje nosiva pločica. | PROVJERENO (izvor + shema) / HIPOTEZA (spoj na nosivoj pločici) | openFPGALoader 676e53e colognechip.cpp r. 52, 88–105; pico-dirtyJtag cmd.c r. 249–274, pio_jtag.h r. 62–66; kicad_netlist.py nad ulx5m-gs-hw 61b6709 |
| H10 | Neovisno o tome stiže li SRST do RST_N, CMD_CFGRST u bitstreamu (H1) čisti konfiguraciju bez oslanjanja na kabel. To je pouzdan lijek i zato je zadano uključen. | PROVJERENO (učinak) | H1 |
| H11 | **Prag > 60 B = LiteEth `last_be` = 0.** LiteEth 40dfb7a prešao je na LiteX Packetizer, koji ne postavlja `last_be`. Uz `core_dw == phy_dw == 8` MAC nema TX LastBE stupanj, pa okvir > 60 B dobije FCS = 00000000 (≤ 60 B spašava PaddingInserter). Popravak: `TXLastBE8` (`last_be = last`) na ulazu MAC TX puta. **ISPRAVAK (REGOČ 24.9. 22:30):** uzrok je neusklađenost inačica — LiteEth 9654767 traži LiteX ≥ 7fca6dba (18.9., `last_be` u Packetizeru), a mi imamo LiteX 52f183ef6 (17.3.). Nije uzvodna greška; pravi popravak je nadogradnja LiteX-a (vidi docs/UPSTREAM_ISSUES_draft.md §2). | PROVJERENO | RTL sim (Verilator, sim/io50rtl/run.sh): RED -s 19/20/100 FCS 0, GREEN svi OK; ploča: ETH_GateMateA1_2409_2130_LastBE_Fix.bit -s 0…120 5/5. Commit 4ee8c97 |
| H12 | LiteEth ICMP echo FIFO je zadano 128 B, pa se ping s više od 120 B podataka odbacuje po dizajnu. `icmp_fifo_depth=2048` omogućuje -s 1472 (MTU). | PROVJERENO | sim -s 1000/1472 OK; ETH_GateMateA1_2409_2141_Ping_MTUs13.bit -s 1000/1472 5/5 |
| H13 | Ishod ovisi o seedu, iako nextpnr javlja PASS: io50f seed 8 (eth_tx 50,59 MHz PASS) ne odgovara uopće, a seed 13 radi 3/3. nextpnr za GateMate ne radi analizu holda. RXC (IO_EB_A7) je fabric takt s ~300 odredišta i rasipanjem kašnjenja 1,58–11,17 ns (s8), odnosno 1,58–9,01 ns (s13). | PROVJERENO (seed) / HIPOTEZA (hold na eth_rx) | ploča 20:40 i 20:41; post-route skripta rxpath.py (rx_s8.json, rx_s13.json) |
| H14 | S preporučenim bitstreamom prvi ping odgovor stiže **2,95 s** nakon kraja `-r` učitavanja (AN 100FD), a nakon toga 100 % odgovora. | PROVJERENO | `ping -D -i 0.2`, 2 mjerenja: 2,95 s i 2,94 s |
| H15 | **Pravilo odabira seeda:** RXC (IO_EB_A7) je fabric takt, a nextpnr ne radi analizu holda. U seed sweepu (23 bitstreama, ploča, CFGRST) u svakoj inačici padaju upravo seedovi s NAJVEĆIM kašnjenjem `eth_rx_clk` do odredišta. Dijagnostička io50f (~300 odredišta, 8,1–11,2 ns): pada samo s8 (11,17 ns). Produkcijska io50p (~50 odredišta, 5,6–7,5 ns): padaju s12 i s9 (7,54 ns), a svi ostali rade. Setup-timing eth_tx (40–49 MHz „FAIL”) NIJE bio presudan. Postupak: sweep seedova → `tools/pnr_probe/rxpath.py` → odaberi seed s najmanjim max kašnjenjem RX takta → provjeri na ploči. Manje logike u eth_rx domeni (bez dijagnostike) smanjuje rasipanje. | PROVJERENO (korelacija) / HIPOTEZA (mehanizam: hold) | docs/seed_sweep_io50_20260924.txt; ETH_GateMateA1_2409_2204_SeedF_s*/SeedP_s* |

## G. Imenovanje bitstreamova (Goran, 24. 9. u 19:35)

Svaki bitstream koji se učitava na ploču imenuje se `ETH_GateMateA1_<DDMM>_<HHMM>_<Opis_2rijeci>.bit` (CEST,
`TZ=Europe/Zagreb date +%d%m_%H%M`) i drži se na Piju u `/home/fpga-klaudio/FPGA/`. Isto ime se navodi uz rezultat u HW_DIAG i ovdje.

## I. 1000 Mb/s (TASK-5032, 24./25. 9. 2026, nova pločica)

Rezultat: **ping na 1000 Mb/s** (`bitstreams/ETH_GateMateA1_2509_0211_GbE_Ping1G.bit`, commit 0d94144, tag `gbe-1000m-ping-ok-20260925`).
Dizajn: `gateware/gbe_phy.py` (na 125 MHz samo IO registri, bajtni poravnjač i 32-bitni BRAM port; CDC po cijelim okvirima kroz BRAM)
i `gateware/target_gbe.py`. LiteEth ostaje u sys (20 MHz).

| # | Lekcija | Status | Dokaz |
|---|---|---|---|
| I1 | **1G na ovoj ploči JE izvediv**: RXC (IO_EB_A7, pin koji nije za takt) preko eksplicitnog CC_BUFG radi na 125 MHz. RX poravnanje A (rastući brid = niski nibble) bez upisa u MMD2 pad-skew. | PROVJERENO | UART: C = 0x6400BD (125,0 MHz), F = D.rx_frames, rx_drops 0, rx_sel 0 (Ping1G, 3 pokušaja) |
| I2 | KSZ9031 s reg9 = 0x0200, reg4 = 0x0001, reg0 = 0x1200 daje **R1F = 0348** (bit 6 = 1000, bit 3 = FD), RA = 3800 (LP 1000FD, lokalni i udaljeni RX OK). | PROVJERENO | UART mdio_core na svakom 1G bitstreamu |
| I3 | Upis AN-a u 6. MDIO prolazu (~2 s) ponovno pokreće AN, pa slijedi drugi 1000BASE-T AN. Prvi odgovor bio je 12,2 / 6,9 / 7,1 s. S upisom u 1. prolazu (`WRITE_AFTER = 0`) je 6,07 / 7,15 / 5,47 s. | PROVJERENO | Ring10 i Ping1G, po 3 pokušaja uz prljavi bitstream |
| I4 | **LiteEth MAC ne postavlja `first` na PHY sinku.** Vlastiti PHY koji okvir počinje tek uz `sink.first` zaglavi TX zauvijek (tx_frames 0). | PROVJERENO | ploča Diag13 (D = tx_frames 0, rx 21); sim `tb_gbe_phy.py` s `first = 0` visi (RED), a nakon popravka prolazi |
| I5 | **Reset-less one-hot prsten s INIT-om** (p = 0001) u domeni PLL takta zaglavi: nextpnr INIT prenosi (FF_INIT), ali takt pri zaključavanju PLL-a daje glitch. Lijek je samokorigirajući prsten `p0 <- ~(p0\|p1\|p2)`. | PROVJERENO (ploča) / HIPOTEZA (mehanizam: glitch) | TXfix11: tx_frames 36, tx_emit 0. Nakon popravka Ring10/Ping1G tx_frames = tx_emit. Sim s pokvarenim prstenom RED → GREEN |
| I6 | **TXC pomaknut za 90° mora ići kroz CC_BUFG.** Izlaz PLL-a bez BUFG-a ruta se fabricom od PLL-a (X46) do pina (X113), 5,8 ns, pa TXC pada na prijelaz podataka (0 okvira). Kroz BUFG TXC ima 1,72 ns do CPE-a ispred pina, a DDR select ODDR-a 1,15 ns (isti tip puta), pa CLK90 daje ~2 ns kao RGMII-ID. | PROVJERENO (nextpnr sonda) / na ploči radi faza 90° kroz BUFG | `tools/pnr_probe`-stil sonda cpein (p2_s13, b90_s9); Ping1G |
| I7 | CC_ODDR: DDR select ide iz globalne mreže kroz CPE u IOSEL. nextpnr zadnji skok RAMIO → IOSEL prijavljuje kao 0,000 ns (nemodelirano, vidi H5). Redoslijed izlaza je D0 pa D1 (UG1001 sl. 2.12), a nextpnr D0 → OUT2 (rastući), D1 → OUT1 (`INV_OUT1_CLOCK`). | PROVJERENO (izvor + UG1001 + ploča) | pack_io.cc; UG1001 str. 42; 1G okviri ispravni |
| I8 | **nextpnr pada** (`dict::at` u `TimingAnalyser::set_required_time`) u punom dizajnu kad TXC ide kroz LUT (invertor ~CLK, međuspremnik CLK0, mux u radu `--txc-rotate`) te za `--txc-phase 270`. Minimalni primjer (PLL → invertor → pin) NE pada, pa okidač nije izoliran. | PROVJERENO (opažanje) / HIPOTEZA (okidač) | p0/p1/p3 × 4 seeda i r1–r19 svi pad; p2 (CLK90 izravno) radi |
| I9 | nextpnr `fpga_mode` mijenja samo vremenski model (i upozorenje za PLL PERF_MD). Uz VDD_CORE 1,1 V ispravan je model SPEED, a PLL-ovi ostaju ECONOMY (B3). Na 125 MHz ECONOMY model daje gtx ≤ 118 i grx ≤ 96 MHz, a SPEED (worst) za dobre seedove gtx 128 i grx 144 MHz. | PROVJERENO (izvor gatemate.cc, izmjereno nextpnr) | f_s15, m33 |
| I10 | **Odabir seeda za 1G:** sweep 14 seedova, uzmi onaj gdje gtx (`…pll0_clkout0`) i grx (`mdio_core.rxc`) PASS na 125 MHz (SPEED, worst). Prolaze ~2/14. `clkin`/`ref_clk` „FAIL na 125” je lažan (25 MHz, zadani `--freq`). | PROVJERENO (korelacija: svi bitstreamovi na ploči s PASS seedom rade) | c/d/e/f sweep |
| I11 | Široki fanout na 125 MHz: WE RX BRAM-a ide na 36 per-bit WEA pinova (3,5 ns rute iz jednog FF-a). Replike registra s `(* keep *)` yosys `opt_merge` ipak spaja. Rade samo eksplicitne `CC_DFF` instance (+ `we_granularity=9`). | PROVJERENO | `synth_gatemate` test (4 → 1 FF s keep, 4 → 4 CC_DFF); grx 122 → 136 MHz |
| I12 | Diagnostički signal koji čita sys (beacon) vuče registar iz 125 MHz domene daleko (rx_sel: 6,5 ns rute). Beaconu daj kopiju (sel_d). | PROVJERENO | x-sweep: grx 101–114 → do 136 MHz |
| I13 | LiteX ≥ 7fca6dba (b6ae9e0b2): **TXLastBE8 nije potreban** (ping 18…1472 OK). Stari LiteX 52f183ef6 bez njega daje FCS grešku na SVIM veličinama. | PROVJERENO (sim) | `sim/tb_lastbe.py` fix/nofix × 2 stabla; na ploči Ping1G (bez TXLastBE8) -s 0…1472 5/5 |
| I14 | Novi LiteX (2026.08) PLL hrani vlastitim `clkin_signal`, pa `clkbuf_inhibit` na pinu clk25 ne vrijedi: domena `ref` pojela je 4. globalnu mrežu. Atribut stavi na `cd_ref.clk`. | PROVJERENO | yosys stat (BUFG: gtx, sys, grx, TXC) |
| I15 | Migen sim s dva generatora u domenama istog takta: redoslijed ovisi o `PYTHONHASHSEED`. TB koji čita što drugi generator dodaje u istom koraku gubi bajtove (lažni RX FAIL s hash 3). Replay mora kasniti (LAG). | PROVJERENO | tb_gbe_phy.py hash 0–5 |

## J. Puni SoC (TASK-5033, 25. 9. 2026)

Rezultat: `ETH_GateMateA1_2509_0918_SoC_S5s9.bit` (`--boot none`, VexRiscv standard) i `ETH_GateMateA1_2509_1027_SoC_NetBoot.bit` (`--boot netboot`, VexRiscv lite), oba 3/3 uz prljavi bitstream. Izvještaj: `docs/SOC_PHASE2_20260925_TASK-5033.md`.

| # | Lekcija | Status | Dokaz |
|---|---|---|---|
| J1 | LiteX BIOS s LiteSDCard-om **bez kartice visi** na „Booting from boot.json...” i nikad ne dođe do konzole. Za razvoj koristi `BIOS_NO_BOOT` (`--boot none`). | PROVJERENO | S4SD (0328) na ploči; S5 s `BIOS_NO_BOOT` odmah daje konzolu |
| J2 | **LiteEthEtherbone odgovara na odredišni port = svoj UDP port (1234)**, ne na izvorni port pošiljatelja. Klijent mora slušati na 1234 (`bind`), kao `litex/tools/remote/comm_udp.py`. | PROVJERENO | tcpdump: zahtjev stiže, a klijent bez `bind` ne prima ništa. S `bind` scratch = 0x12345678 |
| J3 | **Ping 1472 na 1G gubi 10–60 % okvira DOK radi 64 MiB mem_test**, a odmah poslije 20/20. Isto vrijedi i za S3, pa uzrok nije promjena u S5. Mehanizam (SSO SDRAM sabirnice, napajanje ili nešto treće) nije utvrđen. | PROVJERENO (korelacija) / HIPOTEZA (mehanizam) | `tools/gbe/timed.py`: mem_test 8,6 → 87,0 s, u tom prozoru 10–18 od 20 odgovora po 10 s, nakon njega 20/20; `sdcard_init` 20/20 |
| J4 | Naredbe u BIOS šalji **znak po znak (20 ms)** i **tek kad se pojavi „Console”**. Burst gubi znakove („sdId_init”), a naredba poslana za trajanja boot sekvence (netboot, serialboot timeout) stigne okrnjena („000 0x4000000”). | PROVJERENO | S5s9 i NetBoot na ploči |
| J5 | **Tuđi rad na ploči kvari mjerenje.** Dvostruki BIOS banner, zauzet ttyACM0 i mrtav ping u 09:15–09:24 bili su Goranov istodobni Linux test. Pokušaj je nevažeći ako je ttyACM0 otvoren negdje drugdje (`fuser`). | PROVJERENO | uputa #24; poslije toga isti bitstream 3/3 |
| J6 | **Seed PASS ne jamči 1G na ploči, niti FAIL znači kvar.** s5_4 (sve tri domene PASS) gubio je 1472. Svih 7 seedova s gtx/sys FAIL (put u CC_DFF.SR reset sinkronizatora) dalo je 40/40. Seed biraj mjerenjem na ploči. | PROVJERENO (s5_4 uz sumnju J5) | `s5sweep` 40/40 × 7 |
| J7 | **Placer pada iznad ~75 % CPE_LT, a CC_MULT nije uzrok.** Poruka je „Unable to find legal placement for CPE_FF”, a `--placer-heap-cell-placement-timeout` ne pomaže. Goranovu hipotezu (uputa #26, CC_MULT/BRAM zauzimaju CPE-ove) opovrgava čisti pokus: `-nomult` ukloni sva 4 CC_MULT, LT poraste na 85 % i placer i dalje pada, a pada i `linux+no-dsp` bez MULT-a na 79 %. Prolaze: 59, 61, 68, 71 %. Padaju: 76, 77, 79, 83, 84, 85 %. | PROVJERENO (12 buildova, bez iznimke) / HIPOTEZA (točan prag 71–76 %) | nb (std, 4 MULT) 76 % pad 8/8; nbM (`-nomult`, 0 MULT) 85 % pad 3/3; lnd (0 MULT) 79 % pad 2/2; lx 83 %; smpE 84 %; smpM 77 %; nbB/nb2/nb3 71 % i S5 68 % prolaze; smp 61 % prolazi |
| J8 | Netboot uz hardverski stog: LiteEth `interface="hybrid"` (kao `add_etherbone(with_ethmac=True)`). CPU dobije vlastiti MAC/IP i TFTP, a hardverski ARP/ICMP/Etherbone na .212 i dalje radi. Trošak je +3 650 LT i +8 RAM_HALF. | PROVJERENO | NetBoot 3/3: boot.bin 6280 B za 8,2 s nakon -r, ping 5/5 |
| J9 | VexRiscv lite (bez dcachea): 64 MiB mem_test traje više od 5 min (čitanje ~0,25 MiB/s), a standard 78 s. Prozor za mem_test prilagodi CPU varijanti. | PROVJERENO | NetBoot: nakon 170 s pročitano 39,8 MiB, bez grešaka |

| J10 | **Bare-metal aplikacija nakon BIOS netboota NE smije uključiti prekide** (`irq_setie(1)` iz LiteX demo predloška). Inače CPU port (hybrid MAC) ne vidi nijedan okvir: `sram_writer` pending je 0, errors 0, a Pi šalje unicast na 10:e2:d5:00:00:01. Bez IRQ-a (polling UART i ethmac) echo radi odmah. Mehanizam nije utvrđen. | PROVJERENO (ishod) / HIPOTEZA (mehanizam) | speedtest.bin s IRQ: 0 okvira; bez IRQ: echo 3/3, pa puni test |
| J11 | **Pi 3B+ eth0 je na 100 Mb/s** (lan78xx preko USB-a), pa svako mjerenje s Pija staje na ~95 Mb/s. CPU put (VexRiscv lite, 20 MHz): Pi→FPGA 1472 B 95,7 Mb/s (ograničava Pi), FPGA→Pi 6,3 Mb/s (ograničava CPU: libliteeth računa CRC32 u softveru jer `HW_PREAMBLE_CRC` nije definiran, uz kopiranje u SRAM slot). | PROVJERENO | `tools/speedtest/eth_speedtest.py`, `/sys/class/net/eth0/speed` = 100 |
| J12 | LiteX BIOS **ne ispisuje ident** pri pokretanju (samo naredba `ident`). Lokalna zakrpa `docs/litex-bios-print-ident.patch` (`CONFIG_BIOS_PRINT_IDENT`) ga ispisuje u SoC odjeljku. | PROVJERENO | NetBoot3 banner „Ident: … HW ping/Etherbone .212 … CPU/TFTP .213 …” |
| J13 | **BIOS ROM od 64 KiB zauzima 32 od 64 RAM_HALF** (16 × CC_BRAM_40K). Smanjenje na 48 KiB ne štedi ništa, jer yosys dubinu 12K zaokruži na 16K (RAM_HALF ostaje 47). Pomaže tek 32 KiB, a BIOS s mrežom ima 36–48 KB. | PROVJERENO | smpMnR_1 (ROM 0xC000): RAM_HALF 47 = smpMn_1 |
| J14 | **Linux (VexRiscv-SMP, 1 jezgra, I$/D$ 4 KiB, Ldw16, l2 0) stane na CCGM1A1 bez 1G hardverskog stoga.** Serial + SD: LT 61 %, RAM 38/64, P&R PASS, cpu 24,5 MHz. SMP + CPU MAC (bez SD): LT 59 %, RAM 47/64, routanje sporo konvergira. SMP + MAC + SD: 77 % pa pada, SMP + hardverski stog: 84 % pa pada. | PROVJERENO (P&R) | smp_1, smpMn_*, smpM_*, smpE_1 |
| J15 | **SPI-SD umjesto LiteSDCard-a košta samo +85 CPE_LT i +5 RAM_HALF** na Linux SoC-u (SMP + 1G CPU MAC): 55 % LT, 50/64 RAM, P&R PASS; bez kartice BIOS SPI-SD samo istekne i nastavi netbootom (ne visi kao J1). | PROVJERENO | spisd_1/2/3/11, TASK-5039 |
| J16 | **SD utor je na banci NA/NB = SDRAM_VCC (1,8 V)**; SD kartica se inicijalizira na 3,3 V (VIH ≈ 2,06 V), SPI način 1,8 V ne poznaje. Kartica ne odgovara ni SPI-SD-u ni LiteSDCard-u (FatFs 3 = FR_NOT_READY, nema mmcblk0). J2.75 SD_PWR_ON nespojen. | PROVJERENO (simptom, pinovi) / HIPOTEZA (uzrok: razina/napajanje) | TASK-5039, kicad_netlist ulx5m-gs-hw |

## K. DVI, Linux fbcon i DOOM (TASK-5040, 25. 9. 2026)

| # | Lekcija | Status | Dokaz |
|---|---|---|---|
| K1 | **Framebuffer 640×480 rgb565 iz 16-bitnog SDRAM-a na 20 MHz ne ide** (36,9 MB/s = 92 % vrha). `FrameBuffer2x` čita 320×240 (9,2 MB/s) i u hardveru udvostručuje piksel i liniju (line buffer 1 RAM_HALF). Linux ga vidi kao `simple-framebuffer` r5g6b5. | PROVJERENO | Goran: slika i boje OK (17:16), `ETH_GateMateA1_2509_1651_Linux_DVI_s1.bit`; memspeed s fb 27,9/10,5 MiB/s (bez 33,2/13,9) |
| K2 | **1G + DVI stanu u 4 BUFG** ako video ne dobije vlastite taktove: hdmi5x = `gtx0` (125 MHz), a piksel logika radi u `gtx0` s CE 1/5. TMDS takt je riječ `0b0000011111` kroz serijalizator. | PROVJERENO (P&R, Linux boot + ping) / slika NESTABILNA (Goran 18:12) | gdvi_1: LT 68 %, RAM 48, BUFG 4 |
| K3 | **`CEInserter` ne pokriva memorijske portove.** Write enable i read enable line buffera moraju ići kroz `ce`, inače upis ponovi idući piksel na istu adresu, a sinkroni `dat_r` bježi 1 piksel naprijed. | PROVJERENO (sim 132 greške → 0) | `sim/tb_scaler2x.py` [ce 1/5] |
| K4 | **P&R rc=0 ≠ radi.** gdvi seed 9: bitstream se učita, a na UART-u nema ni bajta (ni BIOS). Seed 1 istog dizajna diže Linux. Novi dizajn uvijek probati na ploči na ≥2 seeda. | PROVJERENO | `DEAD_seed9_…1728_Linux_GbE_DVI.bit` |
| K5 | **Prebuilt kernel 5.14 (linux_2022_03_23) ima simplefb, fbcon, tty0 i fontove VGA8x8/VGA8x16, ali nema USB** (ni usbcore ni OHCI). `fbcon=font:VGA8x8` na 320×240 daje 40×30; s 2× uvećanjem slova su 16×16 px („jako velika"). simplefb u 5.14 nema 8bpp format. | PROVJERENO | `strings Image`, dmesg „frame buffer device 40x30", `/proc/fb` = `0 simple` |
| K6 | **fbcon usporava boot ~3×** (kernel ~90 s umjesto ~25 s): svaki redak loga scrolla 150 KB framebuffera kroz SDRAM. | PROVJERENO | `[85.7] ttyLXU0` naspram `[23.3]` bez fb |
| K7 | **USB OHCI (SpinalHDL) je prevelik za CCGM1A1 uz Linux**: +14 k LT, uz DVI 91 % i placer pada. Za tipkovnicu je bolji hardverski HID→ASCII host u UART RX (bez kernela). VBUS na J5 nije napajan. | PROVJERENO (P&R) / PRIJEDLOG | dviusb_9 |
| K8 | **Linux rv32 bez libc-a** (xPack riscv-none-elf + newlib + vlastiti ecall sloj): rv32 ima samo `openat`, `llseek`, `brk`, `mmap2` i `clock_gettime64` (403). Statički ELF `-Ttext-segment=0x10000 -z max-page-size=4096` radi na Buildroot 5.14. | PROVJERENO | `tools/doom_linux/sys_linux.c`, DOOM + `/dev/fb0` mmap |
| K9 | **DOOM na VexRiscv-SMP 20 MHz: 1,7–1,8 FPS** u `-timedemo demo1` (3D), 5,5 FPS na naslovnim ekranima. smunautov engine je v1.10, pa demoe iz doom1.wad v1.9 treba prihvatiti (109). | PROVJERENO | UART log „100 frames in 55953 ms" |
| K10 | **TFTP u Linuxu (busybox) s blokom 512 B ide ~15 KB/s** (35 ms po bloku), a s `-b 1400` WAD 4,2 MB prođe za ~97 s. | PROVJERENO | dnsmasq log 17:01–17:03 |
| K11 | Datoteke u `/tmp` na Piju pripadaju korisniku koji ih je stvorio: skripta pokrenuta kao `pi` ne može prepisati `/tmp/bios_cmds.txt` od `fpga-klaudio` i ispiše **stari log** (lažni rezultat). ttyACM0 piše samo grupa dialout (`fpga-klaudio`). Koristi jedinstvena imena (`$$`). | PROVJERENO | TASK-5040 16:57 |
| K12 | LiteX VTG šalje hsync/vsync **pozitivnog** polariteta, a VESA 640×480@60 traži negativan. `--video-neg-sync` nije promijenio ispade (4/60 naspram 5/48). | PROVJERENO: nije uzrok | gneg_1 |
| K13 | **Pod SDRAM opterećenjem PLL-ovi gube lock tisućama puta** (dvipll_1: mirovanje +0, `mem_test` 8 MB: sys +3787, video +2665), pa DVI slika ispada (i u 2-taktnom buildu bez 1G: 16/30). **VDD_PLL = VDD_CORE preko R23 1 Ω + C42 100 nF, L5 DNP.** Isti uzrok vjerojatno stoji iza nasumičnog reseta SoC-a. | PROVJERENO (mjerenje) / HW prijedlog | `docs/SBC_DVI_USB_TASK-5040.md` §7 |
| K14 | Mjeri sliku sama: MS2109 capture na Piju, servis `hdmi-stream` :8090 (`/snap.jpg`). **`070707` = nema signala, `000000` = crna slika**, a prva snimka nakon otvaranja uređaja zna biti crna. | PROVJERENO | `~/.tmp/t5040/idle_series.sh` |
| K15 | **nextpnr-himbaechel `set_false_path -from/-to` ne radi ništa** („does not do anything (yet)"). Višetaktne CE putove ne možeš izuzeti, pa ih placer tretira kao kritične i zanemari prave jednotaktne putove (CE mreža fanout 146: 10,9 ns na 125 MHz). `--report rep.json --detailed-timing-report` daje kašnjenje po mreži. | PROVJERENO | s_gcer_1_rep, s_gtree_3_rep |
| K16 | `pgrep -f '<uzorak>' \| xargs kill` unutar `ssh '…'` ubije i vlastitu ljusku (uzorak je u njezinoj naredbi). Za ttyACM0 koristi `fuser -k /dev/ttyACM0`. | PROVJERENO | loadtest.sh 19:58 |
| K17 | **Prije HW preporuke „zalemi DNP dio" provjeri ima li dio footprint na PCB-u.** L5/L6/L7 (feriti za VDD_PLL/VDD_SER_PLL/VDD_SER) su u shemi, ali NISU na `ulx5m-gs.kicad_pcb`; ugrađeni su R23/R105/R106 = 1 Ω (0603). Zakrpa: 10 µF na TP6 (VDD_PLL), pa tek onda ferit 0603 umjesto R23. Tvrdnja „SerDes PLL ima ferit" bila je netočna. | PROVJERENO (kicad_netlist.py + grep PCB) | docs/SBC_DVI_USB_TASK-5040.md §8 |
| K18 | **+1V8 je zajednička tračnica za SDRAM i izvor takta.** R116 = 0 Ω spaja SDRAM_VCC (U10 VDD/VDDQ + banke WB/WC/NA/NB) na +1V8, a na +1V8 su i oscilator Y1 25 MHz (ASE2, bez filtra), VDD_CLK (U4.T14) i preko R122 4R7 VDD_SB (ulaz clk25 IO_SB_A8). SDRAM promet zato može kvariti takt i preko **ulaza** PLL-a, ne samo preko VDD_PLL. Zakrpa na TP6 pokriva samo drugi put; prije lemljenja pokreni `tools/dvi/pll_discriminator.sh` (ovisi li broj padova locka o podacima na DQ ili samo o aktivnosti). | SHEMA PROVJERENA / MJERENJE ČEKA PLOČU | `kicad_netlist.py --net SDRAM_VCC`, `--ref R116/Y1/R122`; SBC doc §9 |
| K19 | **Prebuilt kernel 5.14 (florent, 2021) ima samo fontove VGA8x8 i VGA8x16**, bez MINI4x6. Manja slova na 320×240 zato traže novi kernel. Pingvin se miče bez rebuilda: bootarg `logo.nologo` postoji u Image. „Velika slova" su posljedica dizajna: 8×8 → ×2 skaler = 16×16 px, 40×30 znakova. | PROVJERENO (`strings Image`) | SBC doc §9 |
| K20 | **LiteX `GateMatePLL` ostavlja `LOCK_REQ=1`, a uz to CC_PLL ISKLJUČUJE izlazni takt dok god je `USR_PLL_LOCKED`=0 (DS1001 tab. 2.19).** Svaki trzaj detektora locka (pod SDRAM prometom tisuće) postaje rupa u sys/video taktu i slika ispada. `--pll-lock-req 0`: detektor i dalje trepće (STDY=0), ali takt teče. Izmjereno na 1G+DVI (isti placement): LOCK_REQ=1 0/30 ispravnih snimaka pod 2× mem_test 32 MiB, LOCK_REQ=0 30/30. | PROVJERENO (mjerenje) | `docs/SBC_DVI_USB_TASK-5047.md` §2.2 |
| K21 | **`cd_gtx0` nema reset** (`with_reset=False`, bez AsyncResetSynchronizera), pa se CE video put (13 CE brojača, VTG, CDC read strana) nikad ne resetira. Poremećaj takta ga trajno razmakne: resync na svakom okviru, underflow 0, crna slika uz ispravan sync. Restart DMA ne pomaže. Lijek: domena `vid` (isti gtx0 takt) s resetom + `ResyncWatchdog` (`--video-recover`). | PROVJERENO | isto §2.3, §2.4 |
| K22 | **nextpnr-himbaechel (oss-cad 20260923) javlja hold prekršaje; build s `Hold/min time violation` na sys domeni ne pokreće CPU na ploči** (dvistdy/dvilr0/dvis16: clk-skew −3,89 ns BRAM→FF), iako je rc=0 i Fmax PASS. Prije učitavanja: `grep -c 'Hold/min time violation for' log` mora biti 0; `mitigation_sweep.sh` na to upozorava. | PROVJERENO | isto §2.2 |
| K23 | **`SLEW=slow` u CCF-u je no-op: default za izlaze je već SLOW** (nextpnr `.txt`: 42× `GPIO.SLEW 1`; `SLEW=fast` daje `SLEW 0`). Bitstream s `slow` je bit-identičan. `clkbuf_inhibit` za takt iz fabric FF-a mora biti na **registru** (ne samo na `cd.clk`), inače yosys umetne 5. CC_BUFG i nextpnr padne s `dict::at()`. | PROVJERENO | isto §2.1, §5 |

Stablo LiteX-a za 1G: `~/app/litex-1g-deps` (worktree LiteX b6ae9e0b2 + zakrpa CC_IOBUF T; migen/liteeth/litex-boards dijeljeni). Staro stablo (`~/app/litex-rgmii-ulx5m`) netaknuto je radi 100M reference.
