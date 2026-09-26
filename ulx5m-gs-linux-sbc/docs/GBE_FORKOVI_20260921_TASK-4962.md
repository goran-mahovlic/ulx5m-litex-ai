# ULX5M-GS 1 Gbps Ethernet: što je u forkovima Patricka (pu-cc), mmicka i trabucayrea (TASK-4962)

Autor: Grga (REGOČ Designer) · 2026-09-21 · nastavak na `GBE_FEASIBILITY_20260921_TASK-4961.md`
Klonirani izvori: `~/app/task4962/{pu-liteeth,pu-litex,pu-litex-boards,mmicko-boards,trabucayre-demos}`

---

## 0. Sažetak

1. **Patrick NIJE riješio 125 MHz timing u fabricu — zaobišao ga je.** Njegov
   `gatematergmii` PHY deklarira `tx_clk_freq = rx_clk_freq = 25e6`, pa LiteX
   eth-domene ograniči na **25 MHz (40 ns)** umjesto 125 MHz (8 ns). Alat zato
   "prolazi" timing koji nitko nije provjerio na 125 MHz. Uz to cijeli njegov flow
   ide kroz **proprietarni Cologne Chip `p_r`** (toolchain="colognechip"), ne kroz
   nextpnr/peppercorn.
2. **Jedini put kojim Patrick stvarno zatvara gigabit je SerDes (`gatemate1000basex`)**:
   PCS radi na **62,5 MHz half-clock domenama** s 20-bitnim riječima — točno unutar
   raspona koji GateMate fabric stvarno rutira (mi smo izmjerili ~60 MHz). Na ULX5M-GS
   **neprimjenjivo bez izmjene hardvera**: KSZ9031RNX je RGMII-only, SerDes nije spojen
   na PHY.
3. **trabucayre/GateMate_demos grana `ulx5m_ethernet` je NAŠA ploča** — kopija
   Patrickovog PHY-a s popravkom rx_ctl dekodiranja (obje DDR ivice AND-ane), driver
   `eth_refclk` iz clk25 (isti zaključak kao TASK-4961), default toolchain colognechip.
   `~/app/litex-rgmii-ulx5m/` je već lokalni fork toga.
4. **mmicko nema GbE dizajn**: grana `ulx5m-gs` u njegovom litex-boards forku je samo
   platforma (SDRAM/SD/gumbi, bez etherneta); nextpnr fork je iz 2024.
5. **p_r 4.2 skinut i radi u kontejneru** (`~/Programs/cc-toolchain-linux`). Dvije zamke
   nađene pri prvom pokretanju: p_r FATALNO odbija `SLEW` na ulaznim pinovima (peppercorn
   to ignorira) i naš custom PHY (`phy_rgmii_gatemate.py`) pada u p_r ruteru
   ("IDDR input pin from IO_SEL could not be routed") — Patrickov PHY s eksplicitnim
   CC_IBUF→IDDR lancem prolazi.

## 1. Odgovori na ključna pitanja iz zadatka

| # | Pitanje | Odgovor (iz koda, ne nagađanje) |
|---|---|---|
| 1 | Kako je Patrick riješio 125 MHz timing? | **Nije.** Constraint je spušten na 25 MHz (`tx/rx_clk_freq = 25e6` u `liteeth/phy/gatematergmii.py`, LiteX `soc.py` iz toga radi `add_period_constraint`). P&R je proprietarni `p_r`, bez formalnog dokaza 125 MHz. |
| 2 | dw=32 umjesto dw=8? | Ne. `dw = 8` (isti kao ecp5rgmii). |
| 3 | Viši sys_clk? | Ne. Olimex target 24 MHz, trabucayre ULX5M-GS **20 MHz**. |
| 4 | Custom async FIFO bez gray-brojača? | Ne. Stock LiteEth MAC, stock `stream.AsyncFIFO`. |
| 5 | CC_IBUF/CC_OBUF delay? | **Da** — jedino stvarno GateMate-specifično: `CC_IBUF(DELAY_IBF=n)` na rx_ctl/rx_data, `CC_OBUF(DELAY_OBF=n)` na TXC, s tablicom ps/tap po perf-modu (speed/economy/lowpower × best/typ/worst). Defaulti su **0** — skew rješava PHY (RTL8211E TXDLY/RXDLY strap; kod nas KSZ9031 pad-skew registri). |
| 6 | Dedicated clock pin za RXC? | Ne. trabucayre koristi isti IO_EB_A7 kao mi. TX domena = RX domena (`cd_eth_tx.clk = cd_eth_rx.clk` kad se ne da `tx_clk`). |
| 7 | Seed / nextpnr flagovi? | Bespredmetno — flow je `p_r -ccf ... -cCP -A 1 -i ..._synth.v -lib ccag`, a ne nextpnr. |

