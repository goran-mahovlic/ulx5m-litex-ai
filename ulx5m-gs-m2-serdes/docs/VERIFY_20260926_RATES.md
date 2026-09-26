# GS↔M2 SerDes above 1.25 Gb/s — 2.5 and 5 Gb/s (TASK-5063, 26.09.2026)

**Requested by:** Goran (Telegram 26.09.2026 19:31). **Done by:** Jelena (REGOČ). **Starting point:** `VERIFY_20260926.md` §6
(1.25 Gb/s clean, 2.5 Gb/s BER ~10⁻⁴). Lab rules: `regoc_system/docs/FPGA_LAB_ARHITEKTURA.md` (fpga-jtag, CFGRST on every
bit, gs lease `/home/pi/gs.owner` as `TASK-5063`, no power cycle). Raw data: `data_20260926/t5063/`.

## 1. Result in one table

| Rate | Direction | Words checked | Bit errors | 8b10b code errors | BER | Settings | Verdict |
|---|---|---|---|---|---|---|---|
| 0.3 Gb/s | both | 1.14·10⁹ each | 0 | 0 | < 6.6·10⁻¹¹ | as built (`VERIFY_20260926.md` §6) | ✅ clean |
| 1.25 Gb/s | both | 1.885·10⁹ each | 0 | 0 | < 4.0·10⁻¹¹ | as built | ✅ clean |
| **2.5 Gb/s** | m2→gs | **3.76·10⁹** (120 s) | 16 576 | 4 715 | **1.1·10⁻⁷** | AFE PEAK 24, GAIN 0, VCM 3, TX_AMP 24; m2 `TX_NEG=1` | ⚠️ works, not clean |
| **2.5 Gb/s** | gs→m2 | 1.86·10⁸ | 229 446 | 17 870 | 3.1·10⁻⁵ | same (gs has no `TX_NEG`) | ⚠️ |
| 2.5 Gb/s, best 40 s runs | gs→m2 | 1.25·10⁹ | 6 447 | 472 | 1.3·10⁻⁷ | TX_AMP 24 (`tune_best_amp24`) | ⚠️ run-to-run spread ×10–100 |
| **5 Gb/s** | both | 10⁵–10⁶ | — | many | ~6·10⁻² | DFE on + TX pre/post 5/12 + AFE PEAK 15 GAIN 0 | ❌ link up (CDR lock, right sender IDs), not usable |

Rates are **measured** (clock counters): 2500.02 and 5000.04 Mb/s. Bitstreams: `bitstreams/README.md`.

**Eye margin column:** not available. The on-chip eye counters (regfile 0x14–0x1D) never counted on this silicon —
see §5. `tools/eyescan.py` is ready but has no data to show.

## 2. What limits 2.5 Gb/s — three separate causes

1. **RX analog front end (biggest effect).** Writing Patrick Urban's 5G analog set (pu-cc/gm_serdes_lb `ab7ce94`)
   into the regfile one field group at a time, on the *same* bitstream (`tune_n155od2_s1_*`):

   | Step | BER m2→gs | BER gs→m2 |
   |---|---|---|
   | as built (PEAK 15, GAIN 8, VCM 4) | 2.9·10⁻⁴ | 1.0·10⁻⁴ |
   | + DFE on (`RX_EN_EQA=1`, `EQA_LOCK_CFG=0xC`) | 3.0·10⁻⁴ | 3.1·10⁻⁵ |
   | + **AFE: PEAK 24, GAIN 0, AFE/RTERM VCM 3** | **2.8·10⁻⁷** | **9.6·10⁻⁸** |
   | + CDR `CKP=0x3E`, `TRANS_TH=8` | 1.0·10⁻⁷ | 1.1·10⁻⁷ |
   | + TX pre/post-cursor 5 of 12, `TX_AMP 31` | 9.3·10⁻⁷ | 3.2·10⁻⁵ (worse) |

   The sweep with the fixed checker (`tune_best_*`) shows **`RX_AFE_GAIN` is the key**: GAIN 0 → ~6·10⁻⁷,
   GAIN 4 → 2·10⁻², GAIN 8 → 2·10⁻². PEAK 20…31 makes little difference. TX_AMP: 24 best, 4 and 31 worse.
   At 2.5 Gb/s the TX pre/post-emphasis hurts, so the full 5G recipe is not the best recipe for 2.5 Gb/s.

