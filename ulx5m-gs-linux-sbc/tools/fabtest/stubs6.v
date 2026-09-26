module CC_BUFG(input I, output O); assign O = I; endmodule
module CC_LUT1 #(parameter [1:0] INIT = 2'b00) (input I0, output O); assign #1 O = INIT[I0]; endmodule
module CC_PLL #(parameter REF_CLK="", OUT_CLK="", PERF_MD="", LOW_JITTER=0, CI_FILTER_CONST=0, CP_FILTER_CONST=0, LOCK_REQ=0)
  (input CLK_REF, input USR_CLK_REF, input CLK_FEEDBACK, input USR_LOCKED_STDY_RST, output CLK0); assign CLK0 = USR_CLK_REF; endmodule
