`timescale 1ns/1ps
module tb;
  reg clk = 0; always #20 clk = ~clk;
  wire ua, ub, mdc, rst_n; wire mdio; pullup(mdio);
  top #(.WRITE_AFTER(8'd1), .REG0(16'h2100)) dut(.clk25(clk), .uart_a(ua), .uart_b(ub), .mdc(mdc), .mdio(mdio), .rst_n(rst_n), .rxc(clk), .rx_ctl(1'b0));
  reg [127:0] w = 0; integer n = 0, shown = 0; reg was = 0;
  always @(posedge mdc) if (dut.busy) begin w = {w[126:0], mdio}; n = n + 1; end
  always @(posedge clk) begin
    if (was && !dut.busy) begin
      if (!dut.rd && shown < 30) begin $display("frame n=%0d fr_in=%h wire=%h", n, dut.fr_in, w[63:0]); shown = shown + 1; end
      n = 0; w = 0;
    end
    was = dut.busy;
  end
  initial begin #(40*20000000); $finish; end
endmodule
