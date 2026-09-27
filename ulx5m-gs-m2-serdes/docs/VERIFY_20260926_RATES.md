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

### 9.10 TASK-5073: re-test of the PEAK 24 points vs PROFILE 2 (3 loads × 60 s), and PROFILE 3 (27.09.2026)

**Done by:** Jelena, gs lease `TASK-5073`, fpga-jtag, CFGRST bits. **Raw data:** `data_20260927/t5073/`
(`lab6.sh`/`lab7.sh` exactly as run + `lab6.out`/`lab7.out`, one ber_mon JSON per load + health JSONs).
**Procedure:** as §9.4/§9.5. (a)–(d) = E1 5 G PROFILE 1 bits (gs s7, m2 s1) + JTAG writes on both boards + `eyescan.py recal`;
(e) = PROFILE 2 bits (§9.7), no writes. The 3 loads were **interleaved** (round k runs a, b, c, d, e once), so slow drift
hits every point alike. TX FFE for (b)/(c) = the E3 set (31 post branches, DC 47, no pre-cursor) with SEL_POST 0 / 6.
Table: `ab_table.py --runs --rank` (new: one row per load, and points ranked by median synced share gs→m2, then BER).

Per load (BER while synced; synced share = words / word clock; "–" = corrupted counter):

| Point | load | BER gs→m2 | synced gs→m2 | BER m2→gs* | synced m2→gs* |
|---|---|---|---|---|---|
| (a) GAIN 0 PEAK 24 | r1 / r2 / r3 | 1.14e-1 / 1.08e-1 / 1.10e-1 | 1.4e-1 / 1.1e-2 / 9.0e-3 | 1.85e-1 / 1.80e-1 / 1.76e-1 | 3.0e-2 / 4.9e-2 / 1.5e-2 |
| (b) PEAK 24 + SEL_POST 0 | r1 / r2 / r3 | 1.43e-1 / 1.00e-1 / 0.5 (–) | 6.4e-2 / 1.9e-1 / – | 0.5 / 0.5 / 0.5 | 0 / 4.1e-4 / 1.5e-5 |
| (c) PEAK 24 + SEL_POST 6 | r1 / r2 / r3 | 1.49e-1 / 1.57e-1 / 1.23e-1 | 8.3e-2 / 3.1e-2 / 2.9e-2 | 2.81e-1 / 2.70e-1 / 7.59e-2 | 9.3e-2 / 7.6e-2 / 3.3e-1 |
| (d) PEAK 24 + CKP 0x1E TRANS_TH 16 | r1 / r2 / r3 | 1.09e-1 / 1.11e-1 / 1.08e-1 | 2.9e-2 / 1.7e-1 / 3.6e-2 | 1.89e-1 / 9.68e-2 / 2.97e-2 | 1.6e-2 / 2.9e-1 / 7.1e-1 |
| (e) PROFILE 2 (control) | r1 / r2 / r3 | 5.53e-2 / 6.71e-2 / 7.40e-2 | 1.5e-3 / 1.8e-3 / 1.4e-2 | 1.77e-2 / 1.68e-2 / 2.12e-2 | 1.5e-3 / 1.4e-4 / 2.5e-4 |

Medians, ranked by synced share gs→m2 (× = ratio to (e)):

| Rank | Point | BER gs→m2 med (worst) | BER m2→gs* med (worst) | synced gs→m2 | synced m2→gs* |
|---|---|---|---|---|---|
| 1 | (b) PEAK 24 + SEL_POST 0 | 1.43e-1 (0.5) | 0.5 (0.5) | 1.3e-1 (71×; 2 valid loads) | 1.5e-5 (0.06×) |
| 2 | **(d) PEAK 24 + CKP 0x1E TT 16** | 1.09e-1 (1.11e-1) | 9.68e-2 (1.89e-1) | **3.6e-2 (20×)** | **2.9e-1 (1160×)** |
| 3 | (c) PEAK 24 + SEL_POST 6 | 1.49e-1 (1.57e-1) | 2.70e-1 (2.81e-1) | 3.1e-2 (17×) | 9.3e-2 (370×) |
| 4 | (a) GAIN 0 PEAK 24 | 1.10e-1 (1.14e-1) | 1.80e-1 (1.85e-1) | 1.1e-2 (6.0×) | 3.0e-2 (120×) |
| 5 | (e) PROFILE 2 | **6.71e-2** (7.40e-2) | **1.77e-2** (2.12e-2) | 1.8e-3 | 2.5e-4 |

(* m2→gs is counted by the gs checker, rclk Fmax 41–47 MHz < 62.5 MHz: indicative only, §9 intro.)

Reading:
- **The §9.9 single-load 0.43 for PEAK 24 did not repeat.** (a) gives 9·10⁻³ … 0.14 (median 1.1·10⁻²). The load-to-load
  spread (×15 within (a), ×10 within (e)) is as large as in E1, so single-load ranks in §9.4/§9.5 are not reliable.
