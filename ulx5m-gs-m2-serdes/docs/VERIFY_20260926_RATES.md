# GS↔M2 SerDes above 1.25 Gb/s — 2.5 and 5 Gb/s (TASK-5063, 26.09.2026)

**Requested by:** Goran (Telegram 26.09.2026 19:31). **Done by:** Jelena (REGOČ). **Starting point:** `VERIFY_20260926.md` §6
(1.25 Gb/s clean, 2.5 Gb/s BER ~10⁻⁴). Lab rules: `regoc_system/docs/FPGA_LAB_ARHITEKTURA.md` (fpga-jtag, CFGRST on every
bit, gs lease `/home/pi/gs.owner` as `TASK-5063`, no power cycle). Raw data: `data_20260926/t5063/`.

## 1. Result in one table

| Rate | Direction | Words checked | Bit errors | 8b10b code errors | BER | Settings | Verdict |
|---|---|---|---|---|---|---|---|
| 0.3 Gb/s | both | 1.14·10⁹ each | 0 | 0 | < 6.6·10⁻¹¹ | as built (`VERIFY_20260926.md` §6) | ✅ clean |
| 1.25 Gb/s | both | 1.885·10⁹ each | 0 | 0 | < 4.0·10⁻¹¹ | as built | ✅ clean |
| **2.5 Gb/s, `PROFILE=1` in the bitstream** | m2→gs | **9.39·10⁹** (300 s) | **25** | 42 | **6.7·10⁻¹¹** | pu-cc 5G set baked in (DFE on, AFE PEAK 24 GAIN 0 VCM 3, CDR CKP 0x3E TRANS_TH 8, TX pre/post 5/12 AMP 31, TX calib); m2 `TX_NEG=1`; no JTAG writes | ✅ near-clean |
| **2.5 Gb/s, `PROFILE=1`** | gs→m2 | **9.39·10⁹** (300 s) | 435 | 382 | **1.2·10⁻⁹** | same (gs has no `TX_NEG`) | ✅ near-clean |
| 2.5 Gb/s, `PROFILE=0` as built | m2→gs / gs→m2 | 1.89·10⁹ / 1.1·10⁶ (60 s) | 4.4·10⁷ / 9 599 | 9.1·10⁶ / 1 900 | 5.9·10⁻⁴ / 2.1·10⁻⁴ | serdes_lb.v values (AFE PEAK 15 GAIN 8, CDR TRANS_TH 0) | ❌ |
| 2.5 Gb/s, PROFILE 0 + AFE over JTAG | m2→gs | 3.76·10⁹ (120 s) | 16 576 | 4 715 | **1.1·10⁻⁷** | AFE PEAK 24, GAIN 0, VCM 3, TX_AMP 24; m2 `TX_NEG=1` | ⚠️ works, not clean |
| 2.5 Gb/s, PROFILE 0 + AFE over JTAG | gs→m2 | 1.86·10⁸ | 229 446 | 17 870 | 3.1·10⁻⁵ | same (gs has no `TX_NEG`) | ⚠️ |
| 2.5 Gb/s, best 40 s runs | gs→m2 | 1.25·10⁹ | 6 447 | 472 | 1.3·10⁻⁷ | TX_AMP 24 (`tune_best_amp24`) | ⚠️ run-to-run spread ×10–100 |
| **5 Gb/s** | both | 10⁵–10⁶ | — | many | ~6·10⁻² | DFE on + TX pre/post 5/12 + AFE PEAK 15 GAIN 0 | ❌ link up (CDR lock, right sender IDs), not usable |
| 5 Gb/s, `PROFILE=1` in the bitstream | m2→gs / gs→m2 | 1.9·10⁶ / 4.7·10⁶ (60 s) | 4.8·10⁶ / 9.8·10⁶ | 4.7·10⁵ / 1.8·10⁶ | 6·10⁻² / 5·10⁻² | PROFILE 1 + JTAG AFE PEAK 15 (PEAK 24: 0.12 / 0.07); both `TX_NEG=1` | ❌ CDR locks from the bitstream, PEER 8–9/10 |

