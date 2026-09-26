`timescale 1ns/1ps
module CC_DFF #(
	parameter [0:0] CLK_INV = 1'b0,
	parameter [0:0] EN_INV  = 1'b0,
	parameter [0:0] SR_INV  = 1'b0,
	parameter [0:0] SR_VAL  = 1'b0,
	parameter [0:0] INIT    = 1'bx
)(
	input D,
	(* clkbuf_sink *)
	input CLK,
	input EN,
	input SR,
	output reg Q
);
	wire clk, en, sr;
	assign clk = (CLK_INV) ? ~CLK : CLK;
	assign en  = (EN_INV)  ?  ~EN :  EN;
	assign sr  = (SR_INV)  ?  ~SR :  SR;

	initial Q = INIT;

	always @(posedge clk or posedge sr)
	begin
		if (sr) begin
			Q <= SR_VAL;
		end
		else if (en) begin
			Q <= D;
		end
	end

endmodule

module CC_IDDR #(
	parameter [0:0] CLK_INV = 1'b0
)(
	input D,
	(* clkbuf_sink *)
	input CLK,
	output reg Q0, Q1
);
	wire clk;
	assign clk = (CLK_INV) ? ~CLK : CLK;

	always @(posedge clk)
	begin
		Q0 <= D;
	end

	always @(negedge clk)
	begin
		Q1 <= D;
	end

endmodule
