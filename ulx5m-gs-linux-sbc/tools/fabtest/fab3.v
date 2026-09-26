// TASK-4999 fab3: ECONOMY PLL as a 1-bit level detector at 1.1 V.
//  a: ref alternates /2 <-> /8 every 2^24 clk25 cycles (0.67 s)
//  b: ref alternates /2 <-> /4 every 0.67 s
//  c: constant /2      d: constant /8
module top(input clk25_pin, output led4, output led5, output led6, output led7);
  wire clk25; CC_BUFG bgc (.I(clk25_pin), .O(clk25));
  reg [23:0] t = 0; always @(posedge clk25) t <= t + 1;
  reg lvl = 0; always @(posedge clk25) if (&t) lvl <= ~lvl;
  function [0:0] dummy; input x; dummy = x; endfunction
  // dividers
  reg [2:0] ca=0, cb=0, cd8=0; reg ga=0, gb=0, gc=0, gd=0;
  wire [2:0] pa = lvl ? 3'd2 : 3'd8 - 3'd0; // 8 does not fit 3 bits -> use 4-bit below
  reg [3:0] da=0, db=0, dd=0;
  wire [3:0] pera = lvl ? 4'd2 : 4'd8;
  wire [3:0] perb = lvl ? 4'd2 : 4'd4;
  always @(posedge clk25) begin
    da <= (da >= pera-1) ? 4'd0 : da + 1; ga <= (da < (pera>>1));
    db <= (db >= perb-1) ? 4'd0 : db + 1; gb <= (db < (perb>>1));
    gc <= ~gc;
    dd <= (dd >= 4'd7) ? 4'd0 : dd + 1; gd <= (dd < 4'd4);
  end
  (* clkbuf_inhibit *) wire oa; (* clkbuf_inhibit *) wire ob; (* clkbuf_inhibit *) wire oc; (* clkbuf_inhibit *) wire od;
  CC_PLL #(.REF_CLK("12.5"), .OUT_CLK("25.0"), .PERF_MD("ECONOMY"), .LOW_JITTER(1), .CI_FILTER_CONST(2), .CP_FILTER_CONST(4), .LOCK_REQ(0))
    pll_a (.CLK_REF(1'b0), .USR_CLK_REF(ga), .CLK_FEEDBACK(1'b0), .USR_LOCKED_STDY_RST(1'b0), .CLK0(oa));
  CC_PLL #(.REF_CLK("12.5"), .OUT_CLK("25.0"), .PERF_MD("ECONOMY"), .LOW_JITTER(1), .CI_FILTER_CONST(2), .CP_FILTER_CONST(4), .LOCK_REQ(0))
    pll_b (.CLK_REF(1'b0), .USR_CLK_REF(gb), .CLK_FEEDBACK(1'b0), .USR_LOCKED_STDY_RST(1'b0), .CLK0(ob));
  CC_PLL #(.REF_CLK("12.5"), .OUT_CLK("25.0"), .PERF_MD("ECONOMY"), .LOW_JITTER(1), .CI_FILTER_CONST(2), .CP_FILTER_CONST(4), .LOCK_REQ(0))
    pll_c (.CLK_REF(1'b0), .USR_CLK_REF(gc), .CLK_FEEDBACK(1'b0), .USR_LOCKED_STDY_RST(1'b0), .CLK0(oc));

  reg [3:0] a=0,b=0,c=0,d=0;
  always @(posedge oa) a<=a+1; always @(posedge ob) b<=b+1; always @(posedge oc) c<=c+1; 
  assign led4=a[3]; assign led5=b[3]; assign led6=c[3]; assign led7=lvl ^ gd;
endmodule
