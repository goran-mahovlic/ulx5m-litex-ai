// TASK-4999: fabric upset detector, PLL domain vs raw clk25 domain in ONE design.
// Pairs of identical 32-bit counters; mismatch -> error counter (Ep in PLL 50 MHz domain, Er in raw clk25).
// If Er >> 0 and Ep == 0: clk25 input edges are corrupt (PLL filters them). If both > 0: core/supply.
// UART 115200 (clocked by the PLL): "L=l Ep=eeee Er=eeee C=cccccccc\r\n" ~3x/s. PHY held in reset.
module top(input clk25, output uart_a, output uart_b, output rst_n);
  assign rst_n = 1'b0;
  wire clkp, lk;
  CC_PLL #(.REF_CLK("25.0"), .OUT_CLK("50.0"), .PERF_MD("ECONOMY"), .LOW_JITTER(1), .CI_FILTER_CONST(2),
           .CP_FILTER_CONST(4), .LOCK_REQ(0), .CLK180_DOUB(0), .CLK270_DOUB(0))
    pll(.CLK_REF(clk25), .CLK_FEEDBACK(1'b0), .USR_CLK_REF(1'b0), .USR_LOCKED_STDY_RST(1'b0),
        .CLK0(clkp), .CLK90(), .CLK180(), .CLK270(), .CLK_REF_OUT(), .USR_PLL_LOCKED(lk), .USR_PLL_LOCKED_STDY());
  // raw clk25 pair
  (* keep *) reg [31:0] ra = 0; (* keep *) reg [31:0] rb = 0; reg [15:0] er = 0;
  always @(posedge clk25) begin ra <= ra + 1; if (rb != ra) begin er <= er + 1; rb <= ra + 1; end else rb <= rb + 1; end
  wire [15:0] erg = er ^ (er >> 1);
  // PLL pair
  (* keep *) reg [31:0] pa = 0; (* keep *) reg [31:0] pb = 0; reg [15:0] ep = 0;
  always @(posedge clkp) begin pa <= pa + 1; if (pb != pa) begin ep <= ep + 1; pb <= pa + 1; end else pb <= pb + 1; end
  reg [15:0] g1 = 0, g2 = 0; always @(posedge clkp) begin g1 <= erg; g2 <= g1; end
  function [15:0] g2b(input [15:0] g); integer i; begin g2b[15] = g[15]; for (i = 14; i >= 0; i = i - 1) g2b[i] = g2b[i+1] ^ g[i]; end endfunction
  reg l1 = 0, l2 = 0; always @(posedge clkp) begin l1 <= lk; l2 <= l1; end
  // UART on clkp (50 MHz): divider 434
  reg [8:0] baud = 0; wire tick = (baud == 433);
  always @(posedge clkp) baud <= tick ? 0 : baud + 1;
  reg [23:0] pre = 0; reg go = 0;
  function [7:0] hx(input [3:0] n); hx = n < 10 ? 8'h30 + n : 8'h37 + n; endfunction
  reg [5:0] idx = 0; reg [1:0] state = 0; reg [9:0] sh = 10'h3FF; reg [3:0] bits = 0;
  reg [31:0] sc = 0; reg [15:0] sp = 0, sr = 0; reg sl = 0;
  always @(posedge clkp) begin pre <= pre + 1; if (pre == 0) go <= 1; else if (state != 0) go <= 0; end
  reg [7:0] ch;
  always @* case (idx)
    0: ch = "L"; 1: ch = "="; 2: ch = sl ? "1" : "0"; 3: ch = " ";
    4: ch = "E"; 5: ch = "p"; 6: ch = "="; 7: ch = hx(sp[15:12]); 8: ch = hx(sp[11:8]); 9: ch = hx(sp[7:4]); 10: ch = hx(sp[3:0]); 11: ch = " ";
    12: ch = "E"; 13: ch = "r"; 14: ch = "="; 15: ch = hx(sr[15:12]); 16: ch = hx(sr[11:8]); 17: ch = hx(sr[7:4]); 18: ch = hx(sr[3:0]); 19: ch = " ";
    20: ch = "C"; 21: ch = "="; 22: ch = hx(sc[31:28]); 23: ch = hx(sc[27:24]); 24: ch = hx(sc[23:20]); 25: ch = hx(sc[19:16]);
    26: ch = hx(sc[15:12]); 27: ch = hx(sc[11:8]); 28: ch = hx(sc[7:4]); 29: ch = hx(sc[3:0]);
    30: ch = 8'h0D; default: ch = 8'h0A; endcase
  always @(posedge clkp) if (tick) case (state)
    0: if (go) begin sc <= pa; sp <= ep; sr <= g2b(g2); sl <= l2; idx <= 0; state <= 1; end
    1: begin sh <= {1'b1, ch, 1'b0}; bits <= 0; state <= 2; end
    2: begin sh <= {1'b1, sh[9:1]}; bits <= bits + 1;
         if (bits == 9) begin if (idx == 31) state <= 0; else begin idx <= idx + 1; state <= 1; end end end
    default: state <= 0;
  endcase
  assign uart_a = sh[0]; assign uart_b = sh[0];
endmodule
