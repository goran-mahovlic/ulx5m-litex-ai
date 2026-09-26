# ULX5M-GS — flash i test čistog builda (TASK-4959, 2026-09-21)

Bitstream: `build/litex_eth_192.168.10.212.bit` — 438 085 B,
MD5 `d8a85c7cd440422f1caa565810b20077`, građen iz izvornog zip koda
(git `4ca4386` + `71f7e54` CRLF fix u `env.sh`), jedina izmjena
parametra: `--ip 192.168.10.212`.

## Sažetak

| Korak | Ishod |
|---|---|
| Prijenos na Pi (scp) | ✅ MD5 identičan na obje strane |
| SRAM flash `-c dirtyJtag … -r` | ✅ „Load SRAM via JTAG 100 % / Done", exit 0 (2× ponovljeno) |
| ICMP ping 192.168.10.212 s Pi-ja | ❌ 15/15 izgubljeno, `Destination Host Unreachable` |
| ARP razlučivanje | ❌ `ip neigh` = `INCOMPLETE` / `FAILED` |
| UDP echo :7000 | ❌ 4× `socket.timeout` |
| LED 7 (heartbeat) / LED 1 (link) | ⛔ nije provjerivo daljinski — traži oko na ploči |

Nalaz: ploča je nakon oba flasha **elektroničku nijema na mreži** — ne odgovara
ni na ARP, dakle nije riječ o IP/UDP sloju nego o tome da ni jedan valjan okvir
ne dolazi do preklopnika.

## Što je na strani gateware-a provjereno (i ISPRAVNO je)

Provjere nad generiranim Verilogom `build/eth/gateware/intergalaktik_ulx5m_gs.v`
i CCF-om iz istog builda:

| Provjera | Rezultat |
|---|---|
| IP ugrađen u bitstream | `32'd3232238292` = 192.168.10.212, 4 pojave (ARP sender, IP sender, IP rx filtar, ARP rx filtar) |
| MAC ugrađen | `45'd18566422200320` = 10:e2:d5:00:00:00, 3 pojave |
| MD5 isporučenog `.bit` = MD5 svježe sagrađenog `eth/gateware/*.bit` | identičan — isporučen je upravo taj build |
| TXC izlaz | `Net "eth_clocks_tx" Loc = "IO_EB_B2" \| SLEW=fast \| DRIVE=6` — FPGA **daje** TXC PHY-ju (PLL#1, 25 MHz, `crg.py` → `cd_tx25` → `DDROutput`) |
| RXC ulaz | `IO_EB_A7`, ne-clock-capable, fabric routing (po `GATEMATE_CLOCKING.md`) |
| PHY reset se otpušta | `eth_rst_n = ~(reset_storage \| ~counter_done)`; `reset_storage` default `1'd0`, `LiteEthPHYHWReset` daje impuls pa pušta → PHY **nije** trajno u resetu (isključeno kao uzrok) |
| SDC | `create_clock` samo za `clk25` i `eth_clocks_rx` — PLL izlazi namjerno nepokriveni (trap iz dokumentacije) |

Dakle: bitstream nije „krivo sagrađen", parametri su u njemu, pinmap odgovara
`docs/PINMAP.md`, PHY reset se otpušta.

## Što NIJE bilo moguće izmjeriti (i zašto)

1. **Snimanje prometa na žici.** Na Pi-ju `sudo` bez lozinke vrijedi samo za
   `openFPGALoader` i `uhubctl` (`sudo -n -l`). `tcpdump`, `ethtool` i `arping`
   nisu instalirani, a `AF_PACKET` sniffer traži root — lozinka iz skilla je
   odbijena (`sudo: 1 incorrect password attempt`). Zato se ne može razlučiti
   „FPGA ne šalje ništa" od „FPGA šalje okvire s lošim CRC-om koje preklopnik
   baca" — a to su dvije posve različite dijagnoze.
2. **LED-ovi.** Nema kamere ni udaljenog očitanja; LED 7 (~0,95 Hz heartbeat,
   `hb[23]` na 16 MHz) i LED 1 (link) su jedini izravni dokaz da sys takt radi i
   da je link gore. Bez toga se ne zna je li ploča uopće konfigurirana i budna.
3. **Hladni start ploče.** `off_on_FPGA.sh` gasi `1-1` port 2, a ondje
   **ništa nije priključeno** (`uhubctl`: `Port 2: 0100 power`, bez `connect`);
   DirtyJTAG je na `1-1.1` port 2. Napajanje FPGA ploče, dakle, ne visi o tom
   USB portu i ne može se ciklirati odavde.
4. **Je li mrežni kabel FPGA ploče uopće u istom preklopniku** kao Pi `eth0`
   (Pi vidi `192.168.10.1` i `192.168.10.200`, pa njegova strana radi).

## Preostale hipoteze, poredane

1. **RGMII vremenski odnos (najvjerojatnije).** `phy_rgmii_gatemate.py` nema
   DELAYG ekvivalent — GateMate ga nema. Ako TXD/TXC skew promaši prozor
   KSZ9031-a, PHY prima smeće i na žicu ne izađe ni jedan valjan okvir. Simptom
   je točno ovaj: potpuna tišina, bez ijednog ARP odgovora.
2. **Link nikad nije uspostavljen** (PHY ne vidi referencu/strapove kako se
   očekuje, ili kabel nije spojen). Razlučivo jednim pogledom na LED 1.
3. **Bring-up hang PLL-a.** `crg.py` sam upozorava: LiteX-ov `GateMatePLL`
   ostavlja `USR_PLL_LOCKED_STDY` nespojenim i izvodi `locked` iz nestabilnog
   `USR_PLL_LOCKED` — dokumentirani, o sjemenu ovisan zastoj pri podizanju.
   Razlučivo LED-om 7: ako heartbeat ne trepće, sys takt ne radi.

## Sljedeći korak koji odbija hipoteze

Jedan pogled na ploču razdvaja sve tri:

- LED 7 ne trepće → hipoteza 3 (PLL/reset), gateware nikad nije proradio.
- LED 7 trepće, LED 1 ugašen → hipoteza 2 (link/PHY/kabel).
- LED 7 trepće, LED 1 svijetli → hipoteza 1 (RGMII timing), i tada ima smisla
  ulagati u `tcpdump` na Pi-ju (traži root) ili u pomak TXC faze.

## Kako se ovo reproducira

```bash
scp build/litex_eth_192.168.10.212.bit fpga-klaudio@192.168.10.14:/home/fpga-klaudio/FPGA/
ssh fpga-klaudio@192.168.10.14 \
  'cd /home/fpga-klaudio/FPGA/ && sudo -n /usr/local/bin/openFPGALoader -c dirtyJtag litex_eth_192.168.10.212.bit -r'
ssh fpga-klaudio@192.168.10.14 'sleep 60; ping -c 10 -W 2 192.168.10.212; ip neigh show 192.168.10.212'
```