- **Every PEAK 24 point has a higher median synced share than PROFILE 2** (gs→m2). Per load: 9 of the 11 valid PEAK 24 loads
  are above the best PROFILE 2 load (1.4·10⁻²); the two below are (a) r2/r3 (1.1·10⁻², 9·10⁻³). For 3 + 3 loads the smallest
  two-sided Mann–Whitney p is 0.10 ((c) and (d) reach it: 3 of 3 above), so this design cannot give a 5 % test.
- **But the BER while synced is ~2× worse at PEAK 24** (gs→m2 0.11 vs 0.067; m2→gs 0.10–0.27 vs 0.018). More peaking
  (PEAK 12) gives fewer errors while locked, less peaking (PEAK 24) keeps the checker locked longer. Neither is near the target.
- (b) SEL_POST 0 ranks first on gs→m2 only because the m2 TX without post-cursor kills m2→gs (synced 0 … 4·10⁻⁴, BER 0.5 in
  3/3) and r3 had a corrupted counter. It is excluded. The ≥ 10× rule of §9.9 holds in **both** directions only for **(d)** and
  (c). (a) misses it in gs→m2 (6.0×). So the rule "(a)–(d) all ≥ 10×" is **not** met literally. It is met by the best
  point, and PEAK 24 is common to all four, so the rebuild was done on (d).

**PROFILE 3 in the bitstream (instead of changing PROFILE 2).** PROFILE 3 = PROFILE 1 + CDR CKP 0x1E TRANS_TH 16 = point (d).
PROFILE 1 already has AFE GAIN 0 PEAK 24 (0x18) and TX FFE pre/post 5 of 12, so (d) is PROFILE 1 + the E4 CDR values.
A PEAK 24 + SEL_POST 12 variant ("PROFILE 2 on PEAK 24" literally) was never measured, and SEL_POST 12 came from the PEAK 12 base.
PROFILE 2 stays unchanged so that §9.7 can be rebuilt from the source (`ber_top.v`, VER byte 0xB5 for PROFILE 3).
Build: `FREQ=65 [LINK=ber_link_gs.v] build_ber.sh <b> p3_5g_txneg <seed> N1 1 N2 5 N3 5 OUTDIV 1 TX_NEG 1 PROFILE 3`;
m2 s1 rclk 62.82 MHz (≥ 62.5), gs s7 rclk 44.71 MHz (seeds 1–6: 41.2–47.1 MHz, same band as §9). Bits:
`bitstreams/ber_{gs,m2}_5g_p3_txneg_CFGRST.bit` (md5 16f5e73a…, 06b750b8…). No JTAG writes.

| Run | BER gs→m2 | synced gs→m2 | BER m2→gs* | synced m2→gs* |
|---|---|---|---|---|
| `t73f_p3_300s` (1 load, 300 s) | 1.18e-1 | 5.0e-3 (PROFILE 2 300 s §9.7: 1.7e-3 → **3×**) | 2.01e-1 | 1.7e-4 (§9.7 300 s: 1.4e-5 → 12×) |
| `t73f_p3_60s` 3 loads, median (worst) | 1.04e-1 (1.10e-1) | 3.2e-2 (18× (e)) | 1.68e-1 (1.76e-1) | 9.3e-3 (37× (e)) |

Fabric-independent check (`ber_jtag_check.py --samples 200`, PROFILE 3): **m2 182/200 PEER (9 % bad), gs 165/200 (17.5 % bad)**,
vs PROFILE 2 187/200 (6.5 %) and 195/200 (2.5 %) in §9.7. The raw PCS words are worse with PEAK 24, which matches the higher BER.

**Conclusion TASK-5073.**
1. The synced-share gain of PEAK 24 is real but smaller than §9.9 suggested: ×17–20 in gs→m2 at 60 s for (c)/(d)/PROFILE 3, ×3
   at 300 s. It is paid for with ~2× the conditional BER and 1.4–7× more bad raw RX words. No point leaves 10⁻² … 10⁻¹.
2. §9.8 item 1 stands: **5 Gb/s is not reachable by register tuning on this setup.** The trade-off
   "locked longer ↔ fewer errors while locked" between PEAK 12 and PEAK 24 is consistent with an eye that is closed at both
   settings, not with a better equaliser setting that we missed.
3. For the next step (E9/H2 supply noise, H3 channel, H4 refclk; Goran, hardware) use **both** PROFILE 2 and PROFILE 3 as the
   5 G reference, and judge a hardware change by the **3-load median of synced share AND BER** (`ab_table.py --runs --rank`).
   A hardware fix should move both in the same direction. A register change so far only moves one against the other.
