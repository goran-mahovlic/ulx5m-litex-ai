`timescale 1ns/1ps
module tb;
  reg clk = 0; always #20 clk = ~clk;
  reg rxc = 0; always #20 rxc = ~rxc;
  wire ua, ub, mdc, rst_n, txc, tx_ctl; wire [3:0] txd; wire mdio; pullup(mdio);
  top dut(.clk25(clk), .uart_a(ua), .uart_b(ub), .mdc(mdc), .mdio(mdio), .rst_n(rst_n), .rxc(rxc), .rx_ctl(1'b0),
          .txc(txc), .tx_ctl(tx_ctl), .txd(txd));
  // PHY-side capture: sample on TXC rising (as KSZ9031 at 100M), check TX_CTL also stable on TXC falling
  integer nn = 0, frames = 0, bad_ctl = 0; reg [3:0] lo; reg have = 0; reg prev = 0;
  always @(posedge txc) begin
    if (tx_ctl) begin
      if (!have) begin lo = txd; have = 1; end else begin $write("%02x", {txd, lo}); have = 0; end
    end else if (prev) begin $write("\n"); frames = frames + 1; have = 0; end
    prev = tx_ctl;
  end
  always @(negedge txc) if (tx_ctl !== prev) bad_ctl = bad_ctl + 1;
  initial begin #(40*300); $display("FRAMES=%0d BADCTL=%0d", frames, bad_ctl); $finish; end
endmodule