2. **The fabric↔SerDes data ports are not timed by nextpnr.** `nextpnr/himbaechel/uarch/gatemate/delay.cc`
   returns `TMG_IGNORE` for every port of the SERDES cell, so `TX_DATA_I` / `RX_DATA_O` paths are never checked.
   The Fmax numbers in the build logs do not cover them. Proof on the boards:
   - With gs checker bits from 6 different seeds, m2→gs had ~25 % of words with exactly **1 bit** wrong and almost no
     8b10b code errors (1.9·10⁸ bad words vs ~10⁴ code errors) — the data was wrong *before* the 8b10b encoder
     on m2. It changed with the m2 bitstream (6 % with one m2 build, 25 % with another), not with the gs seed.
   - `TX_NEG=1` on m2 (TX data from a negedge register, i.e. half a word clock away from the rising edge):
     m2→gs dropped from 1.96·10⁸ bad words to **4 516** (BER 1.6·10⁻⁶), and the remaining errors now follow
     the code errors (real line errors).
   - The gs receive side also depends on placement: the same analog settings gave 9.5·10³ or 3.3·10⁵ code
     errors with two gs builds.
   - `CLK_DIRECT=1` (TX_CLK_I/RX_CLK_I straight from PLL_CLK_O/RX_CLK_O, as in serdes_lb.v) did **not** help
     (5·10⁻⁶ … 7·10⁻⁵, and m2 sometimes did not sync).
3. **Fabric checker speed on gs.** The first checker had rclk Fmax 32.6 MHz for the 31.25 MHz word clock.
   The one-hot aux-frame write raised it to 45 MHz (`ber_link_gs.v`); the pipelined checker (`ber_link.v`:
   byte popcounts + registered compare) reaches 66–77 MHz on m2 but **does not route on gs** (nextpnr router2
   "Failed to route arc" near the SerDes on seeds 1–7, router1 assertion `gatemate.cc:591`). The fabric STA itself
   is fine (TASK-5064, `NEXTPNR_SETUPHOLD_PATCH.md`); what it does not see is the SerDes port interface (cause 2).

Run-to-run spread: loading the same bits twice gave BER 5.5·10⁻⁷ and 1.5·10⁻⁵ with identical settings
(`tune_best_p24g0` vs `tune_best_amp15`). That fits cause 2: the untimed interface lands at a different phase after
each reset.

## 3. 5 Gb/s (1·5·5, OUTDIV 1; DCO 2500 MHz = in DS1001 spec)

Bits `ber_{gs,m2}_5g_txneg_CFGRST.bit`, JTAG `ber_jtag_check.py` (80-bit RX samples through the regfile, independent
of the fabric checker):

| Settings (both boards) | CDR | RX samples gs / m2 |
|---|---|---|
| as built | 0 | OTHER 10/10 / OTHER 10/10 |
| + CDR CKP 0x3E, TRANS_TH 8, LOCK_CFG 0xD5 | 0 | OTHER / OTHER |
| + DFE on (`RX_EN_EQA=1`, `EQA_LOCK_CFG=0xC`) | **1** | PEER 3/5 / PEER 3/5 |
| + TX pre/post 5/12, AMP 31, DC_ENABLE 43 | 1 | PEER 3/5 / **PEER 5/5** |
| + AFE PEAK 15 (GAIN 0) | 1 | **PEER 5/5 / PEER 5/5** (then 10/10 and 9/10) |
| GAIN 8 | 0 | OTHER / OTHER |

