// TASK-4999 (new board, X1 on XI): standalone KSZ9031 MDIO probe, raw 25 MHz only (no PLL, no LiteX).
// - RESET_N (IO_EB_B3) low for 2^19 cycles (21 ms), then high; MDIO starts at 2^21 cycles (84 ms).
// - Every pass: read reg2 at PHYAD 0..7 (-> ID mask), then regs 0,1,4,5,9,A,1F at the first PHYAD that
//   answered (TA = 0). For the first WRITE_AFTER passes nothing is written (power-on defaults);
//   then ONE write burst reg9=0000, reg4=0101, reg0=1200 (AN, 100BASE-TX FD only) to that PHYAD.
// - RXC (IO_EB_A7) frequency: RXC edges per 2^20 clk25 cycles (25 MHz -> 0x100000, 125 MHz -> 0x500000).
// - RX_CTL rising edges seen by RXC (~frames), 16 bitn.
// One line per pass on the DirtyJTAG UART (115200 8N1):
//   "P=pp W=w M=mm A=a R0=xxxx R1=xxxx R4=xxxx R5=xxxx R9=xxxx RA=xxxx RF=xxxx C=xxxxxx F=xxxx D=<16 hex>\r\n"
module mdio_core(input clk25, output uart_a, output uart_b,
           output mdc, inout mdio, output rst_n, (* clkbuf_inhibit *) input rxc, input rx_ctl,
           output [255:0] snap_bus, input [63:0] dbg);   // dbg: printed as D=<16 hex> (TASK-5032)
  parameter WRITE_AFTER = 8'd6;
  parameter [15:0] REG0 = 16'h1200;   // 0x1200 = AN 100FD only (with reg4/reg9); 0x2100 = forced 100FD, AN off
  parameter [15:0] REG9 = 16'h0000;   // 1000BASE-T control: 0x0000 = no gigabit; 0x0200 = 1000FD (TASK-5032)
  parameter [15:0] REG4 = 16'h0101;   // AN advertisement: 0x0101 = 100FD; 0x0001 = no 10/100 (TASK-5032)
  parameter [7:0]  BAUD = 8'd216;     // clk / 115200 - 1 (216 @ 25 MHz, 173 @ 20 MHz)
  // ---------------- reset / timing ----------------
  reg [21:0] up = 0; always @(posedge clk25) if (!up[21]) up <= up + 1;
  assign rst_n = up[19] | up[20] | up[21];
  wire mdio_en = up[21];
  // ---------------- MDIO bitn engine (MDC = clk25/32) ----------------
  reg [4:0] ph = 0; always @(posedge clk25) ph <= ph + 1;
  reg mdc_r = 0; assign mdc = mdc_r;
  reg mdo = 1, moe = 0;
`ifdef MDIO_WO
  // Write-only MDIO: plain push-pull output, no tristate (GateMate IOBUF/T packing is placement
  // sensitive, memory gatemate-iobuf-workaround). The PHY never drives MDIO during a write frame,
  // so there is no contention; reads are impossible in this mode.
  assign mdio = moe ? mdo : 1'b1;
  reg mi1 = 1, mi2 = 1;
`else
  assign mdio = moe ? mdo : 1'bz;
  reg mi1 = 1, mi2 = 1; always @(posedge clk25) begin mi1 <= mdio; mi2 <= mi1; end
