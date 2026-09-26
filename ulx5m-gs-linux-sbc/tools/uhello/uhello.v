// TASK-4999: minimal UART "hello" on the raw 25 MHz oscillator (no PLL, no LiteX).
// Sends "HELLO xxxxxxxx\r\n" (32-bit seconds-ish counter, hex) at 115200 8N1 on both
// DirtyJTAG UART pins, 4x per second. Proves clk25 + the UART path independently of any design.
module top(input clk25, output uart_a, output uart_b);
  reg [7:0] rst_cnt = 0; wire rst = ~rst_cnt[7];
  always @(posedge clk25) if (rst) rst_cnt <= rst_cnt + 1;
  reg [7:0] baud = 0; wire tick = (baud == 216);
  always @(posedge clk25) baud <= tick ? 0 : baud + 1;
  reg [31:0] cnt = 0; reg [22:0] pre = 0;
  reg go = 0;
  always @(posedge clk25) begin pre <= pre + 1; if (pre == 0) begin cnt <= cnt + 1; go <= 1; end else if (state != 0) go <= 0; end
  function [7:0] hx(input [3:0] n); hx = n < 10 ? 8'h30 + n : 8'h37 + n; endfunction
  reg [4:0] idx = 0; reg [3:0] state = 0; reg [9:0] sh = 10'h3FF; reg [3:0] bits = 0;
  reg [31:0] snap = 0;
  reg [7:0] ch;
  always @* case (idx)
    0: ch = "H"; 1: ch = "E"; 2: ch = "L"; 3: ch = "L"; 4: ch = "O"; 5: ch = " ";
    6: ch = hx(snap[31:28]); 7: ch = hx(snap[27:24]); 8: ch = hx(snap[23:20]); 9: ch = hx(snap[19:16]);
    10: ch = hx(snap[15:12]); 11: ch = hx(snap[11:8]); 12: ch = hx(snap[7:4]); 13: ch = hx(snap[3:0]);
    14: ch = 8'h0D; default: ch = 8'h0A; endcase
  always @(posedge clk25) if (rst) begin state <= 0; sh <= 10'h3FF; end
  else if (tick) case (state)
    0: if (go) begin snap <= cnt; idx <= 0; state <= 1; end
    1: begin sh <= {1'b1, ch, 1'b0}; bits <= 0; state <= 2; end
    2: begin sh <= {1'b1, sh[9:1]}; bits <= bits + 1;
         if (bits == 9) begin if (idx == 15) state <= 0; else begin idx <= idx + 1; state <= 1; end end end
  endcase
  assign uart_a = sh[0]; assign uart_b = sh[0];
endmodule
