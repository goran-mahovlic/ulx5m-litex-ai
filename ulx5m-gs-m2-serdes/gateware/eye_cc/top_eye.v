// TASK-5525 (uputa #333): Patrick Urban's serdes_lb.v (mail UID 85, gateware/upstream_cc_20261015/, unchanged) on ULX5M GS / M2.
// Patrick sent it as a possible fix for RX_EYE_MEAS_EN never clearing. Only the board glue is ours:
//   OUTDIV 2 -> 2.5 Gb/s from the 100 MHz LVDS refclk (Patrick: OUTDIV 4 = 1.25 G), RX_POLARITY_I 1 (P/N swap in the adapter,
//   TASK-5524, = RX_POL 1 of every ber_* bit), trx_rstn_i 1, no fabric data: TX PRBS-15 -> far-end RX PRBS-15 checker.
// The eye path is driven over JTAG (SERDES_TESTMODE 1): tools/eyescan.py diagnose / eye.
module top_eye #(parameter OUTDIV = 2) (output uart_tx);
    assign uart_tx = 1'b1;
    serdes_lb #(.OUTDIV(OUTDIV)) u (
        .trx_rstn_i(1'b1), .RX_SLIDE_I(1'b0), .RX_BUF_RESET_I(1'b0), .RX_PRBS_CNT_RESET_I(1'b0), .RX_POLARITY_I(1'b1),
        .RX_DATA_O(), .RX_DISP_ERR_O(), .RX_CHAR_IS_K_O(), .PLL_CLK_O(), .RX_CLK_O(),
        .RX_RESET_DONE_O_N(), .TX_RESET_DONE_O_N(), .TX_DETECT_RX_PRESENT_O_N(), .TX_DETECT_RX_DONE_O_N(),
        .TX_BUF_ERR_O_N(), .RX_BUF_ERR_O_N(), .RX_BYTE_IS_ALIGNED_O_N(), .RX_BYTE_REALIGN_O_N());
endmodule
