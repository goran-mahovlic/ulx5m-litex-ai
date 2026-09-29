// selfrst_tb.v (TASK-5095): selfrst drives RST_N low only after the bytes "R!" (0x52 0x21), never after 0x00 or "R".
`timescale 1ns/1ps
module tb;
  reg clk = 0, rx = 1; always #20 clk = ~clk;              // 25 MHz
  wire rst_oe;
  selfrst dut (.clk(clk), .rx(rx), .rst_oe(rst_oe));
  task sendb(input [7:0] b); integer k; begin
    rx = 0; #8680; for (k = 0; k < 8; k = k + 1) begin rx = b[k]; #8680; end rx = 1; #8680; end endtask
  integer fails = 0;
  task expect_oe(input v, input [8*24-1:0] what); begin
    #1000; if (rst_oe !== v) begin $display("FAIL %0s: rst_oe=%b want %b", what, rst_oe, v); fails = fails + 1; end
    else $display("ok   %0s: rst_oe=%b", what, rst_oe); end endtask
  initial begin
    #2000; expect_oe(0, "after start");
    sendb(8'h00); sendb(8'h00); expect_oe(0, "after 00 00");
    sendb("R"); expect_oe(0, "after R");
    sendb("x"); sendb("!"); expect_oe(0, "after x !");
    sendb("!"); expect_oe(0, "after lone !");
    sendb("R"); sendb("!"); expect_oe(1, "after R !");
    #100000; expect_oe(1, "stays asserted");
    if (fails) $display("RESULT FAIL %0d", fails); else $display("RESULT PASS");
    $finish;
  end
endmodule
