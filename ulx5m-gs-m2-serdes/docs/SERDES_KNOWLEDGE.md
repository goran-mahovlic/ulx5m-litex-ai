# GateMate SerDes GS ↔ M2 — everything we know (handover for the next engineer or AI)

**State:** 28.09.2026. **Written for:** someone (human or AI) who has to continue this work without the chat history.
Every number here comes from a measurement or a document in this repo; the section sign (§) points at the full data.
If this file and a detailed report disagree, the detailed report is right (it holds the raw numbers), and this file needs a fix.

Tags: **MEASURED** = on the boards, raw data in `docs/data_2026092*/`. **DS** = datasheet DS1001 (Sept 2026) / UG1001.
**DERIVED** = computed from measured or documented values. **OPEN** = not known yet.

---

## 0. Short version

| Rate | Result | Bits (`bitstreams/`) | Settings that matter |
|---|---|---|---|
| 0.3 Gb/s | **0 errors**, BER < 6.7·10⁻¹¹ both ways | `serdes_p1_rxpol1_CFGRST.bit` (both), `ber_*_0g3_*` | N1·N2·N3 = 1·2·3, OUTDIV 4, `RX_POLARITY_I=1` |
| 1.25 Gb/s | **0 errors**, BER < 4·10⁻¹¹ both ways | `ber_*_1g25_*` | 1·5·5, OUTDIV 4 (DCO 2500 MHz, in spec), PROFILE 0 |
| 2.5 Gb/s | **works with errors**: with 1 µF on GS gs→m2 ≈ 6·10⁻¹⁰, m2→gs ≈ 1·10⁻¹¹ (3 loads × 300 s) | `ber_gs_2g5_p1_txneg_s7_*` + `ber_m2_2g5_p1_txneg_s2_*` | 1·5·5, OUTDIV 2, **PROFILE 1 in the bitstream**, **TX_NEG=1 on both**, RX AFE GAIN 0 |
| 5 Gb/s | **does not work**: BER 10⁻² … 10⁻¹, CDR does not hold lock | `ber_*_5g_p2_txneg_*`, `ber_*_5g_p3_txneg_*` (references only) | 1·5·5, OUTDIV 1; ~60 register points tried, none helps |

The three things that decide 2.5 Gb/s: (1) analog settings **in the bitstream**, not written over JTAG later; (2) RX AFE GAIN 0;
(3) the untimed fabric↔SerDes ports (nextpnr ignores them) → `TX_NEG=1` and choose seeds by several loads. Supply decoupling
on GS (1 µF at C127/C128) removed most of the load-to-load spread at 2.5 G. 5 Gb/s is limited by something outside the register set.

---

## 1. The setup (hardware)

| Item | Value | Tag |
|---|---|---|
| FPGAs | two Cologne Chip GateMate **CCGM1A1**, one SerDes lane each (TX pair + RX pair) | DS |
| gs | ULX5M-GS **v005** (github.com/intergalaktik/ulx5m-gs `main` 61b6709) on a CM4 IO baseboard | MEASURED (Goran) |
| m2 | ULX5M-M2 (GateMate on an M.2 card); the board on the bench = `FAST-TRACK-SIM/boards/ulx5m-m2` copy of 02.06.2026, **not** GitHub `ulx5m-m2` f29c5aa (that is v2 WIP) | `SI_SERDES_GS_v004.md` §1.2 |
| Channel | GS → CM4 IO baseboard → PCIe slot → PCIe-to-M.2 adapter (FFC) → M2. The only link between the FPGAs is this lane | `VERIFY_20260926.md` |
| Refclk | **One** 100 MHz LVDS oscillator: X2 (Si511 `511FCA100M000BAG`) on GS → C129/C130 → SER_CLK (balls T12/T13). M2's own oscillator is removed; M2 gets the same clock through the chain (C136/C137 on M2). Result: 0.0 ppm between the boards | MEASURED (rate counters) |
| P/N polarity | **swapped in both directions** somewhere in the chain → `RX_POLARITY_I=1` on both boards. Not on GS, baseboard or M2 by pinout; must be the FFC/adapter chain (not traced) | MEASURED / `TUNING_5G.md` §2.3 |
| Core supply | J3 = 2-3 → **VDD_CORE 1.1 V on both boards** (Goran, 26.09.). VDD_SER / VDD_SER_PLL come from VDD_CORE through 1 Ω (R106/R105) + 100 nF; ≈ 1.05 V at the SerDes. DS1001: VDD_SER 1.00–1.10 V | DS / DERIVED |
| PCB | GS v005 on JLC default 6-layer stack: 97 Ω (F.Cu) / 103 Ω (B.Cu) differential. M2: 88 Ω. Chain loss 3.0 dB nominal / 4.8 dB worst at 2.5 GHz → **the stackup is not the 5 G limit** | `SI_SERDES_GS_v004.md` |
| Silicon max | 5 Gb/s (DS1001 Table 4.3: 0.3–5 Gb/s, DCO ≤ 2500 MHz, refclk jitter ≤ 1 ps) | DS |

