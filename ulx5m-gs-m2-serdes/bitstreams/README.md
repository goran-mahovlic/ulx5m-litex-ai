# Bitstreams (all tested on the boards, all start with CMD_CFGRST)

| File | Load on | Design | Tested |
|---|---|---|---|
| `serdes_p1_rxpol1_CFGRST.bit` | gs **and** m2 (same file) | `gateware/baseline/` (serdes_lb_p1.v, `RX_POLARITY_I=1`), 0.3 Gb/s, 8b10b, K28.5 + D10.2, seed 1 | 26.09.2026: `serdes_link_check.py` DATA_OK 30/30 on both boards (seeds 0–5 all passed) |

| `ber_gs_0g3_CFGRST.bit` / `ber_m2_0g3_CFGRST.bit` | gs / m2 | `gateware/ber/` BER design, N=1,2,3, OUTDIV 4 → **0.3 Gb/s** | 26.09.2026 19:00: 1.14·10⁹ words per direction, 0 errors; `verify_external_link.sh --load` uses these |
| `ber_gs_1g25_CFGRST.bit` / `ber_m2_1g25_CFGRST.bit` | gs / m2 | same design, N=1,5,5, OUTDIV 4 → **1.25 Gb/s** (DCO 2500 MHz, in spec) | 26.09.2026 19:10: 1.885·10⁹ words per direction, 0 errors |

| `ber_gs_2g5_CFGRST.bit` / `ber_m2_2g5_txneg_CFGRST.bit` | gs / m2 | BER design, N=1,5,5, OUTDIV 2 → **2.5 Gb/s**; m2 with `TX_NEG=1`; gs checker `ber_link_gs.v`, seed 7 | 26.09.2026 21:40 (TASK-5063), analog set over JTAG (`RX_AFE_PEAK=24 RX_AFE_GAIN=0 RX_AFE_VCMSEL=3 RX_RTERM_VCMSEL=3 TX_AMP=24` on both): m2→gs 3.76·10⁹ words, BER 1.1·10⁻⁷; gs→m2 BER 3·10⁻⁵. **Not error-free.** |
| **`ber_gs_2g5_p1_CFGRST.bit` / `ber_m2_2g5_p1_txneg_CFGRST.bit`** | gs / m2 | **2.5 Gb/s with `PROFILE=1`** (pu-cc 5G analog set in the bitstream), m2 `TX_NEG=1`, gs `ber_link_gs.v` seed 7 | 26.09.2026 22:10 (TASK-5063), **no JTAG changes**, 300 s: m2→gs 9.39·10⁹ words, 25 bit errors, **BER 6.7·10⁻¹¹**; gs→m2 9.39·10⁹ words, 435, **1.2·10⁻⁹**. Recommended 2.5 Gb/s pair. |
| `ber_gs_5g_txneg_CFGRST.bit` / `ber_m2_5g_txneg_CFGRST.bit` | gs / m2 | same, OUTDIV 1 → **5 Gb/s** (DCO 2500 MHz), `TX_NEG=1` on both | 26.09.2026 21:30: PLL lock, measured 5000.04 Mb/s; CDR locks and JTAG samples are PEER 9–10/10 only with DFE + TX pre/post-emphasis (see `docs/VERIFY_20260926_RATES.md`); fabric BER ~6·10⁻², and the gs checker is too slow for 62.5 MHz (Fmax 44 MHz) |
| `ber_gs_5g_p2_txneg_CFGRST.bit` / `ber_m2_5g_p2_txneg_CFGRST.bit` | gs / m2 | **5 Gb/s `PROFILE=2`** (TASK-5066: PROFILE 1 + AFE PEAK 12, CDR CKP 0x1E TRANS_TH 16, TX post-cursor only 31 branches DC 47 SEL_POST 12), `TX_NEG=1` both, `TX_DETECT_RX_I=0`; gs `ber_link_gs.v` seed 7 | 27.09.2026 (TASK-5066), no JTAG writes, 300 s: gs→m2 BER 6.3·10⁻², m2→gs 2.0·10⁻² (3 more loads × 60 s the same). **Not usable** — best point of the sweeps, no better than PROFILE 1 (`docs/VERIFY_20260926_RATES.md` §9) |

The 0.3 and 1.25 Gb/s BER bitstreams rebuild byte for byte from the sources of commit 4ee6031
(`build_ber.sh gs od4 1`, `… m2 od4 1`, `… gs n155od4 1 N2 5 N3 5 OUTDIV 4`, `… m2 n155od4 1 N2 5 N3 5 OUTDIV 4`,
oss-cad-suite 2026-09-23). The 2.5/5 Gb/s ones rebuild byte for byte from this tree
(`TMPDIR=~/.tmp/yt`, oss-cad-suite 2026-09-23):

    LINK=ber_link_gs.v FREQ=40 build_ber.sh gs 2g5 7 N1 1 N2 5 N3 5 OUTDIV 2
    FREQ=40 build_ber.sh m2 2g5_txneg 1 N1 1 N2 5 N3 5 OUTDIV 2 TX_NEG 1
    LINK=ber_link_gs.v FREQ=65 build_ber.sh gs 5g_txneg 7 N1 1 N2 5 N3 5 OUTDIV 1 TX_NEG 1
    FREQ=65 build_ber.sh m2 5g_txneg 1 N1 1 N2 5 N3 5 OUTDIV 1 TX_NEG 1
    LINK=ber_link_gs.v FREQ=40 build_ber.sh gs 2g5p1 7 N1 1 N2 5 N3 5 OUTDIV 2 PROFILE 1
    FREQ=40 build_ber.sh m2 2g5p1_txneg 1 N1 1 N2 5 N3 5 OUTDIV 2 TX_NEG 1 PROFILE 1

Since TASK-5066 `TX_DETECT_RX_I` defaults to 0: add `TX_DET_RX 1` to the commands above to rebuild the older bits
(checked byte for byte: the 2.5 G PROFILE 1 pair here, and the 5 G PROFILE 1 pair of TASK-5063). The PROFILE 2 pair
(default `TX_DET_RX 0`; built twice, identical):

    LINK=ber_link_gs.v FREQ=65 build_ber.sh gs p2_5g_txneg 7 N1 1 N2 5 N3 5 OUTDIV 1 TX_NEG 1 PROFILE 2
    FREQ=65 build_ber.sh m2 p2_5g_txneg 1 N1 1 N2 5 N3 5 OUTDIV 1 TX_NEG 1 PROFILE 2

Check the checksums with `sha256sum -c SHA256SUMS` and CFGRST with `python3 ../tools/gm_cfgrst_check.py <file>`.
Load order: m2 first, then gs.