4. `ab_table.py`: `--runs` (per-load rows), `--rank` (synced share gs→m2, then BER), and the pooled bit count no longer adds
   corrupted counters (was 6.2·10¹⁴ bits for (b)). Tests: 60 pass (`python3 -m unittest discover -s tools/tests`).

## 10. TASK-5078: A/B after the 1 µF capacitors on GS (E9/H2), 27.09.2026

**Change (Goran, 27.09. 15:54):** 1 µF in parallel to C128 (VDD_SER), C127 (VDD_SER_PLL) and C42 (VDD_PLL, fabric PLLs) on
**GS only**; M2 not touched. Pass criterion (TUNING_5G.md E9/H2): ≥ 3× lower BER. **Done by:** Jelena, gs lease `TASK-5078`,
fpga-jtag, SRAM `-r`, no power-cycle. **Bits = the baseline bits**: sha256 checked on the Pi before loading
(`gs_sd_2g5p1_txneg_s7` 36f09752…, `m2_e1_2g5p1_txneg_s2` b1b98a5d…, PROFILE 2 bec33f07…/ac8132bd…, PROFILE 3 074d2d54…/0f638565…),
all six `CFGRST` (`gm_cfgrst_check.py`). **Raw data:** `data_20260927/t5078/` (`lab8.sh`/`lab8.out` as run, ber_mon + health
JSONs, `diag_16h20.txt`); DVI part in `../ulx5m-gs-linux-sbc/docs/data_20260927/t5078/`. New tool: `tools/lab/health_table.py`
(0x55 PLL flags + CDR/EQA per load and per point; test `test_health_table.py`, suite 63 pass).

### 10.1 SerDes: the GS↔M2 link is down — not measurable, and not because of the capacitors

The 2.5 G best pair (§9.3/§9.7) gave **no sync at all** in both directions in 2 of 2 loads × 300 s (0 words, BER 0.5). The run was
stopped and the link checked without the fabric checkers:

| Check | Baseline (same bits) | After the caps (27.09. 16:00–16:20) |
|---|---|---|
| ber_mon 2.5 G, 300 s, words gs→m2 / m2→gs | 9.4·10⁹ / 9.4·10⁹, BER 4.7·10⁻¹⁰ … 1.2·10⁻⁸ / 1.6·10⁻¹¹ … 4.5·10⁻⁸ | **0 / 0** (r1, r2) |
| `ber_jtag_check` RX words (JTAG regfile) 2.5 G | 200/200 PEER on both (§9.7) | **ZERO 50/50 on both** |
| same at **0.3 G** and **1.25 G** (repo bits `ber_*_0g3`, `ber_*_1g25`) | 0 errors in 1.1·10⁹ words (§8, TASK-5055) | **ZERO 50/50 on both, both rates** |
| TX word rate m2 − gs (one shared 100 MHz refclk) | **0.0 ppm** (26.09. and 27.09.) | **−9.0 / −7.6 ppm**, drifting |
| m2 SerDes PLL `PLL_CAP_FT` (0x55) | 506–517, FT_OF 0 | **842–1007, FT_OF = 1** in r1 |
| gs SerDes PLL `PLL_CAP_FT` (0x55), FT_OF/UF | 433–440, 0/0 | 432–435, 0/0 (unchanged) |
| gs RX: CDR lock / `RX_DETECT_DONE` / `RX_TH_MON` | 1 / 1 / 15 | 0 / 0 / 0 in 3 of 3 loads |

Reading:
- M2 no longer gets the **shared refclk**: its TX rate differs from GS by ~8 ppm (it was 0.0) and its PLL fine-tune sits far off
  (842–1007 vs ~510, overflow flag). M2's refclk and both lanes run the same path GS → CM4 IO board → PCIe slot →
  PCIe→M.2 adapter → M2 (`VERIFY_20260926.md` K5). Losing the refclk **and** all data in both directions at every rate, including
  0.3 G, points at that path (not seated / disturbed while GS was reworked), not at supply noise.
- GS itself is fine at the SerDes PLL: locked, CAP_FT as before, rate exactly as before. The capacitors are on supply rails, not
  on the refclk or the lanes, and M2 was not touched, so they cannot remove M2's refclk.
- **Open (needs Goran at the board):** reseat the GS → PCIe slot → M.2 adapter → M2 chain (and check that nothing was bridged near
  C127/C128/C129/C130 on GS). Then re-run `lab8.sh` unchanged (2.5 G 3 × 300 s; 5 G PROFILE 2 + PROFILE 3, 3 × 60 s interleaved + 300 s,
  `ber_jtag_check` 200) — the E9/H2 verdict for SerDes is **not yet known**.

### 10.2 DVI / fabric PLLs (C42 on VDD_PLL): the lock drops under SDRAM load are gone

