// TASK-4999: PHY bring-up (mdio_core, write-only MDIO) + 3 JTAG-readable PLL flags, no TX, no beacon PLL.
// SET 0: {one, rxc > 100 MHz (1G), rxc 18.75..31.25 MHz (100M)}
// SET 1: {one, rx frames > 0,    rxc 1.9..3.1 MHz (10M)}
// SET 2..4: RXC frequency bisection (see below)
module top(input clk25, output uart_a, output uart_b,
           output mdc, inout mdio, output rst_n, (* clkbuf_inhibit *) input rxc, input rx_ctl,
           output [2:0] flag_load);
  parameter [15:0] REG0 = 16'h1200;
  parameter SET = 0;
  wire [255:0] bus;
  mdio_core #(.REG0(REG0)) core(.clk25(clk25), .uart_a(uart_a), .uart_b(uart_b), .mdc(mdc), .mdio(mdio), .rst_n(rst_n),
                 .rxc(rxc), .rx_ctl(rx_ctl), .snap_bus(bus));
  wire [23:0] rf = bus[255-8*17 -: 24];     // RXC edges per 2^20 clk25 cycles: 25 MHz = 0x100000
  wire [15:0] fr = bus[255-8*20 -: 16];
  wire [2:0] fl = (SET == 0) ? {1'b1, rf > 24'h400000, (rf > 24'h0C0000) && (rf < 24'h140000)}
                : (SET == 1) ? {1'b1, fr != 16'h0,     (rf > 24'h013000) && (rf < 24'h020000)}
                : (SET == 2) ? {1'b1, rf > 24'h040000, rf != 24'h0}          // > 6.25 MHz, any RXC
                : (SET == 3) ? {1'b1, rf > 24'h200000, rf > 24'h0C0000}      // > 50 MHz, > 18.75 MHz
                : (SET == 4) ? {1'b1, rf > 24'h180000, rf > 24'h0E0000}      // > 37.5 MHz, > 21.9 MHz
                : (SET == 5) ? 3'b111                                          // slot calibration: all 1
                :              {3{rf == 24'hFFFFFF}};                          // slot calibration: all 0 (not a synthesis constant)
  pllflags #(.N(3)) pf(.clk25(clk25), .flags(fl), .loads(flag_load));
endmodule