Rates are **measured** (clock counters): 2500.02 and 5000.04 Mb/s. Bitstreams: `bitstreams/README.md`.

**Eye margin column:** not available. The on-chip eye counters (regfile 0x14–0x1D) never counted on this silicon —
see §5. `tools/eyescan.py` is ready but has no data to show.

**Most important result:** the same pu-cc analog set gives BER ~10⁻⁷ when written over JTAG into a running link,
but **6.7·10⁻¹¹ / 1.2·10⁻⁹ when it is in the bitstream** (`PROFILE=1`). The bitstream path applies it before the
reset/calibration sequence (TX termination calibration `TX_CALIB_EN`, `RX_RESET_TIMER_PRESC=4`, DFE adaption from
reset). So: tune over JTAG to find the direction, then bake it into the bitstream and measure again.

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

Tests: `python3 -m unittest discover -s tools/tests` (39 pass; `ber_parse` now skips corrupted UART lines), `gateware/ber/sim/tb_ber_link.v` 11/11 PASS, `tb_top.v` synced with 0 errors.

## 7. Next steps (recommendation)

0. **Use `PROFILE=1` bitstreams for 2.5 Gb/s** (`bitstreams/ber_*_2g5_p1_*`). Next: `TX_NEG=1` on gs too, and a
   long run (≥ 30 min, target BER < 10⁻¹²).
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
| `t5063_profile0_asbuilt` | 2500.02 | PROFILE 0 bits, no JTAG writes, 60 s | 1.89e+09 / 44373016 / 9065141 | 5.9e-04 | 1.13e+06 / 9599 / 1900 | 2.1e-04 |
| `t5063_profile1_asbuilt` | 2500.02 | PROFILE 1 bits, no JTAG writes, 60 s | 1.89e+09 / 8 / 18 | 1.1e-10 | 1.89e+09 / 1656 / 1316 | 2.2e-08 |
| `t5063_profile1_300s` | 2500.02 | PROFILE 1 bits, no JTAG writes, 300 s | 9.39e+09 / 25 / 42 | 6.7e-11 | 9.39e+09 / 435 / 382 | 1.2e-09 |
| `t5063_5g_profile1_pk15` | 5000.04 | PROFILE 1 5G bits, both TX_NEG, JTAG AFE PEAK 15 | 1.93e+06 / 4795495 / 467073 | 6.2e-02 | 4.72e+06 / 9818639 / 1785938 | 5.2e-02 |
| `t5063_5g_profile1_pk24` | 5000.04 | same, PEAK 24 | 1.78e+07 / 86704746 / 7132712 | 1.2e-01 | 1.20e+07 / 33738985 / 5297676 | 7.1e-02 |

## 9. TASK-5066: 5 Gb/s experiments E0–E8 (TUNING_5G.md §3), 26./27.09.2026

