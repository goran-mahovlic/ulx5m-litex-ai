// Test top for the Migen port (gateware/usb_pnru.py, converted by sim/tb_usb_pnru.py to usb_pnru_dut.v), TASK-5051.
// Same USB line model as tb_ref_top.v; the registers are LiteX CSRs on a csr_bus (32-bit words).
`timescale 1ns/1ps
`default_nettype none
module tb_mig_top (
    input  wire        sys_clk,
    input  wire        sys_rst,
    input  wire        usb_clk,
    input  wire        usb_rst,
    input  wire [13:0] csr_adr,
    input  wire        csr_we,
    input  wire [31:0] csr_dat_w,
    output wire [31:0] csr_dat_r,
    input  wire        csr_re,
    output wire        irq,
    input  wire        dev_oe,
    input  wire        dev_dp,
    input  wire        dev_dn,
    input  wire [1:0]  dev_pull,
    output wire        line_dp,
    output wire        line_dn,
    output wire        host_oe
);
    wire usb_dp, usb_dn;
    wire dp_o, dn_o, oe;
    assign usb_dp = oe ? dp_o : 1'bz;
    assign usb_dn = oe ? dn_o : 1'bz;
    assign usb_dp = dev_oe ? dev_dp : 1'bz;
    assign usb_dn = dev_oe ? dev_dn : 1'bz;
    // Icarus drops the strength of `assign (pull1, highz0) net = <expression>`: go through plain wires.
    wire pull_dp = (dev_pull == 2'd1);
    wire pull_dn = (dev_pull == 2'd2);
    assign (pull1, highz0) usb_dp = pull_dp;
    assign (pull1, highz0) usb_dn = pull_dn;
    assign (highz1, weak0) usb_dp = 1'b0;
    assign (highz1, weak0) usb_dn = 1'b0;
    assign line_dp = usb_dp;
    assign line_dn = usb_dn;
    assign host_oe = oe;

    usb_pnru_dut dut (
        .sys_clk(sys_clk), .sys_rst(sys_rst), .usb_clk(usb_clk), .usb_rst(usb_rst),
        .csr_adr(csr_adr), .csr_we(csr_we), .csr_dat_w(csr_dat_w), .csr_dat_r(csr_dat_r), .csr_re(csr_re),
        .irq(irq),
        .usb_dp_o(dp_o), .usb_dn_o(dn_o), .usb_oe(oe), .usb_dp_i(usb_dp === 1'b1), .usb_dn_i(usb_dn === 1'b1)
    );
endmodule