### 1.1 Hardware changes made during the work

| When | Change | Effect |
|---|---|---|
| 27.09.2026 15:54 | **1 µF in parallel to C128 (VDD_SER), C127 (VDD_SER_PLL) and C42 (VDD_PLL) on GS.** M2 not touched | 2.5 G better and much more repeatable; 5 G unchanged (§4). Also: fabric PLL lock drops under SDRAM load gone (DVI, §10.2) |
| 27.09.2026 16:40 | GS → PCIe → M.2 → M2 chain reseated (after the rework, M2 had lost the refclk: −8 ppm, `PLL_CAP_FT` 842–1007 with overflow, no data at any rate) | link back to normal (0.0 ppm, CAP_FT ~508) |

The GS 1 µF is the current state of GS. Later experiments on the M2 unit (VERIFY_20260926_RATES.md §10.5–§10.6) depend on
that particular board and are not general conclusions; they are kept only as raw data.

---

## 2. Clocking and rate

- Line rate = **2 · 100 MHz · N1·N2·N3 / OUTDIV**; f_DCO = 100 MHz · N1·N2·N3 (DS1001 p.56). Word = 80 line bits (8b10b, 64 data bits).
- DS1001 DCO range: 1250–2500 MHz. Use **N = 1·5·5 (DCO 2500 MHz)**. The 1·2·3 recipe (DCO 600 MHz, out of spec) is clean
  only at 0.3 Gb/s; at 0.6 Gb/s one direction has errors, at 1.2 Gb/s both (MEASURED, `VERIFY_20260926.md` §6).
- `PLL_FCNTRL = 0x3A` (80-bit), `PLL_REF_SEL=1` (LVDS), `PLL_REF_RTERM=1` (on-die termination; R108 is DNP).
- The rate is **measured**, not declared: `ber_top` counts `PLL_CLK_O` and `RX_CLK_O` against the 25 MHz board clock;
  `ber_mon.py run` prints it (2500.02 and 5000.04 Mb/s measured). Word clock: 31.25 MHz at 2.5 G, 62.5 MHz at 5 G.
- Health at 5 G: PLL locked, no CAP_FT overflow, CAP_FT the same as at 2.5 G (same DCO) → **5 G does not fail in the PLL**,
  it fails in the CDR / data eye (MEASURED §9.1).

| Config name | N1·N2·N3 | OUTDIV | Rate | Result |
|---|---|---|---|---|
| od4 | 1·2·3 | 4 | 0.3 Gb/s | clean |
| od2 / od1 | 1·2·3 | 2 / 1 | 0.6 / 1.2 Gb/s | errors (DCO out of spec) |
| n155od4 | 1·5·5 | 4 | 1.25 Gb/s | clean |
| n155od2 | 1·5·5 | 2 | 2.5 Gb/s | errors, see §4 |
| n155od1 | 1·5·5 | 1 | 5 Gb/s | not usable |

---

## 3. Gateware

| Folder | What |
|---|---|
| `gateware/baseline/` | CologneChip `serdes_lb.v` + `RX_POL` parameter; K28.5 + D10.2 pattern, 0.3 Gb/s. Same bitstream on both boards |
| `gateware/ber/` | The measuring design: generator + checker in fabric (`ber_link.v`, gs uses the slower-but-routable `ber_link_gs.v`), `ber_top.v` (`top_gs` / `top_m2`), UART status on gs, `build_ber.sh` |
| `gateware/upstream/` | unchanged `serdes_lb.v` |

