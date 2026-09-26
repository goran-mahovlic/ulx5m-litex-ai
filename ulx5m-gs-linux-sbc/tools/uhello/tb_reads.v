`timescale 1ns/1ps
// MDIO slave model: PHYAD 3; reg2=0022 reg3=1622 reg1=796D others=reg*0x111. Drives after MDC rising (+10 ns).
module tb;
  reg clk = 0; always #20 clk = ~clk;
  wire ua, ub, mdc, rst_n; wire mdio; pullup(mdio);
  reg drv = 0, dval = 1; assign mdio = drv ? dval : 1'bz;
  top #(.WRITE_AFTER(8'd200)) dut(.clk25(clk), .uart_a(ua), .uart_b(ub), .mdc(mdc), .mdio(mdio), .rst_n(rst_n), .rxc(clk), .rx_ctl(1'b0));
  integer ones = 0, st = -1; reg [13:0] hdr; reg [15:0] data; reg [4:0] a, r;
  always @(posedge mdc) begin
    if (st < 0) begin
      if (mdio === 1'b1) ones = ones + 1; else begin if (ones >= 32) begin st = 1; hdr = 14'b0; end ones = 0; end
    end else if (st < 14) begin hdr = {hdr[12:0], mdio}; st = st + 1;
      if (st == 14) begin
        a = hdr[9:5]; r = hdr[4:0];
        if (hdr[12] && hdr[11:10] == 2'b10 && a == 3) begin   // ST1=1, OP=10 (read), our PHYAD
          data = (r == 2) ? 16'h0022 : (r == 3) ? 16'h1622 : (r == 1) ? 16'h796D : r * 16'h0111;
          st = 100;             // drive phase starts after this edge (bit 45 = last REG bit)
        end else if (hdr[12:11] == 2'b10) st = -1; else st = -1;
      end
    end else if (st >= 100) begin
      // edge of bit 46 (TA1): drive TA0 (=0) for bit 47; then data bits 15..0; after bit 63 release
      #10;
      if (st == 100) begin drv = 1; dval = 0; end
      else if (st <= 116) begin dval = data[116 - st]; end
      else begin drv = 0; st = -2; end
      if (st >= 0) st = st + 1;
      if (st == -2) st = -1;
    end
  end
  initial begin #(40*9000000);
    $display("idm=%b addr=%0d r1=%h (exp 796d) r4=%h (exp 0444) r5=%h (exp 0555) rf=%h (exp 2121)", dut.idm, dut.addr, dut.r1, dut.r4, dut.r5, dut.rf);
    $finish; end
endmodule
