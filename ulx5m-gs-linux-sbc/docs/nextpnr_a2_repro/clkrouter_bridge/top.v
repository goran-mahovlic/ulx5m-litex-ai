// CCGM1A2 repro (TASK-5092): a PLL output used as a clock WITHOUT CC_BUFG, with users on die 1B.
// Mirror strategy copies only BUFG'd clocks, so the clock router carries the die-0 PLL output across
// the die through the general fabric (incl. CPE bridges) and locks those wires before router2 runs.
module top #(parameter N = 64) (input clk25, input rst, output led);
  wire pclk;
  CC_PLL #(.REF_CLK("25.0"), .OUT_CLK("60.0"), .PERF_MD("ECONOMY"), .LOW_JITTER(1), .CI_FILTER_CONST(2),
           .CP_FILTER_CONST(4)) u_pll (.CLK_REF(clk25), .CLK_FEEDBACK(1'b0), .USR_CLK_REF(1'b0),
           .USR_LOCKED_STDY_RST(1'b0), .CLK0(pclk));
  reg [31:0] s [0:N-1];
  reg [N-1:0] x;
  integer i;
  always @(posedge pclk) begin
    for (i = 0; i < N; i = i + 1) begin
      if (rst) s[i] <= 32'h1 + i;
      else s[i] <= {s[i][30:0], s[i][31] ^ s[i][21] ^ s[i][1] ^ s[i][0] ^ s[(i+1)%N][i%32]};
      x[i] <= ^s[i];
    end
  end
  assign led = ^x;
endmodule
