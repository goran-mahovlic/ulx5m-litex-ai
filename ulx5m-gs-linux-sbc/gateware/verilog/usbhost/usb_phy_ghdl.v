module usb_rx_phy_Bbehavioral_6000000_1500000_8
  (input  clk,
   input  reset,
   input  usb_dif,
   input  usb_dp,
   input  usb_dn,
   output [1:0] linestate,
   output clk_recovered,
   output clk_recovered_edge,
   output rawdata,
   input  rx_en,
   output rx_active,
   output rx_error,
   output valid,
   output [7:0] data);
  wire [7:0] r_pa;
  wire [1:0] r_dif_shift;
  wire [1:0] r_clk_recovered_shift;
  wire s_clk_recovered;
  wire s_linebit;
  wire r_linebit_prev;
  wire s_bit;
  wire r_frame;
  wire [7:0] r_data;
  wire [7:0] r_data_latch;
  reg [7:0] r_valid;
  wire [1:0] r_linestate;
  wire [1:0] r_linestate_sync;
  reg [6:0] r_idlecnt;
  wire r_preamble;
  wire r_rx_en;
  wire r_valid_prev;
  wire n404;
  wire n405;
  wire n406;
  wire [1:0] n407;
  wire n409;
  wire [1:0] n410;
  wire [1:0] n411;
  wire n421;
  wire n422;
  wire n423;
  wire [7:0] n426;
  wire [6:0] n427;
  wire [6:0] n428;
  wire n429;
  wire n430;
  wire n431;
  wire [7:0] n432;
  wire n435;
  wire n437;
  wire n438;
  wire n439;
  wire n441;
  wire n442;
  wire n443;
  wire n447;
  wire n448;
  wire n449;
  wire n450;
  wire n451;
  wire n452;
  wire [5:0] n453;
  wire [6:0] n454;
  wire [6:0] n456;
  wire n457;
  wire n458;
  wire n459;
  wire n460;
  wire n461;
  wire n463;
  wire [6:0] n464;
  wire [7:0] n465;
  wire [7:0] n467;
  wire n469;
  wire n470;
  wire n473;
  wire n474;
  wire n476;
  wire n477;
  wire n478;
  wire n479;
  wire n488;
  wire n489;
  wire n490;
  wire n491;
  wire n493;
  wire [5:0] n494;
  wire n496;
  wire [7:0] n498;
  wire n500;
  wire n503;
  wire n504;
  wire n505;
  wire [6:0] n506;
  wire [7:0] n507;
  wire n509;
  wire [7:0] n511;
  wire n514;
  wire [7:0] n515;
  wire n517;
  wire [7:0] n518;
  wire n519;
  wire [5:0] n521;
  wire n523;
  wire n525;
  wire [7:0] n527;
  wire n529;
  wire n532;
  wire [7:0] n533;
  wire n534;
  wire n537;
  wire [7:0] n539;
  wire n541;
  wire n544;
  wire [7:0] n545;
  wire n550;
  wire [7:0] n552;
  wire n553;
  wire n554;
  localparam n563 = 1'b0;
  wire n567;
  wire n570;
  wire n571;
  wire n572;
  reg [7:0] n574;
  wire [1:0] n575;
  reg [1:0] n576;
  reg [1:0] n577;
  wire n578;
  reg n579;
  reg n580;
  wire [7:0] n581;
  reg [7:0] n582;
  wire [7:0] n583;
  reg [7:0] n584;
  reg [7:0] n585;
  reg [1:0] n586;
  wire [1:0] n587;
  reg [1:0] n588;
  wire [6:0] n589;
  reg [6:0] n590;
  wire n591;
  reg n592;
  reg n593;
  reg n594;
  assign linestate = r_linestate; //(module output)
  assign clk_recovered = s_clk_recovered; //(module output)
  assign clk_recovered_edge = n439; //(module output)
  assign rawdata = r_linebit_prev; //(module output)
  assign rx_active = r_frame; //(module output)
  assign rx_error = n563; //(module output)
  assign valid = n572; //(module output)
  assign data = r_data_latch; //(module output)
  /*# usb11_phy_vhdl/usb_rx_phy.vhd:54:10 */
  assign r_pa = n574; // (signal)
  /*# usb11_phy_vhdl/usb_rx_phy.vhd:55:10 */
  assign r_dif_shift = n576; // (signal)
  /*# usb11_phy_vhdl/usb_rx_phy.vhd:56:10 */
  assign r_clk_recovered_shift = n577; // (signal)
  /*# usb11_phy_vhdl/usb_rx_phy.vhd:57:10 */
  assign s_clk_recovered = n435; // (signal)
  /*# usb11_phy_vhdl/usb_rx_phy.vhd:58:10 */
  assign s_linebit = n441; // (signal)
  /*# usb11_phy_vhdl/usb_rx_phy.vhd:58:21 */
  assign r_linebit_prev = n579; // (signal)
  /*# usb11_phy_vhdl/usb_rx_phy.vhd:58:37 */
  assign s_bit = n443; // (signal)
  /*# usb11_phy_vhdl/usb_rx_phy.vhd:59:10 */
  assign r_frame = n580; // (signal)
  /*# usb11_phy_vhdl/usb_rx_phy.vhd:60:10 */
  assign r_data = n582; // (signal)
  /*# usb11_phy_vhdl/usb_rx_phy.vhd:60:18 */
  assign r_data_latch = n584; // (signal)
  /*# usb11_phy_vhdl/usb_rx_phy.vhd:61:10 */
  always @*
    r_valid = n585; // (isignal)
  initial
    r_valid = 8'b10000000;
  /*# usb11_phy_vhdl/usb_rx_phy.vhd:62:10 */
  assign r_linestate = n586; // (signal)
  /*# usb11_phy_vhdl/usb_rx_phy.vhd:62:23 */
  assign r_linestate_sync = n588; // (signal)
  /*# usb11_phy_vhdl/usb_rx_phy.vhd:64:10 */
  always @*
    r_idlecnt = n590; // (isignal)
  initial
    r_idlecnt = 7'b1000000;
  /*# usb11_phy_vhdl/usb_rx_phy.vhd:65:10 */
  assign r_preamble = n592; // (signal)
  /*# usb11_phy_vhdl/usb_rx_phy.vhd:67:10 */
  assign r_rx_en = n593; // (signal)
  /*# usb11_phy_vhdl/usb_rx_phy.vhd:68:12 */
  assign r_valid_prev = n594; // (signal)
  /*# usb11_phy_vhdl/usb_rx_phy.vhd:73:24 */
  assign n404 = usb_dn | usb_dp;
  /*# usb11_phy_vhdl/usb_rx_phy.vhd:73:41 */
  assign n405 = rx_en & n404;
  /*# usb11_phy_vhdl/usb_rx_phy.vhd:74:45 */
  assign n406 = r_dif_shift[1]; // extract
  /*# usb11_phy_vhdl/usb_rx_phy.vhd:74:32 */
  assign n407 = {usb_dif, n406};
  /*# usb11_phy_vhdl/usb_rx_phy.vhd:76:71 */
  assign n409 = r_clk_recovered_shift[1]; // extract
  /*# usb11_phy_vhdl/usb_rx_phy.vhd:76:48 */
  assign n410 = {s_clk_recovered, n409};
  /*# usb11_phy_vhdl/usb_rx_phy.vhd:77:29 */
  assign n411 = {usb_dn, usb_dp};
  /*# usb11_phy_vhdl/usb_rx_phy.vhd:86:21 */
  assign n421 = r_dif_shift[1]; // extract
  /*# usb11_phy_vhdl/usb_rx_phy.vhd:86:54 */
  assign n422 = r_dif_shift[0]; // extract
  /*# usb11_phy_vhdl/usb_rx_phy.vhd:86:40 */
  assign n423 = n421 != n422;
  /*# usb11_phy_vhdl/usb_rx_phy.vhd:89:22 */
  assign n426 = r_pa + 8'b00100000;
  /*# usb11_phy_vhdl/usb_rx_phy.vhd:89:22 */
  assign n427 = n426[6:0]; // extract
  /*# usb11_phy_vhdl/usb_rx_phy.vhd:86:7 */
  assign n428 = n423 ? 7'b1100000 : n427;
  /*# usb11_phy_vhdl/usb_rx_phy.vhd:89:22 */
  assign n429 = n426[7]; // extract
  /*# usb11_phy_vhdl/usb_rx_phy.vhd:54:10 */
  assign n430 = r_pa[7]; // extract
  /*# usb11_phy_vhdl/usb_rx_phy.vhd:86:7 */
  assign n431 = n423 ? n430 : n429;
  /*# usb11_phy_vhdl/usb_rx_phy.vhd:85:5 */
  assign n432 = {n431, n428};
  /*# usb11_phy_vhdl/usb_rx_phy.vhd:93:26 */
  assign n435 = r_pa[7]; // extract
  /*# usb11_phy_vhdl/usb_rx_phy.vhd:95:55 */
  assign n437 = r_clk_recovered_shift[1]; // extract
  /*# usb11_phy_vhdl/usb_rx_phy.vhd:95:59 */
  assign n438 = n437 != s_clk_recovered;
  /*# usb11_phy_vhdl/usb_rx_phy.vhd:95:29 */
  assign n439 = n438 ? 1'b1 : 1'b0;
  /*# usb11_phy_vhdl/usb_rx_phy.vhd:98:27 */
  assign n441 = r_dif_shift[0]; // extract
  /*# usb11_phy_vhdl/usb_rx_phy.vhd:99:26 */
  assign n442 = s_linebit ^ r_linebit_prev;
  /*# usb11_phy_vhdl/usb_rx_phy.vhd:99:12 */
  assign n443 = ~n442;
  /*# usb11_phy_vhdl/usb_rx_phy.vhd:104:34 */
  assign n447 = ~reset;
  /*# usb11_phy_vhdl/usb_rx_phy.vhd:104:24 */
  assign n448 = n447 & r_rx_en;
  /*# usb11_phy_vhdl/usb_rx_phy.vhd:105:33 */
  assign n449 = r_clk_recovered_shift[1]; // extract
  /*# usb11_phy_vhdl/usb_rx_phy.vhd:105:37 */
  assign n450 = n449 != s_clk_recovered;
  /*# usb11_phy_vhdl/usb_rx_phy.vhd:107:29 */
  assign n451 = r_linebit_prev == s_linebit;
  /*# usb11_phy_vhdl/usb_rx_phy.vhd:108:35 */
  assign n452 = r_idlecnt[0]; // extract
  /*# usb11_phy_vhdl/usb_rx_phy.vhd:108:50 */
  assign n453 = r_idlecnt[6:1]; // extract
  /*# usb11_phy_vhdl/usb_rx_phy.vhd:108:39 */
  assign n454 = {n452, n453};
  /*# usb11_phy_vhdl/usb_rx_phy.vhd:107:11 */
  assign n456 = n451 ? n454 : 7'b1000000;
  /*# usb11_phy_vhdl/usb_rx_phy.vhd:113:24 */
  assign n457 = r_idlecnt[0]; // extract
  /*# usb11_phy_vhdl/usb_rx_phy.vhd:113:28 */
  assign n458 = ~n457;
  /*# usb11_phy_vhdl/usb_rx_phy.vhd:113:34 */
  assign n459 = r_frame & n458;
  /*# usb11_phy_vhdl/usb_rx_phy.vhd:113:64 */
  assign n460 = ~r_frame;
  /*# usb11_phy_vhdl/usb_rx_phy.vhd:113:53 */
  assign n461 = n459 | n460;
  /*# usb11_phy_vhdl/usb_rx_phy.vhd:114:33 */
  assign n463 = r_linestate_sync == 2'b00;
  /*# usb11_phy_vhdl/usb_rx_phy.vhd:117:39 */
  assign n464 = r_data[7:1]; // extract
  /*# usb11_phy_vhdl/usb_rx_phy.vhd:117:31 */
  assign n465 = {s_bit, n464};
  /*# usb11_phy_vhdl/usb_rx_phy.vhd:114:13 */
  assign n467 = n463 ? 8'b00000000 : n465;
  /*# usb11_phy_vhdl/usb_rx_phy.vhd:120:39 */
  assign n469 = r_valid[1]; // extract
  /*# usb11_phy_vhdl/usb_rx_phy.vhd:120:28 */
  assign n470 = n469 & r_frame;
  /*# usb11_phy_vhdl/usb_rx_phy.vhd:105:9 */
  assign n473 = n461 & n450;
  /*# usb11_phy_vhdl/usb_rx_phy.vhd:105:9 */
  assign n474 = n470 & n450;
  /*# usb11_phy_vhdl/usb_rx_phy.vhd:104:7 */
  assign n476 = n450 & n448;
  /*# usb11_phy_vhdl/usb_rx_phy.vhd:104:7 */
  assign n477 = n473 & n448;
  /*# usb11_phy_vhdl/usb_rx_phy.vhd:104:7 */
  assign n478 = n474 & n448;
  /*# usb11_phy_vhdl/usb_rx_phy.vhd:104:7 */
  assign n479 = n450 & n448;
  /*# usb11_phy_vhdl/usb_rx_phy.vhd:134:34 */
  assign n488 = ~reset;
  /*# usb11_phy_vhdl/usb_rx_phy.vhd:134:24 */
  assign n489 = n488 & r_rx_en;
  /*# usb11_phy_vhdl/usb_rx_phy.vhd:135:33 */
  assign n490 = r_clk_recovered_shift[1]; // extract
  /*# usb11_phy_vhdl/usb_rx_phy.vhd:135:37 */
  assign n491 = n490 != s_clk_recovered;
  /*# usb11_phy_vhdl/usb_rx_phy.vhd:137:31 */
  assign n493 = r_linestate_sync == 2'b00;
  /*# usb11_phy_vhdl/usb_rx_phy.vhd:145:28 */
  assign n494 = r_data[6:1]; // extract
  /*# usb11_phy_vhdl/usb_rx_phy.vhd:145:65 */
  assign n496 = n494 == 6'b100000;
  /*# usb11_phy_vhdl/usb_rx_phy.vhd:145:19 */
  assign n498 = n496 ? 8'b10000000 : r_valid;
  /*# usb11_phy_vhdl/usb_rx_phy.vhd:144:17 */
  assign n500 = n519 ? 1'b0 : r_preamble;
  /*# usb11_phy_vhdl/usb_rx_phy.vhd:155:31 */
  assign n503 = r_idlecnt[0]; // extract
  /*# usb11_phy_vhdl/usb_rx_phy.vhd:155:35 */
  assign n504 = ~n503;
  /*# usb11_phy_vhdl/usb_rx_phy.vhd:156:39 */
  assign n505 = r_valid[0]; // extract
  /*# usb11_phy_vhdl/usb_rx_phy.vhd:156:52 */
  assign n506 = r_valid[7:1]; // extract
  /*# usb11_phy_vhdl/usb_rx_phy.vhd:156:43 */
  assign n507 = {n505, n506};
  /*# usb11_phy_vhdl/usb_rx_phy.vhd:158:21 */
  assign n509 = s_bit ? 1'b0 : r_frame;
  /*# usb11_phy_vhdl/usb_rx_phy.vhd:158:21 */
  assign n511 = s_bit ? 8'b00000000 : r_valid;
  /*# usb11_phy_vhdl/usb_rx_phy.vhd:155:19 */
  assign n514 = n504 ? r_frame : n509;
  /*# usb11_phy_vhdl/usb_rx_phy.vhd:155:19 */
  assign n515 = n504 ? n507 : n511;
  /*# usb11_phy_vhdl/usb_rx_phy.vhd:144:17 */
  assign n517 = r_preamble ? r_frame : n514;
  /*# usb11_phy_vhdl/usb_rx_phy.vhd:144:17 */
  assign n518 = r_preamble ? n498 : n515;
  /*# usb11_phy_vhdl/usb_rx_phy.vhd:144:17 */
  assign n519 = n496 & r_preamble;
  /*# usb11_phy_vhdl/usb_rx_phy.vhd:167:24 */
  assign n521 = r_data[7:2]; // extract
  /*# usb11_phy_vhdl/usb_rx_phy.vhd:167:59 */
  assign n523 = n521 == 6'b000111;
  /*# usb11_phy_vhdl/usb_rx_phy.vhd:167:15 */
  assign n525 = n523 ? 1'b1 : r_frame;
  /*# usb11_phy_vhdl/usb_rx_phy.vhd:167:15 */
  assign n527 = n523 ? 8'b00000000 : r_valid;
  /*# usb11_phy_vhdl/usb_rx_phy.vhd:167:15 */
  assign n529 = n523 ? 1'b1 : r_preamble;
  /*# usb11_phy_vhdl/usb_rx_phy.vhd:143:13 */
  assign n532 = r_frame ? n517 : n525;
  /*# usb11_phy_vhdl/usb_rx_phy.vhd:143:13 */
  assign n533 = r_frame ? n518 : n527;
  /*# usb11_phy_vhdl/usb_rx_phy.vhd:143:13 */
  assign n534 = r_frame ? n500 : n529;
  /*# usb11_phy_vhdl/usb_rx_phy.vhd:137:11 */
  assign n537 = n493 ? 1'b0 : n532;
  /*# usb11_phy_vhdl/usb_rx_phy.vhd:137:11 */
  assign n539 = n493 ? 8'b00000000 : n533;
  /*# usb11_phy_vhdl/usb_rx_phy.vhd:137:11 */
  assign n541 = n493 ? 1'b0 : n534;
  /*# usb11_phy_vhdl/usb_rx_phy.vhd:135:9 */
  assign n544 = n491 ? n537 : r_frame;
  /*# usb11_phy_vhdl/usb_rx_phy.vhd:135:9 */
  assign n545 = n491 ? n539 : r_valid;
  /*# usb11_phy_vhdl/usb_rx_phy.vhd:134:7 */
  assign n550 = n489 ? n544 : 1'b0;
  /*# usb11_phy_vhdl/usb_rx_phy.vhd:134:7 */
  assign n552 = n489 ? n545 : 8'b00000000;
  /*# usb11_phy_vhdl/usb_rx_phy.vhd:134:7 */
  assign n553 = n491 & n489;
  /*# usb11_phy_vhdl/usb_rx_phy.vhd:134:7 */
  assign n554 = n491 & n489;
  /*# usb11_phy_vhdl/usb_rx_phy.vhd:197:32 */
  assign n567 = r_valid[0]; // extract
  /*# usb11_phy_vhdl/usb_rx_phy.vhd:201:21 */
  assign n570 = r_valid[0]; // extract
  /*# usb11_phy_vhdl/usb_rx_phy.vhd:201:29 */
  assign n571 = ~r_valid_prev;
  /*# usb11_phy_vhdl/usb_rx_phy.vhd:201:25 */
  assign n572 = n570 & n571;
  /*# usb11_phy_vhdl/usb_rx_phy.vhd:85:5 */
  always @(posedge clk)
    n574 <= n432;
  /*# usb11_phy_vhdl/usb_rx_phy.vhd:72:5 */
  assign n575 = n405 ? n407 : r_dif_shift;
  /*# usb11_phy_vhdl/usb_rx_phy.vhd:72:5 */
  always @(posedge clk)
    n576 <= n575;
  /*# usb11_phy_vhdl/usb_rx_phy.vhd:72:5 */
  always @(posedge clk)
    n577 <= n410;
  /*# usb11_phy_vhdl/usb_rx_phy.vhd:103:5 */
  assign n578 = n476 ? s_linebit : r_linebit_prev;
  /*# usb11_phy_vhdl/usb_rx_phy.vhd:103:5 */
  always @(posedge clk)
    n579 <= n578;
  /*# usb11_phy_vhdl/usb_rx_phy.vhd:133:5 */
  always @(posedge clk)
    n580 <= n550;
  /*# usb11_phy_vhdl/usb_rx_phy.vhd:103:5 */
  assign n581 = n477 ? n467 : r_data;
  /*# usb11_phy_vhdl/usb_rx_phy.vhd:103:5 */
  always @(posedge clk)
    n582 <= n581;
  /*# usb11_phy_vhdl/usb_rx_phy.vhd:103:5 */
  assign n583 = n478 ? r_data : r_data_latch;
  /*# usb11_phy_vhdl/usb_rx_phy.vhd:103:5 */
  always @(posedge clk)
    n584 <= n583;
  /*# usb11_phy_vhdl/usb_rx_phy.vhd:133:5 */
  always @(posedge clk)
    n585 <= n552;
  initial
    n585 = 8'b10000000;
  /*# usb11_phy_vhdl/usb_rx_phy.vhd:72:5 */
  always @(posedge clk)
    n586 <= n411;
  /*# usb11_phy_vhdl/usb_rx_phy.vhd:133:5 */
  assign n587 = n553 ? r_linestate : r_linestate_sync;
  /*# usb11_phy_vhdl/usb_rx_phy.vhd:133:5 */
  always @(posedge clk)
    n588 <= n587;
  /*# usb11_phy_vhdl/usb_rx_phy.vhd:103:5 */
  assign n589 = n479 ? n456 : r_idlecnt;
  /*# usb11_phy_vhdl/usb_rx_phy.vhd:103:5 */
  always @(posedge clk)
    n590 <= n589;
  initial
    n590 = 7'b1000000;
  /*# usb11_phy_vhdl/usb_rx_phy.vhd:133:5 */
  assign n591 = n554 ? n541 : r_preamble;
  /*# usb11_phy_vhdl/usb_rx_phy.vhd:133:5 */
  always @(posedge clk)
    n592 <= n591;
  /*# usb11_phy_vhdl/usb_rx_phy.vhd:72:5 */
  always @(posedge clk)
    n593 <= rx_en;
  /*# usb11_phy_vhdl/usb_rx_phy.vhd:196:7 */
  always @(posedge clk)
    n594 <= n567;
