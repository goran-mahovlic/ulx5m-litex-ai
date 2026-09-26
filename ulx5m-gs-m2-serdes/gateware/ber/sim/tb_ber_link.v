// iverilog testbench: ber_tx -> byte-slipped channel -> ber_rx (TASK-5055)
`timescale 1ns/1ps
module tb;
    reg clk = 0; always #5 clk = ~clk;
    reg inj = 0, clr = 0, brk = 0, flip = 0;
    reg [2:0] off = 3;
    wire [63:0] txd; wire [7:0] txk; wire [4:0] slot; wire [7:0] ic;
    reg [255:0] aux_gs = {32{8'h00}};
    integer j; initial for (j = 0; j < 32; j = j + 1) aux_gs[j*8 +: 8] = 8'hC0 + j;
    ber_tx #(.MY_ID(3'd5)) utx(.clk(clk), .inject_tgl(inj), .aux_in(aux_gs), .tx_data(txd), .tx_k(txk), .slot(slot), .inj_cnt(ic));
    // channel: byte stream regrouped at offset 'off' (what comma alignment on a 32-bit grid can do)
    reg [63:0] pd = 0; reg [7:0] pk = 0;
    always @(posedge clk) begin pd <= txd; pk <= txk; end
    wire [127:0] s2 = {txd, pd}; wire [15:0] k2 = {txk, pk};
    wire [63:0] ch = brk ? 64'hFFFFFFFFFFFFFFFF : (s2[off*8 +: 64] ^ {63'b0, flip});
    wire [7:0]  chk = brk ? 8'h00 : k2[off +: 8];
    wire sy, ss; wire [47:0] wc; wire [31:0] ew, eb, ce, pf; wire [4:0] lc; wire [255:0] fr; wire stb;
    ber_rx #(.MY_ID(3'd3), .PEER_ID(3'd5)) urx(.clk(clk), .rx_data(ch), .rx_k(chk), .rx_code_err(1'b0), .clr_tgl(clr),
        .synced(sy), .self_seen(ss), .word_cnt(wc), .err_words(ew), .err_bits(eb), .code_err(ce),
        .loss_cnt(lc), .peer_frame(fr), .peer_frames(pf), .peer_stb(stb));
    // a receiver that hears its OWN id (internal loop)
    wire sy2, ss2;
    ber_rx #(.MY_ID(3'd5), .PEER_ID(3'd3)) uself(.clk(clk), .rx_data(ch), .rx_k(chk), .rx_code_err(1'b0), .clr_tgl(1'b0),
        .synced(sy2), .self_seen(ss2), .word_cnt(), .err_words(), .err_bits(), .code_err(), .loss_cnt(), .peer_frame(), .peer_frames(), .peer_stb());
    integer fails = 0;
    task check(input c, input [8*48-1:0] msg); begin
        if (c) $display("PASS %0s", msg); else begin $display("FAIL %0s", msg); fails = fails + 1; end end endtask
    initial begin
        repeat (200) @(posedge clk);
        check(sy == 1, "synced at byte offset 3");
        check(ew == 0 && eb == 0, "0 errors on clean channel");
        check(pf > 2 && fr == aux_gs, "aux frame received intact");
        check(!ss && ss2 && !sy2, "own id -> self_seen, never synced");
        // negative control: 3 injected single-bit errors are counted exactly
        inj = 1; repeat (10) @(posedge clk); inj = 0; repeat (10) @(posedge clk); inj = 1; repeat (10) @(posedge clk);
        repeat (20) @(posedge clk);
        check(ew == 3 && eb == 3 && ic == 3, "3 injected errors -> err_words=3 err_bits=3");
        check(sy == 1, "still synced after single errors");
        // cable pull: channel gone for 300 words -> loss of sync, then recovery
        brk = 1; repeat (300) @(posedge clk);
        check(sy == 0 && lc == 1, "cable pulled -> synced=0, loss_cnt=1");
        brk = 0; repeat (100) @(posedge clk);
        check(sy == 1, "cable back -> synced again");
        // clear
        clr = 1; repeat (4) @(posedge clk);
        check(ew == 0 && eb == 0 && lc == 0 && wc < 10, "clear resets counters");
        // other alignment
        off = 0; repeat (300) @(posedge clk); clr = 0; repeat (300) @(posedge clk);
        check(sy == 1, "synced at byte offset 0 (after slip)");
        check(wc > 250 && ew == 0, "words counted, 0 errors after re-clear");
        $display("RESULT fails=%0d", fails);
        $finish;
    end
endmodule
