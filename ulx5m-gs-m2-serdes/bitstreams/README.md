# Bitstreams (all tested on the boards, all start with CMD_CFGRST)

| File | Load on | Design | Tested |
|---|---|---|---|
| `serdes_p1_rxpol1_CFGRST.bit` | gs **and** m2 (same file) | `gateware/baseline/` (serdes_lb_p1.v, `RX_POLARITY_I=1`), 0.3 Gb/s, 8b10b, K28.5 + D10.2, seed 1 | 26.09.2026: `serdes_link_check.py` DATA_OK 30/30 on both boards (seeds 0–5 all passed) |

| `ber_gs_0g3_CFGRST.bit` / `ber_m2_0g3_CFGRST.bit` | gs / m2 | `gateware/ber/` BER design, N=1,2,3, OUTDIV 4 → **0.3 Gb/s** | 26.09.2026 19:00: 1.14·10⁹ words per direction, 0 errors; `verify_external_link.sh --load` uses these |
| `ber_gs_1g25_CFGRST.bit` / `ber_m2_1g25_CFGRST.bit` | gs / m2 | same design, N=1,5,5, OUTDIV 4 → **1.25 Gb/s** (DCO 2500 MHz, in spec) | 26.09.2026 19:10: 1.885·10⁹ words per direction, 0 errors |

`gateware/ber/build_ber.sh gs od4 1`, `… m2 od4 1`, `… gs n155od4 1 N2 5 N3 5 OUTDIV 4`, `… m2 n155od4 1 N2 5 N3 5 OUTDIV 4`
rebuild the four BER bitstreams byte for byte (oss-cad-suite 2026-09-23).

Check the checksums with `sha256sum -c SHA256SUMS` and CFGRST with `python3 ../tools/gm_cfgrst_check.py <file>`.
Load order: m2 first, then gs.