`endif
  reg [63:0] fr = 0; reg [6:0] bitn = 0; reg busy = 0, rd = 0; reg [16:0] rx = 0;
  reg start = 0; reg [63:0] fr_in = 0; reg rd_in = 0;
  always @(posedge clk25) begin
    if (ph == 5'd0) mdc_r <= 0;
    if (ph == 5'd16) mdc_r <= busy;
    if (start && !busy && ph == 5'd0) begin fr <= fr_in; rd <= rd_in; bitn <= 0; busy <= 1; rx <= 0; end
    else if (busy && ph == 5'd1) begin               // drive after MDC falls
      if (rd && bitn >= 46) moe <= 0;
      else begin moe <= 1; mdo <= fr[63]; end
      fr <= {fr[62:0], 1'b1};
    end else if (busy && ph == 5'd15) begin          // sample before MDC rises
      // MDC rises at ph 16 of every bit 0..63 -> 64 edges; the frame ends one bit later, so the
      // 64th edge (last data bit) is really clocked (fix: was 63 edges -> PHY dropped every write).
      if (rd && bitn >= 47 && bitn <= 63) rx <= {rx[15:0], mi2};
      if (bitn == 64) begin busy <= 0; moe <= 0; end
      bitn <= bitn + 1;
    end
  end
`ifdef MDIO_WO
  // write-only: reads go to PHYAD 31, which no KSZ9031 answers (PHYAD[4:3] = 00) -> no bus fight
  function [63:0] rframe(input [4:0] a, input [4:0] r); rframe = {32'hFFFFFFFF, 4'b0110, 5'd31, r, 18'h3FFFF}; endfunction
