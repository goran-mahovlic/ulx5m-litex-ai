// Behavioural stubs for GateMate blackboxes (post-synthesis simulation, TASK-4999).
`timescale 1ns/1ps
module CC_PLL #(
    parameter REF_CLK = "", parameter OUT_CLK = "", parameter PERF_MD = "",
    parameter LOCK_REQ = 1, parameter CLK270_DOUB = 0, parameter CLK180_DOUB = 0,
    parameter LOW_JITTER = 1, parameter CI_FILTER_CONST = 2, parameter CP_FILTER_CONST = 4
)(
    input  CLK_REF, CLK_FEEDBACK, USR_CLK_REF, USR_LOCKED_STDY_RST,
    output reg USR_PLL_LOCKED_STDY, output reg USR_PLL_LOCKED,
    output reg CLK270, output reg CLK180, output reg CLK90, output reg CLK0, output CLK_REF_OUT
);
    real half;
    initial begin
        half = (OUT_CLK == "12.5") ? 40.0 : (OUT_CLK == "6.25") ? 80.0 : (OUT_CLK == "16.0") ? 31.25 : (OUT_CLK == "50.0") ? 10.0 : 20.0;
        CLK0 = 0; CLK90 = 0; CLK180 = 1; CLK270 = 1;
        USR_PLL_LOCKED = 0; USR_PLL_LOCKED_STDY = 0;
        #2000 USR_PLL_LOCKED = 1; USR_PLL_LOCKED_STDY = 1;
    end
    always #(half) CLK0 = ~CLK0;
    always @(CLK0) begin
        CLK90  <= #(half/2.0) CLK0;
        CLK180 <= ~CLK0;
        CLK270 <= #(half/2.0) ~CLK0;
    end
    assign CLK_REF_OUT = CLK_REF;
endmodule

module CC_USR_RSTN (output reg USR_RSTN);
    initial begin USR_RSTN = 0; #500 USR_RSTN = 1; end
endmodule
