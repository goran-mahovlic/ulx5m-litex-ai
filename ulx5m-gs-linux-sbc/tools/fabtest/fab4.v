// TASK-4999 fab4: ECONOMY ft for /3 and /2.5, and /2<->/3 switching every 2^22 cycles (168 ms)
module top(input clk25_pin, output led4, output led5, output led6, output led7);
  wire clk25; CC_BUFG bgc (.I(clk25_pin), .O(clk25));
  reg [21:0] t = 0; always @(posedge clk25) t <= t + 1;
  reg lvl = 0; always @(posedge clk25) if (&t) lvl <= ~lvl;
  reg [3:0] da=0, db=0, dc=0; reg ga=0, gb=0, gc=0, alt=0;
  wire [3:0] perb = lvl ? 4'd2 : 4'd3;
  wire [3:0] perc = alt ? 4'd3 : 4'd2;
  always @(posedge clk25) begin
    da <= (da >= 4'd2) ? 4'd0 : da + 1; ga <= (da < 4'd1);        // /3
    db <= (db >= perb-1) ? 4'd0 : db + 1; gb <= (db < (perb>>1)); // /2 <-> /3
    if (dc >= perc-1) begin dc <= 0; alt <= ~alt; end else dc <= dc + 1; gc <= (dc < (perc>>1)); // /2.5
  end
  (* clkbuf_inhibit *) wire oa; (* clkbuf_inhibit *) wire ob; (* clkbuf_inhibit *) wire oc;
  CC_PLL #(.REF_CLK("12.5"), .OUT_CLK("25.0"), .PERF_MD("ECONOMY"), .LOW_JITTER(1), .CI_FILTER_CONST(2), .CP_FILTER_CONST(4), .LOCK_REQ(0))
    pll_a (.CLK_REF(1'b0), .USR_CLK_REF(ga), .CLK_FEEDBACK(1'b0), .USR_LOCKED_STDY_RST(1'b0), .CLK0(oa));
  CC_PLL #(.REF_CLK("12.5"), .OUT_CLK("25.0"), .PERF_MD("ECONOMY"), .LOW_JITTER(1), .CI_FILTER_CONST(2), .CP_FILTER_CONST(4), .LOCK_REQ(0))
    pll_b (.CLK_REF(1'b0), .USR_CLK_REF(gb), .CLK_FEEDBACK(1'b0), .USR_LOCKED_STDY_RST(1'b0), .CLK0(ob));
  CC_PLL #(.REF_CLK("12.5"), .OUT_CLK("25.0"), .PERF_MD("ECONOMY"), .LOW_JITTER(1), .CI_FILTER_CONST(2), .CP_FILTER_CONST(4), .LOCK_REQ(0))
    pll_c (.CLK_REF(1'b0), .USR_CLK_REF(gc), .CLK_FEEDBACK(1'b0), .USR_LOCKED_STDY_RST(1'b0), .CLK0(oc));
  reg [3:0] a=0,b=0,c=0;
  always @(posedge oa) a<=a+1; always @(posedge ob) b<=b+1; always @(posedge oc) c<=c+1;
  assign led4=a[3]; assign led5=b[3]; assign led6=c[3]; assign led7=lvl;
endmodule