Same procedure as the TASK-5047 baseline (`ab3.sh`, `SBC_DVI_USB_TASK-5047.md` §2.4): BIOS → test image → re-arm STDY → 20 s idle →
2 × `mem_test` 32 MiB at 0x41000000 with 30 grabber snapshots → counters (`main_pll_sys_unlocks`/`tx_unlocks`/`stdy` from 0xf000280c,
`main_video_recoveries` 0xf0002800). Script `ab_dvi.sh` = `ab3.sh` with fpga-jtag and the gs by-id console. Same bit as the baseline
(`…DVI_lr0_rec3.bit`, sha256 1ee3ba40…, CFGRST).

| Build / run | idle 20 s sys / tx drops | 2 × mem_test 32 MiB: sys / tx drops | STDY after load | recoveries | Memtest |
|---|---|---|---|---|---|
| grec_3 **baseline** (25.09., TASK-5047) | +0 / +3 | **+8930 / +43 333** | 0x0 | 0 | OK |
| TASK-5040 reference (dvipll_1, 8 MiB) | +0 / +0 | +3787 / +2665 | – | – | OK |
| grec_3 after caps, r1 | +0 / +0 | **+0 / +0** | 0x3 | 0 | OK |
| grec_3 after caps, r2 | +0 / +0 | **+22 / +0** | 0x2 | 0 | OK |
| pll60 s1 (`…USBPNRU_pll60s1.bit`, 9aeda4dc…) after caps | +0 / +0 | **+0 / +0** | 0x3 | 0 | OK |

(Video frame counter advanced by ~11 000 frames per run in all three, so the video path was running.)
- **≥ 400× fewer sys PLL drops and 0 tx (video) PLL drops** (from 43 333) with the identical bit and test. This confirms hypothesis
  **P1** of `SBC_DVI_USB_TASK-5047`/TASK-5040 §8–§9 (VDD_CORE noise into VDD_PLL through R23 1 Ω + C42 100 nF) as the main path; P2
  (+1V8 → Y1) cannot be the main cause, since only VDD_PLL was changed. The few sys drops in r2 are a small residue.
- **Image not verified:** the HDMI grabber returned a uniform (7,7,7) frame in all 99 snapshots, the same as with the known-good
  bit in TASK-5072 (grabber/HDMI chain), so image stability under load needs a look at the monitor.
- Linux 6.12 boot on pll60 s1 was not repeated; the BIOS stress test is the one with a baseline.

### 10.3 Before / after

| Item | Before | After 1 µF on GS | Verdict |
|---|---|---|---|
| 2.5 G BER (best pair) | 4.7·10⁻¹⁰ … 1.2·10⁻⁸ / 1.6·10⁻¹¹ … 4.5·10⁻⁸ | link down (0 words; M2 lost refclk) | **not measurable** – setup fault |
| 5 G PROFILE 2 / 3 | 6.3·10⁻² / 2.0·10⁻² (P2 300 s) | not run (link down) | **not measurable** |
| fabric PLL drops, 2 × mem_test | +8930 / +43 333 | +0…22 / +0 | **better (≥ 400×)** |
| DVI watchdog recoveries | 0 | 0 | same |

### 10.4 TASK-5079: the chain reseated (Goran 27.09. 16:40) — SerDes A/B measured, DVI image checked

**Done by:** Jelena, gs lease `TASK-5079`, fpga-jtag, CFGRST bits, SRAM `-r`, no power-cycle. **Raw data:** `data_20260927/t5079/`
(`h79.sh`/`h79.out` health check, `lab9.sh` = `lab8.sh` of §10 with only lease/log/labels renamed, `lab9.out`, ber_mon + health
JSONs); DVI in `../ulx5m-gs-linux-sbc/docs/data_20260927/t5079/`. Bits checked by sha256 in `lab9.out` (same six as §10).

**Health first (the §10.1 fault is gone):**

| Check | §10.1 (link down) | 27.09. 16:48 after reseat | Baseline |
|---|---|---|---|
| TX word rate m2 − gs at 2.5 G | −9.0 / −7.6 ppm | **0.0 ppm** (health run + all 3 lab loads) | 0.0 ppm |
| m2 `PLL_CAP_FT` / FT_OF | 842–1007 / 1 | **506–509 / 0** (2.5 G), 513–517 / 0 (5 G) | 506–517 / 0 |
| gs `PLL_CAP_FT` / FT_OF | 432–435 / 0 | 434–440 / 0 | 433–440 / 0 |
| `ber_jtag_check` 0.3 G, m2 / gs | ZERO 50/50 | **PEER 200/200 / 200/200** | 200/200 |
| `ber_jtag_check` 2.5 G, m2 / gs | ZERO 50/50 | **PEER 200/200 / 200/200** | 200/200 (§9.7) |

**2.5 Gb/s, best pair (gs `TX_NEG` s7 + m2 s2), 3 loads × 300 s** (`ab_table.py --runs --rank`):