endmodule

module usb_tx_phy_Brtl
  (input  clk,
   input  rst,
   input  fs_ce,
   input  phy_mode,
   output txdp,
   output txdn,
   output txoe,
   input  linectrl_i,
   input  [7:0] dataout_i,
   input  txvalid_i,
   output txready_o);
  wire [7:0] hold_reg;
  wire ld_data;
  wire ld_data_d;
  wire ld_sop_d;
  wire r_linectrl_i;
  wire r_long_i;
  wire r_busreset_i;
  wire [15:0] bit_cnt;
  wire sft_done_e;
  wire any_eop_state;
  wire append_eop;
  wire se_state;
  wire data_xmit;
  wire [7:0] hold_reg_d;
  wire [2:0] one_cnt;
  wire sd_bs_o;
  wire sd_nrzi_o;
  wire sd_raw_o;
  wire sft_done;
  wire sft_done_r;
  wire [3:0] state;
  wire stuff;
  wire tx_ip;
  wire tx_ip_sync;
  wire txoe_r1;
  wire txoe_r2;
  wire s_long;
  wire n61;
  wire n63;
  wire n64;
  wire n65;
  wire n75;
  wire n78;
  wire n80;
  wire n86;
  wire n94;
  wire n96;
  wire n97;
  wire n98;
  wire n100;
  wire n102;
  wire n108;
  wire n110;
  wire n111;
  wire n112;
  wire [15:0] n114;
  wire [15:0] n115;
  wire [15:0] n117;
  wire n124;
  wire [2:0] n125;
  wire n130;
  wire n134;
  wire n136;
  wire n137;
  wire n138;
  wire [2:0] n139;
  wire n141;
  wire n142;
  wire n143;
  wire n145;
  wire n153;
  wire n154;
  wire n156;
  wire [7:0] n158;
  wire [7:0] n160;
  wire n169;
  wire n171;
  wire n172;
  wire n173;
  wire [2:0] n175;
  wire [2:0] n177;
  wire [2:0] n178;
  wire [2:0] n180;
  wire n187;
  wire n188;
  wire n191;
  wire n193;
  wire n195;
  wire n197;
  wire n204;
  wire n206;
  wire n207;
  wire n208;
  wire n209;
  wire n211;
  wire n212;
  wire n213;
  wire n214;
  wire n215;
  wire n221;
  wire n223;
  wire n224;
  wire n239;
  wire n241;
  wire n242;
  wire n243;
  wire n244;
  wire n245;
  wire n246;
  wire n247;
  wire n257;
  wire n259;
  wire n261;
  wire n262;
  wire n263;
  wire n264;
  wire n265;
  wire n266;
  wire [3:0] n268;
  wire n270;
  wire [3:0] n272;
  wire n274;
  wire n275;
  wire n276;
  wire n278;
  wire n279;
  wire n280;
  wire [3:0] n283;
  wire [3:0] n284;
  wire n286;
  wire [3:0] n288;
  wire n290;
  wire [3:0] n291;
  reg n292;
  reg n293;
  reg n294;
  reg [3:0] n296;
  wire n298;
  wire [3:0] n300;
  wire [3:0] n302;
  wire [3:0] n303;
  wire [3:0] n307;
  wire [1:0] n319;
  wire n321;
  wire n322;
  wire n326;
  wire n327;
  wire n328;
  wire n329;
  wire n330;
  wire n331;
  wire n334;
  wire n335;
  wire n338;
  wire n340;
  wire n341;
  wire n342;
  wire n343;
  wire n347;
  wire n348;
  wire n349;
  wire n351;
  reg n352;
  wire n353;
  reg n354;
  wire n355;
  reg n356;
  reg n357;
  reg [7:0] n358;
  reg n359;
  wire n360;
  wire n361;
  wire n362;
  reg n363;
  wire n364;
  wire n365;
  wire n366;
  reg n367;
  wire n368;
  wire n369;
  wire n370;
  reg n371;
  reg [15:0] n372;
  reg n373;
  reg [7:0] n374;
  reg [2:0] n375;
  wire n376;
  reg n377;
  reg n378;
  reg n379;
  reg n380;
  reg n381;
  reg [3:0] n382;
  reg n383;
  wire n384;
  reg n385;
  wire n386;
  reg n387;
  wire n388;
  reg n389;
  wire n390;
  assign txdp = n352; //(module output)
  assign txdn = n354; //(module output)
  assign txoe = n356; //(module output)
  assign txready_o = n357; //(module output)
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:83:10 */
  assign hold_reg = n358; // (signal)
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:84:10 */
  assign ld_data = n359; // (signal)
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:85:10 */
  assign ld_data_d = n343; // (signal)
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:86:10 */
  assign ld_sop_d = n335; // (signal)
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:87:10 */
  assign r_linectrl_i = n363; // (signal)
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:88:10 */
  assign r_long_i = n367; // (signal)
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:89:10 */
  assign r_busreset_i = n371; // (signal)
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:90:10 */
  assign bit_cnt = n372; // (signal)
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:91:10 */
  assign sft_done_e = n154; // (signal)
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:92:10 */
  assign any_eop_state = n257; // (signal)
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:93:10 */
  assign append_eop = n322; // (signal)
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:94:10 */
  assign se_state = n331; // (signal)
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:95:10 */
  assign data_xmit = n373; // (signal)
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:96:10 */
  assign hold_reg_d = n374; // (signal)
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:97:10 */
  assign one_cnt = n375; // (signal)
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:98:10 */
  assign sd_bs_o = n377; // (signal)
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:99:10 */
  assign sd_nrzi_o = n378; // (signal)
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:100:10 */
  assign sd_raw_o = n379; // (signal)
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:101:10 */
  assign sft_done = n380; // (signal)
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:102:10 */
  assign sft_done_r = n381; // (signal)
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:103:10 */
  assign state = n382; // (signal)
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:104:10 */
  assign stuff = n188; // (signal)
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:105:10 */
  assign tx_ip = n383; // (signal)
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:106:10 */
  assign tx_ip_sync = n385; // (signal)
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:107:10 */
  assign txoe_r1 = n387; // (signal)
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:107:19 */
  assign txoe_r2 = n389; // (signal)
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:108:10 */
  assign s_long = n349; // (signal)
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:129:12 */
  assign n61 = ~rst;
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:132:48 */
  assign n63 = r_linectrl_i & any_eop_state;
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:132:31 */
  assign n64 = ld_data_d | n63;
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:132:68 */
  assign n65 = n64 & txvalid_i;
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:149:12 */
  assign n75 = ~rst;
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:154:7 */
  assign n78 = append_eop ? 1'b0 : tx_ip;
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:152:7 */
  assign n80 = ld_sop_d ? 1'b1 : n78;
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:162:12 */
  assign n86 = ~rst;
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:177:12 */
  assign n94 = ~rst;
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:180:35 */
  assign n96 = ~tx_ip;
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:180:25 */
  assign n97 = n96 & txvalid_i;
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:182:23 */
  assign n98 = ~txvalid_i;
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:182:7 */
  assign n100 = n98 ? 1'b0 : data_xmit;
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:180:7 */
  assign n102 = n97 ? 1'b1 : n100;
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:195:12 */
  assign n108 = ~rst;
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:198:21 */
  assign n110 = ~tx_ip_sync;
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:200:34 */
  assign n111 = ~stuff;
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:200:24 */
  assign n112 = n111 & fs_ce;
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:201:28 */
  assign n114 = bit_cnt + 16'b0000000000000001;
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:200:7 */
  assign n115 = n112 ? n114 : bit_cnt;
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:198:7 */
  assign n117 = n110 ? 16'b0000000000000000 : n115;
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:210:21 */
  assign n124 = ~tx_ip_sync;
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:213:52 */
  assign n125 = bit_cnt[2:0]; // extract
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:210:7 */
  assign n130 = n124 ? 1'b0 : n390;
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:220:12 */
  assign n134 = ~rst;
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:224:17 */
  assign n136 = bit_cnt[15]; // extract
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:224:48 */
  assign n137 = r_linectrl_i & r_long_i;
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:224:32 */
  assign n138 = n136 == n137;
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:224:73 */
  assign n139 = bit_cnt[2:0]; // extract
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:224:86 */
  assign n141 = n139 == 3'b111;
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:224:62 */
  assign n142 = n141 & n138;
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:225:21 */
  assign n143 = ~stuff;
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:224:7 */
  assign n145 = n142 ? n143 : 1'b0;
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:233:30 */
  assign n153 = ~sft_done_r;
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:233:26 */
  assign n154 = sft_done & n153;
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:238:12 */
  assign n156 = ~rst;
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:244:7 */
  assign n158 = ld_data ? dataout_i : hold_reg;
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:242:7 */
  assign n160 = ld_sop_d ? 8'b10000000 : n158;
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:257:12 */
  assign n169 = ~rst;
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:260:21 */
  assign n171 = ~tx_ip_sync;
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:263:21 */
  assign n172 = ~sd_raw_o;
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:263:26 */
  assign n173 = n172 | stuff;
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:266:30 */
  assign n175 = one_cnt + 3'b001;
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:263:9 */
  assign n177 = n173 ? 3'b000 : n175;
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:262:7 */
  assign n178 = fs_ce ? n177 : one_cnt;
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:260:7 */
  assign n180 = n171 ? 3'b000 : n178;
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:272:31 */
  assign n187 = one_cnt == 3'b110;
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:272:18 */
  assign n188 = n187 ? 1'b1 : 1'b0;
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:276:12 */
  assign n191 = ~rst;
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:280:23 */
  assign n193 = ~tx_ip_sync;
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:283:11 */
  assign n195 = stuff ? 1'b0 : sd_raw_o;
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:280:9 */
  assign n197 = n193 ? 1'b0 : n195;
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:299:12 */
  assign n204 = ~rst;
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:302:21 */
  assign n206 = ~tx_ip_sync;
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:302:38 */
  assign n207 = ~txoe_r1;
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:302:27 */
  assign n208 = n206 | n207;
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:302:44 */
  assign n209 = n208 | r_linectrl_i;
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:303:9 */
  assign n211 = r_linectrl_i ? s_long : 1'b1;
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:312:24 */
  assign n212 = ~sd_nrzi_o;
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:309:9 */
  assign n213 = sd_bs_o ? sd_nrzi_o : n212;
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:308:7 */
  assign n214 = fs_ce ? n213 : sd_nrzi_o;
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:302:7 */
  assign n215 = n209 ? n211 : n214;
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:324:12 */
  assign n221 = ~rst;
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:332:33 */
  assign n223 = txoe_r1 | txoe_r2;
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:332:20 */
  assign n224 = ~n223;
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:343:12 */
  assign n239 = ~rst;
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:349:19 */
  assign n241 = ~se_state;
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:349:32 */
  assign n242 = n241 & sd_nrzi_o;
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:350:19 */
  assign n243 = ~se_state;
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:350:36 */
  assign n244 = ~sd_nrzi_o;
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:350:32 */
  assign n245 = n243 & n244;
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:348:9 */
  assign n246 = phy_mode ? n242 : sd_nrzi_o;
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:348:9 */
  assign n247 = phy_mode ? n245 : se_state;
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:363:25 */
  assign n257 = state[3]; // extract
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:367:12 */
  assign n259 = ~rst;
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:370:24 */
  assign n261 = ~any_eop_state;
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:374:53 */
  assign n262 = dataout_i[0]; // extract
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:375:57 */
  assign n263 = dataout_i[1]; // extract
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:372:30 */
  assign n264 = txvalid_i ? linectrl_i : r_linectrl_i;
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:372:30 */
  assign n265 = txvalid_i ? n262 : r_long_i;
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:372:30 */
  assign n266 = txvalid_i ? n263 : r_busreset_i;
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:372:30 */
  assign n268 = txvalid_i ? 4'b0001 : state;
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:372:11 */
  assign n270 = state == 4'b0000;
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:382:30 */
  assign n272 = sft_done_e ? 4'b0010 : state;
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:382:11 */
  assign n274 = state == 4'b0001;
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:385:43 */
  assign n275 = ~data_xmit;
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:385:48 */
  assign n276 = sft_done_e & n275;
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:386:43 */
  assign n278 = one_cnt == 3'b101;
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:386:65 */
  assign n279 = hold_reg_d[7]; // extract
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:386:51 */
  assign n280 = n279 & n278;
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:386:32 */
  assign n283 = n280 ? 4'b1000 : 4'b1001;
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:385:30 */
  assign n284 = n276 ? n283 : state;
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:385:11 */
  assign n286 = state == 4'b0010;
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:392:30 */
  assign n288 = fs_ce ? 4'b0000 : state;
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:392:11 */
  assign n290 = state == 4'b0011;
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:371:9 */
  assign n291 = {n290, n286, n274, n270};
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:371:9 */
  always @*
    case (n291)
      4'b1000: n292 = r_linectrl_i;
      4'b0100: n292 = r_linectrl_i;
      4'b0010: n292 = r_linectrl_i;
      4'b0001: n292 = n264;
      default: n292 = r_linectrl_i;
    endcase
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:371:9 */
  always @*
    case (n291)
      4'b1000: n293 = r_long_i;
      4'b0100: n293 = r_long_i;
      4'b0010: n293 = r_long_i;
      4'b0001: n293 = n265;
      default: n293 = r_long_i;
    endcase
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:371:9 */
  always @*
    case (n291)
      4'b1000: n294 = r_busreset_i;
      4'b0100: n294 = r_busreset_i;
      4'b0010: n294 = r_busreset_i;
      4'b0001: n294 = n266;
      default: n294 = r_busreset_i;
    endcase
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:371:9 */
  always @*
    case (n291)
      4'b1000: n296 = n288;
      4'b0100: n296 = n284;
      4'b0010: n296 = n272;
      4'b0001: n296 = n268;
      default: n296 = 4'b0000;
    endcase
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:399:20 */
  assign n298 = state == 4'b1101;
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:402:38 */
  assign n300 = state + 4'b0001;
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:399:11 */
  assign n302 = n298 ? 4'b0011 : n300;
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:398:9 */
  assign n303 = fs_ce ? n302 : state;
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:370:7 */
  assign n307 = n261 ? n296 : n303;
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:409:32 */
  assign n319 = state[3:2]; // extract
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:409:45 */
  assign n321 = n319 == 2'b11;
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:409:21 */
  assign n322 = n321 ? 1'b1 : 1'b0;
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:410:53 */
  assign n326 = state != 4'b0011;
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:410:67 */
  assign n327 = r_linectrl_i & n326;
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:410:90 */
  assign n328 = r_long_i & n327;
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:410:109 */
  assign n329 = r_busreset_i & n328;
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:410:43 */
  assign n330 = append_eop | n329;
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:410:21 */
  assign n331 = n330 ? 1'b1 : 1'b0;
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:411:39 */
  assign n334 = state == 4'b0000;
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:411:28 */
  assign n335 = n334 ? txvalid_i : 1'b0;
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:412:39 */
  assign n338 = state == 4'b0001;
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:412:61 */
  assign n340 = state == 4'b0010;
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:412:74 */
  assign n341 = data_xmit & n340;
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:412:51 */
  assign n342 = n338 | n341;
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:412:28 */
  assign n343 = n342 ? sft_done_e : 1'b0;
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:413:32 */
  assign n347 = state != 4'b0011;
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:413:46 */
  assign n348 = r_long_i & n347;
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:413:21 */
  assign n349 = n348 ? 1'b0 : 1'b1;
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:346:5 */
  assign n351 = fs_ce ? n246 : n352;
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:346:5 */
  always @(posedge clk or posedge n239)
    if (n239)
      n352 <= 1'b1;
    else
      n352 <= n351;
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:346:5 */
  assign n353 = fs_ce ? n247 : n354;
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:346:5 */
  always @(posedge clk or posedge n239)
    if (n239)
      n354 <= 1'b0;
    else
      n354 <= n353;
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:328:5 */
  assign n355 = fs_ce ? n224 : n356;
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:328:5 */
  always @(posedge clk or posedge n221)
    if (n221)
      n356 <= 1'b1;
    else
      n356 <= n355;
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:131:5 */
  always @(posedge clk or posedge n61)
    if (n61)
      n357 <= 1'b0;
    else
      n357 <= n65;
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:241:5 */
  always @(posedge clk or posedge n156)
    if (n156)
      n358 <= 8'b00000000;
    else
      n358 <= n160;
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:138:5 */
  always @(posedge clk)
    n359 <= ld_data_d;
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:87:10 */
  assign n360 = ~n259;
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:87:10 */
  assign n361 = n261 & n360;
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:369:5 */
  assign n362 = n361 ? n292 : r_linectrl_i;
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:369:5 */
  always @(posedge clk)
    n363 <= n362;
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:88:10 */
  assign n364 = ~n259;
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:88:10 */
  assign n365 = n261 & n364;
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:369:5 */
  assign n366 = n365 ? n293 : r_long_i;
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:369:5 */
  always @(posedge clk)
    n367 <= n366;
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:89:10 */
  assign n368 = ~n259;
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:89:10 */
  assign n369 = n261 & n368;
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:369:5 */
  assign n370 = n369 ? n294 : r_busreset_i;
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:369:5 */
  always @(posedge clk)
    n371 <= n370;
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:197:5 */
  always @(posedge clk or posedge n108)
    if (n108)
      n372 <= 16'b0000000000000000;
    else
      n372 <= n117;
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:179:5 */
  always @(posedge clk or posedge n94)
    if (n94)
      n373 <= 1'b0;
    else
      n373 <= n102;
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:241:5 */
  always @(posedge clk or posedge n156)
    if (n156)
      n374 <= 8'b00000000;
    else
      n374 <= hold_reg;
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:259:5 */
  always @(posedge clk or posedge n169)
    if (n169)
      n375 <= 3'b000;
    else
      n375 <= n180;
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:278:5 */
  assign n376 = fs_ce ? n197 : sd_bs_o;
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:278:5 */
  always @(posedge clk or posedge n191)
    if (n191)
      n377 <= 1'b0;
    else
      n377 <= n376;
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:301:5 */
  always @(posedge clk or posedge n204)
    if (n204)
      n378 <= 1'b1;
    else
      n378 <= n215;
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:209:5 */
  always @(posedge clk)
    n379 <= n130;
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:223:5 */
  always @(posedge clk or posedge n134)
    if (n134)
      n380 <= 1'b0;
    else
      n380 <= n145;
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:223:5 */
  always @(posedge clk or posedge n134)
    if (n134)
      n381 <= 1'b0;
    else
      n381 <= sft_done;
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:369:5 */
  always @(posedge clk or posedge n259)
    if (n259)
      n382 <= 4'b0000;
    else
      n382 <= n307;
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:151:5 */
  always @(posedge clk or posedge n75)
    if (n75)
      n383 <= 1'b0;
    else
      n383 <= n80;
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:164:5 */
  assign n384 = fs_ce ? tx_ip : tx_ip_sync;
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:164:5 */
  always @(posedge clk or posedge n86)
    if (n86)
      n385 <= 1'b0;
    else
      n385 <= n384;
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:328:5 */
  assign n386 = fs_ce ? tx_ip_sync : txoe_r1;
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:328:5 */
  always @(posedge clk or posedge n221)
    if (n221)
      n387 <= 1'b0;
    else
      n387 <= n386;
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:328:5 */
  assign n388 = fs_ce ? txoe_r1 : txoe_r2;
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:328:5 */
  always @(posedge clk or posedge n221)
    if (n221)
      n389 <= 1'b0;
    else
      n389 <= n388;
  /*# usb11_phy_vhdl/usb_tx_phy.vhd:213:32 */
  assign n390 = hold_reg_d[n125 * 1 +: 1]; //(Bmux)
