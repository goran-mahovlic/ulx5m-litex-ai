// empty.v (TASK-5096): "reset" design - no logic, UART TX held idle-high. Loaded between two real designs.
module top(output uart_tx);
  assign uart_tx = 1'b1;
endmodule