| Load | BER gs→m2 | BER m2→gs* | synced share |
|---|---|---|---|
| before the caps: `sd_gs7_m22` (26.09.) | 4.68·10⁻¹⁰ | 1.58·10⁻¹¹ | 1.00 |
| before the caps: `best_2g5_gs7_m22` (27.09.) | 1.21·10⁻⁸ | 4.54·10⁻⁸ | 0.97 |
| **after: t79 r1** | 6.87·10⁻¹⁰ | 2.55·10⁻¹⁰ | 1.00 |
| **after: t79 r2** | 4.29·10⁻¹⁰ | 8.00·10⁻¹² | 0.96 |
| **after: t79 r3** | 5.97·10⁻¹⁰ | 1.33·10⁻¹¹ | 0.96 |

| | gs→m2 | m2→gs* |
|---|---|---|
| before: geometric mean of 2 loads / worst | 2.4·10⁻⁹ / 1.2·10⁻⁸ | 8.5·10⁻¹⁰ / 4.5·10⁻⁸ |
| after: median of 3 / worst | 6.0·10⁻¹⁰ / 6.9·10⁻¹⁰ | 1.3·10⁻¹¹ / 2.6·10⁻¹⁰ |
| ratio (before / after): typical, worst | **4×, 17×** | **65×, 180×** |
| spread between loads (max / min) | ×26 → **×1.6** | ×2900 → **×32** |

(* m2→gs is counted by the gs checker, rclk below 62.5 MHz: indicative only, §9 intro.)

**5 Gb/s, PROFILE 2 and PROFILE 3, 3 loads × 60 s interleaved + 1 × 300 s:**

| Point | BER gs→m2 med (worst) | BER m2→gs* med (worst) | synced gs→m2 / m2→gs* med | `ber_jtag_check` 200 m2 / gs |
|---|---|---|---|---|
| P2 before (§9.7 `e8_p2_60s`) | 7.3·10⁻² (9.9·10⁻²) | 1.8·10⁻² (2.9·10⁻²) | 1.3·10⁻³ / 3.8·10⁻⁴ | 187 / 195 PEER |
| **P2 after** | 4.9·10⁻² (5.3·10⁻²) | 2.0·10⁻² (3.3·10⁻²) | 8.1·10⁻⁴ / 3.4·10⁻⁴ | 181 / 192 PEER |
| P2 300 s before → after | 6.3·10⁻² → 5.9·10⁻² | 2.0·10⁻² → 2.7·10⁻² | 1.7·10⁻³ → 8.7·10⁻⁵ | |
| P3 before (§9.10 `t73f_p3_60s`) | 1.04·10⁻¹ (1.10·10⁻¹) | 1.68·10⁻¹ (1.76·10⁻¹) | 3.2·10⁻² / 9.3·10⁻³ | 182 / 165 PEER |
| **P3 after** | 6.2·10⁻² (6.5·10⁻²) | 1.01·10⁻¹ (1.07·10⁻¹) | 8.1·10⁻³ / 3.1·10⁻⁴ | 183 / 182 PEER |
| P3 300 s before → after | 1.18·10⁻¹ → 6.4·10⁻² | 2.01·10⁻¹ → 9.5·10⁻² | 5.0·10⁻³ → 9.1·10⁻⁵ | |

Health at 5 G: all PLLs locked, FT_OF/UF 0 on both boards in every load. The RX CDR lock flag in the snapshot before each run
was set in 1 of 8 loads on gs (baseline §9.7 + §9.10: 1 of 8, so no change) and in **5 of 8 on m2** (baseline: 0 of 8). The 5 G rate counter shows m2 − gs −1…−11 ppm, and the baseline showed −1…−42 ppm. At 5 G the fabric
rclk is too slow for this counter, so these numbers are not a refclk fault.

Reading (E9/H2 criterion: ≥ 3× lower BER and/or a smaller spread between loads):
- **2.5 G: better, and the criterion is met in both directions.** The typical value is 4× / 65× lower, the worst load 17× / 180×
  lower, and the load-to-load spread dropped from ×26 / ×2900 to ×1.6 / ×32. All 3 loads are at or below the best load before
  the caps. Caveat: the baseline for this exact pair has only 2 loads, so the size of the gain is uncertain. The direction is
  not in doubt: the worst load after the caps is below the geometric mean before them.
- **5 G: the same, within the noise.** The BER while synced is 1.5–2× lower (P3 gs→m2 1.7×, P3 m2→gs 1.7×, P2 gs→m2 1.5×,
  P2 m2→gs unchanged), which is below the 3× threshold and within the ×10–15 load spread of §9.10. The synced share did not
  improve; in the 300 s runs it is lower. The raw RX words (`ber_jtag_check`) are unchanged for P2 and better on gs for P3
  (165 → 182/200). 5 G is still not usable (10⁻² … 10⁻¹).
