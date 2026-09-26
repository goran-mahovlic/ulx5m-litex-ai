`timescale 1ns/1ps
module tb;
  reg clk = 0; always #20 clk = ~clk;
  wire l4,l5,l6,l7;
  top #(.NSTAGE(31)) dut(.clk25_pin(clk), .led4(l4), .led5(l5), .led6(l6), .led7(l7));
  initial begin force dut.r[0] = 1'b0; #5; release dut.r[0]; end
  initial begin #60000000; $display("ro_cnt=%0d idx=%0d data=%h", dut.ro_cnt, dut.idx, dut.data); $finish; end
endmodule
