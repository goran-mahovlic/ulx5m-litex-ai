`timescale 1ns/1ps
module tb;
  reg clk = 0, rx = 1; always #20 clk = ~clk;
  wire tx; wire [7:0] led; wire rst_pad;
  pullup (rst_pad);                                     // R111 on the board
  top dut (.clk25(clk), .serial_rx(rx), .serial_tx(tx), .led(led), .rst_pad(rst_pad));
  task sendb(input [7:0] b); integer k; begin
    rx = 0; #8680; for (k = 0; k < 8; k = k + 1) begin rx = b[k]; #8680; end rx = 1; #8680; end endtask
  integer fails = 0;
  task chk(input v, input [8*20-1:0] w); begin #2000;
    if (rst_pad !== v) begin $display("FAIL %0s rst_pad=%b", w, rst_pad); fails = fails + 1; end
    else $display("ok   %0s rst_pad=%b", w, rst_pad); end endtask
  initial begin
    #5000; chk(1, "start");
    sendb(8'h00); sendb(8'h00); chk(1, "00 00");
    sendb("R"); chk(1, "R");
    sendb("R"); sendb("!"); chk(0, "R !");
    if (fails) $display("RESULT FAIL %0d", fails); else $display("RESULT PASS"); $finish;
  end
endmodule