- So the 1 µF on the GS SerDes supplies (C127/C128) removed most of the load-to-load lottery at 2.5 G. At 5 G it did not
  change the result, which is limited by something else (M2 side still without the caps, the channel H3, or the refclk H4).
  Next step (Goran, 27.09. 18:43): the same 1 µF on **M2** C127/C128, then the health check + `lab9.sh` again.

**DVI (pll60 s1, `…USBPNRU_pll60s1.bit` 9aeda4dc…), with the grabber working again:**

| Test | Image on the grabber (:8090) | Lock drops sys / tx | recoveries | Other |
|---|---|---|---|---|
| BIOS, `ab_dvi.sh` (§10.2 procedure), 20 s idle + 2 × mem_test 32 MiB | **33/33 snapshots = the test image** (8 colour bars, 0 pixels differ by > 40 from t0) | idle +0/+0, load **+0 / +0** | 0 | Memtest OK, ~11 100 frames |
| Linux 6.12 (`linux/k612`, sha256 of all 4 files = README), `lxrun.sh` as user `pi` | kernel log, then `buildroot login:` on tty1 (73 snapshots) | at 217 s up: 921 / 465 (boot + TFTP) | 0 | **login after 266 s** (same as `README`) |
| Linux, idle shell, 62 s | stable | **+85 / +54** (≈ 1.4 / 0.9 per s) | 0 | `S92sbcdiag`: vrec 0 all the time |
| Linux, SDRAM stress: `dd` 24 MiB to tmpfs, then `md5sum` 4 × 24 MiB | **86/86 snapshots identical** (0 changed 10×10 blocks, 6 min) | not read after the stress (see below) | 0 (`diag` lines) | |

- **The image is there and stable**, in BIOS and in Linux, under SDRAM load. The TASK-5078 7,7,7 frames were the grabber/HDMI
  path. Goran reconnected it, and the grabber now shows the picture (`snaps/*.jpg`).
- **New finding, Linux only:** the PLL lock-drop counters keep counting under Linux (≈ 1.4 sys / 0.9 tx per second in an idle shell,
  +26 700 / +18 000 between 217 s and 1155 s up, which included the `dd`). The BIOS test on the same bit gives +0/+0. There is
  **no Linux baseline from before the caps**: every earlier DVI A/B was BIOS-only. So this is not a regression claim. It shows
  that Linux load (CPU + Ethernet + USB + fbcon) still upsets the PLL lock signal, even though the video watchdog never had to
  recover and the image did not change.
- **Not done:** counters after the `md5sum` stress. The prompt had not come back after about 18 min (slow soft CPU; the serial
  console is slow and drops characters). Then Goran stopped all board work at 18:43 to solder M2, so the counters were
  not read.
- Two lab traps: (1) `/tmp/lx_run.txt` on the Pi belongs to `pi`. Running `lxrun.sh` as `fpga-klaudio` reads a stale file and
  reports "LOGIN after 5 s" (run discarded, `lx612/invalid_fpga-klaudio/`), so run it as `pi`. (2) `csrpeek ADDR N INTERVAL COUNT`
  hangs, because `sys_ms()` returns 0 on this rootfs. Read the counters twice by hand instead.
- The Pi dropped off the network twice (17:14–17:23 and ~18:15–18:29) with `Under-voltage detected` in dmesg. It did not reboot
  (up since 26.09. 11:30), and every lab run finished locally. Goran switched Wi-Fi off at 18:34.

| Item | Before 1 µF on GS | After (§10.4) | Verdict |
|---|---|---|---|
| 2.5 G BER, best pair (typ. / worst) | 2.4·10⁻⁹ / 1.2·10⁻⁸ ; 8.5·10⁻¹⁰ / 4.5·10⁻⁸ | 6.0·10⁻¹⁰ / 6.9·10⁻¹⁰ ; 1.3·10⁻¹¹ / 2.6·10⁻¹⁰ | **better (4–180×), E9/H2 met** |
| 2.5 G spread between loads | ×26 / ×2900 | ×1.6 / ×32 | **better** |
| 5 G P2 / P3 BER (60 s median) | 7.3·10⁻² / 1.04·10⁻¹ (gs→m2) | 4.9·10⁻² / 6.2·10⁻² | **same (< 3×)** |
| DVI image under SDRAM load | not seen (grabber) | stable, BIOS 33/33 and Linux 86/86 | **OK** |
| fabric PLL drops, BIOS 2 × mem_test | +8930 / +43 333 | +0 / +0 | **better** (§10.2 confirmed) |

### 10.5 TASK-5080/5082/5084: 2.2 µF added on M2 C127/C128 (Goran 27.09. ~19:00) — lab10 = `lab9.sh` again

