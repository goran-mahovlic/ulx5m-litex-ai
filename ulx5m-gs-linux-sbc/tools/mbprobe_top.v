module top(input clk25);
  reg [31:0] cnt = 0; always @(posedge clk25) cnt <= cnt + 1;
  reg [3:0] rc = 0; wire rst = ~&rc; always @(posedge clk25) if (!(&rc)) rc <= rc + 1;
  wire [15:0] ri;
  jtag_mailbox mb (.clk(clk25), .rst(rst),
     .w16({16'h6666, 16'h5555, 16'h4444, 16'h3333, cnt[31:16], cnt[15:0]}),
     .rdy_info(ri), .w15({ri[14:0],15'h7008,15'h7008,15'h7007,15'h7006,15'h7005,15'h7004,15'h7003,15'h7002,15'h7001}));
endmodule
