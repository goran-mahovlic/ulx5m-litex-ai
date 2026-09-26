// TASK-4999 io50 RTL sim: the generated LiteEth SoC (io50 TX, mdio_core, L2 beacon) receives ICMP echo
// requests of several sizes on RGMII RX (100M: nibble per RXC, low nibble first, stable at the rising
// edge) and answers ARP requests with a fixed ARP reply. TX is decoded like the KSZ9031: TXD and
// TX_CTL on the TXC rising edge; TX_CTL must be equal on the falling edge (else TX_ER).
`timescale 1ns/1ps
module tb;
  reg clk25 = 0; always #20 clk25 = ~clk25;
  reg rxc = 0; initial #7 forever #20 rxc = ~rxc;          // PHY clock: independent phase
  reg rx_ctl = 0; reg [3:0] rxd = 0;
  wire txc, tx_ctl, mdc, rst_n; wire [3:0] txd; wire mdio; pullup(mdio);
  intergalaktik_ulx5m_gs dut(.clk25(clk25), .eth_clocks_rx(rxc), .eth_clocks_tx(txc), .eth_mdc(mdc),
      .eth_mdio(mdio), .eth_rst_n(rst_n), .eth_rx_ctl(rx_ctl), .eth_rx_data(rxd), .eth_tx_ctl(tx_ctl),
      .eth_tx_data(txd), .mdio_core_uart0(), .mdio_core_uart1(), .status_led0(), .status_led1(),
      .status_led2(), .status_led3(), .status_led4(), .status_led5(), .status_led6(), .status_led7());
  reg [7:0] rxb [0:4095]; reg [31:0] rxi [0:31];
  initial begin $readmemh("rx_bytes.memh", rxb); $readmemh("rx_index.memh", rxi); end
  task send(input integer k);
    integer p, n, i;
    begin
      p = rxi[2*k]; n = rxi[2*k+1];
      for (i = 0; i < 2*n; i = i + 1) begin
        @(negedge rxc); rx_ctl <= 1; rxd <= (i % 2) ? rxb[p + i/2][7:4] : rxb[p + i/2][3:0];
      end
      @(negedge rxc); rx_ctl <= 0; rxd <= 0;
      repeat (24) @(negedge rxc);
    end
  endtask
  // ---- TX decoder ----
  integer f, nb, frames = 0, txer = 0; reg [3:0] lo; reg have = 0, inf = 0, en_r = 0;
  reg [7:0] fb [0:2047]; reg arp_req = 0;
  always @(posedge txc) begin
    en_r = tx_ctl;
    if (tx_ctl) begin
      if (!inf) begin inf = 1; have = 0; nb = 0; end
      if (!have) begin lo = txd; have = 1; end else begin fb[nb] = {txd, lo}; nb = nb + 1; have = 0; end
    end else if (inf) begin : fin
      integer i;
      inf = 0; frames = frames + 1;
      for (i = 0; i < nb; i = i + 1) $fwrite(f, "%02x", fb[i]);
      $fwrite(f, "\n"); $fflush(f);
      $display("t=%0t us TX frame %0d: %0d B, ethertype %02x%02x", $time/1000, frames, nb, fb[20], fb[21]);
      if (fb[20] == 8'h08 && fb[21] == 8'h06 && fb[29] == 8'h01) arp_req = 1;
    end
  end
  always @(negedge txc) if (tx_ctl !== en_r) txer = txer + 1;
  initial forever begin #50000; $display("progress t=%0t us", $time/1000); $fflush; end
  initial begin : main
    integer k, w;
    f = $fopen("frames_tx.txt", "w");
    #(2500000);                                        // 2.5 ms: resets, PLL stubs, PHY reset, LiteEth ready
    for (k = 1; k <= `NREQ; k = k + 1) begin
      arp_req = 0;
      $display("t=%0t us RX ICMP request %0d", $time/1000, k); $fflush;
      send(k);
      for (w = 0; w < 400 && !arp_req; w = w + 1) #1000;
      if (arp_req) begin #5000; $display("t=%0t us RX ARP reply", $time/1000); send(0); end
      #400000;
    end
    $display("END frames=%0d TX_ER=%0d", frames, txer); $fclose(f); $finish;
  end
endmodule