**Done by:** Jelena, gs lease `TASK-5080`, same six bits as §10.4 (sha256 in `lab10.out`), CFGRST, SRAM `-r`, no power-cycle.
**Raw data:** `data_20260927/t5080/` (`h80.sh`/`h80.out` first health check, `h81.out` second one, `lab10.sh` = `lab9.sh` with only
lease/log/labels renamed, `lab10.out`, `log5080/*.json`). lab10 ran 19:42:27–20:20:07 and removed `gs.owner` itself.

**Timeline, because it matters for the reading.** 19:04 first health check (`h80.out`): gs did not answer on JTAG
("TDO is stuck at 0"), m2 RX ZERO 200/200. Goran fixed the gs side, and the second check at 19:38 (`h81.out`) was clean again:
`ber_jtag_check` PEER 200/200 on both boards at 0.3 G and 2.5 G, m2 − gs 0.0 ppm, 30 s at 2.5 G gs→m2 4.1·10⁻⁹ / m2→gs 1.4·10⁻¹⁰.
lab10 started 4 min later. So r1 ran about 5–10 min after gs came back; in §10.4 r1 started 13 min after the health check.

**Three columns** (2.5 G: best pair gs `TX_NEG` s7 + m2 s2, 300 s per load; 5 G: 60 s median of 3 loads, worst in brackets):

| Point | no caps (§10.4 "before") | GS 1 µF only (§10.4, t79) | **GS 1 µF + M2 2.2 µF (t80)** |
|---|---|---|---|
| 2.5 G gs→m2, typical / worst | 2.4·10⁻⁹ / 1.2·10⁻⁸ | 6.0·10⁻¹⁰ / 6.9·10⁻¹⁰ | **9.5·10⁻⁹ / 2.3·10⁻⁸** |
| 2.5 G m2→gs*, typical / worst | 8.5·10⁻¹⁰ / 4.5·10⁻⁸ | 1.3·10⁻¹¹ / 2.6·10⁻¹⁰ | **1.7·10⁻⁸ / 9.4·10⁻⁸** |
| 2.5 G per load r1 / r2 / r3, gs→m2 | 4.7·10⁻¹⁰ ; 1.2·10⁻⁸ (2 loads) | 6.9 / 4.3 / 6.0 ·10⁻¹⁰ | **7.5·10⁻¹⁰ / 9.5·10⁻⁹ / 2.3·10⁻⁸** |
| 2.5 G per load r1 / r2 / r3, m2→gs* | 1.6·10⁻¹¹ ; 4.5·10⁻⁸ (2 loads) | 2.6·10⁻¹⁰ / 8.0·10⁻¹² / 1.3·10⁻¹¹ | **1.4·10⁻⁹ / 1.7·10⁻⁸ / 9.4·10⁻⁸** |
| 2.5 G spread between loads gs→m2 / m2→gs | ×26 / ×2900 | ×1.6 / ×32 | **×31 / ×68** |
| 2.5 G synced share | 1.00 ; 0.97 | 1.00 / 0.96 / 0.96 | 1.00 / 0.97 / 0.97 |
| 5 G P2 gs→m2 / m2→gs* | 7.3·10⁻² / 1.8·10⁻² | 4.9·10⁻² / 2.0·10⁻² | **5.0·10⁻² (5.2·10⁻²) / 2.4·10⁻² (2.7·10⁻²)** |
| 5 G P3 gs→m2 / m2→gs* | 1.04·10⁻¹ / 1.68·10⁻¹ | 6.2·10⁻² / 1.01·10⁻¹ | **6.6·10⁻² (6.6·10⁻²) / 7.3·10⁻² (7.3·10⁻²)** |
| 5 G 300 s P2 / P3, gs→m2 | 6.3·10⁻² / 1.18·10⁻¹ | 5.9·10⁻² / 6.4·10⁻² | 5.2·10⁻² / 7.7·10⁻² |
| 5 G synced share P2 / P3 (gs→m2 ; m2→gs*) | 1.3·10⁻³ ; 3.8·10⁻⁴ / 3.2·10⁻² ; 9.3·10⁻³ | 8.1·10⁻⁴ ; 3.4·10⁻⁴ / 8.1·10⁻³ ; 3.1·10⁻⁴ | 1.3·10⁻⁴ ; 2.4·10⁻³ / 8.8·10⁻⁴ ; 8.1·10⁻⁴ |
| `ber_jtag_check` 200 m2 / gs, P2 ; P3 | 187 / 195 ; 182 / 165 | 181 / 192 ; 183 / 182 | 185 / 192 ; 185 / 177 |

(* m2→gs is counted by the gs checker, rclk below 62.5 MHz: indicative only, §9 intro.)

**Why r1 → r3 grows (2.5 G) — what the data shows and what it rules out:**

