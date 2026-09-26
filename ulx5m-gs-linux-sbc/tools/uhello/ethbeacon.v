// TASK-4999: standalone KSZ9031 bring-up + raw 100M RGMII beacon (no LiteX, no PLL-lock reset).
// mdio_core (raw clk25): PHY reset, MDIO reads, one 100BASE-TX-FD-only AN write burst, UART line.
// TX: one ECONOMY CC_PLL 25->25: CLK0 launches TXD/TX_CTL, CLK90 is TXC (data stable around both
// TXC edges). ~3 frames/s: broadcast, src 02:00:00:00:49:99, ethertype 0x88B5, payload:
//   "T499", seq, idm, {wrote,addr}, passes, R0,R1,R4,R5,R9,RA,RF (16b BE), RXC freq (24b), frames (16b).
module top(input clk25, output uart_a, output uart_b,
           output mdc, inout mdio, output rst_n, input rxc, input rx_ctl,
           output txc, output tx_ctl, output [3:0] txd, output [2:0] flag_load);
  wire [255:0] bus;
  parameter [15:0] REG0 = 16'h1200;
  mdio_core #(.REG0(REG0)) core(.clk25(clk25), .uart_a(uart_a), .uart_b(uart_b), .mdc(mdc), .mdio(mdio), .rst_n(rst_n),
                 .rxc(rxc), .rx_ctl(rx_ctl), .snap_bus(bus));
  wire clk0, clk90, lk;
`ifdef SIM
  assign clk0 = clk25; reg c90 = 0; always @(clk25) c90 <= #10 clk25; assign clk90 = c90; assign lk = 1;
`else
  CC_PLL #(.REF_CLK("25.0"), .OUT_CLK("25.0"), .PERF_MD("ECONOMY"), .LOW_JITTER(1), .CI_FILTER_CONST(2),
           .CP_FILTER_CONST(4), .LOCK_REQ(1), .CLK180_DOUB(0), .CLK270_DOUB(0))
    pll(.CLK_REF(clk25), .CLK_FEEDBACK(1'b0), .USR_CLK_REF(1'b0), .USR_LOCKED_STDY_RST(1'b0),
        .CLK0(clk0), .CLK90(clk90), .CLK180(), .CLK270(), .CLK_REF_OUT(), .USR_PLL_LOCKED(lk), .USR_PLL_LOCKED_STDY());
`endif
  assign txc = clk90;
  // ---- snapshot of the diag bus (2-FF, taken at frame start; values change only ~5x/s) ----
  // no load-enable snapshot: a 256-wide EN net does not route on GateMate
  reg [255:0] b1 = 0, b2 = 0; wire [255:0] snap = b2;
  always @(posedge clk0) begin b1 <= bus; b2 <= b1; end
  // ---- frame generator ----
  reg [22:0] tmr = 0; reg [7:0] seq = 0;
  reg active = 0; reg [6:0] pos = 0; reg nib = 0; reg [31:0] crc = 32'hFFFFFFFF;
  function [31:0] crc_byte(input [31:0] c, input [7:0] d); integer i; reg [31:0] x;
    begin x = c; for (i = 0; i < 8; i = i + 1) x = (x[0] ^ d[i]) ? ((x >> 1) ^ 32'hEDB88320) : (x >> 1); crc_byte = x; end
  endfunction
  function [7:0] sb(input integer k); sb = snap[255 - 8*k -: 8]; endfunction   // snap byte k (MSB first)
  reg [7:0] fb;   // frame byte at f = pos - 8
  wire [6:0] f = pos - 7'd8;
  always @* begin
    case (f)
      0,1,2,3,4,5: fb = 8'hFF;
      6: fb = 8'h02; 7,8,9: fb = 8'h00; 10: fb = 8'h49; 11: fb = 8'h99;
      12: fb = 8'h88; 13: fb = 8'hB5;
      14: fb = "T"; 15: fb = "4"; 16: fb = "9"; 17: fb = "9"; 18: fb = seq;
      19: fb = sb(1); 20: fb = sb(2); 21: fb = sb(0);                                  // idm, {w,a}, passes
      22: fb = sb(3);  23: fb = sb(4);  24: fb = sb(5);  25: fb = sb(6);                 // R0 R1
      26: fb = sb(7);  27: fb = sb(8);  28: fb = sb(9);  29: fb = sb(10);                // R4 R5
      30: fb = sb(11); 31: fb = sb(12); 32: fb = sb(13); 33: fb = sb(14);                // R9 RA
      34: fb = sb(15); 35: fb = sb(16);                                                  // RF
      36: fb = sb(17); 37: fb = sb(18); 38: fb = sb(19);                                 // RXC freq
      39: fb = sb(20); 40: fb = sb(21);                                                  // frames
      default: fb = 8'h00;
    endcase
  end
  reg [7:0] cur;
  always @* begin
    if (pos < 7) cur = 8'h55;
    else if (pos == 7) cur = 8'hD5;
    else if (pos < 68) cur = fb;
    else case (pos) 68: cur = ~crc[7:0]; 69: cur = ~crc[15:8]; 70: cur = ~crc[23:16]; default: cur = ~crc[31:24]; endcase
  end
  reg [3:0] txd_r = 0; reg ctl_r = 0;
  always @(posedge clk0) begin
    tmr <= tmr + 1;
    if (!active) begin
      ctl_r <= 0; txd_r <= 0;
      if (tmr == 0) begin active <= 1; pos <= 0; nib <= 0; crc <= 32'hFFFFFFFF; end
    end else begin
      ctl_r <= 1; txd_r <= nib ? cur[7:4] : cur[3:0];
      nib <= ~nib;
      if (nib) begin
        if (pos >= 8 && pos < 68) crc <= crc_byte(crc, cur);
        if (pos == 71) begin active <= 0; seq <= seq + 1; end
        pos <= pos + 1;
      end
    end
  end
  assign tx_ctl = ctl_r; assign txd = txd_r;
`ifdef PLLFLAGS
  // JTAG-readable flags (TASK-4999): RXC frequency from the diag bus, counts per 2^20 clk25 cycles:
  // 25 MHz = 0x100000, 125 MHz = 0x500000, 2.5 MHz = 0x19999.
  wire [23:0] rf = bus[255-8*17 -: 24];
  pllflags #(.N(3)) pf(.clk25(clk25), .flags({1'b1, rf > 24'h400000, (rf > 24'h0C0000) && (rf < 24'h140000)}), .loads(flag_load));
`else
  assign flag_load = 3'b0;
`endif
endmodule
