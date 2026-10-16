TASK-5546 (16.10.2026) - GS<->M2 2.5G bits built with the Cologne Chip p_r 4.2 instead of nextpnr. NOT LOADED BY TASK-5546.
Same design and parameters as the Pi *_2g5_auto.bit (gs 99d80788 = nextpnr seed 7, m2 3f4857df = nextpnr seed 2):
  ber_top.v  N1 1 N2 5 N3 5 OUTDIV 2 PROFILE 1 TX_NEG 1 OV_TX_AMP 12  (2.5G recipe, TX_AMP 12), same .ccf, CCGM1A1
  gs_2g5_pr.bit  = top_gs + ber_link_gs.v      m2_2g5_pr.bit = top_m2 + ber_link.v
Flow: CC yosys 0.52+139 synth_gatemate -nomx8 -vlog -> p_r 4.2 (-tm 3, defaults) -> gm_add_cfgrst.py (CMD_CFGRST checked).
CC_SERDES block (186 B) is byte-identical to the nextpnr bits; only synthesis, placement and routing differ.
Load like the *_auto bits (m2 first, then gs), no JTAG write after the load. A/B test: TASK-5545.
Source: ulx5m-gs-m2-serdes/pr_build/ (build_pr.sh), docs/PR_BUILD_20261016.md.