| Candidate | Evidence (file) | Verdict |
|---|---|---|
| refclk / rate offset (ppm) | TX word rate 2 500 019 200 b/s on **both** boards in all 3 loads, m2 − gs **0.0 ppm** (`t80_2g5_*_r?.json`); §10.4: 2 500 019 440–520, also 0.0 | **ruled out** |
| `PLL_CAP_FT` drift / PLL lock | `health_table.py`: gs 436 / 433 / 434, m2 509 / 509 / 506, FT_OF/UF 0/3, PLL lock 3/3 on both. §10.4: gs 436–437, m2 506–509. The ±3 codes do not follow the BER. | **ruled out** |
| RX CDR / EQA | CDR lock 3/3 and EQA lock 3/3 on both boards; CDR phase-accumulator span gs 558 / 775 / 139, m2 108 / 108 / 248 (no trend; §10.4: 357–542 / 171–248) | **ruled out** as a register-visible cause |
| Pi supply dips | `Under-voltage` in dmesg at 19:47:53–19:48:08, 19:53:16–19:53:33, 19:58:40 = while the **next bitstream was loading**, not during a BER count; same pattern as in §10.4 | **not the cause** of the BER count |
| link loss / resync | `loss 0` in every load; synced share 1.00 / 0.97 / 0.97 (§10.4: 1.00 / 0.96 / 0.96) | **ruled out** |
| error shape | errored words gs→m2 101 → 1611 → 3159 (2.8 / 2.2 / 2.7 bits per word); m2→gs 326 → 3407 → 946 (1.6 / 1.9 / **37** bits per word). In §10.4 both directions had 3–81 errored words per load. | more **random single-bit errors in both directions at once** (r2), plus a burst component in m2→gs r3 |
| temperature | no temperature sensor in the data; no FPGA die temperature is read | **cannot be checked** from this data |

What that leaves: the growth is **in both directions at the same time**, while every PLL/CDR/refclk register stays where it was.
That points to amplitude noise/jitter on a supply both directions share, not to a frequency or lock problem. The M2 SerDes
supply is shared by M2's TX (m2→gs) and M2's RX (gs→m2), and M2 C127/C128 is the only hardware change since §10.4, so a
problem at the new joints is **consistent** with the data. It is not proven: the r1 value (7.5·10⁻¹⁰ / 1.4·10⁻⁹) is close to
the GS-only result, and this is one session of three loads, directly after a gs repair. A slow warm-up after that repair would
produce the same monotonic trend, and we have no temperature to tell the two apart.

**5 G is unchanged** by the M2 caps: all points are within 1.0–1.4× of the GS-only column, and there is no trend from round 1 to
3 (P2 gs→m2 5.0 / 4.1 / 5.2·10⁻²). That is expected: at 10⁻² … 10⁻¹ the 5 G link is limited by something else (§10.4), and a
supply-noise increase that moves 2.5 G from 10⁻¹⁰ to 10⁻⁸ is invisible there.

**Verdict:**

| Item | GS 1 µF only (§10.4) | + M2 2.2 µF (§10.5) | Verdict |
|---|---|---|---|
| 2.5 G BER typical gs→m2 / m2→gs | 6.0·10⁻¹⁰ / 1.3·10⁻¹¹ | 9.5·10⁻⁹ / 1.7·10⁻⁸ | **worse** (×16 / ×1300), and worse than no caps (×4 / ×20) |
| 2.5 G spread between loads | ×1.6 / ×32 | ×31 / ×68, monotonic r1 < r2 < r3 | **worse**, and it is a trend, not a lottery |
| 5 G P2 / P3 | 4.9·10⁻² / 6.2·10⁻² (gs→m2) | 5.0·10⁻² / 6.6·10⁻² | **same** |
| registers, ppm, CAP_FT, CDR, loss | clean | clean | **same** — the cause is not register-visible |

**One check for Goran (multimeter, no scope needed):** with the 2.5 G bit loaded on M2, measure DC on M2 **TP10 (`VDD_SER`)**,
**TP8 (`VDD_SER_PLL`)** and `VDD_CORE` (any core decoupling cap), then again after 10 min. Expected with R105/R106 = 1 Ω:
TP10/TP8 ≈ 30–50 mV below VDD_CORE (≈ 1.05 V at J3 = 2-3), stable. TP ≈ VDD_CORE means R105/R106 are 0 Ω (Goran's suspicion).
TP more than ~100 mV below VDD_CORE, or drifting down while the board warms, means leakage or a partial short at the new
C127/C128 joints → reflow or remove the 2.2 µF and rerun `lab10.sh` (38 min). If the DC readings are normal, the next step is to
rerun `lab10.sh` unchanged after the boards have been powered for ≥ 30 min, to separate "worse with the M2 caps" from
"warm-up after the gs repair".
