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

### 10.6 TASK-5085: rerun after Goran's change at 20:38 (GND wire?) — lab10 again, unchanged

**What changed:** Goran 27.09. 20:38 "neka testira ponovno", after REGOČ's proposal at 20:28 (a short, thick GND wire directly
GS↔M2, because the FFC carries only 4 GND pins, M2 is probably powered through the FFC 5 V, and the DirtyJTAG USB cables are a
second ground path/loop). The exact change was not stated; it is recorded here as **"Goran's change 20:38 (GND wire?)"**.
The M2 2.2 µF (C127/C128) and GS 1 µF from §10.4/§10.5 stay on.

**Done by:** Jelena, gs lease `TASK-5085`, same six bits (sha256 in `lab10_5085.out`, identical to §10.5), CFGRST, SRAM `-r`,
no power-cycle. **Raw data:** `data_20260927/t5085/` (`h85.sh`/`h85.out` health, `lab10_5085.sh` = `lab10.sh` with only
lease/log dir/labels renamed `t80`→`t85`, `lab10_5085.out`, `log5085/*.json`). Health 20:40–20:43, lab 20:44:07–21:21:36,
`gs.owner` removed by the script.

**Health (h85):** `ber_jtag_check` PEER 200/200 on both boards at 0.3 G and 2.5 G; 2.5 G TX word rate 2 500 019 360 b/s on both,
m2 − gs **0.0 ppm**; `PLL_CAP_FT` m2 508 / gs 433, FT_OF/UF 0; 30 s `ber_mon` gs→m2 8.2·10⁻⁹, m2→gs 0 (< 6.9·10⁻¹¹).

**Four columns** (2.5 G: best pair gs `TX_NEG` s7 + m2 s2, 300 s per load; 5 G: 60 s median of 3 loads, worst in brackets):

| Point | no caps (§10.4 "before") | GS 1 µF (§10.4, t79) | + M2 2.2 µF (§10.5, t80) | **+ Goran's change 20:38 (t85)** |
|---|---|---|---|---|
| 2.5 G gs→m2, typical / worst | 2.4·10⁻⁹ / 1.2·10⁻⁸ | 6.0·10⁻¹⁰ / 6.9·10⁻¹⁰ | 9.5·10⁻⁹ / 2.3·10⁻⁸ | **5.5·10⁻⁹ / 9.5·10⁻⁹** |
| 2.5 G m2→gs*, typical / worst | 8.5·10⁻¹⁰ / 4.5·10⁻⁸ | 1.3·10⁻¹¹ / 2.6·10⁻¹⁰ | 1.7·10⁻⁸ / 9.4·10⁻⁸ | **2.5·10⁻¹⁰ / 4.5·10⁻⁸** |
| 2.5 G r1 / r2 / r3, gs→m2 | 4.7·10⁻¹⁰ ; 1.2·10⁻⁸ (2 loads) | 6.9 / 4.3 / 6.0 ·10⁻¹⁰ | 7.5·10⁻¹⁰ / 9.5·10⁻⁹ / 2.3·10⁻⁸ | **5.5·10⁻⁹ / 9.5·10⁻⁹ / 2.2·10⁻⁹** |
| 2.5 G r1 / r2 / r3, m2→gs* | 1.6·10⁻¹¹ ; 4.5·10⁻⁸ (2 loads) | 2.6·10⁻¹⁰ / 8.0·10⁻¹² / 1.3·10⁻¹¹ | 1.4·10⁻⁹ / 1.7·10⁻⁸ / 9.4·10⁻⁸ | **4.5·10⁻⁸ / 2.5·10⁻¹⁰ / 4.5·10⁻¹¹** |
| 2.5 G spread between loads gs→m2 / m2→gs | ×26 / ×2900 | ×1.6 / ×32 | ×31 / ×68 | **×4.4 / ×1000** |
| 2.5 G errored words r1/r2/r3 gs→m2 ; m2→gs | – | 3–81 per load | 101/1611/3159 ; 326/3407/946 | 895/1173/384 ; 6430/54/14 |
| 2.5 G bits per errored word, m2→gs | – | – | 1.6 / 1.9 / **37** | 2.7 / 1.8 / 1.2 |
| 2.5 G synced share | 1.00 ; 0.97 | 1.00 / 0.96 / 0.96 | 1.00 / 0.97 / 0.97 | 1.00 / 0.98 / 0.98 |
| 5 G P2 gs→m2 / m2→gs* | 7.3·10⁻² / 1.8·10⁻² | 4.9·10⁻² / 2.0·10⁻² | 5.0·10⁻² / 2.4·10⁻² | **4.7·10⁻² (4.9·10⁻²) / 2.4·10⁻² (2.5·10⁻²)** |
| 5 G P3 gs→m2 / m2→gs* | 1.04·10⁻¹ / 1.68·10⁻¹ | 6.2·10⁻² / 1.01·10⁻¹ | 6.6·10⁻² / 7.3·10⁻² | **5.8·10⁻² (7.2·10⁻²) / 1.03·10⁻¹ (1.18·10⁻¹)** |
| 5 G 300 s P2 / P3, gs→m2 | 6.3·10⁻² / 1.18·10⁻¹ | 5.9·10⁻² / 6.4·10⁻² | 5.2·10⁻² / 7.7·10⁻² | 2.9·10⁻² / 0.5† (robust 8.1·10⁻²) |
| `ber_jtag_check` 200 m2 / gs, P2 ; P3 | 187 / 195 ; 182 / 165 | 181 / 192 ; 183 / 182 | 185 / 192 ; 185 / 177 | 191 / 199 ; 179 / 181 |

(* m2→gs is counted by the gs checker, rclk below 62.5 MHz: indicative only, §9 intro. † `ab_table.py` caps a corrupted m2
counter at 0.5 (errb > 40·words, `loss 28`); `ber_mon` `ber_robust` over 136 s gives 8.1·10⁻², in line with the 60 s loads.)

