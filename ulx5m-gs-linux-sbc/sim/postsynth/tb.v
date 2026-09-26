// Post-synthesis testbench (TASK-4999): does the SYNTHESISED design put a valid frame on the
// RGMII TX pins? Decodes TX_CTL/TXD on TXC rising edges (100M: one nibble per clock, low first),
// prints every frame and checks the FCS in Python afterwards (frames.txt).
`timescale 1ns/1ps
module tb;
    reg clk25 = 0; always #20 clk25 = ~clk25;
    reg rxc = 0;   always #20 rxc = ~rxc;
    wire txc, tx_ctl, mdc, refclk, rst_n;
    wire [3:0] txd;
    wire mdio;
    pullup(mdio);
    intergalaktik_ulx5m_gs dut (
        .clk25(clk25), .eth_clocks_rx(rxc), .eth_clocks_tx(txc), .eth_mdc(mdc), .eth_mdio(mdio),
        .eth_refclk(refclk), .eth_rst_n(rst_n), .eth_rx_ctl(1'b0), .eth_rx_data(4'h0),
        .eth_tx_ctl(tx_ctl), .eth_tx_data(txd),
        .status_led0(), .status_led1(), .status_led2(), .status_led3(),
        .status_led4(), .status_led5(), .status_led6(), .status_led7()
    );
    integer f, n, frames;
    reg [3:0] lo; reg have_lo; reg in_frame;
    initial begin
        f = $fopen("frames.txt", "w"); frames = 0; in_frame = 0; have_lo = 0;
        #(`SIMTIME);
        $display("END: %0d frames, rst_n=%b", frames, rst_n);
        $fclose(f); $finish;
    end
    always @(posedge txc) begin
        if (tx_ctl) begin
            if (!in_frame) begin in_frame = 1; have_lo = 0; n = 0; end
            if (!have_lo) begin lo = txd; have_lo = 1; end
            else begin $fwrite(f, "%02x", {txd, lo}); have_lo = 0; n = n + 1; end
        end else if (in_frame) begin
            in_frame = 0; frames = frames + 1;
            $fwrite(f, "\n");
            $display("t=%0t frame %0d: %0d bytes", $time, frames, n);
        end
    end
endmodule
