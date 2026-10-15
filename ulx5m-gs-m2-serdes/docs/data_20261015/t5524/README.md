# TASK-5524 — M2 → GS SerDes put (lošiji smjer): slike i provjera spoja (15.10.2026.)

Slike nastaju naredbom `python3 tools/si/render_m2_gs_path.py docs/data_20261015/t5524` (PIL, bez kicad-cli; testovi su u `tools/tests/test_path_render.py`).

| Slika | Što prikazuje |
|---|---|
| `1_m2_tx_cijeli_put.png` | M2 TX U4.U13/V13 → F.Cu 10,2 mm → via 1 → B.Cu 50,8/49,8 mm → via 2 → C144/C143 → J10.43/41 |
| `2_m2_ac_kapovi_C143_C144.png` | AC kondenzatori C144 (P) i C143 (N), 220 nF 0201, uz J10 |
| `3_m2_bga_izlaz_U4.png` | izlaz iz BGA, R110 DNP pločice na TX paru, via 1 |
| `4_gs_rx_J1_U4.png` | GS v005 RX J1.16/18 → B.Cu ~7 mm → via → F.Cu ~20 mm → U4.U11/V11, R107 DNP |
| `5_lanac_M2_GS_pin_po_pin.png` | lanac pin po pin, duljine segmenata za oba smjera, sumnjive točke, preporuka |

Inačica M2: **as built** = `~/app/raid/FAST-TRACK-SIM/boards/ulx5m-m2/ulx5m-m2.kicad_pcb` = panel gerberi 02.06.2026. (SI_SERDES_GS_v004 §1.2). Na toj su inačici AC kapovi 0201, a GitHub f29c5aa je v2 s 0402.

## Nalazi
- **Polaritet je ispravan** na M2 (TX_P → C144 → J10.43 = M.2 PERp0, RX_P ← J10.49 = PETp0), na GS (J1.16 = CM 116 PCIe_RX_P → U4.U11) i na Waveshare P1 (7/8 RX, 10/11 TX, isto kao RPi RP-008298 sl. 1). Za `RX_POLARITY_I=1` u **oba** smjera ostaje adapter.
- Trag za zamjenu P/N: službena RPi **CM5 IO Board** (KiCad, `~/app/tmp/cm5io/r2/PCIe-M2.kicad_sch`) namjerno križa P/N obaju parova na M.2 (CM5 TX_P → pin 47 = PETn0, RX_P ← pin 41 = PERn0). Adapter ili baseboard s M.2 utorom napravljen po RPi uzoru imao bi istu zamjenu. To je hipoteza dok se ne pogleda adapter.
- **Nusnalaz:** `ulx5m-gs-linux-sbc/docs/sd/cm5-io-base-a_netlist.json` je netlista **službene RPi CM5 IO ploče** (company „Raspberry Pi Ltd", list PCIe-M2 s M.2 J4), a ne Waveshare CM5-IO-BASE-A (ta ima P1 FFC). TASK-5234 (J8) je koristio tu datoteku, pa J8 mapiranje treba usporediti s Waveshare PDF-om.
- AC kondenzatori: na pločama je točno jedan po smjeru (M2 TX C143/C144 220 nF 0201, GS TX C134/C135 100 nF 0402 GRM155R60J104KA01D). Waveshare na RX nema serijskih kondenzatora. Za adapter nije poznato.
- Vrijednosti: PCIe Gen1/2 traži 75–265 nF (tipično 100 nF), Gen3 176–265 nF (220 nF), pa su obje vrijednosti dobre. 0402 na 0201 pločice može se zalemiti ručno (0,26 mm zraka među tijelima), ali za SI to ništa ne donosi. Mijenjati ih treba samo ako kondenzator fali ili je oštećen.
- Duljine na pločama (P/N, mm): M2→GS 92,06/91,33 (skew 0,73, 3 vie); GS→M2 91,89/90,07 (skew 1,82, 3 vie). Bolji smjer ima veći skew, pa skew ne objašnjava razliku među smjerovima.

## Ovo se iz datoteka ne može doznati, Goran treba izmjeriti ili pogledati
1. Koji je baseboard na stolu (Waveshare CM5-IO-BASE-A s FFC-om ili RPi CM5 IO s M.2 utorom) i koji je adapter (foto obje strane, oznaka).
2. Duljinu FFC-a (RPi spec ≤ 50 mm, 90 Ω, kontakti na suprotnim stranama).
3. Ima li adapter vlastite AC kondenzatore i križa li par vijama.
4. Jesu li C143/C144 zalemljeni (lupa). DMM bez napajanja: prst J10.43 ↔ C144 pad 1 = 0 Ω, preko C144 otvoreno; isto prst 41 ↔ C143.
5. Kontinuitet GND M2 ↔ GS (FFC GND pinovi 3, 6, 9, 12).
