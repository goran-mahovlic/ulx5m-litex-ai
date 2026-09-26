// TASK-4999 fab7: absolute clk25 frequency + carry-chain health, timed by the Pi clock over JTAG.
//  flag A (PLL a): q[24] of a RIPPLE counter (T flip-flops, no carry chain) -> level = 2^24 / f_clk25
//  flag B (PLL b): c[24] of a normal (CC_ADDF carry-chain) counter          -> same period if healthy
module top(input clk25_pin, output led4, output led5, output led6, output led7);
  wire clk25; CC_BUFG bgc (.I(clk25_pin), .O(clk25));
  (* clkbuf_inhibit *) wire [24:0] q;
  (* clkbuf_inhibit *) reg [24:0] qr = 0;
  assign q = qr;
  always @(posedge clk25) qr[0] <= ~qr[0];
  genvar i;
  generate for (i = 1; i < 25; i = i + 1) begin : rip
    always @(negedge q[i-1]) qr[i] <= ~qr[i];
  end endgenerate
  reg [24:0] c = 0; always @(posedge clk25) c <= c + 1;
  reg fa = 0, fb = 0;
  always @(posedge clk25) begin fa <= qr[24]; fb <= c[24]; end
  reg [2:0] da=0, db=0; reg ga=0, gb=0;
  always @(posedge clk25) begin
    da <= (da >= (fa ? 3'd1 : 3'd7)) ? 3'd0 : da + 1; ga <= fa ? (da < 3'd1) : (da < 3'd4);
    db <= (db >= (fb ? 3'd1 : 3'd7)) ? 3'd0 : db + 1; gb <= fb ? (db < 3'd1) : (db < 3'd4);
  end
  (* clkbuf_inhibit *) wire oa; (* clkbuf_inhibit *) wire ob;
  CC_PLL #(.REF_CLK("12.5"), .OUT_CLK("25.0"), .PERF_MD("ECONOMY"), .LOW_JITTER(1), .CI_FILTER_CONST(2), .CP_FILTER_CONST(4), .LOCK_REQ(0))
    pll_a (.CLK_REF(1'b0), .USR_CLK_REF(ga), .CLK_FEEDBACK(1'b0), .USR_LOCKED_STDY_RST(1'b0), .CLK0(oa));
  CC_PLL #(.REF_CLK("12.5"), .OUT_CLK("25.0"), .PERF_MD("ECONOMY"), .LOW_JITTER(1), .CI_FILTER_CONST(2), .CP_FILTER_CONST(4), .LOCK_REQ(0))
    pll_b (.CLK_REF(1'b0), .USR_CLK_REF(gb), .CLK_FEEDBACK(1'b0), .USR_LOCKED_STDY_RST(1'b0), .CLK0(ob));
  reg [3:0] a=0,b=0; always @(posedge oa) a<=a+1; always @(posedge ob) b<=b+1;
  assign led4=a[3]; assign led5=b[3]; assign led6=qr[24]; assign led7=c[24];
endmodule
