// TASK-4999 fabric liveness test: does fabric logic run? Read PLL states over JTAG.
//  pll_dir : USR_CLK_REF = clk25 routed through fabric, no flop     (REF 25)
//  pll_div : USR_CLK_REF = clk25/2 from ONE toggle flop              (REF 12.5)  == TASK-5007 cal2
//  pll_ded : CLK_REF     = clk25 dedicated input (positive control) (REF 25)
module top(input clk25, output led5, output led6, output led7, output led4);
  reg div = 1'b0;
  always @(posedge clk25) div <= ~div;
  wire o_dir, o_div, o_ded;
  CC_PLL #(.REF_CLK("25.0"), .OUT_CLK("25.0"), .PERF_MD("LOWPOWER"), .LOW_JITTER(1),
           .CI_FILTER_CONST(2), .CP_FILTER_CONST(4), .LOCK_REQ(0))
    pll_dir (.CLK_REF(1'b0), .USR_CLK_REF(clk25), .CLK_FEEDBACK(1'b0), .USR_LOCKED_STDY_RST(1'b0), .CLK0(o_dir));
  CC_PLL #(.REF_CLK("12.5"), .OUT_CLK("25.0"), .PERF_MD("LOWPOWER"), .LOW_JITTER(1),
           .CI_FILTER_CONST(2), .CP_FILTER_CONST(4), .LOCK_REQ(0))
    pll_div (.CLK_REF(1'b0), .USR_CLK_REF(div), .CLK_FEEDBACK(1'b0), .USR_LOCKED_STDY_RST(1'b0), .CLK0(o_div));
  CC_PLL #(.REF_CLK("25.0"), .OUT_CLK("25.0"), .PERF_MD("LOWPOWER"), .LOW_JITTER(1),
           .CI_FILTER_CONST(2), .CP_FILTER_CONST(4), .LOCK_REQ(0))
    pll_ded (.CLK_REF(clk25), .USR_CLK_REF(1'b0), .CLK_FEEDBACK(1'b0), .USR_LOCKED_STDY_RST(1'b0), .CLK0(o_ded));
  reg [3:0] a = 0, b = 0, c = 0;
  always @(posedge o_dir) a <= a + 1;
  always @(posedge o_div) b <= b + 1;
  always @(posedge o_ded) c <= c + 1;
  // slow counter on clk25: LED4 blinks if fabric flops run
  reg [24:0] s = 0; always @(posedge clk25) s <= s + 1;
  assign led5 = a[3]; assign led6 = b[3]; assign led7 = c[3]; assign led4 = s[24];
endmodule
