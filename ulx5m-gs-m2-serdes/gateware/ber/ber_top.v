// ber_top.v — GS<->M2 SerDes BER test (TASK-5055). Same core on both boards:
//   ROLE=0 (gs): id 5, UART report 1/s on IO_NB_B5 (DirtyJTAG if01), commands on IO_NA_B6
//   ROLE=1 (m2): id 3, no UART; its counters travel to gs in the aux back-channel (byte7)
// SerDes reference: 100 MHz LVDS (Si511 X2 on GS, shared to M2), PLL_REF_SEL=1 (lvds).
// Line rate = f(PLL_CLK_O) * 80  (80-bit datapath: 8 x 10b symbols per word clock).
`timescale 1ns/1ps
module ber_top #(
    parameter ROLE = 0,
    parameter N1 = 1, parameter N2 = 2, parameter N3 = 3, parameter OUTDIV = 4,
    parameter [5:0] FCNTRL = 6'h3A,
    parameter RX_POL = 1'b1,
    parameter [2:0] LOOPBACK_SEL = 3'b000,
    parameter SEC = 25_000_000,            // clk_i cycles per report (sim: small)
    parameter CLK_DIRECT = 0,              // 1: TX_CLK_I/RX_CLK_I straight from PLL_CLK_O/RX_CLK_O as in pu-cc serdes_lb.v (no CC_BUFG)
    parameter TX_NEG = 0,                  // 1: TX_DATA_I from a negedge register (SerDes ports are not timed by nextpnr)
    parameter RX_NEG = 0,                  // 1: RX_DATA_O captured on negedge first
    parameter EYE_EN = 0,                  // RX_EYE_MEAS_EN in the bitstream (eye counters did not count with 0, TASK-5063)
    parameter PROFILE = 0,                 // analog/CDR set: 0 = serdes_lb.v (0.3-1.25 Gb/s proven), 1 = pu-cc 5G (ab7ce94), 2 = TASK-5066 5G
    parameter TX_DET_RX = 0,               // TX_DETECT_RX_I: 0 = upstream since pu-cc dda07f7 (TASK-5066 E1); bits before 5066 had 1
    parameter TX_CALIB = 1,                // TX_CALIB_EN in every profile (TASK-5066 E1); bits before 5066: PROFILE 0 had 0
    parameter PLL_RTERM = 1                // PLL_REF_RTERM (refclk LVDS termination; E6: 0 on gs, TUNING_5G.md §2.4)
) (
    input  wire clk_i,          // IO_SB_A8 (GS: 25 MHz)
    output wire uart_tx,
    input  wire uart_rx
);
    localparam [2:0] MY_ID   = (ROLE == 0) ? 3'd5 : 3'd3;   // 101 vs 011: inverted (P/N swap) ids are 010/100 = neither
    localparam [2:0] PEER_ID = (ROLE == 0) ? 3'd3 : 3'd5;
    localparam [1:0] OD = (OUTDIV == 1) ? 2'd0 : (OUTDIV == 2) ? 2'd1 : 2'd3;
    localparam [7:0] CFG = {LOOPBACK_SEL, RX_POL[0], OD, ROLE[0], 1'b0};
    localparam [7:0] VER = 8'hB2 + PROFILE[3:0];   // B2 = one-hot aux frame write (TASK-5063); +PROFILE

    // ------------------------------------------------ reset (as serdes_lb.v: POR on clk_i)
    reg [8:0] rst_cnt = 0; wire rst = ~&rst_cnt;
    always @(posedge clk_i) rst_cnt <= rst_cnt + rst;

    // ------------------------------------------------ CC_SERDES analog/CDR profile
    // PROFILE 1 = Patrick Urban's "prepare 5G tests" set (pu-cc/gm_serdes_lb ab7ce94): DFE adaption on, more AFE
    // peaking, TX pre/post-cursor 5 of 12 branches, full TX current, TX termination calibration, faster CDR loop.
    // PROFILE 2 = PROFILE 1 + the best 5 Gb/s point of the TASK-5066 JTAG sweeps (docs/VERIFY_20260926_RATES.md §9):
    // AFE GAIN 0 PEAK 12 (E2), CDR CKP 0x1E TRANS_TH 16 (E4), TX FFE post-cursor only: 31 post branches,
    // DC_ENABLE 47 = (0+63+31)/2, SEL_POST 12 (E3). No point of the sweeps was clearly better than PROFILE 1 at 5 G.
    localparam P1 = (PROFILE == 1) || (PROFILE == 2);
    localparam P2 = (PROFILE == 2);
    localparam [4:0] A_TIMER_PRESC  = P1 ? 5'h4  : 5'h0;
    localparam [2:0] A_RTERM_VCMSEL = P1 ? 3'h3  : 3'h4;
    localparam [0:0] A_EN_EQA       = P1 ? 1'h1  : 1'h0;
    localparam [3:0] A_EQA_LOCK_CFG = P1 ? 4'hC  : 4'h0;
    localparam [4:0] A_AFE_PEAK     = P2 ? 5'hC  : P1 ? 5'h18 : 5'hF;
    localparam [3:0] A_AFE_GAIN     = P1 ? 4'h0  : 4'h8;
    localparam [2:0] A_AFE_VCMSEL   = P1 ? 3'h3  : 3'h4;
    localparam [7:0] A_CDR_CKP      = P2 ? 8'h1E : P1 ? 8'h3E : 8'hF8;
    localparam [8:0] A_CDR_TRANS_TH = P2 ? 9'h10 : P1 ? 9'h08 : 9'h80;   // the primitive field is 7 bits (default 7'h08)
    localparam [7:0] A_CDR_LOCK_CFG = P1 ? 8'hD5 : 8'h0B;
    localparam [4:0] A_TX_SEL_PRE   = P2 ? 5'h0  : P1 ? 5'h5  : 5'h0;
    localparam [4:0] A_TX_SEL_POST  = P2 ? 5'hC  : P1 ? 5'h5  : 5'h0;
    localparam [4:0] A_TX_AMP       = P1 ? 5'h1F : 5'hF;
    localparam [4:0] A_TX_BR_PRE    = P2 ? 5'h0  : P1 ? 5'hC  : 5'h0;
    localparam [4:0] A_TX_BR_POST   = P2 ? 5'h1F : P1 ? 5'hC  : 5'h0;
    localparam [6:0] A_TX_DC_ENABLE = P2 ? 7'h2F : P1 ? 7'h2B : 7'h3F;   // P1: (12+63+12)/2 = 43 as in ab7ce94
    localparam [0:0] A_TX_CALIB_EN  = TX_CALIB[0];

    // ------------------------------------------------ CC_SERDES (parameters as serdes_lb_dut.v)
    parameter [27:0] kChar = {8'hBC, 10'h283, 10'h17C};
    parameter [2:0]  PRBS_SEL = 3'b000;
    parameter [1:0]  TX_PMA_LOOPBACK = 2'b00;
    parameter [1:0]  DATAPATH_SEL = 2'b11;
    parameter [5:0]  PLL_FCNTRL = FCNTRL;
    parameter [5:0]  PLL_MAIN_DIVSEL = {1'b0,
        N3 == 3 ? 2'b00 : (N3 == 4 ? 2'b10 : 2'b11), N1 == 1 ? 1'b0 : 1'b1,
        N2 == 3 ? 2'b00 : (N2 == 2 ? 2'b01 : (N2 == 4 ? 2'b10 : 2'b11))};
    parameter [1:0]  PLL_OUT_DIVSEL = OD;
    parameter [14:0] RX_EYE_MEAS_CFG = 15'b0;

    wire pll_clk_o, rx_clk_o, tclk, rclk;
    wire [63:0] tx_data, rx_data; wire [7:0] tx_k, rx_k, rx_nit, rx_disp;
    // nextpnr (himbaechel/gatemate delay.cc) marks every SERDES port TMG_IGNORE: the fabric<->SerDes data paths are
    // not timed. TX_NEG/RX_NEG move the transfer half a word clock away from the rising edge (TASK-5063).
    reg [63:0] txd_n = 0, rxd_n = 0; reg [7:0] txk_n = 0, rxk_n = 0, rxnit_n = 0, rxdisp_n = 0;
    wire [63:0] rx_data_o; wire [7:0] rx_k_o, rx_nit_o, rx_disp_o;
    always @(negedge tclk) begin txd_n <= tx_data; txk_n <= tx_k; end
    always @(negedge rclk) begin rxd_n <= rx_data_o; rxk_n <= rx_k_o; rxnit_n <= rx_nit_o; rxdisp_n <= rx_disp_o; end
    wire [63:0] txd_s = TX_NEG ? txd_n : tx_data; wire [7:0] txk_s = TX_NEG ? txk_n : tx_k;
    assign rx_data = RX_NEG ? rxd_n : rx_data_o; assign rx_k = RX_NEG ? rxk_n : rx_k_o;
    assign rx_nit = RX_NEG ? rxnit_n : rx_nit_o; assign rx_disp = RX_NEG ? rxdisp_n : rx_disp_o;
    wire txrd, rxrd, txde, txdp, txbe, rxbe, prbse;
    CC_BUFG u_bt (.I(pll_clk_o), .O(tclk));
    CC_BUFG u_br (.I(rx_clk_o),  .O(rclk));

    CC_SERDES #(
`include "cc_serdes_params.vh"
    ) i_cc_serdes (
        .RX_CLK_O(rx_clk_o), .PLL_CLK_O(pll_clk_o), .LOOPBACK_I(LOOPBACK_SEL),
        .TX_RESET_I(rst), .RX_RESET_I(rst), .PLL_RESET_I(rst),
        .RX_PMA_RESET_I(1'b0), .RX_EQA_RESET_I(1'b0), .RX_CDR_RESET_I(1'b0), .RX_PCS_RESET_I(1'b0),
        .RX_BUF_RESET_I(1'b0), .TX_PCS_RESET_I(1'b0), .TX_PMA_RESET_I(1'b0),
        .TX_RESET_DONE_O(txrd), .RX_RESET_DONE_O(rxrd),
        .TX_CLK_I(CLK_DIRECT ? pll_clk_o : tclk), .TX_DATA_I(txd_s), .TX_POWER_DOWN_N_I(1'b1), .TX_POLARITY_I(1'b0),
        .TX_PRBS_SEL_I(3'b000), .TX_PRBS_FORCE_ERR_I(1'b0), .TX_8B10B_EN_I(1'b1), .TX_8B10B_BYPASS_I(8'h0),
        .TX_CHAR_IS_K_I(txk_s), .TX_CHAR_DISPMODE_I(8'h0), .TX_CHAR_DISPVAL_I(8'h0),
        .TX_ELEC_IDLE_I(1'b0), .TX_DETECT_RX_I(TX_DET_RX[0]), .TX_BUF_ERR_O(txbe),
        .RX_CLK_I(CLK_DIRECT ? rx_clk_o : rclk), .RX_POWER_DOWN_N_I(1'b1), .RX_POLARITY_I(RX_POL),
        .RX_PRBS_SEL_I(3'b000), .RX_PRBS_CNT_RESET_I(1'b0), .RX_PRBS_ERR_O(prbse),
        .RX_8B10B_EN_I(1'b1), .RX_8B10B_BYPASS_I(8'h0), .RX_EN_EI_DETECTOR_I(1'b0),
        .RX_COMMA_DETECT_EN_I(1'b1), .RX_SLIDE_I(1'b0), .RX_MCOMMA_ALIGN_I(1'b1), .RX_PCOMMA_ALIGN_I(1'b1),
        .RX_DATA_O(rx_data_o), .RX_NOT_IN_TABLE_O(rx_nit_o), .RX_CHAR_IS_COMMA_O(), .RX_CHAR_IS_K_O(rx_k_o),
        .RX_DISP_ERR_O(rx_disp_o), .TX_DETECT_RX_DONE_O(txde), .TX_DETECT_RX_PRESENT_O(txdp),
        .RX_BUF_ERR_O(rxbe), .RX_BYTE_IS_ALIGNED_O(), .RX_BYTE_REALIGN_O(), .RX_EI_EN_O(),
        .REGFILE_CLK_I(1'b0), .REGFILE_WE_I(1'b0), .REGFILE_EN_I(1'b0), .REGFILE_ADDR_I(8'h0),
        .REGFILE_DI_I(16'h0), .REGFILE_MASK_I(16'h0), .REGFILE_DO_O(), .REGFILE_RDY_O()
    );

    // ------------------------------------------------ cross-domain toggles (all quasi-static)
    reg  u_clr_t = 0, u_inj_t = 0, u_req_t = 0;   // clk_i domain (UART)
    reg  [7:0] cmd_out = 8'h00;                    // clk_i domain, to peer via TX aux
    reg  c_clr_t = 0, c_inj_t = 0;                 // rclk domain (commands from peer)
    reg  t_req_t = 0;                              // tclk domain: aux snapshot request

    // ------------------------------------------------ RX checker (rclk)
    reg [2:0] s_uclr = 0, s_ureq = 0, s_treq = 0;
    always @(posedge rclk) begin s_uclr <= {s_uclr[1:0], u_clr_t}; s_ureq <= {s_ureq[1:0], u_req_t}; s_treq <= {s_treq[1:0], t_req_t}; end
    wire synced, self_seen, peer_stb; wire [47:0] words; wire [31:0] errw, errb, code, pframes;
    wire [4:0] loss; wire [255:0] pfr;
    ber_rx #(.MY_ID(MY_ID), .PEER_ID(PEER_ID)) u_rx (.clk(rclk), .rx_data(rx_data), .rx_k(rx_k),
        .rx_code_err(|rx_nit | |rx_disp), .clr_tgl(s_uclr[2] ^ c_clr_t),
        .synced(synced), .self_seen(self_seen), .word_cnt(words), .err_words(errw), .err_bits(errb),
        .code_err(code), .loss_cnt(loss), .peer_frame(pfr), .peer_frames(pframes), .peer_stb(peer_stb));
    wire [7:0] flg = {synced, self_seen, 1'b0, loss};
    reg [7:0] exec = 0, pcmd_prev = 0; reg [31:0] rcnt = 0;
    wire [7:0] pcmd = pfr[20*8 +: 8];
    always @(posedge rclk) begin
        rcnt <= rcnt + 32'd1;
        if (peer_stb) begin
            pcmd_prev <= pcmd;
            if (pcmd != pcmd_prev) begin
                exec <= pcmd;
                if (pcmd[3:0] == 4'd1) c_clr_t <= ~c_clr_t;
                if (pcmd[3:0] == 4'd2) c_inj_t <= ~c_inj_t;
            end
        end
    end
    // snapshots (captured on request edges, then static until the next request)
    reg [159:0] snap_tx = 0;           // for the aux frame (tclk samples it 31 words later)
    reg [31:0] us_rcnt = 0; reg [7:0] us_flg = 0, us_exec = 0; reg [47:0] us_words = 0;
    reg [31:0] us_errw = 0, us_errb = 0, us_code = 0, us_pframes = 0; reg [255:0] us_pfr = 0;
    always @(posedge rclk) begin
        if (s_treq[2] ^ s_treq[1]) snap_tx <= {exec, flg, code, errb, errw, words};
        if (s_ureq[2] ^ s_ureq[1]) begin
            us_rcnt <= rcnt; us_flg <= flg; us_exec <= exec; us_words <= words; us_errw <= errw;
            us_errb <= errb; us_code <= code; us_pframes <= pframes; us_pfr <= pfr;
        end
    end

    // ------------------------------------------------ TX (tclk)
    reg [2:0] t_uinj = 0, t_cinj = 0, t_ureq = 0; reg [7:0] t_cmd1 = 0, t_cmd2 = 0, t_cmd = 0;
    reg [31:0] tcnt = 0, ut_tcnt = 0; reg [7:0] ut_inj = 0;
    wire [4:0] slot; wire [7:0] inj_cnt;
    always @(posedge tclk) begin
        t_uinj <= {t_uinj[1:0], u_inj_t}; t_cinj <= {t_cinj[1:0], c_inj_t}; t_ureq <= {t_ureq[1:0], u_req_t};
        t_cmd1 <= cmd_out; t_cmd2 <= t_cmd1; if (t_cmd1 == t_cmd2) t_cmd <= t_cmd2;
        tcnt <= tcnt + 32'd1;
        if (slot == 5'd0) t_req_t <= ~t_req_t;
        if (t_ureq[2] ^ t_ureq[1]) begin ut_tcnt <= tcnt; ut_inj <= inj_cnt; end
    end
    wire [255:0] aux_in = {64'h0, CFG, VER, inj_cnt, t_cmd, snap_tx};
    ber_tx #(.MY_ID(MY_ID)) u_tx (.clk(tclk), .inject_tgl(t_uinj[2] ^ t_cinj[2]), .aux_in(aux_in),
        .tx_data(tx_data), .tx_k(tx_k), .slot(slot), .inj_cnt(inj_cnt));

    // ------------------------------------------------ UART report + commands (clk_i, gs only)
    generate if (ROLE == 0) begin : g_uart
`include "report_fmt.vh"
        localparam DIV = 217;                         // 25 MHz / 115200
        reg [24:0] sec = 0; reg [31:0] t25 = 0, t25_s = 0;
        reg [7:0] idx = LINE_LEN; reg [9:0] sh = 10'h3FF; reg [3:0] nb = 0; reg [7:0] bd = 0;
        reg [REP_BITS-1:0] rep = 0; reg [7:0] wait_c = 0; reg pend = 0;
        always @(posedge clk_i) begin
            t25 <= t25 + 32'd1;
            sec <= (sec == SEC - 1) ? 25'd0 : sec + 25'd1;
            if (sec == 25'd0) begin u_req_t <= ~u_req_t; t25_s <= t25; wait_c <= 8'd200; pend <= 1'b1; end
            else if (wait_c != 0) wait_c <= wait_c - 8'd1;
            else if (pend && idx == LINE_LEN) begin
                pend <= 1'b0; idx <= 8'd0;
                rep <= {t25_s, ut_tcnt, us_rcnt, us_flg, us_words, us_errw, us_errb, us_code, ut_inj,
                        us_exec, cmd_out, CFG,
                        us_pfr[47:0], us_pfr[79:48], us_pfr[111:80], us_pfr[143:112], us_pfr[151:144],
                        us_pfr[159:152], us_pfr[167:160], us_pfr[175:168], us_pfr[183:176], us_pfr[191:184],
                        us_pframes};
            end
            // byte transmitter
            if (bd != 0) bd <= bd - 8'd1;
            else if (nb != 0) begin sh <= {1'b1, sh[9:1]}; nb <= nb - 4'd1; bd <= DIV - 1; end
            else if (idx != LINE_LEN) begin sh <= {1'b1, char_at(idx, rep), 1'b0}; nb <= 4'd10; idx <= idx + 8'd1; bd <= DIV - 1; end
        end
        assign uart_tx = sh[0];
        // receiver: 'z' clear local, 'e' inject on gs TX, 'Z' clear local+peer, 'E' peer injects on its TX
        reg [2:0] rs = 3'b111; reg [7:0] rb = 0; reg [3:0] rn = 0; reg [8:0] rd = 0; reg rbusy = 0;
        always @(posedge clk_i) begin
            rs <= {rs[1:0], uart_rx};
            if (!rbusy) begin
                if (!rs[2]) begin rbusy <= 1'b1; rd <= DIV + DIV/2; rn <= 4'd0; end
            end else if (rd != 0) rd <= rd - 9'd1;
            else if (rn < 8) begin rb <= {rs[2], rb[7:1]}; rn <= rn + 4'd1; rd <= DIV - 1; end
            else begin
                rbusy <= 1'b0;
                case (rb)
                    "z": u_clr_t <= ~u_clr_t;
                    "e": u_inj_t <= ~u_inj_t;
                    "Z": begin u_clr_t <= ~u_clr_t; cmd_out <= {cmd_out[7:4] + 4'd1, 4'd1}; end
                    "E": cmd_out <= {cmd_out[7:4] + 4'd1, 4'd2};
                    default: ;
                endcase
            end
        end
    end else begin : g_nouart
        assign uart_tx = 1'b1;
    end endgenerate
endmodule

module top_gs #(parameter N1 = 1, N2 = 2, N3 = 3, OUTDIV = 4, parameter [5:0] FCNTRL = 6'h3A,
                parameter RX_POL = 1'b1, parameter [2:0] LOOPBACK_SEL = 3'b000, parameter CLK_DIRECT = 0, parameter TX_NEG = 0, parameter RX_NEG = 0, parameter PROFILE = 0, parameter EYE_EN = 0,
                parameter TX_DET_RX = 0, parameter TX_CALIB = 1, parameter PLL_RTERM = 1)
               (input wire clk_i, output wire uart_tx, input wire uart_rx);
    ber_top #(.ROLE(0), .N1(N1), .N2(N2), .N3(N3), .OUTDIV(OUTDIV), .FCNTRL(FCNTRL), .RX_POL(RX_POL),
              .LOOPBACK_SEL(LOOPBACK_SEL), .CLK_DIRECT(CLK_DIRECT), .TX_NEG(TX_NEG), .RX_NEG(RX_NEG), .PROFILE(PROFILE), .EYE_EN(EYE_EN),
              .TX_DET_RX(TX_DET_RX), .TX_CALIB(TX_CALIB), .PLL_RTERM(PLL_RTERM)) u (.clk_i(clk_i), .uart_tx(uart_tx), .uart_rx(uart_rx));
endmodule

module top_m2 #(parameter N1 = 1, N2 = 2, N3 = 3, OUTDIV = 4, parameter [5:0] FCNTRL = 6'h3A,
                parameter RX_POL = 1'b1, parameter [2:0] LOOPBACK_SEL = 3'b000, parameter CLK_DIRECT = 0, parameter TX_NEG = 0, parameter RX_NEG = 0, parameter PROFILE = 0, parameter EYE_EN = 0,
                parameter TX_DET_RX = 0, parameter TX_CALIB = 1, parameter PLL_RTERM = 1)
               (input wire clk_i);
    ber_top #(.ROLE(1), .N1(N1), .N2(N2), .N3(N3), .OUTDIV(OUTDIV), .FCNTRL(FCNTRL), .RX_POL(RX_POL),
              .LOOPBACK_SEL(LOOPBACK_SEL), .CLK_DIRECT(CLK_DIRECT), .TX_NEG(TX_NEG), .RX_NEG(RX_NEG), .PROFILE(PROFILE), .EYE_EN(EYE_EN),
              .TX_DET_RX(TX_DET_RX), .TX_CALIB(TX_CALIB), .PLL_RTERM(PLL_RTERM)) u (.clk_i(clk_i), .uart_tx(), .uart_rx(1'b1));
endmodule
