// CCGM1A2 die-1B hardware test (TASK-5092). All at 25 MHz (clk25). Board: ULX5M-GS with CCGM1A2.
// Per bit g: a[g] (1A) -> CC_DFF ".ub" on 1B -> CC_DFF on 1A, compared with a delayed by 2 -> sticky mask E;
// a[g] (1A) -> CC_LUT1 ".ul" on 1B -> CC_DFF on 1A, compared with a delayed by 1 -> sticky mask K[31:4].
// Probes on 1B: K[0] toggle FF seen toggling, K[1] FF with D=1, K[2] FF with D=0, K[3] = 1 (marker).
// UART: "E<hex> K<hex> N<frames>" + CR LF every ~0.67 s; any received byte with a 0 bit clears the masks (reset).
module top #(parameter N = 32) (input clk25, input serial_rx, output serial_tx, output [7:0] led, inout rst_pad);
  wire clk, usr_rstn;
  CC_BUFG u_bufg (.I(clk25), .O(clk));
  // TASK-5095: self-reset through IO_SB_B8 = RST_N (selfrst.v); UART "R!" resets the whole chip, 0x00 only clears masks
  wire rst_oe;
  selfrst u_sr (.clk(clk), .rx(serial_rx), .rst_oe(rst_oe));
  assign rst_pad = rst_oe ? 1'b0 : 1'bz;
  CC_USR_RSTN u_rstn (.USR_RSTN(usr_rstn));   // FF init values are not applied on GateMate: explicit reset
  // Reset from the UART: GateMate ignores init values, yosys may fold a power-on shift register fed with a constant,
  // and CC_USR_RSTN gave no reset pulse on the A2. Any byte with a low bit (e.g. 0x00 from the Pi) clears the masks.
  reg rx1, rx2;
  always @(posedge clk) begin rx1 <= serial_rx; rx2 <= rx1; end
  wire rst = ~rx2;
  reg [N-1:0] a = {N{1'b1}}, a_d1 = 0, a_d2 = 0, e = 0, kerr = 0, lerr = 0;
  wire [N-1:0] b_q, c, k1, k2, l_b, l_c;
  // die-1B register probes: toggle, D=1, D=0 (CC_DFF primitives, names end in .ub so they go to 1B)
  wire t_q, one_q, zero_q;
  generate if (1) begin : tp
    CC_DFF #(.CLK_INV(1'b0), .EN_INV(1'b0), .SR_INV(1'b0), .SR_VAL(1'b0)) ub (.D(~t_q), .CLK(clk), .EN(1'b1), .SR(1'b0), .Q(t_q));
  end endgenerate
  generate if (1) begin : op
    CC_DFF #(.CLK_INV(1'b0), .EN_INV(1'b0), .SR_INV(1'b0), .SR_VAL(1'b0)) ub (.D(1'b1), .CLK(clk), .EN(1'b1), .SR(1'b0), .Q(one_q));
  end endgenerate
  generate if (1) begin : zp
    CC_DFF #(.CLK_INV(1'b0), .EN_INV(1'b0), .SR_INV(1'b0), .SR_VAL(1'b0)) ub (.D(1'b0), .CLK(clk), .EN(1'b1), .SR(1'b0), .Q(zero_q));
  end endgenerate
  reg t1, t2, t_seen, one_s, zero_s;
  // CC_DFF primitives: plain registers with the same D would be merged by yosys (opt_merge) and the test folded away
  genvar g;
  generate for (g = 0; g < N; g = g + 1) begin : p
    CC_DFF #(.CLK_INV(1'b0), .EN_INV(1'b0), .SR_INV(1'b0), .SR_VAL(1'b0)) ub (.D(a[g]),   .CLK(clk), .EN(1'b1), .SR(1'b0), .Q(b_q[g])); // 1A -> 1B
    CC_DFF #(.CLK_INV(1'b0), .EN_INV(1'b0), .SR_INV(1'b0), .SR_VAL(1'b0)) uc (.D(b_q[g]), .CLK(clk), .EN(1'b1), .SR(1'b0), .Q(c[g]));   // 1B -> 1A
    CC_DFF #(.CLK_INV(1'b0), .EN_INV(1'b0), .SR_INV(1'b0), .SR_VAL(1'b0)) uk1 (.D(a[g]),  .CLK(clk), .EN(1'b1), .SR(1'b0), .Q(k1[g]));
    // L path: 1A reg -> LUT buffer on 1B (no clock on 1B) -> 1A reg
    CC_LUT1 #(.INIT(2'b10)) ul (.I0(a[g]), .O(l_b[g]));
    CC_DFF #(.CLK_INV(1'b0), .EN_INV(1'b0), .SR_INV(1'b0), .SR_VAL(1'b0)) ulc (.D(l_b[g]), .CLK(clk), .EN(1'b1), .SR(1'b0), .Q(l_c[g]));
    CC_DFF #(.CLK_INV(1'b0), .EN_INV(1'b0), .SR_INV(1'b0), .SR_VAL(1'b0)) uk2 (.D(k1[g]), .CLK(clk), .EN(1'b1), .SR(1'b0), .Q(k2[g]));
  end endgenerate
  reg [5:0] warm = 0;
  integer i;
  always @(posedge clk) if (rst) begin
    a <= {N{1'b1}}; a_d1 <= 0; a_d2 <= 0; e <= 0; kerr <= 0; lerr <= 0; warm <= 0; t_seen <= 0;
  end else begin
    for (i = 0; i < N/32; i = i + 1)
      a[32*i +: 32] <= {a[32*i +: 31], a[32*i+31] ^ a[32*i+21] ^ a[32*i+1] ^ a[32*i]};
    a_d1 <= a; a_d2 <= a_d1;
    if (~&warm) warm <= warm + 1;
    else begin
      e <= e | (c ^ a_d2);
      kerr <= kerr | (k2 ^ a_d2);
      lerr <= lerr | (l_c ^ a_d1);
      t1 <= t_q; t2 <= t1; if (t1 != t2) t_seen <= 1; one_s <= one_q; zero_s <= zero_q;
    end
  end
  // UART 115200 from 25 MHz: 217 clocks per bit
  localparam MSG = 1 + N/4 + 2 + N/4 + 2 + 4 + 2;   // E<hex> ' ' K<hex> ' ' N<4 hex> \r\n
  reg [7:0] div = 0; reg [3:0] bitn = 0; reg [9:0] sh = 10'h3ff; reg busy = 0;
  reg [7:0] idx = 0; reg [23:0] tick = 0; reg [15:0] frames = 0; reg sending = 0;
  reg [N-1:0] es = 0, ks = 0;
  function [7:0] hexc(input [3:0] v); hexc = v < 10 ? 8'h30 + v : 8'h37 + v; endfunction
  reg [7:0] ch;
  always @(*) begin
    if (idx == 0) ch = "E";
    else if (idx <= N/4) ch = hexc(es[N - 4*idx +: 4]);
    else if (idx == N/4 + 1) ch = " ";
    else if (idx == N/4 + 2) ch = "K";
    else if (idx <= N/2 + 2) ch = hexc(ks[N - 4*(idx - N/4 - 2) +: 4]);
    else if (idx == N/2 + 3) ch = " ";
    else if (idx == N/2 + 4) ch = "N";
    else if (idx <= N/2 + 8) ch = hexc(frames[16 - 4*(idx - N/2 - 4) +: 4]);
    else if (idx == N/2 + 9) ch = 8'h0d;
    else ch = 8'h0a;
  end
  always @(posedge clk) if (rst) begin
    tick <= 1; frames <= 0; sending <= 0; busy <= 0; idx <= 0; div <= 0; bitn <= 0; sh <= 10'h3ff;
  end else begin
    tick <= tick + 1;
    if (tick == 0 && !sending) begin sending <= 1; idx <= 0; es <= e; ks <= {lerr[N-1:4], 1'b1, zero_s, one_s, t_seen}; frames <= frames + 1; end
    if (!busy && sending) begin
      sh <= {1'b1, ch, 1'b0}; busy <= 1; div <= 0; bitn <= 0;
    end else if (busy) begin
      if (div == 216) begin
        div <= 0; sh <= {1'b1, sh[9:1]}; bitn <= bitn + 1;
        if (bitn == 9) begin busy <= 0; if (idx == N/2 + 10) sending <= 0; else idx <= idx + 1; end
      end else div <= div + 1;
    end
  end
  assign serial_tx = busy ? sh[0] : 1'b1;
  assign led = {frames[3:0], |kerr, |e, 2'b00};
endmodule
