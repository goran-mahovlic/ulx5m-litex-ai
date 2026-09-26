// TASK-4999: fabric upset detector vs PHY reset state. Raw clk25 only (no PLL).
// RSTN=0: PHY held in reset for ever; RSTN=1: PHY released after 21 ms (link comes up by itself).
// Two identical 32-bit counters A/B: any mismatch = fabric upset -> E increments, B resyncs to A.
// UART 115200 on both bridge pins: "R=r C=cccccccc E=eeee\r\n" ~3x/s.
module top(input clk25, output uart_a, output uart_b, output rst_n);
  parameter RSTN = 1;
  reg [21:0] up = 0; always @(posedge clk25) if (!up[21]) up <= up + 1;
  assign rst_n = RSTN ? (up[19] | up[20] | up[21]) : 1'b0;
  (* keep *) reg [31:0] ca = 0; (* keep *) reg [31:0] cb = 0; reg [15:0] err = 0;
  always @(posedge clk25) begin
    ca <= ca + 1;
    if (cb != ca) begin err <= err + 1; cb <= ca + 1; end else cb <= cb + 1;
  end
  reg [7:0] baud = 0; wire tick = (baud == 216);
  always @(posedge clk25) baud <= tick ? 0 : baud + 1;
  reg [22:0] pre = 0; reg go = 0;
  function [7:0] hx(input [3:0] n); hx = n < 10 ? 8'h30 + n : 8'h37 + n; endfunction
  reg [4:0] idx = 0; reg [1:0] state = 0; reg [9:0] sh = 10'h3FF; reg [3:0] bits = 0;
  reg [31:0] sc = 0; reg [15:0] se = 0;
  always @(posedge clk25) begin pre <= pre + 1; if (pre == 0) go <= 1; else if (state != 0) go <= 0; end
  reg [7:0] ch;
  always @* case (idx)
    0: ch = "R"; 1: ch = "="; 2: ch = RSTN ? "1" : "0"; 3: ch = " "; 4: ch = "C"; 5: ch = "=";
    6: ch = hx(sc[31:28]); 7: ch = hx(sc[27:24]); 8: ch = hx(sc[23:20]); 9: ch = hx(sc[19:16]);
    10: ch = hx(sc[15:12]); 11: ch = hx(sc[11:8]); 12: ch = hx(sc[7:4]); 13: ch = hx(sc[3:0]);
    14: ch = " "; 15: ch = "E"; 16: ch = "="; 17: ch = hx(se[15:12]); 18: ch = hx(se[11:8]); 19: ch = hx(se[7:4]); 20: ch = hx(se[3:0]);
    21: ch = 8'h0D; default: ch = 8'h0A; endcase
  always @(posedge clk25) if (tick) case (state)
    0: if (go) begin sc <= ca; se <= err; idx <= 0; state <= 1; end
    1: begin sh <= {1'b1, ch, 1'b0}; bits <= 0; state <= 2; end
    2: begin sh <= {1'b1, sh[9:1]}; bits <= bits + 1;
         if (bits == 9) begin if (idx == 22) state <= 0; else begin idx <= idx + 1; state <= 1; end end end
    default: state <= 0;
  endcase
  assign uart_a = sh[0]; assign uart_b = sh[0];
endmodule