## 2. Što točno radi `gatematergmii.py` (pu-cc/liteeth, commit fc31236, 2025-06-29)

- TX: `self.sync` (eth_tx) registri → `DDROutput` → `CC_OBUF(DELAY_OBF=taps, SLEW=fast)`.
- RX: `CC_IBUF(DELAY_IBF=taps)` → `DDRInput` → registri; rising=LSB nibble, falling=MSB.
  **Gigabit-only dekodiranje** (na 10/100 RGMII duplicira nibble po ivicama — dekoder bi
  davao smeće; inband_status je zakomentiran).
- CRG: RXC ide direktno u `cd_eth_rx` (bez eksplicitnog BUFG-a — p_r sam promovira
  taktove), TXC se generira `DDROutput(i1=0,i2=1)` iz eth_tx domene.
- Jedina druga izmjena u grani: `liteeth/gen.py` dobiva `colognechip` vendor.

## 3. Zašto SerDes put (gatemate1000basex) zatvara timing, a RGMII ne

`gatemate_1000basex.py` (commit 0b4e2c8): PCS 1000Base-X nad GateMate SerDes-om,
`cd_eth_tx_half`/`cd_eth_rx_half` na **62,5 MHz**, 20-bitne 8b10b riječi, PLL iz
100/125 MHz refclka. Fabric nikad ne vidi 125 MHz — SerDes hardver odrađuje serijalizaciju.
Naš izmjereni strop fabrica (~52–65 MHz post-route) je točno ispod 62,5 — zato ovaj
pristup na GateMateu uopće postoji. Za ULX5M-GS bi tražio PHY sa SGMII/1000Base-X
(hardverska izmjena; M2 teritorij), pa je za GS mrtav.

## 4. p_r pokusi na našim dizajnima (danas)

| Pokus | Ishod |
|---|---|
| `target_eth.py --gbe --toolchain colognechip` (naš custom PHY) | **FATAL u ruteru**: "IDDR input pin from IO_SEL 8414_1 could not be routed" — naš PHY hrani IDDR bez eksplicitnog CC_IBUF lanca i dijeli pad s drugom logikom. |
| `build.py --with-etherbone --toolchain colognechip` (Patrickov PHY, trabucayre target) 1. pokušaj | **FATAL**: "SLEW defined at input buffer!" — platforma je imala `SLEW=fast` na rx_ctl/rx_data/mdio ulazima (peppercorn to šutke guta). Popravljeno u `intergalaktik_ulx5m_gs_platform.py` (slew samo na izlazima) + **ispravljen eth_refclk pin IO_EA_A8 → IO_EB_A3** (hardverski dokazan u TASK-4961). |
| 2. pokušaj (nakon popravaka) | **PROŠAO do bitstreama** (98 s, `intergalaktik_ulx5m_gs_platform_00.cfg.bit`, 688 210 B; 10 IDDR, 6 ODDR, 1 PLL, 2 GLB, BRAM 21,9 %). |

### 4.1 p_r STA presuda za eth domenu (etherbone, dw=8, cpu None, bez SDRAM-a)

- `-tp 800` ispisao 23 004 puta; **CLK 5744 = `eth_rx_clk`** (provjereno mapiranjem
  komponente 5744 → `_09247_` → `CLK=eth_rx_clk` u `_synth.v`; 3075 od 4811 DFF-ova
  je u eth domeni — s dw=8 **cijeli UDP/IP stack živi na RXC-u**).
- Najgori put u eth domeni: **40,07 ns → 24,95 MHz** (worst corner, default effort).
  Za gigabit treba 8 ns — manjak **5,0×**.
- **Zašto p_r ne pokušava bolje: LiteX mu nikad ne kaže.**
  `litex/build/colognechip/colognechip.py:157 add_period_constraint() = pass` —
  period constraints se za colognechip toolchain BACAJU. 24,95 MHz je dakle
  neoptimizirani rezultat, a Patrickov `rx_clk_freq=25e6` znači da ni jedan alat u
  cijelom lancu nikad nije ni pokušao zatvoriti 125 MHz za RGMII granu.
