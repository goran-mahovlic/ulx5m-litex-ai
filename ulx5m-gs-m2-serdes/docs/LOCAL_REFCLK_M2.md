# Local refclk on M2 (X2 on M2, C136/C137 off) — what the datasheets say, what we measured (TASK-5087, 27.09.2026)

Goran's question: "we can't have two oscillators on one line — and how is the signal synchronised then?"

## 1. One driver per net — confirmed from the manufactured M2 PCB

`FAST-TRACK-SIM/boards/ulx5m-m2/ulx5m-m2.kicad_pcb` (= the board on the bench, see SI_SERDES_GS_v004.md):

| Part | Pad 1 | Pad 2 |
|---|---|---|
| C136 / C137 (100 n) | SER_CLK_P / SER_CLK_N | PCIe_CLK_P / PCIe_CLK_N (J10 pins 55 / 53 = refclk from GS over the cable) |
| X2 511FCA100M000BAG | pin 4 → SER_CLK_P, pin 5 → SER_CLK_N, pin 6 VDD_CLK, pin 1 OE (R143 100 k to VDD_CLK) | |
| C129 / C130 (100 n) | SER_CLK_P / SER_CLK_N | SER_CK_P / SER_CK_N (FPGA side, T12/T13) |

So SER_CLK is driven either by the cable (through C136/C137) **or** by X2. Remove C136/C137 → X2 alone; keep them and fit
X2 → two LVDS drivers on one net (must not be done). C129/C130 stay: they are the AC coupling X2 → FPGA, exactly as the
cable clock uses them today. GS is not touched.

## 2. Synchronisation: the CDR, and what DS1001 does (not) specify

- DS1001 (Sept 2026) §2.5: RX PCS has a CDR and an "elastic buffer to compensate for clock tolerances"; the PCS has a
  "phase adjust FIFO for clock correction". `ber_top.v` clocks the RX checker from `RX_CLK_O` (recovered clock, `rclk`),
  so the elastic buffer never sees two clocks and clock correction (`RX_CLKCOR_USE`) is not needed for the BER test.
- **DS1001 gives no ppm tolerance for the CDR** (the word "ppm" does not occur; table 4.3 only has SER_CLK 100–125 MHz,
  **refclk jitter max 1 ps**, 0.3–5 Gb/s). None of the upstream designs we have (gm_serdes_lb, gatemate-pipe,
  openCologne-PCIE, liteiclink) runs with `RX_CDR_CKI ≠ 0`, so nobody has published a number either.