**Order:** Goran 26.09. 21:44 (driver strength, equalizer …), new order TUNING_5G.md `6747484`/`09df250`, instructions #94–#101
(J3 = 1.1 V on both boards, so the supply is not a gate; #98 side comparison; #99 no per-board loopback).
**Done by:** Jelena. Lab rules: FPGA_LAB_ARHITEKTURA.md (fpga-jtag, every bit CFGRST, gs lease `TASK-5066`).
**Raw data:** `data_20260926/t5066/` (one ber_mon JSON per load `<point>_r<k>.json` + E0/health JSONs + the lab scripts
`lab1.sh`–`lab4.sh` exactly as run + their console output `lab*.out`).
**Tools:** `tools/lab/abrun.sh` (every point = fresh load m2 then gs, JTAG writes, sweep procedure `eyescan.py recal`,
health of both receivers, BER run with cleared counters), `tools/lab/ab_table.py` (median per point),
`tools/eyescan.py health|recal`.

**How to read the 5 Gb/s numbers.** The m2 checker runs at 73 MHz (word clock 62.5 MHz), so gs→m2 is measured on
m2 — but its counters reach gs over the m2→gs link, which itself has errors: single status lines carry corrupted
counters (seen: BER 1.92, 1.3·10¹¹ words in 60 s). `ab_table.py` caps BER at 0.5 and treats a word count above
(secs + 10 s) × word rate as corrupted (0.5). The gs checker still has rclk Fmax 45–50 MHz < 62.5 MHz
(pipelined `ber_link.v` still does not route on gs: 8 more seeds, 4 × "Failed to route", 4 × nextpnr
`std::out_of_range`), so **m2→gs at 5 G is indicative only**. Everything at 5 G is in the 10⁻² … 10⁻¹ band, where
this does not change any conclusion. "bits" = checked bits while synced; at 5 G the checkers are synced only
~1–10 % of the time (loss of sync every few seconds).

### 9.1 E0 — health snapshot, read-only (PROFILE 1, no JTAG writes; FREQ/PHASE_ACC: 10 reads 1 s apart)

| Field | gs 2.5 G | m2 2.5 G | gs 5 G | m2 5 G |
|---|---|---|---|---|
| PLL lock (`PLL_LOCKED`) | 1 | 1 | 1 | 1 |
| **FT_OF / FT_UF** (`PLL_CAP_FT_OF/UF`) | 0 / 0 | 0 / 0 | **0 / 0** | **0 / 0** |
| CAP_FT (`PLL_CAP_FT`) | 437 | 509 | 439 | 517 |
| BISC timer done / CP valid | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 |
| BISC CP / CO | 24 / 65360 | 24 / 63701 | 24 / 65298 | 24 / 63422 |
| RX cal done / cal (`RX_CALIB_DONE/CAL`) | 1 / 0 | 1 / 0 | 1 / 0 | 1 / 0 |
| TX cal done / cal (`TX_CALIB_DONE/CAL`) | 1 / 0 | 1 / 0 | 1 / 0 | 1 / 0 |
| EQA lock (`RX_EQA_LOCKED`) | 1 | 1 | 1 | 1 |
| DFE tap (`RX_EQA_TAPW`) | 0 | 0 | 5 | 4 |
| `RX_TH_MON` | 15 (rail) | 15 (rail) | 15 (rail) | 15 (rail) |
| `RX_OFFSET` | 2 | 7 | −3 | 0 |
| **CDR lock in every sample** | 1 | 1 | **0** | **0** |
| `RX_PRESENT` / `RX_DETECT_DONE` / `RX_BUF_ERR` (0x2A[12..14]) | 0 / 1 / 0 | 0 / 1 / 0 | 0 / 1 / 0 | 0 / 1 / 0 |
| `RX_CDR_FREQ_ACC_VAL` ×10 | 0 | 0 | 0 | 0 |
| `RX_CDR_PHASE_ACC_VAL` ×10 | 16058…17453 | 12212…12491 | 8804…10664 | 5037…9346 |

Reading:
- **The PLL is healthy at 5 G**: locked, no FT overflow/underflow, and CAP_FT equals the 2.5 G value (same 2.5 GHz DCO,
  only OUTDIV differs). TUNING_5G.md E0 question "does 5 G fail in the PLL/CDR or in the data eye?" → **not in the PLL**;
  the CDR does not hold lock (0 in most samples at 5 G; the recal step sees it locked for a moment), and on m2 the
  phase accumulator spans 4309 codes over 10 s vs 279 at 2.5 G (gs: 1860 vs 1395).
- FREQ_ACC = 0 everywhere: `RX_CDR_CKI = 0` in all profiles → the frequency integrator is off (expected; both boards
  share the refclk).
- BISC TIMER_DONE / CP_VALID = 0 at both rates on both boards, with PLL lock → the same state where 2.5 G works;
  not a 5 G marker. `RX/TX_CALIB_CAL = 0` and `RX_TH_MON = 15` (the top of the signed 5-bit range) on both boards at both
  rates — UNVERIFIED whether that is "calibrated to code 0" / "threshold monitor at the rail"; worth one question to
  CologneChip.
- `RX_PRESENT = 0` with `TX_DETECT_RX_I = 1` (these bits) — the receiver detection did not report the far end.

### 9.2 E1 — `TX_DETECT_RX_I` 1 → 0 (and `TX_CALIB_EN = 1` in every profile)

`ber_top.v` parameters `TX_DET_RX` (default now 0 = upstream pu-cc `dda07f7`), `TX_CALIB` (default 1), `PLL_RTERM`.
With `TX_DET_RX 1` the old 2.5 G PROFILE 1 pair and the 5 G PROFILE 1 pair **rebuild byte for byte**
(`ber_gs_2g5_p1_CFGRST.bit` sha256 5dfba1ec…); the `TX_DET_RX 0` bits differ from them in **3 bytes** (the
config bit + CRC) — same placement, a pure A/B. Loads interleaved for r4–r6.

| Point | loads × s | BER gs→m2 median (worst) | BER m2→gs median (worst) |
|---|---|---|---|
| 2.5 G `TX_DETECT_RX_I=1` (old) | 6 × 60 | 4.7·10⁻⁹ (1.5·10⁻⁷) | 5.7·10⁻¹⁰ (4.8·10⁻⁹) |
| 2.5 G `TX_DETECT_RX_I=0` | 6 × 60 | 2.0·10⁻⁸ (4.3·10⁻⁷) | 1.1·10⁻⁸ (7.1·10⁻⁸) |
| 5 G `TX_DETECT_RX_I=1` | 3 × 60 | 7.9·10⁻² | 1.0·10⁻¹ |
| 5 G `TX_DETECT_RX_I=0` | 3 × 60 | 7.8·10⁻² | 9.8·10⁻² |

**Result: no improvement** (TUNING_5G.md E1 pass criterion "≥ 3× better" not met). At 2.5 G the medians are even a
little worse with 0, but the ranges of the two sets overlap (single loads of either bit span 5·10⁻¹⁰ … 4·10⁻⁷).
At 5 G no difference. `TX_DET_RX = 0` stays the default (= upstream, as TUNING_5G.md asks for "no change").

### 9.3 Side comparison (instruction #98): which side is weaker, 2.5 Gb/s PROFILE 1, `TX_DETECT_RX_I=0`, 300 s each

| Direction → | TX board (bit, seed) | RX board (bit, seed) | TX_NEG on TX | BER gs→m2 | BER m2→gs |
|---|---|---|---|---|---|
| `sd_gs7_m21` | gs s7 / m2 s1 | m2 s1 / gs s7 | gs 1, m2 1 | 2.4·10⁻⁹ | 1.2·10⁻⁸ |
| `sd_gs2_m21` | gs **s2** / m2 s1 | | gs 1, m2 1 | 3.4·10⁻⁹ | 1.9·10⁻⁸ |
| `sd_gs3_m21` | gs **s3** / m2 s1 | | gs 1, m2 1 | 9.5·10⁻⁹ | 1.6·10⁻⁸ |
| `sd_gs7_m22` | gs s7 / m2 **s2** | | gs 1, m2 1 | **4.7·10⁻¹⁰** | **1.6·10⁻¹¹** |
| `sd_gs7_m23` | gs s7 / m2 **s3** | | gs 1, m2 1 | 7.5·10⁻¹⁰ | 6.9·10⁻⁸ |
| `sd_gs7nt_m21` | gs s7 **without TX_NEG** / m2 s1 | | gs **0**, m2 1 | 1.5·10⁻⁷ | 1.1·10⁻¹⁰ |

Conclusion (each row one 300 s load; the same bit loaded again spreads ×10–100, so single factors below ~10× are not
significant):
- **gs→m2 (gs TX, m2 RX): the gs TX fabric timing.** `TX_NEG=1` on gs: 2.4·10⁻⁹ vs 1.5·10⁻⁷ without (≈ 60×). The gs seed
  moves it only ×1.4–4; the m2 build (m2 RX placement) ×3–5.
- **m2→gs (m2 TX, gs RX): the m2 build.** With the same gs bit, m2 seed 2 / 1 / 3 gives 1.6·10⁻¹¹ / 1.2·10⁻⁸ / 6.9·10⁻⁸
  (×4000). Three gs seeds with the same m2 bit stay at 1.2–1.9·10⁻⁸.
- So today's asymmetry at 2.5 G (m2→gs better than gs→m2 before `e3a6375`) was **fabric timing of the TX path**
  (nextpnr does not time the SerDes ports, §2 cause 2), not one board being worse. Near-end loopback per board was
  dropped on Goran's instruction #99.
- Best pair: **gs `TX_NEG=1` s7 + m2 s2**: 4.7·10⁻¹⁰ / 1.6·10⁻¹¹ (re-measured in §9.7).

### 9.4 E2 — 5 G RX AFE (DFE on, `EQA_LOCK_CFG 0xC`, VCM 3), both boards, 1 load × 60 s per point

| GAIN \ PEAK | 24 | 16 | 12 | 8 | 4 | 0 (= most peaking) |
|---|---|---|---|---|---|---|
| 0 | 4.8e-2 / 9.5e-3 | 1.1e-1 / 1.7e-1 | **4.3e-2 / 2.4e-2** | 8.4e-2 / 5.0e-2 | 9.9e-2 / 6.1e-2 | 1.1e-1 / 6.4e-2 |
| 1 | 1.0e-1 / no sync | 1.1e-1 / no sync | 7.7e-2 / 6.6e-2 | corrupt / 3.5e-2 | 1.3e-1 / 7.1e-2 | 1.1e-1 / 2.7e-1 |
| 2 | 1.0e-1 / no sync | 1.1e-1 / no sync | 3.7e-2 / 9.2e-2 | 1.2e-1 / 6.0e-2 | corrupt / 1.0e-1 | corrupt / no sync |
| 3 | 1.2e-1 / no sync | 1.4e-1 / no sync | 1.1e-1 / 6.9e-2 | 8.3e-2 / 7.7e-2 | 1.1e-1 / 6.1e-2 | 1.2e-1 / no sync |

(gs→m2 / m2→gs; "no sync" = gs checker never synced, "corrupt" = impossible m2 counters.) **No AFE point below ~10⁻²**
(pass criterion < 10⁻⁶ not reached). GAIN ≥ 1 with little peaking loses the gs receiver completely; GAIN 0 stays best
as at 2.5 G. The first E2 attempt had a point-generator bug (every point followed by an empty duplicate that
overwrote its JSON) and was stopped and repeated; only the repeat is in the data.

### 9.5 5 G: seeds, CLK_DIRECT, E4 CDR, E3 TX FFE, E5 VCM, E6 refclk (AFE GAIN 0 PEAK 12 on both, 1 × 60 s)

| Point | BER gs→m2 | BER m2→gs |
|---|---|---|
| seeds: m2 s2 / s3 / s4 / s5 (gs s7) | 1.0e-1 / 4.0e-2 / 1.3e-1 / 1.5e-1 | 1.9e-1 / 2.6e-2 / 2.0e-1 / 2.0e-1 |
| seeds: gs s2 / s3 / s4 (m2 s1) | 1.1e-1 / 1.2e-1 / 1.2e-1 | 2.0e-1 / 1.9e-1 / 4.0e-2 |
| `CLK_DIRECT=1` both | 1.2e-1 | 2.2e-1 |
| E4 CKP 0xF8: TRANS_TH 8 / 16 / 32 | 4.6e-2 / 5.6e-2 / 5.1e-2 | 1.9e-2 / 2.6e-2 / 2.7e-2 |
| E4 CKP 0x7E: 8 / 16 / 32 | 4.0e-2 / 6.5e-2 / 5.1e-2 | 2.9e-2 / 5.4e-2 / 3.6e-2 |
| E4 CKP 0x3E: 8 / 16 / 32 | 5.6e-2 / 8.3e-2 / 5.3e-2 | 3.3e-2 / 3.6e-2 / 3.4e-2 |
| E4 CKP 0x1E: 8 / 16 / 32 | 5.5e-2 / **2.5e-2** / 4.7e-2 | 3.3e-2 / **2.7e-2** / 3.3e-2 |
| E3 BR_PRE 0, BR_POST 31, DC 47, SEL_POST 0 / 6 / 12 / 17 / 20 | 4.4e-2 / 7.7e-2 / 5.4e-2 / 9.7e-2 / 1.1e-1 | 4.2e-2 / 2.3e-2 / **1.6e-2** / 4.6e-2 / 5.6e-2 |
| E3 BR_PRE 12, DC 53, SEL_POST 12, SEL_PRE 2 / 5 | 6.3e-2 / 7.4e-2 | 2.3e-2 / 2.6e-2 |
| E3 TX_AMP 20 / 24 / 28 (on PROFILE 1 FFE) | 5.6e-2 / 5.3e-2 / 4.5e-2 | 3.9e-2 / 5.9e-2 / 3.1e-2 |
| E5 RX/RTERM VCM 2 / 4 / 5 | 5.7e-2 / 4.8e-2 / 4.2e-2 | 4.4e-2 / 2.5e-2 / 2.9e-2 |
| E6 gs `PLL_REF_RTERM=0` (3 loads, median) vs 1 (3 loads) | 5.2e-2 vs 4.8e-2 | 2.7e-2 vs 3.1e-2 |

E3 was run on both boards at the same time: each direction depends only on its own TX, so the gs→m2 column is the gs TX
sweep and the m2→gs column the m2 TX sweep. `RX_NEG=1` at 5 G was built but not loaded: it drops rclk Fmax to
35–42 MHz (< 62.5). E6 needed a rebuild of gs only (`PLL_RTERM 0`, 3-byte difference to the E1 bit).

**Nothing moves 5 G out of the 10⁻² … 10⁻¹ band.** The spread between points (×2–5) is the size of the load-to-load
spread seen at 2.5 G, so none of the "best" entries above is a proven improvement.

### 9.6 E7 — on-chip eye scan with the TUNING_5G.md §5.1 fixes

`tools/eyescan.py scan` now (a) writes the TH_MON2 value to 0x05[10:6] and its override to **0x06[11]** (vendor map;
0x05[11] is unused), (b) turns on `RX_EN_EQA` and `EQA_LOCK_CFG` bit1 for the scan and restores 0x04/0x05/0x06, and
(c) treats 0x14[0] as **EYE_MEAS_DONE** on read (DS1001 Table 2.59: "RX_EYE_MEAS_EN / EYE_MEAS_DONE", w/c). The old
loop waited for the bit to go to 0 and timed out at the first point (seen in `lab4.out`).

Scan 16 phases × 11 thresholds, window 512, on both receivers, with the link running and locked
(`RX_EQA_LOCKED=1`, `RX_CDR_LOCKED=1`, `ber_jtag_check` PEER 200/200 at 2.5 G):

| Link | m2: sum of the 8 counters over 176 points | gs: same |
|---|---|---|
| 2.5 G (gs `TX_NEG` s7 + m2 s2, PROFILE 1) | 0 | 0 |
| 5 G PROFILE 2 | 0 | 0 |

**The counters still never count.** All three suspected causes from §5.1 are ruled out for our use of the registers.
Per TUNING_5G.md E7 the next step is a question to CologneChip / Patrick Urban (upstream `tc_eyemeas` is a stub):
which other condition starts the eye counters (a TESTMODE bit, a monitor enable, `RX_EQA_CONFIG`?).

### 9.7 E8 — PROFILE=2 in the bitstream, 5 Gb/s; and the 2.5 G best pair again

PROFILE 2 = PROFILE 1 + the "best" sweep point (AFE PEAK 12, CDR CKP 0x1E TRANS_TH 16, TX post-cursor only:
31 branches, DC 47, SEL_POST 12). Rebuilt twice → byte-identical (gs s7, m2 s1). Bits:
`bitstreams/ber_{gs,m2}_5g_p2_txneg_CFGRST.bit`. No JTAG writes.

| Run | words gs→m2 / bit err / code err / loss | BER gs→m2 | words m2→gs / bit err / code err / loss | BER m2→gs |
|---|---|---|---|---|
| `e8_p2_300s` (308 s) | 3.32·10⁷ / 8.4·10⁷ / 1.55·10⁷ / 0 | **6.3·10⁻²** | 2.65·10⁵ / 2.1·10⁵ / 4.6·10⁴ / 2 | **2.0·10⁻²** |
| `e8_p2_60s` 3 loads, median (worst) | | 7.3·10⁻² (9.9·10⁻²) | | 1.8·10⁻² (2.9·10⁻²) |

Fabric-independent check (JTAG, 200 RX words per board through the regfile, header = K28.5 + peer id):
**m2 187/200 PEER (6.5 % bad), gs 195/200 (2.5 % bad)** at 5 G PROFILE 2; **200/200 on both** at 2.5 G. So the 5 G
errors are already in the SerDes PCS output. They are not only an artefact of the gs checker being too slow.

5 G target (BER < 10⁻¹⁰ in 300 s → soak) is **not reached**; the soak (§5.3) was not started.

The 2.5 G "best pair" of §9.3 loaded again for 300 s (`best_2g5_gs7_m22`): gs→m2 1.2·10⁻⁸, m2→gs 4.5·10⁻⁸ — vs
4.7·10⁻¹⁰ / 1.6·10⁻¹¹ the first time. Same bits, ×25 / ×2900 apart: the load-to-load lottery (untimed SerDes ports)
is at least as large as the seed effect, so a seed must be chosen by **several** loads, not by one.

### 9.8 Conclusion TASK-5066 and what is left

1. **5 Gb/s is not reachable by register tuning on this setup.** E1–E6 plus seeds and CLK_DIRECT (≈ 60 points) all stay
   at 10⁻² … 10⁻¹, and so does PROFILE 2 in the bitstream. The PLL is clean (E0), so is the DC supply (J3 = 1.1 V, Goran).
   The CDR does not hold lock. The regfile RX words show 2.5–6.5 % bad headers without the fabric.
2. The remaining suspects are **outside the register set**, in TUNING_5G.md order: supply **noise** (E9 = H2: ferrite or
   extra µF at C127/C128 on GS — needs Goran), the channel (H3: FFC/adapter chain, reflections), and refclk quality at
   M2 (H4: scope at C129/C130). E6 (single termination on the shared refclk) did not change anything.
3. **2.5 Gb/s**: `TX_NEG=1` on gs matters (≈ 60× for gs→m2); m2→gs follows the m2 build. The load-to-load spread
   (×10–1000 with identical bits) is the biggest effect left → the SerDes port timing (§2 cause 2) is still the main
   2.5 G problem. Constraining those ports in nextpnr is the real fix.
4. `TX_DETECT_RX_I=0` (upstream): no measurable effect at either rate; kept as the default.
5. Eye counters: still 0 with the register-map fixes → question to CologneChip (E7).
6. Tools: `abrun.sh`/`ab_table.py` (point = fresh load, medians, corrupted-counter guard), `eyescan.py health/recal`,
   E7 fixes; tests 57 pass (`python3 -m unittest discover -s tools/tests`).

### 9.9 Review of §9 (Manda, TASK-5070, 27.09.2026): re-computation and one metric that changes the reading

**Re-computed from the raw data.** `tools/lab/ab_table.py docs/data_20260926/t5066/*.json` gives every median and worst
value in §9.2–§9.7 again (72 points; no number differs).

**Experiment numbering.** The task text (TASK-5066/5070) uses the *old* TUNING_5G.md order (`8b8582e`). §9 uses the
*new* order (`6747484`/`09df250`, after J3 = 1.1 V was confirmed). The two map as follows:

| Task text (old) | §9 (new) | What |
|---|---|---|
| E0 | E0 | health snapshot (§9.1) |
| E1 | — | supply TP10/TP8: not measured, J3 = 2-3 (1.1 V) on both boards per Goran |
| E2 | E1 | `TX_DETECT_RX_I` 1 → 0, `TX_CALIB_EN` = 1 (§9.2) |
| E3 | E2 | 5 G RX AFE GAIN × PEAK (§9.4) |
| E4 | E3 | 5 G TX FFE / TX_AMP (§9.5) |
| E5 | E4 | CDR CKP × TRANS_TH (§9.5) |
| E6 | E5 | VCM (§9.5) |
| E7 | E6 | gs `PLL_REF_RTERM=0` (§9.5) |
| E8 | E7 | eye scan (§9.6) |
| E9 | E8 | PROFILE 2 in the bitstream + 300 s (§9.7); the soak was not run because the gate was not reached |
| — | E9 | supply noise H2 (ferrite / µF): Goran, hardware |

**E1 (§9.2) is a null result, not "slightly worse".** Mann–Whitney on the 6 + 6 loads at 2.5 G gives U = 21/36 (gs→m2) and
22/36 (m2→gs). For n = 6 + 6, two-sided α = 0.05 needs U ≤ 5 or ≥ 31. So neither direction shows a difference. The
det0/det1 bits used for E1 are not in `bitstreams/`, so the "3-byte difference" claim cannot be re-checked from the repo.

**At 5 G the BER in §9.4–§9.7 is conditional on sync.** The checkers count only while synced. The synced share of the
word clock (`words / (secs × rate / 80)`, new last column of `ab_table.py`, test `test_sync_fraction`) spans
**10⁻⁵ … 0.5** across the 5 G loads. It is only weakly related to the BER: the Spearman correlation is +0.20 over the
72 valid gs→m2 loads. Ranking by BER alone therefore picks different points than ranking by "how long the link stays
up".

| Point (1 load unless noted) | BER gs→m2 / m2→gs | synced share gs→m2 / m2→gs |
|---|---|---|
| **E2 GAIN 0 PEAK 24** (least peaking in the sweep) | 4.8e-2 / **9.5e-3** | **0.43 / 0.49** |
| sd5 gs s7 + m2 s3 | 4.0e-2 / 2.6e-2 | 0.38 / 0.65* |
| E3 SEL_POST 0 / 6 | 4.4e-2 / 7.7e-2 | 0.31 / 0.28 (gs→m2) |
| E2 GAIN 0 PEAK 12 (= **base of E3–E6 and PROFILE 2**) | 4.3e-2 / 2.4e-2 | **6.5e-4 / 3.6e-4** |
| PROFILE 2, 300 s | 6.3e-2 / 2.0e-2 | 1.7e-3 / 1.4e-5 |
| PROFILE 1 (E1 5 G, 3 loads, median) | 7.8e-2 / 1.0e-1 | 4.5e-3 / 2.1e-3 |

(* m2→gs is counted by the gs checker, which cannot run at 62.5 MHz (§9 intro), so treat it as indicative only.)

Reading:
- PEAK 12 was chosen as the base of every later sweep because its conditional BER was lowest, but that BER comes from
  only 9.7·10⁷ bits: the link was synced 0.06 % of the time. PEAK 24 held sync ~660× longer, with the lowest m2→gs BER in the
  whole data set. The same holds for SEL_POST 0/6 (TX post-cursor off or small), where the synced share is ~200× higher
  than at SEL_POST 12, which went into PROFILE 2.
- So **PROFILE 2 combines the settings with the shortest synced time**. §9.8 item 1 ("nothing moves 5 G out of
  10⁻² … 10⁻¹") still holds for the BER while synced. But the claim that no register point is better than another
  is not supported: all 5 G sweeps are single loads, and the load-to-load spread (E1 5 G: synced share 10⁻⁴ … 8·10⁻³ for the
  same bit) is large, so neither PEAK 24 nor PEAK 12 is proven.
- This also corrects TUNING_5G.md §1 item 4 ("5 G needs more peaking, PEAK 15 → 0"). That item was written from conditional
  BER. The E2 row GAIN 0 shows no BER gain toward PEAK 0, and the synced share is highest at PEAK 24.
- Still consistent with §9.7: the regfile RX words are 2.5–6.5 % bad without the fabric, so even the best point has a
  real error floor in the PCS. The synced share decides whether a longer soak can collect meaningful statistics.

**Next step (lab, ~1 h, gs lease):** before any hardware change (E9/H2), re-run 3 loads × 60 s each of
(a) GAIN 0 PEAK 24, (b) PEAK 24 + SEL_POST 0, (c) PEAK 24 + SEL_POST 6, (d) PEAK 24 + TRANS_TH 16 CKP 0x1E, and (e) PROFILE 2 as the control.
Rank the points by the median synced share gs→m2 first and by BER second (`ab_table.py` prints both). If (a)–(d)
stay ≥ 10× above (e) in synced share, rebuild PROFILE 2 on PEAK 24 and repeat §9.7. Otherwise §9.8 stands as written.