- p_r sa svim speed opcijama (`-sp -s -dC -mXA -mMA -AF`): **25,01 MHz** — nikakav
  dobitak. Razlog je strukturan: najgori put ima **17 CPE razina** (~8,5 ns čiste
  CPE-logike i bez ijednog ps rutiranja), a 125 MHz dopušta 8 ns ukupno. LiteEth
  dw=8 stack u eth domeni na GateMateu **ne može** na 125 MHz ni teoretski.

## 4.2 Konačna presuda

**1 Gbps RGMII na ULX5M-GS s postojećim kodom s GitHuba NE POSTOJI.** Dokazni lanac:

1. nextpnr/peppercorn: 52–65 MHz post-route (TASK-4961).
2. p_r (Patrickov vlastiti flow, njegov PHY, trabucayreov target za našu ploču):
   24,95–27,8 MHz, jer mu nitko constraint ni ne preda (`add_period_constraint=pass`)
   a i Patrickov PHY traži samo 25 MHz.
3. Dubina logike (17 CPE razina > 8 ns) čini 125 MHz nemogućim neovisno o P&R alatu.
4. Patrickov jedini stvarni gigabit (`gatemate1000basex`) radi jer fabric vrti na
   62,5 MHz uz SerDes — hardver koji ULX5M-GS nema spojen na KSZ9031.

**Put naprijed (novi RTL, ne postojeći kod):** RGMII front držati trivijalnim
(IDDR + 2-bajtni gearbox, jedina logika na 125 MHz su IO ćelije + par FF-ova),
cijeli MAC/UDP stack spustiti na **62,5 MHz s dw=16** — po uzoru na arhitekturu
1000basex PHY-a. Fabric na ~62 MHz je na rubu dokazanog (nextpnr 60–65 MHz s dubokom
logikom; s plitkom logikom realno). To je dizajnerski zadatak za nas, ne kloniranje.

Odgovor na Goranovo pitanje o "DDR ili neki drugi buffer umjesto async FIFO-a":
async FIFO nije uzrok — uzrok je što s dw=8 SVA logika (MAC, ARP, IP, ICMP, UDP,
depacketizeri od 17+ razina) živi na 125 MHz RXC-u. Zamjena FIFO-a ne mijenja ništa;
spuštanje takta uz širi datapath (gearbox u IO sloju) mijenja sve.

## 5. Noviji nextpnr (za usporedbu)

oss-cad-suite je v20260313; od tada u nextpnr GateMate archu: static placer opcija
(2026-05-05), clock-router i za RAM taktove (2026-08-12), "reserve one level further
uphill" (2026-08-13), MULT packing popravci. Ništa od toga ne obećava 2× na rutiranju
gray-brojača — issue-tracker nema otvorenu temu o routing-delay deficitu ove klase.
Vrijedi probati novi nightly, ali očekivanje je marginalno poboljšanje, ne 60→125 MHz.

## 6. Zaključak za ULX5M-GS

- Put do "gigabit RADI" na ovoj ploči ide kroz **p_r + Patrickov/trabucayreov dizajn**,
  uz svijest da ni tamo 125 MHz nije formalno zatvoren — presuda je empirijska
  (link + promet na stvarnom hardveru).
- Ako p_r build prođe: flash preko Pi-ja (`test_script/flash_and_test_remote.sh`
  prilagođen etherbone dizajnu), ping + link-speed provjera.
- Ako i p_r pokaže strop < 125 MHz: na GS-u s otvorenim/postojećim kodom gigabit
  ostaje nedostižan; alternativa je fabric-gearbox na 62,5 MHz (2 bajta/takt) —
  ali to NIJE postojeći kod na GitHubu, to je novi dizajn.

## 7. Empirijska potvrda na hardveru (2026-09-21 ~21:15)

Pi se vratio online pa je bitstream i **testiran na ploči**: `task4962_etherbone.cfg.bit`
(md5 `6346393fb68a6b9920d8c0e6e831a99c`, 711 729 B) flashan u SRAM preko dirtyJtag
("Load SRAM via JTAG: 100% / Done"), 30 s za autoneg, zatim s Pi-ja:

```
ping -c 8 192.168.10.212  ->  100% packet loss, Destination Host Unreachable
ip neigh                  ->  192.168.10.212 INCOMPLETE   (nema ni ARP odgovora)
```

Točno kako STA predviđa: RXC na gigabitu je 125 MHz, a eth-logika se smiruje tek na
~25–45 MHz — dizajn ne dekodira ni ARP. Negativan rezultat time ima tri neovisna
dokaza (nextpnr mjerenja, p_r STA, hardver).
