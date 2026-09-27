# SI analysis of the SerDes path: ULX5M-GS v005 (vs v003) and ULX5M-M2 — how fast with a standard stackup (TASK-5086)

**Order:** Goran, Telegram 27.09.2026 21:47/22:00: *"na githubu je nova verzija gs, trebalo bi vidjeti koliko sa standardnim
stackupom možemo dobiti brzine. M2 je na [pravilnom stackupu]"*. Correction #107 (22:04): **the board on the table is v005 =
GitHub `main` 61b6709** (README "Please use v005", `project_version` v005), not v004/v003. This document analyses v005;
v003 (tag `v003`) is shown only for comparison. The file name keeps "v004" because that is what the order asked for.
**Done by:** Jelena. **No hardware was touched** — pure analysis of the PCB files, gerbers and the lab data already in this repo.

Tags as in the rest of this repo: **VERIFIED** = read from the PCB/gerber/datasheet (location given), **DERIVED** = computed
by the tools below from verified geometry, **UNVERIFIED** = typical/assumed value (no drawing or measurement we have).

---

## 0. Short answer

| Question | Answer | Tag |
|---|---|---|
| What stackup does a "standard" GS order actually get? | JLC builds a 6-layer 1.6 mm order without impedance control on its **default JLC06161H-3313** stack (outer prepreg 3313 = 0.0994 mm, Dk 4.1). The stack drawn in `ulx5m-gs.kicad_pcb` (5 × 0.274 mm, εr 4.5) is KiCad's generic placeholder, not an orderable JLC stack; the fab ignores it. | VERIFIED (`FAST-TRACK-SIM/docs/jlc-stackup-spec.md` [1]) / VERIFIED (`.kicad_pcb`) |
| GS v005 Zdiff on that standard stack | **97 Ω** on F.Cu (w 0.127 / gap 0.145), **103 Ω** on B.Cu (gap ~0.21). With the 1080 stack: 89 / 93 Ω. | DERIVED (field solver, §3) |
| GS v005 Zdiff if a fab really built the `.kicad_pcb` stack | 118 Ω F.Cu, 132 Ω B.Cu (v003: 136 Ω) | DERIVED |
| GS v005 loss | TX path 25.9 mm: **0.37 dB @ 2.5 GHz** trace loss; 0.9 dB with all pads/vias/die. The GS board alone keeps an eye of 0.97 of swing at 5 Gb/s and 0.70 at 12.5 Gb/s. | DERIVED |
| **Max SerDes rate with the standard stackup** | **5 Gb/s = the silicon limit** (DS1001 Table 4.3: D_SER 0.3–5 Gbit/s, DCO ≤ 2500 MHz). The linear channel limit of the whole GS → baseboard → FFC → adapter → M2 chain is **≈ 9 Gb/s nominal, ≈ 6.5 Gb/s worst case** (eye with 3-tap DFE ≥ 0.5 of swing). So the stackup is **not** what limits us. | VERIFIED (DS) / DERIVED (model) |
| With controlled impedance | The same: v005 geometry already lands at 97–103 Ω on the JLC stack. Ordering impedance control buys the ±10 % guarantee, not speed. | DERIVED |
| M2 (as built) | JLC 4-layer 0.8 mm, 1080 prepreg (0.0764 mm, εr 3.91) — the stack in the `.kicad_pcb` and in the panel job file agree. **Zdiff 88 Ω** (w 0.147 / gap 0.253), a PCIe-style 85–90 Ω target. RX 64 mm + 2 vias: **1.0 dB @ 2.5 GHz**; M2 alone: eye 0.89 at 5 Gb/s. | VERIFIED (stack) / DERIVED |
| Whole chain @ 2.5 GHz (5 Gb/s Nyquist) | **3.0 dB nominal, 4.8 dB worst** (longer FFC, second adapter). Earlier estimate (TUNING_5G.md §2.2): 5–7 dB. | DERIVED + UNVERIFIED middle |
| Does SI explain the 5 Gb/s failure (BER 1e-2…1e-1, CDR not holding lock)? | **No, not by loss or trace impedance.** The linear model leaves an eye of 0.59–0.70 at 5 Gb/s. The SI suspects that remain are the **reference clock to M2** (§6), the **unverified adapter chain** and **FFC crosstalk** (not modelled). | DERIVED |

**Top 5 changes for the next revision** (details §8): (1) reference clock — fan-out buffer on GS or a local oscillator on M2,
SER_CK on an outer layer over GND, only one AC-coupling pair; (2) put the real JLC stack in the `.kicad_pcb` and order
impedance control, w/s from §8.1; (3) void the plane under AC-cap pads and take the DNP R110/R107 pads off the line;
(4) via antipads ≥ 0.8 mm plus GND stitching vias ≤ 0.5 mm from every data via pair; (5) M2: keep the short
v2 routing (15 mm, no vias, as in GitHub f29c5aa), and give SER_CK a continuous GND reference.

---

## 1. Which files describe the boards we measured

### 1.1 GS