**Checker basics.** Every word = K28.5 + sender ID (gs 5 = `101`, m2 3 = `011`; the inverted IDs are neither, so a P/N or
loop error cannot look valid) + a counter pattern. 40 checked bits per word. BER = bit errors / (40 · words). m2's counters
reach the gs UART inside the m2→gs stream, so at 5 G they can be corrupted (`ab_table.py` caps BER at 0.5).
**Error injection:** `ber_mon.py inject e|E --n 3` — the far side must count exactly 3 (only on a clean link).

**`ber_top.v` parameters** (set with `build_ber.sh <gs|m2> <name> <seed> PARAM VALUE …`):

| Parameter | Default | Meaning / what we learned |
|---|---|---|
| `N1 N2 N3 OUTDIV` | 1 2 3 4 | rate (§2) |
| `PROFILE` | 0 | analog/CDR set, table below |
| `TX_NEG` | 0 | TX data from a negedge register. **Use 1 on both at 2.5 G/5 G** (gs→m2 ≈ 60× better with it on gs) |
| `RX_NEG` | 0 | RX capture on negedge first. Drops rclk Fmax to 35–42 MHz → unusable at 5 G |
| `CLK_DIRECT` | 0 | TX/RX clocks straight from the SerDes, no CC_BUFG (as serdes_lb.v). Did not help |
| `TX_DET_RX` | 0 | `TX_DETECT_RX_I`. 0 = upstream since pu-cc dda07f7. 1 vs 0: no measurable difference (E1) |
| `TX_CALIB` | 1 | `TX_CALIB_EN` in every profile. Keep 1 |
| `PLL_RTERM` | 1 | refclk termination. 0 on gs (E6): no change |
| `CDR_CKI` | 0 | CDR frequency integrator. 0 is right with a shared refclk. **Needed (1) with two oscillators** (§6) |
| `EYE_EN` | 0 | eye counters in the bitstream — they never count anyway |
| `RX_POL` | 1 | `RX_POLARITY_I`, must be 1 (P/N swap) |

**PROFILE values** (baked into CC_SERDES parameters, `ber_top.v` localparams):