So at 5 Gb/s the full pu-cc recipe matters: DFE + TX FFE + low AFE gain. The fabric BER with it is ~6·10⁻²
(m2 checker: 3.7·10⁶ words, 9.6·10⁶ bit errors, 1.7·10⁶ code errors; `t5063_5g_recipe.json`). The gs checker cannot run
at 62.5 MHz (Fmax 44 MHz), so the m2→gs number is not meaningful. 6.4 Gb/s (2·4·4, DCO 3.2 GHz, above DS1001) was
**not tried**: it makes no sense before 5 Gb/s is clean.

## 4. Findings from pu-cc / colognechip (items 1–6 of the task)

| # | Item | Result |
|---|---|---|
| 1 | pu-cc/gm_serdes_lb @56aa48b | `tools/serdestool.py` = upstream 56aa48b + Python 3.7 fix (Pi) + optional eyetools import; `serdes_jtag.py` keeps our probe choice (`FPGA_JTAG_BUSDEV`, idx 0) and adapts to the new `rd_regfile(idx, addr)` signature (`tests/test_serdes_jtag_compat.py`). `tools/eyetools.py` copied. **Upstream `tc_eyemeas` is an empty stub** — the acquisition was never published; `tools/eyescan.py` is our acquisition. `RX_SLIDE_MODE=00` was already set in our design. |
| 2 | ab7ce94 "prepare 5G tests" | Recipe decoded into `ber_top.v` `PROFILE=1` (bitstream) and tried field by field over JTAG (§2, §3). DATAPATH 80 was already ours. |
| 3 | nextpnr | `30669ec` (CDR param widths) is upstream and in oss-cad-suite 2026-09-23 — and it **confirms our bug**: `RX_CDR_TRANS_TH` is 7 bits, we passed `9'h80` → reads **0** on m2 (DS default 8). Fixed in `PROFILE=1`. `7e68bea` (SER_CLK) is upstream. `abd0731` "fix setuphold corners" (pu-cc/nextpnr gatemate-setuphold-fix) is **not** in YosysHQ main (checked 26.09.2026, `git merge-base`; no PR by pu-cc). TASK-5064 evaluated it (`NEXTPNR_SETUPHOLD_PATCH.md`): `fast_*`/`slow_*` are rise/fall, not corners, so **upstream is correct and the patch is wrong** (no effect on CPE FFs, swaps BRAM setup/hold; byte-identical result for the BER designs). My first reading ("upstream STA is optimistic", Telegram 20:40) was wrong. |
| 4 | liteeth gatemate1000basex / gatematergmii | Not used yet (Ethernet over SerDes is a later step). |
| 5 | gatemate-pipe `0x51=0x16FA` | Decoded: OUTDIV 2, N 1·5·5, FCNTRL 0x3A = **exactly our n155od2 (2.5 Gb/s)**. The testbench notes "N1 and N2 names are twisted compared to spec". Polarity: gatemate-pipe inverts RX polarity from the LTSSM, same idea as our `RX_POLARITY_I=1`. |
| 6 | ulx5m-gh 760f7bc "+1V8 instead of VDD_CLK" | In pu-cc's schematic `VDD_CLK` (U4.T14) was on +1V8 before and after the commit — a label clean-up, no electrical change. **Our `ulx5m-gs-hw`: U4.T14 VDD_CLK = +1V8**, VDD_SER / VDD_SER_PLL from VDD_CORE through L7/L6 (`kicad_netlist.py`). No supply problem for 2.5 G on GS. The M2 schematic is not in our tree → not checked. |

## 5. Things that did not work (so nobody repeats them blindly)

- **On-chip eye scan:** `RX_EYE_MEAS_EN` (0x14[0]) reads 1 at once and all 8 counters (0x16–0x1D) stay 0 — with and
  without data, with DFE on/off, `EQA_LOCK_CFG` 0/2/0xE, and with `RX_EYE_MEAS_EN=1` in the bitstream (`EYE_EN=1`).
- **Hard PRBS checker:** with PRBS-15/PRBS-7 (select 2/1, not the reserved 4 used before) it now **locks**, but counts
  ~1400–2200 errors/s independent of the AFE settings; with comma detect/align disabled it saturates at once.
  Not a BER instrument here.
- `ber_mon.py inject` fails on a link with background errors (the window counts real errors too). Use it only on a
  clean link.
