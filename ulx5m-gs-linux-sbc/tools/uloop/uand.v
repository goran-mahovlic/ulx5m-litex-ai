module top(input [33:0] rx, output tx, output tx2);
  wire a = &rx; assign tx = a; assign tx2 = a;
endmodule
