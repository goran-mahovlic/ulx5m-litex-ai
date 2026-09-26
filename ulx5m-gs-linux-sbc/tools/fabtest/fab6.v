// TASK-4999 fab6: ring-oscillator speed (-> VDD_CORE) sent over the PLL serial channel.
//  RO: NSTAGE inverting LUTs in a loop, counted for 2^20 clk25 cycles (41.9 ms) -> 24-bit count
//  frame (pll_serial_rx.py rx --state --thr 0x100 --bytes 8): 12x1 sync, 0, 8 bytes each '0'+8 bits LSB first
//   bytes: RO count[23:8] (2), frame seq, c[31:24], errcnt, err_at (c1[31:24] at 1st error), 0xA5, 0x3C
module top(input clk25_pin, output led4, output led5, output led6, output led7);
  parameter NSTAGE = 31;
  wire clk25; CC_BUFG bgc (.I(clk25_pin), .O(clk25));
  // ring oscillator
  (* keep *) wire [NSTAGE-1:0] r;
  genvar i;
  generate for (i = 0; i < NSTAGE; i = i + 1) begin : ro
    if (i == 0) begin
      (* keep *) CC_LUT1 #(.INIT(2'b01)) inv (.I0(r[NSTAGE-1]), .O(r[0]));
    end else begin
      (* keep *) CC_LUT1 #(.INIT(2'b10)) buf_ (.I0(r[i-1]), .O(r[i]));
    end
  end endgenerate
  // RO counter: window = w[19] high (2^19 clk25 = 20.97 ms); rc cleared on window start, held after
  reg [19:0] w = 0; always @(posedge clk25) w <= w + 1;
  reg en = 0; always @(posedge clk25) en <= w[19];
  reg en_s1 = 0, en_s2 = 0, en_s3 = 0;
  (* clkbuf_inhibit *) wire roclk = r[NSTAGE-1];
  reg [23:0] rc = 0;
  always @(posedge roclk) begin
    en_s1 <= en; en_s2 <= en_s1; en_s3 <= en_s2;
    if (en_s2 && !en_s3) rc <= 0; else if (en_s2) rc <= rc + 1;
  end
  reg [23:0] ro_cnt = 0;
  always @(posedge clk25) if (w == 20'h40000) ro_cnt <= rc;   // mid of the idle half: rc is stable
  // integrity monitor (fab5): two identical counters + LFSRs, saturating error count
  wire rstn; CC_USR_RSTN ur (.USR_RSTN(rstn));
  reg [3:0] rs = 0; wire rst = ~rs[3];
  always @(posedge clk25 or negedge rstn) if (!rstn) rs <= 0; else if (!rs[3]) rs <= rs + 1;
  (* keep *) reg [31:0] c1 = 0; (* keep *) reg [31:0] c2 = 0;
  (* keep *) reg [31:0] l1 = 32'h1; (* keep *) reg [31:0] l2 = 32'h1;
  reg [7:0] errcnt = 0; reg [7:0] err_at = 0;
  always @(posedge clk25) begin
    if (rst) begin c1 <= 0; c2 <= 0; l1 <= 32'h1; l2 <= 32'h1; errcnt <= 0; err_at <= 0; end
    else begin
      c1 <= c1 + 1; c2 <= c2 + 1;
      l1 <= {l1[30:0], l1[31] ^ l1[21] ^ l1[1] ^ l1[0]};
      l2 <= {l2[30:0], l2[31] ^ l2[21] ^ l2[1] ^ l2[0]};
      if (((c1 != c2) || (l1 != l2)) && (errcnt != 8'hFF)) begin
        errcnt <= errcnt + 1;
        if (errcnt == 0) err_at <= c1[31:24];
      end
    end
  end
  // serial out
  reg [31:0] c = 0; always @(posedge clk25) c <= c + 1;
  reg [7:0] seq = 0;
  reg [63:0] data = 0;
  localparam NB = 8, NBITS = 13 + 9*NB;
  reg [6:0] idx = 0;
  reg [23:0] tick = 0;
  reg clk_lvl = 0, dat = 1;
  wire [NBITS-1:0] frame;
  genvar k;
  assign frame[12:0] = {1'b0, 12'hFFF};  // bits 0..11 = 1 (sync), bit 12 = 0
  generate for (k = 0; k < NB; k = k + 1) begin : fb
    assign frame[13 + 9*k] = 1'b0;
    assign frame[13 + 9*k + 8 : 13 + 9*k + 1] = data[8*k +: 8];
  end endgenerate
  always @(posedge clk25) begin
    tick <= tick + 1;
    if (&tick) begin
      clk_lvl <= ~clk_lvl;
      if (idx == NBITS - 1) begin
        idx <= 0; seq <= seq + 1;
        data <= {8'h3C, 8'hA5, err_at, errcnt, c[31:24], seq, ro_cnt[23:8]};
      end else idx <= idx + 1;
    end
    dat <= frame[idx];
  end
  // reference generators /2 (1) and /8 (0)
  reg [2:0] da=0, db=0; reg ga=0, gb=0;
  always @(posedge clk25) begin
    da <= (da >= (clk_lvl ? 3'd1 : 3'd7)) ? 3'd0 : da + 1; ga <= clk_lvl ? (da < 3'd1) : (da < 3'd4);
    db <= (db >= (dat ? 3'd1 : 3'd7)) ? 3'd0 : db + 1; gb <= dat ? (db < 3'd1) : (db < 3'd4);
  end
  (* clkbuf_inhibit *) wire oa; (* clkbuf_inhibit *) wire ob;
  CC_PLL #(.REF_CLK("12.5"), .OUT_CLK("25.0"), .PERF_MD("ECONOMY"), .LOW_JITTER(1), .CI_FILTER_CONST(2), .CP_FILTER_CONST(4), .LOCK_REQ(0))
    pll_clk (.CLK_REF(1'b0), .USR_CLK_REF(ga), .CLK_FEEDBACK(1'b0), .USR_LOCKED_STDY_RST(1'b0), .CLK0(oa));
  CC_PLL #(.REF_CLK("12.5"), .OUT_CLK("25.0"), .PERF_MD("ECONOMY"), .LOW_JITTER(1), .CI_FILTER_CONST(2), .CP_FILTER_CONST(4), .LOCK_REQ(0))
    pll_dat (.CLK_REF(1'b0), .USR_CLK_REF(gb), .CLK_FEEDBACK(1'b0), .USR_LOCKED_STDY_RST(1'b0), .CLK0(ob));
  reg [3:0] a=0,b=0; always @(posedge oa) a<=a+1; always @(posedge ob) b<=b+1;
  assign led4=a[3]; assign led5=b[3]; assign led6=rc[0]; assign led7=clk_lvl;
endmodule