| Item | Value | Tag |
|---|---|---|
| Repo | `github.com/intergalaktik/ulx5m-gs`, local `~/app/ulx5m-gs-hw`, `git pull` = already up to date at `61b6709` (20.08.2026, "Adding fiducials") | VERIFIED |
| Board on the table | **v005** (Goran #107). Production gerbers `hardware/production/ULX5M-GS-v05.zip` (KiCad 9, `TF.CreationDate` 2026-07-12) | VERIFIED |
| Gerber ↔ PCB check | Every straight SerDes segment in the v05 gerbers has the same length as in `ulx5m-gs.kicad_pcb` (e.g. PCIe_TX_P F.Cu 9.71 mm, TX_N 9.44, B.Cu 0.79/0.95, RX_P/N B.Cu 6.90/7.23). `gbr_netlen.py` does not add up gerber arcs (G02/G03); RX F.Cu therefore reads 16.05 mm from the gerber vs 20.22 mm with the PCB arcs included | VERIFIED |
| Comparison board | tag `v003` (`hardware/ulx5m-gs.kicad_pcb` at `v003`, extracted to `data_20260927/t5086/gs_v003.json`) | VERIFIED |
| Layers | F.Cu sig / In1 GND1 / In2 sig / In3 POWER / In4 GND2 / B.Cu sig. GND zones: In1/In3/In4 clearance **0.1 mm**, B.Cu/In2 0.15 mm | VERIFIED |

### 1.2 M2 — which file is the manufactured board (instruction #107)

| Source | SerDes routing | Matches the manufactured gerbers? |
|---|---|---|
| Panel gerbers `ulx5m-m2/panel/production/user/ulx5m-m2.zip` (`ulx5m-m2_panel_edit`, `TF.CreationDate` 2026-06-02, job file: 4 layers, 0.8337 mm, `ImpedanceControlled: true`) | RX_P/N F.Cu **10.63 / 9.89 mm**, TX_P/N **10.18 / 10.19**, SER_CK_P/N **4.99 / 7.17**, PET0P/N 3.34/3.33, PCIe_CLK 3.50 | reference |
| `~/app/FAST-TRACK-SIM/boards/ulx5m-m2/ulx5m-m2.kicad_pcb` (copy of 02.06.2026) | **identical** F.Cu lengths for every net above; B.Cu straight segments equal (TX_N 49.82 = 49.82 mm), the rest differs only by arcs; RX 63–65 mm, **2 vias** per net, AC caps C143/C144 **0201** | **YES** |
| GitHub `intergalaktik/ulx5m-m2` `main` f29c5aa (v001 per Goran) | RX_P/N **15.19 / 14.79 mm on F.Cu only, no vias**; AC caps 0402; C129/C130 missing; X2 on B.Cu directly on SER_CK; C127/C128/R105/R106/C42 outside the board outline (Goran) | **NO** — this is the v2 work in progress ("Cleanup for v2", `5f3e2c5` 03.06.2026) |

**Conclusion:** the manufactured M2 = the FAST-TRACK-SIM copy = the panel gerbers of 02.06.2026. All M2 numbers below
use that file. GitHub f29c5aa is used only in §8.2 as "what the next revision already changes". (VERIFIED, `m2_gerber_len.txt`.)
Side note: `ulx5m-m2/production/ULX5M-GS-v04.zip` in the M2 repo contains **GS** 6-layer gerbers, not M2 (known, see
`regoc_system/docs/ulx5m-m2/STANJE_ULX5M-M2_2026-09-01.md`).

---

## 2. Extracted SerDes path (step 1)

Tool: `tools/si/si_extract.py` (stdlib; KiCad 7–10 s-expressions, arcs by their mid point, P/N edge gap sampled every
0.1 mm, reference plane found by point-in-polygon on the zone fills of the adjacent layer). `kicad-cli` is not needed.
Raw output: `data_20260927/t5086/gs_v005.json`, `gs_v003.json`, `m2_built.json`, `m2_github_f29c5aa.json`.

### 2.1 GS v005 (on the table)

| Segment | Layer: length (mm) | w (mm) | P/N edge gap (mm), median (min) | Vias | Skew | Parts on the line |
|---|---|---|---|---|---|---|
| TX_BC U4.U13/V13 → C134/C135 | F.Cu 15.44 / 15.24 | 0.127 | 0.143 (0.064 at the BGA) | 0 | 0.20 mm | R110 (DNP, 0402 pads **on the line**), C134/C135 0402 100 nF |
| TX C134/C135 → J1.22/24 | F.Cu 9.71/9.44, B.Cu 0.79/0.95 | 0.127 | F 0.163, B 0.248 | 1 per net (0.35/0.2, F→B) | 0.12 mm | J1 DF40 pads 0.23 × 0.66 on B.Cu |
| RX J1.16/18 → U4.U11/V11 | B.Cu 6.90/7.23, F.Cu 20.22/20.12 | 0.127 | F 0.146 (0.053), B 0.234 | 1 per net | 0.23 mm | R107 (DNP 0402 pads on the line) |
| SER_CLK X2 → C129/C130 + C136/C137 | F.Cu 7.70 / 9.44 | 0.2032 | 0.247 | 0 | 1.74 mm | Si511 X2 (LVDS) drives both branches |
| SER_CK C129/C130 → U4.T12/T13 | F 1.5, B 4.2/3.9, **In2 5.8** | 0.127/0.2 | In2 0.24, B 0.18 | **3 per net** | 0.46 mm | R108 DNP |
| PCIe_CLK C136/C137 → J1.10/12 | F 2.7/0.8, B 0.6 | 0.2 | 0.2 | 1 per net | 1.88 mm | — |

Reference plane (sampled along every trace):
- F.Cu over In1 GND and B.Cu over In4 GND are **continuous**. The only 0.2–0.34 mm without a plane per net is the antipad
  next to each via.
- AC-cap pads C134/C135 (and C129/C130/C136/C137) have **solid GND1 under them** (no cut-out). J1 pads have solid GND2 under them.
- No coplanar GND pour on F.Cu next to the pairs. B.Cu has GND within 0.25 mm on 3 mm of the RX path.
- **SER_CK on In2** is over In1 GND on one side, and over In3 **POWER: VDD_CORE 1.9 mm, +3V3 2.2 mm, no copper 1.6 mm**
  on the other. On the JLC stack the *closer* plane of In2 is In3 (0.109 mm vs 0.55 mm), so the refclk is referenced to a
  split power plane (§6).
- Signal vias: 0.35 mm pad / 0.2 mm drill, F↔B through, **inner pads kept** (only 8 vias on the board use
  `remove_unused_layers`), plane clearance 0.1 mm → **antipad Ø 0.55 mm**. The nearest GND via to a data via is
  **1.17–1.57 mm** away (`coplanar.py`).
- Via stubs: none on the data pairs (every data via is used F→B). SER_CK changes F→In2→B through vias: stub ≈ 0.9 mm on the
  JLC stack. That does not matter at 100 MHz.

### 2.2 v005 vs v003 (a8b9be8 "Improve SerDes routing …")

| | v003 | v005 | Effect |
|---|---|---|---|
| F.Cu P/N gap (TX, RX) | 0.24 mm | **0.145–0.163 mm** | tighter coupling: 104.7 → 97.0 Ω (JLC 3313) |
| RX length / skew | 23.5/22.4 mm, **1.11 mm** | 27.1/27.4 mm, **0.23 mm** | skew fixed with meanders (+3.7 mm) |
| TX_BC skew | 0.59 mm | 0.20 mm | fixed |
| TX C→J1 | 7.9 mm | 10.5 mm | longer |
| Refclk, vias, AC caps, layers | same | same | not touched |

Both versions are electrically almost the same channel: on the JLC stack 97–105 Ω, and a 0.2 dB difference in loss.
Skew is below 0.25 mm on every data pair in v005 (< 1.6 ps, < 0.01 UI at 5 Gb/s).

### 2.3 M2 as built (FAST-TRACK-SIM copy = gerbers)

| Segment | Layer: length (mm) | w / gap (mm) | Vias | Notes |
|---|---|---|---|---|
| RX J10.49/47 → U4.U11/V11 | F 10.6/9.9, **B 54.4/53.6** | 0.147 / 0.253 | **2 per net** (0.4/0.2) | skew 1.5 mm; first 1.2–1.3 mm under the edge fingers has no In1 plane (normal for M.2) |
| TX U4.U13/V13 → C144/C143 | F 10.2, **B 50.8/49.8** | 0.147 (0.13 neck) / 0.253 | 2 per net | skew 0.95 mm |
| PET0 C143/C144 → J10.41/43 | F 3.3 | 0.147 / 0.253 | 0 | C143/C144 **0201**, solid GND1 under the pads |
| PCIe_CLK J10.53/55 → C136/C137 | F 3.5 | 0.147 / 0.26 | 0 | |
| SER_CLK C136/C137 → C129/C130 (+X2 footprint) | F 2.7, **B 49.4** | 0.147 / 0.25 | 2 per net | **two series caps** (C136 + C129) on the M2 refclk; the X2 pads sit on the same net (X2 not fitted per STANJE B9) |
| SER_CK C129/C130 → U4.T12/T13 | F 5.0/7.2, B 7.5/8.0 | 0.127 / 0.25 | 2 per net | **4.5 mm (P) / 3.3 mm (N) of B.Cu over no In2 copper** (BGA via field); skew 2.6 mm |

Plane clearance 0.15–0.2 mm → via antipad Ø 0.7–0.8 mm; nearest GND via 0.75–1.15 mm. B.Cu has a GND pour within 0.25 mm
on about half the length (slightly lower Z, included in the ±5 % below).

---

## 3. Differential impedance (step 2)

Tool: `tools/si/fd2d.py` — 2-D quasi-TEM finite-difference solver (uniform 2.5–5 µm grid, conformal soldermask 15 µm
εr 3.8, real copper thickness, asymmetric stripline). Validated against Hammerstad–Jensen microstrip (50.4 Ω vs 49.6 Ω)
and Cohn stripline (64.4 Ω vs 62.5 Ω, thin strip) — `tools/tests/test_si.py`. Loss: conductor loss from the vacuum
surface-charge distribution (J = ρ·I/Q, Wheeler-equivalent) with Hammerstad roughness (Rq 1 µm), dielectric loss from
the electric-energy fraction in each material. Runs: `tools/si/run_matrix.py`, `run_pads.py`, `run_rec.py`; log
`data_20260927/t5086/matrix.log`.

Stacks used: **(a)** the `.kicad_pcb` stack (F–In1 0.274 mm, εr 4.5, tanδ 0.02); **(b)** JLC06161H-3313 (outer 3313
0.0994 mm Dk 4.1; In2: 0.55 mm core to In1, 0.1088 mm 2116 to In3); **(c)** JLC06161H-1080 (outer 1080 0.0764 mm Dk 3.91;
In2: 0.2104 mm 7628 to In3); **M2** JLC 4-layer 0.8 mm 1080 (0.0764 mm Dk 3.91, from its `.kicad_pcb` and panel job file).
Df 0.02 everywhere (conservative, same as the KiCad files).

| Geometry | (a) `.kicad_pcb` stack | (b) JLC 3313 (default) | (c) JLC 1080 | Target |
|---|---|---|---|---|
| GS v005 F.Cu, w 0.127 / gap 0.145 | 118.5 Ω | **97.0 Ω** | 89.1 Ω | 100 (link), 85–90 (CM5 PCIe) |
| GS v005 B.Cu, w 0.127 / gap 0.21 | 131.8 Ω | **103.0 Ω** | 93.3 Ω | |
| GS v003 F.Cu, w 0.127 / gap 0.24 | 136.5 Ω | 104.7 Ω | 94.5 Ω | |
| GS BGA neck, w 0.127 / gap 0.06 (~1 mm) | — | 77.1 Ω | — | short, acceptable |
| GS refclk SER_CLK, w 0.2032 / gap 0.17 | 107.9 Ω | **79.6 Ω** | — | 100 (LVDS) |
| GS SER_CK on In2, w 0.127 / gap 0.23 | 114.5 Ω | 97.2 Ω (ref. In3 POWER) | 112.7 Ω | 100 |
| GS 0402 AC-cap pad pair (0.56 wide, gap 0.40), solid GND1 below | 82.1 Ω | **44.5 Ω** | — | |
| **M2** RX/TX, w 0.147 / gap 0.253 | — | — | **88.3 Ω** (M2 stack) | 85–90 |
| M2 BGA neck, w 0.13 / gap 0.27 | — | — | 93.1 Ω | |
| M2 0201 AC-cap pad pair (0.46 wide, gap 0.30), solid GND1 below | — | — | **43.1 Ω** | |
| FFC (RPi spec) | 90 Ω ±10 % | | | VERIFIED spec (TUNING_5G.md §2.1) |

Differential trace loss per cm (DERIVED, same solver):

| Line | 1.25 GHz | 2.5 GHz | 3.125 GHz |
|---|---|---|---|
| GS F.Cu, `.kicad_pcb` stack | 0.069 dB | 0.122 dB | 0.147 dB |
| GS F.Cu, JLC 3313 | 0.081 dB | 0.141 dB | 0.170 dB |
| GS F.Cu, JLC 1080 | 0.088 dB | 0.154 dB | 0.185 dB |
| M2, 1080 0.8 mm | 0.088 dB | 0.154 dB | 0.186 dB |

Path trace loss (dB @ 1.25 / 2.5 / 3.125 GHz): **GS TX 25.9 mm** 0.21/0.37/0.44 (JLC 3313), 0.18/0.32/0.38 (`.kicad_pcb`
stack); **GS RX 27.2 mm** 0.22/0.39/0.46; **M2 RX 64.2 mm** 0.56/0.99/1.19; **M2 TX 60.5 mm** 0.53/0.93/1.12.
The earlier hand estimate (TUNING_5G.md §2.2: GS 0.55 dB, M2 1.2 dB @ 2.5 GHz) is in the same range.

Why the GS lands near 100 Ω "by accident": 0.127 mm over ~0.1 mm dielectric is the usual 50 Ω single-ended geometry, and the
tighter v005 gap brings the pair to 97 Ω. In the KiCad calculator (with the 0.274 mm placeholder) the same traces show
118–132 Ω. That mismatch between the drawn stack and the built one is the first thing to fix (§8.1). It is harmless today.

---

## 4. Discontinuities / reflections (step 2, continued)

Reflection coefficient against the 100 Ω link reference, and the size of the bump a 60 ps (0.3 UI at 5 Gb/s) edge sees
(≈ ρ · 2τ / t_r for elements shorter than the edge). DERIVED unless marked.

| Element | Z_diff | Length | ρ | Seen by a 60 ps edge | Where |
|---|---|---|---|---|---|
| GS trace F.Cu / B.Cu (JLC 3313) | 97 / 103 Ω | 10–20 mm | −0.015 / +0.015 | full | GS |
| … if built to the `.kicad_pcb` stack | 118 / 132 Ω | | +0.08 / +0.14 | full | GS |
| BGA neck (gap 0.053–0.064) | 77 Ω | ~1 mm | −0.13 | ~0.02 | GS |
| 0402 AC-cap pads + DNP R110 pads on the line | 44.5 Ω | 2 × 0.5 mm + 0.6 mm | **−0.38** | ~0.05 each, two lumps 1 mm apart | GS TX |
| Data via 0.35/0.2, antipad Ø 0.55, 1.6 mm, no stitching via ≤ 1.2 mm | ~59 Ω (coax estimate 60/√εr·ln(D/d)) | 1.6 mm (11 ps) | **−0.26** | ~0.09 | GS TX, RX |
| DF40 mated pair (CM5 HSIO) | ~85 Ω | ~2 mm | −0.08 | small | UNVERIFIED typical |
| Waveshare trace CM5 → P1 | ~95 Ω | 40–60 mm | −0.03 | full | UNVERIFIED length and Z |
| FFC ZIF connector ×2 | ~75 Ω | ~2 mm each | −0.14 | ~0.02 | UNVERIFIED typical |
| FFC | 90 Ω | ≤ 50 mm (spec), maybe 100 mm | −0.05 | full | spec VERIFIED, our cable UNVERIFIED |
| Adapter(s) FFC → M.2 | ~95 Ω + 1 via | 30–90 mm | ? | ? | **UNVERIFIED — the adapter is not identified** (TUNING_5G.md §2.1) |
| M.2 socket + edge fingers over plane void | ~80–85 Ω | ~3 + 1.3 mm | −0.08…−0.11 | small | UNVERIFIED typical |
| M2 trace | 88 Ω | 60–65 mm | −0.06 | full | M2 |
| M2 0201 AC-cap pads | 43 Ω | 2 × 0.4 mm | −0.34 | ~0.03 | M2 TX |
| M2 via 0.4/0.2, antipad Ø 0.7–0.8, 0.8 mm | ~73 Ω (estimate) | 0.8 mm | −0.09 (vs 88) | small | M2 |
| Die (pad + ESD) | 100 Ω ‖ ~0.25 pF diff | — | — | — | UNVERIFIED (0.5 pF per pin assumed; DS1001 gives only RTERM 100 Ω) |

The largest *known* discontinuities are on the GS: the 0402 pads on a solid plane and the small-antipad vias without nearby
stitching. Neither is large enough to close a 5 Gb/s eye (§5). The largest *unknown* is the adapter chain.

---

## 5. Channel budget and max rate (step 3)

Tool: `tools/si/cascade.py` — odd-mode ABCD cascade of every segment from §2–§4 (line Z, εeff and loss from the solver,
connectors and middle-chain values UNVERIFIED typical), die capacitance at both ends, 100 Ω reference. Output:
S21/S11 and a **peak-distortion eye estimate**: 1-UI pulse (0.3 UI edges), eye height = main cursor − Σ|ISI|, raw and with
the first 3 post-cursors cancelled (the GateMate "3-tap DFE", DS1001 §2.5.1). Linear only: **no random noise, no jitter, no
crosstalk, no CTLE** (the GateMate RX EQ transfer function is not documented). Results `cascade_results.json`,
`rate_sweep.json`.

### 5.1 Insertion loss, return loss

| Chain | IL 1.25 GHz | IL 2.5 GHz | IL 3.125 GHz | worst RL 0.1–2.5 GHz |
|---|---|---|---|---|
| GS v005 alone (JLC 3313), TX incl. pads/vias/die | 0.29 dB | 0.92 dB | 1.38 dB | 9.6 dB |
| GS v005 alone if built to the `.kicad_pcb` stack | 0.24 dB | 1.47 dB | 1.69 dB | 6.5 dB |
| M2 alone (as built), RX | 0.78 dB | 1.69 dB | 1.51 dB | 9.0 dB |
| **GS→M2, nominal** (baseboard 40 mm, FFC 50 mm, adapter 30 mm) | 1.82 dB | **3.04 dB** | 4.03 dB | 9.5 dB |
| M2→GS, nominal | 1.83 dB | 3.09 dB | 4.08 dB | 8.1 dB |
| **GS→M2, worst** (baseboard 60 mm, FFC 100 mm, FFC→slot→M.2 = 2 adapters) | 2.52 dB | **4.76 dB** | 5.65 dB | 10.2 dB |
| GS→M2 nominal, GS built to the `.kicad_pcb` stack | 1.56 dB | 3.04 dB | 4.24 dB | 6.4 dB |

(The ripple, e.g. M2-alone IL at 3.125 GHz below 2.5 GHz, is standing waves between the pads/vias.)

### 5.2 Eye height vs rate (fraction of the DC swing, 3-tap DFE)

| Chain | 2.5 G | 3.125 G | 4 G | **5 G** | 6.25 G | 8 G | 10 G | 12.5 G |
|---|---|---|---|---|---|---|---|---|
| GS alone (JLC 3313) | 0.97 | 0.98 | 0.98 | **0.97** | 0.94 | 0.90 | 0.81 | 0.70 |
| M2 alone (as built) | 0.93 | 0.92 | 0.90 | **0.89** | 0.84 | 0.78 | 0.72 | 0.59 |
| Chain nominal, as built | 0.80 | 0.79 | 0.75 | **0.70** | 0.65 | 0.57 | 0.45 | 0.30 |
| Chain worst, as built | 0.71 | 0.68 | 0.62 | **0.59** | 0.52 | 0.40 | 0.33 | 0.18 |
| Chain nominal, GS on the `.kicad_pcb` stack | 0.81 | 0.78 | 0.75 | **0.68** | 0.63 | 0.55 | 0.44 | 0.34 |

Other points from `cascade_results.json`:
- Without DFE the 5 G eye is 0.62 (nominal) / 0.45 (worst).
- A −3.5 dB TX post-cursor (PCIe Gen2 de-emphasis) **lowers** the eye (0.59 vs 0.70 nominal). The channel has too little
  loss to need it. This agrees with the measurement that TX FFE hurt (VERIFY_20260926_RATES.md §9.5, E3).
- Direction makes no difference: GS→M2 and M2→GS are within 0.02.
- The "fixed" boards of §8 (100 Ω everywhere, voided pads, better vias) give 0.71 nominal. That is no better, because the
  unverified middle of the chain dominates.

**Reading.** With a criterion of "eye ≥ 0.5 of swing after DFE" (generous margin for noise and jitter, which the model does not include):

| Case | SI-limited rate | Practical max |
|---|---|---|
| GS on the standard (JLC default) stack | > 12.5 Gb/s for the board itself | **5 Gb/s (silicon)** |
| GS with controlled impedance (same stack, ±10 % guaranteed) | same | **5 Gb/s (silicon)** |
| GS if it were really built to the `.kicad_pcb` 0.274 mm stack | ≈ 8.5 Gb/s chain nominal | 5 Gb/s |
| M2 as built | > 12.5 Gb/s board, ≈ 9 Gb/s chain nominal, ≈ 6.5 Gb/s chain worst | **5 Gb/s (silicon)** |

### 5.3 Comparison with what we measured

| Rate | Model (chain) | Measured (VERIFY_20260926_RATES.md §9–10) | Consistent? |
|---|---|---|---|
| 2.5 Gb/s | eye 0.71–0.80, IL 1.8–2.5 dB @ 1.25 GHz → SI-wise error-free | BER 1.6e-11 … 1e-8, spread ×10–1000 between loads of the **same** bitstream; driven by fabric/SerDes-port timing (`TX_NEG`, seeds), 1 µF on GS helped (§10.4) | yes — the residual errors are not SI (§9.3, §9.8 item 3) |
| 5 Gb/s | eye 0.59–0.70, IL 3.0–4.8 dB @ 2.5 GHz | BER 1e-2 … 1e-1, CDR does not hold lock, 2.5–6.5 % bad raw PCS words **without** the fabric, eye counters dead | **no** — a channel with 3–5 dB loss and this eye does not give 10 % BER. The cause is outside trace impedance and loss |

What the linear model cannot see, and so stays on the list for 5 G:
1. **Reference-clock quality at M2** (§6). The DS allows 1 ps. The M2 receiver multiplies the refclk ×25 and has no frequency
   integrator (CKI = 0). Wander and jitter at M2 go straight into its CDR and TX.
2. **The adapter chain.** One badly built FFC→M.2 or FFC→slot adapter (no GND between pairs, a stub, a slot plus riser) can
   put a −10 dB reflection or a resonance at 2–3 GHz that the model does not include. Identifying the adapter (photo or part
   number) is the cheapest next step. A TDR of the chain would settle it.
3. **FFC crosstalk** (TX 10/11 and RX 7/8 separated by one GND; CLK 4/5 next to GND 6 / RX 7).
4. Non-SI, already documented: gs checker rclk Fmax 44 MHz < 62.5 MHz (m2→gs at 5 G is only indicative), supply noise.

---

## 6. Reference clock path (important for 5 Gb/s)

| Item | GS | M2 | Tag |
|---|---|---|---|
| Source | X2 Si511 100 MHz LVDS on GS drives **two AC-coupled branches** in parallel | none fitted; refclk comes over the cable | VERIFIED (PCB/netlist) |
| Branch length | SER_CLK 8–9 mm + SER_CK 11 mm (3 vias, In2) | GS 3 mm + baseboard + FFC + adapter + J10 3.5 mm + **SER_CLK 52 mm B.Cu** + SER_CK 13–15 mm; ≈ 180–250 mm total | VERIFIED board parts / UNVERIFIED middle |
| Series caps | C129/C130 | **C136/C137 on GS + C136/C137 on M2 + C129/C130 on M2 = 3 caps in series** (≈ 33 nF, no DC path; fine at 100 MHz, but 3 pad discontinuities) | VERIFIED |
| Termination | internal (`PLL_REF_RTERM=1`) | internal | VERIFIED (gateware) |
| Swing at the input | one LVDS driver into two 100 Ω terminations → ≈ ½ the nominal V_OD on each (DERIVED, TUNING_5G.md §2.4) | same, plus the long path | DERIVED |
| Reference plane | SER_CK on In2: nearest plane on the JLC stack = **In3 POWER** (VDD_CORE / +3V3 split, 1.6 mm with no copper) | SER_CK 3–4.5 mm of B.Cu **over no In2 copper** (BGA via field) | DERIVED from zone fills |
| Z | SER_CLK w 0.2032 on JLC 3313: **80 Ω** | 88 Ω | DERIVED |
| X2 footprint | fitted | footprint **on the same net** as the incoming clock (as built: not fitted). GitHub f29c5aa: X2 on SER_CK **and** C136/C137 to J10 → with both X2 and the host clock present, two drivers fight | VERIFIED (PCB) |

Halving the swing halves the slew rate. With the same noise, the noise-to-jitter conversion doubles, and there is 1 ps
to spend. E6 (`PLL_REF_RTERM=0` on GS) did not change BER (§9.5). That rules out neither jitter picked up on the long
path nor noise from the split POWER reference. A scope/phase-noise look at M2 C129/C130 (H4) is the direct test.

---

## 7. M2 path review (step 4)

- **Stack and impedance: correct.** 88 Ω on a 0.8 mm JLC 1080 4-layer is the right target for an M.2 (PCIe) card. The drawn
  stack and the panel job file agree (VERIFIED).
- **Length:** 60–65 mm + 2 vias per net is the longest part of the board chain (1.0 dB @ 2.5 GHz, eye 0.89 at 5 G on its own).
  Not a problem at 5 Gb/s. GitHub f29c5aa (v2) already cuts it to 15 mm with no vias.
- **AC caps 0201 on solid GND1:** 43 Ω pads, ρ −0.34 but only 0.4 mm long. Small effect. Voiding In1 under the pads
  (reference In2 at 0.64 mm) gives 114 Ω; a partial void (pad width only) brings it near 100 Ω.
- **Refclk:** the weakest part of the M2 routing. 52 mm on B.Cu, two extra series caps, 3–4.5 mm of SER_CK without a plane,
  2.6 mm skew on SER_CK. On top of that, the X2 footprint sits on the same net.
- **Vias:** antipad 0.7–0.8 mm is good for a 0.8 mm board. The GND stitching vias are 0.75–1.15 mm away; ≤ 0.5 mm would be better.
- **Skew:** RX 1.5 mm (≈ 9 ps ≈ 0.05 UI at 5 G), TX 0.95 mm. Acceptable, but v2 should match within 0.25 mm like GS v005.

---

## 8. Changes for the next revision (step 4) and which stackup to order

### 8.1 GS

| # | Change | Why / number |
|---|---|---|
| G1 | **Put the real stack in `ulx5m-gs.kicad_pcb`** (JLC06161H-3313: 0.0994 / 0.55 / 0.1088 / 0.55 / 0.0994 mm, Dk 4.1/4.3/4.16) **and order "impedance control" (free at JLC for 6 layers)**. Widths/gaps (JLC 3313, outer, with mask): **100 Ω → w 0.127 / gap 0.18 mm (100.7 Ω)**; 90 Ω → w 0.127 / gap 0.10 (89.3 Ω); w 0.10 / gap 0.15 → 105 Ω | today the KiCad calculator shows 118–132 Ω for traces that are really 97–103 Ω |
| G2 | **Void GND1 under the AC-cap pads C134/C135** (pad-sized cut-out) and put a GND patch on In2 below them; or use 0201 caps | pad pair 44.5 Ω → ~100–113 Ω (ρ −0.38 → ≤ ±0.06) |
| G3 | **Take R110 / R107 (DNP 0402 across the TX/RX pairs) off the line**: delete them, or put them on 0201 stubs off the pair | two extra 44 Ω lumps within 1 mm of the caps |
| G4 | **Data vias:** antipad ≥ 0.8 mm (plane clearance ≥ 0.2 mm, or one oval antipad around the pair), remove unused inner pads, **2 GND stitching vias ≤ 0.5 mm** from each pair via | via ≈ 59 Ω → ≈ 80–95 Ω; return path when the reference changes In1 → In4 (today 1.2–1.6 mm away) |
| G5 | **Refclk:** route SER_CLK/SER_CK only on F.Cu over In1 GND (no In2 over the POWER split), w 0.127 / gap 0.15 (≈ 97 Ω; today w 0.2032 = 80 Ω on the JLC stack). Add a **1:2 fan-out buffer** (LVDS/HCSL, e.g. Si53302 or LMK00304 class — part UNVERIFIED) so that GS SER_CLK and J1 PCIe_CLK each get their own driver and termination; or send standard HCSL on J1 and leave M2's refclk to M2 (G5/M3) | full swing and one termination per branch; no split-plane return |
| G6 | Keep: data pairs on F/B only (no stubs → **no back-drill needed**; JLC does not back-drill standard orders), skew < 0.25 mm (done in v005), BGA neck ≤ 1 mm | |

**Stack to order for GS: JLC06161H-3313, 1.6 mm, 6 layers, impedance control on**, with G1 widths. JLC06161H-1080 also
works (w 0.10 / gap 0.15 → 97.7 Ω). Do not order it with the current 0.127/0.145 geometry: that gives 89 Ω.

### 8.2 M2

| # | Change | Why / number |
|---|---|---|
| M1 | **Keep the v2 (f29c5aa) routing:** RX/TX ≈ 15 mm on F.Cu, no vias; match skew < 0.25 mm | as-built 60–65 mm + 2 vias = 1.0 dB and 4 vias per pair |
| M2 | Keep the stack (JLC 4-layer 0.8 mm 1080, impedance control on). 85 Ω (PCIe) → w 0.147 / gap 0.20 (86.5 Ω); 100 Ω → w 0.11 / gap 0.20 (97.7 Ω). Pick **one** reference impedance for the whole GS↔M2 link: 90 Ω matches the FFC and the Pi/PCIe world best | chain mixes 97–103 Ω (GS), 90 Ω (FFC), 88 Ω (M2) |
| M3 | **Refclk:** decide the topology. **(a)** host clock: no X2 footprint on the net, **one** AC-coupling pair only (C129/C130 → 0 Ω or removed; GS already has C136/C137), SER_CLK short, on F.Cu over GND. **(b)** local X2 on M2: remove the J10 refclk connection (C136/C137 DNP), set CDR `RX_CDR_CKI ≠ 0` for the ppm offset. f29c5aa has X2 on SER_CK **and** C136/C137 to J10 → both drivers on one net unless one side is DNP | today 3 series caps, 52 mm on B.Cu, X2 pads on the net |
| M4 | SER_CK: continuous GND under it (today 3–4.5 mm over the BGA via field with no In2), skew < 0.25 mm (today 2.6 mm) | |
| M5 | Void In1 under the AC-cap pads (pad-sized) and GND stitching vias ≤ 0.5 mm from every via pair | 43 Ω pads; stitching 0.75–1.15 mm today |

### 8.3 Outside the boards (cheapest first)

1. **Identify the FFC → M.2 adapter(s) and the FFC length** (photo). This is the only UNVERIFIED part of the chain that could
   plausibly hide a 5 G-killing reflection.
2. Scope/phase noise of the refclk at M2 C129/C130 (H4 in TUNING_5G.md).
3. If a VNA/TDR is ever available: one S21/TDR of the chain from J1 to J10 replaces every UNVERIFIED row in §4.

---

## 9. Tools and data added

| File | What |
|---|---|
| `tools/si/si_extract.py` | per-pair extraction: layer lengths (arcs included), widths, P/N edge gap, vias, pads, reference-plane coverage from the zone fills. `python3 tools/si/si_extract.py <board.kicad_pcb> "$(cat tools/si/pairs_gs.json)" [layer→ref-plane JSON]` |
| `tools/si/summ.py` | readable summary of the JSON above |
| `tools/si/coplanar.py`, `pads_planes.py` | same-layer GND pour next to the pairs, nearest GND via, plane under given pads |
| `tools/si/gbr_netlen.py` | per-net track length from gerbers with `TO.N` attributes (straight segments only) — used for the "which M2 file" check |
| `tools/si/fd2d.py` | 2-D FD field solver (numpy + scipy) |
| `tools/si/run_matrix.py`, `run_pads.py`, `run_rec.py` | the runs behind §3 and §8 |
| `tools/si/cascade.py`, `sweep.py` | channel cascade, IL/RL, peak-distortion eye, rate sweep (§5) |
| `tools/tests/test_si.py` | extractor on a synthetic board (arc length, gap, plane coverage); solver vs Hammerstad/Cohn; cascade matched line / quarter-wave. The solver tests skip without numpy |
| `docs/data_20260927/t5086/` | `gs_v005.json`, `gs_v003.json`, `m2_built.json`, `m2_github_f29c5aa.json`, `m2_gerber_len.txt`, `matrix.log`, `cascade_results.json`, `rate_sweep.json` |

numpy/scipy are not in the system Python. Use a venv (`python3 -m venv v && TMPDIR=$HOME/.tmp v/bin/pip install numpy scipy`;
`/tmp` in the container is a 100 MB tmpfs and pip fails there).

## 10. Limits of this analysis (so nobody over-reads it)

- The model is linear: no random noise, no jitter, no crosstalk, no CTLE. The eye numbers are **upper bounds**.
- Connector, baseboard, FFC and adapter values are **typical, UNVERIFIED**. The Waveshare CM5-IO-BASE-A trace length/stack
  and the adapter are unknown. Worst case covers a 100 mm FFC and a two-adapter path, not a defective adapter.
- Die capacitance (0.5 pF per pin) and the via impedances (coaxial estimate) are estimates. Etch trapezoid and glass weave
  are ignored (±2–3 Ω, and skew from glass weave is below the 0.25 mm routing skew at these lengths).
- "JLC default = 3313" comes from the FAST-TRACK-SIM research note [1]. If the GS order specified another JLC stack
  (1080), the GS is 89–93 Ω instead of 97–103 Ω — still inside ±10 % of 90–100 Ω, and the eye changes by < 0.02.

## Sources

[1] `~/app/FAST-TRACK-SIM/docs/jlc-stackup-spec.md` (Manda 05.05.2026, jlcpcb.com/impedance: JLC06161H-3313 = default
"no requirement" 6-layer 1.6 mm; 3313 Dk 4.1, 2116 4.16, 7628 4.4). DS1001 GateMate datasheet 2026-09 (§2.5.1 SerDes features,
Table 4.3 p.155). `ulx5m-gs` 61b6709 / v003, `ulx5m-m2` f29c5aa, FAST-TRACK-SIM `boards/ulx5m-m2/ulx5m-m2.kicad_pcb`,
M2 panel gerbers 2026-06-02. TUNING_5G.md §2, VERIFY_20260926_RATES.md §9–10 (this repo).