| Field | P0 (serdes_lb.v) | P1 (pu-cc 5G, ab7ce94) | P2 (5G sweep best) | P3 (P1 + CDR) |
|---|---|---|---|---|
| RX_EN_EQA (DFE) / EQA_LOCK_CFG | 0 / 0 | 1 / 0xC | 1 / 0xC | 1 / 0xC |
| RX_AFE_PEAK (0 = most peaking) | 15 | **24** | 12 | 24 |
| RX_AFE_GAIN | 8 | **0** | 0 | 0 |
| RX_AFE_VCMSEL / RX_RTERM_VCMSEL | 4 / 4 | 3 / 3 | 3 / 3 | 3 / 3 |
| RX_CDR_CKP / TRANS_TH / LOCK_CFG | 0xF8 / 0 (bug: 9'h80 in a 7-bit field) / 0x0B | 0x3E / 8 / 0xD5 | 0x1E / 16 / 0xD5 | 0x1E / 16 / 0xD5 |
| RX_RESET_TIMER_PRESC | 0 | 4 | 4 | 4 |
| TX_AMP | 15 | 31 | 31 | 31 |
| TX pre / post branches, SEL_PRE / SEL_POST, DC_ENABLE | 0/0, 0/0, 63 | 12/12, 5/5, 43 | 0/31, 0/12, 47 | 12/12, 5/5, 43 |

Version byte in the status line: `VER = 0xB2 + PROFILE`.

---

## 4. Results with settings and how to get them

### 4.1 0.3 and 1.25 Gb/s — clean

| Rate | Words per direction | Errors | BER (95 %) | Bits | Build |
|---|---|---|---|---|---|
| 0.3 Gb/s | 1.14·10⁹ | 0 | < 6.6·10⁻¹¹ | `ber_{gs,m2}_0g3_CFGRST.bit` | `build_ber.sh gs od4 1` / `… m2 od4 1` (sources of 4ee6031) |
| 1.25 Gb/s | 1.885·10⁹ | 0 | < 4.0·10⁻¹¹ | `ber_{gs,m2}_1g25_CFGRST.bit` | `… n155od4 1 N2 5 N3 5 OUTDIV 4` |

Baseline link test (no BER design): `serdes_p1_rxpol1_CFGRST.bit` on both, `serdes_link_check.py --samples 30` → `DATA_OK 30/30`
on both; 6 seeds × 2 boards × 30 = 360/360.

### 4.2 2.5 Gb/s — how the result improved, step by step

| Step | BER gs→m2 | BER m2→gs | What changed | § |
|---|---|---|---|---|
| PROFILE 0 as built | 2.1·10⁻⁴ | 5.9·10⁻⁴ | serdes_lb.v analog values | RATES §1 |
| + DFE on (JTAG) | 3.1·10⁻⁵ | 3.0·10⁻⁴ | | RATES §2 |
| + **AFE PEAK 24, GAIN 0, VCM 3** (JTAG) | 9.6·10⁻⁸ | 2.8·10⁻⁷ | GAIN 0 is the key (GAIN 4/8 → 2·10⁻²) | RATES §2 |
| same set **in the bitstream** (PROFILE 1), m2 TX_NEG | 1.2·10⁻⁹ | 6.7·10⁻¹¹ | calibration/DFE adaptation run from reset with the right values | RATES §1 |
| + **TX_NEG on gs too**, seed choice (gs s7 + m2 s2) | 4.7·10⁻¹⁰ | 1.6·10⁻¹¹ | best single load; the same bits loaded again: 1.2·10⁻⁸ / 4.5·10⁻⁸ | RATES §9.3, §9.7 |
| + **1 µF on GS C127/C128/C42** (same bits, 3 loads × 300 s) | **6.0·10⁻¹⁰** median, worst 6.9·10⁻¹⁰ | **1.3·10⁻¹¹** median, worst 2.6·10⁻¹⁰ | load-to-load spread ×26 / ×2900 → **×1.6 / ×32** | RATES §10.4 |

### 4.3 The 1 µF on GS — full A/B (TASK-5078/5079, 27.09.2026)

Same six bitstreams before and after (sha256 checked on the Pi), every load = fresh load m2 then gs, CFGRST, SRAM only.
Script: `docs/data_20260927/t5079/lab9.sh`; raw data `docs/data_20260927/t5079/`.

2.5 Gb/s, best pair, 300 s per load:

| Load | BER gs→m2 | BER m2→gs* | synced share |
|---|---|---|---|
| before: 26.09. | 4.68·10⁻¹⁰ | 1.58·10⁻¹¹ | 1.00 |
| before: 27.09. | 1.21·10⁻⁸ | 4.54·10⁻⁸ | 0.97 |
| **after r1** | 6.87·10⁻¹⁰ | 2.55·10⁻¹⁰ | 1.00 |
| **after r2** | 4.29·10⁻¹⁰ | 8.00·10⁻¹² | 0.96 |
| **after r3** | 5.97·10⁻¹⁰ | 1.33·10⁻¹¹ | 0.96 |

Typical improvement 4× (gs→m2) and 65× (m2→gs), worst load 17× / 180×. The pass criterion (≥ 3× lower BER, TUNING_5G.md E9/H2)
is met in both directions. Caveat: only 2 "before" loads exist for this exact pair.

5 Gb/s, 3 loads × 60 s median (worst):

| Point | gs→m2 before → after | m2→gs* before → after | raw RX words OK (`ber_jtag_check` 200) m2 / gs, after |
|---|---|---|---|
| PROFILE 2 | 7.3·10⁻² → 4.9·10⁻² (5.3·10⁻²) | 1.8·10⁻² → 2.0·10⁻² | 181 / 192 |
| PROFILE 3 | 1.04·10⁻¹ → 6.2·10⁻² (6.5·10⁻²) | 1.68·10⁻¹ → 1.01·10⁻¹ | 183 / 182 |

1.5–2× — inside the load-to-load noise; **5 G is not changed by the GS decoupling**.

(* m2→gs is counted by the gs checker, whose rclk Fmax (41–50 MHz) is below the 62.5 MHz word clock at 5 G, and is only
indicative at 5 G. At 2.5 G (31.25 MHz) it is valid.)

### 4.4 5 Gb/s — what was tried (none leaves 10⁻² … 10⁻¹)

| Experiment | Range | Result | § |
|---|---|---|---|
| pu-cc recipe over JTAG (DFE + TX FFE + low GAIN) | | needed for CDR lock at all; BER ~6·10⁻² | RATES §3 |
| RX AFE GAIN × PEAK | GAIN 0–3 × PEAK 0–24 | GAIN 0 best; no point < 10⁻² | §9.4 |
| CDR CKP × TRANS_TH | 0xF8/0x7E/0x3E/0x1E × 8/16/32 | 2.5·10⁻² … 8·10⁻² | §9.5 |
| TX FFE (pre/post, SEL_POST 0–20), TX_AMP 20–28 | | 1.6·10⁻² … 1.1·10⁻¹ | §9.5 |
| VCM 2/4/5, refclk termination on gs off | | no change | §9.5 |
| seeds (m2 s1–s5, gs s2–s7), CLK_DIRECT | | no change | §9.5 |
| `TX_DETECT_RX_I` 1 → 0 | | no change | §9.2 |
| PROFILE 2 / PROFILE 3 in the bitstream | | 6·10⁻² / 1·10⁻¹; raw RX words 2.5–17.5 % bad even without the fabric | §9.7, §9.10 |
| 1 µF on GS SerDes supplies | | no change at 5 G | §10.4 |

Trade-off found: PEAK 12 gives fewer errors while locked, PEAK 24 stays locked longer (×17–20 synced share). Both are closed-eye
behaviour. **Judge any 5 G change by the 3-load median of synced share AND BER** (`ab_table.py --runs --rank`); a real
fix should move both the same way.

Remaining suspects (OPEN): refclk quality at M2 (it crosses the whole chain; DS1001 wants ≤ 1 ps jitter), the unidentified
FFC→M.2 adapter and FFC crosstalk, M2-side supply noise. Not the stackup (§1), not the PLL (§2), not the DC supply level.

---

## 5. Traps (each of these cost time once)

1. **JTAG-written analog settings ≠ the same settings in the bitstream.** 1·10⁻⁷ over JTAG vs 6.7·10⁻¹¹ baked in. Calibration
   and DFE adaptation run from reset. Tune over JTAG only to find a direction, then bake in and re-measure. If you write over
   JTAG, run `eyescan.py recal` (TX/RX termination calibration + DFE reset) afterwards; `abrun.sh` does it.
2. **nextpnr does not time the SerDes ports** (`delay.cc`: SERDES = `TMG_IGNORE`). The fabric↔SerDes paths change with every
   placement; the Fmax in the log does not cover them. Symptom: exactly 1 wrong bit per word and no 8b10b code errors (the error
   is before the encoder). Mitigation: `TX_NEG=1`, several seeds, and **judge a seed by ≥ 3 loads**, never by one.
3. **The same bitstream loaded twice can differ ×25 … ×3000** in BER (load-to-load lottery). One load proves nothing.
4. **`RX_CDR_LOCKED` and `RX_BYTE_IS_ALIGNED` lie**: they stay 1 while the far TX is idle. Judge by received data
   (`ber_jtag_check.py`: PEER = K28.5 + the other board's ID).
5. **The regfile does not mirror fabric ports** when `*_OVR=0`: `RX_POLARITY` reads 0 while `RX_POLARITY_I=1`; `LOOPBACK_SEL=0`
   only proves "no regfile override". Proof of "no loop" = sender IDs + idle/cable tests (`verify_external_link.sh`).
6. **The hard PRBS checker is not a BER instrument here.** PRBS select 3/4 are reserved (only 1 = PRBS-7, 2 = PRBS-15); with 1/2
   it locks but counts ~2000 errors/s regardless of settings. Use the fabric checker.
7. **Eye counters (regfile 0x14–0x1D) never count**, even with the register-map fixes (TH_MON2 override at 0x06[11], 0x14[0] =
   EYE_MEAS_DONE). Upstream `tc_eyemeas` is an empty stub. Question for Cologne Chip.
8. **`RX_CDR_TRANS_TH` is 7 bits**; the old `9'h80` read back 0. Fixed in PROFILE ≥ 1.
9. **The pu-cc nextpnr "setuphold" patch (abd0731) is wrong** — do not use (`NEXTPNR_SETUPHOLD_PATCH.md`).
10. **Every bitstream must start with CMD_CFGRST** (`gmpack --reset`, check with `tools/gm_cfgrst_check.py`). The old claim
    "1·5·5 does not lock" came from bits without CFGRST.
11. **Two identical probes:** both GateMates have the same IDCODE and both DirtyJTAGs the same VID:PID; openFPGALoader takes the
    first one and ignores `--busdev-num`. Use the `fpga-jtag gs|m2` wrapper (serial number → `LD_PRELOAD` shim). UART only by the
    by-id path, never `/dev/ttyACMn`.
12. **Load order: m2 first, then gs.** SRAM only (`-r`), no power cycle.
13. **The gs pipelined checker (`ber_link.v`) does not route on gs** (router2 "Failed to route arc", router1 assertion); gs uses
    `ber_link_gs.v` (45–50 MHz). So gs cannot check at 62.5 MHz → m2→gs numbers at 5 G are indicative.
14. **After a rework, check the refclk first:** m2 − gs rate must be 0.0 ppm and m2 `PLL_CAP_FT` ~506–517 without FT_OF.
    Otherwise the chain is not seated (§1.1) and every BER number is meaningless.
15. **`ber_mon.py inject` only works on a clean link** (the window also counts real errors).
16. The Pi (192.168.10.14) reports `Under-voltage` during bitstream loads; runs finish locally, but do not trust the network.

---

## 6. Local refclk on M2 — TASK-5087 (`LOCAL_REFCLK_M2.md`), fitted and measured in TASK-5089 (VERIFY_RATES §11)

**Measured 28.09.2026 (§11):** X2 on M2 works (PLL lock at 0.3/1.25/2.5 G, CAP_FT 108/492/501–508, +2.6 ppm vs GS). 2.5 G with separate
clocks: gs→m2 2.7·10⁻⁸, m2→gs 5.6·10⁻⁸ (CKI 0; CKI 1 not better) vs 6.0·10⁻¹⁰ / 1.3·10⁻¹¹ shared — worse, the M2 RX loses sync part of
the time. At +2.6 ppm CKI 0 is enough. Open suspects: ~52 mm open stub on SER_CLK to the removed C136/C137, no VDD_CLK decoupling at X2.


- One driver per net: M2 SER_CLK is driven **either** by the cable (C136/C137) **or** by a local X2. Fit X2 → remove C136/C137.
  C129/C130 stay. GS untouched.
- With two oscillators the receivers must track a frequency offset: `CDR_CKI` (integral term, default 0 = off) must be ≠ 0 on
  **both** boards. DS1001 gives **no ppm tolerance** for the CDR; nobody has published one.
- Measured at 0 ppm: CKI 1 = within the baseline spread (**use this**), CKI 2 = 10–30× worse, CKI 4 = integrator at the rail,
  m2 unlocked (**do not use**). With CKI ≠ 0 the integrator can latch at the rail at start-up → after every load
  `eyescan.py set RX_CDR_SET_ACC_CONFIG=2` then `=0`.
- Offset injection through register 0x0E does not work (reads back 0) → **the ppm tolerance stays unmeasured** until two
  oscillators are really on the link.
- Part: X2 on the schematics is a **2.5 V** LVDS Si511 (`511F…`), but VDD_CLK is **1.8 V** on both boards → order the **1.8 V**
  variant (`511J…`, ±30 ppm) for M2, and read the marking of the GS X2.
- Bits: `bitstreams/ber_{gs,m2}_2g5_p1_txneg_cki1_CFGRST.bit`. Procedure: `LOCAL_REFCLK_M2.md` §6.

---

## 7. How to reproduce a measurement

Lab: Raspberry Pi 192.168.10.14 with both DirtyJTAG probes, `openFPGALoader`, the `fpga-jtag` wrapper, Python 3 + pyusb +
pyserial. Tools are deployed from this repo to `/home/pi/ulx5m-serdes/tools/` (+ `tools/lab/`). The gs board is shared with other
work: take the lease `/home/pi/gs.owner` (`<TASK-ID> <unix time> <text>`); `abrun.sh` respects a lease younger than 2 h.

```bash
# health first (refclk, PLLs, CDR/EQA, raw words)
fpga-jtag m2 bitstreams/ber_m2_2g5_p1_txneg_s2_CFGRST.bit -r
fpga-jtag gs bitstreams/ber_gs_2g5_p1_txneg_s7_CFGRST.bit -r
fpga-jtag m2 run python3 tools/ber_jtag_check.py --samples 200     # expect PEER 200/200
fpga-jtag gs run python3 tools/ber_jtag_check.py --samples 200
fpga-jtag gs run python3 tools/eyescan.py health                  # PLL_CAP_FT, CDR/EQA lock, FREQ/PHASE_ACC
python3 tools/ber_mon.py run --secs 300 --clear                    # BER both ways + measured rate (gs UART)

# A/B with repeated loads (every load = fresh m2 then gs), then medians
ME=TASK-xxxx LOG=$PWD/log tools/lab/abrun.sh <gs.bit> <m2.bit> 300 3 "label||"
python3 tools/lab/ab_table.py --runs --rank log/label_r*.json
python3 tools/lab/health_table.py log/label_r*.health_*.json

# JTAG register tuning of one point (then recal is run by abrun.sh)
tools/lab/abrun.sh <gs.bit> <m2.bit> 60 3 "p24|gs:RX_AFE_PEAK=24|m2:RX_AFE_PEAK=24"

# external-lane proof (idle, inject, foreign pattern; cable steps need a person)
tools/verify_external_link.sh --load --no-cable
```

The complete A/B used for the 1 µF result is `docs/data_20260927/t5079/lab9.sh` (2.5 G best pair 3 × 300 s; 5 G PROFILE 2 and 3,
3 × 60 s interleaved + 300 s; `ber_jtag_check` 200). Run it unchanged for any new hardware change, so the numbers compare.

Build (oss-cad-suite 2026-09-23; commands for every bit are in `bitstreams/README.md`):

```bash
cd gateware/ber
LINK=ber_link_gs.v FREQ=40 ./build_ber.sh gs sd_2g5p1_txneg 7 N1 1 N2 5 N3 5 OUTDIV 2 PROFILE 1 TX_NEG 1
FREQ=40 ./build_ber.sh m2 e1_2g5p1_txneg 2 N1 1 N2 5 N3 5 OUTDIV 2 PROFILE 1 TX_NEG 1
```

`FREQ` sets the nextpnr timing target (2.5 G needs rclk ≥ 31.25 MHz, 5 G ≥ 62.5 MHz; the summary line prints the Fmax).
Tests: `python3 -m unittest discover -s tools/tests`; checker simulation in `gateware/ber/sim/`.

---

## 8. Open items, in order

1. **5 Gb/s:** hardware side — refclk at M2 (scope at C129/C130, or the local X2 of §6), the FFC→M.2 adapter chain, crosstalk.
   Use `lab9.sh` unchanged as the before/after test.
2. **2.5 Gb/s error-free:** timing constraints for the SerDes ports in nextpnr (report `TMG_IGNORE` upstream). Until then:
   `TX_NEG=1` and seeds chosen by ≥ 3 loads.
3. Eye counters: ask Cologne Chip / Patrick Urban how they are started.
4. `RX_TH_MON = 15` (rail) and `RX/TX_CALIB_CAL = 0` on both boards at all rates — meaning unknown, ask Cologne Chip.
5. Trace the P/N swap (GS → baseboard → slot → adapter → M2).
6. Cable-pull steps of `verify_external_link.sh` (need a person).
7. A long soak at 2.5 G (≥ 30 min, target < 10⁻¹²) with the best pair after the GS decoupling.

---

## 9. Where things are

| File | Content |
|---|---|
| `README.md` | overview, what works / does not, bitstreams, how to repeat |
| `docs/VERIFY_20260926.md` | verification: no loop, polarity, refclk, BER checker, rate sweep 0.3–2.5 G |
| `docs/VERIFY_20260926_RATES.md` | 2.5 / 5 G: all tuning (§1–§9), hardware A/B (§10) — **the lab book** |
| `docs/TUNING_5G.md` | every tunable register with DS page, channel analysis, experiment plan |
| `docs/SI_SERDES_GS_v004.md` | PCB SI of GS v005 and M2, max rate, next-revision changes |
| `docs/LOCAL_REFCLK_M2.md` | local oscillator on M2, CDR integrator |
| `docs/NEXTPNR_SETUPHOLD_PATCH.md` | why the pu-cc nextpnr patch is wrong |
| `docs/REVIEW_20260926.md`, `SOURCES_20260926.md` | first review; datasheets and reference designs |
| `docs/data_2026092*/t<task>/` | raw data: the lab scripts exactly as run, their output, one JSON per load |
| `bitstreams/README.md` | every bitstream: design, settings, result, build command |
| `tools/README_verify_external_link.hr.md` | external-lane test (Croatian) |
