// CCGM1A2 mirror-clock repro (TASK-5092): RGMII-like DDR input on die 1B (bank EB), logic on die 1A.
module top(input clk, input d, output q);
  wire gclk, d0, d1;
  CC_BUFG u_bufg (.I(clk), .O(gclk));
  CC_IDDR u_iddr (.D(d), .CLK(gclk), .Q0(d0), .Q1(d1));
  reg r0, r1;
  always @(posedge gclk) begin r0 <= d0 ^ d1; r1 <= r0; end
  assign q = r1;
endmodule
