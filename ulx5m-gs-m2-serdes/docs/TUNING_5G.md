# GS↔M2 SerDes to 5 Gb/s: what to tune, what to measure, what needs hardware (TASK-5065)

**Order:** Goran, Telegram 26.09.2026 21:44: *"There are a lot of things we should check to reach for example 5 Gbit/s.
Driver strength, equalizer settings etc. so please do more research what is needed to get there."*
**Author:** Manda (REGOČ research). **For:** Jelena (TASK-5063, board work). **No board was touched for this document.**
**Update 26.09.2026 22:30 (TASK-5067):** Goran, Telegram 22:19: *"Na obje ploče jumper je na 1.1V."* J3 = 2‑3 (VDD_CORE 1.1 V)
on **both** GS and M2, checked on the boards. The SerDes supply is therefore **in spec** and is no longer a suspect. §0 item 1,
§1.7, §3 (E0/E1, new order) and §4 (H1) are updated. The 5–12 % BER at 5 Gb/s was measured **with** VDD_SER in spec.
**Starting point:** `VERIFY_20260926_RATES.md` up to commit `e3a6375`:
- 2.5 Gb/s with `PROFILE=1` in the bitstream: BER 6.7·10⁻¹¹ (m2→gs) and 1.2·10⁻⁹ (gs→m2) over 300 s.
- 5 Gb/s: the CDR locks, but BER is 5–12 %.

Tags: **VERIFIED** = read in the datasheet, the code or the schematic/PCB (location given). **DERIVED** = arithmetic from
verified numbers. **UNVERIFIED** = inference or estimate. It needs a board test or a document we do not have.

Page numbers: DS1001 = `DS1001_GateMate1_datasheet_2026-09.pdf`, UG1001 = March 2025. Both are in
`regoc_system/docs/ulx5m-serdes/sources_20260926/`. "pu-cc" = `github.com/pu-cc/gm_serdes_lb` (Patrick Urban,
CologneChip): `56aa48b` is HEAD (checked by `git fetch` on 26.09.2026: no newer commits), `22bbe50` is the last change
to `serdes_lb.v`, and `ab7ce94` is "prepare 5G tests".

---

## 0. Short version: the five things most likely to matter for 5 Gb/s

1. ~~**The SerDes supply is probably out of spec on both boards.**~~ **RESOLVED (26.09.2026 22:19): J3 = 2‑3 = 1.1 V on both boards (Goran, checked on the boards). The DC supply level is in spec; it does not explain the 5 G BER.**
   - `VDD_SER` and `VDD_SER_PLL` come from `VDD_CORE` through **1 Ω resistors**: R106 and R105, 100 nF each, ferrites L6/L7 DNP on GS and not on the M2 PCB at all. VERIFIED.
   - J3 "Vcore_sel": open = 0.9 V (factory default), 1‑2 = 1.0 V, **2‑3 = 1.1 V ← both boards**. The ulx5m-gs-hw README note (*"DEFAULT VCC CORE is 0.9V - if you use SerDes this needs to be higher"*) was already done.
   - DS1001 p.155: **VDD_SER = 1.00–1.10 V**. At 40–51 mA (5 Gb/s, Table 4.4) the 1 Ω drops 40–51 mV, so **VDD_SER ≈ VDD_SER_PLL ≈ 1.05–1.06 V** (DERIVED). **Reserve ≈ 50 mV to the 1.00 V minimum** and ≈ 40–50 mV to the 1.10 V maximum (at nominal VDD_CORE).
   - What is left of the supply topic is **noise, not DC level**: 1 Ω / 100 nF filters only above ≈ 1.6 MHz, and the SerDes PLL is an all-digital DCO (§1.7). With VDD_CORE's own ±50 mV tolerance (MPM3833C mode spec) the corners are: low = 1.05 V − 51 mV ≈ **1.00 V** (reserve ~0), high = 1.15 V − 40 mV ≈ **1.11 V** (10 mV over p.155, still under the 1.15 V of p.154) (DERIVED). The nominal 1.1 V setting sits in the middle of the window, so both corners touch an edge only if the regulator is at its tolerance limit. A one-off multimeter reading of TP10/TP8 (§4, H1) tells which case we are in; it is no longer a blocker.
   - Consequence: the other items move up. **The most likely causes of 5–12 % BER are now RX peaking (item 4), TX_DETECT_RX (item 2), refclk distribution/jitter (§2.4) and reflections (item 5).**
   - Also consistent with 1.1 V: nextpnr-himbaechel for GateMate defaults to `fpga_mode` 3 = **SPEED** (1.1 V) and `time_mode` 3 = WORST (`gatemate.cc:44–45`, speed grade `worst_spd`). The fabric Fmax numbers (gs checker 44 MHz) were therefore computed for the voltage the boards really run at — they stay valid. Fabric PLL DCO range in SPEED mode is also the widest (`pll.cc`, eco = 1000–2000 MHz).
2. **The TX receiver-detect input is held high in our gateware; upstream holds it low.** UNVERIFIED effect, one rebuild to test.
   - Our code: `ber_top.v:94` and `baseline/serdes_lb_*.v:435` have `.TX_DETECT_RX_I(1'b1)`. That is the old CologneChip `serdes_lb.v`.
   - Patrick changed it to `1'b0` in `dda07f7` (2025-10-28, "fix CDR parameter"). It has stayed 0 since, including `ab7ce94`/`22bbe50`.
   - While receiver detection is active, the driver uses a **third, separate parameter set** (`*_RXDET`: TX_AMP_RXDET = 15, no pre/post-cursor) and a modified common mode (DS p.73).
