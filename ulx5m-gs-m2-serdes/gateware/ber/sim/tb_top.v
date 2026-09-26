`timescale 1ns/1ps
module tbt; reg clk = 0; always #20 clk = ~clk; wire tx;
  top_gs_sim u(.clk_i(clk), .uart_tx(tx), .uart_rx(1'b1));
  // UART decoder at 115200 with 25 MHz clk: bit = 217 clk = 8680 ns
  integer i; reg [7:0] c;
  initial begin
    forever begin @(negedge tx); #(8680*1.5); for (i=0;i<8;i=i+1) begin c[i]=tx; #8680; end $write("%c", c); end
  end
  initial begin #30_000_000; $display("\n[end]"); $finish; end
endmodule
module top_gs_sim(input clk_i, output uart_tx, input uart_rx);
  ber_top #(.ROLE(0), .SEC(100_000)) u(.clk_i(clk_i), .uart_tx(uart_tx), .uart_rx(uart_rx));
endmodule
