# Bitstreams (all tested on the boards, all start with CMD_CFGRST)

| File | Load on | Design | Tested |
|---|---|---|---|
| `serdes_p1_rxpol1_CFGRST.bit` | gs **and** m2 (same file) | `gateware/baseline/` (serdes_lb_p1.v, `RX_POLARITY_I=1`), 0.3 Gb/s, 8b10b, K28.5 + D10.2, seed 1 | 26.09.2026: `serdes_link_check.py` DATA_OK 30/30 on both boards (seeds 0–5 all passed) |

Check the checksums with `sha256sum -c SHA256SUMS` and CFGRST with `python3 ../tools/gm_cfgrst_check.py <file>`.
Load order: m2 first, then gs.
