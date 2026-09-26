# ULX5M-GS: izvedivost 1 Gbps Etherneta (TASK-4961, 2026-09-21)

Autor: Grga (REGOČ Designer) · Projekt: PRJ-033 (pripada FPGA/ULX5M-GS radu — ne pretincu)
Repo: `/home/klaudio/app/litex-eth-ulx5m-gs/litex-eth-ulx5m-gs`
Alati: oss-cad-suite (`nextpnr-0.10-45-g98c18d7`), LiteX `52f183ef6`, LiteEth `9654767`

---

## 0. Sažetak u tri rečenice

1. **GbE se danas ne zatvara vremenski**: traži 125 MHz, izmjereno je **60,45 MHz (RX)** i
   **61,93 MHz (TX)** nakon rutiranja — manjak **≈ 2,0×**. Uskim grlom NISU RGMII izlazi ni
   RXC pin, nego **gray-brojači LiteEth-ovih async FIFO-a**, i to pretežno **rutiranjem**
   (12,96 ns od 16,54 ns = 78 %).
2. **Postoji stariji, teži kvar koji blokira i 100 Mbps**: KSZ9031-u **nitko ne daje
   referentni takt**. Oscilator X1 i njegov serijski otpornik R104 su na ULX5M-GS-u **oba
   `dnp`**, a pin XI visi na netu `ETH_CLK` koji ide **isključivo na FPGA pin IO_EB_A3** —
   koji dosadašnji gateware nikad nije vozio. To objašnjava i „ploča je nijema" (TASK-4959)
   i MDIO koji vraća 0x0000.
3. Isporučeno: zastavica `--gbe` (ukupno 29 redaka izmjene) i **pogon 25 MHz referentnog
   takta na IO_EB_A3** (`--no-phy-refclk` gasi). Zadani 100 Mbps build s refclkom prolazi
   vremenski i daje bitstream (453 676 B, md5 `fdc72cb175520564f72b82edb49215f0`) — to je
   ono što treba prvo staviti na ploču. GbE build prolazi na sjemenu 7 **bez** refclka;
   s refclkom ruter pada, pa gigabit ostaje mjerni rezultat, ne isporuka.

---

## 1. Što je izmjereno (nextpnr, post-route, worst corner)

