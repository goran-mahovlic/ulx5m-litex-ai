// TASK-4999 fab5: logic-integrity monitor (power / timing), readable over JTAG.
//  flag0 (PLL a): sticky ERROR = two identical 32-bit counters ever disagreed (or LFSR pair)
//  flag1 (PLL b): ALIVE = counter bit 24 (toggles every 0.67 s)
//  stress: NSTRESS flops toggling every cycle (switching current on VDD_CORE)
module top(input clk25_pin, output led4, output led5, output led6, output led7);
  parameter NSTRESS = 8;
  wire clk25; CC_BUFG bgc (.I(clk25_pin), .O(clk25));
  wire rstn; CC_USR_RSTN ur (.USR_RSTN(rstn));
  reg [3:0] rs = 0; wire rst = ~rs[3]; always @(posedge clk25 or negedge rstn) if (!rstn) rs <= 0; else if (!rs[3]) rs <= rs + 1;
  (* keep *) reg [31:0] c1 = 0; (* keep *) reg [31:0] c2 = 0;
  (* keep *) reg [31:0] l1 = 32'h1; (* keep *) reg [31:0] l2 = 32'h1;
  reg err = 0;
  always @(posedge clk25) begin
    if (rst) begin c1 <= 0; c2 <= 0; l1 <= 32'h1; l2 <= 32'h1; err <= 0; end
    else begin
      c1 <= c1 + 1; c2 <= c2 + 1;
      l1 <= {l1[30:0], l1[31] ^ l1[21] ^ l1[1] ^ l1[0]};
      l2 <= {l2[30:0], l2[31] ^ l2[21] ^ l2[1] ^ l2[0]};
      if ((c1 != c2) || (l1 != l2)) err <= 1;
    end
  end
  (* keep *) reg [NSTRESS-1:0] st = 0;
  always @(posedge clk25) st <= ~st;
  wire stx = ^st;
  // flag -> reference /2 (1) or /8 (0)
  reg [2:0] da=0, db=0; reg ga=0, gb=0; reg fa=0, fb=0;
  always @(posedge clk25) begin
    fa <= err; fb <= c1[24];
    da <= (da >= (fa ? 3'd1 : 3'd7)) ? 3'd0 : da + 1; ga <= fa ? (da < 3'd1) : (da < 3'd4);
    db <= (db >= (fb ? 3'd1 : 3'd7)) ? 3'd0 : db + 1; gb <= fb ? (db < 3'd1) : (db < 3'd4);
  end
  (* clkbuf_inhibit *) wire oa; (* clkbuf_inhibit *) wire ob;
  CC_PLL #(.REF_CLK("12.5"), .OUT_CLK("25.0"), .PERF_MD("ECONOMY"), .LOW_JITTER(1), .CI_FILTER_CONST(2), .CP_FILTER_CONST(4), .LOCK_REQ(0))
    pll_a (.CLK_REF(1'b0), .USR_CLK_REF(ga), .CLK_FEEDBACK(1'b0), .USR_LOCKED_STDY_RST(1'b0), .CLK0(oa));
  CC_PLL #(.REF_CLK("12.5"), .OUT_CLK("25.0"), .PERF_MD("ECONOMY"), .LOW_JITTER(1), .CI_FILTER_CONST(2), .CP_FILTER_CONST(4), .LOCK_REQ(0))
    pll_b (.CLK_REF(1'b0), .USR_CLK_REF(gb), .CLK_FEEDBACK(1'b0), .USR_LOCKED_STDY_RST(1'b0), .CLK0(ob));
  reg [3:0] a=0,b=0; always @(posedge oa) a<=a+1; always @(posedge ob) b<=b+1;
  assign led4=a[3]; assign led5=b[3]; assign led6=stx; assign led7=err;
endmodule
