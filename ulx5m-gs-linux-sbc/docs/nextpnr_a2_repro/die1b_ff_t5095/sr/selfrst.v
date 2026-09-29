// selfrst.v (TASK-5095): design-driven chip reset for the ULX5M-GS. On this board the FPGA ball RST_N (U4.T15) and
// the user IO IO_SB_B8 (U4.N15) are the same net (R111 10k to +1V8, C138 100 nF; ulx5m-gs-hw 61b6709). A design can
// therefore reset its own chip: after the UART bytes "R!" (0x52 0x21, 8N1, 115200 at 25 MHz) rst_oe goes to 1 and stays
// there until the chip resets; the top level drives IO_SB_B8 low only while rst_oe = 1 (open drain, otherwise high-Z). The reset tri-states
// every IO, so the pin releases itself and R111/C138 give a rising edge ~1 ms later - no path can hold RST_N low
// for good. Any other byte (0x00 from uart_nr.sh, a lone "R" or "!") does nothing.
// GateMate does not apply FF init values, so the enable is a 16-bit key that only the byte sequence writes: a random
// start state asserts it with p = 2^-16, a cleared one (all 0) never.
module selfrst (input clk, input rx, output rst_oe);
  reg [15:0] key = 16'h0000;
  assign rst_oe = (key == 16'hA55A);
  reg rx1 = 1'b1, rx2 = 1'b1;
  reg [7:0] div = 0; reg [3:0] bitn = 0; reg [7:0] sh = 0; reg busy = 0; reg got_r = 0;
  always @(posedge clk) begin
    rx1 <= rx; rx2 <= rx1;
    if (!busy) begin
      if (!rx2) begin busy <= 1; div <= 108; bitn <= 0; end     // start bit: sample at mid-bit
    end else if (div == 216) begin
      div <= 0; bitn <= bitn + 1;
      if (bitn == 0) begin if (rx2) busy <= 0; end               // false start
      else if (bitn <= 8) sh <= {rx2, sh[7:1]};
      else begin                                                  // stop bit
        busy <= 0;
        if (rx2) begin
          if (got_r && sh == 8'h21) key <= 16'hA55A;
          got_r <= (sh == 8'h52);
        end else got_r <= 0;
      end
    end else div <= div + 1;
  end
endmodule
