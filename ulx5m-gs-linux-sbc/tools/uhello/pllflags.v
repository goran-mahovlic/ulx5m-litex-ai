// TASK-4999: static 1-bit flags readable over JTAG STATUS_PLLx (standalone, no LiteX).
// One ECONOMY CC_PLL per flag. Reference (USR_CLK_REF) = clk25/2 (12.5 MHz, = REF_CLK) for 1, clk25/32
// (0.78 MHz, far below the PFD range -> cannot lock) for 0. A stopped reference is NOT used for 0: it
// freezes the PLL state (measured 24.9.). Each PLL clocks a toggle routed to a pin (an unloaded PLL
// output does not track). Decode: LOCKED (status bits 13:12 == 2) = 1.
module pllflags #(parameter N = 3) (input clk25, input [N-1:0] flags, output [N-1:0] loads);
  genvar i;
  generate for (i = 0; i < N; i = i + 1) begin : g
    reg fr = 0; reg [4:0] d = 0; reg refc = 0;
    wire [4:0] per = fr ? 5'd1 : 5'd31;              // count 0..per -> period per+1 (2 or 32)
    always @(posedge clk25) begin
      fr <= flags[i];
      d <= (d >= per) ? 5'd0 : d + 5'd1;
      refc <= (d < ((per + 5'd1) >> 1));
    end
    (* clkbuf_inhibit *) wire out;   // no global buffer: 4 PLLs + clk25 exceed the BUFGs
    (* keep *) CC_PLL #(.REF_CLK("12.5"), .OUT_CLK("100.0"), .PERF_MD("ECONOMY"), .LOW_JITTER(1),
                        .CI_FILTER_CONST(2), .CP_FILTER_CONST(4), .LOCK_REQ(0), .CLK180_DOUB(0), .CLK270_DOUB(0))
      pll(.CLK_REF(1'b0), .USR_CLK_REF(refc), .CLK_FEEDBACK(1'b0), .USR_LOCKED_STDY_RST(1'b0),
          .CLK0(out), .CLK90(), .CLK180(), .CLK270(), .CLK_REF_OUT(), .USR_PLL_LOCKED(), .USR_PLL_LOCKED_STDY());
    reg t = 0; always @(posedge out) t <= ~t;
    assign loads[i] = t;
  end endgenerate
endmodule
