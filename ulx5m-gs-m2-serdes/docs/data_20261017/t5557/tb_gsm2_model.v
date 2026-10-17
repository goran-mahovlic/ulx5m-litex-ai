// tb_gsm2_model.v — TASK-5557: GS<->M2 link on the open GateMate SerDes model (openCologne-PCIE,
// 2.rtl/1.phy/2.serdes-model/ccfpga_serdes.v) with OUR CC_SERDES settings where the model takes them.
// Two instances cross-linked (GS TX -> M2 RX, M2 TX -> GS RX), 2.5 Gb/s, PRBS7 both directions (PRBS31 optional).
// Checks (printed, nothing is asserted silently):
//   R1  regfile readback of 0x03 (RX_EQA_CKP_LF/HF), 0x04 (CKP_OFFSET + RX_EN_EQA), 0x2B (EQA/RX reset OVR)
//   R2  reset ordering: M2 loaded first, GS PLL enabled GS_DELAY_NS later; RX_WAIT_CDR_LOCK 0 vs 1
//   R3  PRBS errors after lock, both directions
//   R4  rx_eqa_reset_i pulse and regfile 0x2B EQA reset: effect on lock / resetdone / errors
//   R5  rx_cdr_reset_i pulse (contrast: the model does relock)
`timescale 1ns/100fs
module tb;
   parameter        WAIT_CDR    = 0;        // our bits: RX_WAIT_CDR_LOCK(1'b0)
   parameter real   GS_DELAY_NS = 20000.0;  // M2 up first, GS later (our load order)
   parameter real   PPM         = 250.0;    // M2 refclk offset vs GS; 100 ppm makes the model crawl (see doc), 250 ppm runs
   parameter real   WIRE_NS     = 5.0;
   parameter  [2:0] PRBS        = 3'b001;   // 001 PRBS7; 100 PRBS31 has 31-bit runs > model EI window (20 UI)

   // our ber_top PROFILE 1 + R1 values that the model has parameters for
   localparam [4:0] PRESC = 5'h4;           // A_TIMER_PRESC (P1)
   localparam [7:0] CKP   = 8'hA3;          // RX_EQA_CKP_LF/HF in cc_serdes_params.vh
   localparam [7:0] CKOFF = 8'h00;          // R1: RX_EQA_CKP_OFFSET 0

   reg clk_ref_gs = 0, clk_ref_m2 = 0, clk_reg = 0, clk_cfg = 0;
   always #(5.0)                      clk_ref_gs = ~clk_ref_gs;   // 100 MHz
   always #(5.0 * (1.0 + PPM * 1e-6)) clk_ref_m2 = ~clk_ref_m2;
   always #4.0  clk_reg = ~clk_reg;
   always #20.0 clk_cfg = ~clk_cfg;

   reg reset_n = 0;
   // per-instance control: index 0 = GS, 1 = M2
   reg        cfg_en [0:1], cfg_valid [0:1];
   reg [15:0] cfg_di [0:1];  reg [7:0] cfg_addr [0:1];
   reg        rf_en [0:1], rf_we [0:1];
   reg  [7:0] rf_addr [0:1]; reg [15:0] rf_mask [0:1], rf_di [0:1];
   wire [15:0] rf_do [0:1];  wire rf_rdy [0:1];
   reg        eqa_rst [0:1], cdr_rst [0:1];
   reg  [2:0] prbs;

   wire gs_tx_p, gs_tx_n, m2_tx_p, m2_tx_n;
   reg  gs_rx_p = 0, gs_rx_n = 1, m2_rx_p = 0, m2_rx_n = 1;
   always @(m2_tx_p) gs_rx_p <= #(WIRE_NS) m2_tx_p;
   always @(m2_tx_n) gs_rx_n <= #(WIRE_NS) m2_tx_n;
   always @(gs_tx_p) m2_rx_p <= #(WIRE_NS) gs_tx_p;
   always @(gs_tx_n) m2_rx_n <= #(WIRE_NS) gs_tx_n;

   wire gs_core, m2_core, gs_rcn, m2_rcn;
   wire gs_rxdone, m2_rxdone, gs_txdone, m2_txdone;

`define SERDES(NAME, IDX, REF, CORE, RCN, TXP, TXN, RXP, RXN, TXD, RXD) \
   ccfpga_serdes #( \
      .RX_WAIT_CDR_LOCK(WAIT_CDR), .RX_RESET_TIMER_PRESC(PRESC), \
      .RX_PMA_RESET_TIME(5'h3), .RX_EQA_RESET_TIME(5'h3), .RX_CDR_RESET_TIME(5'h3), \
      .RX_PCS_RESET_TIME(5'h3), .RX_BUF_RESET_TIME(5'h3), \
      .RX_CALIB_OVR(1'b1), .RX_CALIB_VAL(4'h0), .TX_CALIB_OVR(1'b1), .TX_CALIB_VAL(4'h0), \
      .RX_EQA_CKP_LF(CKP), .RX_EQA_CKP_HF(CKP), .RX_EQA_CKP_OFFSET(CKOFF), .RX_EN_EQA(1'b1), \
      .RX_EQA_LOCK_CFG(4'hC), .RX_AFE_PEAK(5'h18), .RX_AFE_GAIN(4'h0), .RX_CDR_CKP(8'h3E), \
      .TX_SEL_PRE(5'h0), .TX_SEL_POST(5'h5), .TX_AMP(5'h1F), \
      .RX_DATAPATH_SEL(2'b11), .TX_DATAPATH_SEL(2'b11), .ALIGN_COMMA_WORD(2'b11), \
      .PLL_FCNTRL(6'd58), .PLL_MAIN_DIVSEL(6'b011011), .PLL_OUT_DIVSEL(2'b01) \
   ) NAME ( \
      .clk_ref_i(REF), .clk_reg_i(clk_reg), .clk_cfg_i(clk_cfg), \
      .clk_core_tx_i(CORE), .clk_core_rx_i(CORE), .clk_core_rx_o(), \
      .reset_n_i(reset_n), .reset_reg_n_i(reset_n), .reset_core_tx_n_i(RCN), .reset_core_rx_n_i(RCN), \
      .testmode_i(1'b0), .scan_enable_i(1'b0), .scan_in_i(7'h0), .scan_out_o(), .loopback_i(3'b000), \
      .pll_reset_i(1'b0), .clk_core_pll_o(CORE), .reset_core_pll_n_o(RCN), .refclk_sel_o(), .refclk_rterm_o(), \
      .RX_SERIO_P_B(RXP), .RX_SERIO_N_B(RXN), .TX_SERIO_P_B(TXP), .TX_SERIO_N_B(TXN), \
      .regfile_we_i(rf_we[IDX]), .regfile_en_i(rf_en[IDX]), .regfile_addr_i(rf_addr[IDX]), \
      .regfile_mask_i(rf_mask[IDX]), .regfile_di_i(rf_di[IDX]), .regfile_do_o(rf_do[IDX]), .regfile_rdy_o(rf_rdy[IDX]), \
      .cfg_en_i(cfg_en[IDX]), .reset_cfg_i(1'b0), .cfgfile_di_i(cfg_di[IDX]), .cfgfile_valid_i(cfg_valid[IDX]), \
      .cfgfile_addr_i(cfg_addr[IDX]), \
      .tx_reset_i(1'b0), .tx_pcs_reset_i(1'b0), .tx_pma_reset_i(1'b0), .tx_elec_idle_i(1'b0), \
      .tx_detect_rx_i(1'b0), .tx_prbs_sel_i(prbs), .tx_prbs_force_err_i(1'b0), .tx_powerdown_n_i(1'b1), \
      .tx_data_i(64'h0), .tx_char_is_k_i(8'h0), .tx_polarity_i(1'b0), .tx_8b10b_en_i(1'b1), \
      .tx_8b10b_bypass_i(8'h0), .tx_char_dispmode_i(8'h0), .tx_char_dispval_i(8'h0), \
      .tx_buf_err_o(), .tx_resetdone_o(TXD), .rx_detect_done_o(), .rx_present_o(), .TERM_SERIO_O(), \
      .rx_reset_i(1'b0), .rx_pma_reset_i(1'b0), .rx_eqa_reset_i(eqa_rst[IDX]), .rx_cdr_reset_i(cdr_rst[IDX]), \
      .rx_pcs_reset_i(1'b0), .rx_buf_reset_i(1'b0), .rx_prbs_sel_i(prbs), .rx_prbs_cnt_reset_i(1'b0), \
      .rx_powerdown_n_i(1'b1), .rx_en_ei_detector_i(1'b1), .rx_comma_detect_en_i(1'b1), .rx_slide_i(1'b0), \
      .rx_polarity_i(1'b0), .rx_8b10b_en_i(1'b1), .rx_8b10b_bypass_i(8'h0), \
      .rx_mcomma_align_i(1'b1), .rx_pcomma_align_i(1'b1), .rx_prbs_err_o(), .rx_data_o(), .rx_char_is_k_o(), \
      .rx_char_is_comma_o(), .rx_not_in_table_o(), .rx_disp_err_o(), .rx_buf_err_o(), \
      .rx_byte_is_aligned_o(), .rx_byte_realign_o(), .rx_resetdone_o(RXD), .rx_ei_en_o() );

   `SERDES(u_gs, 0, clk_ref_gs, gs_core, gs_rcn, gs_tx_p, gs_tx_n, gs_rx_p, gs_rx_n, gs_txdone, gs_rxdone)
   `SERDES(u_m2, 1, clk_ref_m2, m2_core, m2_rcn, m2_tx_p, m2_tx_n, m2_rx_p, m2_rx_n, m2_txdone, m2_rxdone)

   integer k;
   initial begin
      prbs = PRBS;     // TX generator and RX checker, both sides
      for (k = 0; k < 2; k = k + 1) begin
         cfg_en[k] = 0; cfg_valid[k] = 0; cfg_di[k] = 0; cfg_addr[k] = 0;
         rf_en[k] = 0; rf_we[k] = 0; rf_addr[k] = 0; rf_mask[k] = 0; rf_di[k] = 0;
         eqa_rst[k] = 0; cdr_rst[k] = 0;
      end
   end

   task writeCfg(input integer i, input [7:0] a, input [15:0] d);
      begin
         @(posedge clk_cfg); #1 cfg_en[i] = 1;
         @(posedge clk_cfg); #1 cfg_valid[i] = 1; cfg_di[i] = d; cfg_addr[i] = a;
         @(posedge clk_cfg); #1 cfg_valid[i] = 0;
         @(posedge clk_cfg); #1 cfg_en[i] = 0;
      end
   endtask
   task wr(input integer i, input [7:0] a, input [15:0] d, input [15:0] m);
      begin
         @(posedge clk_reg); #1 rf_en[i] = 1; rf_we[i] = 1; rf_addr[i] = a; rf_mask[i] = m; rf_di[i] = d;
         @(posedge clk_reg); #1 rf_en[i] = 0; rf_we[i] = 0;
         repeat (20) @(posedge clk_reg);
      end
   endtask
   task rd(input integer i, input [7:0] a, output [15:0] q);
      begin
         @(posedge clk_reg); #1 rf_en[i] = 1; rf_we[i] = 0; rf_addr[i] = a;
         @(posedge clk_reg); #1 rf_en[i] = 0;
         while (!rf_rdy[i]) @(posedge clk_reg);
         q = rf_do[i];
         repeat (20) @(posedge clk_reg);
      end
   endtask
   task bringup(input integer i);
      begin
         writeCfg(i, 8'h5C, 16'h0001);            // SERDES_CFG: enable
         wr(i, 8'h50, 16'h0002, 16'h0007);        // PLL_CFG0: config select
         wr(i, 8'h50, 16'h0003, 16'h0003);        // PLL_CFG0: enable ADPLL
      end
   endtask

   // event times
   real t_m2_lock = -1, t_m2_done = -1, t_gs_lock = -1, t_gs_done = -1, t_gs_pll = -1;
   always @(posedge u_m2.rx_cdr_locked)  if (t_m2_lock < 0) t_m2_lock = $realtime;
   always @(posedge m2_rxdone)            if (t_m2_done < 0) t_m2_done = $realtime;
   always @(posedge u_gs.rx_cdr_locked)  if (t_gs_lock < 0) t_gs_lock = $realtime;
   always @(posedge gs_rxdone)            if (t_gs_done < 0) t_gs_done = $realtime;
   always @(posedge u_gs.pll_locked)     if (t_gs_pll  < 0) t_gs_pll  = $realtime;

   integer n_lock_drop_gs = 0, n_done_drop_gs = 0;
   always @(negedge u_gs.rx_cdr_locked) if ($realtime > 1.0) n_lock_drop_gs = n_lock_drop_gs + 1;
   always @(negedge gs_rxdone)          if ($realtime > 1.0) n_done_drop_gs = n_done_drop_gs + 1;

   reg [15:0] q;
   reg [15:0] e_gs0, e_m20, e_gs1, e_m21, dlt; integer ld0, dd0;
   integer n_ei_gs = 0;
   always @(posedge u_gs.rx_ei_filt) if ($realtime > 30000.0) n_ei_gs = n_ei_gs + 1;
   initial begin
      $display("=== TASK-5557 tb_gsm2_model: RX_WAIT_CDR_LOCK=%0d, GS delay %0.0f ns, M2 ref %+0.0f ppm ===",
               WAIT_CDR, GS_DELAY_NS, PPM);
      #100 reset_n = 1;
      #100;
      // ---------------- R1: regfile readback (M2 instance)
      rd(1, 8'h03, q); $display("R1 0x03 before any write             : 0x%04h  (param CKP_LF/HF = 0x%02h%02h)", q, CKP, CKP);
      wr(1, 8'h03, 16'h8383, 16'hFFFF);
      rd(1, 8'h03, q); $display("R1 0x03 write 0x8383 -> readback     : 0x%04h  %s", q, (q == 16'h8383) ? "== write" : "!= write");
      wr(1, 8'h04, 16'h0100, 16'h01FF);
      rd(1, 8'h04, q); $display("R1 0x04 write [8]=1,[7:0]=0x00 -> rb : 0x%04h  %s", q, (q == 16'h0100) ? "== write" : "!= write");
      wr(1, 8'h2B, 16'h000C, 16'h000C);
      rd(1, 8'h2B, q); $display("R1 0x2B write EQA OVR+RST [3:2]=11   : 0x%04h  %s", q, (q[3:2] == 2'b11) ? "== write" : "!= write");
      wr(1, 8'h2B, 16'h0000, 16'h000C);
      rd(1, 8'h2B, q); $display("R1 0x2B write [3:2]=00 -> readback   : 0x%04h", q);
      // ---------------- R2: M2 first, GS later
      bringup(1);
      #(GS_DELAY_NS);
      bringup(0);
      wait (gs_rxdone && m2_rxdone && u_gs.rx_cdr_locked && u_m2.rx_cdr_locked);
      #2000;
      $display("R2 GS PLL locked @ %0.1f ns (GS TX starts toggling)", t_gs_pll);
      $display("R2 M2 rx_resetdone @ %0.1f ns, M2 CDR lock @ %0.1f ns -> resetdone %s lock by %0.1f ns",
               t_m2_done, t_m2_lock, (t_m2_done < t_m2_lock) ? "BEFORE" : "AFTER", (t_m2_done < t_m2_lock) ? (t_m2_lock - t_m2_done) : (t_m2_done - t_m2_lock));
      $display("R2 GS rx_resetdone @ %0.1f ns, GS CDR lock @ %0.1f ns -> resetdone %s lock by %0.1f ns",
               t_gs_done, t_gs_lock, (t_gs_done < t_gs_lock) ? "BEFORE" : "AFTER", (t_gs_done < t_gs_lock) ? (t_gs_lock - t_gs_done) : (t_gs_done - t_gs_lock));
      // ---------------- R3: PRBS errors after lock
      e_gs0 = u_gs.rx_prbs_err_cnt; e_m20 = u_m2.rx_prbs_err_cnt;
      #100000;
      e_gs1 = u_gs.rx_prbs_err_cnt; e_m21 = u_m2.rx_prbs_err_cnt;
      $display("R3 PRBS sel=%0d 100 us (250 kbit/dir): M2->GS errors %0d, GS->M2 errors %0d (16-bit counters since sync: GS %0d, M2 %0d), GS EI-idle events after 30 us: %0d, GS CDR lock drops so far: %0d",
               PRBS, e_gs1 - e_gs0, e_m21 - e_m20, e_gs1, e_m21, n_ei_gs, n_lock_drop_gs);
      // ---------------- R4: EQA reset, pin and regfile
      ld0 = n_lock_drop_gs; dd0 = n_done_drop_gs; e_gs0 = u_gs.rx_prbs_err_cnt;
      @(posedge gs_core); eqa_rst[0] = 1; repeat (8) @(posedge gs_core); eqa_rst[0] = 0;
      wr(0, 8'h2B, 16'h000C, 16'h000C); wr(0, 8'h2B, 16'h0000, 16'h000C);
      #20000; dlt = u_gs.rx_prbs_err_cnt - e_gs0;
      $display("R4 GS EQA reset (pin 8 clk + regfile 0x2B pulse): CDR lock drops %0d, rx_resetdone drops %0d, new errors %0d",
               n_lock_drop_gs - ld0, n_done_drop_gs - dd0, dlt);
      // ---------------- R5: CDR reset (contrast)
      ld0 = n_lock_drop_gs; dd0 = n_done_drop_gs; e_gs0 = u_gs.rx_prbs_err_cnt;
      @(posedge gs_core); cdr_rst[0] = 1; repeat (8) @(posedge gs_core); cdr_rst[0] = 0;
      #20000; dlt = u_gs.rx_prbs_err_cnt - e_gs0;
      $display("R5 GS CDR reset (pin 8 clk): CDR lock drops %0d, rx_resetdone drops %0d, relocked=%0d, new errors %0d",
               n_lock_drop_gs - ld0, n_done_drop_gs - dd0, u_gs.rx_cdr_locked, dlt);
      $display("=== END @ %0.1f ns ===", $realtime);
      $finish;
   end
   initial begin #2_000_000; $display("TIMEOUT"); $finish; end
endmodule
