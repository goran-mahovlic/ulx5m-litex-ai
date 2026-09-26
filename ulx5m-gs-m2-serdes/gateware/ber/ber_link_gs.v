// ber_link_gs.v = ber_link.v as of 965520c (TASK-5063): one-hot aux write, single-cycle compare/popcount. Used for gs:
// the pipelined ber_link.v does not route on gs (nextpnr router2 "Failed to route" / assertion near the SerDes).
// ber_link.v — fabric BER generator/checker for the GS<->M2 CC_SERDES link (TASK-5055).
// 80-bit datapath, 8b10b on: one 64-bit word (8 bytes) per SerDes word clock.
//   byte0      K28.5 (0xBC, K flag)          -> word alignment
//   byte1      {slot[4:0], id[2:0]}           -> id: who sent it (gs=5, m2=3); slot: aux frame position
//   byte2..6   40-bit PRBS payload            -> checked (LFSR x^40+x^38+x^21+x^19+1, 8 steps/word)
//   byte7      aux byte = aux_frame[slot]     -> 32-byte status/command back-channel
`timescale 1ns/1ps

module ber_prbs40_step8(input [39:0] s, output [39:0] n);
    function [39:0] step8(input [39:0] x);
        integer i; reg [39:0] y;
        begin
            y = x;
            for (i = 0; i < 8; i = i + 1)
                y = {y[38:0], y[39] ^ y[37] ^ y[20] ^ y[18]};
            step8 = y;
        end
    endfunction
    assign n = step8(s);
endmodule

// ---------------------------------------------------------------- TX
module ber_tx #(parameter [2:0] MY_ID = 3'd5) (
    input             clk,
    input             inject_tgl,     // any toggle (already in clk domain) -> flip 1 bit in 1 word
    input      [255:0] aux_in,        // frame to send, sampled at slot 31
    output reg [63:0] tx_data = 64'h0,
    output     [7:0]  tx_k,
    output reg [4:0]  slot = 5'd0,
    output reg [7:0]  inj_cnt = 8'd0
);
    reg  [39:0] lfsr = 40'h00DEADBEEF;
    wire [39:0] lfsr_n;
    ber_prbs40_step8 u_step(.s(lfsr), .n(lfsr_n));
    reg  [255:0] aux = 256'h0;
    reg  inj_q = 1'b0;
    wire inj = inject_tgl ^ inj_q;
    wire [7:0] aux_byte = aux[slot*8 +: 8];

    assign tx_k = 8'h01;
    always @(posedge clk) begin
        inj_q   <= inject_tgl;
        lfsr    <= lfsr_n;
        slot    <= slot + 5'd1;
        if (slot == 5'd31) aux <= aux_in;
        if (inj) inj_cnt <= inj_cnt + 8'd1;
        tx_data <= {aux_byte, lfsr ^ {39'b0, inj}, slot, MY_ID, 8'hBC};
    end
endmodule

// ---------------------------------------------------------------- RX checker
module ber_rx #(parameter [2:0] MY_ID = 3'd5, parameter [2:0] PEER_ID = 3'd2) (
    input             clk,
    input      [63:0] rx_data,
    input      [7:0]  rx_k,
    input             rx_code_err,     // NOT_IN_TABLE | DISP_ERR (any byte) this word
    input             clr_tgl,         // toggle (in clk domain) -> clear counters
    output reg        synced = 1'b0,
    output reg        self_seen = 1'b0, // received OUR id: internal/near loop, not the far board
    output reg [47:0] word_cnt = 0,     // words checked while synced
    output reg [31:0] err_words = 0,
    output reg [31:0] err_bits = 0,
    output reg [31:0] code_err = 0,
    output reg [4:0]  loss_cnt = 0,
    output reg [255:0] peer_frame = 0,  // last complete, error-free aux frame from the peer
    output reg [31:0] peer_frames = 0,  // number of good frames received
    output reg        peer_stb = 1'b0   // 1 cycle when peer_frame updated
);
    // -- alignment: find K28.5 in the previous word, take 8 bytes starting there
    reg [63:0] prev = 0; reg [7:0] prev_k = 0; reg prev_ce = 0;
    // K position is found on the incoming word and registered with it (p_r/found_r describe 'prev'),
    // so the barrel shift below starts from a register (was the rclk critical path).
    reg [2:0] p; reg found; integer i; reg [2:0] p_r = 0; reg found_r = 0;
    always @* begin
        found = 1'b0; p = 3'd0;
        for (i = 7; i >= 0; i = i - 1)
            if (rx_k[i] && rx_data[i*8 +: 8] == 8'hBC) begin found = 1'b1; p = i[2:0]; end
    end
    wire [127:0] two = {rx_data, prev};
    reg  [63:0] w = 0; reg wv = 0; reg wce = 0;
    always @(posedge clk) begin
        prev <= rx_data; prev_k <= rx_k; prev_ce <= rx_code_err; p_r <= p; found_r <= found;
        w  <= two[p_r*8 +: 64];
        wv <= found_r;
        wce <= prev_ce | rx_code_err;
    end

    wire [2:0]  id   = w[10:8];
    wire [4:0]  wslot = w[15:11];
    wire [39:0] pay  = w[55:16];
    wire [7:0]  aux  = w[63:56];

    reg  [39:0] expv = 0;
    wire [39:0] exp_n, pay_n;
    ber_prbs40_step8 u_e(.s(expv), .n(exp_n));
    ber_prbs40_step8 u_p(.s(pay),  .n(pay_n));
    wire [39:0] diff = pay ^ expv;
    // bit-error count is pipelined (d1 -> pop -> p2 -> err_bits): popcount+add was the rclk critical path
    reg  [39:0] d1 = 0; reg e1 = 0, e2 = 0; reg [5:0] p2 = 0;
    reg  [5:0] pop;
    always @* begin pop = 0; for (i = 0; i < 40; i = i + 1) pop = pop + d1[i]; end
    wire good = wv && id == PEER_ID && diff == 40'b0;

    reg [4:0] good_run = 0; reg [6:0] bad_run = 0;
    reg clr_q = 0; wire clr = clr_tgl ^ clr_q;

    // aux frame assembly
    // a_we is a registered one-hot write enable (no slot*8 index arithmetic between registers and the
    // 256 frame bits: that ALU + demux was the rclk critical path at 2.5 Gb/s); a_inc = slot follows the last one
    reg [255:0] fr = 0; reg fr_ok = 1'b0;
    reg a_ok = 1'b0; reg [4:0] a_slot = 0; reg [7:0] a_byte = 0; reg [31:0] a_we = 0;
    reg a_first = 1'b0, a_last = 1'b0, a_inc = 1'b0;
    integer k;

    always @(posedge clk) begin
        clr_q <= clr_tgl;
        peer_stb <= 1'b0;
        e1 <= synced && !good;  d1 <= wv ? diff : {40{1'b1}};
        e2 <= e1;               p2 <= pop;
        if (e2) err_bits <= err_bits + p2;
        if (wv && id == MY_ID) self_seen <= 1'b1;
        if (!synced) begin
            expv <= pay_n;                        // self-seed from what we just got
            if (wv && id == PEER_ID && pay == expv) begin
                if (good_run == 5'd15) begin synced <= 1'b1; bad_run <= 0; end
                good_run <= good_run + 5'd1;
            end else good_run <= 0;
        end else begin
            expv <= exp_n;                        // free-running: 1 bad word = 1 error
            word_cnt <= word_cnt + 48'd1;
            if (!good) begin
                err_words <= err_words + 32'd1;
                bad_run   <= bad_run + 7'd1;
                if (bad_run == 7'd63) begin synced <= 1'b0; good_run <= 0; loss_cnt <= loss_cnt + 5'd1; end
            end else bad_run <= 0;
            if (wce) code_err <= code_err + 32'd1;
        end
        // back-channel frame (only from error-free, contiguous words); one register stage after the
        // 40-bit compare so the compare and the 32-way byte demux are not one path
        a_ok <= good || (!synced && wv && id == PEER_ID && pay == expv);
        a_slot <= wslot; a_byte <= aux;
        a_we <= 32'd1 << wslot; a_first <= wslot == 5'd0; a_last <= wslot == 5'd31; a_inc <= wslot == a_slot + 5'd1;
        for (k = 0; k < 32; k = k + 1) if (a_ok && a_we[k]) fr[k*8 +: 8] <= a_byte;
        if (a_ok) begin
            if (a_first) fr_ok <= 1'b1;
            else if (!a_inc) fr_ok <= 1'b0;
            if (a_last && fr_ok && a_inc) begin
                peer_frame <= {a_byte, fr[247:0]};
                peer_frames <= peer_frames + 32'd1;
                peer_stb <= 1'b1;
            end
        end else fr_ok <= 1'b0;
        if (clr) begin
            word_cnt <= 0; err_words <= 0; err_bits <= 0; code_err <= 0; loss_cnt <= 0;
            self_seen <= 1'b0; peer_frames <= 0;
        end
    end
endmodule