- Table 2.48 / register 0x0A: `RX_CDR_CKP` proportional, **`RX_CDR_CKI` integral, default 0**. With CKI = 0 the frequency
  integrator is off (our `RX_CDR_FREQ_ACC_VAL` has always read 0): a first-order loop that follows phase only. With two
  oscillators the phase walks continuously; a proportional-only loop can follow only a limited slope, so **CKI ≠ 0 is
  needed** (on **both** boards — each receiver sees the other side's oscillator), and the tolerance has to be measured.
- Register encoding of CKI is not documented → values 1 / 2 / 4 built and measured (§4).

## 3. The X2 part: supply mismatch — check before buying

- Si510/511 datasheet (Skyworks rev 1.4) ordering code `511 F C A 100M000 B A G`: **F = 2.5 V LVDS**, C = ±30 ppm total
  (±20 ppm over temperature), A = OE active high, 100.000 MHz. Two such parts differ by at most **60 ppm** (+ aging).
- Supply: 2.5 V option **2.25–2.75 V**; 1.8 V option 1.71–1.89 V.
- **VDD_CLK is 1.8 V on both boards**: TLV62569 U1, R3 200 k / R4 100 k, V_FB 0.6 V → 0.6 × (1 + 200/100) = 1.8 V; the
  same rail feeds the 1.8 V flash AT25QL321 (U9) and `+1V8_FLASH` / `+1V8_SB` through 4R7.
- So the schematic value (a 2.5 V part) on a 1.8 V rail is out of spec. Either the part fitted on GS is actually a 1.8 V
  variant (value field wrong) or GS runs its X2 out of spec (then the 1 ps refclk jitter of DS1001 is not guaranteed —
  relevant for the 5 G work). **Read the marking on GS X2.** For M2 order a **1.8 V LVDS** variant (1st option **J**:
  `511JCA100M000…`, package code for 2.5×3.2 mm from the Skyworks configurator), same ±30 ppm.
- Package code `B` in the value = 3.2×5 mm, footprint is 2.5×3.2 mm 6-pin → another sign the value field is not the ordered part.

## 4. Measurements before soldering (lab_5087.sh)

Pi run 27.09. 23:02–23:24, shared refclk (today's wiring, 0 ppm), 2.5 G best pair, `docs/data_20260927/t5087/`
(`lab_5087.sh`, `lab_5087.out`, `log/`). The runs cannot show the ppm tolerance (there is no offset yet). What they do
show is whether CKI ≠ 0 is safe to leave on, and how it behaves.

**A — CKI on both boards, 2 loads × 60 s each (interleaved):**

| CDR_CKI | BER gs→m2 median (worst) | BER m2→gs median (worst) | FREQ_ACC_VAL m2 / gs (3 × 1 s) | CDR lock |
|---|---|---|---|---|
| 0 (baseline) | 2.3·10⁻⁹ (3.5·10⁻⁹) | 2.9·10⁻⁸ (5.8·10⁻⁸) | 0 / 0 | yes |
| **1** | 1.6·10⁻⁸ (3.1·10⁻⁸) | 8.6·10⁻⁹ (1.7·10⁻⁸) | −7…+5 / −23…+10 | yes |
| 2 | 7.1·10⁻⁸ (1.3·10⁻⁷) | 1.0·10⁻⁶ (1.7·10⁻⁶) | −18…+16 / −70…+34 | yes |
| 4 | 6.1·10⁻⁵ (8.9·10⁻⁵), synced 0.2 % | 8.5·10⁻⁶ (1.1·10⁻⁵) | **+16371…+16383 (rail)** / −72…+156 | **m2 no** |

- CKI 1: within the known load-to-load spread of the baseline (single loads of the same bits span 5·10⁻¹⁰ … 4·10⁻⁷,
  VERIFY_20260926_RATES.md §9.2) → **usable, first choice**. CKI 2: 10–30× worse. CKI 4: the integrator runs to the
  positive rail (15-bit signed, +16383) and m2 loses lock in both loads → **unstable, do not use**.
- The integrator gain per LSB of CKI is large: doubling it twice turns a working loop into a runaway one.

**C — start-up trap (cki2 pair, fresh load, no recal):** m2 `RX_CDR_LOCKED=0`, `FREQ_ACC_VAL` 16375/16379/16381 (rail)
3 s after load, on a 0 ppm link. `RX_CDR_SET_ACC_CONFIG=2` then `=0` (override on, then off) → locked, FREQ_ACC_VAL −54…+82
over 10 s, `ber_jtag_check` PEER 100/100 on both. So with CKI ≠ 0 **the integrator can latch at the rail at start-up**
(not a ppm problem — there was no offset). The procedure in §6 therefore pulses SET_ACC_CONFIG after every load.

**B — offset injection: NOT a valid measurement.** The plan was to force `RX_CDR_FREQ_ACC=±16…±8192` with
`SET_ACC_CONFIG` bit 1 at CKI 0 and see where the link breaks. The register 0x0E read back 0 after every write
(`set RX_CDR_FREQ_ACC=0` in `lab_5087.out`) and FREQ_ACC_VAL stayed 0, so no offset was applied (BER of all 8 points =
baseline spread). Whether 0x0E is write-only, needs testmode, or is only latched on a CDR reset is unknown (DS1001 does
not say). **The CDR ppm tolerance of GateMate stays unmeasured until two oscillators are really on the link.**

## 5. Bitstreams for the local clock

`ber_top.v` has a new parameter `CDR_CKI` (default 0 → every older bit rebuilds byte for byte: `gs_cki0…s7` =
`gs_sd_2g5p1_txneg_s7` 36f09752…, `m2_cki0…s2` = `m2_e1_2g5p1_txneg_s2` b1b98a5d…). Test `tools/tests/test_cdr_cki_param.py`.

Build (2.5 G best pair): `FREQ=40 [LINK=ber_link_gs.v] build_ber.sh <b> cki<k>_2g5p1_txneg <seed> N1 1 N2 5 N3 5 OUTDIV 2
PROFILE 1 TX_NEG 1 CDR_CKI <k>` (gs seed 7 with ber_link_gs.v, m2 seed 2). Bits on the Pi: `/home/pi/ulx5m-serdes/t5087/`.
CKI can also be written at run time without a rebuild: `fpga-jtag <b> run python3 eyescan.py set RX_CDR_CKI=<k>`.

| bit | sha256 |
|---|---|
| gs_cki1_2g5p1_txneg_s7 | 12a338c9… |
| gs_cki2_2g5p1_txneg_s7 | dd382c83… |
| gs_cki4_2g5p1_txneg_s7 | ccf02ee7… |
| m2_cki1_2g5p1_txneg_s2 | d872b4a9… |
| m2_cki2_2g5p1_txneg_s2 | ac96c6fe… |
| m2_cki4_2g5p1_txneg_s2 | 6bbab3aa… |

## 6. After X2 is fitted (procedure)

1. M2: C136/C137 off, X2 (1.8 V part) on. Nothing on GS.
2. Load the **`cki1`** pair on **both** boards, then on each board `eyescan.py set RX_CDR_SET_ACC_CONFIG=2` and
   `set RX_CDR_SET_ACC_CONFIG=0` (start-up trap, §4 C); check `RX_CDR_LOCKED=1` and FREQ_ACC_VAL not at ±16383. The fabric rate counter (`ber_mon`) gives m2 − gs in ppm directly; `eyescan.py
   health` gives `FREQ_ACC_VAL`. One pair of numbers calibrates FREQ_ACC LSB → ppm.
3. If CKI 1 cannot follow the real offset (lock lost, FREQ_ACC_VAL at a rail): try CKI 2; CKI 4 is unstable.
4. Pass: CDR locked, FREQ_ACC_VAL steady (not at a rail), BER at 2.5 G not worse than the shared-refclk baseline.
