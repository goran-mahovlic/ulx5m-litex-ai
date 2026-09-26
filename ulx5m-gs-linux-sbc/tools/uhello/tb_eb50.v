`timescale 1ns/1ps
// TASK-4999 eb50: PHY-side RGMII 100M check. KSZ9031: TXD on TXC rise, TX_CTL on both edges (rise=TX_EN,
// fall=TX_EN^TX_ER), setup/hold >= 1 ns (DS00002117F tab. 7-1). Prints frames (hex) and min setup/hold.
module tb;
  reg clk = 0; always #20 clk = ~clk;
  reg rxc = 0; always #20 rxc = ~rxc;
  wire ua, ub, mdc, rst_n, txc, tx_ctl; wire [3:0] txd; wire mdio; pullup(mdio); wire [2:0] fl;
  top dut(.clk25(clk), .uart_a(ua), .uart_b(ub), .mdc(mdc), .mdio(mdio), .rst_n(rst_n), .rxc(rxc), .rx_ctl(1'b0),
          .txc(txc), .tx_ctl(tx_ctl), .txd(txd), .flag_load(fl));
  realtime last_chg = 0, last_edge = -1000, min_su = 1e9, min_ho = 1e9;
  always @(txd or tx_ctl) begin
    if ($realtime - last_edge < min_ho && last_edge > 0) min_ho = $realtime - last_edge;
    last_chg = $realtime;
  end
  always @(txc) if ($realtime > 100) begin
    if ($realtime - last_chg < min_su) min_su = $realtime - last_chg;
    last_edge = $realtime;
  end
  integer frames = 0, er = 0; reg [3:0] lo; reg have = 0; reg en = 0, prev = 0;
  always @(posedge txc) begin
    en = tx_ctl;
    if (en) begin
      if (!have) begin lo = txd; have = 1; end else begin $write("%02x", {txd, lo}); have = 0; end
    end else if (prev) begin $write("\n"); frames = frames + 1; have = 0; end
    prev = en;
  end
  always @(negedge txc) if ((tx_ctl ^ en) !== 1'b0) er = er + 1;   // TX_ER must stay 0
  initial begin #(40*600); $display("FRAMES=%0d TX_ER=%0d MIN_SETUP=%0.1f ns MIN_HOLD=%0.1f ns", frames, er, min_su, min_ho); $finish; end
endmodule
