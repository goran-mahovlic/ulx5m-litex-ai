// JTAG snapshot mailbox for GateMate (TASK-4999).
//
// Uses the CC_SERDES register file as a fabric -> JTAG mailbox. The SerDes itself stays in
// reset and powered down (no SerDes pins are used); only its regfile is shared by two ports:
//   - fabric port (REGFILE_* pins, clocked by `clk`)
//   - JTAG port   (TAP instructions 0x25 WR_SERDES_REGFILE / 0x26 RD_SERDES_REGFILE,
//                  read on the Pi with tools/jtag_mailbox.py over DirtyJTAG)
// No user IO is touched, so the JTAG pins stay dedicated and `openFPGALoader -r` keeps working.
//
// MEASURED (23.9.2026): the fabric port stops accepting writes after a random number of accesses
// (ms .. s; earlier in big designs). Hence GAP_LOG2: write the snapshot only a few times per
// second. TAG (seq) tells how many passes landed before a stall.
// Treat it as a SNAPSHOT: the fabric rewrites the whole snapshot continuously and the reader
// takes it once per configuration (`openFPGALoader -r`, wait, read). See docs for measurements.
//
// Layout: 0x00 TAG0 (written first) and 0x39 TAG1 (written last) = the same sequence number,
// a snapshot is consistent when TAG0 == TAG1.
//   w16: 6 x 16-bit words -> 0x01 0x03 0x08 0x0A 0x31 0x35
//   w15: 9 x 15-bit words -> 0x30 0x32 0x33 0x34 0x36 0x37 0x38 0x3A 0x3B
module jtag_mailbox #(
    parameter GAP_LOG2 = 11   // idle cycles between passes = 2**GAP_LOG2
) (
    input  wire          clk,
    input  wire          rst,
    input  wire [95:0]   w16,
    input  wire [134:0]  w15,
    output wire [15:0]   rdy_info   // {RDY ever seen high, 15'b0}
);
    // REGFILE_CLK must be the global clock (a fabric-generated clk/8 never wrote: measured).
    // ADDR/DI/WE come from flops that change only at ph == 0 and EN is high for exactly one clk
    // cycle at ph == 4: every input is stable >= 3 cycles around the sampling edge, so routing
    // skew into the SerDes block (not analysed by nextpnr) cannot corrupt a transfer.
    reg  [2:0]  ph;
    reg         rf_en, rf_we;
    reg  [7:0]  rf_addr;
    reg  [15:0] rf_di;
    wire [15:0] rf_do;
    wire        rf_rdy;

    CC_SERDES #(
        .SERDES_ENABLE(1'b1)
    ) mailbox_serdes (
        .REGFILE_CLK_I (clk),
        .REGFILE_EN_I  (rf_en),
        .REGFILE_WE_I  (rf_we),
        .REGFILE_ADDR_I(rf_addr),
        .REGFILE_DI_I  (rf_di),
        .REGFILE_MASK_I(16'hFFFF),
        .REGFILE_DO_O  (rf_do),
        .REGFILE_RDY_O (rf_rdy),
        .PLL_RESET_I   (1'b1),
        .TX_RESET_I    (1'b1),
        .RX_RESET_I    (1'b1),
        .TX_POWER_DOWN_N_I(1'b0),
        .RX_POWER_DOWN_N_I(1'b0)
    );

    // step 0 = TAG0, 1..6 = w16, 7..15 = w15, 16 = TAG1; one access per 16 regfile clocks,
    // 2**GAP_LOG2 ticks (of clk/8) idle between passes.
    reg  [4:0]  step;
    reg  [GAP_LOG2-1:0] wait_cnt;
    reg  [15:0] seq;
    reg  [271:0] sr;    // snapshot latched at step 0 (coherent pass), shifted out 16 bits/access
    reg         rdy_seen;

    reg  [7:0]  addr_n;
    always @(*) begin
        case (step)
            5'd0:  addr_n = 8'h00;
            5'd1:  addr_n = 8'h01;
            5'd2:  addr_n = 8'h03;
            5'd3:  addr_n = 8'h08;
            5'd4:  addr_n = 8'h0A;
            5'd5:  addr_n = 8'h31;
            5'd6:  addr_n = 8'h35;
            5'd7:  addr_n = 8'h30;
            5'd8:  addr_n = 8'h32;
            5'd9:  addr_n = 8'h33;
            5'd10: addr_n = 8'h34;
            5'd11: addr_n = 8'h36;
            5'd12: addr_n = 8'h37;
            5'd13: addr_n = 8'h38;
            5'd14: addr_n = 8'h3A;
            5'd15: addr_n = 8'h3B;
            default: addr_n = 8'h39;
        endcase
    end

    assign rdy_info = {rdy_seen, 15'd0};

    always @(posedge clk) begin
        if (rst) begin
            ph <= 3'd0;
            rf_en <= 1'b0; rf_we <= 1'b0; rf_addr <= 8'h00; rf_di <= 16'h0;
            step <= 5'd0; wait_cnt <= 0; seq <= 16'd0;
            sr <= 272'd0; rdy_seen <= 1'b0;
        end else begin
            ph <= ph + 3'd1;
            if (rf_rdy) rdy_seen <= 1'b1;
            rf_en <= (ph == 3'd3) && (wait_cnt == 5);   // high during ph == 4 only
            if (ph == 3'd0) begin
                wait_cnt <= wait_cnt + 1'd1;
                if (wait_cnt == 0) begin
                    if (step == 5'd0)
                        sr <= {seq,
                               1'b0, w15[134:120], 1'b0, w15[119:105], 1'b0, w15[104:90],
                               1'b0, w15[89:75],   1'b0, w15[74:60],   1'b0, w15[59:45],
                               1'b0, w15[44:30],   1'b0, w15[29:15],   1'b0, w15[14:0],
                               w16, seq};
                end else if (wait_cnt == 2) begin
                    rf_addr <= addr_n;
                    rf_di   <= sr[15:0];
                    sr      <= {16'd0, sr[271:16]};
                    rf_we   <= 1'b1;
                end
                if (step == 5'd16 ? (&wait_cnt) : (wait_cnt == 15)) begin
                    wait_cnt <= 0;
                    if (step == 5'd16) begin
                        step <= 5'd0;
                        seq  <= seq + 16'd1;
                    end else
                        step <= step + 5'd1;
                end
            end
        end
    end
endmodule
