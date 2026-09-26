`timescale 1ns/1ps
module tb;
  reg clk = 0; always #20 clk = ~clk;
  reg rxc = 0; always #20 rxc = ~rxc;
  wire ua, ub, mdc, rst_n; wire mdio; pullup(mdio);
  top dut(.clk25(clk), .uart_a(ua), .uart_b(ub), .mdc(mdc), .mdio(mdio), .rst_n(rst_n), .rxc(rxc), .rx_ctl(1'b0));
  integer n = 0; integer ut = 0; always @(ua) ut = ut + 1;
  always @(posedge dut.print_req) begin n = n + 1; $display("%t print_req passes=%h idm=%h r1=%h", $time, dut.passes, dut.idm, dut.r1); end
  initial begin
    #1; $display("start");
    #(40*7000000);
    $display("uart toggles=%0d", ut); $display("end: wst=%d step=%d busy=%b start=%b up=%h gap=%h ph=%h passes=%h us=%d preq=%b", dut.wst, dut.step, dut.busy, dut.start, dut.up, dut.gap, dut.ph, dut.passes, dut.us, dut.preq);
    $finish;
  end
endmodule
