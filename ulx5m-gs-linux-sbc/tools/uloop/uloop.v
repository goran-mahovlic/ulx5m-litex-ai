// TASK-4999: clock-free UART path test. RP2040 TX (CM4 GPIO15 = IO_NA_B4) looped straight back to
// RP2040 RX (GPIO14 = IO_NA_A4) and GPIO5 (IO_NB_B5). Echo on ttyACMx <=> the bridge + carrier work.
module top(input rx, output tx, output tx2);
  assign tx = rx;
  assign tx2 = rx;
endmodule
