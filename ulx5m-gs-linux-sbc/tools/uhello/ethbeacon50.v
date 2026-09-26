// TASK-4999 eb50: ethbeacon with a PLACEMENT-INDEPENDENT TXC phase (Goran 24.9. 19:46, uputa #12).
// Problem found in the routed netlists: TXC = PLL CLK90 reaches the pad through general fabric routing
// (n1: 6.9 ns, CPE X46 -> X113) while TXD/TX_CTL come from IOSEL FFs on the global clock (0.3 ns), so the
// real TXC phase is 90 deg + a seed/voltage dependent route delay (n1: ~17-18 ns instead of 10 ns; the TXC
// falling edge, where the PHY samples TX_EN^TX_ER, lands ~3 ns before the next nibble).
// Fix: one 50 MHz global clock (PLL 25->50, ECONOMY), ALL six TX pins are IOSEL flip-flops (FF_OBF):
//   TXD/TX_CTL: posedge IO FF, change every 2nd clk50 cycle (40 ns nibble);
//   TXC       : IO FF on PLL CLK180 (= falling edge of clk50, own global net) fed by the phase bit -> rises
//               10 ns after the data change, falls 30 ns after, i.e. exactly 90 deg by construction.
// NOT a plain `always @(negedge)`: nextpnr 0.11.1-31-g3edea68e (and master) loses CLK_INV when it merges a
// CC_DFF into the IOSEL (FF_OBF): cleanup()/dff_to_cpe() unsets CLK_INV before pack_io_sel() reads it, so the
// IO FF silently becomes posedge (repro: tools/uhello/negff_repro/, TASK-4999 24.9.).
// The DDR select net of CC_ODDR (fabric-routed, delay not modelled by nextpnr) is not used at all.
module top(input clk25, output uart_a, output uart_b,
           output mdc, inout mdio, output rst_n, input rxc, input rx_ctl,
           output txc, output tx_ctl, output [3:0] txd, output [2:0] flag_load);
  wire [255:0] bus;
  parameter [15:0] REG0 = 16'h1200;
  mdio_core #(.REG0(REG0)) core(.clk25(clk25), .uart_a(uart_a), .uart_b(uart_b), .mdc(mdc), .mdio(mdio), .rst_n(rst_n),
                 .rxc(rxc), .rx_ctl(rx_ctl), .snap_bus(bus));
  wire clk0, clk180, lk;   // clk0 = 50 MHz, clk180 = its inverse (same PLL)
`ifdef SIM
  reg c50 = 0; always @(clk25) begin c50 <= 1; #10 c50 <= 0; end assign clk0 = c50; assign clk180 = ~c50; assign lk = 1;
`else
  CC_PLL #(.REF_CLK("25.0"), .OUT_CLK("50.0"), .PERF_MD("ECONOMY"), .LOW_JITTER(1), .CI_FILTER_CONST(2),
           .CP_FILTER_CONST(4), .LOCK_REQ(1), .CLK180_DOUB(0), .CLK270_DOUB(0))
    pll(.CLK_REF(clk25), .CLK_FEEDBACK(1'b0), .USR_CLK_REF(1'b0), .USR_LOCKED_STDY_RST(1'b0),
        .CLK0(clk0), .CLK90(), .CLK180(clk180), .CLK270(), .CLK_REF_OUT(), .USR_PLL_LOCKED(lk), .USR_PLL_LOCKED_STDY());
`endif
  // nibble phase: ce=1 on every 2nd clk50 edge -> generator runs at 25 MHz nibble rate
  reg ph = 0; always @(posedge clk0) ph <= ~ph;
  wire ce = ph;
  // ---- snapshot of the diag bus (2-FF, taken at frame start; values change only ~5x/s) ----
  // no load-enable snapshot: a 256-wide EN net does not route on GateMate
  reg [255:0] b1 = 0, b2 = 0; wire [255:0] snap = b2;
  always @(posedge clk0) begin b1 <= bus; b2 <= b1; end
  // ---- frame generator ----
  reg [22:0] tmr = 0; reg [7:0] seq = 0;
  reg active = 0; reg [10:0] pos = 0; reg nib = 0; reg [31:0] crc = 32'hFFFFFFFF;
  function [31:0] crc_byte(input [31:0] c, input [7:0] d); integer i; reg [31:0] x;
    begin x = c; for (i = 0; i < 8; i = i + 1) x = (x[0] ^ d[i]) ? ((x >> 1) ^ 32'hEDB88320) : (x >> 1); crc_byte = x; end
  endfunction
  function [7:0] sb(input integer k); sb = snap[255 - 8*k -: 8]; endfunction   // snap byte k (MSB first)
  parameter FL = 60;   // frame bytes without FCS (TASK-4999: 60 = minimum; >60 tests the long-frame TX path)
  reg [7:0] fb;   // frame byte at f = pos - 8
  wire [10:0] f = pos - 11'd8;
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
    else if (pos < 8 + FL) cur = fb;
    else if (pos == 8 + FL) cur = ~crc[7:0]; else if (pos == 9 + FL) cur = ~crc[15:8];
    else if (pos == 10 + FL) cur = ~crc[23:16]; else cur = ~crc[31:24];
  end
  reg [3:0] txd_r = 0; reg ctl_r = 0;
  always @(posedge clk0) if (ce) begin
    tmr <= tmr + 1;
    if (!active) begin
      ctl_r <= 0; txd_r <= 0;
      if (tmr == 0) begin active <= 1; pos <= 0; nib <= 0; crc <= 32'hFFFFFFFF; end
    end else begin
      ctl_r <= 1; txd_r <= nib ? cur[7:4] : cur[3:0];
      nib <= ~nib;
      if (nib) begin
        if (pos >= 8 && pos < 8 + FL) crc <= crc_byte(crc, cur);
        if (pos == 11 + FL) begin active <= 0; seq <= seq + 1; end
        pos <= pos + 1;
      end
    end
  end
  // pad registers -- all packed into IOSEL (FF_OBF=true in the .ccf); single user each, no enable
  (* keep *) reg [3:0] txd_io = 0; (* keep *) reg ctl_io = 0; (* keep *) reg txc_io = 0;
  always @(posedge clk0) begin txd_io <= txd_r; ctl_io <= ctl_r; end
  always @(posedge clk180) txc_io <= ph;
  assign tx_ctl = ctl_io; assign txd = txd_io; assign txc = txc_io;
`ifdef PLLFLAGS
  // JTAG-readable flags (TASK-4999): RXC frequency from the diag bus, counts per 2^20 clk25 cycles:
  // 25 MHz = 0x100000, 125 MHz = 0x500000, 2.5 MHz = 0x19999.
  wire [23:0] rf = bus[255-8*17 -: 24];
  pllflags #(.N(3)) pf(.clk25(clk25), .flags({1'b1, rf > 24'h400000, (rf > 24'h0C0000) && (rf < 24'h140000)}), .loads(flag_load));
`else
  assign flag_load = 3'b0;
`endif
endmodule