endmodule

module usb_phy
  (input  clk,
   input  rst,
   input  phy_tx_mode,
   output usb_rst,
   input  rxd,
   input  rxdp,
   input  rxdn,
   output txdp,
   output txdn,
   output txoe,
   output ce_o,
   output sync_err_o,
   output bit_stuff_err_o,
   output byte_err_o,
   input  LineCtrl_i,
   input  [7:0] DataOut_i,
   input  TxValid_i,
   output TxReady_o,
   output [7:0] DataIn_o,
   output RxValid_o,
   output RxActive_o,
   output RxError_o,
   output [1:0] LineState_o);
  wire [1:0] linestate;
  wire fs_ce;
  wire [4:0] rst_cnt;
  wire txoe_out;
  reg usb_rst_out;
  wire reset;
  wire n19;
  wire \e_rx_phy_emard.clk_recovered ;
  wire \e_rx_phy_emard.rawdata ;
  wire \e_rx_phy_emard.rx_error ;
  localparam n25 = 1'b0;
  wire n27;
  wire n30;
  wire n31;
  wire n32;
  wire [4:0] n34;
  wire [4:0] n35;
  wire [4:0] n37;
  wire n45;
  wire n48;
  localparam n51 = 1'bX;
  localparam n52 = 1'bX;
  localparam n53 = 1'bX;
  reg [4:0] n54;
  reg n55;
  assign usb_rst = usb_rst_out; //(module output)
  assign txoe = txoe_out; //(module output)
  assign ce_o = fs_ce; //(module output)
  assign sync_err_o = n51; //(module output)
  assign bit_stuff_err_o = n52; //(module output)
  assign byte_err_o = n53; //(module output)
  assign RxError_o = n25; //(module output)
  assign LineState_o = linestate; //(module output)
  /*# usb11_phy_vhdl/usb_phy.vhd:113:10 */
  assign rst_cnt = n54; // (signal)
  /*# usb11_phy_vhdl/usb_phy.vhd:115:10 */
  always @*
    usb_rst_out = n55; // (isignal)
  initial
    usb_rst_out = 1'b0;
  /*# usb11_phy_vhdl/usb_phy.vhd:116:10 */
  assign reset = n19; // (signal)
  /*# usb11_phy_vhdl/usb_phy.vhd:132:3 */
  usb_tx_phy_Brtl i_tx_phy (
    .clk(clk),
    .rst(rst),
    .fs_ce(fs_ce),
    .phy_mode(phy_tx_mode),
    .linectrl_i(LineCtrl_i),
    .dataout_i(DataOut_i),
    .txvalid_i(TxValid_i),
    .txdp(txdp),
    .txdn(txdn),
    .txoe(txoe_out),
    .txready_o(TxReady_o));
  /*# usb11_phy_vhdl/usb_phy.vhd:152:12 */
  assign n19 = ~rst;
  /*# usb11_phy_vhdl/usb_phy.vhd:153:3 */
  usb_rx_phy_Bbehavioral_6000000_1500000_8 e_rx_phy_emard (
    .clk(clk),
    .reset(reset),
    .usb_dif(rxd),
    .usb_dp(rxdp),
    .usb_dn(rxdn),
    .rx_en(txoe_out),
    .linestate(linestate),
    .clk_recovered(),
    .clk_recovered_edge(fs_ce),
    .rawdata(),
    .rx_active(RxActive_o),
    .rx_error(),
    .valid(RxValid_o),
    .data(DataIn_o));
  /*# usb11_phy_vhdl/usb_phy.vhd:179:14 */
  assign n27 = ~rst;
  /*# usb11_phy_vhdl/usb_phy.vhd:182:22 */
  assign n30 = linestate != 2'b00;
  /*# usb11_phy_vhdl/usb_phy.vhd:184:27 */
  assign n31 = ~usb_rst_out;
  /*# usb11_phy_vhdl/usb_phy.vhd:184:32 */
  assign n32 = fs_ce & n31;
  /*# usb11_phy_vhdl/usb_phy.vhd:185:30 */
  assign n34 = rst_cnt + 5'b00001;
  /*# usb11_phy_vhdl/usb_phy.vhd:184:9 */
  assign n35 = n32 ? n34 : rst_cnt;
  /*# usb11_phy_vhdl/usb_phy.vhd:182:9 */
  assign n37 = n30 ? 5'b00000 : n35;
  /*# usb11_phy_vhdl/usb_phy.vhd:193:20 */
  assign n45 = rst_cnt == 5'b11111;
  /*# usb11_phy_vhdl/usb_phy.vhd:193:9 */
  assign n48 = n45 ? 1'b1 : 1'b0;
  /*# usb11_phy_vhdl/usb_phy.vhd:181:7 */
  always @(posedge clk or posedge n27)
    if (n27)
      n54 <= 5'b00000;
    else
      n54 <= n37;
  /*# usb11_phy_vhdl/usb_phy.vhd:192:7 */
  always @(posedge clk)
    n55 <= n48;
  initial
    n55 = 1'b0;
endmodule

