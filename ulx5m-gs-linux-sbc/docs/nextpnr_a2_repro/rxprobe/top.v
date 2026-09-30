// rxprobe (TASK-5094): does the CCGM1A2 see the KSZ9031 RX pins at all? RX_CTL (IO_EB_A8) and RXD0 (IO_EB_A0) are
// sampled on RXC (IO_EB_A7 -> CC_BUFG) either by CC_IDDR in the die-1B IOSEL (default) or, with -DFAB, by plain
// fabric flip-flops behind a CC_IBUF (logic on die 1A). Gray-coded edge counters are printed on the UART every
// ~0.67 s: "C<RX_CTL rising, rising-edge sample> F<RX_CTL rising, falling-edge sample (IDDR Q1; = C with FAB)>
// D<RXD0 changes> R<RXC cycles / 1024> " (hex, 16 bit each; R grows ~24400/s at 25 MHz RXC, ~122000/s at 125). PHY: RESET_N held high, MDIO untouched (the PHY keeps
// the configuration of the previous SoC). selfrst: UART "R!" pulls IO_SB_B8 = RST_N (reload without power cycle).
`ifndef TICKW
`define TICKW 24   // ~0.67 s at 25 MHz; the testbench uses 16
`endif
module top (input clk25, input serial_rx, output serial_tx, inout rst_pad,
            input eth_clocks_rx, input eth_rx_ctl, input eth_rx_d0, output eth_rst_n);
  wire clk, rxc;
  CC_BUFG u_bufg (.I(clk25), .O(clk));
  CC_BUFG u_rxc (.I(eth_clocks_rx), .O(rxc));
  assign eth_rst_n = 1'b1;
  wire rst_oe;
  selfrst u_sr (.clk(clk), .rx(serial_rx), .rst_oe(rst_oe));
  assign rst_pad = rst_oe ? 1'b0 : 1'bz;

  // RX sampling ------------------------------------------------------------------------------------------------
  wire c_r, c_f, d_r, d_f;
`ifdef FAB
  reg c_r_q, d_r_q; always @(posedge rxc) begin c_r_q <= eth_rx_ctl; d_r_q <= eth_rx_d0; end
  assign c_r = c_r_q; assign c_f = c_r_q; assign d_r = d_r_q; assign d_f = d_r_q;
`else
  CC_IDDR #(.CLK_INV(1'b0)) u_ictl (.D(eth_rx_ctl), .CLK(rxc), .Q0(c_r), .Q1(c_f));
  CC_IDDR #(.CLK_INV(1'b0)) u_id0  (.D(eth_rx_d0),  .CLK(rxc), .Q0(d_r), .Q1(d_f));
`endif
  reg c1 = 0, f1 = 0, d1 = 0;
  reg [15:0] nc = 0, nf = 0, nd = 0, gc = 0, gf = 0, gd = 0, gr = 0; reg [25:0] nr = 0;
  always @(posedge rxc) begin
    c1 <= c_r; f1 <= c_f; d1 <= d_r;
    if (c_r & ~c1) nc <= nc + 1;
    if (c_f & ~f1) nf <= nf + 1;
    if (d_r ^ d1)  nd <= nd + 1;
    nr <= nr + 1;
    gc <= nc ^ (nc >> 1); gf <= nf ^ (nf >> 1); gd <= nd ^ (nd >> 1); gr <= nr[25:10] ^ (nr[25:10] >> 1);
  end
  // into clk (two stages, gray -> binary)
  reg [15:0] sc1, sc2, sf1, sf2, sd1, sd2, sr1, sr2;
  always @(posedge clk) begin sc1 <= gc; sc2 <= sc1; sf1 <= gf; sf2 <= sf1; sd1 <= gd; sd2 <= sd1; sr1 <= gr; sr2 <= sr1; end
  function [15:0] g2b(input [15:0] g); integer k; begin g2b[15] = g[15];
    for (k = 14; k >= 0; k = k - 1) g2b[k] = g2b[k+1] ^ g[k]; end endfunction

  // UART 115200 from 25 MHz (217 clocks per bit) -------------------------------------------------------------------
  localparam MSG = 26;    // 4 x (letter, 4 hex, space) + CR LF
  reg [7:0] div = 0; reg [3:0] bitn = 0; reg [9:0] sh = 10'h3ff; reg busy = 0; reg [4:0] idx = 0;
  reg [`TICKW-1:0] tick = 0; reg sending = 0; reg [15:0] vc, vf, vd, vr;
  function [7:0] hexc(input [3:0] v); hexc = v < 10 ? 8'h30 + v : 8'h37 + v; endfunction
  reg [7:0] ch; reg [15:0] v; reg [2:0] fld; reg [2:0] pos;
  always @(*) begin
    fld = idx / 6; pos = idx % 6;
    case (fld) 0: v = vc; 1: v = vf; 2: v = vd; default: v = vr; endcase
    if (idx == 24) ch = 8'h0d; else if (idx == 25) ch = 8'h0a; else if (pos == 5) ch = " ";
    else if (pos == 0) ch = (fld == 0) ? "C" : (fld == 1) ? "F" : (fld == 2) ? "D" : "R";
    else ch = hexc(v[16 - 4*pos +: 4]);
  end
  assign serial_tx = sh[0];
  always @(posedge clk) begin
    tick <= tick + 1;
    if (!sending && tick == 0) begin sending <= 1; idx <= 0; vc <= g2b(sc2); vf <= g2b(sf2); vd <= g2b(sd2); vr <= g2b(sr2); end
    if (!busy) begin
      if (sending) begin sh <= {1'b1, ch, 1'b0}; busy <= 1; div <= 0; bitn <= 0; end
    end else if (div == 216) begin
      div <= 0; sh <= {1'b1, sh[9:1]}; bitn <= bitn + 1;
      if (bitn == 9) begin busy <= 0; sh <= 10'h3ff; if (idx == MSG - 1) sending <= 0; else idx <= idx + 1; end
    end else div <= div + 1;
  end
endmodule
