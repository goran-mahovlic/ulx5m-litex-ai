# A2: `CC_IDDR` na die 1B ne vraća podatke (kratko + ponovljiv test)

**30.09.2026.** Puni kontekst: `../../A2_1G_ETH_SAZETAK.md` i `../../A2_CCGM1A2_TASK-5092.md` §5.9.

## Što je otkriveno

- **1G na A2 ne radi zbog RX-a:** `CC_IDDR` u IOSEL-u na die 1B (banka EB, RGMII) daje stalno isti Q0/Q1.
  Na pinovima podaci postoje: isti pin preko `CC_IBUF` → FF u fabricu broji bridove.
- U istoj banci radi `CC_ODDR` (TX), obični ulazi (MDIO, RXC → `CC_BUFG`) i CPE FF-ovi na 1B.
- IOSEL konfiguracija IDDR-a u `.txt` jednaka je kao na A1 (`IN1_FF 1`, `IN2_FF 1`, `INV_IN2_CLOCK 1`, `IN_CLOCK 00`).
  Razlikuju se samo ulazni muxevi IOES, a A1 build ima i `LES2.PINX_SEL` / `LES2.SB_Y3_SEL2` kojih A2 nema.
  Sumnjamo na chipdb ili pisač bitstreama (takt ili povratni put ulaznih registara na 1B). To nije dokazano.
- „FF-ovi na 1B ne rade” bio je **reset**, a ne alat: load preko A2 dizajna koji radi nije čist. Zato prije svakog
  loada ide `R!`: `selfrst` povuče `IO_SB_B8` = `RST_N` i to resetira oba die-a.
- Bez IDDR-a put 1B → 1A traje ~12 ns, a na 1G ciklus je 8 ns, pa radi samo 100 Mb/s (nadsemplirani RX).

## Dizajn (`top.v`, `top.ccf`)

RXC (`IO_EB_A7`) → `CC_BUFG`. RX_CTL (`IO_EB_A8`) i RXD0 (`IO_EB_A0`) uzorkuju se na RXC:

- zadano kroz **`CC_IDDR`**, koji nextpnr pakira u IOSEL na die 1B;
- s `-DFAB` kroz `CC_IBUF` → `CC_DFF` na 1A.

Logika je `force_die=1A`, a `eth_rst_n` je stalno 1 (PHY zadržava link). UART 115200 svakih ~0,67 s ispisuje:
`C` = rastući bridovi RX_CTL (Q0), `F` = isto za Q1, `D` = promjene RXD0, `R` = RXC ciklusi / 1024 (hex).
U sadržaju je i `selfrst`, pa se odmah može učitati sljedeća varijanta bez power-cyclea.

## Ponovljiv test

**1. Build i simulacija (lokalno).** Koristi lokalni A2 toolchain `~/app/raid/tools/nextpnr-a2fix`:

```sh
docs/nextpnr_a2_repro/rxprobe/build.sh
```

Očekivano:

- sim ispisuje `C0003 F0003 D0096`;
- `gm_cfgrst_check` za oba bitstreama javlja `CFGRST`;
- sha256 `rxp_iddr.bit` = `174ea69a…`, `rxp_fab.bit` = `bc7cd817…`.

**2. Ploča (Pi, `fpga-klaudio@192.168.10.14`).** Bitstreamovi su već ondje, a hash im je provjeren 30.09.:
`~/t5094/A2_rxprobe_iddr.bit`, `~/t5094/A2_rxprobe_fab.bit`.

Preduvjeti:

- `gs` izvodi dizajn sa selfrst-om (Linux T5094 ili sama proba);
- PHY link je gore;
- zakup `/home/pi/gs.owner` je slobodan.

```sh
scp docs/nextpnr_a2_repro/rxprobe/run_rxprobe.sh fpga-klaudio@192.168.10.14:t5094/
ssh fpga-klaudio@192.168.10.14 '~/t5094/run_rxprobe.sh 4'
```

Za svaku varijantu skripta napravi ovo: `R!` → load (`--index-chain 0`, bez `-r`) → Pi pinga `.213` (ARP okviri stižu na RX pinove) → UART 4 s.

| varijanta | očekivano (izmjereno 30.09.) |
|---|---|
| `iddr` | `C0000 F0000 D0000` u svakom retku → **IDDR na 1B ne radi** |
| `fab` | `C` i `D` rastu (`C0002→0005→0007`, `D003A→008E→00C2`) → pinovi i PHY su ispravni |

Ako je `iddr` tih ili se oba ne mijenjaju: provjeri link (LED) i da Pi stvarno šalje (`ping` .213).
Ako je UART potpuno tih, čip je zaglavio i treba power-cycle.

**3. Kontrola na A1 (kad bude A1 ploča).** Isti `top.v`/`top.ccf` s `--device CCGM1A1` (build je već postojao:
`~/.tmp/a2/t5094rxp/rxp_iddr_a1.txt`). Na A1 `iddr` mora brojati jednako kao `fab`.

**4. Izolacija u alatu.** Usporedi `.tile` blok pada `IO_EB_A8` u `rxp_iddr_a2.txt` i `rxp_iddr_a1.txt`
(`~/.tmp/a2/t5094rxp/`): IOSEL, IOES muxeve, `LES*`/bank clock, pa po jedan bit vraćaj na A1 vrijednost.
Svaka izmjena = nova proba kroz korak 2.