`else
  function [63:0] rframe(input [4:0] a, input [4:0] r); rframe = {32'hFFFFFFFF, 4'b0110, a, r, 18'h3FFFF}; endfunction
`endif
  function [63:0] wframe(input [4:0] a, input [4:0] r, input [15:0] d); wframe = {32'hFFFFFFFF, 4'b0101, a, r, 2'b10, d}; endfunction
  // ---------------- sequencer ----------------
  reg [4:0] step = 0; reg [7:0] passes = 0; reg wrote = 0; reg [7:0] idm = 0; reg [2:0] addr = 0; reg found = 0; reg [2:0] waddr = 0;
  reg [15:0] r0 = 0, r1 = 0, r4 = 0, r5 = 0, r9 = 0, ra = 0, rf = 0;
  reg waitb = 0; reg [1:0] wst = 0; reg print_req = 0;
  reg [22:0] gap = 0;
  wire do_write = (passes == WRITE_AFTER) && !wrote;
  always @(posedge clk25) begin
    print_req <= 0;
    if (mdio_en) case (wst)
      0: if (gap[22] || step != 0) begin                       // ~3 passes / s
           gap <= 0;
           if (step < 8) begin fr_in <= rframe(step, 2); rd_in <= 1; end
           else case (step)
             // writes go to EVERY PHYAD 0..7 (reads may not identify the PHY)
             8:  begin fr_in <= wframe(waddr, 9, REG9); rd_in <= 0; end
             9:  begin fr_in <= wframe(waddr, 4, REG4); rd_in <= 0; end
             10: begin fr_in <= wframe(waddr, 0, REG0); rd_in <= 0; end
             11: begin fr_in <= rframe(addr, 0);  rd_in <= 1; end
             12: begin fr_in <= rframe(addr, 1);  rd_in <= 1; end
             13: begin fr_in <= rframe(addr, 4);  rd_in <= 1; end
             14: begin fr_in <= rframe(addr, 5);  rd_in <= 1; end
             15: begin fr_in <= rframe(addr, 9);  rd_in <= 1; end
             16: begin fr_in <= rframe(addr, 10); rd_in <= 1; end
             default: begin fr_in <= rframe(addr, 31); rd_in <= 1; end
           endcase
           if (step >= 8 && step <= 10 && !do_write) step <= 11;  // skip writes
           else begin start <= 1; wst <= 1; end
         end else gap <= gap + 1;
      1: if (busy) begin start <= 0; wst <= 2; end
      2: if (!busy) begin
           if (step < 8) begin idm[step[2:0]] <= ~rx[16] & (rx[15:0] == 16'h0022);
                               if (!found && !rx[16]) begin found <= 1; addr <= step[2:0]; end end
           case (step) 11: r0 <= rx[15:0]; 12: r1 <= rx[15:0]; 13: r4 <= rx[15:0]; 14: r5 <= rx[15:0];
                       15: r9 <= rx[15:0]; 16: ra <= rx[15:0]; 17: rf <= rx[15:0]; default: ; endcase
           if (step == 10 && waddr == 3'd7) wrote <= 1;
           if (step == 17) begin step <= 0; passes <= passes + 1; print_req <= 1; found <= 0; end
           else if (step == 10 && waddr != 3'd7) begin waddr <= waddr + 1; step <= 8; end
           else step <= step + 1;
           wst <= 0;
         end
    endcase
  end
  // ---------------- RXC frequency + RX_CTL frames ----------------
  reg [23:0] rc = 0; reg [15:0] fc = 0; reg ctl_d = 0;
`ifndef NO_RXC
  always @(posedge rxc) begin rc <= rc + 1; ctl_d <= rx_ctl; if (rx_ctl && !ctl_d) fc <= fc + 1; end
`endif
  wire [23:0] rcg = rc ^ (rc >> 1); wire [15:0] fcg = fc ^ (fc >> 1);
  reg [23:0] rcg1 = 0, rcg2 = 0; reg [15:0] fcg1 = 0, fcg2 = 0;
  always @(posedge clk25) begin rcg1 <= rcg; rcg2 <= rcg1; fcg1 <= fcg; fcg2 <= fcg1; end
  function [23:0] g2b24(input [23:0] g); integer i; begin g2b24[23] = g[23]; for (i = 22; i >= 0; i = i - 1) g2b24[i] = g2b24[i+1] ^ g[i]; end endfunction
  function [15:0] g2b16(input [15:0] g); integer i; begin g2b16[15] = g[15]; for (i = 14; i >= 0; i = i - 1) g2b16[i] = g2b16[i+1] ^ g[i]; end endfunction
  reg [19:0] win = 0; reg [23:0] rc_prev = 0, rfreq = 0; reg [15:0] frames = 0;
  always @(posedge clk25) begin
    win <= win + 1;
    if (win == 0) begin rfreq <= g2b24(rcg2) - rc_prev; rc_prev <= g2b24(rcg2); frames <= g2b16(fcg2); end
  end
  // ---------------- UART line ----------------
  function [7:0] hx(input [3:0] n); hx = n < 10 ? 8'h30 + n : 8'h37 + n; endfunction
  reg [7:0] baud = 0; wire tick = (baud == BAUD);
  always @(posedge clk25) baud <= tick ? 0 : baud + 1;
  reg [6:0] idx = 0; reg [1:0] us = 0; reg [9:0] sh = 10'h3FF; reg [3:0] nb = 0; reg preq = 0;
  // UART prints the live registers (a load-enabled snapshot is a ~150-wide EN net that does not route
  // next to the Ethernet beacon); a value may change mid-line, which is cosmetic.
  wire [7:0] sp = passes; wire sw = wrote; wire [7:0] sm = idm; wire [2:0] sa = addr;
  wire [15:0] s0 = r0, s1 = r1, s4 = r4, s5 = r5, s9 = r9, sa_ = ra, sf = rf; wire [23:0] sc = rfreq; wire [15:0] sfr = frames;
  always @(posedge clk25) if (print_req) preq <= 1; else if (us == 1) preq <= 0;
  reg [7:0] ch;
  always @* begin
    ch = " ";
    case (idx)
      0: ch = "P"; 1: ch = "="; 2: ch = hx(sp[7:4]); 3: ch = hx(sp[3:0]);
      5: ch = "W"; 6: ch = "="; 7: ch = hx({3'b0, sw});
      9: ch = "M"; 10: ch = "="; 11: ch = hx(sm[7:4]); 12: ch = hx(sm[3:0]);
      14: ch = "A"; 15: ch = "="; 16: ch = hx({1'b0, sa});
      18: ch = "R"; 19: ch = "0"; 20: ch = "="; 21: ch = hx(s0[15:12]); 22: ch = hx(s0[11:8]); 23: ch = hx(s0[7:4]); 24: ch = hx(s0[3:0]);
      26: ch = "R"; 27: ch = "1"; 28: ch = "="; 29: ch = hx(s1[15:12]); 30: ch = hx(s1[11:8]); 31: ch = hx(s1[7:4]); 32: ch = hx(s1[3:0]);
      34: ch = "R"; 35: ch = "4"; 36: ch = "="; 37: ch = hx(s4[15:12]); 38: ch = hx(s4[11:8]); 39: ch = hx(s4[7:4]); 40: ch = hx(s4[3:0]);
      42: ch = "R"; 43: ch = "5"; 44: ch = "="; 45: ch = hx(s5[15:12]); 46: ch = hx(s5[11:8]); 47: ch = hx(s5[7:4]); 48: ch = hx(s5[3:0]);
      50: ch = "R"; 51: ch = "9"; 52: ch = "="; 53: ch = hx(s9[15:12]); 54: ch = hx(s9[11:8]); 55: ch = hx(s9[7:4]); 56: ch = hx(s9[3:0]);
      58: ch = "R"; 59: ch = "A"; 60: ch = "="; 61: ch = hx(sa_[15:12]); 62: ch = hx(sa_[11:8]); 63: ch = hx(sa_[7:4]); 64: ch = hx(sa_[3:0]);
      66: ch = "R"; 67: ch = "F"; 68: ch = "="; 69: ch = hx(sf[15:12]); 70: ch = hx(sf[11:8]); 71: ch = hx(sf[7:4]); 72: ch = hx(sf[3:0]);
      74: ch = "C"; 75: ch = "="; 76: ch = hx(sc[23:20]); 77: ch = hx(sc[19:16]); 78: ch = hx(sc[15:12]); 79: ch = hx(sc[11:8]); 80: ch = hx(sc[7:4]); 81: ch = hx(sc[3:0]);
      83: ch = "F"; 84: ch = "="; 85: ch = hx(sfr[15:12]); 86: ch = hx(sfr[11:8]); 87: ch = hx(sfr[7:4]); 88: ch = hx(sfr[3:0]);
      90: ch = "D"; 91: ch = "=";
      92: ch = hx(dbg[63:60]); 93: ch = hx(dbg[59:56]); 94: ch = hx(dbg[55:52]); 95: ch = hx(dbg[51:48]);
      96: ch = hx(dbg[47:44]); 97: ch = hx(dbg[43:40]); 98: ch = hx(dbg[39:36]); 99: ch = hx(dbg[35:32]);
      100: ch = hx(dbg[31:28]); 101: ch = hx(dbg[27:24]); 102: ch = hx(dbg[23:20]); 103: ch = hx(dbg[19:16]);
      104: ch = hx(dbg[15:12]); 105: ch = hx(dbg[11:8]); 106: ch = hx(dbg[7:4]); 107: ch = hx(dbg[3:0]);
      108: ch = 8'h0D; 109: ch = 8'h0A;
      default: ch = " ";
    endcase
  end
  always @(posedge clk25) if (tick) case (us)
    0: if (preq) begin idx <= 0; us <= 1; end
    1: begin sh <= {1'b1, ch, 1'b0}; nb <= 0; us <= 2; end
    2: begin sh <= {1'b1, sh[9:1]}; nb <= nb + 1;
         if (nb == 9) begin if (idx == 109) us <= 0; else begin idx <= idx + 1; us <= 1; end end end
    default: us <= 0;
  endcase
  assign uart_a = sh[0]; assign uart_b = sh[0];
  // bus for the Ethernet beacon (TASK-4999): quasi-static, re-sampled per frame
  assign snap_bus = {passes, idm, {wrote, 4'b0, addr}, r0, r1, r4, r5, r9, ra, rf, rfreq, frames, 80'h0};
endmodule
