# verify_external_link.sh — kako sam provjeriti da SerDes GS↔M2 radi preko kabela

Skripta je na Piju: `tools/verify_external_link.sh` (izvor u repou:
`tools/`). Radi s dizajnom **ber_top** (`docs/ulx5m-serdes/gw/`) učitanim na obje ploče.

## Što skripta dokazuje

1. **Podaci idu vanjskim kabelom, a ne unutarnjom petljom.** Svaka riječ na liniji nosi ID pošiljatelja
   (gs = 5, m2 = 3). Prijemnik broji samo riječi s ID-om **druge** ploče. Kad bi signal kružio
   unutarnjom petljom, prijemnik bi vidio vlastiti ID ili nečitljive podatke, a ne ID druge ploče.
   Uz to: kad utišaš TX jedne ploče, prijem na drugoj mora pasti, a kad izvučeš kabel, moraju pasti obje.
2. **Checker stvarno broji greške** (negativna kontrola). Skripta na svaki TX ubaci točno 3 greške,
   a druga strana mora izbrojiti točno 3.
3. **LOOPBACK_SEL=0** na obje ploče u svakom JTAG očitanju.

## Pokretanje

```bash
ssh <lab-pi>
# ako na pločama nije ber_top, dodaj --load (učita m2 pa gs, 300 Mb/s, bitovi s CFGRST-om)
tools/verify_external_link.sh --load
```

Skripta se u koraku 5 zaustavi i ispiše **„SAD IZVUCI SerDes KABEL“**. Izvuci kabel i pritisni ENTER.
U koraku 6 traži **„VRATI SerDes KABEL“**: vrati kabel i pritisni ENTER.
Bez koraka s kabelom (npr. na daljinu): `--no-cable`.

Prije pokretanja provjeri da gs nije zauzet: `cat <lab-dir>/gs.owner`. Ako tamo stoji tuđi zadatak
mlađi od 2 sata, pričekaj.

## Koraci i što mora biti

| Korak | Radnja | Mora biti |
|---|---|---|
| 1 | početno stanje | gs i m2 primaju ID druge ploče (JTAG `PEER 10/10`), `LOOPBACK_SEL=0`, `GS=UP M2=UP` |
| 2 | TX na m2 u električni idle (JTAG) | `GS=DOWN`; m2 i dalje prima od gs (`PEER`) |
| 2b | TX na m2 vraćen | `GS=UP M2=UP` |
| 3 | TX na gs u idle | `M2=DOWN` (m2 dojavi preko povratnog kanala), JTAG na m2 ne vidi gs; gs i dalje `UP` |
| 3b | TX na gs vraćen | `GS=UP M2=UP` |
| 4a/4b | 3 ubačene greške na gs TX, pa 3 na m2 TX | druga strana izbroji točno 3 (`sent=3 counted=3`) |
| 4c | m2 šalje fiksni uzorak (TX_DATA_OVR) | gs ga odbija (`GS=DOWN`, JTAG nije `PEER`) |
| 4d | uzorak vraćen | `GS=UP M2=UP` |
| 5 | **kabel izvučen** | obje strane padnu (`GS=DOWN`, JTAG na m2 ne vidi gs) |
| 6 | **kabel vraćen** | oporavak: `GS=UP M2=UP`, obje `PEER` |

Na kraju piše `UKUPNO: N PASS, M FAIL -> PASS|FAIL`. Exit status je 0 samo ako su svi koraci PASS.

## Kako čitati `GS=… M2=…`

`ber_mon.py state` čita 3 statusna retka s UART-a gs (`/dev/serial/by-id/…E660583883501E2C-if01`):
- `GS=UP`: prijemnik na gs je sinkroniziran, broji nove riječi, nema novih grešaka i ne vidi vlastiti ID.
- `M2=UP/DOWN`: isto za prijemnik na m2. Stanje stiže povratnim kanalom (bajt 7 svake riječi, okvir od 32 bajta).
- `M2=UNKNOWN`: od m2 ne stižu novi okviri (npr. kad je TX na m2 utišan). Tada se m2 provjerava preko JTAG-a.

## Ostali alati (isti direktorij)

| Alat | Namjena |
|---|---|
| `ber_mon.py run --secs 300 --clear` | BER u oba smjera + izmjerena brzina linije (iz brojača taktova, ne iz postavki) |
| `ber_mon.py inject e\|E --n 3` | negativna kontrola: gs TX (`e`) ili m2 TX (`E`) ubaci N grešaka |
| `ber_mon.py cmd z\|Z` | obriši brojače na gs (`z`) ili na gs i m2 (`Z`) |
| `fpga-jtag gs\|m2 run python3 ber_jtag_check.py` | JTAG pogled na ploču: čije podatke prima i `LOOPBACK_SEL` |
| `fpga-jtag gs\|m2 run python3 serdes_status.py` | sva CC_SERDES polja, uključujući sve bitove petlji |

## Napomena o LOOPBACK_SEL

Regfile polja petlji (0x2A far-end, 0x40 near-end) pokazuju samo **override preko regfilea**. Izmjereno
26. 9. 2026.: kad je `*_OVR=0`, polja ne prate port iz bitstreama (RX_POLARITY čita 0, a u bitstreamu je 1).
Zato je `LOOPBACK_SEL=0` nužan uvjet, ali nije dokaz. Dokaz su ID-ovi i koraci 2–6.
