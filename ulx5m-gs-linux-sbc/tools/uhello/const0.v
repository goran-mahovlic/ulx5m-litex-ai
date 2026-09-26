module top(input clk25, output uart);
  reg [3:0] c = 0; always @(posedge clk25) c <= c + 1;
  assign uart = 1'b0 | (c == 4'hF & 1'b0);
endmodule
