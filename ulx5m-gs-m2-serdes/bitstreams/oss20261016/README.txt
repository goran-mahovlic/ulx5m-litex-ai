oss20261016 — 2,5G gs/m2 bitovi s novim zadanim lancem oss-cad-suite-20261016 (TASK-5549, 17.10.2026.)
yosys 0.70+145 a31d95ea0 | nextpnr-himbaechel 0.11.1-63-g44a6c739 | gmpack v1.13-6-gb1eb52f --reset (CMD_CFGRST provjeren)
NISU UCITANI NI ISPROBANI NA PLOCI. Novi lanac = novi smjestaj -> prije dugog laba >= 3 ucitavanja po bitu (REVIEW_INIT §9).

gs_2g5_oss1016.bit   = isti dizajn i parametri kao gs_2g5_auto.bit (99d80788), seed 7, FREQ 40
m2_2g5_oss1016.bit   = isti dizajn i parametri kao m2_2g5_auto.bit (3f4857df), seed 2, FREQ 40
   parametri: N1 1 N2 5 N3 5 OUTDIV 2 PROFILE 1 TX_NEG 1 OV_TX_AMP 12  (gs: LINK=ber_link_gs.v)
   CC_SERDES blok: 0/186 B i 0/252 polja razlike prema *_2g5_auto.bit
gs_2g5r1_oss1016.bit / m2_2g5r1_oss1016.bit = isto + recept R1 upecen: OV_CALIB 0 OV_TX_SEL_PRE 0 OV_EQA_CKP_OFFSET 0
   CC_SERDES: tocno 4 polja razlike: RX_CALIB_OVR 0->1, TX_CALIB_OVR 0->1 (VAL ostaje 0), TX_SEL_PRE 5->0, RX_EQA_CKP_OFFSET 1->0
   NIJE upecen dio R1 "DFE/EQA reset nakon ucitavanja" (to je strob, ne polje) - po potrebi i dalje JTAG-om.
Fmax (MHz, potrebno rclk/tclk >= 31,25, clk_i >= 25):
   gs  rclk 44.98 tclk 71.31 clk_i 38.21 | gs R1 rclk 43.42 tclk 74.08 clk_i 33.72 | 0 hold
   m2  rclk 63.08 tclk 80.70 clk_i 125.63 | m2 R1 isto | 0 hold
Detalji: ulx5m-gs-m2-serdes/docs/TOOLCHAIN_20261017.md