**Registers (`health_table.py`), unchanged:** 2.5 G PLL lock 3/3, FT_OF/UF 0/3, CDR 3/3, EQA 3/3 on both boards; CAP_FT gs
433–436, m2 506–509 (§10.5: 433–436 / 506–509); rate m2 − gs 0.0 ppm in all three loads. 5 G: ppm P2 −0.6…−1.2, P3 −6.1…−10.2
(§10.5: −0.6…−1.8 / −4.6…−6.8, so P3's m2 PLL offset is a known property of that profile, not new). Pi `Under-voltage` again only
at bitstream loads (20:49:48, 20:55:05, 21:00:14…, 21:14:23–21:14:58, 21:21:32), not during a 2.5 G count.

**Trend r1 → r3 (warm-up vs ground):**
- §10.5 grew monotonically in **both** directions (×31 / ×68). Here it does **not**: m2→gs **falls** ×1000 (4.5·10⁻⁸ → 2.5·10⁻¹⁰ →
  4.5·10⁻¹¹), gs→m2 goes 5.5 → 9.5 → 2.2·10⁻⁹ with no direction. The growth of §10.5 is therefore **not reproduced**.
- Warm-up does not explain both sessions: this run started with boards already powered for over an hour (health 20:40, gs back
  since 19:38; Goran's change may have needed a power-down — not reported), and its worst load is the **first** one. A pure
  thermal drift would give the same sign in both sessions. The pattern is the load-to-load spread already seen in the "no caps"
  column (×2900), i.e. per-load adaptation/lottery, not a slow drift.
- The m2→gs burst component of §10.5 r3 (37 bits per errored word) is gone: all loads are 1.2–2.7 bits per word, random errors.
- Ground (GND wire?) is **consistent** with the m2→gs improvement (typical ×68 better than §10.5, r3 back at the GS-only level
  4.5·10⁻¹¹), but gs→m2 (= M2 RX) stays ×9 worse than GS-only (5.5·10⁻⁹ vs 6.0·10⁻¹⁰) in all three loads. One session of three
  loads per column cannot separate "ground helped" from "this session's loads were luckier"; the exact change is also unknown.

**Verdict:**

| Item | + M2 2.2 µF (§10.5) | + Goran's change 20:38 (§10.6) | Verdict |
|---|---|---|---|
| 2.5 G gs→m2 typical / worst | 9.5·10⁻⁹ / 2.3·10⁻⁸ | 5.5·10⁻⁹ / 9.5·10⁻⁹ | slightly **better** (×1.7 / ×2.4), still ×9 worse than GS 1 µF only |
| 2.5 G m2→gs typical / worst | 1.7·10⁻⁸ / 9.4·10⁻⁸ | 2.5·10⁻¹⁰ / 4.5·10⁻⁸ | **better** typical (×68), worst unchanged (r1) |
| 2.5 G trend r1 → r3 | monotonic growth both ways | no growth; m2→gs falls | §10.5 growth **not reproduced** — not a warm-up drift |
| 5 G P2 / P3 | 5.0·10⁻² / 6.6·10⁻² | 4.7·10⁻² / 5.8·10⁻² | **same** (5 G is limited elsewhere, §10.4) |
| registers, ppm, CAP_FT, CDR, loss | clean | clean | **same** |

**Next:** the cleanest separation is an A/B on the one variable: rerun `lab10_5085.sh` unchanged with the GND wire removed
(or, if the change was something else, with it undone), same session, no power-cycle. If gs→m2 should return to the 6·10⁻¹⁰ of
§10.4, the M2 2.2 µF on C127/C128 (and the TP10/TP8 vs VDD_CORE check proposed in §10.5) remain the prime suspect for the M2 RX.

## 11. TASK-5089: separate refclks: local X2 on M2, C136/C137 removed (Goran 28.09.2026 ~11:00)

**Change:** on M2 a local 100 MHz LVDS oscillator X2 was fitted and C136/C137 (refclk from GS over the cable) were removed;
C129/C130 stay. GS unchanged (1 µF on C127/C128/C42 since §10.4). Every board now runs from its own oscillator.
Which X2 variant was fitted (1.8 V `511J…` or the 2.5 V `511F…` of the schematic, `LOCAL_REFCLK_M2.md` §3) is not recorded.
**Done by:** REGOČ (daemon autonomy was down because the usage meter failed, so the run was done directly), gs lease `TASK-5089`, fpga-jtag, CFGRST bits, SRAM `-r`,
no power-cycle. **Raw data:** `data_20260928/t5089/` (`log/step1.out` + `step1_cki1_60s.json` = oscillator check; `lab11.sh`/`lab11.out`
= A/B as run, one ber_mon JSON + two health JSONs per load).

### 11.1 Step 1: is X2 on M2 working?

| Check (m2 alone, then both) | Result |
|---|---|
| m2 SerDes PLL, 0.3 G / 1.25 G / 2.5 G bits | `PLL_LOCKED=1`, FT_OF/UF 0/0 at all three; `PLL_CAP_FT` 108 / 492 / 501–508 (2.5 G with the shared clock: 506–517) |
| TX word rate, m2 vs gs at 2.5 G (fabric counters, 7 runs 12:00–12:38) | m2 2 500 024 640 … 2 500 026 160 b/s, gs 2 500 018 480 … 2 500 019 600 b/s → **m2 − gs = +2.5 … +2.7 ppm**, stable (both parts ±30 ppm) |
| cki1 pair right after load, before the SET_ACC pulse | m2 `FREQ_ACC_VAL` 16380–16383 (**rail**), m2 CDR 0 — the start-up trap of `LOCAL_REFCLK_M2.md` §4C |
| after `RX_CDR_SET_ACC_CONFIG` 2 → 0 on both | CDR 1 on both, `FREQ_ACC_VAL` m2 −4…+30, gs −20…+35; `ber_jtag_check` PEER 50/50 on both |

**Verdict: X2 works.** The PLL locks at every rate with CAP_FT close to the shared-clock value, and the offset to GS is +2.6 ppm.

### 11.2 Step 2: 2.5 Gb/s with separate refclks (3 loads × 300 s, interleaved)

`cki1` = best pair + `CDR_CKI=1` (`bitstreams/ber_*_2g5_p1_txneg_cki1_*`); `cki0` = the best pair itself (same bits as the §10.4
reference). After every load the SET_ACC pulse on both boards (harmless with CKI 0).

| Load | cki1 gs→m2 | cki1 m2→gs* | cki0 gs→m2 | cki0 m2→gs* |
|---|---|---|---|---|
| r1 | 1.27·10⁻⁷ (synced 0.38) | 8.2·10⁻⁸ (0.97) | 5.8·10⁻⁹ (0.17) | 5.6·10⁻⁸ (0.98) |
| r2 | 1.18·10⁻⁷ (0.33) | 3.7·10⁻⁸ (0.97) | 6.4·10⁻⁸ (0.98) | 6.1·10⁻⁸ (0.98) |
| r3 | 1.00·10⁻⁷ (0.16) | 1.9·10⁻⁷ (0.98) | 2.7·10⁻⁸ (0.81) | 4.7·10⁻⁸ (0.98) |

| | gs→m2 median (worst) | m2→gs* median (worst) | synced gs→m2 / m2→gs | 
|---|---|---|---|
| **shared clock**, GS 1 µF (§10.4, t79) | **6.0·10⁻¹⁰** (6.9·10⁻¹⁰) | **1.3·10⁻¹¹** (2.6·10⁻¹⁰) | 0.96–1.00 / 0.96–1.00 |
| separate clocks, cki0 | 2.7·10⁻⁸ (6.4·10⁻⁸) | 5.6·10⁻⁸ (6.1·10⁻⁸) | 0.81 / 0.98 |
| separate clocks, cki1 | 1.2·10⁻⁷ (1.3·10⁻⁷) | 8.2·10⁻⁸ (1.9·10⁻⁷) | 0.33 / 0.97 |

(* counted by the gs checker; valid at 2.5 G.) Health: PLL lock, CDR lock and EQA lock 3/3 on both boards in every load, FT_OF/UF 0,
CAP_FT gs 434–437 / m2 505–508.

Reading:
- **2.5 G works with separate clocks, but it is worse than with the shared clock**: gs→m2 ×45 (cki0) … ×200 (cki1), m2→gs ×4000–6000,
  and the M2 checker loses sync (gs→m2 synced share 0.16–0.98 instead of ~1.0). The GS receiver stays synced (0.97–0.98).
- **CKI 0 is not worse than CKI 1 at +2.6 ppm**: the proportional-only CDR follows this small offset. CKI 1 gives ×4 higher gs→m2 BER
  and a lower synced share on M2. So at this offset the integrator is not needed, and it adds its own wander (FREQ_ACC ±30).
- What is new in this setup and could explain the M2-RX-side loss is the **refclk at M2 itself**, not the frequency offset:
  (a) SER_CLK_P/N on M2 still run ~52 mm (2.7 mm F.Cu + ~49 mm B.Cu, 2 vias per line) to the now open pads of C136/C137 at J10:
  an open stub on the X2 output (round trip ≈ 0.6 ns), and with `PLL_REF_RTERM=1` the only termination is at the FPGA;
  (b) VDD_CLK has no decoupling at X2 (nearest C47 100 nF on B.Cu 8.4 mm, C131 2.2 µF 8.9 mm); (c) the X2 supply variant is unknown.
  Both boards' SerDes PLLs lock with normal CAP_FT, so the PLL is not the problem; refclk **jitter** (DS1001: ≤ 1 ps) is the suspect.
  Not measured: no scope on SER_CLK.
- Traps seen: without the SET_ACC pulse the cki1 m2 CDR sits at the FREQ_ACC rail and does not lock (as §4C of `LOCAL_REFCLK_M2.md`).
  The gs DirtyJTAG re-enumerated at 12:38 (Pi `Under-voltage`), so the last gs `ber_jtag_check` failed on the probe, not on the link.

### 11.3 M2 refclk internal termination on/off (Goran 12:45: "try the internal termination; an external one is not an option")

`PLL_REF_RTERM` (0x50[11]) was **1 in every earlier run**, including §11.2. The only internal choice is on/off. `lab12.sh`: best pair, CKI 0,
rterm0 = `PLL_REF_RTERM=0` written on m2 over JTAG right after the load (PLL stays locked, CAP_FT 505–508, readback 0), rterm1 = as loaded;
3 rounds interleaved × 300 s, 12:47–13:21.

| M2 internal refclk termination | gs→m2 median (worst) | m2→gs* median (worst) | synced gs→m2 / m2→gs |
|---|---|---|---|
| **on** (`PLL_REF_RTERM=1`, lab12) | **1.5·10⁻⁸** (9.6·10⁻⁸) | **4.7·10⁻⁸** (4.8·10⁻⁸) | 0.96 / 0.96 |
| on (§11.2 cki0, same bits) | 2.7·10⁻⁸ (6.4·10⁻⁸) | 5.6·10⁻⁸ (6.1·10⁻⁸) | 0.81 / 0.98 |
| off (`PLL_REF_RTERM=0`) | 3.7·10⁻⁷ (7.9·10⁻⁷) | 1.4·10⁻⁶ (3.7·10⁻⁶) | **0.006** / 1.0 |

**Internal termination must stay on.** Off is ×25 (gs→m2) and ×30 (m2→gs) worse, and the M2 receiver is synced only 0.6 % of the
time (one load had the M2 CDR unlocked in the health snapshot). With it on, the separate-clock result is repeatable (two sessions agree),
but still ×25 (gs→m2) and ×3600 (m2→gs) worse than the shared clock. The m2→gs direction (M2 TX, clocked by the M2 refclk) degrades
most, which again points at the M2 refclk itself.

### 11.4 GS: 1 Ω → 5.1 Ω in the VDD_SER and VDD_SER_PLL feeds (R106/R105; Goran, on Patrick Urban's advice), quick check 15:40–15:55

Separate clocks as in §11.2 (X2 on M2), internal termination on, same bits; short runs only (`log/q*`).

| | 2.5 G gs→m2 | 2.5 G m2→gs* | 2.5 G M2 synced | 5 G P2 gs→m2 / m2→gs* | 5 G synced gs→m2 | raw words PEER m2 / gs (5 G) |
|---|---|---|---|---|---|---|
| before (1 Ω; §11.3 on, 3 × 300 s) | 1.5·10⁻⁸ | 4.7·10⁻⁸ | 0.96 | 4.7·10⁻² / 2.4·10⁻² (§10.6, shared clock) | ~8·10⁻⁴ | 191 / 199 |
| **after (5.1 Ω)**, 3 × 90 s median (range) | 2.4·10⁻⁸ (1.0–5.4·10⁻⁸) | 2.4·10⁻⁸ (1.6–6.5·10⁻⁸) | 1.0 | 1.1–3.5·10⁻² / 1.2·10⁻² (2 × 60 s) | 6·10⁻⁷ … 2.4·10⁻⁴ | 193 / 197 |

- gs SerDes PLL `PLL_CAP_FT` moved from 434–437 to **446–449** (same bits): the DCO needs a different setting, consistent with a
  lower VDD_SER_PLL. Offset m2 − gs +1.8 ppm (was +2.6).
- **2.5 G: no significant change** (within the load-to-load spread); M2 stays synced all the time. **5 G: still unusable**; BER while
  synced 2–4× lower, but the link is synced even less of the time. Not a result that 5.1 Ω helps or hurts.
- **Check the voltage:** the SerDes draws 40–51 mA at 5 G (DS1001 Table 4.4). 5.1 Ω drops 0.20–0.26 V, so VDD_SER ≈ 0.84–0.90 V
  from VDD_CORE 1.1 V, **below the DS1001 minimum of 1.00 V** (p.155). Measure VDD_SER / VDD_SER_PLL at the SerDes side of
  R106/R105 (TP10/TP8) under load before further tests.

### 11.5 Shared refclk restored, with 5.1 Ω (GS) / 4.7 Ω (M2) in the SerDes supply feeds — lab13 (28.09. 16:23–16:49)

**State:** M2 X2 removed, C136/C137 100 nF 0402 back (= the shared-clock setup of §10.4). GS R106/R105 = 5.1 Ω, M2 R105/R106 = 4.7 Ω
(Goran, Patrick Urban's advice), GS 1 µF on C127/C128/C42 unchanged. VDD_SER not measured yet. `lab13.sh` = the `lab9.sh` protocol
unchanged (same six bits). Raw data `data_20260928/t5089/lab13.*`, `log13/`. Health: m2 − gs 0.0 ppm (2500.02 / 2500.02 Mb/s),
all PLLs locked, FT_OF/UF 0; CAP_FT gs 442–450 (was 433–440 with 1 Ω), m2 504–515.

| Point | §10.4: 1 Ω, shared clock (t79) | **lab13: 5.1/4.7 Ω, shared clock** |
|---|---|---|
| 2.5 G gs→m2 r1 / r2 / r3 | 6.9 / 4.3 / 6.0 ·10⁻¹⁰ | **1.1·10⁻¹¹** / 1.0·10⁻⁹ / 2.0·10⁻⁹ |
| 2.5 G m2→gs* r1 / r2 / r3 | 2.6·10⁻¹⁰ / 8.0·10⁻¹² / 1.3·10⁻¹¹ | **0 / 0** / 2.2·10⁻⁹ (0 errors in 300 s = BER < 1.0·10⁻¹¹) |
| 2.5 G median (worst) gs→m2 ; m2→gs | 6.0·10⁻¹⁰ (6.9·10⁻¹⁰) ; 1.3·10⁻¹¹ (2.6·10⁻¹⁰) | 1.0·10⁻⁹ (2.0·10⁻⁹) ; 0 (2.2·10⁻⁹) |
| 2.5 G synced share | 0.96–1.00 | 0.97 |
| 5 G P2 60 s median gs→m2 / m2→gs* | 4.9·10⁻² / 2.0·10⁻² | 3.0·10⁻² / 1.1·10⁻² |
| 5 G P3 60 s median gs→m2 / m2→gs* | 6.2·10⁻² / 1.0·10⁻¹ | 3.2·10⁻² / 6.1·10⁻² |
| 5 G synced share P2 / P3 (gs→m2) | 8·10⁻⁴ / 8·10⁻³ | 1.9·10⁻⁴ / 3.1·10⁻⁴ |
| `ber_jtag_check` 200 P3 m2 / gs | 183 / 182 | **197 / 191** |

Reading:
- **2.5 G: the best single loads so far** (gs→m2 1.1·10⁻¹¹; m2→gs 0 errors in 2 of 3 loads × 300 s), but the load-to-load spread is
  back (×190 in gs→m2), and the median is not better than §10.4. With 3 loads per column the two settings cannot be ranked.
- **5 G: 1.5–2× lower BER while synced and fewer bad raw words, but the link is synced even less of the time. Still unusable.**
- Separate clocks (§11.2–§11.4) vs this: shared clock is 20–1000× better at 2.5 G. Keep the shared refclk.
- Open: VDD_SER / VDD_SER_PLL on both boards (5.1 Ω / 4.7 Ω × 40–51 mA may put them below the 1.00 V of DS1001), measured under a 5 G load.

**Next (hardware, Goran):** terminate or remove the stub (100 Ω P–N on the SER_CLK pads of C136/C137 plus `PLL_RTERM 0` on M2, or cut the
line right after C129/C130), add 100 nF from X2 pin 6 to pin 3, then run `lab11.sh` unchanged. If the shared-clock numbers do not come
back, the separate-clock penalty is the CDR tracking, and the shared refclk stays the better design for this link.

## 12. TASK-5482: retest 2.5 / 5 Gb/s after the M2 JTAG fix (12.10.2026 16:00–16:32) — BER counters NOT readable

**State:** both boards answer on JTAG (`fpga-jtag gs|m2 --detect`, idcode 0x20000001; Goran fixed the M2 `TDO is stuck at 0` before 15:59).
Same boards on the same probes as 28.09. (fingerprint: RX_OFFSET gs 3 / m2 7, RX_DETECT_DONE gs 0 / m2 1, = `log13`).
Same six bits as lab9/lab13 (sha256 in `lab14.out`). Loading only `fpga-jtag gs|m2 <bit> -r`; after every load the
`RX_CDR_SET_ACC_CONFIG` 2→0 pulse on both (`LOCAL_REFCLK_M2.md` §4C). Raw data `data_20261012/t5482/` (`lab14.sh/.out`, `log/`).

**Blocker — the gs UART is silent, so `ber_mon.py` gets no lines and no BER can be computed.** Checked by the agent:
0 bytes on all four DirtyJTAG ACM ports (gs if01/if03, m2 if01/if03) for 3.5 s each with `ber_top` loaded, at 9600/57600/115200/230400/1 M
baud; also 0 bytes with the LiteX SoC `ETH_GateMateA1_0410_..._np1817s1.bit` (same UART pins IO_NB_B5/IO_NA_B6, same clock IO_SB_A8),
whose BIOS printed on this port on 07.10. (TASK-5224). No process holds the port. The gs probe was re-enumerated at 16:01:41
(`port4 disabled by hub (EMI?)`, Pi under-voltage `throttled=0xd0005`). Both designs need `clk_i` (IO_SB_A8) and the UART wire;
the SerDes does not, which is why the link works below. Which of the two is missing (25 MHz clock on IO_SB_A8 or the
IO_NB_B5 → probe RX wire) cannot be separated over JTAG with the existing tools (`gatemate_ila`/`lab_watch` do not exist).

**What JTAG shows (lab14, 3 loads per point; `ber_jtag_check` 200 RX words per board per load):**

| Point | PLL lock gs/m2 | CAP_FT gs / m2 | CDR lock gs / m2 (health) | PEER words gs RX (m2→gs) r1/r2/r3 | PEER words m2 RX (gs→m2) r1/r2/r3 | BER |
|---|---|---|---|---|---|---|
| 2.5 G best pair (RTERM 1) | 3/3 / 3/3 | 491–494 / 505–508 | 2/3 / 3/3 | **200 / 200 / 200** | **200 / 200 / 200** | not readable (UART) |
| 5 G P2 | 3/3 / 3/3 | 497–498 / 513–516 | 0/3 / 0/3 | 191 / 186 / 197 | 195 / 188 / 190 | not readable |
| 5 G P3 | 3/3 / 3/3 | 494–497 / 515–516 | 2/3 / 3/3 | 111 / 104 / 154 | 181 / 172 / 172 | not readable |
| *lab13 28.09. P3 (ref.)* | | *442–450 / 512–515* | | *191* | *197* | *3.2·10⁻² / 6.1·10⁻²* |

Reading:
- **2.5 G: the link is up in both directions in every load** (PLL, CDR at the BER-sample time, K28.5 alignment, data from the peer:
  1200/1200 words). With ≤ 1200 sampled words this only says the word error rate is < ~1·10⁻³; the 28.09. figures
  (lab12 separate clocks 1.5·10⁻⁸ / 4.7·10⁻⁸, lab13 shared clock 1.0·10⁻⁹ / 0) can be neither confirmed nor refuted today.
- **5 G: reaches PLL lock and word alignment in every load; the step that fails is bit-clean data** — 2–14 % (P2) and 9–48 % (P3) of
  sampled words are not valid peer words, and the CDR lock bit drops out (P2 0/3 in the health snapshot). P3 on gs RX is worse
  than lab13 (111–154/200 vs 191/200). Still unusable, as on 28.09.
- **New: gs `PLL_CAP_FT` 491–498** (28.09.: 442–450 with 5.1 Ω, 434–437 with 1 Ω; same bits). The gs SerDes PLL needs a different DCO
  setting than on 28.09., consistent with a changed VDD_SER_PLL feed (R105/R106) — hardware state since 28.09. not recorded.
  m2 unchanged (505–516).

**To finish this retest:** get the gs UART back (UART wire IO_NB_B5 → DirtyJTAG E660583883501E2C RX and the 25 MHz clock on IO_SB_A8),
then run `lab14.sh` → `lab13.sh` protocol unchanged (2.5 G 3 × 300 s, 5 G P2/P3 3 × 300 s) for the BER table.

## 13. TASK-5483: re-characterisation after Goran's supply-filter rework (12.10.2026 17:20) — **gs SerDes PLL does not start**

**Order:** Goran 17:20 (uputa #303): first set-up/tuning (snapshot of both boards, FFE/AFE/CDR sweep 2.5 G m2→gs then 5 G), eye scan,
then BER **over JTAG only** (no UART). **Done by:** Jelena, gs lease `TASK-5483`, `fpga-jtag … -r` only, CFGRST bits from `/home/pi/fpga`
(sha256 unchanged, see `snap.out`). **Raw data:** `data_20261012/t5483/log/` (`snap.out`, health JSONs); the lab15 input (2.5 G × 3,
stopped by Goran at 17:08) is in `data_20261012/t5482b/` (`lab15.out`, `log15/`).

**Timeline (same bits, same procedure: m2 then gs, `-r`, SET_ACC 2→0 pulse on both):**

| Time | State | gs PLL lock / CAP_FT | m2 PLL lock / CAP_FT | `ber_jtag_check` PEER gs RX / m2 RX | BER (gs UART) gs→m2 ; m2→gs |
|---|---|---|---|---|---|
| 28.09. 16:23–16:49 (lab13) | 5.1 Ω / 4.7 Ω feeds | 1 / 442–450 | 1 / 504–515 | 191 / 197 of 200 (P3) | 1.0·10⁻⁹ ; 0 (2.5 G median) |
| 12.10. 16:00–16:32 (lab14) | after the first filter change | 1 / 491–498 | 1 / 505–516 | 2.5 G 200/200 both | UART silent |
| 12.10. 16:48–17:08 (lab15) | same | 1 / 490–494 (2.5 G), 500 (5 G P2) | 1 / 505–508, 514 | 2.5 G 50/50 both | r1 9.97·10⁻¹¹ ; 4.45·10⁻⁸, r2 3.40·10⁻⁸ ; 3.38·10⁻⁹, r3 1.15·10⁻¹⁰ ; 4.22·10⁻⁹ |
| 12.10. 17:08–17:20 | **Goran reworks the filter again** | | | | |
| **12.10. 17:24–17:31 (this task)** | after the rework | **0 / 0, CAP_STATE 0, BISC_CO 0** | 1 / 503–507 | **ZERO 50/50 both** | — |

**What the agent checked before calling it hardware (rule 4: "what worked in the last bitstream works now"):**

| Check | Result |
|---|---|
| gs 2.5 G bit loaded 4× (`fpga-jtag gs /home/pi/fpga/gs_2g5.bit -r`) | `PLL_LOCKED=0`, `PLL_CAP_FT=0`, `PLL_CAP_STATE=0`, `PLL_BISC_CO=0`, `PLL_BISC_CP=0` every time |
| other rates on gs: 0.3 G, 1.25 G (`t5066/ber_gs_0g3/1g25_CFGRST.bit`), 5 G P2 | the same — **rate-independent** |
| ADPLL restart over the regfile (`PLL_EN_ADPLL_CTRL` 1→0→1), then `PLL_REF_RTERM` 0 | still 0 / 0 / CAP_STATE 0 / `PLL_SYNC_VALUE` 0 |
| PLL configuration registers gs vs m2 | **identical**: CP 80, CI 3, FILTER_SHIFT 2, BISC_MODE 5, CONFIG_SEL 1, CP_MIN/MAX/START 6/30/6, FT 512, FCNTRL 58, MAIN_DIVSEL 27, OUT_DIVSEL 1, EN_ADPLL_CTRL 1, REF_SEL 1, REF_RTERM 1 |
| m2 (refclk comes from the GS oscillator over the cable) | PLL locks, CAP_FT 503–507 (= 505–508 before) → **the shared 100 MHz refclk source is alive** |
| gs JTAG / fabric | `--detect` OK, bits load (`Done`), TX/RX termination calibration done (`TX/RX_CALIB_DONE=1`) |
| gs RX analog (same bit, vs lab14/15) | `RX_CALIB_CAL` 0 → **8**, `RX_OFFSET` 3 → **6**, `RX_TH_MON` 15 → 8 — the RX analog calibration also lands elsewhere |
| link | m2 RX `ZERO` 50/50 (gs TX silent without its PLL), m2 CDR 0; gs RX `ZERO` |
| Pi supply | `throttled=0xd0000` (past under-voltage, not current) — the probes stay enumerated |

**Reading.** The gs SerDes ADPLL never leaves state 0 (no capacitor search, `BISC_CO` 0), at every rate and after a regfile restart, with
the same registers as the working m2 and with bits that locked at 17:08. The refclk source is alive (m2 locks on it). Between 17:08 and
17:24 only the GS supply filter was reworked. The most likely cause is **no or too low VDD_SER_PLL on GS** (the feed R105 + the new filter;
DS1001 p.155 min 1.00 V), or less likely an open on the GS-side SER_CLK_P/N into the FPGA. This cannot be fixed or separated over JTAG.

**Consequence for the order of #303:** steps 1–5 (sweep, eye, JTAG BER, new bits) need a working gs PLL — **not done**; no new bitstreams,
the six bits in `/home/pi/fpga` stay unchanged. **What Goran should measure (GS, under load with `gs_2g5.bit` loaded):** VDD_SER_PLL at
TP8 (SerDes side of R105) and VDD_SER at TP10 (R106), both ≥ 1.00 V; continuity of the new filter parts. Then re-run step 1:
`fpga-jtag gs /home/pi/fpga/gs_2g5.bit -r; fpga-jtag gs run python3 eyescan.py get PLL_LOCKED PLL_CAP_FT PLL_CAP_STATE` → expect 1 / ~440–500 / 2.

### 13.1 TASK-5483 retry (12.10. 18:00–19:15): the gs PLL locks again — lab17 sweep stopped at 12/17

After Goran's second look at the filter the gs ADPLL locks (CAP_FT 502 at 2.5 G; 106/495/503 at 0.3/1.25/5 G, `snap2.out`, commit
`675dba9`). lab17 (2.5 G, one load per point, 60 s `ber_mon sparse`, `ber_jtag_check` 200) ran 12 of 17 points before the boards were
switched off (~19:21); raw `data_20261012/t5483/lab17.out`. Numbers are in the §14.2 table.

## 14. TASK-5487 (dorada 5483): A/B UART, 2.5 G sweep + confirmation, 5 G P2/P3, load-to-load scatter, eye (12.10.2026 19:36–)

**Order:** Goran 12.10. 19:31 (boards on again) and uputa #308 (21:35). **Done by:** Jelena, gs lease `TASK-5487`, loading only
`fpga-jtag gs|m2 <bit> -r`, the six CFGRST bits in `/home/pi/fpga` (sha256 unchanged), `RX_CDR_SET_ACC_CONFIG` 2→0 on both after every
load. **Raw data:** `data_20261012/t5483/` — `uart_ab2.out`, `lab18*.sh/.out`, `log18/`, `lab19.*`, `log19/`, `eye20.*`.
Scripts: `lab18.sh` = `lab17.sh` + per-board fields (`gs:F=V`, `m2:F=V`) + one JTAG retry + `SER=1` option.
**Metrics:** BER = `ber_mon.py sparse` (gs UART read only at the start and end of the window); `ber_jtag_check` = share of raw RX words
that are valid peer words (only resolves word error rates > ~1/N).

### 14.1 A/B: is the gs UART dropout caused by JTAG traffic on the same probe? — **No**

| Run | Windows without JTAG (bytes / lines per 60 s) | Windows with back-to-back JTAG reads |
|---|---|---|
| 19:15–19:21 (before the power-off, `uart_ab.out`) | 10442/69, 9120/60, **0/0** | **0/0**, 11128/74, port error (boards switched off) |
| 19:36–19:42 (fresh boards, `uart_ab2.out`) | 9475/60, 9120/60, 9272/61 | 9120/60, 9728/64, 9576/63 |

A dropout happened with no JTAG at all (A3), and with JTAG 3/3 windows were full → concurrency is not the cause; the lab scripts stay
parallel (`SER=0`). The dropout remains intermittent (whole windows, both modes); the Pi showed `throttled=0xd0005` (under-voltage now)
at 19:36 — a USB/supply cause on the Pi side is still open. In the series below 6 of 52 windows were `NOUART`.

### 14.2 2.5 G search (one load per point, 60 s; PROFILE 1 defaults PRE 5, POST 5, AMP 31, CKP 62, TRANS_TH 8, PEAK 24, GAIN 0)

TX fields act on the far RX: gs TX → gs→m2, m2 TX → m2→gs. `ber_jtag_check` 200/200 PEER on both boards at **every** 2.5 G point.

| Point | gs→m2 | m2→gs | Point | gs→m2 | m2→gs |
|---|---|---|---|---|---|
| base (lab17 18:40) | 2.0·10⁻⁸ | 4.7·10⁻⁷ | base (lab18 19:45) | 1.2·10⁻⁶ | 4.4·10⁻⁷ |
| POST 0 | 1.5·10⁻⁶ | 2.5·10⁻⁷ | base2 (20:20) | NOUART | NOUART |
| POST 10 | 5.7·10⁻⁸ | 3.8·10⁻⁹ | CKP 126 | 1.8·10⁻⁶ (19:14 NOUART) | 3.1·10⁻⁶ |
| POST 12 | 6.7·10⁻⁸ | 8.3·10⁻⁹ | CKP 30 | 4.3·10⁻⁶ | 1.1·10⁻⁷ |
| POST 15 | 1.1·10⁻⁶ | **3.5·10⁻¹⁰** | CKP 248 | 1.3·10⁻⁵ | 5.9·10⁻⁶ |
| m2 POST 15 only | 1.4·10⁻⁷ | 6.3·10⁻⁹ | TRANS_TH 16 | 7.1·10⁻⁸ | 4.4·10⁻⁸ |
| gs 10 / m2 15 | NOUART | NOUART | VCMSEL 4 (AFE+RTERM) | 5.0·10⁻⁵ | 4.7·10⁻⁶ |
| gs 12 / m2 20 | 1.7·10⁻⁶ | 3.8·10⁻⁹ | PEAK 16 / 8 / 31 | 6.9·10⁻⁸ / 1.7·10⁻⁷ / 8.8·10⁻⁷ | 4.0·10⁻⁷ / 1.2·10⁻⁸ / 1.1·10⁻⁷ |
| gs 10 / m2 12 | 1.2·10⁻⁵ | 1.2·10⁻⁷ | GAIN 1 / 2 | 1.0·10⁻⁷ / NOUART | 1.5·10⁻⁵ / NOUART |
| PRE 0, AMP 24 | NOUART | NOUART | | | |

Only one pattern looked like a direction-specific gain: m2 TX POST ≥ 10 gave m2→gs 3.5·10⁻¹⁰…8.3·10⁻⁹ vs 4.4–4.7·10⁻⁷ at POST 5. CKP and
VCMSEL away from the default are worse in both directions. gs→m2 had no clear winner (the base itself spread 2·10⁻⁸…1.2·10⁻⁶).

### 14.3 2.5 G confirmation: base vs m2 POST 15 vs m2 POST 15 + TRANS_TH 16, 3 loads interleaved, 240 s, `ber_jtag_check` 1000

| Point | gs→m2 r1 / r2 / r3 | m2→gs r1 / r2 / r3 | JTAG PEER m2 / gs |
|---|---|---|---|
| **base** | **3.7·10⁻⁷** / NOUART / **3.0·10⁻⁸** | **6.3·10⁻¹⁰** / NOUART / **6.2·10⁻⁹** | 1000/1000 ×3 |
| m2 POST 15 | 1.9·10⁻⁷ / 1.5·10⁻⁴ / 3.2·10⁻⁶ | 4.0·10⁻⁹ / 2.5·10⁻⁸ / 2.4·10⁻⁶ | 1000/1000 ×3 |
| m2 POST 15 + TH 16 | 1.8·10⁻⁶ / 4.6·10⁻⁵ / NOUART | 1.9·10⁻⁸ / 9.2·10⁻⁷ / NOUART | 1000/1000 ×3 |

**Reading:** the search winner does not survive repeated loads — the baseline is the best of the three in both directions. The sweep
"gain" was load-to-load scatter, which after the rework spans ~4 decades with identical settings (gs→m2 3·10⁻⁸…1.5·10⁻⁴). **No new 2.5 G
recipe; the bits in `/home/pi/fpga` stay.** A candidate `m2_e1_2g5p1_txneg_post15_s2.bit` (OV_TX_SEL_POST 15, sha256 3bfe186f…) was built
to check the flow: it differs from `m2_2g5.bit` in 4 bytes only (same placement/routing, same Fmax) and is NOT deployed.
Compared with before the rework: lab13 28.09. median 1.0·10⁻⁹ / 0, lab15 12.10. 16:48 r1 1.0·10⁻¹⁰ / 4.5·10⁻⁸ → **2.5 G is 1–3 decades
worse after the 17:08–17:20 supply-filter rework**, and the spread grew.

### 14.4 5 G, recipes P2 / P3 × (base, m2 POST 15), 3 loads interleaved, 60 s, `ber_jtag_check` 1000

| Point | gs→m2 BER r1 / r2 / r3 | m2→gs BER r1 / r2 / r3 | JTAG PEER m2 RX (gs→m2) median | gs RX (m2→gs) median |
|---|---|---|---|---|
| **P2 base** | 8.2·10⁻² / **4.2·10⁻⁸** / 0.5 | 3.0·10⁻² / 6.4·10⁻³ / 3.6·10⁻³ | 881/1000 | 895/1000 |
| P2 m2 POST 15 | 1.0·10⁻¹ / 9.0·10⁻² / 5.7·10⁻² | 1.8·10⁻² / 7.0·10⁻³ / 8.8·10⁻² | 863 | 839 |
| P3 base | 0.5 / 0.5 / NOUART | 2.6·10⁻¹ / 2.7·10⁻¹ / NOUART | 557 | 618 |
| P3 m2 POST 15 | 2.6·10⁻¹ / 3.3·10⁻¹ / 2.3·10⁻¹ | 2.1·10⁻² / 4.6·10⁻² / 4.7·10⁻² | 572 | 730 |
| *lab14 12.10. 16:00 (before rework), of 200* | | | *P2 190/200 = 95 %, P3 172/200* | *P2 191/200, P3 111/200* |

**Reading:** 5 G is still unusable. P2 stays the better recipe (88–90 % valid words vs 56–62 % for P3); m2 POST 15 does not help P2 and moves
only P3 m2→gs (618 → 730), not enough to matter. One P2 load had gs→m2 at 4.2·10⁻⁸ for the whole 60 s — the first 5 G window close to
usable in this direction, again load-dependent. P2/P3 are worse than lab14 before the rework (P2 95 % → 88 %). **No new 5 G recipe.**

### 14.5 Load-to-load scatter at 2.5 G (uputa #308): 10 loads × 240 s, baseline bits, standard procedure (no recal), lab19 23:10–00:18

Per load: `eyescan.py health --raw` on both boards right after SET_ACC (new option: RX_AFE_OFFSET + raw words 0x02/0x04–0x07/0x0B–0x0D/
0x3C/0x55/0x5A/0x5B), `ber_mon sparse` 240 s, the same snapshot at the end of the window, `ber_jtag_check` 200 (PEER 200/200 every load).
Table and correlation: `tools/lab/scatter_table.py docs/data_20261012/t5483/log19` (Spearman ρ of every state value vs log10 BER).
**All 10 windows had UART** (no dropout in this series).

| Load | gs→m2 | m2→gs | gs RX_OFFSET start→end | gs CAP_FT | m2 CAP_FT |
|---|---|---|---|---|---|
| r1 | 8.6·10⁻⁷ | 7.7·10⁻⁸ | 3→2 | 502 | 509 |
| r2 | 3.6·10⁻⁷ | 2.7·10⁻⁸ | 3 | 499 | 510 |
| r3 | 2.7·10⁻⁶ | 1.2·10⁻⁷ | 3→2 | 499 | 509 |
| r4 | 3.7·10⁻⁷ | 3.8·10⁻⁷ | 2→3 | 502 | 512 |
| r5 | 1.6·10⁻⁶ | 3.6·10⁻⁷ | 3 (gs CDR 0 at start, 1 at end) | 502 | 509 |
| r6 | 1.7·10⁻⁷ | **5.0·10⁻⁹** | **4**→3 | 499 | 510 |
| r7 | 6.8·10⁻⁸ | 2.8·10⁻⁷ | 4 | 502 | 513 |
| r8 | 7.5·10⁻⁷ | **1.7·10⁻⁶** | **2** | 501 | 513 |
| r9 | 1.2·10⁻⁵ | **1.0·10⁻⁶** | **2**→3 | 502 | 513 |
| r10 | 1.0·10⁻⁵ | 2.7·10⁻⁷ | 3 | 499 | 510 |

Constant in all 10 loads on both boards: RX_CALIB_CAL 9, TX_CALIB_CAL 7, RX_EQA_TAPW 0, RX_TH_MON 15 (rail), RX_AFE_OFFSET 8,
RX_EQA_LOCKED 1, FREQ_ACC_VAL 0; **m2 RX_OFFSET 7 in every load**. PHASE_ACC_VAL moves ±200 codes inside a snapshot (live).

**Reading:**
- Same bits, same procedure, 3 h of lab: gs→m2 spans 6.8·10⁻⁸…1.2·10⁻⁵ (×175), m2→gs 5.0·10⁻⁹…1.7·10⁻⁶ (×340). No time trend that
  explains it (ρ vs load index +0.28 / +0.52).
- **The only state that varies with the BER is gs RX_OFFSET** (data-sampler offset calibration of the gs receiver = the m2→gs direction):
  ρ = −0.74 vs log10 BER m2→gs. Loads with offset 2: 3.8·10⁻⁷, 1.0·10⁻⁶, 1.7·10⁻⁶ (the three worst); offset 4: 5.0·10⁻⁹ (the best), 2.8·10⁻⁷.
  gs RX_OFFSET also **changes inside a window** (5 of 10 loads, ±1), so the offset loop is live and sits on a code boundary; m2's
  never moves. With ~80 state/direction pairs a |ρ| ≥ 0.65 can appear by chance (~4 expected), so this is a lead, not proof — the
  direct test is §14.6 (vertical bathtub = forced RX_AFE_OFFSET on gs). gs.PLL_BISC_CO ρ −0.78 is also listed but varies over the
  whole 16-bit range (64179..65458 = a counter, not a setting).
- gs→m2 (received by m2, RX_OFFSET constant 7) has no state that follows it (best |ρ| 0.47) → its spread comes from something the
  registers do not show (TX side of gs, channel, supply noise).

### 14.6 Eye scan: Manda's hypotheses (TASK-5486/5488) tested on m2 — **counters stay 0; no bathtub either**

Bits: 2.5 G baseline pair, fresh load + SET_ACC. Scripts: `tools/eyeprobe.py` (TASK-5488) and `data_20261012/t5483/eye_tests.py`
(`h7 h2 h3 h4 h8 phase`). Raw: `eye20.out`, `probe_m2_*.json`, `eye21.out`, `log21/`.

| Test (order of uputa #308) | What was done | Result |
|---|---|---|
| H7 W/C strobes over JTAG | `RX_CALIB_EN=1`, read at 0 / 50 / 500 ms | `RX_CALIB_EN` reads 1 **before and after** the write (never self-clears); eyeprobe: `W/C STUCK`. Plain R/W writes work (TX_SEL_POST, SET_ACC have measurable effect) |
| H2 EN edge/level, read later | 0x14 write 0 → reads 0x2000, write 1 → 0x2001 (= a level, readable); fresh 0→1 edge, wait 0 / 0.01 / 0.1 / 1 / 5 s, then EN=0 | counters 0x16–0x1D = 0 at every step |
| H1 PRBS-7 reference | eyeprobe: near-end PMA loopback + TX/RX PRBS-7 on m2, H2 sequence, control without PRBS | 0 |
| H3 0x14[3:1] | the bits ARE writable (0x200E); H2 sequence for m = 1…7 | 0 for every m |
| H4 TH_MON2 override bit | TH_MON2 = 3 with 0x05[11] (DS) and with 0x06[11] (PU), H2 sequence | `RX_TH_MON` stays 15 with both bits; counters 0 |
| H8 0x2B reset order | `W(0x2B, 0x0C00, 0x0C00)` | CDR/EQA stay locked; 0x2B reads **0x0100** after the write (0x0400 before) → inconclusive; the next recal needed 3 s for EQA lock. Note: eye20's `h4` restored 0x05/0x06 to 0x00C8/0x01C8 (TH_MON2 3, AFE_OFFSET 7) instead of 0x0208/0x0208 — test bug, no lasting effect (every later test reloads the bits) |
| Bathtub, horizontal (§3.1) | `RX_CDR_PHASE_ACC`=VAL+4096, `SET_ACC_CONFIG=1`, `FORCE_LOCK=1`, then CKP=CKI=0 | `PHASE_ACC_VAL` does not follow (frozen 52934 after H8; on a fresh load reads 0); no effect → **not feasible** with the documented fields |
| Bathtub, vertical (§3.2) on gs RX | `RX_EN_EQA_EXT_VALUE[3]=1` + `RX_AFE_OFFSET` = 0…31 (16 points, 30 s each) | override is active (`RX_OFFSET` reads 0 instead of 3) but **m2→gs stays 2.5·10⁻⁸…9.7·10⁻⁸ over the whole range** (base 1.1·10⁻⁷; 2 points NOUART); gs→m2 (control) 4.0–5.4·10⁻⁶ unchanged → no BER edge, **no eye height** |

**Reading:** the eye counters cannot be started with anything documented or guessed so far; the one new fact is H7 — a W/C bit written
over JTAG reads back as 1 and does not clear, which would also explain a start strobe that never fires (`RX_EYE_MEAS_EN` is W/C in the
DS). The phase override does nothing visible, and the forced data-sampler offset changes nothing over its full range: either the field
does not reach the data sampler, or the errors are not threshold-limited. The vertical result also **weakens the §14.5 lead**: forcing
the gs offset to any of 0…31 did not change m2→gs, so gs RX_OFFSET 2 vs 4 is not shown to be the cause. Next step is Patrick Urban
(question in `EYE_SCAN_ISTRAZIVANJE.md` §4, add: "W/C bits written over the regfile read back 1 and never clear — is a regfile clock
needed?").

### 14.7 Result of TASK-5483/5487

- **No new recipe and no new bitstreams.** Every search "winner" (m2 POST 10–15 at 2.5 G, m2 POST 15 at 5 G) lost to the baseline on
  repeated loads. The six bits in `/home/pi/fpga` stay; `README.txt` there got a 12.10. note.
- **After the 12.10. supply-filter rework the link is worse than before:** 2.5 G baseline over 13 loads (§14.3 + §14.5) gs→m2
  3.0·10⁻⁸…1.2·10⁻⁵ (median ~8·10⁻⁷), m2→gs 5.0·10⁻⁹…1.7·10⁻⁶ (median ~2·10⁻⁷) vs lab13 (28.09.) median 1.0·10⁻⁹ / 0 and lab15
  (12.10. 16:48, before the rework) 1.0·10⁻¹⁰ / 4.5·10⁻⁸. The spread is in the hardware state (load-to-load), not in any register we can read.
  5 G P2 valid words 88 % (lab14 95 %).
- **For the long serial test TASK-5482:** `m2_2g5.bit` (sha256 b1b98a5d…) + `gs_2g5.bit` (36f09752…), load m2 then gs with `-r`, SET_ACC
  2→0 on both. 5 G is not usable (P2 `gs_5g.bit`/`m2_5g.bit` only if a 5 G run is wanted for comparison).
- **Hardware first:** measure VDD_SER / VDD_SER_PLL on GS (TP8/TP10) under load and compare with 28.09.; the BER loss coincides with the
  rework, and no setting recovers it.

## 15. TASK-5482: long serial BER run 2.5 G (3 loads × 3600 s) + 5 G P2 (1 × 300 s), lab22 13.10.2026 00:52–04:22

Bits per §14.7: `m2_2g5.bit` + `gs_2g5.bit` (5 G: `m2_5g.bit` + `gs_5g.bit`, recipe P2). Per load: `fpga-jtag m2 … -r`, `fpga-jtag gs … -r`,
SET_ACC 2→0 on both, `eyescan.py health`, `ber_jtag_check`, then `tools/lab/ber_long.py` over the gs UART (snapshot every 60 s,
**no `Z`** — see the finding below; BER = sum of the intervals since the baseline), health + `ber_jtag_check` again at the end.
Raw: `docs/data_20261013/t5482/` (`lab22.sh`, `lab22.out`, `log22/*.jsonl`, `*.start_/end_*.json`).

| Rate | Load | Time | gs→m2 BER | m2→gs BER | synced gs→m2 / m2→gs | 60 s intervals gs→m2 (min…max) | JTAG PEER start/end |
|---|---|---|---|---|---|---|---|
| 2.5 G | r1 | 3602 s | 2.0·10⁻⁷ | 3.3·10⁻⁸ | 1.00 / 1.00 | 7.3·10⁻⁸ … 1.9·10⁻⁶ | 200/200 both |
| 2.5 G | r2 | 3601 s | 7.6·10⁻⁷ | 1.1·10⁻⁷ | 1.00 / 1.00 | 5.7·10⁻⁷ … 1.0·10⁻⁶ | 200/200 both |
| 2.5 G | r3 | 3604 s | 4.2·10⁻⁶ | 2.8·10⁻⁷ | 1.00 / 1.00 | 3.1·10⁻⁶ … 5.3·10⁻⁶ | 200/200 both |
| **2.5 G** | **median of 3** | 3 h | **7.6·10⁻⁷** | **1.1·10⁻⁷** | 1.00 / 1.00 | | |
| 5 G P2 | r1 | 300 s | 5.5·10⁻³ | 2.0·10⁻² | 0.83 / 1.00 | gs→m2 checker restarted 3× | 826–873/1000 → FAIL |

Bits per 2.5 G load and direction: 4.5·10¹² (≥ 1.5·10⁵ errors in each, so these are measured BERs, not upper bounds).
Health at every 2.5 G start: PLL_LOCKED 1, FT_OF/UF 0, CAP_FT m2 512–513 / gs 499–502, CDR/EQA lock 1 (r3 end: gs RX_CDR_LOCKED 0 in the
snapshot, counters synced throughout). 5 G P2: PLLs lock (CAP_FT m2 517 / gs 503), RX_CDR_LOCKED 0 on both boards at start and end,
JTAG PEER 83–87 % → it reaches PLL lock and partial word alignment, not CDR lock / a usable BER.

Comparison (2.5 G, median gs→m2 / m2→gs): 28.09. lab12 separate refclks + RTERM 1.5·10⁻⁸ / 4.7·10⁻⁸; 28.09. lab13 shared refclk
1.0·10⁻⁹ / 0; 12.10. §14.5 scatter (after the supply-filter rework) ~8·10⁻⁷ / ~2·10⁻⁷; **now 7.6·10⁻⁷ / 1.1·10⁻⁷**.

**Reading:**
- **2.5 G is not better than before; it equals the post-rework state of §14.5** and is ×50 (gs→m2) / ×2 (m2→gs) worse than lab12
  and ×760 / ≫ than lab13 on 28.09. The link never loses sync in 3 h (synced 1.00, no checker restart in either direction).
- **Inside a load the BER is constant for an hour** (first vs second half within ×1.4); **between loads it moves ×21** (gs→m2
  2.0·10⁻⁷ → 4.2·10⁻⁶). The error rate is fixed at load/calibration time, not drifting thermally — consistent with §14.5.
- gs→m2 (m2 receiver) stays the worse direction in every load (×6–15 over m2→gs).
- **5 G did not work** (one load, P2): 1–2 % bit errors, CDR not locked; no improvement over §14.4.
- Finding (tooling, not hardware): after a UART `Z` the m2 checker re-clears its counters every ~10–20 s, because `ber_top.v` r.146
  executes a command whenever the aux-frame command byte changes and that frame has no check; a corrupted-then-restored byte counts as
  a new `Z`. `ber_long.py` therefore never sends `Z`. Gateware fix (accept a command only after two identical frames) not done.

## 16. TASK-5522: re-run of the lab22 procedure on 15.10.2026 (Goran 12:02 "recalibrate and test SerDes again") — **2.5 G is back at the 28.09. level, 5 G still does not work**

Procedure = `lab22.sh` of §15 unchanged (only the log path and `SECS`/`SECS5` parameters): per load `fpga-jtag m2 … -r`, `fpga-jtag gs … -r`,
SET_ACC 2→0, `eyescan.py health`, `ber_jtag_check`, `ber_long.py` over the gs UART (snapshot every 60 s, no `Z`), health + JTAG at the end.
Same bits as §15 (`/home/pi/fpga/{m2,gs}_{2g5,5g}.bit`, mtime 12.10. 16:47, unchanged), same `eyescan.py` (12.10. 21:38). No power cycle.
Quick round 12:03–12:22 (1 × 60 s 2.5 G + 1 × 60 s 5 G P2), long round 12:22–13:07 (3 × 300 s 2.5 G + 1 × 300 s 5 G P2).
Raw: `docs/data_20261015/t5522/` (`lab.sh`, `quick.out`, `long.out`, `log/`, `log_quick/`).

| Rate | Load | Time | gs→m2 BER (errors / bits) | m2→gs BER (errors / bits) | synced gs→m2 / m2→gs | 60 s intervals gs→m2 ; m2→gs | JTAG PEER start/end |
|---|---|---|---|---|---|---|---|
| 2.5 G | quick | 55 s | 2.9·10⁻⁷ (18 251 / 6.3·10¹⁰) | 7.0·10⁻¹⁰ (44 / 6.3·10¹⁰) | 1.00 / 1.00 | 2.4…3.7·10⁻⁷ ; 0.6…1.1·10⁻⁹ | 200/200 both |
| 2.5 G | r1 | 296 s | **0** (0 / 3.6·10¹¹, < 8.4·10⁻¹² at 95 %) | 8.4·10⁻¹² (3 / 3.6·10¹¹) | 1.00 / 1.00 | 0 … 0 ; 0 … 3.9·10⁻¹¹ | 200/200 both |
| 2.5 G | r2 | 303 s | 2.1·10⁻⁹ (843 / 3.9·10¹¹) | 2.0·10⁻⁸ (7 774 / 3.9·10¹¹) | 1.00 / 1.00 | 1.1…3.4·10⁻⁹ ; 1.4…2.5·10⁻⁸ | 200/200 both |
| 2.5 G | r3 | 304 s | 3.6·10⁻¹⁰ (142 / 4.0·10¹¹) | 4.1·10⁻⁹ (1 637 / 4.0·10¹¹) | 1.00 / 1.00 | 1.5…5.3·10⁻¹⁰ ; 0.2…18·10⁻⁹ | 200/200 both |
| **2.5 G** | **median r1–r3** | 15 min | **3.6·10⁻¹⁰** | **4.1·10⁻⁹** | 1.00 / 1.00 | no checker restart | |
| 5 G P2 | quick | 60 s | 2.1·10⁻² | 6.7·10⁻² | — | | 894 / 883 of 1000 → FAIL |
| 5 G P2 | long | 242 s counted of 300 | 1.7·10⁻² | 5.1·10⁻² (gs checker restarted 3×, only 1.9·10⁹ bits) | snapshots 1 / 1, UART lost at 304 s | 1.0…2.8·10⁻² ; 4.6…5.7·10⁻² | m2 897→927, gs 908→878 of 1000 → FAIL |

Health: PLL_LOCKED 1, FT_OF/UF 0 everywhere; CAP_FT m2 507–510 / gs 495–500 (2.5 G), m2 515–518 / gs 499–500 (5 G); 2.5 G CDR and EQA lock 1
on both boards at start and end; 5 G: m2 RX_CDR_LOCKED 0 at start and end (as §15). gs RX_OFFSET 1–3 (2 at every start), m2 RX_OFFSET 7.

**Comparison, 2.5 G median gs→m2 / m2→gs:**

| Run | gs→m2 | m2→gs | now vs that run |
|---|---|---|---|
| 28.09. lab13, shared refclk, 5.1/4.7 Ω (§11.5), 3 × 300 s | 1.0·10⁻⁹ | 0 (worst 2.2·10⁻⁹) | same order (gs→m2 ×3 better, m2→gs within the load scatter) |
| 28.09. lab12, separate refclks + RTERM (§11.3) | 1.5·10⁻⁸ | 4.7·10⁻⁸ | **×42 / ×11 better** |
| 12.10. §14.5 scatter, 10 × 240 s (after the supply-filter rework) | ~8·10⁻⁷ | ~2·10⁻⁷ | ×2000 / ×50 better |
| 13.10. lab22 §15, 3 × 3600 s | 7.6·10⁻⁷ | 1.1·10⁻⁷ | **×2100 / ×27 better** |
| **15.10. this run, 3 × 300 s** | **3.6·10⁻¹⁰** | **4.1·10⁻⁹** | |

5 G P2: 13.10. 5.5·10⁻³ / 2.0·10⁻² → now 1.7·10⁻² / 5.1·10⁻² (×3 worse, same order), JTAG PEER 83–87 % → 88–93 %. Not usable either way.

**Is it better? — 2.5 G: yes. 5 G: no.**
- **2.5 G is ×2100 (gs→m2) / ×27 (m2→gs) better than 13.10.** and back at the best shared-clock level of 28.09. (lab13). Load r1 had
  0 errors gs→m2 in 3.6·10¹¹ bits and 3 errors m2→gs. No sync loss, no checker restart, JTAG PEER 200/200 in every check.
- **The load-to-load scatter is still there:** the quick load at 12:03 gave gs→m2 2.9·10⁻⁷ (13.10.-like), the three long loads
  0 … 2.1·10⁻⁹. That is ≥ ×3·10⁴ between loads with the same bits, so "better" means "most loads are good now", not "every load is
  good". Inside a load the 60 s intervals stay within ×2–4 (r3 m2→gs ×90), consistent with §15 (BER fixed at load time).
- **The worse direction swapped**: on 12./13.10. gs→m2 (m2 receiver) was ×6–15 worse in every load; now m2→gs (gs receiver) is worse in
  r1–r3 (×10). gs RX_OFFSET is 2 at every start — in §14.5 offset 2 marked the three worst loads, now it comes with the good ones, so the
  ρ = −0.74 hint of §14.5 does not hold.
- 300 s instead of 3600 s per load: §15 showed the BER is constant within a load (halves within ×1.4), so 300 s is representative; the
  floor at 300 s is 8.4·10⁻¹² (0 errors, 95 %).

**`RX_CALIB_CAL` / `TX_CALIB_CAL` = 0 / 0 (was 9 / 7) — what it is and what changed:**
- These are the 4-bit read-only results of the RX / TX **termination calibration** (`0x02[10:7]`, `0x3C[10:7]`, `TUNING_5G.md`), with
  `*_CALIB_DONE = 1` both times. They are not set by the bitstream or by any lab tool.
- History from the raw health JSONs: **0 / 0 on both boards on 26.–28.09.** (§9, `data_20260928/t5089/log/q1.health_*.json`, the good
  lab13 state) and on 12.10. before the rework; **9 / 7 on both boards** from 12.10. 17:24 (after Goran's supply-filter rework, §13) in
  all 10 loads of §14.5 and in lab22 §15 (13.10.); **0 / 0 again on 15.10.** in all 24 health snapshots (quick + long, start + end, both boards, both rates).
- Same bits, same `eyescan.py`, same procedure → the change is in the boards, not in the setup. The good BER coincides with 0 / 0 and
  the bad one with 9 / 7 in every run so far (correlation in 3 periods, not proof of cause). An identical 9 / 7 on two different dies,
  constant over 13 loads, looks more like a common supply / reference condition seen by the calibration than a per-die trim.
- UNVERIFIED: the exact meaning of the code (CologneChip question still open, §9) and what changed between 13.10. 04:22 and 15.10. 12:02
  — the agents did no power cycle; if the boards were power-cycled or reworked in between, that is the most likely trigger. **Question for
  Goran:** was anything done to the boards / their supply after 13.10.?

**Pi:** `throttled=0xd0005` at the end of the quick round (under-voltage now + throttled now + both in the past); the long round logged
0xd0000 / 0xd0008 (past only / soft temperature limit). No probe re-enumerated and every JTAG check passed, so it did not affect this
data, but the Pi supply is still marginal (as on 28.09.).

## 17. TASK-5525: Cologne Chip eye tools (serdestool 15.10.2026, Patrick Urban, mail UID 84) on both receivers — **the freeze path works, the eye counters still do not run; the adapted thresholds sit on the +15 rail at 2.5 G**

Goran 15.10. 14:18: "new tools from Cologne — see what is new and whether we can use it for a better calibration". Upstream copy:
`tools/upstream_cc_20261015/serdestool.py` (2439 r.; `eyetools.py` identical to ours). Same bits as §16 (`/home/pi/fpga/{m2,gs}_{2g5,5g}.bit`),
lab22 procedure per load (m2 then gs `-r`, SET_ACC 2→0), no power cycle. Raw: `docs/data_20261015/t5525/` (`lab25.*`, `lab26*`, `probes.out`, `log25/`, `log26*/`, `png/`).

### 17.1 What is new upstream and what was wrong in our E7 scan (§9.6, §14.6)

| Upstream rule (docstrings of `eye_freeze` / `eye_measure` / `eye_capture_op`) | What our `eyescan.py scan` did since E7 | Now measured on HW |
|---|---|---|
| `RX_EN_EQA` must be 0 **before** `RX_EQA_CONFIG` (0x08) is written, else the write is silently dropped; `sel_comp_data` (0x08[5:3]) = 2 routes monitor 2 | set `RX_EN_EQA=1` + `RX_EQA_LOCK_CFG[1]`, never wrote 0x08 → monitor never routed | after `eye_freeze`: `sel_comp_data=2`, `en_acc=0` read back (PASS, both boards) |
| `RX_TH_MON2` is **write-protected** while `RX_EN_EQA_EXT_VALUE[3]` = 0x06[11] is 1; freeze uses EXT_VALUE 0b0111 | set exactly 0x06[11]=1 (`th2_ovr_write`) → every threshold write was ignored | with 0b0111: wrote −15, read −15 (PASS, both boards) |
| `RX_EYE_MEAS_EN` 0x14[0] is start **and** status: 1 = running, 0 = done | read 1 as "done" (TASK-5066) and read the counters at once | bit never clears (§17.3) |
| a read of 0x07 **is** the capture; slice TAPW / TH_MON / OFFSET from ONE read (`eye_capture_op`) | `health` used `rd_fields` = one read of 0x07 too | identical sets (§17.4) |

Port (`tools/serdestool.py` = upstream + py3.7 + 2 fixes, `tools/eyescan.py capture|diagnose|eye|freeze|restore`, `tests/test_eye_cc.py` on a fake
regfile that models the three rules). Two upstream bugs fixed in our copy (to report to Patrick): `eye_diagnose` freezes with EXT_VALUE 0b0111 but then
demands 0b1111 → that check FAILs on every healthy receiver; `eye_freeze` writes the captured sign-magnitude `RX_OFFSET` into the unsigned
`RX_AFE_OFFSET` → ValueError for a negative offset (now written only when EXT_VALUE[3] is set). Plus our own: `freeze` printed with `%04b`
(ValueError after the writes, lab26 TAPW steps had no readback → repeated in lab26b).

### 17.2 `eye_diagnose` (lab25 14:37–14:54, 2.5 G / 5 G P2 / 2.5 G again)

| Check | m2 RX 2.5 G | gs RX 2.5 G | m2 RX 5 G P2 | gs RX 5 G P2 |
|---|---|---|---|---|
| CDR locked / EQA locked | PASS / PASS | PASS / PASS | **FAIL** / PASS | **FAIL** / PASS |
| adapted threshold in range | **FAIL** th1 = th2 = +15 | **FAIL** +15 / +15 | **FAIL** +15 / +15 | PASS 13–14 |
| ext-value set, sel_comp_data routed, integrators frozen, TH_MON2 writable | PASS ×4 | PASS ×4 | PASS ×4 | PASS ×4 |
| phase sweep / counters respond | **TimeoutError: RX_EYE_MEAS_EN stuck at 1** | same | same | same |

`PNG: png/diag_chain.png`. After every diagnose the restore was checked (EN_EQA 1, EXT 0, 0x08 = 0x01C0, CDR/EQA lock 1) and the link was
intact: JTAG PEER 200/200 before and after on both boards at 2.5 G; 60 s serial BER after the freeze/restore 6.7·10⁻¹⁰ / 4.2·10⁻⁹
(gs→m2 / m2→gs, = §16 r3) and 6.0·10⁻⁹ / 5.5·10⁻⁸ on the third load (load scatter as §16).

### 17.3 The eye engine does not start on our boards — probes (`probes.out`, m2 and gs, 2.5 G, IDCODE 0x20000001 both)

- After the upstream freeze, `RX_EYE_MEAS_EN` stays 1 for 1.5 s for window 1, 15, 255, 2048 (upstream: a full window is 131 µs at 1.25 G,
  "never observable over JTAG"); all eight counters 0x16–0x1D stay 0. 0x14[0] simply reads back the last written value; 0x14[15:4] is
  writable only while 0x14[0] = 0.
- **PRBS on the link** (gs TX_PRBS_SEL 2 → m2 RX_PRBS_SEL 2, `RX_PRBS_LOCKED=1`, then m2 TX → gs RX the same) — still stuck, still 0 →
  Manda's H1 (counters need the PRBS reference) is not sufficient.
- `RX_EQA_CONFIG` sel_comp_data 0…7 × sel_tap 0/1 (16 values, readback = written), adapting with the monitor routed, LOCK_CFG 14, and the
  undocumented 0x14[3:1] = 0…7 on both boards — no counter ever moves.
- So the vendor sequence is now implemented and verified register by register, and the measurement engine still does not run on
  CCGM1A1 here. **No eye picture is possible yet** (64 × 31 scan not run — it would return 1984 timeouts). Question for Patrick: is there a
  bitstream / CFG-level enable or clock for the eye unit outside the regfile (our `CC_SERDES` has `RX_EYE_MEAS_EN(EYE_EN=0)`,
  `RX_EYE_MEAS_CFG=0`, `RX_MON_PH_OFFSET=0`, `RX_DATAPATH_SEL=3`), or a silicon revision where it works?

### 17.4 `eye_capture_op` ×10 — is the RX_OFFSET movement a read-out artefact? — **No**

| Load | m2 RX_OFFSET (op / split) | gs RX_OFFSET (op / split) | TH_MON1/2 | TAPW |
|---|---|---|---|---|
| 2.5 G | 7 ×10 / 7 ×10 | **2 2 2 2 1 1 1 2 2 1** / 2 1 1 1 1 2 1 1 1 2 | +15 / +15 both | 0 both |
| 5 G P2 | 1 1 0 1 0 1 1 1 0 1 / 0–1 | 2 ×10 / 2–3 | m2 +15, gs 13–14 | 2–3 both |
| 2.5 G again | 7 ×10 | 2 2 2 2 1 2 2 2 1 2 / 2…1 | +15 / +15 | 0 |

`op` = one read of 0x07 per monitor (upstream), `split` = three separate field reads (three captures). gs RX_OFFSET moves 1↔2 **also with the
single-read capture**, so the "offset changes inside a window" of §14.5 (lab19) is the live offset loop sitting on a code boundary, not an
artefact of how it was read. Our `health` already sliced all three fields from one 0x07 read (`rd_fields`), so the §14.5/§16 values stand.
`PNG: png/capture_op.png`.

### 17.5 Calibration toward the operating point — gs RX (m2→gs), A/B/A inside one 2.5 G load (lab26 14:55–15:17)

The eye diagnose names the one lever left: both monitors sit on the +15 rail at 2.5 G (amplitude above the threshold DAC), so the DFE tap
(= th1 − th2) is forced to 0. TX_AMP is already 31 (max) and RX_AFE_GAIN 0 (min), so the lever is the m2 TX amplitude. Second lever: pin the
gs DFE tap by freeze (EXT_VALUE 0b0111, `RX_TAPW`). Each step 60 s serial BER (`ber_long`, ≈ 8·10¹⁰ bits per direction).

| Step | gs TH_MON1/2, TAPW, OFFSET | m2→gs (gs RX, tuned) | gs→m2 (m2 RX, control) |
|---|---|---|---|
| A0 (TX_AMP 31) | +15 / +15, 0, 2 | 2.6·10⁻⁷ | 3.2·10⁻⁸ |
| m2 TX_AMP 24 | +15 / +15, 0, 0 | 8.3·10⁻⁸ | **7.9·10⁻⁷** |
| A | | 2.5·10⁻⁷ | 3.0·10⁻⁸ |
| m2 TX_AMP 16 | +15 / +15, 1, 1 | **3.6·10⁻⁸** | **1.0·10⁻⁶** |
| A | | 3.1·10⁻⁷ | 3.6·10⁻⁸ |
| m2 TX_AMP 10 | **11 / 11–12**, 0–1, 1–2 | 7.9·10⁻⁸ | **3.8·10⁻⁶** |
| A | | 2.2·10⁻⁷ | 3.6·10⁻⁸ |
| gs `freeze RX_TAPW` −4 / −2 / +2 / +4 (lab26) | **not applied** (see below) | 2.5 / 3.4 / 3.1 / 2.4·10⁻⁷ | 3.6 / 4.0 / 4.4 / 3.4·10⁻⁸ |
| A after each | | 2.7 / 2.5 / 1.3 / 2.7·10⁻⁷ | 4.4 / 4.6 / 3.5 / 3.8·10⁻⁸ |

**m2 TX_AMP 16 repeated (lab26b 15:28–15:33, same load, A/B/A ×2):** m2→gs 5.8·10⁻⁸ / 3.8·10⁻⁸ against A 2.7·10⁻⁷ / 2.8·10⁻⁷ (×5–7 better),
gs→m2 1.4·10⁻⁶ / 1.5·10⁻⁶ against A 4.4·10⁻⁸ / 4.0·10⁻⁸ (×30–40 worse). Every A step returns to the A0 level → the effect is causal and
reproduces 3/3. Lowering the m2 TX swing helps the gs receiver (the +15 rail / over-drive story) and hurts the m2 receiver of the other
direction; `TX_AMP` is a pure TX field (0x30[14:10], next to PRE/POST), so the coupling is physical (driver current on the shared SerDes
supply, or near-end crosstalk in the adapter) — UNVERIFIED which. Sum of both directions: A ≈ 3.1·10⁻⁷, TX_AMP 16 ≈ 1.5·10⁻⁶ →
**×5 worse for the link, not adopted.**

**TAPW pin — a write-protect upstream does not document (lab26b readback):** `freeze RX_TAPW=-8/-4/+4/+8` read back `RX_TAPW=0` with
EXT_VALUE 0b0111: `RX_EN_EQA_EXT_VALUE[2]` write-protects `RX_TAPW` as well, not only `RX_TH_MON1`. The lab26 TAPW steps and the lab26b
TAPW steps (m2→gs 3.2 / 2.1 / 1.1 / 3.0·10⁻⁷, = A) therefore measured the unchanged adapted tap. Upstream `tc_eyemeas(tapw_sweep=True)`
writes `RX_TAPW` after `eye_freeze` the same way, so its sweep pins nothing either (on these chips). Fixed: `eyescan.pin_fields` clears
EXT_VALUE, writes, enables EXT_VALUE last (test `test_upstream_tapw_sweep_write_is_blocked`, `test_freeze_pins_tapw_and_prints`).

**gs TAPW really pinned (lab26c 15:34–15:46, same load, readback −8 / −4 / +4 / +8):**

| gs RX_TAPW | m2→gs (gs RX) | A after it (adapted, TAPW 0) | gs→m2 (control) |
|---|---|---|---|
| A0 | — | 1.7·10⁻⁷ | 3.7·10⁻⁸ |
| −8 | **3.3·10⁻⁴** | 2.0·10⁻⁷ | 7.2·10⁻⁸ |
| −4 | **2.0·10⁻⁵** | 1.9·10⁻⁷ | 6.3·10⁻⁸ |
| +4 | 6.7·10⁻⁷ | 1.4·10⁻⁷ | 6.5·10⁻⁸ |
| +8 | **7.0·10⁻⁴** (gs checker restarted once) | 1.1·10⁻⁷ | 4.9·10⁻⁸ |

The DFE tap is a live knob on the gs receiver (×4000 over ±8 codes) and the bathtub is asymmetric (+4 ×30 better than −4).

**Fine TAPW sweep (lab26d 15:47–16:01, same load):**

| gs RX_TAPW (readback) | m2→gs (gs RX) | A after it (adapted 0) | gs→m2 (control) |
|---|---|---|---|
| A0 | — | 1.9·10⁻⁷ | 4.4·10⁻⁸ |
| −2 | 2.9·10⁻⁶ | 1.8·10⁻⁷ | 4.1·10⁻⁸ |
| −1 | 6.4·10⁻⁷ | 1.7·10⁻⁷ | 7.4·10⁻⁸ |
| +1 | 4.8·10⁻⁸ | 1.5·10⁻⁷ | 7.6·10⁻⁸ |
| **+2** | **6.7·10⁻⁹** | 9.7·10⁻⁸ | 6.7·10⁻⁸ |
| +3 | 4.4·10⁻⁸ | 9.7·10⁻⁸ | 5.4·10⁻⁸ |
| (+4, lab26c) | 6.7·10⁻⁷ | 1.4·10⁻⁷ | 6.5·10⁻⁸ |

**The bottom of the gs bathtub is TAPW +2, not the adapted 0:** ×15–28 lower m2→gs BER than the A steps around it, the control direction
unchanged. Why the adaptation misses it: both monitors are railed at +15 and the tap is computed as th1 − th2 = 0, so the DFE loop never
gets a gradient. This is the "calibration toward the eye" the vendor tools enable — with the eye itself measured as BER over the pinned tap,
because the eye counters do not run (17.3). Raw logs: `log26c/` (lab26c ran with the old log path `log26b`; its files were moved to `log26c/`; the lab26b
TAPW/A0 jsonl were overwritten by it — their totals are in `lab26b.out`).

**Confirmation on two fresh loads (lab27 16:02–16:47, 300 s per step, JTAG PEER 200/200 at start / B / end of both loads):**

| Load | A1 (adapted) m2→gs | **B: gs TAPW +2** m2→gs | A2 (adapted) m2→gs | gs→m2 A1 / B / A2 | exploratory m2 TAPW +2, 120 s: gs→m2 |
|---|---|---|---|---|---|
| r1 | 7.4·10⁻⁸ | **4.7·10⁻⁹** | 5.4·10⁻⁸ | 7.7·10⁻⁹ / 5.2·10⁻⁹ / 1.2·10⁻⁸ | 2.3·10⁻⁹ (m2→gs 8.2·10⁻⁸, gs adapted again) |
| r2 | 3.6·10⁻⁸ | **1.1·10⁻⁸** | 4.3·10⁻⁸ | 1.3·10⁻⁹ / 1.5·10⁻⁹ / 3.8·10⁻⁹ | 1.5·10⁻⁹ (= A, inconclusive) |

**gs TAPW +2 is better on every load tested (3/3: lab26d ×15–28, r1 ×11–16, r2 ×3–4), the control direction does not move.** The gain
depends on the load (the load scatter of §14.5/§16 remains). Recipe added to `/home/pi/fpga/README.txt` (bits unchanged; a JTAG step after
each load: `fpga-jtag gs run python3 eyescan.py freeze RX_TAPW=2`, undo `restore`). Baking it into the bitstream needs the regfile power-up
values `RX_EN_EQA=0`, `RX_TAPW=2`, `RX_EN_EQA_EXT_VALUE=0b0111` — not done (the freeze also stops the DFE and offset adaptation,
which is fine at 2.5 G on this channel but has to be re-checked at 5 G). PNG: `png/tapw_bathtub.png`, `png/calib_log2*.png`.

### 17.6 Uputa #333: Patrick's `serdes_lb.v` (mail UID 85) as a fix for `RX_EYE_MEAS_EN` — **does not fix it on our boards**

Built unchanged for both boards (`gateware/eye_cc/top_eye.v`: OUTDIV 2 = 2.5 G from the 100 MHz LVDS refclk, RX_POLARITY_I 1 for the
adapter P/N swap, PRBS-15 both ways, `RX_EYE_MEAS_CFG` {12'h800,3'b0}, `RX_EQA_LOCK_CFG` C, all RX resets overridden, TX_CALIB_EN 1,
PLL_CP 96 / AO A, TX_AMP 15; `eye_pu2g5_s1.bit` sha256 2627c71c…). Same bit on both (labeye 16:47–16:53):
PLL and CDR locked, `RX_PRBS_LOCKED=1` but `RX_PRBS_ERR_CNT` saturated (32767; this profile has DFE off, EQA not locked, no FFE on our
channel), `RX_EYE_MEAS_EN` stuck at 1 for 1.5 s at window 1…2048, all counters 0, `eye_diagnose` FAIL at the measurement on both.
Minimal change of our own bits, `ber_top` parameter `EYE_CFG` = 0x4000 (RX_EYE_MEAS_CFG 2048; LOCK_CFG is already C in PROFILE 1;
default 0 rebuilds gs_2g5 byte-identical 36f09752): gs f4a07905…, m2 91638802… — same result. Standard pair reloaded afterwards,
JTAG PEER 200/200. So neither the bitstream defaults nor the link data pattern start the engine here. Open for Patrick: chip revision
(IDCODE 0x20000001 both), a CFG/clock enable of the eye unit outside the regfile, or the exact board/bit where he saw it count.

### 17.7 Result of TASK-5525

- Ported: upstream eye path in `tools/serdestool.py` + `eyescan.py capture|diagnose|eye|freeze|restore`, 28 tests on a fake regfile
  (`tests/test_eye_cc.py`, `test_eye_cc_report.py`), green on the Pi (py3.7). Three upstream defects found and fixed in our copy:
  diagnose EXT 0b1111 check, negative offset into `RX_AFE_OFFSET`, and **`RX_TAPW` write-protected by `RX_EN_EQA_EXT_VALUE[2]`** (so
  `tc_eyemeas(tapw_sweep=True)` pins nothing) — to report to Patrick.
- E7 was wrong in two ways (0x06[11] locked `RX_TH_MON2`, monitor never routed); with the vendor sequence the freeze verifiably works,
  **but the eye counters still do not count** on either board, also with Patrick's own bitstream → no eye picture (64 × 31 scan not run).
- (b) answered: the gs RX_OFFSET movement is real (offset loop on a code boundary), not a read-out artefact.
- Calibration toward the operating point: the diagnose finding "thresholds railed at +15" explains why the DFE tap adapts to 0; pinning
  the gs tap to +2 lowers the m2→gs BER ×3–28 on 3/3 loads. Lowering m2 TX_AMP instead helps gs but costs the m2 receiver ×30–40 → rejected.
- 5 G P2: diagnose/capture only (CDR unlocked on both, BER 3·10⁻², gs thresholds 13–14 not railed, TAPW 2–3); no calibration attempted.

## 18. TASK-5527: after Goran's C143/C144 repair (15.10. 18:49) — calibration first (uputa #336), then 3 × 300 s — **no fixed recipe holds; the worse direction changes from load to load, and a TAPW +2 pin helps only the receiver that is bad on that load**

Goran 15.10. 17:46 "new measurement of the worse direction"; 18:32 pause (C143/C144 on M2, the 220 nF 0201 coupling caps of M2→GS, TASK-5524);
19:05 uputa #336: "first calibration/equalisation, only then the measurement". Same bits as §16/§17 (`/home/pi/fpga/{m2,gs}_2g5.bit`), lab22
procedure per load (m2 then gs `-r`, SET_ACC 2→0), no power cycle, metric = serial BER (`lab/ber_long.py`, both directions at once, gs own
counters for M2→GS, m2 counters carried in the gs UART line for GS→M2; 0 errors → 95 % upper bound). Raw: `docs/data_20261015/t5527/`
(`lab2[8-9]*`, `quick30.*`, `lab3[0-5].{sh,out}`, `log3*/`, `calib_table_lab30-32.md`, `calib_table_lab34.md`, `png33/`, `png35/`).
Tables: `tools/lab/calib_table.py` (PT lines → BER + ratio vs the nearest A row of the same load), `tools/lab/aba_table.py` (A1/B/A2).

### 18.1 Before the repair (17:45–18:33, lab28/lab29) — not valid any more

After the first change at 17:45 M2→GS was 1.0·10⁻²…4·10⁻² on every load (lab28 r1 A1/B/A2 300 s: 1.3·10⁻² / 4.1·10⁻² / 1.3·10⁻²) and no
gs RX lever (AFE_GAIN 1–8, PEAK 8–31, TAPW −4…+4, CDR CKP/CKI, EQA_LOCK_CFG; lab29, 20 s points) moved it below 1.5·10⁻². Goran found
the C143/C144 fault; lab29 was stopped at 18:33 and is kept only as a record.

### 18.2 quick30 (REGOČ 18:51, after the repair)

Both boards on JTAG, health without problems (PLL BISC flags as always), JTAG PEER 200/200 both, TH_MON +15 / +15 on both receivers, gs
RX_OFFSET 1, m2 7. 60 s: **M2→GS 8.9·10⁻¹¹, GS→M2 8.9·10⁻⁹** — the C143/C144 fault is gone, and on this load GS→M2 was the worse one.

### 18.3 Calibration screening (lab30/lab31 19:08–20:40 one load, lab32 two fresh loads 20:34–21:05)

The lab30 load came up the other way round: **M2→GS 1.5–3.3·10⁻⁷, GS→M2 0–2·10⁻¹¹**. Every change undone before the next, A rows in
between (30 s points, the offset block 60 s). Full tables in `calib_table_lab30-32.md`; the levers that matter:

| Lever (one load, lab30/31) | M2→GS (A ≈ 1.5–3·10⁻⁷) | GS→M2 (A ≈ 0–1·10⁻¹⁰) | Verdict |
|---|---|---|---|
| m2 RX TAPW −2…+3, AFE_GAIN 1–8, PEAK 8–31, CDR CKP/CKI, EQA_LOCK_CFG, AFE offset 6/8 | unchanged | ×3–1000 **worse** or unchanged | m2 RX stays adapted (on this load GS→M2 had no resolution, see 18.5) |
| gs RX AFE_GAIN 1–8 / PEAK / CDR / LOCK_CFG | ×1 … ×5 worse | unchanged | rejected |
| gs RX AFE offset pinned (uputa #337: 1, 0, 3; freeze control without override 2.6·10⁻⁷) | 1.1·10⁻⁷ / 4.5·10⁻⁸ / 3.2·10⁻⁷ | unchanged | at most ×4 → **not the recipe**; the load-start offset 1↔2 correlates with good/bad loads but pinning it does not reproduce a good load |
| **gs RX TAPW +2 (pin)** | **3.2·10⁻¹⁰** (lab30, ×700) / 1.8·10⁻⁸ (lab31, ×11); +1 1.9–4·10⁻⁸, +3 2.2·10⁻⁸, −1 1·10⁻⁶ | unchanged | best single lever on a bad M2→GS load |
| gs TX_AMP 16 / m2 TX_AMP 24–16 | 4.7·10⁻¹⁰ / 2.5–5·10⁻⁸ | 4·10⁻¹⁰ / **1.2–3.2·10⁻⁹** | lowering a TX amplitude helps one direction and costs the other (as lab26) |
| m2 TX_SEL_POST 10 | 2.0·10⁻⁸ (×9) | unchanged | candidate |
| m2 TX_BRANCH_EN_PRE 0 / gs BRANCH_EN_POST 0 | 8.8·10⁻¹⁰ / 2.5·10⁻⁹ | 4.8·10⁻¹⁰ (×20 worse) / unchanged | rejected / unstable (lab32 r2 ×10 worse) |

Recipe selection on two fresh loads (lab32, 60 s per recipe, `calib_table_lab30-32.md`): r1 (M2→GS A 2.9·10⁻⁸/7.7·10⁻⁹) R1 gs TAPW+2
2.6·10⁻⁹, **R5 = gs TAPW+2 + m2 TX_SEL_POST 10: 8.0·10⁻¹⁰ (GS→M2 2.0·10⁻¹⁰)**, R4 gs TX_AMP 16 1.3·10⁻¹⁰ but GS→M2 1.0·10⁻⁹; r2 (a good
M2→GS load, A 3.2·10⁻⁹/4.9·10⁻⁹) R5 3.9·10⁻⁹ (= A), R1 9.1·10⁻⁹, R4 GS→M2 1.1·10⁻⁸. R5 was chosen (21:08, chat) as the best balance.

### 18.4 Step 2 — measurement with R5, 3 fresh loads × A1/B/A2 300 s (lab33 21:06–22:05) — **R5 rejected**

JTAG PEER 200/200 at start / B / end of every load; health without problems; throttled 0xd0005 at r1/r2 start (under-voltage flag of the
Pi itself, as in lab28), 0xd0000 at r3. B = gs `freeze RX_TAPW=2` + m2 `set TX_SEL_POST=10`, undone before A2 (`png33/aba.png`).

| Load (gs RX_OFFSET at start) | M2→GS A1 | **M2→GS B (R5)** | M2→GS A2 | GS→M2 A1 | GS→M2 B | GS→M2 A2 |
|---|---|---|---|---|---|---|
| r1 (0/1/2) | 5.6·10⁻¹² | ≤ 8.4·10⁻¹² (0 err) | 5.0·10⁻¹² | 8.4·10⁻¹² | ≤ 8.4·10⁻¹² (0 err) | 1.0·10⁻¹¹ |
| r2 (1/2) | 2.2·10⁻⁹ | **1.7·10⁻⁸** | 1.2·10⁻⁹ | 1.7·10⁻⁸ | 1.7·10⁻⁸ | 1.9·10⁻⁸ |
| r3 (1) | 8.5·10⁻¹⁰ | **2.9·10⁻⁸** | 4.1·10⁻⁹ | 3.6·10⁻⁸ | 2.4·10⁻⁸ | 6.0·10⁻⁸ |
| median | 8.5·10⁻¹⁰ | 1.7·10⁻⁸ | 1.2·10⁻⁹ | 1.7·10⁻⁸ | 1.7·10⁻⁸ | 1.9·10⁻⁸ |

r1 is the best load ever recorded on this pair (both directions ≈ 10⁻¹¹ without any recipe). On r2 and r3 M2→GS was already good
(≈ 10⁻⁹) and **R5 made it ×7–30 worse**, while GS→M2 was the bad direction (1.7–6·10⁻⁸) and R5 does not touch the m2 RX. So the
recipe chosen on the lab30–32 loads (where M2→GS was bad) is not a recipe for the pair.

### 18.5 Why: the pin helps only the receiver that is bad on that load (lab34 on lab33-r3, lab35 conditional rule on 3 fresh loads)

lab34 (22:10–22:25, the r3 load kept, 60 s points, `calib_table_lab34.md`): GS→M2 A 4.9–5.6·10⁻⁸ — m2 TAPW +1 1.6·10⁻⁸, **+2 9.8·10⁻⁹,
+3 8.7·10⁻⁹**, −1 3.3·10⁻⁷, +4 7.0·10⁻⁸; m2 AFE offset pinned 8 5.0·10⁻⁹, 6 8.5·10⁻⁸; and **gs TAPW +2 on this good M2→GS (9·10⁻¹⁰)
→ 1.0·10⁻⁷**. Together with lab30 (gs pin on a bad M2→GS ×700) and lab30 (m2 pin on a good GS→M2 → ×50–1000 worse): the tap +2 is
the bottom of the bathtub only when the adapted point (tap 0, thresholds on the +15 rail) is the bad one; otherwise it moves a good
receiver off its point. The DFE cannot find this itself while TH_MON is railed (Dora, SERDES_UMJERAVANJE_KAKO_DRUGI §6: no gradient at
the DAC rail → the adapted point depends on the start conditions = the "load lottery").

lab35 (22:26–23:15, `png35/aba.png`), rule per load: A1 120 s; a direction with BER > 5·10⁻⁹ gets TAPW +2 on its receiver; B 300 s; A2 300 s.

| Load (gs offset) | M2→GS A1 / B / A2 | GS→M2 A1 / B / A2 | Rule |
|---|---|---|---|
| r1 (2) | 1.5·10⁻⁷ / **4.0·10⁻⁹** / 1.2·10⁻⁷ | 1.8·10⁻¹⁰ / 2.8·10⁻¹⁰ / 1.7·10⁻¹⁰ | pin gs (×34) |
| r2 (–) | 6.4·10⁻¹² / 1.4·10⁻¹¹ / 1.4·10⁻¹¹ | 4.7·10⁻⁹ / 7.4·10⁻⁹ / 4.8·10⁻⁹ | none (GS→M2 just below 5·10⁻⁹) |
| r3 (–) | 4.2·10⁻¹⁰ / 8.8·10⁻¹⁰ / 1.7·10⁻⁹ | 1.9·10⁻¹¹ / 2.6·10⁻¹⁰ / 6.6·10⁻¹⁰ | none |

The rule repairs the bad receiver (×34) and leaves good loads alone, but the worst load after the rule is still ≈ 4–7·10⁻⁹, not < 10⁻⁹
(G9). Over the 10 loads after the repair (first A step of quick30, lab30, lab32 ×2, lab33 ×3, lab35 ×3) the median of the adapted A is
M2→GS 1.5·10⁻⁹ (range 5.6·10⁻¹²…1.5·10⁻⁷) and GS→M2 4.4·10⁻¹⁰ (8.4·10⁻¹²…3.6·10⁻⁸); the worse direction is M2→GS on 5 loads, GS→M2
on 4, one tie (lab33 r1). Compared with the morning (§16: median gs→m2 3.6·10⁻¹⁰, m2→gs 4.1·10⁻⁹) M2→GS is ×2.7 better in the median,
GS→M2 about the same; the load-to-load spread (4–5 decades) is unchanged.

### 18.6 Uputa #338 P1/P2 (EYE_MEAS_UZROK.md §4) — **W/C strobes execute; only the eye engine is dead** (lab36 23:14–23:20)

PRBS-15 gs TX → m2 RX checker (`tools/lab/strobe_probe.py`, one board per `fpga-jtag … run`): RX_PRBS_LOCKED 1, ERR_CNT 0→1 in ~10 s.
- **P1:** gs `TX_PRBS_FORCE_ERR` ×200 (7.8 s) and ×20 → m2 `RX_PRBS_ERR_CNT` 1 → **32767** (saturated) both times, field reads back 0
  (self-cleared). m2 `RX_PRBS_CNT_RESET` → ERR_CNT 32767 → **0** with no extra TCK, field reads back 0. So W/C strobes are executed
  through the JTAG path with `REGFILE_CLK_I = 0` → **H-A (no W/C strobe ever executes) is false** for these two strobes.
- **P2:** after the upstream freeze, `RX_EYE_MEAS_CFG` 15, `RX_EYE_MEAS_EN` 1 and then 0 / 10⁵ / 10⁶ TCK in Run-Test/Idle (up to
  4.8 s): 0x14 = 0x00F1 (EN still 1), counters 0x16–0x1D all 0. Extra TCK changes nothing.
- So the dead part is the eye measurement engine itself (H-B: silicon revision or an enable outside the regfile) → question to Patrick,
  P3 (free clock on `REGFILE_CLK_I`) is not expected to help. Side effect for G7: an RX reset strobe over JTAG most likely does execute.
- After lab36 the standard pair was reloaded, JTAG PEER 200/200 on both.

### 18.7 Uputa #338 G2 — adapt on PRBS-15, then freeze (lab37 23:32–00:13, 5 fresh loads, 60 s per step) — **helps the bad loads, can break a good one**

Per load: A1 (adapted on the 8b10b frame as always) → both TX `TX_PRBS_OVR/SEL=2` (PRBS-15) 5 s → `eyescan freeze` on both RX (EN_EQA 0,
EXT 0b0111, op pinned) → PRBS off → B → `restore` → A2 (`png37/aba.png`). The first lab37 attempt (23:20–23:33) ran in **two instances**
(my chaining error: an earlier `setsid nohup` chain thought dead was alive) — its output is kept as `lab37_dup_contaminated.out` and not used.

| Load | M2→GS A1 / **B** / A2 | GS→M2 A1 / **B** / A2 | op frozen on PRBS (m2 / gs offset) |
|---|---|---|---|
| r1 | 4.8·10⁻¹¹ / **1.6·10⁻⁸** / 7.5·10⁻⁹ | ≤3.6·10⁻¹¹ / **4.4·10⁻⁸** / 3.3·10⁻⁷ | 2 / 0 |
| r2 | 2.9·10⁻⁸ / **5.3·10⁻⁹** / 2.1·10⁻⁸ | 1.4·10⁻⁹ / **≤3.8·10⁻¹¹** / 7.5·10⁻¹⁰ | 2 / −1 |
| r3 | 9.0·10⁻⁹ / **≤3.9·10⁻¹¹** / 1.5·10⁻¹⁰ | 5.5·10⁻¹⁰ / **≤3.9·10⁻¹¹** / 1.3·10⁻⁹ | 2 / 0 |
| r4 | 3.9·10⁻⁹ / **4.9·10⁻¹⁰** / 3.2·10⁻⁹ | 1.2·10⁻⁸ / **5.4·10⁻¹⁰** / 1.0·10⁻⁸ | 2 / 0 |
| r5 | 1.3·10⁻¹¹ / **≤3.6·10⁻¹¹** / 1.6·10⁻¹⁰ | 5.2·10⁻¹¹ / **≤3.6·10⁻¹¹** / 9.7·10⁻¹¹ | 2 / 0 |

Worse direction per load, median: A1 9·10⁻⁹ → **B 5.4·10⁻¹⁰**; on r3 and r5 zero errors in both directions. On PRBS the offset loop settles
at m2 2 (on the frame always 7) and gs 0/−1 (frame 1–3). r1 (a very good load) was broken by the PRBS episode and stayed bad after
`restore` too (A2 3.3·10⁻⁷) — so G2 is used only as a rule for a load that fails the acceptance test, never on a good load (18.10).

### 18.8 Uputa #338 G3 — symmetric TX swing (lab38 00:13–01:20, 3 fresh loads, 60 s per point, `calib_table_lab38.md`)

Both TX together, default FFE 5/5; then FFE off (SEL_PRE = SEL_POST = 0) at 31 and 20.

| Load | worse direction A (31) | 24 | 20 | 16 | **12** | FFE off 31 / 20 | TH_MON gs / m2 at 12 |
|---|---|---|---|---|---|---|---|
| r1 | M2→GS 6·10⁻¹⁰–1·10⁻⁸ | 4.8·10⁻¹⁰ | 1.1·10⁻⁸ | **2.6·10⁻¹¹ (both)** | 2.2·10⁻¹⁰ | 4.5·10⁻⁷ / 3.3·10⁻⁸ | 12 / 14 |
| r2 | M2→GS 5.4·10⁻⁷ | 3.1·10⁻⁷ | 3.3·10⁻⁷ | 6.6·10⁻⁸ | **1.5·10⁻⁸** | 2.0·10⁻⁵ / 2.6·10⁻⁶ | 13 / 14 |
| r3 | GS→M2 2.1–2.5·10⁻⁸ | 7.8·10⁻⁸ | 4.9·10⁻⁸ | 1.7·10⁻⁸ | **6.0·10⁻¹⁰** (M2→GS 5.3·10⁻⁹) | 3.7·10⁻⁸ / 6.8·10⁻⁸ | 12 / 15 |

Symmetric 12 lowers the worse direction ×4–36 on 3/3 loads and the thresholds leave the +15 rail (Dora's G3 criterion), the other
direction does not get worse (asymmetric changes in §18.3 always cost the other direction). FFE off is ×40–40 000 worse for M2→GS.
**G3 does not remove the load-to-load difference** (r2 stays 1.5·10⁻⁸), so — uputa #339 — the parameter search stops here.

### 18.9 Uputa #338 G7 — map RX_AFE_OFFSET → RX_OFFSET (lab38, end, both boards identical)

`freeze RX_AFE_OFFSET=v --ext 0b1111`, read `RX_OFFSET` (0x07[13:10]) for v = 0…31 (`MAP` lines in `lab38.out`):
v 0…7 → 0…+7, **v 8 (default) → 0**, v 9…15 → −7…−1, v 16…31 repeat 0…15 (bit 4 is not visible in the readout). So to pin the point
read as r: AFE = r for r ≥ 0, AFE = 16 + r for r < 0 (upstream `eye_freeze` writes r itself, which is wrong for r < 0, §17.1).
"Retry by offset" (G7 b) is not supported by the data: start offset vs M2→GS A over the 8 loads with a recorded start offset — gs 1: 8.9·10⁻¹¹, 8.5·10⁻¹⁰ but also 2.9·10⁻⁸;
gs 2–3: 1.5·10⁻⁷ ×2, 5.4·10⁻⁷, 3.1·10⁻⁹ but also 6.1·10⁻¹⁰. A BER gate after the load (60 s) is the reliable test → used in 18.10.

### 18.10 Uputa #339 PROOF (lab39 01:20–07:59): repeatability of link establishment + overnight soak

Recipe (unchanged bits `m2_2g5.bit` b1b98a5d…, `gs_2g5.bit` 36f09752…): load m2 then gs (`-r`), SET_ACC 2→0, **TX_AMP 12 on both TX**.
Acceptance: both directions < 10⁻⁹ in 60 s serial BER. Rule if not: G2 (18.7) and 60 s again; still not: reload (≤ 3 loads per trial).
(B) 10 trials (t_link, PEER 200/200 both, BER per attempt), then (A) reload until accepted and soak on that one load until 07:58
(REGOČ shortened the 8 h soak to end at 08:00, uputa #340; hourly report by REGOČ), 60 s snapshots, both RX lock/TH_MON/OFFSET +
Pi temperature/throttled every 15 min. Results in 18.11.

### 18.11 Proof result (lab39, 21 fresh loads + 4.79 h soak) — **the link always comes up and holds without a single restart, but at BER ≈ 4–8·10⁻¹⁰, not error-free; only every second load passes the 1e-9 gate**

Raw: `docs/data_20261015/t5527/{lab39.sh,lab39.out,log39/}`; table and picture `png39/proof_table.md`, `png39/proof.png`, made by
`tools/lab/proof_table.py` (+4 tests); summary for Goran (Croatian) `png39/SERDES_DOKAZ_LAB39_20261016.pdf` (`png39/make_pdf.py`). Bits as 18.10 (sha256 `m2_2g5.bit` b1b98a5d946169d1…, `gs_2g5.bit` 36f09752d8b85ebd…), Pi
`throttled=0xd0000` (past under-voltage flags only; 0xd0005 at 3 of 19 reads = under-voltage now), Pi temperature 53.7–58.5 °C.

**(B) Repeatability, 21 fresh loads** (10 trials + 2 soak loads):

| | count |
|---|---|
| link up, JTAG PEER 200/200 both directions | **21/21**, t_link 40.8–51.3 s (end of gs load → PEER 10/10 both, first poll) |
| accepted on the first 60 s (both < 1e-9) | **7/21** (33 %) |
| + accepted after the G2 rule | +3 → **10/21** (48 %) |
| trials accepted within ≤ 3 loads | **9/10** (t1: 3 loads, all M2→GS 1.5–4.2·10⁻⁸ even after G2) |
| worse direction on the 14 loads failing the first 60 s | **M2→GS on 12/14** (1.0·10⁻⁹…2.7·10⁻⁷); GS→M2 on t1_l3, t4_l1, both within ×1.1 |

Start offset was gs 1–3 / m2 7 on every load and does not separate good from bad loads (again, 18.9). G2 ran on the 14 loads that
failed the first 60 s: it turned 3 into accepted, M2→GS got better on 7 and worse on 7 (e.g. t3_l1 9.3·10⁻⁹ → 1.8·10⁻⁸, t6_l1
1.0·10⁻⁹ → 7.9·10⁻⁹) — the reload is what really works.

**(A) Soak on load soak_l2** (accepted first try: M2→GS 3.1·10⁻¹⁰, GS→M2 4.8·10⁻¹¹), 03:10–07:58, 278 × 60 s snapshots, all UART reads OK:

| Direction | bits | bit errors | BER | 95 % interval | 60 s intervals with 0 errors | checker restarts |
|---|---|---|---|---|---|---|
| M2→GS | 2.16·10¹³ | 17 844 | **8.3·10⁻¹⁰** | 8.15–8.39·10⁻¹⁰ | 0 / 278 | 0 |
| GS→M2 | 2.16·10¹³ | 8 953 | **4.2·10⁻¹⁰** | 4.06–4.24·10⁻¹⁰ | 19 / 278 | 0 |

Hourly M2→GS 6.4 / 5.9 / 10 / 7.3 / 13 ·10⁻¹⁰ (last hour 0.79 h), GS→M2 4.9 / 1.6 / 1.5 / 5.3 / 8.4 ·10⁻¹⁰; worst single minute
1.1·10⁻⁸ / 9.9·10⁻⁹. No burst, no loss of sync (`synced`/`psynced` 1 on every read), PEER 200/200 both at the end. Every 15 min both RX
CDR and EQA locked, EQA running, TH_MON gs 12–13 / m2 14 (off the +15 rail, G3), RX_OFFSET gs 1–2 / m2 2–3, TAPW gs 0–1 / m2 1 — one
read (04:57) gave m2 RX_CDR_LOCKED=0 with no trace in the BER of that minute (GS→M2 9·10⁻¹¹) and no restart, so it is a single glitch
of the status bit or a sub-second slip, not a lock loss.

Compared with the reference: morning 2.5 G (TASK-5522/5523, default TX_AMP, 300 s, median) GS→M2 3.6·10⁻¹⁰ / M2→GS 4.1·10⁻⁹; lab27
(TASK-5525, gs TAPW +2) M2→GS 4.7·10⁻⁹ / 1.1·10⁻⁸. After the C143/C144 repair + TX_AMP 12 + BER gate the accepted load holds
M2→GS at 8.3·10⁻¹⁰ for 4.8 h — about **×5 better than the morning median** of M2→GS, and the two directions are now within ×2.

**What this proves and what it does not** (for the HW revision, Goran 15.10. 23:59):
- proven: with unchanged bits the 2.5 G link comes up on every load in < 52 s and an accepted load runs 4.8 h with 0 restarts,
  0 lost syncs and a stable BER (no drift beyond ×2 between hours);
- not proven: an error-free link. ~1 bit error per second in M2→GS (17 844 in 17 257 s on the 1.25 Gb/s checked payload); a 10⁻¹² link would need
  ~×800 less. As is, a long fast link needs FEC/CRC+retransmit on top, or a better channel;
- not proven: a fixed recipe. Only 48 % of loads reach < 1e-9, and which one is decided by the load itself (the scatter of §18.4–18.5
  stays); the gate + reload is a procedure, not a fix. The cause of the load-to-load scatter is still open (eye engine dead, §18.6).
- 5 G was not part of lab39 (unchanged, TUNING_5G.md).


## 19. TASK-5531 — lab39 recipe baked into the bitstream for a flash boot (16.10.2026, Goran 09:00)

### 19.1 What of the lab39 recipe can live in the bits

| lab39 step after every JTAG load | In the bits now | How / why |
|---|---|---|
| TX_AMP 12 on both TX | **yes** | build parameter `OV_TX_AMP 12` (exists since TASK-5483, no `ber_top.v` change). Control rebuild of both old bits byte-identical (gs 36f09752…, m2 b1b98a5d…); the new `.txt` differs in exactly one line, `TX_AMP 11111 → 01100`. Test `tools/tests/test_tx_amp_bake.py` (3 tests) |
| `RX_CDR_SET_ACC_CONFIG` 2→0 pulse | **not needed — no sequencer built** | the pair has `RX_CDR_CKI=0` (frequency integrator off). The start-up trap of `LOCAL_REFCLK_M2.md` §4C (FREQ_ACC at the rail) was seen only with CKI ≠ 0 (cki1/cki2 bits); §11.2 already called the pulse "harmless with CKI 0". lab40 confirms it on 6/6 loads: right after the load, with no write, `RX_CDR_LOCKED=1`, `RX_EQA_LOCKED=1`, `SET_ACC_CONFIG=0`, `FREQ_ACC_VAL=0` on both. The pulse ends at 0 = the power-up value anyway |
| G2 (PRBS-15 adapt + freeze) | no | a conditional runtime rule (§18.7: it can break a good load); stays a JTAG step |

Bits: `ber_m2_2g5_p1_txneg_amp12_s2_CFGRST.bit` 3f4857df… = Pi `/home/pi/fpga/m2_2g5_auto.bit`,
`ber_gs_2g5_p1_txneg_amp12_s7_CFGRST.bit` 99d80788… = `gs_2g5_auto.bit`; both `gmpack --reset`, `gm_cfgrst_check` → CFGRST,
hold violations 0, Fmax as the old pair (gs tclk 85.8 / rclk 50.9 MHz, m2 79.7 / 77.5 MHz). Build:
`LINK=ber_link_gs.v FREQ=40 ./build_ber.sh gs 2g5p1_txneg_amp12 7 N1 1 N2 5 N3 5 OUTDIV 2 PROFILE 1 TX_NEG 1 OV_TX_AMP 12`,
m2 the same without `LINK`, seed 2.

### 19.2 SRAM check with NO JTAG write after the load (lab40 09:04–09:24, 6 fresh loads, m2 then gs `-r`)

Only reads (`eyescan.py get`, read-only `ber_jtag_check`, gs UART `ber_long`). Raw: `docs/data_20261016/t5531/`.

| Load | t_link (PEER 10/10 both) | PEER 200/200 | 60 s gs→m2 | 60 s m2→gs |
|---|---|---|---|---|
| l1 | 33.1 s | both PASS | 3.1·10⁻⁸ | 1.2·10⁻⁸ |
| l2 | 32.2 s | both PASS | 3.7·10⁻¹⁰ | 2.0·10⁻⁸ |
| l3 | 33.8 s | both PASS | 1.1·10⁻¹⁰ | 1.5·10⁻⁹ |
| l4 | 31.8 s | both PASS | 3.2·10⁻¹⁰ | 1.1·10⁻⁹ |
| l5 | 32.9 s | both PASS | 8.5·10⁻¹⁰ | 4.1·10⁻⁹ |
| l6 | 39.3 s | both PASS | 0 (< 3.8·10⁻¹¹) | 2.0·10⁻⁹ |

- **The link comes up by itself on 6/6 loads**, 31.8–39.3 s (lab39 with the JTAG steps: 40.8–51.3 s), 0 restarts.
- BER is in the lab39 first-try spread: worse direction median 3.1·10⁻⁹ (lab39 first try over 21 loads: 9.3·10⁻⁹, range
  9.7·10⁻¹¹…2.7·10⁻⁷). The 1e-9 gate in 60 s: 0/6 here vs 7/21 in lab39 (P(0/6 | p = 1/3) = 9 %, so not a proven difference).
  Without G2 and without the reload gate a flash boot gets "a random load": expect 10⁻⁹…10⁻⁸ in the worse direction, not
  the 8.3·10⁻¹⁰ / 4.2·10⁻¹⁰ of the selected lab39 soak load.

### 19.3 SPI flash — not written (uputa #342: independent review TASK-5532 first) + an open access problem

- Not written: Goran 09:12, the init must pass Kosjenka's review (TASK-5532, `docs/REVIEW_INIT_20261016.md`) before the flash.
- Read-only preparation found that the flash is **not reachable over JTAG today**: `fpga-jtag gs|m2 --detect -f` →
  `Read Flash 0 0 0 0 Fail / Read ID failed` on both boards, also at 1 MHz and 200 kHz TCK. The configured SRAM design
  survived the tool's reset pulse (link still up, TX_AMP 12 read back), i.e. the DirtyJTAG GPIO the CologneChip driver uses
  as RSTN (`_rstn_pin = 1<<6`) does not reset these FPGAs, so the JTAG-SPI bypass (IR 0x05) runs on a configured chip.
  Hypothesis (unproven): the bypass only reaches the flash while the chip is unconfigured / in reset. Without a working
  read the old flash content cannot be backed up and a write cannot be verified.

### 19.4 Flash access found, GS backup, Goran writes the flash himself (16.10. 09:46–10:05, uputa #343/#344)

- **The cause of `Read ID failed` is the design in SRAM, not a setting.** GS 09:50 with the amp12 ber bit
  configured: `fpga-jtag gs --dump-flash --freq 1000000` → `Read Flash Fail / Read ID failed`. 09:51, the same command
  after `fpga-jtag gs <np1817.bit> -r` (LiteX, the bit TASK-5224 had in SRAM when the flash worked on 04.10.) → read OK.
  The ber `.ccf` uses no bank-WA pin (JTAG, CFG_MD and the config SPI live there), so this is not a pin clash; why the
  ber designs block the JTAG-SPI bypass is not known. Rule: **before `-f`, load a non-SerDes bit with `-r`**.
- **P1 — image for the way back (GS):** 4 MiB dump `~/t5531/flash_before_T5531_gs.bin` on the Pi (1 m 56 s at 1 MHz),
  sha256 `74b3accf…`; the first 1 286 336 B = np1817 (`dcf82c64…`, the TASK-5224 write), the rest 0xFF (0 non-FF bytes).
  Undo = `fpga-jtag gs -f --verify --freq 1000000 /home/pi/FPGA/ETH_GateMateA1_2909_1015_Linux_GbE_DVI_USBPNRU_pll60s2_np1817.bit`.
  M2 flash: not read (uputa #344 came first).
- Uputa #344 (Goran 09:51): Goran writes `gs_2g5_auto.bit` → GS and `m2_2g5_auto.bit` → M2 himself; we do not touch
  flash or boards until he reports the reset. Sent to the chat at 09:5x: the GS SRAM holds np1817 now (so the GS write
  can go straight away), M2 still runs the ber design (load a non-SerDes bit with `-r` first).
- P4 tool ready: `tools/lab/p4_flash_boot.sh` (reads only: SerDes regs incl. TX_AMP = 12 as the proof that the flash bits
  booted, PEER 200, 300 s BER) and `ber_long.py` now also writes `SYNC … frac … dloss` (REVIEW_INIT N4/N5: synced share
  = words / (t25 s × sender word rate), Δloss summed mod 32 per 60 s interval); 4 new tests in `test_ber_long.py`.
- Correction (REVIEW_INIT 🟢): the §19.2 "t_link 31.8–39.3 s" is the duration of the first PEER poll pair (polls = 1), i.e.
  the link was already up when it was asked; it is an upper bound, not the link-up time.
