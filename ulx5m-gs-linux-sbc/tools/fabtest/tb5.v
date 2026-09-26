`timescale 1ns/1ps
module tb;
  reg clk = 0; always #20 clk = ~clk;
  wire l4,l5,l6,l7;
  top dut(.clk25_pin(clk), .led4(l4), .led5(l5), .led6(l6), .led7(l7));
  initial begin
    #2000000;  // 2 ms = 50000 cycles
    $display("err=%b c1=%h c2=%h l1=%h l2=%h", dut.err, dut.c1, dut.c2, dut.l1, dut.l2);
    $finish;
  end
endmodule
