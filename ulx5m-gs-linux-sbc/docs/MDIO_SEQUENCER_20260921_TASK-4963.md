# HW MDIO sequencer + toolchain 20260920 + ping test — TASK-4963, 2026-09-21

## Što je napravljeno

1. **`gateware/mdio_sequencer.py`** — čisti hardverski clause-22 MDIO write engine
   (`MDIOWriteSequencer`). `LiteEthPHYMDIO` je CSR bit-bang i u dizajnu bez CPU-a
   je mrtav teret; ovaj modul nakon PHY reseta + 10 ms settle sam piše:
   - reg 9 = 0x0000 (bez 1000BASE-T advertisementa)
   - reg 4 = 0x0101 (samo 100BASE-TX FD)
   - reg 0 = 0x1200 (AN enable + restart)

   PHYAD strap KSZ9031 nije dokumentiran za ovu reviziju ploče → sekvenca se
   ponavlja na svih 8 mogućih adresa (PHYAD[2:0]); KSZ9031 je jedini na busu,
   pisanje na nepostojeću adresu se ignorira. MDC 1 MHz, MDIO mijenja se u
   niskoj polovici MDC-a, Hi-Z između frameova i nakon završetka.
   **MMD2 pad-skew registri se NE diraju** (ubijaju TX, v. LITEETH_INTEGRATION.md).

2. **`gateware/phy_rgmii_gatemate.py`** — novi parametar `mdio_sequencer_clk_freq`:
   kad je zadan, umjesto `LiteEthPHYMDIO` instancira se sequencer (samo jedan
   smije voziti mdc/mdio padove). `target_eth.py` ga pali za 100M build.

3. **`sim/tb_mdio_sequencer.py`** — testbench: sample na rising edge MDC-a
   (točno kao PHY), reassemblira frameove, provjerava broj, polja, redoslijed
   reg9→reg4→reg0 po adresi, Hi-Z između frameova, i da ništa ne izlazi dok
   je PHY reset aktivan. **PASS 9/9.**

4. **LED dijagnostika** (`status_leds.py`): build-ID zamijenjen korisnijim:

   | LED | Značenje |
   |-----|----------|
   | 7 | heartbeat ~1 Hz |
   | 6 | reset released (sticky) |
   | 5 | TX aktivnost |
   | 4 | RX aktivnost |
   | 3 | in-band speed MSB (svijetli = 1G) |
   | 2 | in-band speed LSB (sama = **100M — očekivano dobro stanje**) |
   | 1 | link up (in-band status) |
   | 0 | **MDIO sequencer done** |

   Sve dobro = 7 (treperi), 6, 2, 1, 0 svijetle; 3 ugašena.

5. **Toolchain** — `~/Programs/oss-cad-suite-20260920/` (Yosys 0.69+75,
   nextpnr-himbaechel 0.11.1-30 s gatemate uarch-om, gmpack). Build čist,
   exit 0, timing bez negativnog slacka (eth_rx max delay 15,3 ns @ 40 ns).

## Rezultat testa na hardveru (2026-09-21 ~19:35)

- Flash u SRAM preko dirtyJtag s Pi-ja (192.168.10.14): **OK** (100 %, Done), 2×.
- `ping -c 5 192.168.10.212` s Pi-ja nakon 30 s: **FAIL** — 100 % loss,
  `ip neigh` = INCOMPLETE/FAILED. Ploča ne odgovara ni na ARP ni na UDP echo
  (port 7000, probano i s dell-home kontejnera).
- Switch port speed: nije očitljiv daljinski (switch nije upravljiv iz mreže;
  Pi je na switchu, ne izravno na ploči).
- tcpdump na Pi-ju nemoguć (sudo NOPASSWD samo za openFPGALoader/uhubctl).

## Kako LED-ice bisektiraju kvar (treba fizički pogled)

| Viđeno | Zaključak |
|--------|-----------|
| LED0 ugašena | sequencer nije završio → bug u FSM-u / reset visi |
| LED0+, LED1 ugašena | AN nije završio: MDIO ne dopire do PHY-a (el. problem, MDC/MDIO zamijenjeni?) ili link partner ne surađuje |
| LED0+, LED1+, LED3 svijetli | PHY i dalje na 1G → MDIO writes nisu sjeli |
| LED0+, LED1+, LED2 sama | **AN = 100M uspio**; kvar je u RGMII datapathu — prvi osumnjičeni RX capture na fabric-routanom RXC (IO_EB_A7, skew), zatim TX |

Ako je zadnji red: sljedeći korak je RXC skew (pokušati `rxc_global=True` uz
seed sweep, ili CC_IBUF DELAY taps na rx padovima), ne MDIO.

## Grane / commitovi

Grana `mdio-100m-autoneg` u ovom repou.
