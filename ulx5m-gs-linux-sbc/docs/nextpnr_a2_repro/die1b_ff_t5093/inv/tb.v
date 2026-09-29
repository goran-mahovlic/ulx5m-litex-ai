`timescale 1ns/1ps
module tb;
  reg clk=0; always #20 clk=~clk;
  reg rx=1; wire tx; wire [7:0] led;
  top dut(.clk25(clk), .serial_rx(rx), .serial_tx(tx), .led(led));
  // decode UART 217 clocks/bit
  integer i; reg [7:0] b; reg [8*64-1:0] line; integer n=0, lines=0;
  initial begin
    #(40*300) rx=0; #(40*217*9) rx=1;   // one 0x00 byte = reset
  end
  always begin
    @(negedge tx);
    #(40*217/2); #(40*217);
    for (i=0;i<8;i=i+1) begin b[i]=tx; #(40*217); end
    if (b==8'h0a) begin $display("UART: %0s | %h", line, line[8*26-1:0]); n=0; line=0; lines=lines+1; if (lines==3) $finish; end
    else if (b!=8'h0d) begin line = {line[8*63-1:0], b}; n=n+1; end
  end
endmodule