- `ber_mon.py run --clear --json`: the `new_*` deltas can wrap after the clear; the BER line uses the absolute
  counters (cleared at the start), which are correct.

## 6. Tools added (all in this repo)

| File | What |
|---|---|
| `gateware/ber/ber_top.v` | parameters `PROFILE` (0 = as proven, 1 = pu-cc 5G analog set), `TX_NEG`, `RX_NEG`, `CLK_DIRECT`, `EYE_EN` |
| `gateware/ber/ber_link.v` | pipelined checker (one-hot aux write, byte popcounts, registered compare); m2 rclk 66–77 MHz |
| `gateware/ber/ber_link_gs.v` | 965520c checker for gs (routes; 45–49 MHz) |
| `gateware/ber/build_ber.sh` | env `FREQ` (nextpnr timing target), `ROUTER`, `SYNTH_OPTS`, `LINK` |
| `tools/eyescan.py` | `set`/`get` any regfile field by name (analog tuning without rebuild), `scan`/`margin`/`plot` (eye; needs working counters) |
| `tools/lab/tune.sh` | load once, then per step: JTAG field writes → BER run → optional eye scan |
| `tools/serdestool.py`, `eyetools.py` | pu-cc 56aa48b |

Tests: `python3 -m unittest discover -s tools/tests` (38 pass), `gateware/ber/sim/tb_ber_link.v` 11/11 PASS, `tb_top.v` synced with 0 errors.

## 7. Next steps (recommendation)

1. **Constrain or hand-place the SerDes interface.** The biggest lever left at 2.5 Gb/s is the untimed
   `TX_DATA_I`/`RX_DATA_O` path. Options: add SERDES port timing to nextpnr, or keep `TX_NEG`/`RX_NEG` and pick
   seeds by a short BER run.
2. Report the missing SERDES port timing (`delay.cc` `TMG_IGNORE`) upstream. Not `abd0731` — see `NEXTPNR_SETUPHOLD_PATCH.md`.
3. gs checker: shrink the rclk logic on gs (the 256-bit peer-frame snapshot) so the pipelined checker routes, then 5 Gb/s.
4. Ask CologneChip/Patrick how the eye counters are started (the upstream `tc_eyemeas` is empty).

## 8. Measurement log (every run, 40–120 s, cleared counters)

