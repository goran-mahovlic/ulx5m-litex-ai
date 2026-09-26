// TASK-4999: timing-margin probe on raw clk25 (no PLL). Four pairs of identical 32-bit counters that
// advance every 1, 2, 4, 8 clk25 cycles (the adders get 1x/2x/4x/8x 40 ns to settle). Mismatch -> Ek++.
// E1 >> E2 >> E4 ~ 0: silicon slower than the timing model (VDD_CORE low / wrong PERF mode).
// E1 ~ E2 ~ E4 ~ E8: clock glitches or supply noise. hex via LUT (case), no adder. PHY held in reset.
// UART 115200: "E1=xxxx E2=xxxx E4=xxxx E8=xxxx\r\n" ~3x/s.
module top(input clk25, output uart_a, output uart_b, output rst_n);
  assign rst_n = 1'b0;
  reg [2:0] dv = 0; always @(posedge clk25) dv <= dv + 1;
  wire [3:0] en = {dv == 3'd7, dv[1:0] == 2'd3, dv[0], 1'b1};
  reg [15:0] e [0:3];
  genvar k;
  generate for (k = 0; k < 4; k = k + 1) begin : P
    (* keep *) reg [31:0] a = 0; (* keep *) reg [31:0] b = 0; reg [15:0] er = 0;
    always @(posedge clk25) if (en[k]) begin a <= a + 1; if (b != a) begin er <= er + 1; b <= a + 1; end else b <= b + 1; end
  end endgenerate
  reg [7:0] baud = 0; wire tick = (baud == 216);
  always @(posedge clk25) baud <= tick ? 0 : baud + 1;
  reg [22:0] pre = 0; reg go = 0;
  function [7:0] hx(input [3:0] n);
    case (n) 0: hx="0"; 1: hx="1"; 2: hx="2"; 3: hx="3"; 4: hx="4"; 5: hx="5"; 6: hx="6"; 7: hx="7";
             8: hx="8"; 9: hx="9"; 10: hx="A"; 11: hx="B"; 12: hx="C"; 13: hx="D"; 14: hx="E"; default: hx="F"; endcase
  endfunction
  reg [5:0] idx = 0; reg [1:0] state = 0; reg [9:0] sh = 10'h3FF; reg [3:0] bits = 0;
  reg [63:0] s = 0;
  always @(posedge clk25) begin pre <= pre + 1; if (pre == 0) go <= 1; else if (state != 0) go <= 0; end
  reg [7:0] ch; wire [3:0] q = idx[2:0] < 3 ? 0 : 0;
  always @* case (idx)
    0: ch="E"; 1: ch="1"; 2: ch="="; 3: ch=hx(s[63:60]); 4: ch=hx(s[59:56]); 5: ch=hx(s[55:52]); 6: ch=hx(s[51:48]); 7: ch=" ";
    8: ch="E"; 9: ch="2"; 10: ch="="; 11: ch=hx(s[47:44]); 12: ch=hx(s[43:40]); 13: ch=hx(s[39:36]); 14: ch=hx(s[35:32]); 15: ch=" ";
    16: ch="E"; 17: ch="4"; 18: ch="="; 19: ch=hx(s[31:28]); 20: ch=hx(s[27:24]); 21: ch=hx(s[23:20]); 22: ch=hx(s[19:16]); 23: ch=" ";
    24: ch="E"; 25: ch="8"; 26: ch="="; 27: ch=hx(s[15:12]); 28: ch=hx(s[11:8]); 29: ch=hx(s[7:4]); 30: ch=hx(s[3:0]);
    31: ch=8'h0D; default: ch=8'h0A; endcase
  always @(posedge clk25) if (tick) case (state)
    0: if (go) begin s <= {P[0].er, P[1].er, P[2].er, P[3].er}; idx <= 0; state <= 1; end
    1: begin sh <= {1'b1, ch, 1'b0}; bits <= 0; state <= 2; end
    2: begin sh <= {1'b1, sh[9:1]}; bits <= bits + 1;
         if (bits == 9) begin if (idx == 32) state <= 0; else begin idx <= idx + 1; state <= 1; end end end
    default: state <= 0;
  endcase
  assign uart_a = sh[0]; assign uart_b = sh[0];
endmodule
