// TASK-5532 revizija: rubni slucajevi ber_rx/ber_tx (ne mijenja repo)
`timescale 1ns/1ps
module tbr;
  reg clk = 0; always #5 clk = ~clk;
  reg brk = 0, zero = 0, auxbad = 0;
  wire [63:0] txd; wire [7:0] txk; wire [4:0] slot; wire [7:0] ic;
  ber_tx #(.MY_ID(3'd5)) utx(.clk(clk), .inject_tgl(1'b0), .aux_in({256{1'b0}}), .tx_data(txd), .tx_k(txk), .slot(slot), .inj_cnt(ic));
  // T1: zakljucavanje na nulu - kanal salje payload 0 (kao da je TX LFSR = 0), K28.5 i id ispravni
  wire [63:0] ch0 = zero ? {txd[63:56], 40'h0, txd[15:0]} : txd;
  // T3: pogreska samo u aux bajtu (byte7) uz ispravan PRBS
  wire [63:0] ch1 = auxbad ? (ch0 ^ {8'h01, 56'h0}) : ch0;
  wire [63:0] ch = brk ? 64'hFFFFFFFFFFFFFFFF : ch1; wire [7:0] chk = brk ? 8'h00 : txk;
  wire sy, ss, stb; wire [47:0] wc; wire [31:0] ew, eb, ce, pf; wire [4:0] lc; wire [255:0] fr;
  ber_rx #(.MY_ID(3'd3), .PEER_ID(3'd5)) urx(.clk(clk), .rx_data(ch), .rx_k(chk), .rx_code_err(1'b0), .clr_tgl(1'b0),
     .synced(sy), .self_seen(ss), .word_cnt(wc), .err_words(ew), .err_bits(eb), .code_err(ce), .loss_cnt(lc),
     .peer_frame(fr), .peer_frames(pf), .peer_stb(stb));
  integer k, pf0;
  initial begin
    repeat (200) @(posedge clk);
    $display("T0 init: tx lfsr=%h (!=0: %0d) synced=%0d errw=%0d", utx.lfsr, utx.lfsr != 0, sy, ew);
    // T2: 40 prekida -> loss_cnt (5 bita) se preljeva
    for (k = 0; k < 40; k = k + 1) begin brk = 1; repeat (100) @(posedge clk); brk = 0; repeat (100) @(posedge clk); end
    $display("T2 40 prekida sinkronizacije -> loss_cnt=%0d (ocekivano 40 bez preljeva; 40 mod 32 = 8)", lc);
    // T1: payload 0 -> nakon gubitka sinkronizacije checker se sam zasije na 0 i broji 0 pogresaka
    zero = 1; brk = 1; repeat (100) @(posedge clk); brk = 0; repeat (300) @(posedge clk);
    $display("T1 payload=0: synced=%0d errw_delta_check expv=%h -> lazni PASS ako synced=1 i expv=0", sy, urx.expv);
    zero = 0; repeat (200) @(posedge clk);
    // T3: aux bajt pokvaren, PRBS ispravan -> okvir se i dalje prihvaca (nema zastite aux kanala)
    pf0 = pf; auxbad = 1; repeat (200) @(posedge clk); auxbad = 0;
    $display("T3 aux bajt pokvaren: prihvaceno okvira=%0d, peer_frame[7:0]=%h (0 = ispravno)", pf - pf0, fr[7:0]);
    $finish;
  end
endmodule
