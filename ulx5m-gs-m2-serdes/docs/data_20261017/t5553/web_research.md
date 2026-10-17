# TASK-5553: web and local research on CC_SERDES (RX_EQA_CKP_OFFSET, settings, tuning method)

Date: 2026-10-17. Read-only research. No hardware, Pi or boards were touched.
Tags: **SOURCE-VERIFIED** = read in the source (URL or file:line given). **INFERRED** = my conclusion, not stated anywhere.

Short names for local paths:
- `UP` = `/home/klaudio/app/raid/projekti/ulx5m-litex-ai/ulx5m-gs-m2-serdes/tools/upstream_cc_20261015/serdestool.py` (Cologne Chip, P. Urban, 2026-10-15)
- `UPV` = `.../ulx5m-gs-m2-serdes/gateware/upstream_cc_20261015/serdes_lb.v`
- `DS26` = `/home/klaudio/app/raid/work/tmp-arhiva/serdes_research/ds26.txt`, the text of DS1001 **September 2026** (https://colognechip.com/docs/ds1001-gatemate1-datasheet-latest.pdf)
- `UG` = `/home/klaudio/app/raid/work/tmp-arhiva/serdes_research/UG1001--Primitives-Library.txt` (UG1001 July 2024)
- `R` = `/home/klaudio/app/raid/work/tmp-arhiva/serdes_research/repos/` (local clones: gm_serdes_lb @56aa48b, gatemate-pipe, openCologne(-PCIE), prjpeppercorn, nextpnr, yosys, liteeth-pucc)
- `PP` = `/home/klaudio/app/raid/tools/nextpnr-a2fix/prjpeppercorn` @6db2eaf (2026-09-29)
- `NP` = `/home/klaudio/app/raid/tools/nextpnr-main-ad8527f/src/himbaechel/uarch/gatemate/`

---

## 1. RX_EQA_CKP_OFFSET: writing 0 or 2 reads back 1

### 1.1 What the sources say

| # | Claim | Tag / source |
|---|---|---|
| 1 | DS1001 Sep 2026, Table 2.59: `0x04 r/w [7:0] 0x01 RX_EQA_CKP_OFFSET`, `r/w [8] RX_EN_EQA`, `r/w [12:9] RX_EQA_LOCK_CFG`, `r [13] RX_EQA_LOCKED`, `r [15:14] unused`. The datasheet documents the field as plain R/W. It has no note about it being locked or overridden. | SOURCE-VERIFIED, DS26 p.90 (lines 3640-3700) |
| 2 | DS1001 Table 2.44: "RX_EQA_CKP_OFFSET 8 r/w 0x01 *Proportional coefficient of control loop for offset detection*". CKP_LF and CKP_HF (0xA3) are the "proportional coefficient of control loop for low/high frequency amplitude detection". RX_EQA_LOCK_CFG: bit0 reserved, bit1 selects the monitor output for capture, bit2 turns on divide-by-2 for the tap weight, bit3 chooses LF (0) or HF (1) amplitude. RX_EQA_CONFIG (0x01C0) has no bit description. | SOURCE-VERIFIED, DS26 p.80 |
| 3 | The same bit position is used in prjpeppercorn `add_word_settings("RX_EQA_CKP_OFFSET", (0x04<<4)+0, 8)`, in serdestool `{'addr':0x04,'hbit':7,'lbit':0,'val':1}` and in nextpnr `{id_RX_EQA_CKP_OFFSET, 8, 0x01}`. The bit position therefore agrees across DS, bitstream DB and JTAG tool. | SOURCE-VERIFIED, PP `libgm/src/TileBitDatabase.cpp:446`; UP:348; NP `pack_serdes.cc:52` |
| 4 | Every public design keeps the default 0x01: the CC examples (UG1001 cc_serdes_inst.v, gm_serdes_lb, serdes_lb in openCologne and prjpeppercorn-test-cases), the gatemate-pipe wrapper and testbench, liteeth gatemate_1000basex and serdes_gm.py. I found **no one** who has ever written a different value, at either bitstream time or runtime. | SOURCE-VERIFIED, `grep -rn CKP_OFFSET R/` (e.g. `R/gatemate-pipe/src/ccfpga_pipe_wrapper.v:140`, `R/liteeth-pucc/liteeth/phy/gatemate_1000basex.py:150`) |
| 5 | The Cologne Chip testbench writes the loop coefficients as **3 + 5 bit groups**: `RX_EQA_CKP_HF = 8'b101_00011`, `RX_EQA_CKP_LF = 8'b101_00011`, `RX_EQA_CKP_OFFSET = 8'b000_00001`, `RX_CDR_CKI = {3'b000, 5'b00000}`. | SOURCE-VERIFIED, `R/openCologne-PCIE/5.sim/tb_ccfpga_serdes.v:302-305,320` (same in `R/gatemate-pipe/sim/tb_ccfpga_serdes.v`) |
| 6 | From #5: the 8-bit CKP coefficients are probably {3-bit exponent/shift, 5-bit mantissa}. The default OFFSET would then be mantissa 1 with shift 0, the smallest non-zero gain. Under that encoding 0 = loop off and 2 = twice the gain (or, for 0x20, a different shift). | INFERRED |
| 7 | **Documented precedent for silently blocked writes in the same register block.** Upstream serdestool: "two fields are write-protected and a blocked write fails silently: 1. RX_EN_EQA must be 0 BEFORE RX_EQA_CONFIG is written. The register file freezes RX_EQA_CONFIG while the adaptation engine is enabled ... 2. RX_TH_MON2 is write-protected while RX_EN_EQA_EXT_VALUE[3] is set". `eye_freeze()` therefore writes `RX_EN_EQA=0` first. | SOURCE-VERIFIED, UP:1354-1397 |
| 8 | DS1001 does not mention the RX_EQA_CONFIG lock either. The datasheet is therefore known to leave out runtime write interlocks. | SOURCE-VERIFIED (DS26 p.80 lists RX_EQA_CONFIG as plain r/w) + UP:1361 |
| 9 | **Documented precedent for a misdocumented register map.** prjpeppercorn PR #20 (pu-cc, merged 2026-06-16): "the SERDES register file contents at address 0x2B were incorrectly documented". The RX_*RESET_OVR bit order was shifted by 2. | SOURCE-VERIFIED, https://github.com/YosysHQ/prjpeppercorn/pull/20 (commit b1eb52f4). PP @6db2eaf already includes it. |
| 10 | In our setup the readback was taken at runtime with `RX_EN_EQA=1` (PR_BUILD §: `RX_EN_EQA=1, CKP_OFFSET=1, LOCK_CFG=12`), over JTAG, with mask 0x00FF. TX_SEL_PRE (0x30) writes stick. | SOURCE-VERIFIED, `ulx5m-gs-m2-serdes/docs/PR_BUILD_20261016.md:138`, `docs/CHAIN4_5G_P2_20261017.md:60-71`, `tools/eyescan.py:232-240` |
| 11 | No web hits at all for `RX_EQA_CKP_OFFSET` / `RX_EN_EQA` outside the code repositories. There is no Cologne Chip forum thread, issue or errata on it. | SOURCE-VERIFIED (WebSearch 2026-10-17; GitHub issue search "gatemate serdes": 20 hits, none about EQA) |

### 1.2 Hypotheses and how to tell them apart (all INFERRED)

| H | Explanation | Fits "0 -> 1 and 2 -> 1"? | Discriminating test (cheap, one board) |
|---|---|---|---|
| **H1 (most likely)** | 0x04[7:0] is **write-protected while RX_EN_EQA=1**, the same as RX_EQA_CONFIG (#7). | yes: every write is ignored and the old 1 stays | `RX_EN_EQA=0` -> write `CKP_OFFSET=0` (and 2) -> read back -> `RX_EN_EQA=1` -> read back again. Run a control test on `RX_EQA_CKP_LF/HF` (0x03) with EN_EQA=1 and EN_EQA=0. |
| H2 | The field is not stored. It is tied to a constant (hardwired, or the reset value is reloaded by the EQA FSM). | yes | Read back from the **R1 bitstream** that has `RX_EQA_CKP_OFFSET=0` baked in (`gs_2g5r1_oss1016.bit`, `m2_2g5r1_oss1016.bit`, TOOLCHAIN_20261017 §6). If it reads 0, H2 is false and H1 is very likely. If it reads 1 even from the bitstream, H2 (or a remap) is likely. |
| H3 | The engine writes the field back (EQA_RESET or each lock event reloads it). | yes | Same as H1. Also read it immediately after `RX_EQA_RESET` / RX reset while `RX_EN_EQA=0`. |
| H4 | Value clamp: mantissa 0 is illegal and gets clamped to 1. | only for 0. It does not explain 2 -> 1. | Already ruled out by the 2 -> 1 result. |
| H5 | Bit position is shifted, like the 0x2B case (#9). | only if the true field sits elsewhere and [7:0] is read-only | Write 0x04 with mask 0x00FF and value 0x55, read back the full 16 bits. Compare bits [15:14] (documented unused) and bit 13 (LOCKED). |

The bitstream readback (H2 test) needs no extra JTAG write ordering and answers the most. It is the first A/B candidate already listed in TOOLCHAIN_20261017 §6.

Consequence if H1 holds: any runtime EQA loop change must use the same order upstream uses for RX_EQA_CONFIG: EN_EQA=0, then write, then readback check, then EN_EQA=1. `link_gate.py after_load()` and `eyescan.py set` should check the readback exit code, as CHAIN4 §4 already noted.

### 1.3 Other EQA / CDR / TX / PLL / reset facts

| Topic | Fact | Tag / source |
|---|---|---|
| EQA freeze | Upstream freezes the integrators with `RX_EQA_CONFIG[8:6]=0b000` (en_acc). The default 0x01C0 has en_acc=0b111. `sel_comp_data` is in [5:3] and the cursor select is in [2:0]. The check is `chk('integrators frozen', (cfg>>6)&7 == 0)`. | SOURCE-VERIFIED, UP:1399-1402, 1633 |
| EQA overrides | Upstream: the DFE tap is computed combinationally as (mon1 threshold - mon2 threshold) and re-registered every RX clock. EXT_VALUE[2] write-protects RX_TAPW and TH_MON1. EXT_VALUE[3] write-protects TH_MON2 and AFE_OFFSET. DS1001 instead says bit0 = TH_MON1_OVR, bit1 = TH_MON2_OVR, bit2 = TAPW_OVR, bit3 = AFE_OFFSET_OVR. UP's comments say that EXT_VALUE[0] and [1] are unused and that [2] and [3] each cover two overrides. **DS and tool disagree.** | SOURCE-VERIFIED, DS26 p.80; UP:95-101, 1368-1378 |
| EQA config in CC's current example | `RX_EN_EQA=1`, `RX_EQA_LOCK_CFG=0xC` (HF amplitude + tap /2), `RX_AFE_PEAK=0x18`, `RX_AFE_GAIN=0`, `RX_AFE_VCMSEL=3`, `RX_RTERM_VCMSEL=3` ("~800 mV @ VDDIO=1.1V"), `RX_CDR_CKP=0x3E`, `RX_CDR_CKI=0`. Before commit dda07f7 (Oct 2025) the values were CDR_CKP 0xF8 (DS default), AFE_PEAK 0xF, GAIN 8. | SOURCE-VERIFIED, `R/gm_serdes_lb/src/verilog/serdes_lb.v` @56aa48b; `git show dda07f7` |
| Copy in our tree | `UPV` (dated 2026-10-15) differs from gm_serdes_lb HEAD: EN_EQA=0, AFE_PEAK=0x1F, VCMSEL=4, TX_SEL_PRE/POST=0, TX_AMP=0xF, PLL_CP 0x96/AO 0xA, BISC CP min/max/start 4/18/12, OUTDIV=4. It is not the same as the "5G prep" HEAD. | SOURCE-VERIFIED, diff of the two files |
| CDR | DS defaults: CKP=0xF8, CKI=0, TRANS_TH=8 ("min. no. of PFD transitions"), LOCK_CFG=0xD5, WAIT_CDR_LOCK=1 ("reset sequence is stopped until CDR lock"). CKI=0 means a proportional-only loop by default. CC examples use WAIT_CDR_LOCK=0 with the comment "turn off if loopback enabled". nextpnr fills WAIT_CDR_LOCK=1 if the parameter is not set. | SOURCE-VERIFIED, DS26 p.82; UPV:248; NP pack_serdes.cc:42, 374-375 |
| CDR encoding | 0xF8 = 111_11000 and 0x3E = 001_11110 in {3,5} notation. CC lowered the shift from 7 to 1 (a narrower proportional gain) when it "fixed" the CDR parameter. | INFERRED from #5 + dda07f7 |
| TX FFE | 125 branches: 63 main-only, 31 pre-or-main, 31 post-or-main. `TX_SEL_PRE <= TX_BRANCH_EN_PRE`, `TX_SEL_POST <= TX_BRANCH_EN_POST`. `I_TX = (TX_TAIL_CASCODE+10)*(TX_AMP+1)*9.375 uA`. N_MAIN = N_BRA - SEL_PRE - SEL_POST. TX_TAIL_CASCODE: "keep default". TX_DC_OFFSET: "Set to 8". | SOURCE-VERIFIED, DS26 p.70-72 |
| TX in CC 5G-prep | BRANCH_EN_PRE=POST=12, MAIN=63, SEL_PRE=SEL_POST=5, TX_AMP=31, TX_DC_ENABLE=(12+63+12)/2=43, TX_DC_OFFSET=8, TX_CALIB_EN=1. | SOURCE-VERIFIED, `R/gm_serdes_lb/src/verilog/serdes_lb.v:231-234,331-339,367` |
| PLL | Any runtime change to the ADPLL registers needs `PLL_EN_ADPLL_CTRL=0` first. BISC: Mode B (internal PFD) is "preferred" and Mode A "not recommended". Rates: 100 MHz ref, N=1*5*5 (DCO 2500 MHz) with OUT /2 = 2.5 G and /1 = 5 G. DCO range 1250-2500 MHz, so 5 G runs at the **top edge** of the DCO. | SOURCE-VERIFIED, DS26 p.58-59, p.155; CC slides p.11 https://colognechip.com/docs/presentations/gatemate-serdes-fpgaconf2025.pdf |
| Reset order | Resets are chained internally. A TX/RX path reset always resets PCS, PMA, CDR and DFE (RX also resets the elastic buffer). The ADPLL keeps both paths in reset until it locks. The sequence starts at `PLL_EN_ADPLL_CTRL` (0x50[0]) and ends at TX_RESET_DONE_O, then RX_RESET_DONE_O, with RX later than TX. `*_RESET_TIME` = number of clocks "prescaled with RX_RESET_TIMER_PRESC". The prescale law is not documented. CC uses PRESC=4 and RESET_TIME=3. | SOURCE-VERIFIED, DS26 p.60-61, p.75-77; UPV:241-247 |
| Regfile access | At least 16 clocks must pass between two regfile accesses from the CPE side. | SOURCE-VERIFIED, DS26 p.89 |
| Supply | VDD_SER and VDD_SER_PLL: 1.00 V min, 1.0 V typ, 1.1 V max (Table 4.3). Power: 2.5 G 36-46 mA, 5 G 40-51 mA (1.00-1.15 V). Ref clock 100-125 MHz with 1 ps jitter. The Olimex EVB Rev C schematic says: "SerDes is not working when VDD_CORE = 0.9V ... minimum working voltage: 0.95V". | SOURCE-VERIFIED, DS26 p.155; https://github.com/intergalaktik/ulx5m-gs/issues/28 (comment by mrcmry, Olimex PDF https://github.com/OLIMEX/GateMateA1-EVB/blob/main/HARDWARE/GateMateA1-EVB-Rev.C/GateMateA1-EVB_Rev_C.pdf) |

---

## 2. Public GateMate SerDes projects: settings and reported problems

| Project | Rate / status | Settings of note | Tag / source |
|---|---|---|---|
| pu-cc/gm_serdes_lb (Cologne Chip R&D) | 2.5 G default. "prepare 5G tests" ab7ce94 (2026-09-03) briefly used N=2,4,4 OUT /1, then went back to 1,5,5 /2. Comments mention `//1551` and `//2441 6.4G`. **No published 5 G result.** | as in §1.3 (EN_EQA=1, TX pre/post 5/5 of 12/12, AMP 31) | SOURCE-VERIFIED, https://github.com/pu-cc/gm_serdes_lb (HEAD 56aa48b, 2026-09-18) |
| colognechip/gatemate-pipe | PCIe Gen1 2.5 G PIPE wrapper, 80 bit, hard 8b10b, EN_EQA=0, CKP_OFFSET 0x01 | defaults | SOURCE-VERIFIED, https://github.com/colognechip/gatemate-pipe (63ba8b1, 2025-11-10) |
| chili-chips-ba/openCologne-PCIE | WIP. Simulation with pcieVHost (2026-10-16). No hardware link-up published. Gen2 5 G is a "best-effort bonus". Issue #5: the SerDes simulation model is proprietary. | defaults | SOURCE-VERIFIED, https://github.com/chili-chips-ba/openCologne-PCIE (a3cb12f, 2026-10-17) |
| pu-cc/liteeth gatemate_1000basex | 1.25 G, 20-bit, PCS bypassed, 125 MHz fabric (shown on CC slides p.17-18) | EN_EQA=0 | SOURCE-VERIFIED, https://github.com/pu-cc/liteeth/tree/gatemate1000basex |
| enjoy-digital/litepcie #151 | "Port to GateMate": request only, no code | - | SOURCE-VERIFIED, https://github.com/enjoy-digital/litepcie/issues/151 |
| nextpnr PR #1846 | Fix: SERDES config was always written to die 0 (affects A2 lane 1 only, not A1) | - | SOURCE-VERIFIED, https://github.com/YosysHQ/nextpnr/pull/1846 |
| Eye monitor / CDR lock / VDD_SER reports | Public: only the VDD_SER at 0.9 V core issue (ulx5m-gs #28, Olimex note). The CC eye-measurement write-protect rules appear only as comments in serdestool (§1.3). I found no public report of a 5 G GateMate link with BER numbers. | SOURCE-VERIFIED (search) / absence = INFERRED |

---

## 3. General link tuning method (numbers)

| Topic | Concrete number / rule | Tag / source |
|---|---|---|
| Zero-error BER confidence | N = -ln(1-CL)/BER: 90% -> 2.30/BER, **95% -> 3.00/BER**, 99% -> 4.61/BER. With 1 error: 3.89 / 4.74 / 6.64. With 2 errors: 5.32 / 6.30 / 8.40. General form: N = (1/BER)[-ln(1-CL) + ln(sum_{k=0..E} (N*BER)^k/k!)]. | SOURCE-VERIFIED, Maxim HFTA-010.0 Table 1 and eq. 2, https://optiwave.com/wp-content/uploads/2014/11/3419.pdf |
| Test time for our link | BER < 1e-12 at 95%: 3e12 bits. That is **1200 s at 2.5 Gb/s** line rate (1500 s if only 8b10b payload bits are counted), **600 s at 5 Gb/s**. BER < 1e-15 needs about 13.9 days at 2.5 G. A 1800 s soak with 0 errors at 2.5 G gives BER < 6.7e-13 (95%). | INFERRED (arithmetic) |
| Q-scale / dual-Dirac | TJ(BER) = 2*Q_BER*sigma_RJ + DJ(dd). Q_BER: 6.4 @1e-10, 6.7 @1e-11, **7.0 @1e-12**, 7.3 @1e-13, 7.6 @1e-14 (exactly 7.034 -> 2Q = 14.07). Fit the bathtub tails on a Q scale (Q = sqrt2*erfc^-1(2*BER)), where they are linear for Gaussian RJ, and extrapolate to Q = 7.03. | SOURCE-VERIFIED, Agilent 5989-3206EN Table 2 and eq. 1, https://people.engr.tamu.edu/spalermo/ecen689/jitter_dual_dirac_agilent.pdf |
| Application to the CC eye counter | One CC run = 40*(window+1) UI (UP `eye_run_time`). Window 4095 gives 163,840 UI per run, so the direct BER floor per point is about 1e-5 to 1e-6. Below that, Q-scale extrapolation is required. Use only points with 1e-3 > BER > 1e-6 and at least 2 points per tail. | SOURCE-VERIFIED (formula, UP:1440-1447) + INFERRED (floor, method) |
| Xilinx eye scan | A statistical eye sample count ranges "from tens of thousands to greater than 10^14". Eye scan runs on live data and needs no RX setting changes. | SOURCE-VERIFIED, UG476 v1.12.1 p.215, https://0x04.net/~mwk/xidocs/ug/ug476_7Series_Transceivers.pdf |
| **DFE with 8b10b (relevant!)** | "DFE mode must be carefully considered in 8B/10B applications or where data scrambling is not employed ... auto adaptation in DFE mode requires incoming data to be random ... repeated patterns can cause the auto adapting algorithms to drift away from the ideal equalization setting. Patterns similar to PRBS7 (or higher) are sufficiently random." Also "LPM mode is recommended for 8B/10B encoded data" (CDR tables). | SOURCE-VERIFIED, UG476 p.195, p.206 |
| Adaptation freeze | "RXDFEAGCHOLD and RXDFELFHOLD should be asserted after training to freeze the AGC adapt value" (after T_DLOCK). The held value lasts until GTRXRESET/RXPMARESET/RXDFELPMRESET. | SOURCE-VERIFIED, UG476 p.195 |
| LPM vs DFE choice | LPM for <= 11.2 Gb/s with <= 12 dB loss at Nyquist. DFE for >= 8 dB loss. | SOURCE-VERIFIED, UG476 p.195 |
| Applied to CC_SERDES | Train EQA on PRBS (TX_PRBS_SEL) with RX_EN_EQA=1 until RX_EQA_LOCKED. Then freeze with RX_EQA_CONFIG[8:6]=0 (EN_EQA=0 first, §1.2 H1), switch to the 8b10b payload, and A/B against continuous adaptation on 8b10b. | INFERRED |
| CDR bandwidth | Reference ("golden") PLL / jitter tolerance corner = **baud/1667** (SATA Gen1/2, FC, 1GbE and XAUI-class; 10GbE moved to baud/2578). At 2.5 G that is 1.5 MHz, at 5 G 3.0 MHz. A wider CDR tracks more low-frequency jitter (refclk wander, supply ripple) but passes more high-frequency noise. A narrower CDR does the opposite. | SOURCE-VERIFIED, IEEE 802.3bm Ghiasi https://www.ieee802.org/3/bm/public/mar14/ghiasi_01_0314_optx.pdf (corner values); trade-off = textbook, INFERRED for CC |
| Matrix sweep | Xilinx IBERT/ISI sweep: TX diff swing x pre-cursor x post-cursor x RX (LPM/DFE), 2D eye per point, rank by open area. Intel TTK "Auto Sweep" ranks PMA settings by target BER. HEP practice: coarse grid, then a +/-step refinement around the best point. | SOURCE-VERIFIED (via prior doc `ulx5m-gs-m2-serdes/docs/SERDES_UMJERAVANJE_KAKO_DRUGI_20261015.md` [X2][X3][X6][X16]); https://arxiv.org/pdf/1901.02722 |
| Sweep cost for CC | Example: TX_SEL_PRE {0,2,5} x SEL_POST {0,2,5} x AMP {15,23,31} x AFE_PEAK {0x10,0x18,0x1F} = 81 points. At 60 s BER per point that is 81 min. A 0-error 60 s point at 2.5 G only shows BER < 2e-11 (95%). Rank on eye area or Q, not on 0-error counts, then soak the top 2-3 points for >= 1200 s. | INFERRED |

---

## 4. Recommended next steps (INFERRED, ordered)

1. Read RX_EQA_CKP_OFFSET from the baked R1 bitstream (no runtime write). If 0 -> H1. If 1 -> H2/H5.
2. Runtime test: EN_EQA=0 -> write CKP_OFFSET -> readback -> EN_EQA=1. Run the same control on CKP_LF/HF and LOCK_CFG.
3. Make `eyescan.py set` / `link_gate.py` fail on readback mismatch, which already returns exit code 1 (`eyescan.py:240`).
4. Ask Cologne Chip (support@colognechip.com, P. Urban) whether 0x03 and 0x04[7:0] are locked while RX_EN_EQA=1 and what the {3,5} coefficient encoding is. This is not documented anywhere public.
5. For 5 G: the DCO is at 2500 MHz (the top edge) and VDD_SER is marginal (see CALIBRATION_REVIEW_20261016 K2). There is no public 5 G GateMate result to copy settings from. The closest reference is the CC 5G-prep set (§1.3).
