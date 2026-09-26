// TASK-4999 fab2: why do flops not toggle?
//  PLL a: USR_CLK_REF = clk25 & USR_RSTN (no flop)          -> LOCKED iff user reset released
//  PLL b: toggle flop, clock = clk25 on LOCAL routing        -> LOCKED iff flop runs off-global
//  PLL c: toggle flop, clock = clk25 via explicit CC_BUFG    -> (fab1 PLL0 case)
//  PLL d: CLK_REF dedicated (control)
module top(input clk25, output led4, output led5, output led6, output led7);
  wire rstn;
  CC_USR_RSTN ur (.USR_RSTN(rstn));
  wire ga = clk25 & rstn;
  (* clkbuf_inhibit *) wire clk_loc = clk25;
  reg tb = 1'b0; always @(posedge clk_loc) tb <= ~tb;
  wire clk_g; CC_BUFG bg (.I(clk25), .O(clk_g));
  reg tc = 1'b0; always @(posedge clk_g) tc <= ~tc;
  wire oa, ob, oc, od;
  CC_PLL #(.REF_CLK("25.0"), .OUT_CLK("25.0"), .PERF_MD("LOWPOWER"), .LOW_JITTER(1), .CI_FILTER_CONST(2), .CP_FILTER_CONST(4), .LOCK_REQ(0))
    pll_a (.CLK_REF(1'b0), .USR_CLK_REF(ga), .CLK_FEEDBACK(1'b0), .USR_LOCKED_STDY_RST(1'b0), .CLK0(oa));
  CC_PLL #(.REF_CLK("12.5"), .OUT_CLK("25.0"), .PERF_MD("LOWPOWER"), .LOW_JITTER(1), .CI_FILTER_CONST(2), .CP_FILTER_CONST(4), .LOCK_REQ(0))
    pll_b (.CLK_REF(1'b0), .USR_CLK_REF(tb), .CLK_FEEDBACK(1'b0), .USR_LOCKED_STDY_RST(1'b0), .CLK0(ob));
  CC_PLL #(.REF_CLK("12.5"), .OUT_CLK("25.0"), .PERF_MD("LOWPOWER"), .LOW_JITTER(1), .CI_FILTER_CONST(2), .CP_FILTER_CONST(4), .LOCK_REQ(0))
    pll_c (.CLK_REF(1'b0), .USR_CLK_REF(tc), .CLK_FEEDBACK(1'b0), .USR_LOCKED_STDY_RST(1'b0), .CLK0(oc));
  CC_PLL #(.REF_CLK("25.0"), .OUT_CLK("25.0"), .PERF_MD("LOWPOWER"), .LOW_JITTER(1), .CI_FILTER_CONST(2), .CP_FILTER_CONST(4), .LOCK_REQ(0))
    pll_d (.CLK_REF(clk25), .USR_CLK_REF(1'b0), .CLK_FEEDBACK(1'b0), .USR_LOCKED_STDY_RST(1'b0), .CLK0(od));
  reg [3:0] a=0,b=0,c=0,d=0;
  always @(posedge oa) a<=a+1; always @(posedge ob) b<=b+1; always @(posedge oc) c<=c+1; always @(posedge od) d<=d+1;
  assign led4=a[3]; assign led5=b[3]; assign led6=c[3]; assign led7=d[3];
endmodule
