module dut_top(input wire clk_i, input wire pll_rstn_i, trx_rstn_i,
               output wire LED0,LED1,LED2,LED3,LED4,LED5,LED6,LED7);
    wire [63:0] rxd;
    wire pll_clk, rx_clk, rxrd_n, txrd_n, txdp_n, txdd_n, txbuf_n, rxbuf_n, prbs_n;
    serdes_lb u_dut(
        .pll_rstn_i(pll_rstn_i), .trx_rstn_i(trx_rstn_i), .ref_clk(clk_i),
        .RX_PRBS_CNT_RESET_I(1'b0), .TX_PRBS_FORCE_ERR_I(1'b0),
        .RX_DATA_O(rxd), .PLL_CLK_O(pll_clk), .RX_CLK_O(rx_clk),
        .RX_RESET_DONE_O_N(rxrd_n), .TX_RESET_DONE_O_N(txrd_n),
        .TX_DETECT_RX_PRESENT_O_N(txdp_n), .TX_DETECT_RX_DONE_O_N(txdd_n),
        .TX_BUF_ERR_O_N(txbuf_n), .RX_BUF_ERR_O_N(rxbuf_n), .RX_PRBS_ERR_O_N(prbs_n));
    reg [22:0] hb=0; always @(posedge clk_i) hb<=hb+1'b1;
    assign LED0=~rxrd_n; assign LED1=~txrd_n; assign LED2=~txdd_n; assign LED3=~txdp_n;
    assign LED4=rxbuf_n; assign LED5=txbuf_n; assign LED6=prbs_n; assign LED7=hb[22];
endmodule