3. **Settings must be in the bitstream, not written into a running link** (Jelena's `e3a6375`: 1·10⁻⁷ over JTAG vs 6.7·10⁻¹¹ baked in). VERIFIED on the boards.
   - Termination calibration (`TX_CALIB_EN` 0x3C[0], `RX_CALIB_EN` 0x02[0], both W/C) and DFE adaptation run from reset.
   - A JTAG sweep must therefore re-trigger calibration and reset RX/DFE after each write (§3, "sweep procedure").
   - Also: `PROFILE=0` has `TX_CALIB_EN=0` (`ber_top.v:54`). Keep 1 in every profile.
4. **At 5 Gb/s the RX needs more peaking, not less.** DS p.78: `RX_AFE_PEAK` **0 = maximum, 31 = minimum** peaking. VERIFIED (DS), consistent with the measurements.
   - The pu-cc 5G value 24 (0x18) is *less* peaking than the default 16. At 5 Gb/s Jelena measured PEAK 15 → 6·10⁻² and PEAK 24 → 7–12·10⁻².
   - The unexplored direction is **PEAK 15 → 0**, with GAIN 0…3 and the DFE on.
5. **The channel is moderate-loss.** Insertion loss is estimated at ≈ 5–7 dB at 2.5 GHz (DERIVED/UNVERIFIED, §2). That is well inside what a 5 Gb/s SerDes with TX FFE + CTLE + DFE is designed for.
   - So loss alone does not explain 5–12 % BER. Supply (1), refclk/jitter (§2.4) and reflections (the 90 Ω FFC, connectors) are more likely.
   - Supporting evidence: GAIN 0 is best, i.e. the input is large, and TX FFE *hurt* at 2.5 Gb/s, i.e. little ISI at 1.25 GHz.

Also found:
- **`tools/eyescan.py` sets the `RX_TH_MON2` override at 0x05[11].** The vendor register map (`serdestool.py` 56aa48b L320–326) marks 0x05[5] and 0x05[11] as *unused*. It puts the overrides at **0x06[5] (TH_MON1 + TAPW)** and **0x06[11] (TH_MON2 + AFE_OFFSET)**. See §5.1.
- **The P/N swap is not on GS, not on the Waveshare baseboard and not on M2.** All three follow the CM5 / Raspberry Pi FFC / M.2 pinouts. It must be in the FFC-to-M.2 adapter chain (§2.3).

---

## 1. (a) Parameter table

Columns:
- **Reg** = regfile address[bits] (DS1001 Table 2.59, p.90–98); the CC_SERDES parameter has the same name (UG1001 p.122–124).
- **DS def** = datasheet default.
- **P0** = our `PROFILE=0` (`cc_serdes_params.vh`).
- **pu-cc 5G** = `ab7ce94`/`22bbe50` = our `PROFILE=1`.
- **Measured** = Jelena, TASK-5063.

### 1.1 TX driver (DS p.70–73, Fig 2.36, Table 2.36)

The driver has 125 current branches in three groups:
- 63 main-only (`TX_BRANCH_EN_MAIN`),
- 31 main-or-pre (`TX_BRANCH_EN_PRE`),
- 31 main-or-post (`TX_BRANCH_EN_POST`).

`TX_SEL_PRE` / `TX_SEL_POST` move that many branches of the pre/post group to the pre/post cursor. Formulas (DS eq. 2.9–2.12):

- I_TX = (TX_TAIL_CASCODE + 10)·(TX_AMP + 1)·9.375 µA
- N_BRA = BR_PRE + BR_MAIN + BR_POST
- N_MAIN = N_BRA − SEL_PRE − SEL_POST
- Voltage levels: Va = (N_MAIN − N_PRE + N_POST)·I·50 Ω (signal), Vb = (N_MAIN − N_PRE − N_POST) (de-emphasised), Vc = (N_MAIN + N_PRE − N_POST) (pre-emphasised), Vd = N_BRA (boost).
- **FFE depth = 20·log10(Vb/Vd) = 20·log10((N_BRA − 2·(SEL_PRE+SEL_POST)) / N_BRA)**. DERIVED from eq. 2.12.

Taken literally, the absolute formula gives volts that are impossible (87 branches × 4.2 mA × 50 Ω). Use it **only for ratios**; the absolute swing is UNVERIFIED. serdestool's "TX driver info" (45b1dc3, L1536–1552) prints the same numbers.

| Parameter | Reg | Range | DS def | P0 | pu-cc 5G | Measured | Recommendation / sweep | Tag |
|---|---|---|---|---|---|---|---|---|
| `TX_AMP` (unit current = swing) | 0x30[14:10] | 0–31 | 15 | 15 | **31** | 2.5 G: 24 best; 4, 8, 15, 31 worse (PROFILE 0 + JTAG) | 5 G, after the supply fix: 20, 24, 28, 31. VDD_SER is in spec (J3 1.1 V), so an optimum below 31 is not a low-supply effect → look at reflections/over-drive | VERIFIED reg / meas. |
| `TX_BRANCH_EN_MAIN` | 0x31[10:5] | 0–63 | 63 | 63 | 63 | — | keep 63 | VERIFIED |
| `TX_BRANCH_EN_PRE` | 0x31[4:0] | 0–31 | 0 | 0 | **12** | — | 0 or 12 (pre-cursor only if post alone is not enough) | VERIFIED |
| `TX_BRANCH_EN_POST` | 0x31[15:11] | 0–31 | 0 | 0 | **12** | — | 31 for a deeper post-cursor sweep | VERIFIED |
| `TX_SEL_PRE` | 0x30[4:0] | 0…BR_PRE | 0 | 0 | **5** | 5/12 pre+post hurt at 2.5 G | 5 G: 0, 2, 5 | VERIFIED |
| `TX_SEL_POST` | 0x30[9:5] | 0…BR_POST | 0 | 0 | **5** | see above | 5 G with BR_POST=31, BR_PRE=0: **0, 6, 12, 17, 20** = 0, −1.2, −2.6, −3.9, −4.8 dB (PCIe Gen2 uses −3.5 / −6 dB) | DERIVED dB |
| pu-cc 5G FFE depth | — | — | — | 0 dB | **−2.3 dB** (N_BRA 87, 5+5 → 67/87) | — | reference point | DERIVED |
| `TX_DC_ENABLE` (common-mode branches) | 0x32[9:3] | 0–127 | 63 | 63 | **43 = N_BRA/2** | — | **always N_BRA/2** (Patrick's rule, `22bbe50`: `(PRE+MAIN+POST)/2`) → 47 for 0+63+31 | VERIFIED rule, reason UNVERIFIED |
| `TX_DC_OFFSET` | 0x32[14:10] | 0–31 | 0 | 8 | 8 | — | 8 (DS p.71: "Set to 8") | VERIFIED |
| `TX_TAIL_CASCODE` | 0x32[2:0] | 0–7 | 4 | 4 | 4 | — | 4 (DS: "Keep default") | VERIFIED |
| `TX_CM_RAISE`, `TX_CM_THRESHOLD_0/1` | 0x33 | 5 b each | 0 / 14 / 16 | same | same | — | keep. V_CM window = VDD·(14+TH)/60 (eq. 2.13); reading `TX_CM_SAR_RESULT_0/1` (0x3E) needs TH0 = TH1 | VERIFIED |
| `TX_CM_REG_EN`, `TX_CM_REG_KI` | 0x3D[9], [7:0] | — | 1, 0x80 | same | same | — | keep | VERIFIED |
| `TX_CALIB_EN` (TX termination calibration) | 0x3C[0] W/C | 0/1 | 0 | **0** | **1** | part of the `e3a6375` gain | **1 in every bitstream**. Read `TX_CALIB_DONE` 0x3C[1] and `TX_CALIB_CAL` 0x3C[10:7] on both boards | VERIFIED |
| `TX_POLARITY_I` / 0x41[5] (+OVR 0x41[4]) | port | 0/1 | 0 | 0 | 0 | swap is fixed on RX | keep 0 | VERIFIED |
| **`TX_DETECT_RX_I`** (port) | port (+0x41[2:3] OVR) | 0/1 | — | **1** | **0** | never tested | **0** (§0 item 2) | VERIFIED difference / UNVERIFIED effect |
| `*_EI`, `*_RXDET` sets | 0x34–0x3B | as normal | as normal | defaults | defaults | — | only matter in electrical idle / receiver detect. With TX_DETECT_RX_I=0 the RXDET set is unused | VERIFIED |
| Slew-rate control | — | — | — | — | — | — | **no slew field exists** in Table 2.59 or UG1001 7.12 | VERIFIED (absence) |
| TX termination | internal, calibrated | — | — | — | — | — | external R110 is **DNP** on GS and M2 (correct) | VERIFIED |

### 1.2 RX analog front end, termination (DS p.74, 78–79, Tables 2.41–2.42)

| Parameter | Reg | Range | DS def | P0 | pu-cc 5G | Measured | Recommendation / sweep | Tag |
|---|---|---|---|---|---|---|---|---|
| `RX_AFE_PEAK` (CTLE peaking) | 0x09[4:0] | 0–31, **0 = max, 31 = min** | 16 (serdestool: 15) | 15 | **24** (= less) | 2.5 G: 20–31 flat. 5 G: 15 better than 24 | **5 G: 16, 12, 8, 4, 0** (more peaking) | VERIFIED DS / meas. |
| `RX_AFE_GAIN` | 0x09[8:5] | 0–15 (0 = min) | 8 | 8 | **0** | **key**: 0 → 6·10⁻⁷, 4/8 → 2·10⁻² (2.5 G) | 5 G: 0, 1, 2, 3 | VERIFIED |
| `RX_AFE_VCMSEL` (internal CM) | 0x09[11:9] | 0–7 | 4 | 4 | 3 | part of the AFE step | 2, 3, 4 | VERIFIED |
| `RX_RTERM_VCMSEL` (line CM through RTERM) | 0x02[13:11] | 0–7 = (18…25)/29·VDD_SER | 4 | 4 | 3 | part of the AFE step | 2, 3, 4. **Absolute CM follows VDD_SER** (Table 2.42): at the actual ≈ 1.05 V supply code 3 is ≈ 0.76 V (0.72 V at 1.0 V) | VERIFIED / DERIVED |
| `RX_CALIB_EN` (termination calibration) | 0x02[0] W/C | — | 0 | 1 | 1 | — | 1. Read `RX_CALIB_DONE` 0x02[1] and `RX_CALIB_CAL` 0x02[10:7]; `RX_CALIB_OVR/VAL` only for experiments | VERIFIED |
| `RX_RTERM_PD` | 0x02[14] | 0/1 | 0 | 0 | 0 | — | 0 (AC-coupled link) | VERIFIED |
| Internal R_TERM | — | 100 Ω diff (p.155); calibration reference is the 200 Ω on `SER_RTERM` | — | — | — | — | GS and M2 fit **R109 = 200R 1 %** on SER_RTERM (V12). External R107 across RX is **DNP** (correct) | VERIFIED |
| `RX_EI_*` | 0x1E | — | 4/4/0/0 | same | same | — | not used (no electrical idle) | VERIFIED |

### 1.3 RX DFE (DS p.74, 77, 80–81, Tables 2.44–2.45)

The DS calls it a "3-tap DFE". Only **one** writable tap weight (`RX_TAPW`) and one status tap (`RX_EQA_TAPW`) are visible, so how the 3 taps map is UNVERIFIED.

| Parameter | Reg | Range | DS def | P0 | pu-cc 5G | Measured | Recommendation | Tag |
|---|---|---|---|---|---|---|---|---|
| `RX_EN_EQA` (DFE adaptation) | 0x04[8] | 0/1 | 0 | 0 | **1** | **5 G: CDR locks only with DFE on** | 1 at 2.5 and 5 G | VERIFIED |
| `RX_EQA_LOCK_CFG` | 0x04[12:9] | bit1 = monitor output for capture, bit2 = tap weight ÷2, bit3 = 1: HF amplitude / 0: LF | 0 | 0 | **0xC** | — | 0xC. Try 0x4 (LF amplitude) and 0x8 (no ÷2) at 5 G | VERIFIED |
| `RX_EQA_CKP_LF/HF`, `RX_EQA_CKP_OFFSET` | 0x03, 0x04[7:0] | 8 b | 0xA3/0xA3/0x01 | same | same | — | keep. Lower = slower but less noisy adaptation (UNVERIFIED direction) | VERIFIED |
| `RX_EQA_CONFIG` | 0x08 | 16 b | 0x01C0 | same | same | — | undocumented bits, keep | VERIFIED |
| `RX_TAPW`, `RX_AFE_OFFSET`, `RX_TH_MON1/2` | 0x05, 0x06 | 5 b signed | 8 | 8 | 8 | — | only as overrides for experiments (bit positions: §5.1) | VERIFIED DS / conflict |
| **Status to log every run** | `RX_EQA_LOCKED` 0x04[13]; `RX_EQA_TAPW` 0x07[4:0], `RX_TH_MON` 0x07[9:5], `RX_OFFSET` 0x07[13:10] | — | — | — | — | not logged yet | the adapted tap is the cheapest on-chip ISI indicator: compare it across directions and settings | VERIFIED |

### 1.4 CDR (DS p.82, Table 2.48; regfile 0x0A–0x10)

| Parameter | Reg | Range | DS def | P0 | pu-cc 5G | Measured | Recommendation | Tag |
|---|---|---|---|---|---|---|---|---|
| `RX_CDR_CKP` (proportional gain) | 0x0A[7:0] | 8 b | 0xF8 | 0xF8 | **0x3E** | 2.5 G: +CKP/TRANS_TH 2.8→1.0·10⁻⁷ | 5 G: 0xF8, 0x7E, 0x3E, 0x1E. The encoding is not documented. gatemate-pipe's comment `old: {3'b101, 5'b01111}` hints at a 3+5-bit split | VERIFIED reg / UNVERIFIED meaning |
| `RX_CDR_CKI` (integral gain) | 0x0A[15:8] | 8 b | 0 | 0 | 0 | — | 0 (shared refclk → no frequency offset). Try 1–2 only if `FREQ_ACC_VAL` wanders | VERIFIED |
| `RX_CDR_TRANS_TH` | 0x0B[14:8] | **7 b**, def **8** | 8 | **0** (9'h80 truncated) | 8 | fixed in PROFILE 1 | 8, 16, 32 | VERIFIED (UG1001 still says 9 b / 128, wrong) |
| `RX_CDR_LOCK_CFG` | 0x0B[7:0] | 8 b: [0] lock window, [2:1] phase comp cap, [4:3] phase comp lock, [7:5] freq comp | 0xD5 | **0x0B** | 0xD5 | — | 0xD5 (UG1001's 6-bit 0x0B is the old map) | VERIFIED |
| `RX_CDR_FORCE_LOCK` | 0x10[2] | 0/1 | 0 | 0 | 0 | — | **never for BER**: it hides a CDR that has not locked | VERIFIED |
| `RX_WAIT_CDR_LOCK` | 0x01[15] | 0/1 | 1 | 0 | 0 | — | 0 (pu-cc: "turn off if loopback enabled") | VERIFIED |
| Status | `RX_CDR_LOCKED` 0x0B[15]; `FREQ_ACC_VAL` 0x0C; `PHASE_ACC_VAL` 0x0D | — | — | — | — | — | log. With one shared refclk the frequency accumulator should sit still; drift = refclk or PLL problem | VERIFIED reg / UNVERIFIED interpretation |

### 1.5 PCS: comma/slide, elastic buffer, polarity

| Parameter | Reg | Value now | Recommendation | Tag |
|---|---|---|---|---|
| `RX_SLIDE_MODE` | 0x13[11:10] | 00 | 00 is required for automatic comma alignment (pu-cc `22bbe50`) ✓ | VERIFIED |
| `RX_MCOMMA/PCOMMA_ALIGN_I`, `RX_COMMA_DETECT_EN_I` | ports | 1/1/1 | ✓. pu-cc uses the `_OVR` register versions instead: same effect | VERIFIED |
| `RX_ALIGN_COMMA_WORD` | 0x12[13:12] | 3 (32-bit) | ✓ | VERIFIED |
| `RX_BUF_BYPASS` / `RX_CLKCOR_USE` | 0x25[0] / [1] | 0 / 0 | ✓. Shared refclk → no clock correction needed. Monitor `RX_BUF_ERR` 0x2A[14] | VERIFIED |
| `RX_POLARITY_I` | port | 1 (both boards) | ✓ (swap location: §2.3) | VERIFIED |
| fabric↔SerDes interface timing | — | `TX_NEG` | nextpnr does not time SERDES ports (`delay.cc` TMG_IGNORE, Jelena §2 cause 2). At 5 G the word clock is 62.5 MHz (16 ns) — keep `TX_NEG`/`RX_NEG` and seed selection | VERIFIED (Jelena) |

### 1.6 PLL / BISC / refclk (DS p.53–60, 155)

| Parameter | Reg | Value for 5 G | Note | Tag |
|---|---|---|---|---|
| `PLL_MAIN_DIVSEL` / `PLL_OUT_DIVSEL` / `PLL_FCNTRL` | 0x51 | **0x06FA** = N 1·5·5, M3 = 1, FCNTRL 58 (80-bit, PLL_CLK_O 62.5 MHz) | f_DCO = 2500 MHz = **top edge** of 1250–2500 MHz (p.155) | VERIFIED / DERIVED |
| 6.4 Gb/s (2·4·4, DCO 3.2 GHz) | — | — | **outside DS1001** (DCO > 2500 MHz, data rate > 5 Gb/s). Do not try before 5 G is clean | VERIFIED |
| `PLL_CI` / `PLL_CP` | 0x52 | 3 / 80 (0x50) | regfile map says CP 80. Table 2.18 says 12, a DS inconsistency. BISC overwrites CP anyway | VERIFIED |
| `PLL_FILTER_SHIFT`, `FAST_LOCK`, `LOCK_WINDOW` | 0x53[8:7], 0x50[6], 0x50[5] | 2, 1, 1 | keep | VERIFIED |
| `PLL_BISC_MODE` (loop-gain self-calibration) | 0x57[2:0] | **5** = mode B + enable (ours = pu-cc ✓) | DS: mode B preferred. `TIMER_MAX` 0xC, `CP_MIN/MAX/START` 6/30/6, `CAL_SIGN` 1 (Patrick's values, ours are the same) | VERIFIED |
| **PLL status to log** | 0x55: `PLL_LOCKED`[0], **`PLL_CAP_FT_OF`[1], `PLL_CAP_FT_UF`[2]**, `PLL_CAP_FT`[12:3], `CAP_STATE`[14:13]; 0x5A: `BISC_TIMER_DONE`[0], `BISC_CP`[7:1]; 0x5B `BISC_CO` | — | FT overflow/underflow = the DCO fine-tune is at its end, i.e. the DCO cannot reach 2.5 GHz. VDD_SER_PLL DC is in spec (J3 1.1 V), so a flag would point to supply noise or the refclk | VERIFIED reg / UNVERIFIED interpretation |
| `PLL_REF_SEL` / `PLL_REF_RTERM` | 0x50[10] / [11] | 1 / 1 | LVDS input with internal termination. For the shared-clock topology see §2.4 | VERIFIED |
| Refclk requirement | — | 100–125 MHz, **jitter ≤ 1 ps** (J_SER, p.155) | GS X2 = Skyworks/SiLabs **511FCA100M000BAG** (Si511 LVDS, 100 MHz) → the source is fine; the distribution is the question (§2.4) | VERIFIED |

### 1.7 Supply (DS p.128, 155, pin list p.176–177)

| Pin (CCGM1A1) | Requirement | ULX5M-GS (schematic) | ULX5M-M2 (PCB) | Tag |
|---|---|---|---|---|
| `VDD_SER` U12, V17 | 1.00–1.10 V (p.155; 1.15 V in the recommended table p.154). 36–51 mA (Table 4.4). "should be connected to noise filters" (p.128) | from VDD_CORE through **R106 = 1 Ω** 0603, **C128 = 100 nF** only; ferrite L7 (MPZ1608) **DNP**; R9 DNP; TP10 | same: R106 1 Ω, C128 100 nF, no ferrite footprint; TP10 | VERIFIED |
| `VDD_SER_PLL` T16 | 1.00–1.10 V | from VDD_CORE through **R105 = 1 Ω**, **C127 = 100 nF**; L6 **DNP**; TP8 | same; TP8 | VERIFIED |
| `VDD_CORE` | 0.9 / 1.0 / 1.1 V ±50 mV by mode | MPM3833C, R15 20k / R12 40.2k, **J3 Vcore_sel: open 0.9 V, 1‑2 1.0 V (‖120k), 2‑3 1.1 V (‖60k)** | same (R12 40k, R14 120k, R16 60k, J3 marked DNP/open on PCB) | VERIFIED; **board state: J3 = 2‑3 = 1.1 V on both boards (Goran, 26.09. 22:19)** |
| `VDD_CLK` T14 (SER_CLK input buffer) | 1.1–2.7 V | +1V8 | VDD_CLK net (also X2) | VERIFIED |
| Estimated VDD_SER at 5 G | ≥ 1.00 V | 0.9 V core → ≈ 0.85 V; 1.0 → ≈ 0.95 V; **1.1 (actual) → ≈ 1.05–1.06 V, reserve ≈ 50 mV to 1.00 V** (≈ 0 mV at the −50 mV regulator corner; ≈ 1.11 V at the +50 mV corner, 10 mV over p.155) | same (J3 also 2‑3) | DERIVED (1 Ω × 40–51 mA; MPM3833C Vref 0.6 V from the schematic note) |

RC corner of 1 Ω / 100 nF ≈ 1.6 MHz (DERIVED). This barely filters the core switching noise that the fabric (checker at 31–62 MHz) puts on
VDD_CORE, and the SerDes PLL is an **all-digital** PLL (DCO). Supply noise becomes DCO jitter directly (UNVERIFIED magnitude).

---

## 2. (b) Channel analysis

### 2.1 The physical path (both directions)

```
GS U4 (CCGM1A1) ── GS PCB ── J1 (CM5 HSIO, Hirose DF40) ── Waveshare CM5-IO-BASE-A ── P1 16-pin 0.5 mm FFC
  ── FFC cable ── [adapter chain, UNVERIFIED: FFC→M.2 or FFC→PCIe x1 slot→M.2] ── M.2 M-key J10 ── M2 PCB ── M2 U4
```

| Segment | TX direction (GS→M2) | RX direction (M2→GS) | Source | Tag |
|---|---|---|---|---|
| GS PCB | U4.U13/V13 → 15 mm → **C134/C135 100 nF 0402** → 10.5 mm → J1.22/24 (CM pins 122/124 = PCIe_TX_P/N); 0.127 mm, 1 via | J1.16/18 (116/118) → 27 mm → U4.U11/V11; 1 via; no series C (AC coupling is on the M2 TX) | `ulx5m-gs-hw` netlist + PCB (`pcbnets.py`) | VERIFIED |
| GS impedance | Z_diff 101.8 Ω (RX pair, FAST-TRACK-SIM model) | | `FAST-TRACK-SIM/boards/ulx5m-gs/impedance_cache.json` | VERIFIED (model) |
| Baseboard | CM5 connector → P1 pins 10/11 (TX_P/N) | P1 7/8 (RX_P/N) → CM5 116/118 | Waveshare `CM5-IO-BASE-A_Sch.pdf`, sheet block P1 "PCIe 2.0 100Ω" | VERIFIED pinout; trace length unknown |
| P1 pinout | 1‑2 5V, 3 GND, 4/5 CLK_P/N, 6 GND, 7/8 RX_P/N, 9 GND, 10/11 TX_P/N, 12 GND, 13 PWR_EN, 14 WAKE, 15 CLKREQ, 16 nRST | | = Raspberry Pi 5 PCIe FFC standard (RP-008298-DS Fig. 2, zig-zag numbering) | VERIFIED |
| FFC | RPi spec: **≤ 50 mm, 90 Ω ±10 %, opposite-side contacts**, Gen 2 (5 GT/s) official | | `pcie-connector-standard.pdf` ch.3 | VERIFIED spec; our cable UNVERIFIED |
| Adapter(s) | UNVERIFIED. The README says "PCIe slot through a PCIe-to-M.2 adapter". The CM5-IO-BASE-A has **no PCIe slot**, only P1 FFC. So either FFC→M.2 directly, or FFC→x1 slot board→x1-to-M.2 riser | | lab docs disagree | UNVERIFIED |
| M2 PCB | J10 → M2 FPGA RX (PCIe_RX = J10.47/49 = PETn0/PETp0): 63–64 mm, 0.147 mm, **2 vias**, Z_diff 93.3 Ω | M2 TX U4.U13/V13 → 60–61 mm → **C143/C144 220 nF 0201** → PET/PER0 pins; 2 vias, Z_diff 94.9 Ω | FAST-TRACK-SIM `ulx5m-m2.kicad_pcb`, `impedance_cache.json` | VERIFIED |
| AC coupling | exactly one series C per direction (GS 100 nF on GS TX, M2 220 nF on M2 TX) — if the adapters add none | | netlists | VERIFIED on GS/M2 |
| Intra-pair skew | M2 RX 1.36 mm, TX 0.80 mm; GS < 0.25 mm → < 10 ps ≈ 0.05 UI at 5 G | | `pcbnets.py` | DERIVED |

### 2.2 Loss estimate at the 5 Gb/s Nyquist frequency (2.5 GHz)

Trace model: conductor loss 36/(w_mil·Z0)·√f × 1.4 roughness + dielectric loss 2.3·f·Df·√ε_eff, with FR4 Df 0.02 and ε_eff ≈ 3.2. DERIVED. Numbers from `python3` in `~/.tmp/t5065` (the formula is in this document, so anyone can repeat it).

| Part | Length | dB @ 1.25 GHz (2.5 G) | dB @ 2.5 GHz (5 G) | Tag |
|---|---|---|---|---|
| GS traces | 25–27 mm, 0.127 mm | 0.35 | 0.55 | DERIVED |
| CM5 connector (DF40) | — | ~0.2 | ~0.3–0.5 | UNVERIFIED (typical) |
| Baseboard traces | ~40 mm? | 0.5 | 0.8 | UNVERIFIED length |
| 2× FFC connectors + FFC ≤ 50 mm | — | ~0.5–1 | ~0.8–1.5 | UNVERIFIED (typical) |
| Adapter(s) + M.2 connector | ~30 mm? | ~0.5 | ~0.8–1.5 (+1–2 dB if there is a slot + second adapter) | UNVERIFIED |
| M2 traces | 60–64 mm, 0.147 mm, 2 vias | 0.75 | 1.2 | DERIVED |
| **Total** | | **≈ 3–4 dB** | **≈ 5–7 dB** (7–9 dB with slot variant) | DERIVED/UNVERIFIED |

**Margin:** a PCIe Gen2-class SerDes is designed for channels around 10–15+ dB at 2.5 GHz, using the −3.5/−6 dB TX de-emphasis plus RX EQ (general knowledge, UNVERIFIED for GateMate). The loss is therefore not the first suspect. What the numbers do not capture:
- **Impedance steps**: 100 Ω boards vs a 90 Ω FFC (spec), connectors, and 0201/0402 cap pads. Reflections cause ISI that TX FFE does not fix and the DFE only partly fixes.
- **Crosstalk** in the FFC: TX and RX are 2 pins apart with one GND between them.

The measurements agree:
- `RX_AFE_GAIN 0` is best → the signal arriving at the RX is large, not small.
- TX FFE hurts at 2.5 Gb/s → at 1.25 GHz there is little ISI to cancel.

At 5 Gb/s the loss roughly doubles in dB, so some FFE/peaking is expected to help there (§3 E2/E3).

### 2.3 Where the P/N swap is

| Place | Finding | Tag |
|---|---|---|
| GS | SER_RX_P → PCIe_RX_P → J1.16 (CM pin 116 = PCIe_RX_P); SER_TX_P → C134 → J1.22 (122 = PCIe_TX_P). No swap | VERIFIED (netlist) |
| Waveshare CM5-IO-BASE-A | nets PCIE_RX/TX_P/N from the CM5 socket to P1 7/8/10/11 keep their names; P1 = Pi 5 FFC pinout exactly | VERIFIED (schematic labels; copper not checked) |
| M2 | M2 RX_P → J10.49 (PETp0), RX_N → J10.47 (PETn0); TX via C144/C143 → PET0P/PET0N net names on the PCB | VERIFIED (PCB) |
| FFC → M.2 adapter chain | **the only unchecked element → the swap must be here** (or a baseboard layout error under correct labels) | UNVERIFIED (identify the adapter) |

The swap costs nothing electrically (`RX_POLARITY_I=1`). It only matters if the adapter crosses the pair with vias (an extra discontinuity).
The refclk pair goes through the same adapter. An inverted LVDS clock is only a 180° phase shift, which is harmless.

### 2.4 Refclk distribution (probably important at 5 Gb/s)

- GS X2 (Si511 LVDS) drives **two AC-coupled branches**: C129/C130 → GS SER_CLK (8–10 mm, then 11 mm), and C136/C137 → J1 PCIe_CLK (1–3 mm) → baseboard → FFC → adapter → M2 J10.53/55 → C136/C137 → C129/C130 → M2 SER_CLK (52 mm + 12–15 mm). VERIFIED (netlists).
- Both FPGA inputs have `PLL_REF_RTERM=1` (internal termination). One LVDS driver then sees **two terminations in parallel**, i.e. about half the swing on each input (DERIVED, assuming ~100 Ω internal RTERM, which the DS does not state).
- M2 also sees **two series caps** (C136 + C129) and the whole channel's crosstalk. The DS allows only **1 ps** refclk jitter (p.155).
- Because both ADPLLs multiply the same clock ×25, refclk jitter at M2 that is uncorrelated with GS's shows up directly in the M2 receiver's CDR budget (UI = 200 ps at 5 G).
- Experiment E6: set `PLL_REF_RTERM=0` on GS only, so the short GS branch is an unterminated stub and the long line stays terminated at M2. Then compare M2's PLL/CDR status and BER.

---

## 3. (c) Experiment order for Jelena (highest expected gain first)

**Sweep procedure (applies to every JTAG sweep).** `e3a6375` showed that a value written into a running link does not reach the same state as a value in the bitstream. After each field write:
1. Re-trigger termination calibration: `0x3C[0]=1` (TX_CALIB_EN, W/C) and `0x02[0]=1` (RX_CALIB_EN, W/C).
2. Reset the DFE: `0x2B` EQA_RESET_OVR[2] + EQA_RESET[3], or the RX via RESET_OVR[10] + RESET[11]. Do **not** copy upstream `reset_serdes_rx` L1086–1087, which writes 0x3F instead of 0x2B.
3. Wait for `RX_EQA_LOCKED` and `RX_CDR_LOCKED`.
4. Clear the counters and measure.

Confirm every winner **in a bitstream** before quoting it.

**Repeat rule.** Run-to-run spread is ×10–100 (Jelena §2). Each A/B point needs **≥ 3 loads × 60 s**. Compare medians.

| # | Experiment | Who / cost | Pass criterion | Why here |
|---|---|---|---|---|
**Order changed 26.09.2026 (TASK-5067).** The supply is confirmed in spec, so the old E1 (Goran with a multimeter, possible J3 bridge) is
**no longer a gate**. E0 stays the first step but now only checks health; everything else moves forward by one.

| # | Experiment | Who / cost | Pass criterion | Why here |
|---|---|---|---|---|
| **E0** | **Health snapshot, read-only**, both boards, at 2.5 G (PROFILE 1) and 5 G. Log: 0x55 (PLL_LOCKED, **CAP_FT_OF/UF**, CAP_FT), 0x5A/0x5B (BISC done, CP, CO), 0x02 (RX_CALIB_DONE/CAL), 0x3C (TX_CALIB_DONE/CAL), 0x04/0x07 (EQA_LOCKED, TAPW, TH_MON, OFFSET), 0x0B–0x0D (CDR_LOCKED, FREQ/PHASE_ACC_VAL; 10 reads 1 s apart), 0x2A[12..14]. `eyescan.py get` works for all of these. **Supply: CONFIRMED by Goran (J3 2‑3 = 1.1 V on both boards, 26.09. 22:19)** — nothing to do on the hardware. There is no absolute on-chip voltage monitor in the SerDes register map we use (TX_CM_SAR 0x3E is ratiometric to VDD, eq. 2.13), so JTAG cannot replace a multimeter; the PLL/calibration flags are the indirect check | Jelena, 10 min, no rebuild | PLL locked, **no FT_OF/UF**, BISC done, calibration done, FREQ_ACC steady. A flag at 5 G but not at 2.5 G now points to DCO noise / refclk (§2.4, E6), not to the DC supply | Cheap. Tells whether 5 G fails in the PLL/CDR or in the data eye |
| ~~E1~~ | ~~Measure VDD_SER/VDD_SER_PLL, bridge J3~~ → **RESOLVED**: J3 = 2‑3 on both boards, VDD_SER ≈ 1.05–1.06 V (DERIVED, ≈ 50 mV reserve). Optional one-off TP10/TP8 reading = H1, not a gate | Goran, optional | — | Was §0 item 1 |
| **E1** | Rebuild with `TX_DETECT_RX_I=0` (ber_top.v:94) and `TX_CALIB_EN=1` in PROFILE 0 as well. A/B at 2.5 G PROFILE 1 (the gs→m2 1.2·10⁻⁹ direction), then 5 G | Jelena, 1 rebuild pair | 2.5 G: gs→m2 median BER ≥ 3× better, or no change (then keep 0 anyway = upstream). 5 G: CDR locked, BER vs baseline | Matches upstream; one rebuild (was E2) |
| **E2** | **5 G RX AFE sweep** (DFE on, `EQA_LOCK_CFG 0xC`): GAIN {0,1,2,3} × PEAK {16,12,8,4,0}; VCM 3. Log the DFE tap per point | Jelena, JTAG + sweep procedure | Find BER < 10⁻⁶ → continue; the best point should also show `RX_EQA_TAPW` away from the rail | Peaking toward 0 is unexplored and 15 > 24 already helped (was E3) |
| **E3** | **5 G TX FFE sweep, each direction on its own** (A's TX settings only affect B's RX): BR_PRE 0, BR_POST 31, `DC_ENABLE = N_BRA/2` = 47; SEL_POST {0,6,12,17,20} (0…−4.8 dB); then SEL_PRE {0,2,5} with BR_PRE 12; TX_AMP {20,24,28,31} | Jelena | ≥ 10× lower BER than the pu-cc 5/5 point | Loss doubles at 2.5 GHz; a Gen2 PHY normally uses −3.5 dB (was E4) |
| **E4** | **CDR loop**: CKP {0xF8, 0x7E, 0x3E, 0x1E} × TRANS_TH {8,16,32}, CKI 0 → then CKI 1, 2 if FREQ_ACC wanders | Jelena | stable lock over 60 s, lower BER | CKP encoding unknown → empirical (was E5) |
| **E5** | RX common mode: RTERM_VCMSEL and AFE_VCMSEL {2,3,4,5}. VDD_SER ≈ 1.05 V, so code 3 ≈ 0.76 V absolute (Table 2.42) | Jelena | lower BER | DS: "small input signal → higher CM" (was E6; no longer waits for the supply) |
| **E6** | Refclk: GS `PLL_REF_RTERM=0` (0x50[11]), rebuild or write + PLL restart (0x50[0] off/on); M2 unchanged | Jelena, 1 rebuild | M2 PLL/CDR status unchanged or better; 5 G BER m2-RX ≥ 3× better | §2.4; with the supply cleared, refclk is the main PLL/CDR suspect (was E7) |
| **E7** | Eye scan fix (§5.1): override at 0x06[11], `RX_EN_EQA=1`, `EQA_LOCK_CFG` bit1 = 1; if the counters still stay 0 → ask Patrick (the upstream `tc_eyemeas` is a stub) | Jelena, 30 min | non-zero `CORRECT_*` counters | Gives eye margin instead of BER-only (was E8) |
| **E8** | Bake the best E1–E6 point into a `PROFILE=2` (5 G) bitstream, check the rebuild is byte-identical, 300 s per direction; then the soak (§5.3) | Jelena | 5 G BER < 10⁻¹⁰ in 300 s → soak for < 10⁻¹² | Only the bitstream counts (`e3a6375`) (was E9) |
| E9 | Only if E2–E6 leave 5 G noisy: supply **noise** check — H2 (ferrite / extra µF on C127/C128) on GS, A/B at 5 G | Goran + Jelena | ≥ 3× lower BER after H2 | The DC level is fine; noise through 1 Ω/100 nF is the remaining supply risk |

Parallel track, not analog: gs fabric checker Fmax (44 MHz < 62.5 MHz word clock at 5 G, Jelena §3, next step 3). Without it, the m2→gs number at 5 G is not meaningful. JTAG `ber_jtag_check.py` samples are only a coarse substitute.

---

## 4. (d) What needs a hardware intervention (Goran)

| # | Action | Board | Effect | Priority |
|---|---|---|---|---|
| ~~H1~~ | ~~Bridge J3 2‑3~~ **RESOLVED 26.09.2026: J3 = 2‑3 (1.1 V) on both boards (Goran).** Optional: one multimeter reading of TP10/TP8 with the 5 G bitstream running, to confirm ≈ 1.05 V (reserve ≈ 50 mV to 1.00 V) | GS and M2 | VDD_SER ≈ 1.05–1.06 V = in spec | done / optional |
| H2 | Replace R105/R106 (1 Ω) with the MPZ1608 ferrites (L6/L7 footprints on GS; M2 has no footprint → keep the 1 Ω but add 2.2–4.7 µF next to C127/C128) | GS (M2 partly) | less drop (≈ 0.05 Ω DCR, typical) and real filtering above ~10 MHz | **1** now, but only if E2–E6 leave 5 G noisy (= E9) |
| H3 | **Identify the FFC and adapter chain**: part numbers or photo, FFC length (RPi spec ≤ 50 mm, 90 Ω). Is there a PCIe x1 slot in between? Use the shortest FFC | chain | completes §2.2/§2.3; finds the P/N swap | 2 |
| H4 | Optional scope check of the M2 refclk at C129/C130 (amplitude, edges) | M2 | confirms §2.4 | 3 |
| H5 | Next board spin: ferrite + 1–10 µF on VDD_SER/VDD_SER_PLL; SerDes supply from its own LDO at 1.05 V independent of Vcore; refclk fan-out buffer (one driver per load); SerDes path with no FFC | both | removes the three structural risks | later |

---

## 5. Measurement

### 5.1 On-chip eye scan (DS p.77, 81; pu-cc `eyetools.py` 83d7858, `tc_eyemeas` stub L1285)

- **Principle** (VERIFIED from the register map plus the `tc_eyemeas` signature `window=512, monitor=2, sel_tap, phase_step, tapw_sweep`):
  - Monitor 2 of the DFE samples at phase offset `RX_MON_PH_OFFSET` (0x15[5:0], signed; eyetools uses 64 codes per UI) and threshold `RX_TH_MON2` (5-bit signed).
  - `RX_EYE_MEAS_EN` (0x14[0], W/C, reads back as DONE) with window count `RX_EYE_MEAS_CFG` (0x14[15:4]) counts correct/wrong detections for the classes X11, X00, 001, 110 (0x16–0x1D).
  - BER per point = wrong / (correct + wrong). Margin = the width in phase codes (×UI/64) and the height in threshold codes where BER < target.
- **Why ours may read 0** (UNVERIFIED, in order):
  1. The threshold override is at the wrong bit: `eyescan.py th2_write` sets 0x05[11]. Vendor map: **0x06[11] = TH_MON2_OVR + AFE_OFFSET_OVR**, 0x06[5] = TH_MON1_OVR + TAPW_OVR; 0x05[5]/[11] unused. DS Table 2.44 lists only EXT_VALUE[3:0], without positions. That is a vendor-vs-DS conflict; follow the vendor tool. Note: setting 0x06[11] also overrides `RX_AFE_OFFSET` → write it with its current value (read 0x07[13:10] first).
  2. The monitor only runs with the DFE adaptation on (`RX_EN_EQA=1`) and `EQA_LOCK_CFG` bit1 ("select monitor output for capturing").
  3. `RX_EYE_MEAS_CFG` width: DS 12 bit [15:4] vs UG1001 15 bit. pu-cc `9c3b391` "fix RX_EYE_MEAS_CFG lsb start" → use the 56aa48b map (lsb 4).
- **How to read the margin once it works:** a horizontal opening of < ~0.3 UI or a vertical opening of a few threshold codes at BER 10⁻³ means no margin for 10⁻¹². Compare the two directions and the settings by **open area at 10⁻³** (`EyeData.open_area`).

### 5.2 PRBS: hard checker vs fabric checker

- Hard PRBS: only **PRBS-7 (001)** and **PRBS-15 (010)**; codes 011–101 are *Reserved* (DS p.70/86).
- The counter is 15 bits and saturates at 0x7FFF. It is cleared only via the pins, or via 0x2A[9] **with RX_PRBS_OVR=1** (VERIFIED).
- The checker sits *before* the 8b10b decoder. With 8b10b and comma alignment on, the comma aligner can re-slide inside the PRBS stream. The vendor `tc_prbs` runs with **8b10b off** on one board in loopback (UNVERIFIED as the cause of Jelena's ~1400–2200 errors/s floor).
- Keep the **fabric checker** (`ber_link.v`, exact bit counts + 8b10b code errors + sender IDs) as the BER instrument. Use the hard checker only as a quick lock indicator.
- **Far-end PMA loopback** (`LOOPBACK_I=100` on M2, DS p.62) returns GS's stream from M2's PMA over the whole channel. With that, GS alone measures both directions of the *channel* with one fabric checker (UNVERIFIED on our boards). It is useful while the gs checker cannot run at 62.5 MHz.

### 5.3 How long for BER < 10⁻¹² at 5 Gb/s (DERIVED)

- With zero errors: N = −ln(1−CL)/BER → **3.0·10¹² bits at 95 %** (4.6·10¹² at 99 %).
- Line bits at 5 Gb/s: 600 s = **10 min**.
- Our checker counts **40 checked bits per word** (README: "40 checked bits per word") at a 62.5 MHz word clock = 2.5·10⁹ checked bits/s → **1200 s = 20 min per direction** (with the gs checker at 62.5 MHz). 99 %: 31 min.
- Only start the soak after a 300 s run shows BER < 10⁻¹⁰, otherwise it wastes board time.

---

## 6. Public experience (searched 26.09.2026)

- **No published GateMate result above 2.5 Gb/s**, and no GateMate PCIe link-up (openCologne-PCIE PHY boxes unticked; see `SOURCES_20260926.md` §1.5). Web search found nothing newer.
- CologneChip's FDF 2025 slides (CERN indico, `gatemate-fdf2025.pdf`, slide 11) list "5 Gbit/s SerDes", eye scan, DFE and 4 loopback modes. No measured eye.
- pu-cc `ab7ce94` "prepare 5G tests" (2026-09-03) is the only vendor 5 G setting set. Its values are our PROFILE 1: DFE on, AFE PEAK 24 GAIN 0, CKP 0x3E, TX 5/5 of 12, AMP 31, TX calibration. No result was published; `tc_eyemeas` is still a stub.
- colognechip/gatemate-pipe (PCIe Gen1 2.5 G wrapper, `63ba8b1`): TX_AMP 30, BR_PRE/POST 15 but SEL 0 (no FFE), DFE off, AFE defaults, TRANS_TH 8 → a Gen1 setting with no equalisation.
- Useful comparison: the Raspberry Pi 5 runs PCIe Gen2 (5 GT/s) officially over the same FFC standard (≤ 50 mm, 90 Ω), and Gen3 "not officially supported" (RP-008298-DS §2.1). **The FFC part of our channel is rated for 5 Gb/s.**

---

## 7. Datasheet/tool inconsistencies found (so nobody trusts one source blindly)

| Item | Source A | Source B | Use |
|---|---|---|---|
| `RX_CDR_TRANS_TH` | DS: 7 b, def 8 | UG1001 03/2025: 9 b, def 128 | DS (nextpnr `30669ec` agrees) |
| `RX_CDR_LOCK_CFG` | DS: 8 b, 0xD5 | UG1001: 6 b, 0x0B | DS |
| `PLL_CP` default | DS Table 2.18: 12 | DS regfile p.96 / UG: 80 | 80 (BISC calibrates) |
| `PLL_BISC_MODE` default | Table 2.19: 0 | regfile / UG: 4 | write 5 explicitly |
| `PLL_CONFIG_SEL` default | Table 2.18: 1 | regfile / UG: 0 | write 1 explicitly |
| `RX_EYE_MEAS_CFG` width | DS: 12 b | UG: 15 b | pu-cc map (lsb 4) |
| `RX_EN_EQA_EXT_VALUE` bit positions | DS Table 2.59: 0x05[5], 0x05[11], 0x06[5], 0x06[11] as [0]..[3] with the names in Table 2.44 | serdestool 56aa48b: 0x05 bits unused; 0x06[5] = TH_MON1+TAPW, 0x06[11] = TH_MON2+AFE_OFFSET | vendor tool |
| `RX_AFE_PEAK` default | DS: 16 | serdestool: 15 | irrelevant, we set it |
| TX voltage formula (eq. 2.12) | absolute volts | physically impossible values | ratios only |
| VDD_SER max | p.155: 1.1 V | p.128/p.154: 1.15 V | aim for 1.05 V |
| RTERM common mode | Table 2.41 text: "·VDDIO" | Table 2.42: VDD_SER | VDD_SER |

---

## 8. Sources

- DS1001 GateMate Datasheet 09/2026:
  - p.50–98: SerDes; p.53–60 ADPLL/BISC; p.62 loopback; p.70–73 TX driver; p.74–82 RX/DFE/eye/CDR; p.84–88 comma/PRBS/elastic buffer; p.90–98 regfile.
  - p.128: power pins; p.155: SerDes electrical characteristics; p.176–177: pin list.
- UG1001 Primitives Library 03/2025, p.122–124 CC_SERDES parameters.
- pu-cc/gm_serdes_lb:
  - `56aa48b` `serdestool.py` L296–560 (register map), L1285 (`tc_eyemeas`), L1536–1552 (TX driver info), `eyetools.py`.
  - `serdes_lb.v` history: `dda07f7` (TX_DETECT_RX_I 1→0), `ab7ce94`, `22bbe50`.
- colognechip/gatemate-pipe `63ba8b1` `src/ccfpga_pipe_wrapper.v`.
- `ulx5m-gs-hw/hardware/{serdes,power,cm4-hsio}.kicad_sch` (+ README "DEFAULT VCC CORE is 0.9V") and `ulx5m-gs.kicad_pcb`.
- `FAST-TRACK-SIM/boards/ulx5m-m2/ulx5m-m2.kicad_pcb`, `impedance_cache.json`, `stackup.json`; `boards/ulx5m-gs/impedance_cache.json`.
- Waveshare CM5-IO-BASE-A schematic: https://files.waveshare.com/wiki/CM5-IO-BASE-A/CM5-IO-BASE-A_Sch.pdf (block P1).
- Raspberry Pi "Connector for PCIe" RP-008298-DS: https://datasheets.raspberrypi.com/pcie/pcie-connector-standard.pdf (Fig. 2, ch.3).
- CologneChip FDF 2025 slides: https://indico.cern.ch/event/1587509/contributions/6690211/attachments/3140818/5574499/gatemate-fdf2025.pdf
- This repo: `VERIFY_20260926_RATES.md` (up to `e3a6375`), `gateware/ber/ber_top.v`, `cc_serdes_params.vh`, `tools/eyescan.py`.
