// TASK-5093 H2: CCGM1A2 CPE flip-flop probes at several positions (floorplanned via CCF place boxes).
// Group g: toggle FF, FF with D=1, FF with D=0. UART "E<hex> K<hex> N<frames>": K nibble g = {1, zero_s, one_s, t_seen};
// a working group reads B (toggle seen, D=1 -> 1, D=0 -> 0). Byte with a 0 bit on serial_rx clears (reset).
module probe (input clk, input tgl, output t_q, output one_q, output zero_q);
  // H4 (TASK-5093): t = transparent latch (G=1) following tgl from 1A; one = FF D=0 with async SET driven by tgl
  // (reads 1 whenever tgl=1 -> "seen 1" if async control works); zero = FF D=tgl with EN=tgl routed (not constant)
  CC_DLT #(.G_INV(1'b0), .SR_INV(1'b0), .SR_VAL(1'b0)) t (.D(tgl), .G(1'b1), .SR(1'b0), .Q(t_q));
  CC_DFF #(.CLK_INV(1'b0), .EN_INV(1'b0), .SR_INV(1'b0), .SR_VAL(1'b1)) o (.D(1'b0), .CLK(clk), .EN(1'b1), .SR(tgl), .Q(one_q));
  CC_DFF #(.CLK_INV(1'b0), .EN_INV(1'b0), .SR_INV(1'b0), .SR_VAL(1'b0)) z (.D(tgl), .CLK(clk), .EN(tgl), .SR(1'b0), .Q(zero_q));
endmodule
module top #(parameter G = 8) (input clk25, input serial_rx, output serial_tx, output [7:0] led);
  wire clk; CC_BUFG u_bufg (.I(clk25), .O(clk));
  reg rx1, rx2; always @(posedge clk) begin rx1 <= serial_rx; rx2 <= rx1; end
  wire rst = ~rx2;
  reg [22:0] dv = 0; always @(posedge clk) dv <= dv + 1; wire tgl = dv[22];
  wire [G-1:0] tq, oq, zq;
  probe g0 (clk, tgl, tq[0], oq[0], zq[0]);
  probe g1 (clk, tgl, tq[1], oq[1], zq[1]);
  probe g2 (clk, tgl, tq[2], oq[2], zq[2]);
  probe g3 (clk, tgl, tq[3], oq[3], zq[3]);
  probe g4 (clk, tgl, tq[4], oq[4], zq[4]);
  probe g5 (clk, tgl, tq[5], oq[5], zq[5]);
  probe g6 (clk, tgl, tq[6], oq[6], zq[6]);
  probe g7 (clk, tgl, tq[7], oq[7], zq[7]);
  reg [G-1:0] t1 = 0, t2 = 0, seen = 0, os = 0, zs = 0, z1 = 0, z2 = 0;
  always @(posedge clk) begin
    t1 <= tq; t2 <= t1; z1 <= zq; z2 <= z1;
    if (rst) begin seen <= 0; os <= 0; zs <= 0; end else begin seen <= seen | (t1 ^ t2); os <= os | oq; zs <= zs | (z1 ^ z2); end
  end
  wire [31:0] kk;
  genvar i; generate for (i = 0; i < G; i = i + 1) begin : k
    assign kk[4*i +: 4] = {1'b1, zs[i], os[i], seen[i]};
  end endgenerate
  localparam N = 32;
  reg [7:0] div = 0; reg [3:0] bitn = 0; reg [9:0] sh = 10'h3ff; reg busy = 0;
  reg [7:0] idx = 0; reg [23:0] tick = 0; reg [15:0] frames = 0; reg sending = 0;
  reg [N-1:0] ks = 0;
  function [7:0] hexc(input [3:0] v); hexc = v < 10 ? 8'h30 + v : 8'h37 + v; endfunction
  reg [7:0] ch;
  always @(*) begin
    if (idx == 0) ch = "K";
    else if (idx <= N/4) ch = hexc(ks[N - 4*idx +: 4]);
    else if (idx == N/4 + 1) ch = " ";
    else if (idx == N/4 + 2) ch = "N";
    else if (idx <= N/4 + 6) ch = hexc(frames[16 - 4*(idx - N/4 - 2) +: 4]);
    else if (idx == N/4 + 7) ch = 8'h0d;
    else ch = 8'h0a;
  end
  always @(posedge clk) if (rst) begin
    tick <= 1; frames <= 0; sending <= 0; busy <= 0; idx <= 0; div <= 0; bitn <= 0; sh <= 10'h3ff;
  end else begin
    tick <= tick + 1;
    if (tick == 0 && !sending) begin sending <= 1; idx <= 0; ks <= kk; frames <= frames + 1; end
    if (!busy && sending) begin
      sh <= {1'b1, ch, 1'b0}; busy <= 1; div <= 0; bitn <= 0;
    end else if (busy) begin
      if (div == 216) begin
        div <= 0; sh <= {1'b1, sh[9:1]}; bitn <= bitn + 1;
        if (bitn == 9) begin busy <= 0; if (idx == N/4 + 8) sending <= 0; else idx <= idx + 1; end
      end else div <= div + 1;
    end
  end
  assign serial_tx = busy ? sh[0] : 1'b1;
  assign led = frames[7:0];
endmodule
