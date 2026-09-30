// top_tb.v (TASK-5094): rxprobe prints the counters it sees. RXC 25 MHz, RX_CTL pulses (3 frames), RXD0 toggling.
`timescale 1ns/1ps
module tb;
  reg clk = 0, rxc = 0, ctl = 0, d0 = 0; always #20 clk = ~clk; always #20 rxc = ~rxc;
  wire tx, rst_pad, rstn;
  top dut (.clk25(clk), .serial_rx(1'b1), .serial_tx(tx), .rst_pad(rst_pad), .eth_clocks_rx(rxc), .eth_rx_ctl(ctl),
           .eth_rx_d0(d0), .eth_rst_n(rstn));
  integer k; reg [7:0] b; reg [8*40-1:0] line = 0; integer n = 0;
  initial begin
    #2000; repeat (3) begin @(negedge rxc); ctl = 1; repeat (50) begin @(negedge rxc); d0 = ~d0; end ctl = 0; #4000; end
  end
  initial forever begin
    @(negedge tx); #4340; b = 0; for (k = 0; k < 8; k = k + 1) begin #8680; b[k] = tx; end #8680;
    if (b == 8'h0a) begin $display("LINE %0s", line); n = n + 1; line = 0; if (n == 2) begin
        if (line == 0) ; $finish; end end
    else if (b != 8'h0d) line = {line[8*39-1:0], b};
  end
  initial begin #1400000000; $display("TIMEOUT"); $finish; end
endmodule