| Run (JSON) | Rate [Mb/s] | Settings (both boards, JTAG regfile) | m2→gs words / bit err / 8b10b code err | BER m2→gs | gs→m2 words / bit err / code err | BER gs→m2 |
|---|---|---|---|---|---|---|
| `tune_n155od2_s1_base` | 2500.02 | old sweep bits (TASK-5055), analog as built | 1.36e+09 / 15530483 / 3332433 | 2.9e-04 | 6.89e+07 / 274698 / 65340 | 1.0e-04 |
| `tune_n155od2_s1_eqa` | 2500.02 | + RX_EN_EQA=1, EQA_LOCK_CFG=0xC | 1.25e+09 / 14867088 / 3556165 | 3.0e-04 | 1.23e+06 / 1519 / 695 | 3.1e-05 |
| `tune_n155od2_s1_afe` | 2500.02 | + AFE PEAK 24, GAIN 0, AFE/RTERM VCM 3 | 1.93e+07 / 216 / 98 | 2.8e-07 | 5.16e+07 / 198 / 359 | 9.6e-08 |
| `tune_n155od2_s1_cdr` | 2500.02 | + CDR_CKP 0x3E, CDR_TRANS_TH 8 | 2.11e+08 / 844 / 529 | 1.0e-07 | 2.07e+08 / 906 / 1127 | 1.1e-07 |
| `tune_n155od2_s1_txffe` | 2500.02 | + TX pre/post 5 of 12, TX_AMP 31 | 1.28e+09 / 47575 / 24570 | 9.3e-07 | 1.13e+08 / 143538 / 39714 | 3.2e-05 |
| `tune_n155od2p0_s1_p0base` | 2500.02 | 965520c bits (one-hot aux), analog as built | 1.43e+09 / 97635516 / 2055489 | 1.7e-03 | 1.34e+06 / 4155 / 977 | 7.7e-05 |
| `tune_n155od2p0_s1_afe24` | 2500.02 | + AFE PEAK 24 GAIN 0 VCM 3 | 1.41e+09 / 83694202 / 5714 | 1.5e-03 | 7.23e+05 / 747 / 44 | 2.6e-05 |
| `tune_best_d15g8` | 2500.02 | m2 TX_NEG + gs s7: AFE PEAK 15 GAIN 8 (as built) | 1.25e+09 / 40496076 / 9996537 | 8.1e-04 | 2.75e+05 / 4026 / 1190 | 3.7e-04 |
| `tune_best_p20g0` | 2500.02 | PEAK 20 GAIN 0 VCM 3 | 1.25e+09 / 34993 / 20866 | 7.0e-07 | 5.66e+08 / 286130 / 137759 | 1.3e-05 |
| `tune_best_p24g0` | 2500.02 | PEAK 24 GAIN 0 | 1.26e+09 / 27718 / 18163 | 5.5e-07 | 1.26e+09 / 478761 / 244725 | 9.5e-06 |
| `tune_best_p28g0` | 2500.02 | PEAK 28 GAIN 0 | 1.26e+09 / 31799 / 20768 | 6.3e-07 | 1.05e+09 / 475391 / 234542 | 1.1e-05 |
| `tune_best_p31g0` | 2500.02 | PEAK 31 GAIN 0 | 1.25e+09 / 33042 / 24353 | 6.6e-07 | 7.64e+08 / 351516 / 175837 | 1.1e-05 |
| `tune_best_p24g4` | 2500.02 | PEAK 24 GAIN 4 | 1.27e+09 / 1090654419 / 136550084 | 2.1e-02 | 3.03e+04 / 4499 / 612 | 3.7e-03 |
| `tune_best_p24g8` | 2500.02 | PEAK 24 GAIN 8 | 1.26e+09 / 901545515 / 120516487 | 1.8e-02 | 1.06e+06 / 54489 / 10248 | 1.3e-03 |
| `tune_best_amp15` | 2500.02 | reload, PEAK 24 GAIN 0, TX_AMP 15 | 1.29e+09 / 792547 / 332121 | 1.5e-05 | 1.29e+09 / 58640 / 5862 | 1.1e-06 |
| `tune_best_amp8` | 2500.02 | TX_AMP 8 | 1.27e+09 / 1802046 / 634631 | 3.6e-05 | 1.68e+07 / 3544 / 484 | 5.3e-06 |
| `tune_best_amp4` | 2500.02 | TX_AMP 4 | 1.26e+09 / 24946788 / 5529490 | 4.9e-04 | 5.46e+07 / 52517 / 9473 | 2.4e-05 |
| `tune_best_amp24` | 2500.02 | TX_AMP 24 | 1.25e+09 / 262016 / 132301 | 5.2e-06 | 1.25e+09 / 6447 / 472 | 1.3e-07 |
| `tune_best_amp31` | 2500.02 | TX_AMP 31 | 1.26e+09 / 4537513 / 1198706 | 9.0e-05 | 1.26e+09 / 186270 / 15022 | 3.7e-06 |
| `t5063_5g_recipe` | 5000.04 | 5 Gb/s (1·5·5/1), m2 TX_NEG + gs s7 TX_NEG: DFE on, TX pre/post 5/12, AMP 31, PEAK 15 GAIN 0 | 1.32e+05 / 335386 / 45246 | 6.3e-02 | 3.66e+06 / 9561144 / 1724322 | 6.5e-02 |

| `t5063_2g5_final` | 2500.02 | reproducible bits `ber_gs_2g5` + `ber_m2_2g5_txneg`, PEAK 24 GAIN 0 VCM 3 TX_AMP 24, 120 s | 3.76e+09 / 16576 / 4715 | 1.1e-07 | 1.86e+08 / 229446 / 17870 | 3.1e-05 |