| Build | eth_tx (PLL#1) | eth_rx (RXC) | sys (PLL#2) | ishod |
|---|---|---|---|---|
| 100M baseline (prije zakrpe), seed 7 | 57,61 MHz @ 25 | 79,80 MHz @ 25 | 30,92 MHz @ 16 | PASS |
| 100M nakon zakrpe (regresija), seed 7 | 52,80 MHz @ 25 | 68,67 MHz @ 25 | 27,85 MHz @ 16 | PASS |
| **GbE `--gbe`, seed 7** | **61,93 MHz @ 125** | **60,45 MHz @ 125** | 29,13 MHz @ 16 | **FAIL** |

Za GbE je potrebno 125 MHz u obje PHY-domene. Manjak: **125 / 61,93 = 2,02×** (TX) i
**125 / 60,45 = 2,07×** (RX).

### 1.3 Tablica mjerenja (nextpnr, worst corner, `--freq 125`)

| Sjeme | faza | eth_tx (PLL#1 @125) | eth_rx (RXC @125) | sys (PLL#2 @16) | ishod PnR |
|---|---|---|---|---|---|
| 7 | nakon plasiranja | 104,09 | 107,17 | 37,46 | — |
| 7 | **nakon rutiranja** | **61,93 FAIL** | **60,45 FAIL** | 29,13 PASS | rc=0 |
| 1 | nakon plasiranja | 115,59 | 103,71 | 38,31 | — |
| 1 | **nakon rutiranja** | **59,15 FAIL** | **62,89 FAIL** | 28,92 PASS | rc=0 |
| 3 | nakon plasiranja | 126,50 PASS | 94,86 | 38,30 | — |
| 3 | **nakon rutiranja** | **52,82 FAIL** | **65,50 FAIL** | 27,37 PASS | rc=0 |
| 11 | nakon plasiranja | 123,38 | 108,52 | 40,08 | **rc=255 — ruter pao** |

Dvije stvari se vide odmah:

1. **Sjeme ne zatvara jaz.** Nakon rutiranja je raspon 52,8–65,5 MHz; traži se 125. Nema
   sjemena koje je i blizu.
2. **Plasiranje laže.** Procjena nakon plasiranja (95–127 MHz) je 1,7–2,4× optimističnija
   od stvarnog rezultata nakon rutiranja. Tko gleda samo prvu tablicu iz nextpnr-a, misli
   da je gigabit nadohvat ruke. Nije.

### 1.4 Cijena globalnog takta na RXC-u

`rxc_global=True` znači da Yosys smije staviti `CC_BUFG` na RXC. Dokaz da to prolazi
(Kosjenkin nalaz, ovdje neovisno potvrđen na ovom dizajnu):

```
100 Mbps build (clkbuf_inhibit):   Inserting CC_BUFG on ...crg_gatematepll1_clkout[0]
                                   Inserting CC_BUFG on ...crg_gatematepll0_clkout[0]
                                        2   CC_BUFG
GbE build     (rxc_global):        Inserting CC_BUFG on ...eth_rx_clk[0]        <---
                                   Inserting CC_BUFG on ...crg_gatematepll1_clkout[0]
                                   Inserting CC_BUFG on ...crg_gatematepll0_clkout[0]
                                        3   CC_BUFG
```

Build prolazi do bitstreama — **CC_BUFG na ne-clock pinu IO_EB_A7 ne ruši nextpnr.**
Ali ima cijenu: treći globalni takt troši dodatni GLBOUT i sjeme 11 zbog toga **više ne
rutira**:

```
Info:   failed to find a route using dedicated resources. GLBOUT0 -> X111Y129/CPE.CLK_int
ERROR:  Failed to route arc 654.0 of net 'crg_gatematepll1_clkout' ...
```

Dakle stara zabilješka („CC_BUFG na RXC-u ruši nextpnr") je **netočna kao uzrok**, ali je
opažena krhkost bila stvarna — samo je uzrok bio nedostatak globalnih taktnih resursa, ne
sam pin.

### 1.1 Gdje točno pada

Kritični put NIJE RGMII serdes ni DDR na padovima — u obje domene to su **gray-brojači
LiteEth-ovih async FIFO-a na granici MAC-a**:

```
eth_rx (16,54 ns, treba ≤ 8,00 ns):   3,58 ns logika + 12,96 ns rutiranje (78 %)
   mac_core_cdc_graycounter0_q[3] -> ... -> mac_core_cdc_graycounter0_ce -> FF
eth_tx (16,15 ns, treba ≤ 8,00 ns):   5,45 ns logika + 10,70 ns rutiranje (66 %)
   mac_core_txdatapath_cdc_asyncfifo_re -> graycounter1_q_next_binary -> BRAM ADDRB0
```

Dakle: **problem je rutiranje/placement, ne silicij i ne odabir pina.** Logika sama
(3,6–5,5 ns) stala bi u 8 ns proračun; 11–13 ns rutiranja je ono što ubija.

### 1.2 Pin RXC (IO_EB_A7) NIJE ograničenje

Kosjenkin nalaz da CC_BUFG na ne-clock pinu radi — potvrđen u praksi: build s
`rxc_global=True` (bez `clkbuf_inhibit`) prolazi kroz nextpnr do bitstreama, bez pada.
Domena `eth_rx_clk` pritom drži 60,45 MHz, što je **isti red veličine** kao PLL-om vođena
`eth_tx` domena (61,93 MHz). Da je USR_GLB put kriv, RX bi bio dramatično lošiji od TX-a.
Nije. Pin je oslobođen sumnje.

---

## 2. Tvrdi hardverski nalaz: PHY nema referentni takt

Provjereno **izravno iz sheme** (`/home/klaudio/app/ulx5m-gs-hw/hardware`,
alat `regoc_system/tools/kicad_netlist.py`):

```
### ETH_CLK  (3 pina)
    R104.2   ~                      passive
    U14.46   XI                     input          <- KSZ9031 referentni takt
    U4.E16   IO_EB_A3               bidirectional  <- FPGA

X1  (ECS-2520MV-250-xx, 25 MHz)  -> (dnp yes)   ethernet.kicad_sch:23337
R104 (27 R, X1 -> ETH_CLK)       -> (dnp yes)
tekst u shemi: "Use EB-A3 as clock source. Or use EB-A3 as input and place X1, C118, R104"
```

Dakle jedini mogući izvor 25 MHz za PHY je **FPGA preko IO_EB_A3**. Dosadašnji gateware ga
ne vozi:

```
$ grep -c "IO_EB_A3" build/eth/gateware/intergalaktik_ulx5m_gs.ccf   ->  0
```

Bez takta na XI KSZ9031-ov interni PLL ne starta: nema linka, nema RXC-a, MDIO čita
0x0000. To je točno opaženo ponašanje iz TASK-4959 i iz starog „MDIO mystery" traga.

**Usput nađena greška u sestrinskom projektu:** `litex-rgmii-ulx5m` vozi `eth_refclk` na
`IO_EA_A8` (`intergalaktik_ulx5m_gs_platform.py:84`), a taj pin je na netu `N$0061` koji
ima **samo taj jedan pin** — nigdje ne ide. Taj projekt, dakle, također nikad nije taktirao
PHY.

### 2.1 Ostali nalazi iz sheme (bitni za GbE)

| Signal | KSZ9031 | FPGA | napomena |
|---|---|---|---|
| `RGMII_REFCLK` | pin 41 `CLK125_NDO/LED_MODE` | **IO_EB_B8** | PHY može dati **125 MHz** natrag FPGA-i; isti net nosi i strap `LED_MODE` (R66 = 4k7 na +1V8) |
| PHYAD1 / PHYAD0 | pin 15 / 17 | LEDY / LEDG | R74/R75 (pull-up) su `dnp`, R84/R85 = 4k7 na GND → **PHYAD = 0** |
| MODE[3:0], CLK125_EN, PHYAD2 | pinovi 27/28/31/32/33/35 | preko R97–R102 = **27 Ω serijski** prema FPGA-i | ovo **nisu** strap otpornici — vrijednost strapa određuju interni pull-ovi KSZ9031 (default = RGMII, CLK125 uključen) |

Ranija bilješka koja je R66–R85 pripisala MODE/CLK125_EN strapovima **nije točna**; ti
otpornici sjede na `RGMII_REFCLK`, `LEDY` i `LEDG`, a RX linija ima samo 27 Ω serijske.

---

## 3. Što je promijenjeno u kodu (29 + 15 redaka)

Sve je iza zastavica; zadano ponašanje repozitorija (100 Mbps) ostaje netaknuto.

### 3.1 `--gbe` — brzinski prilagodljiv RGMII

| Datoteka | Promjena |
|---|---|
| `gateware/target_eth.py` | `gbe=False` parametar; `--gbe` CLI; `fixed_100m = not gbe`, `with_dynamic_link = gbe`, `rxc_global = gbe`, `line_rate_1g = gbe`; period constraint RXC-a 8 ns umjesto 40 ns; `--gbe` diže `tx_clk_freq` na 125 MHz |
| `gateware/phy_rgmii_gatemate.py` | `line_rate_1g` parametar (postavlja `tx_clk_freq`/`rx_clk_freq` na 125 MHz) |
| `gateware/crg.py` | nula — `tx_clk_freq` je već bio parametar |

Mehanizam je LiteEth-ov vlastiti: `LiteEthRGMIITXClock(external_tx_clk=True)` pri
`link_1G` propušta 125 MHz kao TXC, a pri `link_100M` dijeli ga s 5 → 25 MHz. Brzina se
bira iz RGMII in-band statusa, bez MDIO-a. Isti bitstream, dakle, pokriva 10/100/1000.

### 3.2 Pogon referentnog takta PHY-ja (uključeno po defaultu)

| Datoteka | Promjena |
|---|---|
| `gateware/ulx5m_eth_platform.py` | novi IO `("eth_refclk", 0, Pins("IO_EB_A3"), SLEW=fast, DRIVE=3)` |
| `gateware/crg.py` | `self.clk25 = clk25` (izloženo cilju) |
| `gateware/target_eth.py` | `self.comb += platform.request("eth_refclk").eq(self.crg.clk25)`; `--no-phy-refclk` gasi |

Ovo je ispravak koji **mora ići i u 100 Mbps build** — bez njega PHY ne radi uopće.

---

## 4. Vanjski forkovi — što je ondje stvarno

| Izvor | Nalaz |
|---|---|
| `pu-cc/liteeth`, grana **`gatematergmii`** | `liteeth/phy/gatematergmii.py` (Patrick Urban, Cologne Chip) — **gigabitni** RGMII PHY za GateMate: bajt po taktu, DDR, bez 10/100 nibble-geara |
| isti file | **GateMate IMA programabilno kašnjenje na padu**: `CC_IBUF(DELAY_IBF=n)` i `CC_OBUF(DELAY_OBF=n)`, do 16 stepenica; u SPEED modu 30/38/50 ps (best/typ/worst) → **max ≈ 0,5–0,8 ns**. Komentar u našem repozitoriju („GateMate nema programabilni delay primitiv") je **netočan** |
| `pu-cc/litex-boards`, grana `olimex_gatemate_ethio` | referentna uporaba: `tx_delay = 0.0`, `rx_delay = 0.0`, uz komentar *„RTL8211E adds 2ns TXDLY=1 / RXDLY=1"* — 2 ns RGMII pomak radi **PHY**, ne FPGA. Taktiranje: `tx_clk=None` ⇒ `cd_eth_tx.clk = cd_eth_rx.clk` (**TXC izveden iz PHY-jevog RXC-a**, bez 125 MHz PLL-a) |
| `pu-cc/litex`, grana `gatemate-oddr-fix` | popravak `CC_ODDR`/`CC_IDDR` lowering-a (`i_DDR = clk` + re-timing `CC_DFF`). **Već je u našem LiteX-u** (`litex/build/colognechip/common.py:108` ima `i_DDR = clk` i oba DFF-a) — nije otvoren problem |
| `pu-cc/liteeth`, grana **`gatemate1000basex`** | `liteeth/phy/gatemate_1000basex.py` (477 redaka) — gigabit preko **SerDes-a i 1000BASE-X**, potpuno zaobilazi RGMII i 125 MHz fabric. Traži SFP/optiku, ne KSZ9031 |
| `mmicko` | **ima** fork `mmicko/nextpnr` (i `yosys`, `litex`, `litex-boards`) — tvrdnja „nema javni fork nextpnr-a" ne stoji; je li fork ičim ispred upstreama nije provjereno |

Zaključak: **postoji** javni gigabitni RGMII PHY za GateMate (pu-cc), samo nije za ovu
ploču i nije mu nigdje pokazana zatvorena vremenska analiza na 125 MHz.

---

## 5. Što bi trebalo da GbE stvarno proradi

Poredano po omjeru učinka i rizika.

### P0 — bez ovoga ništa ne radi (ni 100M)
1. **Voziti 25 MHz na IO_EB_A3.** Isporučeno u ovoj zakrpi. Treba potvrditi na ploči:
   MDIO očitanje registara 0x02/0x03 na PHYAD = 0 mora dati `0x0022` / `0x1620`.
   Dok je MDIO 0x0000, svaka rasprava o 100 vs. 1000 Mbps je bespredmetna.

### P1 — vremensko zatvaranje 125 MHz (manjak ≈ 2,0×)
2. **Novi nextpnr.** Lokalni je `nextpnr-0.10-45-g98c18d7`. Upstream ima control-set-aware
   HeAP legaliser (#1678) i iterativni `reassign_bridges` (#1697), oboje mjeri upravo ono
   što nas ubija (rutiranje FF-grupa). Ovo je najjeftiniji potez s najvećim potencijalom.
3. **Skratiti gray-brojače LiteEth-ovih async FIFO-a.** Kritični put je
   `graycounter_q -> ce -> q_next_binary -> BRAM ADDRB0`. Plići FIFO (manje bitova u
   gray-brojaču) skraćuje i logiku i rutiranje.
4. **Seed sweep je obavezan, ne kozmetika.** Raspon nakon plasiranja: eth_tx
   115,6–126,5 MHz, eth_rx 94,9–108,5 MHz (sjemena 1/3/11). Jedno sjeme (3) čak *prolazi*
   125 MHz na TX-u nakon plasiranja — pa padne u ruteru.
5. **Probati timing-driven ripup** (`--router2-tmg-ripup`), jer je 66–78 % kritičnog puta
   rutiranje.

### P2 — propusnost, a ne samo takt
6. Čak i kad se 125 MHz zatvori, `sys` na 16 MHz uz `dw=8` nosi **16 MB/s**, a gigabit
   traži **125 MB/s**. Izmjereni strop `sys` domene je **29–42 MHz**. Dakle:
   - **sustavni put do punog gigabita ne postoji pri `dw=8`.** Treba `dw=32` uz `sys`
     ≥ 31,25 MHz (izmjereno 29,1–42,5 MHz → tijesno, ali u dometu) ili `dw=64` uz ≥ 15,6 MHz.
   - S `dw=8` i `sys` = 16 MHz gigabitni link može *stajati* i primati kratke okvire, ali
     async FIFO se prelije usred okvira dugog 1500 B. Ovo treba mjeriti, ne pretpostavljati.

### P3 — RGMII kašnjenja (2 ns)
7. **Ne raditi to u FPGA-i.** `CC_OBUF DELAY_OBF` daje najviše ≈ 0,8 ns — premalo.
   Cologne Chip u vlastitoj referenci ostavlja 0 i traži da **PHY** doda 2 ns
   (`RTL8211E: TXDLY=1 / RXDLY=1`). KSZ9031 ekvivalent je RGMII-ID preko MMD registara.
8. **Alternativa bez MDIO-a:** `CC_PLL` CLK90 na 125 MHz = točno 2 ns pomaka za TXC.
   `GateMatePLL.create_clkout(..., phase=90)` to već podržava. Ovo je čisto unutar FPGA-e
   i ne dira pad-skew registre (koji su prošli put ubili TX).

### Ne raditi
- ❌ pisati pad-skew registre (MMD2 dev2 reg8) — ranije je ubilo TX;
- ❌ voziti IO_EB_B8 kao izlaz — na njemu je `LED_MODE` strap (4k7 na +1V8) i PHY-jev
  `CLK125_NDO`; smije biti samo ulaz;
- ❌ `eth_refclk` na `IO_EA_A8` — taj pin nigdje ne ide (net `N$0061`).

---

## 7. Što je pokušano da se jaz zatvori (i kako je prošlo)

| Pokušaj | Rezultat |
|---|---|
| Sweep sjemena 7 / 1 / 3 na 125 MHz | 52,8–65,5 MHz nakon rutiranja — jaz ostaje ≈ 2× |
| Sjeme 11 | ruter pao: `Failed to route arc ... net 'crg_gatematepll1_clkout'` (GLBOUT0) |
| `--router2-tmg-ripup` (timing-driven ripup), sjeme 7 | **ne konvergira**: prekinut nakon **532 iteracije** s `overused=1..3` koji samo titra. Nije upotrebljiv na ovom dizajnu |
| `--gbe` + pogon refclka, sjeme 7 | ruter pao: `Failed to route arc 29.0 of net 'eth_rx_clk'` |

Zadnji redak je važan: **jedan dodatni IO pin (25 MHz na IO_EB_A3) dovoljan je da GbE
varijanta prestane rutirati na sjemenu 7.** Dizajn s tri globalna takta na 125 MHz je na
rubu routabilnosti — to nije „skoro gotovo", to je nestabilno.

### 7.1 Suprotno tome: 100 Mbps s refclkom prolazi bez muke

| Build | eth_tx | eth_rx | sys | ishod |
|---|---|---|---|---|
| **100 Mbps + pogon refclka (zadano nakon zakrpe)** | 58,08 @ 25 PASS | 63,09 @ 25 PASS | 26,62 @ 16 PASS | **rc=0, bitstream 453 676 B** |

```
$ grep IO_EB_A3 build/eth/gateware/intergalaktik_ulx5m_gs.ccf
Net "eth_refclk" Loc = "IO_EB_A3" | SLEW=fast | DRIVE=3;
$ md5sum intergalaktik_ulx5m_gs.bit
fdc72cb175520564f72b82edb49215f0
```

**To je bitstream koji vrijedi prvi isprobati na ploči** — prvi put uopće daje KSZ9031-u
referentni takt.

---

## 6. Kako ovo ponoviti

```bash
export OSS_CAD_SUITE=/home/klaudio/Programs/oss-cad-suite
export LXROOT=/home/klaudio/app/litex-rgmii-ulx5m
cd /home/klaudio/app/litex-eth-ulx5m-gs/litex-eth-ulx5m-gs
source ./env.sh                       # NE kroz cjevovod -- exporti se gube u podljusci

python3 gateware/target_eth.py --build                 # 100 Mbps (zadano) + refclk
python3 gateware/target_eth.py --build --gbe           # 1000 Mbps datapath, eth_tx = 125 MHz
python3 gateware/target_eth.py --build --gbe --no-phy-refclk   # bez pogona XI

# brojke po domenama:
grep -E "Max frequency" build/eth/gateware/../../..  # vidi build.log; zadnje 4 linije = nakon rutiranja
```

Za sweep sjemena bez ponovne sinteze:

```bash
nextpnr-himbaechel --json <build>.json --vopt ccf=<build>.ccf --device CCGM1A1 \
  --vopt out=x.txt --router router2 --timing-allow-fail --seed <N> --freq 125
```

### 6.1 Zamka u alatnom lancu koju treba znati

`litex/build/colognechip/peppercorn.py:73` ima **zakomentiran** redak:

```python
#pnr_opts += " --sdc {top}.sdc"
```

Generirani `.sdc` se, dakle, **nikad ne predaje nextpnr-u**. Jedino što stvarno stiže do
statičke analize je `--freq <najveći period constraint>`, koji se primjenjuje na sve
neograničene taktove. Posljedica: u 100 Mbps buildu cilj je `--freq 25`, pa su brojke
„57 MHz / 79 MHz" samo *dovoljno dobro za 25*, a ne strop. Tek `--gbe` (koji podigne
`--freq` na 125) natjera plasirač da stvarno pritisne — i tek tada se vidi pravi strop.
Ovo je razlog zašto naivna usporedba brojki iz dva builda vara.

---

## 8. Presuda

**1 Gbps na ULX5M-GS danas nije izvediv „minimalnim promjenama".** Kod jest minimalan
(29 redaka) i build prolazi, ali:

- vremenski je jaz **≈ 2,0×** (traži 125 MHz, dobiva 52,8–65,5 MHz), i **ne zatvara ga
  sjeme**, nego bi ga trebalo zatvoriti novim nextpnr-om i prekrajanjem LiteEth-ovih
  async FIFO-a — to više nisu minimalne promjene;
- čak i da se takt zatvori, `sys` na 16 MHz uz `dw=8` nosi 16 MB/s, a gigabit traži
  125 MB/s — treba i **širi datapath** (`dw=32`);
- a prije svega toga, **PHY na ovoj ploči trenutno uopće nema referentni takt**, pa ni
  100 Mbps ne radi.

**Redoslijed koji preporučam:** prvo IO_EB_A3 i dokaz da MDIO na PHYAD 0 vraća
`0x0022/0x1620`; zatim 100 Mbps na žici od kraja do kraja (ping + UDP echo); i tek onda
gigabit kao zaseban projekt s novim nextpnr-om, `dw=32` i CLK90 TXC-om.

Isporučena `--gbe` zastavica ostaje korisna kao **mjerni instrument** i kao pripremljena
infrastruktura — ne kao tvrdnja da gigabit radi.
